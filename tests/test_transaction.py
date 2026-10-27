import copy
from dataclasses import replace
import errno
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.discovery import Discovery, Issue, child, discover
from ld2patch.planner import ProcessEvidence, plan_install
from ld2patch.transaction import plan_uninstall, recover_simulation, simulate_transaction
from fake_steam import APP_ID, ORIGINAL, PATCHED
from transaction_fixture import SimulatedCrash, temporary_example


def fail(error):
    def callback():
        raise error
    return callback


class FailClosedReview(unittest.TestCase):
    def setUp(self):
        self.fs,self.root,self.install,self.config=temporary_example()
        self.addCleanup(self.fs.close)
        self.discovery=discover([self.root],APP_ID,self.fs)

    def preview(self):
        return plan_install(self.discovery,self.config,self.fs,ProcessEvidence(True))

    def test_boolean_schema_is_not_version_one(self):
        self.config['schema_version']=True
        self.assertEqual(self.preview().issues[0].code,'unsupported_version_schema')

    def test_invalid_candidate_type_is_structured_refusal(self):
        self.discovery.candidates=[{'install_dir':self.install}]
        self.assertEqual(self.preview().issues[0].code,'invalid_candidates')

    def test_inconsistent_discovery_cannot_override_denial(self):
        self.discovery.issues.append(Issue('access_denied'))
        self.discovery.complete=True
        self.assertEqual(self.preview().issues[0].code,'discovery_inconsistent')

    def test_file_version_is_bounded_ascii_uint16(self):
        for version in ['1.2.3.65536','1.2.3.'+'9'*5000,'\u0661.2.3.4']:
            with self.subTest(version=version[:24]):
                self.config['versions'][0]['file_version']=version
                self.assertEqual(self.preview().issues[0].code,'invalid_file_version')


