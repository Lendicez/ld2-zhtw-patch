import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ld2patch.windows_fixture import (NativeFixture,FixtureRefusal,NativeFailure,
    ReplacementGate,validate_leaf,validate_parent,validate_attributes,READ,WRITE,
    REPARSE,DIRECTORY,_Rename)

def sha(data): return hashlib.sha256(data).hexdigest()


class FixturePolicyTests(unittest.TestCase):
    def test_leaf_names_reject_paths_ads_reserved_and_game(self):
        for name in ['../target.bin','x/y.bin','x\\y.bin','x:stream.bin','CON.bin',
                     'target.bin.','Ld95.exe','USR','target.BIN','',None]:
            with self.subTest(name=name),self.assertRaises(FixtureRefusal): validate_leaf(name)
        self.assertEqual(validate_leaf('stage-1.bin'),'stage-1.bin')

    def test_parent_paths_reject_ambiguous_or_network(self):
        for path in ['relative','C:relative','\\\\server\\share','\\\\?\\C:\\temp',
                     'C:\\x\\..\\y','C:\\x.','C:\\x:stream','C:\\x/y','C:\\']:
            with self.subTest(path=path),self.assertRaises(FixtureRefusal): validate_parent(path)

    def test_reparse_and_hardlink_metadata_rejected(self):
        for attrs,links,directory in [(REPARSE,1,False),(REPARSE|DIRECTORY,1,True),
                                       (0,2,False),(DIRECTORY,1,False),(0,1,True)]:
            with self.subTest(attrs=attrs,links=links),self.assertRaises(FixtureRefusal):
                validate_attributes(attrs,links,directory)

    def test_production_and_mutation_gates_need_no_os_call(self):
        fixture=object.__new__(NativeFixture)
        self.assertFalse(fixture.can_apply)
        for method in (fixture.apply,fixture.uninstall,fixture.recover):
            with self.assertRaises(ReplacementGate): method()


