import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fake_steam import example
from ld2patch.controller import Controller
from ld2patch.trial_controller import TrialController
from ld2patch.trial_backend import TrialBackend,TrialFailure
from ld2patch.trial_store import CurrentUserProtector,TrialSpace,policy_for_new_parent,validate_policy,PURPOSE
from ld2patch.planner import ProcessEvidence
from ld2patch.discovery import EvidenceError,child
from ld2patch.windows_fixture import FixtureRefusal,NativeFailure
from ld2patch.windows_capture import encode,digest,token


class TrialFlow(unittest.TestCase):
    def setUp(self):
        self.fs,self.root,self.install,self.config=example(two=True)
        self.query=Mock(return_value=self.root)
        self.processes=Mock(return_value=ProcessEvidence(True))
        self.base=Controller(self.config,self.fs,self.query,self.processes,Mock())
        self.backend=Mock()
        self.backend.plan.side_effect=lambda source:{'source':source,'workspace':'new-trial','target':'new-trial/Ld95.exe'}
        self.backend.install.return_value={'status':'installed_trial','workspace':'new-trial'}
        self.backend.inspect.return_value={'status':'recovery_available','workspace':'new-trial'}
        self.backend.restore.return_value={'status':'restored_trial','workspace':'new-trial'}
        self.c=TrialController(self.base,self.backend)
    def ready(self):
        self.c.discover();self.c.inspect(self.install)

    def test_multiple_candidates_require_explicit_selection(self):
        view=self.c.discover()
        self.assertEqual(len(view['candidates']),2)
        with self.assertRaises(EvidenceError):self.c.request_install()
        self.c.inspect(self.install)
        self.assertTrue(self.c.view()['trial_enabled'])
        self.assertFalse(self.c.view()['install_enabled'])
        self.backend.install.assert_not_called()

    def test_unknown_version_and_hash_refuse(self):
        self.fs.add(child(self.install,'Ld95.exe'),b'UNKNOWN')
        self.ready()
        with self.assertRaises(EvidenceError):self.c.request_install()
        self.backend.install.assert_not_called()
        self.backend.plan.assert_not_called()

    def test_confirmation_is_required_and_cancel_back_write_nothing(self):
        self.ready()
        with self.assertRaises(EvidenceError):self.c.confirm()
        self.c.request_install()
        self.backend.install.assert_not_called()
        self.c.cancel();self.assertEqual(self.c.stage,'ready')
        with self.assertRaises(EvidenceError):self.c.confirm()
        self.c.request_install();self.c.back()
        self.backend.install.assert_not_called()

    def test_source_changes_between_preview_and_confirmation(self):
        self.ready();self.c.request_install()
        self.fs.add(child(self.install,'Ld95.exe'),b'CHANGED')
        with self.assertRaises(EvidenceError):self.c.confirm()
        self.assertEqual(self.c.stage,'failed')
        self.backend.install.assert_not_called()

    def test_install_complete_and_repeated_clicks(self):
        self.ready();self.c.request_install()
        view=self.c.confirm()
        self.assertEqual(view['stage'],'installed')
        self.backend.install.assert_called_once()
        with self.assertRaises(EvidenceError):self.c.confirm()
        self.assertEqual(self.backend.install.call_count,1)

    def test_reentrant_click_and_cancel_are_refused_while_busy(self):
        self.ready();self.c.request_install()
        def install(plan):
            for call in (self.c.confirm,self.c.cancel,lambda:self.c.inspect(self.install)):
                with self.assertRaisesRegex(EvidenceError,'operation_in_progress'):call()
            return {'status':'installed_trial','workspace':'new-trial'}
        self.backend.install.side_effect=install
        self.c.confirm();self.backend.install.assert_called_once()

    def test_failure_keeps_workspace_then_restore_requires_confirmation(self):
        self.ready();self.c.request_install()
        self.backend.install.side_effect=TrialFailure('injected failure','new-trial',True)
        with self.assertRaises(TrialFailure):self.c.confirm()
        self.assertEqual(self.c.workspace,'new-trial')
        self.c.request_restore('new-trial')
        self.backend.restore.assert_not_called()
        self.c.confirm();self.assertEqual(self.c.stage,'restored')

    def test_restore_cancel_and_already_restored_do_not_write(self):
        self.c.request_restore('new-trial');self.c.cancel()
        self.backend.restore.assert_not_called()
        self.backend.inspect.return_value={'status':'already_original','workspace':'new-trial'}
        self.assertEqual(self.c.request_restore('new-trial')['stage'],'restored')
        self.backend.restore.assert_not_called()
        with self.assertRaises(EvidenceError):self.c.confirm()

    def test_missing_or_untrusted_store_never_recovers(self):
        for error in (FileNotFoundError('missing anchor'),FixtureRefusal('corrupt card')):
            self.backend.inspect.side_effect=error
            with self.assertRaises(type(error)):self.c.request_restore('new-trial')
            self.assertEqual(self.c.stage,'failed')
            self.backend.restore.assert_not_called()

    def test_denial_latches_stop_no_fallback(self):
        self.backend.inspect.side_effect=PermissionError('denied')
        with self.assertRaises(PermissionError):self.c.request_restore('new-trial')
        for call in (lambda:self.c.manual(self.install),self.c.confirm,self.c.discover):
            with self.assertRaises(EvidenceError):call()
        self.assertEqual(self.backend.inspect.call_count,1)

    def test_native_restore_access_denial_stops_new_requests(self):
        self.c.request_restore('new-trial')
        self.backend.restore.side_effect=NativeFailure('read',5)
        with self.assertRaises(NativeFailure):self.c.confirm()
        with self.assertRaises(EvidenceError):self.c.request_restore('new-trial')
        self.assertTrue(self.c.view()['stopped'])
        self.backend.restore.assert_called_once()

    def test_bound_policy_and_path_inputs_fail_closed(self):
        p={'schema':1,'purpose':PURPOSE,'parent':r'C:\OwnedTrials',
           'identity':{'volume':1,'file_id':'1'*32}}
        b=TrialBackend(p)
        for source in (r'C:\OwnedTrials\old\Ld95.exe',r'C:\Ld95.exe','../Ld95.exe'):
            with self.assertRaises(FixtureRefusal):b.plan(source)
        with self.assertRaises(FixtureRefusal):b._leaf(r'C:\Game\ld2-trial-'+'a'*32)
        for bad in ({},dict(p,parent=r'\\server\share'),dict(p,schema=True)):
            with self.assertRaises(FixtureRefusal):validate_policy(bad)

    def test_additional_plaintext_integrity_validation(self):
        protector=object.__new__(CurrentUserProtector)
        protector._call=Mock(return_value=encode({'body':{'schema':1},'sha256':'0'*64}))
        with self.assertRaises(FixtureRefusal):protector.open(b'corrupt')

    def test_cli_dispatch_does_not_open_gui(self):
        from ld2patch.desktop import main
        with patch('ld2patch.trial_entry.main',return_value=0) as run, \
             patch('ld2patch.trial_ui.launch',side_effect=AssertionError('no GUI')):
            self.assertEqual(main(['--trial','inspect','--workspace','fixture']),0)
            run.assert_called_once_with(['inspect','--workspace','fixture'])


