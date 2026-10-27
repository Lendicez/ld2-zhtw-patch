import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.disposable import (CopyRecipe, DisposableCase, DisposableTransaction, REVIEWED,
    MAX_COPY, validate_receipt, parse_streams, load_payloads, build_reviewed, observed_guard)
from ld2patch.windows_capture import digest, encode, token
from ld2patch.windows_fixture import FixtureRefusal, NativeFailure
from ld2patch.planner import ProcessEvidence

SOURCE=b'SYNTHETIC SOURCE\n'*9000
OUTPUT=b'SYNTHETIC PATCHED\n'*9500
RECIPE=CopyRecipe('synthetic-1',digest(SOURCE),len(SOURCE),digest(OUTPUT),len(OUTPUT))


class CopySchemaTests(unittest.TestCase):
    def receipt(self):
        ids=[{'volume':1,'file_id':str(i)*32} for i in range(4)]
        return {'schema':1,'version':RECIPE.version,'leaf':'case-01',
                'source_size':len(SOURCE),'output_size':len(OUTPUT),
                'prepared':{'schema':1,'root':ids[0],'original':ids[1],'backup':ids[2],
                            'stage':ids[3],'source_sha256':RECIPE.source_hash,'output_sha256':RECIPE.output_hash},
                'metadata':{'attributes':32,'created':1,'written':2,'security_sha256':'a'*64}}
    def test_recipe_size_and_hash_fail_closed(self):
        for r in [CopyRecipe('x','0'*64,MAX_COPY+1,'1'*64,1),
                  CopyRecipe('x','0'*64,True,'1'*64,1),
                  CopyRecipe('x','0'*64,1,'0'*64,1)]:
            with self.assertRaises(FixtureRefusal):r.validate()
        with self.assertRaises(FixtureRefusal):RECIPE.check(b'UNKNOWN')
        with self.assertRaises(FixtureRefusal):build_reviewed(SOURCE,b'',{},{})

    def test_receipt_requires_independent_digest(self):
        raw=encode(self.receipt())
        for digest_value in (None,'',[],{},'0'*64):
            with self.assertRaises(FixtureRefusal):validate_receipt(raw,digest_value,RECIPE)
        self.assertEqual(validate_receipt(raw,digest(raw),RECIPE),self.receipt())

    def test_receipt_shapes_paths_aliases_and_versions(self):
        good=self.receipt()
        variants=[]
        for key,values in {'schema':[True,[],None],'leaf':['../case-01','Ld95.exe'],
            'version':['unknown'],'prepared':[[],{},None],'metadata':[[],{},None],
            'source_size':[True,-1]}.items():
            for value in values:
                bad=copy.deepcopy(good);bad[key]=value;variants.append(bad)
        bad=copy.deepcopy(good);bad['prepared']['stage']=bad['prepared']['backup'];variants.append(bad)
        bad=copy.deepcopy(good);bad['path']='elsewhere';variants.append(bad)
        for bad in variants:
            raw=encode(bad)
            with self.subTest(value=bad),self.assertRaises(FixtureRefusal):
                validate_receipt(raw,digest(raw),RECIPE)

    def test_duplicate_keys_and_oversized_receipt(self):
        for raw in (b'{"schema":1,"schema":1}',b'x'*16385,b'null',b'[]'):
            with self.assertRaises(FixtureRefusal):validate_receipt(raw,digest(raw),RECIPE)

    def test_stream_shape_refuses_extra_streams(self):
        raw=struct.pack('<IIqq',0,14,123,4096)+'::$DATA'.encode('utf-16-le')
        parse_streams(raw,123)
        for broken in (raw[:20],b'\x28'+raw[1:],raw.replace(b'D\x00',b'Z\x00')):
            with self.assertRaises(FixtureRefusal):parse_streams(broken,123)
        with self.assertRaises(FixtureRefusal):parse_streams(raw,124)

    def test_guard_unknown_running_other_copy(self):
        target=r'C:\fixture\case-01\Ld95.exe'
        self.assertEqual(observed_guard(target,ProcessEvidence(False)), 'unknown')
        self.assertEqual(observed_guard(target,ProcessEvidence(True,(target,))), 'running')
        self.assertEqual(observed_guard(target,ProcessEvidence(True,(r'C:\other\Ld95.exe',))), 'clear')


