import json,os,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ld2patch.windows_capture import (CaptureExperiment,ORIGINAL,PATCHED,NAMES,
    InjectedFault,InjectedInterruption,parse_prepared,encode,digest,token)
from ld2patch.windows_fixture import NativeFixture,FixtureRefusal,NativeFailure


class CaptureSchemaTests(unittest.TestCase):
    def record(self):
        ids=[{'volume':1,'file_id':str(n)*32} for n in range(4)]
        return {'schema':1,'root':ids[0],'original':ids[1],'backup':ids[2],'stage':ids[3],
                'source_sha256':digest(ORIGINAL),'output_sha256':digest(PATCHED)}
    def test_schema_rejects_malformed_shapes_before_native_calls(self):
        good=self.record()
        for key,values in {'schema':[True,[],{},None,2],
            'original':[[],{},None,{'volume':True,'file_id':'1'*32}],
            'stage':[{'volume':2,'file_id':'3'*32},{'volume':1,'file_id':'../target'}],
            'source_sha256':['0'*64,[],None]}.items():
            for value in values:
                bad=dict(good);bad[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(FixtureRefusal):
                    parse_prepared(encode(bad),good['root'],good['original'])
    def test_root_and_original_must_match_independent_evidence(self):
        good=self.record()
        self.assertEqual(parse_prepared(encode(good),good['root'],good['original']),good)
        for root,original in [(good['backup'],good['original']),(good['root'],good['stage'])]:
            with self.assertRaises(FixtureRefusal):parse_prepared(encode(good),root,original)
    def test_duplicate_keys_and_unknown_fields_rejected(self):
        good=self.record()
        for bad in [b'{"schema":1,"schema":1}',encode({**good,'path':'target.bin'}),b'null',b'[]',b'not-json']:
            with self.assertRaises(FixtureRefusal):parse_prepared(bad,good['root'],good['original'])
    def test_identity_aliases_rejected(self):
        good=self.record();good['stage']=good['backup']
        with self.assertRaises(FixtureRefusal):parse_prepared(encode(good),good['root'],good['original'])


PARENT=os.environ.get('LD2_CAPTURE_FIXTURE_PARENT')
@unittest.skipUnless(os.name=='nt' and PARENT,'requires explicit fresh Windows capture fixture parent')
class WindowsCaptureTests(unittest.TestCase):
    def setUp(self):
        self.f=NativeFixture(Path(PARENT),NAMES)
        self.addCleanup(self.f.stack.close)
        self.initial=self.f.create('target.bin',ORIGINAL)
        self.f.create('save.bin',b'SYNTHETIC SAVE UNCHANGED')
        self.addCleanup(lambda:self.assertEqual(self.f.read('save.bin'),b'SYNTHETIC SAVE UNCHANGED'))
    def experiment(self,guard=lambda:'clear',hook=None):
        return CaptureExperiment(self.f,self.initial,guard,hook)
    def state(self):
        return {p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
    def change(self,name,data):
        with self.f.path(name).open('r+b') as f:
            f.seek(0);f.write(data);f.truncate();f.flush();os.fsync(f.fileno())
    def fault(self,when,cls=InjectedFault):
        def hook(phase):
            if phase==when:raise cls(phase)
        return hook

    def test_install_then_restore_same_original_identity(self):
        x=self.experiment();result=x.install()
        self.assertEqual(result['status'],'committed_fixture');self.assertFalse(result['can_apply'])
        self.assertEqual(self.f.read('target.bin'),PATCHED)
        self.assertEqual(self.f.read('captured.bin'),ORIGINAL)
        self.assertEqual(self.f.read('backup.bin'),ORIGINAL)
        self.assertEqual(x.restore()['status'],'rolled_back')
        with self.f.open('target.bin') as h:self.assertEqual(token(h.identity()),token(self.initial))
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertEqual(self.f.read('revoked.bin'),PATCHED)
        before=self.state();self.assertEqual(x.restore()['status'],'already_original')
        self.assertEqual(self.state(),before)

    def test_unknown_process_initially_performs_no_writes(self):
        before=self.state()
        for state in ('unknown','running',None,False):
            with self.subTest(state=state),self.assertRaisesRegex(FixtureRefusal,'process state'):
                self.experiment(lambda:state).install()
            self.assertEqual(self.state(),before)

    def test_process_becomes_unknown_before_capture(self):
        status=['clear']
        def hook(phase):
            if phase=='prepared':status[0]='unknown'
        with self.assertRaisesRegex(FixtureRefusal,'process state'):
            self.experiment(lambda:status[0],hook).install()
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertFalse(self.f.path('captured.bin').exists())

    def test_process_unknown_after_capture_retains_original_for_explicit_restore(self):
        status=['clear']
        def hook(phase):
            if phase=='captured':status[0]='unknown'
        with self.assertRaisesRegex(FixtureRefusal,'process state'):
            self.experiment(lambda:status[0],hook).install()
        self.assertFalse(self.f.path('target.bin').exists())
        self.assertEqual(self.f.read('captured.bin'),ORIGINAL)
        before=self.state()
        with self.assertRaises(FixtureRefusal):self.experiment(lambda:'unknown').restore()
        self.assertEqual(self.state(),before)

    def test_external_change_before_install_refused_without_staging(self):
        self.change('target.bin',b'EXTERNAL CHANGE')
        before=self.state()
        with self.assertRaisesRegex(FixtureRefusal,'content mismatch'):self.experiment().install()
        self.assertEqual(self.state(),before)

    def test_injected_failure_before_capture_preserves_original(self):
        result=self.experiment(hook=self.fault('prepared')).install()
        self.assertEqual(result['status'],'aborted_unchanged')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertEqual(self.f.read('backup.bin'),ORIGINAL)

    def test_injected_failure_after_capture_rolls_back(self):
        result=self.experiment(hook=self.fault('captured')).install()
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertEqual(self.f.read('stage.bin'),PATCHED)

    def test_injected_failure_after_promotion_rolls_back(self):
        result=self.experiment(hook=self.fault('promoted')).install()
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertEqual(self.f.read('revoked.bin'),PATCHED)

    def test_interrupted_capture_recovered_from_journal_after_handles_close(self):
        with self.assertRaises(InjectedInterruption):
            self.experiment(hook=self.fault('captured',InjectedInterruption)).install()
        self.assertFalse(self.f.path('target.bin').exists())
        # Fresh controller, persisted journal, independently retained original ID.
        self.assertEqual(self.experiment().restore()['status'],'rolled_back')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)

    def test_interrupted_promotion_recovered_from_journal_after_handles_close(self):
        with self.assertRaises(InjectedInterruption):
            self.experiment(hook=self.fault('promoted',InjectedInterruption)).install()
        self.assertEqual(self.f.read('target.bin'),PATCHED)
        self.assertEqual(self.experiment().restore()['status'],'rolled_back')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)

    def test_competing_name_during_gap_is_never_overwritten(self):
        def hook(phase):
            if phase=='captured':self.f.create('target.bin',b'COMPETING OWNER')
        with self.assertRaises(NativeFailure) as caught:self.experiment(hook=hook).install()
        self.assertIn(caught.exception.code,(80,183))
        self.assertEqual(self.f.read('target.bin'),b'COMPETING OWNER')
        self.assertEqual(self.f.read('captured.bin'),ORIGINAL)
        self.assertEqual(self.f.read('backup.bin'),ORIGINAL)
        before=self.state()
        with self.assertRaises(FixtureRefusal):self.experiment().restore()
        self.assertEqual(self.state(),before)

    def test_modified_patched_target_refuses_restore(self):
        self.experiment().install();self.change('target.bin',b'THIRD PARTY CHANGE')
        before=self.state()
        with self.assertRaisesRegex(FixtureRefusal,'content mismatch'):self.experiment().restore()
        self.assertEqual(self.state(),before)

    def test_tampered_backup_refuses_restore(self):
        self.experiment().install();self.change('backup.bin',b'TAMPERED BACKUP')
        before=self.state()
        with self.assertRaisesRegex(FixtureRefusal,'content mismatch'):self.experiment().restore()
        self.assertEqual(self.state(),before)

    def test_tampered_journal_refuses_restore(self):
        self.experiment().install();self.change('txn-prepared.json',b'{"schema":[]}')
        before=self.state()
        with self.assertRaises(FixtureRefusal):self.experiment().restore()
        self.assertEqual(self.state(),before)

    def test_repeated_install_refuses_preserves_backup(self):
        self.experiment().install();before=self.state()
        with self.assertRaises(FixtureRefusal):self.experiment().install()
        self.assertEqual(self.state(),before)

    def test_backup_collision_preserves_existing_backup_and_target(self):
        self.f.create('backup.bin',b'UNKNOWN BACKUP')
        with self.assertRaises(NativeFailure) as caught:self.experiment().install()
        self.assertIn(caught.exception.code,(80,183))
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)
        self.assertEqual(self.f.read('backup.bin'),b'UNKNOWN BACKUP')

    def test_unknown_rollback_slot_is_retained(self):
        self.experiment().install();self.f.create('rollback-intent-0.json',b'UNKNOWN ORPHAN')
        self.assertEqual(self.experiment().restore()['status'],'rolled_back')
        self.assertEqual(self.f.read('rollback-intent-0.json'),b'UNKNOWN ORPHAN')

    def test_rollback_slot_budget_refuses_before_moving_target(self):
        self.experiment().install()
        for i in range(3):self.f.create(f'rollback-intent-{i}.json',b'UNKNOWN ORPHAN')
        before=self.state()
        with self.assertRaisesRegex(FixtureRefusal,'slots exhausted'):self.experiment().restore()
        self.assertEqual(self.state(),before)

    def test_interrupted_restore_gap_can_resume_without_overwrite(self):
        self.experiment().install();calls=[0]
        def guard():
            calls[0]+=1
            if calls[0]==3:raise InjectedInterruption('after patched inode moved aside')
            return 'clear'
        with self.assertRaises(InjectedInterruption):self.experiment(guard).restore()
        self.assertFalse(self.f.path('target.bin').exists())
        self.assertEqual(self.f.read('revoked.bin'),PATCHED)
        self.assertEqual(self.f.read('captured.bin'),ORIGINAL)
        self.assertEqual(self.experiment().restore()['status'],'rolled_back')
        self.assertEqual(self.f.read('target.bin'),ORIGINAL)

    def test_competing_name_during_restore_gap_is_retained(self):
        self.experiment().install();calls=[0]
        def guard():
            calls[0]+=1
            if calls[0]==3:self.f.create('target.bin',b'EXTERNAL RESTORE COMPETITOR')
            return 'clear'
        with self.assertRaises(NativeFailure) as caught:self.experiment(guard).restore()
        self.assertIn(caught.exception.code,(80,183))
        self.assertEqual(self.f.read('target.bin'),b'EXTERNAL RESTORE COMPETITOR')
        self.assertEqual(self.f.read('captured.bin'),ORIGINAL)
        self.assertEqual(self.f.read('revoked.bin'),PATCHED)


if __name__=='__main__':unittest.main()
