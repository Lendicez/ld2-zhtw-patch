import copy
from dataclasses import replace
import io
import contextlib
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.controller import Controller
from ld2patch.discovery import EvidenceError, child, read_stable
from ld2patch.planner import ProcessEvidence
from ld2patch.windows_readonly import (REGISTRY_LOCATIONS, ProcessObservation, ProcessRow,
    WindowsReadOnlyFS, detect, process_state, registry_roots)
from fake_steam import APP_ID, ORIGINAL, VERSION, example


class WindowsPorts(unittest.TestCase):
    def test_registry_views_and_missing_values(self):
        calls = []
        def query(location):
            calls.append(location)
            if location[0] == 'HKCU':
                raise FileNotFoundError()
            return r'D:\合成 Steam'
        self.assertEqual(registry_roots(query), [r'D:\合成 Steam'] * 2)
        self.assertEqual(calls, list(REGISTRY_LOCATIONS))

    def test_registry_denial_stops_before_other_hives_or_files(self):
        fs, root, install, config = example()
        query = Mock(side_effect=PermissionError('synthetic refusal'))
        result = detect(APP_ID, fs, query)
        self.assertEqual([x.code for x in result.issues], ['registry_access_denied'])
        self.assertEqual(query.call_count, 1)
        self.assertEqual(fs.probes, [])
        self.assertFalse(result.complete)

    def test_invalid_appid_never_reads_registry(self):
        query = Mock(side_effect=AssertionError('must not query'))
        fs, *_ = example()
        self.assertEqual(detect(None, fs, query).issues[0].code, 'appid_required')
        query.assert_not_called()

    def test_bad_registry_values_do_not_expand_or_search(self):
        fs, *_ = example()
        for value in ([], '%SECRET%\\Steam', r'C:\Steam\..\Other', r'\\server\Steam'):
            with self.subTest(value=value):
                query = Mock(return_value=value)
                result = detect(APP_ID, fs, query)
                self.assertFalse(result.complete)
                self.assertEqual(query.call_count, 1)
                self.assertEqual(fs.probes, [])

    def test_process_snapshot_empty_invalid_partial_are_unknown(self):
        for rows in ([], None, [ProcessRow(True, 'x')], [ProcessRow(1, 'x'), ProcessRow(1, 'y')]):
            with self.subTest(rows=rows):
                self.assertFalse(process_state(lambda: rows).complete)
        def incomplete():
            raise OSError('synthetic enumeration error')
        self.assertFalse(process_state(incomplete).complete)

    def test_process_matching_path_and_clear_snapshot(self):
        query = Mock(return_value=r'D:\Game\Ld95.exe')
        result = process_state(lambda: [ProcessRow(1, 'Other.exe'), ProcessRow(2, 'LD95.EXE')], query)
        self.assertEqual(result, ProcessEvidence(True, (r'D:\Game\Ld95.exe',), False))
        query.assert_called_once_with(2)
        query.reset_mock()
        self.assertEqual(process_state(lambda: [ProcessRow(1, 'Other.exe')], query), ProcessEvidence(True))
        query.assert_not_called()

    def test_process_denied_path_is_not_clear_and_stops(self):
        query = Mock(side_effect=PermissionError('synthetic denied'))
        result = process_state(lambda: [ProcessRow(1, 'Ld95.exe'), ProcessRow(2, 'Ld95.exe')], query)
        self.assertFalse(result.complete)
        self.assertTrue(result.unresolved_game_processes)
        self.assertEqual(result.issue, 'process_access_denied')
        self.assertEqual(query.call_count, 1)

    def test_process_changed_or_unsafe_path_is_unknown(self):
        for path in (r'C:\Other.exe', '../Ld95.exe', None):
            with self.subTest(path=path):
                self.assertFalse(process_state(lambda: [ProcessRow(1, 'Ld95.exe')], lambda pid: path).complete)

    def test_stat_preview_adapter_reads_only_explicit_paths(self):
        paths = []
        target = r'C:\Game\Ld95.exe'
        def probe(path):
            paths.append(path)
            if path not in ('C:\\', r'C:\Game', target):
                raise FileNotFoundError()
            return SimpleNamespace(st_mode=stat.S_IFREG if path == target else stat.S_IFDIR,
                st_file_attributes=0, st_nlink=1, st_ino=3 if path == target else 2,
                st_dev=1, st_size=len(ORIGINAL), st_mtime_ns=123)
        fs = WindowsReadOnlyFS(lstat=probe, read=lambda path, limit: ORIGINAL[:limit + 1], version=lambda path: VERSION)
        data, meta = read_stable(fs, target, 1024)
        self.assertEqual(data, ORIGINAL); self.assertEqual(meta.file_version, VERSION)
        self.assertEqual(set(paths), {'C:\\', r'C:\Game', target})
        self.assertEqual(fs.metadata(r'C:\Game\missing').kind, 'missing')

    def test_stat_preview_reparse_hardlink_denial_no_fallback(self):
        for fault in ('reparse', 'hardlink', 'denied'):
            with self.subTest(fault=fault):
                calls = []
                def probe(path):
                    calls.append(path)
                    if path == 'C:\\':
                        return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0, st_ino=1)
                    if fault == 'denied':
                        raise PermissionError('synthetic denied')
                    return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400 if fault == 'reparse' else 0,
                                           st_nlink=2, st_ino=2)
                fs = WindowsReadOnlyFS(lstat=probe, read=Mock(side_effect=AssertionError('no read')))
                with self.assertRaises((EvidenceError, PermissionError)):
                    fs.metadata(r'C:\Ld95.exe')
                self.assertEqual(calls, ['C:\\', r'C:\Ld95.exe'])


