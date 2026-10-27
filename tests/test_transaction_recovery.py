"""Crash-window and untrusted JSON regressions; synthetic bytes and owned temp files only."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.discovery import child, discover
from ld2patch.planner import ProcessEvidence, plan_install
from ld2patch.transaction import recover_simulation, simulate_transaction
from fake_steam import APP_ID, ORIGINAL, PATCHED
from transaction_fixture import SimulatedCrash, temporary_example


def fail(error):
    def callback():
        raise error
    return callback


class RecoveryRegressions(unittest.TestCase):
    def setUp(self):
        self.fs, self.root, self.install, self.config = temporary_example()
        self.addCleanup(self.fs.close)
        self.discovery = discover([self.root], APP_ID, self.fs)
        self.processes = lambda: ProcessEvidence(True)
        self.preview = plan_install(self.discovery, self.config, self.fs, self.processes())
        self.target = child(self.install, 'Ld95.exe')
        self.save = child(self.install, 'USR', 'LUNAS.000')
        self.fs.seed(self.save, b'SYNTHETIC SAVE MUST NOT CHANGE')

    def crash(self, event='created:restore.bin'):
        self.fs.hooks['after_replace:apply'] = fail(OSError('synthetic acknowledgement lost'))
        self.fs.hooks[event] = fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):
            simulate_transaction(self.preview, self.discovery, self.config, self.fs,
                                 self.processes, patch_bytes=PATCHED)
        self.txid = self.fs.last_transaction_id
        return self.fs.load_journal(self.txid)

    def recover(self):
        return recover_simulation(self.txid, self.install, self.config, self.fs, self.processes)

    def body(self, path):
        return self.fs.read_bytes(path, 1024)

    def snapshot(self):
        # Include directory entries and file identity/time, not only target bytes.
        return {str(p.relative_to(self.fs.root)):
                ('dir',) if p.is_dir() else (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                for p in self.fs.root.rglob('*')}

    def assert_restored(self):
        self.assertEqual(self.body(self.target), ORIGINAL)
        self.assertEqual(self.body(self.preview.backup), ORIGINAL)
        self.assertEqual(self.body(self.save), b'SYNTHETIC SAVE MUST NOT CHANGE')

    def assert_refused_without_mutation(self, record, issue=None):
        self.fs.journal_path(self.txid).write_text(json.dumps(record), encoding='utf-8')
        before, calls = self.snapshot(), list(self.fs.calls)
        previous = self.processes
        self.processes = lambda: self.fail('invalid journal reached process lookup')
        try:
            result = self.recover()
        finally:
            self.processes = previous
        self.assertEqual(result.status, 'recovery_required')
        if issue:
            self.assertEqual(result.issues, [issue])
        self.assertFalse(result.production_apply_enabled)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fs.calls, calls)

    def test_created_restore_orphan_recovery_preserves_old_stage(self):
        record = self.crash()
        self.assertIsNone(record['restore_meta'])
        self.assertEqual(record['phase'], 'restore_preparing')
        orphan = self.fs.actual(record['restore'])
        before = (orphan.read_bytes(), orphan.stat().st_ino, orphan.stat().st_mtime_ns)
        self.assertEqual(self.body(self.target), PATCHED)
        self.assertEqual(self.recover().status, 'rolled_back')
        self.assert_restored()
        self.assertEqual((orphan.read_bytes(), orphan.stat().st_ino, orphan.stat().st_mtime_ns), before)
        saved = self.fs.load_journal(self.txid)
        self.assertEqual(saved['schema'], 2)
        self.assertEqual(saved['restore_attempt'], 1)
        self.assertTrue(saved['restore'].endswith('restore-1.bin'))
        self.assertIn('before_replace:restore', self.fs.calls)

    def test_untrusted_orphan_bytes_are_not_read_or_adopted(self):
        record = self.crash()
        orphan = self.fs.actual(record['restore'])
        orphan.write_bytes(b'UNTRUSTED ORPHAN, NOT A PREIMAGE')
        read = self.fs.read_bytes
        def guarded(path, limit):
            self.assertNotEqual(path, record['restore'], 'orphan must not be read')
            return read(path, limit)
        self.fs.read_bytes = guarded
        self.assertEqual(self.recover().status, 'rolled_back')
        self.assert_restored()
        self.assertEqual(orphan.read_bytes(), b'UNTRUSTED ORPHAN, NOT A PREIMAGE')

    def test_legacy_v1_orphan_can_recover_without_adoption(self):
        record = self.crash()
        record['schema'] = 1
        del record['restore_attempt']
        record['phase'] = 'replace_pending'
        self.fs.journal_path(self.txid).write_text(json.dumps(record), encoding='utf-8')
        orphan = self.fs.actual(record['restore']).read_bytes()
        self.assertEqual(self.recover().status, 'rolled_back')
        self.assert_restored()
        self.assertEqual(self.fs.actual(record['restore']).read_bytes(), orphan)
        self.assertEqual(self.fs.load_journal(self.txid)['restore_attempt'], 1)

    def test_three_orphan_slots_stop_with_diagnostic_without_overwrite(self):
        record = self.crash()
        for slot in (1, 2):
            self.fs.hooks[f'created:restore-{slot}.bin'] = fail(SimulatedCrash())
            with self.assertRaises(SimulatedCrash):
                self.recover()
            saved = self.fs.load_journal(self.txid)
            self.assertEqual(saved['restore_attempt'], slot)
            self.assertIsNone(saved['restore_meta'])
        before, calls = self.snapshot(), list(self.fs.calls)
        for _ in range(2):
            result = self.recover()
            self.assertEqual(result.status, 'recovery_required')
            self.assertEqual(result.issues, ['restore_stage_retry_budget'])
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.fs.calls, calls)
        self.assertEqual(self.body(self.target), PATCHED)
        self.assertEqual(self.body(self.preview.backup), ORIGINAL)
        for name in ('restore.bin', 'restore-1.bin', 'restore-2.bin'):
            self.assertEqual(self.body(child(record['work'], name)), ORIGINAL)

    def test_crash_after_slot_intent_before_creation_can_recover(self):
        record = self.crash('journal_saved:restore_preparing')
        self.assertEqual(self.fs.metadata(record['restore']).kind, 'missing')
        self.assertEqual(self.recover().status, 'rolled_back')
        self.assert_restored()
        self.assertEqual(self.fs.load_journal(self.txid)['restore_attempt'], 0)

    def test_crash_after_alternate_restore_replace_can_recover(self):
        self.crash()
        self.fs.hooks['after_replace:restore'] = fail(SimulatedCrash())
        with self.assertRaises(SimulatedCrash):
            self.recover()
        self.assert_restored()
        self.assertEqual(self.recover().status, 'rolled_back')

    def test_nonstring_phase_is_structured_refusal_without_writes(self):
        record = self.crash()
        for phase in ([], {}, 1, None, True, 1.5):
            with self.subTest(phase=phase):
                edited = copy.deepcopy(record)
                edited['phase'] = phase
                self.assert_refused_without_mutation(edited, 'invalid_journal_state')

    def test_invalid_root_is_structured_refusal_without_writes(self):
        self.crash()
        for record in ([], None, 'journal', 123):
            with self.subTest(record=record):
                self.assert_refused_without_mutation(record, 'invalid_journal')

    def test_complete_journal_schema_rejects_malformed_fields_before_writes(self):
        record = self.crash()
        edits = [
            ('schema', True), ('schema', 3), ('action', []), ('action', 'upgrade'),
            ('version_id', {}), ('install_dir', None), ('app_id', 123),
            ('transaction_id', '0' * 32), ('target', self.save), ('restore', '../escape'),
            ('before_hash', []), ('original_hash', '0' * 64), ('after_hash', 'BAD'),
            ('before_size', True), ('after_size', '1'), ('original_size', -1),
            ('restore_attempt', True), ('restore_attempt', 3), ('restore_attempt', -1),
            ('restore_attempt', 1), ('before_meta', None), ('stage_meta', None),
            ('before_meta', []), ('restore_meta', []), ('phase', 'rollback_pending'),
        ]
        for key, value in edits:
            with self.subTest(field=key, value=value):
                edited = copy.deepcopy(record)
                edited[key] = value
                self.assert_refused_without_mutation(edited)
        for key, value in [('identity', 1), ('identity', 'bad\0id'), ('change_token', []),
                           ('size', True), ('canonical_path', self.save), ('reparse', True),
                           ('ancestors_verified', 1), ('file_version', []), ('kind', {})]:
            with self.subTest(metadata=key):
                edited = copy.deepcopy(record)
                edited['stage_meta'][key] = value
                self.assert_refused_without_mutation(edited)
        for operation in ('missing', 'extra', 'metadata_missing', 'metadata_extra'):
            with self.subTest(operation=operation):
                edited = copy.deepcopy(record)
                if operation == 'missing':
                    del edited['restore_meta']
                elif operation == 'extra':
                    edited['unreviewed_path'] = self.save
                elif operation == 'metadata_missing':
                    del edited['stage_meta']['identity']
                else:
                    edited['stage_meta']['unreviewed'] = True
                self.assert_refused_without_mutation(edited)

    def test_unsafe_or_denied_orphan_does_not_advance_slots(self):
        record = self.crash()
        before, calls = self.snapshot(), list(self.fs.calls)
        self.fs.unsafe.add(record['restore'].casefold())
        self.assertEqual(self.recover().issues, ['fixture_reparse_rejected'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fs.calls, calls)
        self.fs.unsafe.clear()
        metadata = self.fs.metadata
        def denied(path):
            if path == record['restore']:
                raise PermissionError('synthetic unreadable orphan')
            return metadata(path)
        self.fs.metadata = denied
        self.assertEqual(self.recover().status, 'recovery_required')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fs.calls, calls)


if __name__ == '__main__':
    unittest.main()
