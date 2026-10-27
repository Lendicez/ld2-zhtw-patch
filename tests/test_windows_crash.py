import hashlib,json,os,sys,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ld2patch.windows_fixture import NativeFixture,FixtureRefusal
from ld2patch.windows_capture import ORIGINAL,PATCHED,encode,token
from ld2patch.windows_crash_fixture import (REGISTERED_NAMES,INSTALL_PHASES,RESTORE_PHASES,
    register_fixture,validate_registration,metadata,stable_metadata)
import owned_worker
from owned_worker import OwnedWorker,WorkerUnavailable,validate_identity


class WorkerIdentityTests(unittest.TestCase):
    def sample(self):
        identity={'pid':123,'created':456,'image':'X:\\fixture\\python.exe'}
        command={'ProcessId':123,'ExecutablePath':identity['image'],'CommandLine':'expected command'}
        hello={'pid':123,'argv':['worker.py'],'nonce':'a'*32}
        return identity,command,hello
    def test_pid_creation_image_command_nonce_mismatches_block_termination(self):
        i,c,h=self.sample()
        validate_identity(i,i,123,i['image'],c,'expected command',h,['worker.py'],'a'*32)
        variants=[({**i,'created':457},c,h),({**i,'pid':124},c,h),({**i,'image':'X:\\Ld95.exe'},c,h),
            (i,{**c,'CommandLine':'different'},h),(i,{**c,'ExecutablePath':None},h),
            (i,c,{**h,'nonce':'b'*32}),(i,c,{**h,'argv':['other.py']}),(i,c,{**h,'pid':999})]
        for current,command,hello in variants:
            with self.subTest(current=current,command=command),self.assertRaises(FixtureRefusal):
                validate_identity(i,current,123,i['image'],command,'expected command',hello,['worker.py'],'a'*32)
    def registration(self):
        from ld2patch.windows_crash_fixture import RECIPE,digest
        return {'schema':1,'recipe':RECIPE,'leaf':'ld2-native-abcdefgh','root':{'volume':1,'file_id':'0'*32},
            'original':{'volume':1,'file_id':'1'*32},'metadata':{'attributes':32,'created':1,'written':2,'accessed':3},
            'source_sha256':digest(ORIGINAL),'output_sha256':digest(PATCHED),'nonce':'a'*32}
    def test_registration_rejects_paths_versions_hashes_and_extra_fields(self):
        good=self.registration();self.assertEqual(validate_registration(encode(good)),good)
        for key,value in [('leaf','../outside'),('leaf','C:\\game'),('recipe','unknown'),('source_sha256','0'*64),
                          ('schema',True),('nonce',[]),('root',None),('metadata',{'attributes':32})]:
            with self.subTest(key=key),self.assertRaises(FixtureRefusal):validate_registration(encode({**good,key:value}))
        with self.assertRaises(FixtureRefusal):validate_registration(encode({**good,'command':'anything'}))
    def test_registration_duplicate_key_rejected(self):
        with self.assertRaises(FixtureRefusal):validate_registration(b'{"schema":1,"schema":1}')