class ControllerTests(unittest.TestCase):
    def setup_controller(self, two=False):
        self.fs, self.root, self.install, self.config = example(two=two)
        self.query = Mock(return_value=self.root)
        self.processes = Mock(return_value=ProcessEvidence(True))
        self.writer = Mock(return_value={'output_sha256': 'synthetic'})
        self.c = Controller(self.config, self.fs, self.query, self.processes, self.writer)
        return self.c

    def test_construction_and_view_have_no_host_side_effects(self):
        self.setup_controller()
        self.assertFalse(self.c.view()['install_enabled'])
        self.assertFalse(self.c.view()['generate_enabled'])
        self.query.assert_not_called(); self.processes.assert_not_called(); self.writer.assert_not_called()

    def test_multicandidate_requires_explicit_inspection(self):
        self.setup_controller(two=True)
        view = self.c.discover()
        self.assertEqual(len(view['candidates']), 2)
        self.assertFalse(view['generate_enabled'])
        self.assertIsNone(view['preview'])
        view = self.c.inspect(self.install)
        self.assertTrue(view['generate_enabled']); self.assertFalse(view['install_enabled'])
        self.assertEqual(view['preview']['file_version'], VERSION)
        self.assertEqual(view['preview']['origin'], 'steam_manifest')

    def test_manual_portable_selection_never_queries_registry(self):
        self.setup_controller()
        self.c.manual(self.install)
        view = self.c.inspect(self.install)
        self.assertEqual(view['preview']['origin'], 'manual')
        self.assertTrue(view['generate_enabled'])
        self.query.assert_not_called()

    def test_denial_latches_stop_and_refuses_manual_fallback(self):
        self.setup_controller(); self.query.side_effect = PermissionError('synthetic denied')
        self.assertTrue(self.c.discover()['stopped'])
        for operation in (self.c.discover, lambda: self.c.manual(self.install), lambda: self.c.inspect(self.install)):
            with self.assertRaisesRegex(EvidenceError, 'session_stopped'):
                operation()
        self.assertEqual(self.query.call_count, 1)
        self.assertEqual(self.fs.probes, [])

    def test_unknown_or_running_process_disables_generation(self):
        self.setup_controller(); self.c.manual(self.install)
        for state in (ProcessEvidence(False), ProcessEvidence(True, (child(self.install, 'Ld95.exe'),))):
            self.processes.return_value = state
            self.assertFalse(self.c.inspect(self.install)['generate_enabled'])
            self.assertIsNone(self.c.preview)
        self.writer.assert_not_called()

    def test_process_denial_latches_stop(self):
        self.setup_controller(); self.c.manual(self.install)
        self.processes.return_value = ProcessObservation(False, (), True, 'process_access_denied')
        self.assertTrue(self.c.inspect(self.install)['stopped'])
        with self.assertRaises(EvidenceError): self.c.inspect(self.install)
        self.assertEqual(self.processes.call_count, 1)

    def test_known_hash_preview_never_enables_install_even_if_release_approved(self):
        self.setup_controller(); self.c.manual(self.install); view = self.c.inspect(self.install)
        self.assertTrue(self.config['versions'][0]['release_approved'])
        self.assertFalse(view['preview']['can_install']); self.assertFalse(view['install_enabled'])

    def test_unknown_hash_is_visible_but_generation_disabled(self):
        self.setup_controller(); self.fs.add(child(self.install, 'Ld95.exe'), b'UNKNOWN')
        self.c.manual(self.install); view = self.c.inspect(self.install)
        self.assertEqual(len(view['preview']['source_sha256']), 64)
        self.assertFalse(view['generate_enabled'])

    def test_generation_requires_confirmation_and_fresh_process_evidence(self):
        self.setup_controller(); self.c.manual(self.install); self.c.inspect(self.install)
        with self.assertRaises(EvidenceError): self.c.generate('output', 'metadata')
        self.writer.assert_not_called()
        self.processes.return_value = ProcessEvidence(False)
        with self.assertRaisesRegex(EvidenceError, 'preview_changed'): self.c.generate('output', 'metadata', confirmed=True)
        self.writer.assert_not_called()

    def test_confirmed_generation_passes_only_selected_source_to_writer(self):
        self.setup_controller(); self.c.manual(self.install); self.c.inspect(self.install)
        result = self.c.generate('new.exe', 'new.json', confirmed=True)
        self.assertEqual(result, {'output_sha256': 'synthetic'})
        self.writer.assert_called_once_with(child(self.install, 'Ld95.exe'), 'new.exe', 'new.json')
        self.assertFalse(self.c.view()['install_enabled'])

    def test_failed_manual_selection_discards_previous_preview(self):
        self.setup_controller(); self.c.manual(self.install); self.c.inspect(self.install)
        view = self.c.manual('../bad')
        self.assertIsNone(view['preview']); self.assertEqual(view['candidates'], [])
        self.assertFalse(view['generate_enabled'])

    def test_cli_help_and_version_never_launch_gui(self):
        from ld2patch.desktop import main
        with patch('ld2patch.ui.launch', side_effect=AssertionError('No GUI')) as launch:
            for args in (['--help'], ['--version']):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                    main(args)
                self.assertEqual(result.exception.code, 0)
            launch.assert_not_called()

    def test_public_product_evidence_does_not_mark_local_installation(self):
        product = json.loads((ROOT / 'patches/steam-product.json').read_text(encoding='utf-8'))
        self.assertEqual(product['steam_app_id'], '335420')
        self.assertFalse(product['local_installation_verified'])
        self.assertEqual(product['source'], 'https://store.steampowered.com/app/335420/?l=english')


if __name__ == '__main__':
    unittest.main()