PARENT=os.environ.get('LD2_DISPOSABLE_PARENT')
@unittest.skipUnless(os.name=='nt' and PARENT,'explicit new Windows disposable fixture parent required')
class NativeCopyTests(unittest.TestCase):
    def setUp(self):
        self.parent=Path(tempfile.mkdtemp(prefix='copy-',dir=PARENT))
        with DisposableCase(self.parent,'case-01',create=True,recipe=RECIPE) as case:
            self.sha=case.prepare(SOURCE,OUTPUT)
        self.addCleanup(self.keep_sentinel)
        self.sentinel=self.parent/'outside.bin';self.sentinel.write_bytes(b'OUTSIDE UNCHANGED')
    def keep_sentinel(self):
        self.assertEqual(self.sentinel.read_bytes(),b'OUTSIDE UNCHANGED')
    def case(self):
        return DisposableCase(self.parent,'case-01',receipt_sha=self.sha,recipe=RECIPE)
    def state(self):
        return {p.name:digest(p.read_bytes()) for p in (self.parent/'case-01').iterdir() if p.is_file()}
    def change(self,name,raw):
        (self.parent/'case-01'/name).write_bytes(raw)
    def tx(self,case,guard=lambda:'clear'):
        source,output=load_payloads(case)
        return DisposableTransaction(case,source,output,guard)

    def test_large_copy_roundtrip_reopen_restore_and_idempotence(self):
        with self.case() as case:
            tx=self.tx(case);before=tx.snapshot()
            self.assertEqual(tx.install()['status'],'committed_disposable')
            self.assertEqual(digest(case.read('target.bin')),RECIPE.output_hash)
        with self.case() as case:
            tx=self.tx(case);self.assertEqual(tx.restore()['status'],'rolled_back')
            after=tx.snapshot()
            self.assertEqual(after['target.bin'],before['target.bin'])
            state=self.state();self.assertEqual(tx.restore()['status'],'already_original')
            self.assertEqual(state,self.state())

    def test_unknown_guard_and_repeated_install_preserve_state(self):
        with self.case() as case:
            before=self.state()
            with self.assertRaises(FixtureRefusal):self.tx(case,lambda:'unknown').install()
            self.assertEqual(self.state(),before)
            self.tx(case).install();before=self.state()
            with self.assertRaises(FixtureRefusal):self.tx(case).install()
            self.assertEqual(self.state(),before)

    def test_receipt_and_journal_tampering_no_mutation(self):
        for name in ('receipt.json','txn-prepared.json'):
            original=(self.parent/'case-01'/name).read_bytes()
            self.change(name,b'{"path":"elsewhere"}');before=self.state()
            with self.assertRaises(FixtureRefusal):self.case()
            self.assertEqual(self.state(),before)
            self.change(name,original)

    def test_backup_tamper_refuses(self):
        self.change('backup.bin',b'UNKNOWN')
        before=self.state()
        with self.case() as case,self.assertRaises(FixtureRefusal):self.tx(case)
        self.assertEqual(self.state(),before)

    def test_external_target_preserved_on_restore(self):
        with self.case() as case:self.tx(case).install()
        self.change('Ld95.exe',b'EXTERNAL CHANGE')
        before=self.state()
        with self.case() as case,self.assertRaises(FixtureRefusal):self.tx(case).restore()
        self.assertEqual(self.state(),before)

    def test_extra_data_stream_refused_without_stripping(self):
        p=self.parent/'case-01'/'Ld95.exe'
        Path(str(p)+':synthetic').write_bytes(b'KEEP')
        with self.case() as case,self.assertRaises(FixtureRefusal):self.tx(case).install()
        self.assertEqual(Path(str(p)+':synthetic').read_bytes(),b'KEEP')
        self.assertEqual(p.read_bytes(),SOURCE)

    def test_restart_with_wrong_independent_hash_refuses(self):
        before=self.state()
        with self.assertRaises(FixtureRefusal):
            DisposableCase(self.parent,'case-01',receipt_sha='0'*64,recipe=RECIPE)
        self.assertEqual(self.state(),before)

    def test_existing_directory_not_adopted(self):
        before=self.state()
        with self.assertRaises(FileExistsError):
            DisposableCase(self.parent,'case-01',create=True,recipe=RECIPE)
        self.assertEqual(self.state(),before)

    def test_identical_foreign_file_cannot_be_adopted_via_journal(self):
        with self.case() as case:
            tx=self.tx(case)
            foreign=case.create_with_metadata('save.bin',SOURCE,case.receipt['metadata'])
            before=self.state()
            with case.open('save.bin') as h,self.assertRaisesRegex(FixtureRefusal,'anchored receipt'):
                tx.verify(h,foreign,SOURCE)
            self.assertEqual(self.state(),before)

    def _interrupted_controller(self,phase,mode='install'):
        from owned_worker import OwnedWorker,WorkerUnavailable
        request={'nonce':uuid.uuid4().hex,'receipt_sha':self.sha,'leaf':'case-01'}
        w=OwnedWorker(self.parent,request,mode,phase,kind='disposable')
        self.addCleanup(w.close)
        try:w.kill_at_pause()
        except WorkerUnavailable as e:self.skipTest(str(e))
        # No live transaction controller or private registration is reused.
        request={'nonce':uuid.uuid4().hex,'receipt_sha':self.sha,'leaf':'case-01'}
        recovered=OwnedWorker(self.parent,request,'restore',kind='disposable')
        self.addCleanup(recovered.close)
        code,result=recovered.finish()
        self.assertEqual((code,result['status']),(0,'rolled_back'))
        again=OwnedWorker(self.parent,request,'restore',kind='disposable')
        self.addCleanup(again.close)
        code,result=again.finish()
        self.assertEqual((code,result['status']),(0,'already_original'))
        self.assertEqual((self.parent/'case-01/Ld95.exe').read_bytes(),SOURCE)

    def test_controller_death_after_capture(self):
        self._interrupted_controller('captured')
    def test_controller_death_after_promotion(self):
        self._interrupted_controller('promoted')
    def test_controller_death_during_restore(self):
        with self.case() as case:self.tx(case).install()
        self._interrupted_controller('restore-gap','restore')