class Transactions(unittest.TestCase):
    def setUp(self):
        self.fs,self.root,self.install,self.config=temporary_example()
        self.addCleanup(self.fs.close)
        self.discovery=discover([self.root],APP_ID,self.fs)
        self.processes=lambda:ProcessEvidence(True)
        self.target=child(self.install,'Ld95.exe')
        self.save=child(self.install,'USR','LUNAS.000')
        self.fs.seed(self.save,b'SYNTHETIC SAVE MUST NOT CHANGE')
        self.preview=self.make_plan()

    def make_plan(self,action='install'):
        function=plan_install if action=='install' else plan_uninstall
        return function(self.discovery,self.config,self.fs,self.processes())

    def run_transaction(self,preview=None):
        return simulate_transaction(preview or self.preview,self.discovery,self.config,self.fs,self.processes,patch_bytes=PATCHED)

    def body(self,path=None):
        return self.fs.read_bytes(path or self.target,1024)

    def recover(self):
        return recover_simulation(self.fs.last_transaction_id,self.install,self.config,self.fs,self.processes)

    def assert_save(self):
        self.assertEqual(self.body(self.save),b'SYNTHETIC SAVE MUST NOT CHANGE')

    def test_install_backup_and_order_then_uninstall(self):
        result=self.run_transaction()
        self.assertEqual(result.status,'simulated_committed')
        self.assertFalse(result.production_apply_enabled)
        self.assertEqual(self.body(),PATCHED);self.assertEqual(self.body(self.preview.backup),ORIGINAL)
        self.assertLess(self.fs.calls.index('created:backup'),self.fs.calls.index('before_replace:apply'))
        self.assertLess(self.fs.calls.index('journal_saved:replace_pending'),self.fs.calls.index('before_replace:apply'))
        uninstall=self.make_plan('uninstall')
        result=self.run_transaction(uninstall)
        self.assertEqual(result.status,'simulated_committed');self.assertEqual(self.body(),ORIGINAL)
        self.assertEqual(self.body(self.preview.backup),ORIGINAL);self.assert_save()

    def test_production_backend_rejected_before_access(self):
        self.fs.synthetic_scope=False
        result=self.run_transaction()
        self.assertEqual(result.issues,['production_transactions_disabled']);self.assertEqual(self.fs.calls,[])

    def test_tampered_plan_target_hash_action_or_multifile(self):
        for mutation in ['can_apply','target','hash','extra_file','action']:
            with self.subTest(mutation=mutation):
                preview=copy.deepcopy(self.preview)
                if mutation=='can_apply':preview.can_apply=True
                elif mutation=='target':preview.target=self.save
                elif mutation=='hash':preview.expected_output_sha256='0'*64
                elif mutation=='extra_file':preview.proposed_changes.append(dict(preview.proposed_changes[0],path=self.save))
                else:preview.action='upgrade'
                result=self.run_transaction(preview)
                self.assertEqual(result.status,'blocked');self.assertEqual(self.fs.calls,[])
                self.assertEqual(self.body(),ORIGINAL);self.assert_save()

    def test_bad_payload_rejected_before_journal(self):
        result=simulate_transaction(self.preview,self.discovery,self.config,self.fs,self.processes,patch_bytes=b'UNKNOWN')
        self.assertEqual(result.issues,['patch_payload_mismatch']);self.assertEqual(self.fs.calls,[])

    def test_game_started_after_preview(self):
        self.processes=lambda:ProcessEvidence(True,(self.target,))
        result=self.run_transaction()
        self.assertIn('game_running',result.issues);self.assertEqual(self.fs.calls,[])

    def test_unknown_process_at_commit_keeps_evidence(self):
        calls=[]
        def provider():
            calls.append(1)
            return ProcessEvidence(len(calls)==1)
        self.processes=provider
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),ORIGINAL)
        self.assertNotIn('before_replace:apply',self.fs.calls)

    def test_changed_identity_same_bytes_invalidates_preview(self):
        self.fs.seed(self.target,ORIGINAL)
        # Force observable change even on a coarse-resolution temporary volume.
        p=self.fs.actual(self.target);s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000000))
        result=self.run_transaction()
        self.assertEqual(result.issues,['plan_changed_or_tampered']);self.assertEqual(self.fs.calls,[])

    def test_toctou_external_change_before_replace_never_overwritten(self):
        self.fs.hooks['before_replace:apply']=lambda:self.fs.seed(self.target,b'EXTERNAL MOD')
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),b'EXTERNAL MOD')
        self.assertIn('compare_and_replace_conflict',result.issues);self.assert_save()

    def test_partial_stage_and_no_space_leave_original(self):
        self.fs.hooks['partial:after.bin']=fail(OSError(errno.ENOSPC,'synthetic disk full'))
        result=self.run_transaction()
        self.assertEqual(result.status,'aborted_unchanged');self.assertEqual(self.body(),ORIGINAL)
        record=self.fs.load_journal(result.transaction_id)
        self.assertNotEqual(self.body(record['stage']),PATCHED)
        self.assertEqual(self.body(self.preview.backup),ORIGINAL);self.assert_save()

    def test_partial_backup_is_retained_and_never_overwritten(self):
        self.fs.hooks['partial:backup']=fail(OSError(errno.ENOSPC,'synthetic disk full'))
        result=self.run_transaction();partial=self.body(self.preview.backup)
        self.assertEqual(result.status,'aborted_unchanged');self.assertNotEqual(partial,ORIGINAL)
        blocked=self.make_plan();self.assertEqual(blocked.status,'blocked')
        self.assertEqual(self.run_transaction(blocked).status,'blocked')
        self.assertEqual(self.body(self.preview.backup),partial);self.assertEqual(self.body(),ORIGINAL)

    def test_locked_target_aborts_without_replacement_retry(self):
        self.fs.hooks['before_replace:apply']=fail(PermissionError('synthetic target locked'))
        result=self.run_transaction()
        self.assertEqual(result.status,'aborted_unchanged');self.assertEqual(self.body(),ORIGINAL)
        self.assertEqual(self.fs.calls.count('before_replace:apply'),1)

    def test_replace_applied_then_error_rolls_back(self):
        self.fs.hooks['after_replace:apply']=fail(OSError('synthetic acknowledgement lost'))
        result=self.run_transaction()
        self.assertEqual(result.status,'rolled_back');self.assertEqual(self.body(),ORIGINAL)
        self.assertEqual(self.body(self.preview.backup),ORIGINAL);self.assert_save()

    def test_commit_journal_failure_rolls_back(self):
        self.fs.hooks['journal:committed']=fail(OSError('synthetic journal full'))
        result=self.run_transaction()
        self.assertEqual(result.status,'rolled_back');self.assertEqual(self.body(),ORIGINAL)

    def test_initial_journal_failure_does_not_start_file_changes(self):
        self.fs.hooks['journal:prepared']=fail(OSError(errno.ENOSPC,'synthetic journal full'))
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),ORIGINAL)
        self.assertIn('initial_journal_not_confirmed',result.issues)
        self.assertFalse(any(x.startswith('create:') for x in self.fs.calls))

    def test_journal_collision_never_overwrites_existing_evidence(self):
        first=self.run_transaction();self.assertEqual(first.status,'simulated_committed')
        journal=self.fs.journal_path(first.transaction_id)
        evidence=journal.read_bytes()
        with patch('ld2patch.transaction.uuid.uuid4') as generate:
            generate.return_value.hex=first.transaction_id
            result=self.run_transaction(self.make_plan('uninstall'))
        self.assertEqual(result.status,'recovery_required');self.assertEqual(journal.read_bytes(),evidence)
        self.assertEqual(self.body(),PATCHED);self.assertEqual(self.body(self.preview.backup),ORIGINAL)

    def test_unknown_external_write_after_replace_refuses_rollback(self):
        def foreign():
            self.fs.seed(self.target,b'EXTERNAL AFTER REPLACE')
            raise OSError('synthetic failure')
        self.fs.hooks['after_replace:apply']=foreign
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),b'EXTERNAL AFTER REPLACE')
        self.assertNotIn('before_replace:restore',self.fs.calls)

    def test_backup_corruption_refuses_rollback(self):
        def corrupt():
            self.fs.seed(self.preview.backup,b'CORRUPTED BACKUP')
            raise OSError('synthetic journal failure')
        self.fs.hooks['journal:committed']=corrupt
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),PATCHED)
        self.assertNotIn('before_replace:restore',self.fs.calls)

    def test_rollback_lock_retains_then_explicit_recovery(self):
        self.fs.hooks['after_replace:apply']=fail(OSError('synthetic failure'))
        self.fs.hooks['before_replace:restore']=fail(PermissionError('synthetic rollback locked'))
        result=self.run_transaction()
        self.assertEqual(result.status,'recovery_required');self.assertEqual(self.body(),PATCHED)
        recovered=self.recover()
        self.assertEqual(recovered.status,'rolled_back');self.assertEqual(self.body(),ORIGINAL)

    def test_crash_after_replace_reloads_persisted_journal(self):
        self.fs.hooks['after_replace:apply']=fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):self.run_transaction()
        self.assertEqual(self.body(),PATCHED)
        self.assertEqual(self.fs.load_journal(self.fs.last_transaction_id)['phase'],'replace_pending')
        self.assertEqual(self.recover().status,'rolled_back');self.assertEqual(self.body(),ORIGINAL)

    def test_crash_before_replace_aborts_unchanged(self):
        self.fs.hooks['journal_saved:replace_pending']=fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):self.run_transaction()
        self.assertEqual(self.recover().status,'aborted_unchanged');self.assertEqual(self.body(),ORIGINAL)

    def test_crash_after_commit_does_not_undo_success(self):
        self.fs.hooks['journal_saved:committed']=fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):self.run_transaction()
        self.assertEqual(self.recover().status,'already_committed');self.assertEqual(self.body(),PATCHED)

    def test_crash_during_rollback_is_recoverable(self):
        self.fs.hooks['after_replace:apply']=fail(OSError('synthetic failure'))
        self.fs.hooks['after_replace:restore']=fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):self.run_transaction()
        self.assertEqual(self.recover().status,'rolled_back');self.assertEqual(self.body(),ORIGINAL)

    def test_repeated_install_and_uninstall_are_noops(self):
        self.assertEqual(self.run_transaction().status,'simulated_committed')
        count=len(self.fs.calls);backup=self.body(self.preview.backup)
        self.assertEqual(self.run_transaction(self.make_plan()).status,'already_patched')
        self.assertEqual(len(self.fs.calls),count)
        self.assertEqual(self.run_transaction(self.make_plan('uninstall')).status,'simulated_committed')
        count=len(self.fs.calls)
        self.assertEqual(self.run_transaction(self.make_plan('uninstall')).status,'already_original')
        self.assertEqual(len(self.fs.calls),count);self.assertEqual(self.body(self.preview.backup),backup)

    def test_repeated_install_does_not_claim_backup_is_valid(self):
        self.assertEqual(self.run_transaction().status,'simulated_committed')
        self.fs.seed(self.preview.backup,b'OTHER BACKUP')
        result=self.run_transaction(self.make_plan())
        self.assertEqual(result.status,'blocked');self.assertEqual(self.body(),PATCHED)

    def test_uninstall_modified_exe_or_bad_backup_refuses(self):
        self.assertEqual(self.run_transaction().status,'simulated_committed')
        self.fs.seed(self.target,b'STEAM OR OTHER MOD')
        plan=self.make_plan('uninstall');self.assertEqual(plan.status,'blocked')
        self.assertEqual(self.run_transaction(plan).status,'blocked');self.assertEqual(self.body(),b'STEAM OR OTHER MOD')
        self.fs.seed(self.target,PATCHED);self.fs.seed(self.preview.backup,b'BAD BACKUP')
        self.assertEqual(self.make_plan('uninstall').status,'blocked')

    def test_uninstall_failure_restores_patch_and_preserves_original_backup(self):
        self.assertEqual(self.run_transaction().status,'simulated_committed')
        self.fs.hooks['after_replace:apply']=fail(OSError('synthetic uninstall failure'))
        result=self.run_transaction(self.make_plan('uninstall'))
        self.assertEqual(result.status,'rolled_back');self.assertEqual(self.body(),PATCHED)
        self.assertEqual(self.body(self.preview.backup),ORIGINAL);self.assert_save()

    def test_journal_path_or_hash_tampering_refused(self):
        self.fs.hooks['after_replace:apply']=fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):self.run_transaction()
        txid=self.fs.last_transaction_id;original=self.fs.load_journal(txid)
        for key,value in [('target',self.save),('backup',r'C:\Other'),('undo','../escape'),('before_hash','0'*64),('schema',True)]:
            with self.subTest(key=key):
                edited=dict(original);edited[key]=value
                self.fs.journal_path(txid).write_text(json.dumps(edited),encoding='utf-8')
                self.assertEqual(self.recover().status,'recovery_required');self.assertEqual(self.body(),PATCHED)
                self.assert_save()

    def test_malformed_journal_and_id_refused(self):
        self.assertEqual(recover_simulation('../escape',self.install,self.config,self.fs,self.processes).status,'recovery_required')
        self.assertEqual(self.run_transaction().status,'simulated_committed')
        self.fs.journal_path(self.fs.last_transaction_id).write_text('{broken',encoding='utf-8')
        self.assertEqual(self.recover().status,'recovery_required')

    def test_reparse_evidence_rejected_before_write(self):
        self.fs.unsafe.add(self.target.casefold())
        result=self.run_transaction()
        self.assertEqual(result.status,'blocked');self.assertEqual(self.fs.calls,[])

    def test_hardlink_alias_rejected(self):
        p=self.fs.actual(self.target);alias=p.with_name('synthetic-alias')
        os.link(p,alias)
        result=self.run_transaction()
        self.assertEqual(result.status,'blocked');self.assertEqual(self.fs.calls,[])
        self.assertEqual(p.read_bytes(),ORIGINAL)

    @unittest.skipIf(os.name=='nt','Real symlink creation not attempted on Windows; reparse evidence test runs')
    def test_real_symlink_rejected_without_following(self):
        p=self.fs.actual(self.target);alias=p.with_name('synthetic-real')
        p.rename(alias);p.symlink_to(alias)
        self.assertEqual(self.run_transaction().status,'blocked');self.assertEqual(self.fs.calls,[])

    def test_concurrent_fixture_transaction_rejected(self):
        self.fs.mutex.acquire()
        try:result=self.run_transaction()
        finally:self.fs.mutex.release()
        self.assertEqual(result.issues,['fixture_transaction_locked']);self.assertEqual(self.body(),ORIGINAL)


if __name__=='__main__':unittest.main()