PARENT=os.environ.get('LD2_NATIVE_FIXTURE_PARENT')
@unittest.skipUnless(os.name=='nt' and PARENT,'requires explicit fresh Windows fixture parent')
class WindowsNativeFixtureTests(unittest.TestCase):
    """Actual OS cases. Never called against an existing game directory."""
    def setUp(self):
        self.f=NativeFixture(Path(PARENT),['source.bin','stage.bin','output.bin','backup.bin',
            'target.bin','alias.bin','link.bin','save.bin','restore.bin'])
        self.addCleanup(self.f.stack.close)
        self.f.create('save.bin',b'SYNTHETIC SAVE SENTINEL')
        self.addCleanup(self.check_save)
    def check_save(self):
        self.assertEqual(self.f.read('save.bin'),b'SYNTHETIC SAVE SENTINEL')

    def test_native_identity_flush_and_exception_cleanup(self):
        data=b'invented original bytes\n'; initial=self.f.create('source.bin',data)
        self.assertEqual(len(initial.file_id),32)
        self.assertEqual(self.f.filesystem,'NTFS')
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with self.f.open('source.bin') as h:
                self.assertEqual(h.read(),data)
                self.assertEqual(h.identity().file_id,initial.file_id)
                raise RuntimeError('injected ordinary exception')
        self.assertIsNone(h.value)
        self.assertEqual(self.f.verify('source.bin',initial,sha(data)).size,len(data))
        self.assertEqual(_Rename.name.offset,20 if sys.maxsize>2**32 else 12)

    def test_exclusive_backup_creation_never_overwrites(self):
        self.f.create('backup.bin',b'original backup')
        with self.assertRaises(NativeFailure) as caught:
            self.f.create('backup.bin',b'conflicting duplicate install')
        self.assertIn(caught.exception.code,(80,183))
        self.assertEqual(self.f.read('backup.bin'),b'original backup')

    def test_same_process_lock_blocks_writer(self):
        self.f.create('target.bin',b'locked target')
        with self.f.open('target.bin') as held:
            with self.assertRaises(NativeFailure) as caught:
                with self.f.open('target.bin',access=WRITE): pass
            self.assertEqual(caught.exception.code,32)
            self.assertEqual(held.read(),b'locked target')

    def test_cross_process_lock_blocks_writer(self):
        self.f.create('target.bin',b'locked target')
        # Existing interpreter, no new EXE, no game. Child only attempts open.
        code="""import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from ld2patch.windows_fixture import NativeAPI,NativeFailure,WRITE
try:
    with NativeAPI().open_handle(Path(sys.argv[2]),access=WRITE): pass
except NativeFailure as e:
    print(e.code)
else:
    print('unexpected-open')
"""
        with self.f.open('target.bin') as held:
            result=subprocess.run([sys.executable,'-I','-B','-c',code,
                str(Path(__file__).resolve().parents[1]/'src'),str(self.f.path('target.bin'))],
                capture_output=True,text=True,timeout=15,check=True)
            self.assertEqual(result.stdout.strip(),'32',result.stderr)
            self.assertEqual(held.read(),b'locked target')

    def test_handle_rename_to_new_name_preserves_file_id(self):
        data=b'same-volume stage'; before=self.f.create('stage.bin',data)
        after=self.f.promote_new('stage.bin','output.bin',sha(data))
        self.assertEqual((before.volume,before.file_id),(after.volume,after.file_id))
        self.assertFalse(self.f.path('stage.bin').exists())
        self.assertEqual(self.f.read('output.bin'),data)

    def test_existing_destination_not_overwritten(self):
        self.f.create('stage.bin',b'new'); self.f.create('output.bin',b'occupied')
        with self.assertRaises(NativeFailure) as caught:
            self.f.promote_new('stage.bin','output.bin',sha(b'new'))
        self.assertIn(caught.exception.code,(80,183))
        self.assertEqual(self.f.read('output.bin'),b'occupied')
        self.assertEqual(self.f.read('stage.bin'),b'new')

    def test_protected_replace_contract_is_blocked_without_unlock_retry(self):
        self.f.create('target.bin',b'original'); self.f.create('stage.bin',b'patch')
        evidence=self.f.probe_protected_replace('target.bin','stage.bin')
        self.assertIn(evidence['winerror'],(5,32))
        self.assertFalse(evidence['retry'])
        self.assertEqual(self.f.read('target.bin'),b'original')
        self.assertEqual(self.f.read('stage.bin'),b'patch')
        # Local evidence only; not a journal claiming a committed transaction.
        Path(PARENT,'replace-contract.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_same_identity_external_edit_detected_without_restore(self):
        original=b'original'; before=self.f.create('target.bin',original)
        self.f.create('backup.bin',original)
        with self.f.path('target.bin').open('r+b') as external:
            external.write(b'EXTERNAL'); external.flush(); os.fsync(external.fileno())
        with self.assertRaisesRegex(FixtureRefusal,'content changed'):
            self.f.verify('target.bin',before,sha(original))
        with self.assertRaises(ReplacementGate): self.f.recover()
        self.assertEqual(self.f.read('target.bin'),b'EXTERNAL')
        self.assertEqual(self.f.read('backup.bin'),original)

    def test_tampered_backup_refuses_validation_and_no_restore(self):
        before=self.f.create('backup.bin',b'original'); self.f.create('target.bin',b'patch')
        with self.f.path('backup.bin').open('r+b') as external:
            external.write(b'tampered'); external.flush(); os.fsync(external.fileno())
        with self.assertRaisesRegex(FixtureRefusal,'content changed'):
            self.f.verify('backup.bin',before,sha(b'original'))
        with self.assertRaises(ReplacementGate): self.f.uninstall()
        self.assertEqual(self.f.read('target.bin'),b'patch')
        self.assertEqual(self.f.read('backup.bin'),b'tampered')

    def test_incomplete_stage_is_retained_and_never_promoted(self):
        self.f.create('stage.bin',b'partial')
        with self.assertRaisesRegex(FixtureRefusal,'stage hash mismatch'):
            self.f.promote_new('stage.bin','output.bin',sha(b'complete stage'))
        self.assertFalse(self.f.path('output.bin').exists())
        self.assertEqual(self.f.read('stage.bin'),b'partial')

    def test_real_hardlink_refused(self):
        self.f.create('source.bin',b'invented alias target')
        self.f.api.check(self.f.api.hardlink(str(self.f.path('alias.bin')),str(self.f.path('source.bin')),None),'CreateHardLinkW')
        with self.assertRaisesRegex(FixtureRefusal,'hardlink alias'):
            self.f.read('alias.bin')

    def test_real_symlink_requires_existing_privilege(self):
        self.f.create('source.bin',b'invented link target')
        # Flags=0: do not enable or request Developer Mode behavior.
        import ctypes
        if not self.f.api.symlink(str(self.f.path('link.bin')),str(self.f.path('source.bin')),0):
            code=ctypes.get_last_error()
            if code==1314: self.skipTest('CreateSymbolicLinkW WinError 1314; no privilege change/retry')
            raise NativeFailure('CreateSymbolicLinkW',code)
        with self.assertRaisesRegex(FixtureRefusal,'reparse point'):
            self.f.read('link.bin')

    def test_non_allowlisted_path_stops_before_native_open(self):
        with self.assertRaises(FixtureRefusal): self.f.read('undeclared.bin')
        with self.assertRaises(FixtureRefusal): self.f.read('../outside.bin')


if __name__=='__main__': unittest.main()