PARENT=os.environ.get('LD2_TRIAL_STORE_PARENT')
@unittest.skipUnless(os.name=='nt' and PARENT,'explicit new native recovery-store parent required')
class NativeRecoveryStore(unittest.TestCase):
    def setUp(self):
        self.parent=Path(tempfile.mkdtemp(prefix='store-',dir=PARENT))
        self.policy=policy_for_new_parent(self.parent)
        self.leaf='ld2-trial-'+'a'*32
    def test_dpapi_roundtrip_reopen_and_corruption_refusal(self):
        with TrialSpace(self.policy,self.leaf,create=True) as s:
            body=s.save('b'*64,{'volume':1,'file_id':'c'*32})
            anchor=(s.vault/'anchor.bin').read_bytes()
        with TrialSpace(self.policy,self.leaf) as s:self.assertEqual(s.load(),body)
        altered=bytearray(anchor);altered[len(altered)//2]^=1
        (self.parent/self.leaf/'recovery-store/anchor.bin').write_bytes(altered)
        with TrialSpace(self.policy,self.leaf) as s,self.assertRaises((NativeFailure,FixtureRefusal,ValueError)):
            s.load()

    def test_profile_version_is_protected_and_reopened(self):
        from ld2patch.profiles import copy_recipe
        version=copy_recipe('m042').version
        with TrialSpace(self.policy,self.leaf,create=True) as s:
            body=s.save('b'*64,{'volume':1,'file_id':'c'*32},version)
        with TrialSpace(self.policy,self.leaf) as s:
            self.assertEqual(s.load(),body)
            self.assertEqual(s.load()['version'],version)

    def test_unknown_profile_rejected_before_anchor_write(self):
        with TrialSpace(self.policy,self.leaf,create=True) as s:
            with self.assertRaises(ValueError):
                s.save('b'*64,{'volume':1,'file_id':'c'*32},'unknown')
            self.assertEqual(list(s.vault.iterdir()),[])

    def test_missing_anchor_no_reconstruction(self):
        with TrialSpace(self.policy,self.leaf,create=True) as s:
            with self.assertRaises(NativeFailure):s.load()
            self.assertEqual(list(s.vault.iterdir()),[])

    def test_moved_valid_card_is_not_trusted_for_other_workspace(self):
        with TrialSpace(self.policy,self.leaf,create=True) as a:
            a.save('b'*64,{'volume':1,'file_id':'c'*32})
            blob=(a.vault/'anchor.bin').read_bytes()
        with TrialSpace(self.policy,'ld2-trial-'+'d'*32,create=True) as b:
            (b.vault/'anchor.bin').write_bytes(blob)
            with self.assertRaisesRegex(FixtureRefusal,'binding mismatch'):b.load()

    def test_wrong_bound_parent_identity_refuses_before_writes(self):
        p=copy.deepcopy(self.policy);p['identity']['file_id']='0'*32
        with self.assertRaisesRegex(FixtureRefusal,'parent identity'):
            TrialSpace(p,self.leaf,create=True)
        self.assertEqual(list(self.parent.iterdir()),[])

