import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch import generator
from ld2patch.patch_engine import _safe_path
from pe_fixture import bundle


class Generator(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ld2-generator-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ('input', 'output', 'resources'):
            (self.root / name).mkdir()
        source, catalog, versions, recipe, self.expected = bundle()
        # The CLI uses one fixed catalog name; the synthetic fixture is rebound
        # consistently in memory rather than accepting arbitrary runtime input.
        recipe['catalog'] = versions['versions'][0]['catalog'] = 'ui-m020.zh-TW.json'
        self.source = self.root / 'input' / 'original.exe'
        self.source.write_bytes(source)
        self.original = source
        self.output = self.root / 'output' / 'result.exe'
        self.metadata = self.output.with_suffix('.json')
        resources = self.root / 'resources'
        (resources / 'ui-m020.zh-TW.json').write_bytes(catalog)
        (resources / 'm020-recipe.json').write_text(json.dumps(recipe), encoding='utf-8')
        (resources / 'versions.json').write_text(json.dumps(versions), encoding='utf-8')
        self.addCleanup(patch.stopall)
        patch.object(generator, 'resource_root', return_value=resources).start()
        patch.object(generator, 'elevated', return_value=False).start()

    def run_cli(self, **paths):
        args = {'input': self.source, 'out': self.output, 'metadata-out': self.metadata}
        args.update(paths)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = generator.main([arg for k, v in args.items() for arg in ('--' + k, str(v))])
        return code, out.getvalue(), err.getvalue()

    def test_generates_only_new_artifacts_from_synthetic_bundle(self):
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(self.output.read_bytes(), self.expected)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(json.loads(out)['installed'])
        self.assertFalse(json.loads(out)['production_can_apply'])

    def test_elevation_refused_before_resource_or_input_access(self):
        with patch.object(generator, 'elevated', return_value=True), patch.object(generator, 'resource_root', side_effect=AssertionError('No access')):
            code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn('Administrator execution refused', err)
        self.assertFalse(self.output.exists())

    def test_unknown_source_creates_no_artifacts(self):
        self.source.write_bytes(b'unknown source bytes')
        code, _, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn('refused_or_failed', err)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.metadata.exists())

    def test_existing_output_preserved(self):
        self.output.write_bytes(b'KEEP')
        self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(self.output.read_bytes(), b'KEEP')
        self.assertFalse(self.metadata.exists())

    def test_original_directory_and_traversal_refused(self):
        for target in (self.source, self.source.parent / 'new.exe', self.output.parent / '..' / 'escape.exe'):
            with self.subTest(target=target):
                self.assertEqual(self.run_cli(out=target)[0], 1)
                self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(self.output.exists())

    def test_hardlinked_input_refused_without_writes(self):
        alias = self.source.with_name('alias.exe')
        os.link(self.source, alias)
        self.assertEqual(self.run_cli()[0], 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(alias.read_bytes(), self.original)

    def test_reparse_metadata_refused_without_following(self):
        original = Path.lstat
        def fake(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == self.output.parent:
                class Reparse:
                    st_mode = result.st_mode
                    st_file_attributes = 0x400
                return Reparse()
            return result
        with patch.object(Path, 'lstat', fake), self.assertRaisesRegex(ValueError, 'reparse'):
            _safe_path(self.output, False)

    def test_help_and_version_need_no_resource_or_source(self):
        for argv in (['--help'], ['--version']):
            with self.subTest(argv=argv), patch.object(generator, 'resource_root', side_effect=AssertionError('No data access')):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
                    generator.main(argv)
                self.assertEqual(result.exception.code, 0)
                self.assertIn('generator', output.getvalue())


if __name__ == '__main__':
    unittest.main()