PARENT=os.environ.get('LD2_CRASH_FIXTURE_PARENT')
@unittest.skipUnless(os.name=='nt' and PARENT,'requires explicit owned Windows worker crash fixture')
class WindowsWorkerCrashTests(unittest.TestCase):
    def setUp(self):
        if owned_worker.BLOCKED:self.skipTest('previous worker action blocked; no retry: '+owned_worker.BLOCKED)
        self.f=NativeFixture(Path(PARENT),REGISTERED_NAMES)
        self.addCleanup(self.f.stack.close)
        self.f.create('target.bin',ORIGINAL);self.f.create('save.bin',b'SYNTHETIC SAVE UNCHANGED')
        self.r=register_fixture(self.f,uuid.uuid4().hex)
        # Independent control-plane receipt outside the worker's fixture root.
        self.receipt=Path(PARENT)/('receipt-'+self.f.root.name+'.json')
        self.receipt.write_bytes(encode(self.r));self.receipt_hash=hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        self.addCleanup(lambda:self.assertEqual(self.f.read('save.bin'),b'SYNTHETIC SAVE UNCHANGED'))
    def registration_from_disk(self):
        data=self.receipt.read_bytes()
        if len(data)>16384 or hashlib.sha256(data).hexdigest()!=self.receipt_hash:
            raise FixtureRefusal('independent receipt changed')
        return validate_registration(data)
    def worker(self,mode,pause=None):
        w=OwnedWorker(self.f.parent,self.registration_from_disk(),mode,pause)
        self.addCleanup(w.close);return w
    def terminate(self,w):
        try:return w.kill_at_pause()
        except WorkerUnavailable as e:self.skipTest(str(e))
    def finish_ok(self,w):
        code,event=w.finish();self.assertEqual(code,0,event);self.assertEqual(event['event'],'result')
        return event['result']
    def assert_original(self,name='target.bin'):
        with self.f.open(name) as h:
            self.assertEqual(h.read(),ORIGINAL)
            self.assertEqual(token(h.identity()),self.r['original'])
            self.assertEqual(stable_metadata(metadata(h)),stable_metadata(self.r['metadata']))
    def install_crash(self,phase):
        killed=self.worker('install',phase);self.terminate(killed)
        if phase in ('captured','promote-intent','promoted','committed'):self.assert_original('captured.bin')
        else:self.assert_original()
        if phase in ('captured','promote-intent'):self.assertFalse(self.f.path('target.bin').exists())
        if phase in ('promoted','committed'):self.assertEqual(self.f.read('target.bin'),PATCHED)
        recovered=self.worker('restore');self.assertNotEqual(killed.initial['created'],recovered.initial['created'])
        self.finish_ok(recovered);self.assert_original()
        before={p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
        self.finish_ok(self.worker('restore'));self.assert_original()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})
    def restore_crash(self,phase):
        self.finish_ok(self.worker('install'))
        killed=self.worker('restore',phase);self.terminate(killed)
        if phase=='restore-gap':
            self.assertFalse(self.f.path('target.bin').exists());self.assert_original('captured.bin')
        else:self.assert_original()
        self.finish_ok(self.worker('restore'));self.assert_original()
        self.finish_ok(self.worker('restore'));self.assert_original()
    def change(self,name,data):
        with self.f.path(name).open('r+b') as f:f.seek(0);f.write(data);f.truncate();f.flush();os.fsync(f.fileno())
    def test_tampered_prepared_journal_after_kill_refused(self):
        self.terminate(self.worker('install','promoted'))
        self.change('txn-prepared.json',b'{"schema":1,"path":"../outside"}')
        before={p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
        code,event=self.worker('restore').finish();self.assertEqual(code,2);self.assertEqual(event['event'],'error')
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})
    def test_modified_target_after_kill_refused(self):
        self.terminate(self.worker('install','promoted'));self.change('target.bin',b'EXTERNAL CHANGE')
        code,event=self.worker('restore').finish();self.assertEqual(code,2,event)
        self.assertEqual(self.f.read('target.bin'),b'EXTERNAL CHANGE');self.assert_original('captured.bin')
    def test_unknown_restore_destination_is_retained(self):
        self.terminate(self.worker('install','promoted'));self.f.create('revoked.bin',b'UNKNOWN FILE')
        code,event=self.worker('restore').finish();self.assertEqual(code,2,event)
        self.assertEqual(self.f.read('target.bin'),PATCHED)
        self.assertEqual(self.f.read('revoked.bin'),b'UNKNOWN FILE');self.assert_original('captured.bin')
    def test_disk_registration_not_trusted_over_control_receipt(self):
        bad={**self.r,'recipe':'unknown'};self.change('fixture-registration.json',encode(bad))
        before={p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
        code,event=self.worker('install').finish();self.assertEqual(code,2,event)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})
    def test_independent_receipt_hash_is_required(self):
        self.receipt.write_bytes(b'{}')
        with self.assertRaisesRegex(FixtureRefusal,'receipt changed'):self.worker('restore')
        self.assert_original()


def install_case(phase):
    def test(self):self.install_crash(phase)
    return test
def restore_case(phase):
    def test(self):self.restore_crash(phase)
    return test
for phase in INSTALL_PHASES:setattr(WindowsWorkerCrashTests,'test_kill_install_'+phase.replace('-','_'),install_case(phase))
for phase in RESTORE_PHASES:setattr(WindowsWorkerCrashTests,'test_kill_restore_'+phase.replace('-','_'),restore_case(phase))


if __name__=='__main__':unittest.main()
