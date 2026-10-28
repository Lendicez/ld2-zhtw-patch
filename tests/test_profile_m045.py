import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.catalog import output_hash, validate_catalog
from ld2patch.contracts import contract, native_cp950, validate
from ld2patch.patch_engine import build_patch, strict_json
from ld2patch.pe_resources import PE, sha, string_block

def profile(name):
    folder = ROOT / 'patches' / name
    return ((folder / 'catalog.json').read_bytes(),
            strict_json((folder / 'versions.json').read_bytes()),
            strict_json((folder / 'recipe.json').read_bytes()))

class StatusPromptProfileTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.versions, self.recipe = profile('m045')
        self.catalog = json.loads(self.raw)
        self.review = json.loads((ROOT / 'patches/m045/review.json').read_bytes())

    def test_two_new_prompts_preserve_all_prior_entries_fonts_and_identifier(self):
        old = json.loads(profile('m042')[0])
        self.assertEqual(self.catalog['entries'][:552], old['entries'])
        self.assertEqual(self.catalog['dialog_fonts'], old['dialog_fonts'])
        self.assertEqual(validate_catalog(self.catalog), 554)
        self.assertEqual({e['string_id'] for e in self.catalog['entries'][552:]}, {57345, 57346})
        self.assertEqual(self.review['preserved'], [dict(string_id=57344, source_anchor='LD95', reason='Program identifier; retain exactly')])
        self.assertEqual(self.review['empty_slots_preserved'], 13)

    def test_source_hash_contracts_f1_and_shorter_candidates(self):
        anchors = {e['string_id']: e for e in self.review['changes']}
        for entry in self.catalog['entries'][552:]:
            source = anchors[entry['string_id']]['source_anchor']
            translated = entry['translation']
            self.assertEqual(sha(source.encode('utf-16le')), entry['source_utf16_sha256'])
            self.assertEqual(contract(source), entry['source_contract'])
            validate(translated, entry['source_contract'])
            self.assertEqual(source.count('[F1]'), translated.count('[F1]'))
            self.assertLess(len(translated), len(source))
            self.assertFalse(entry['current_version_game_seen'])

    def test_16_corrupted_contract_or_unrepresentable_inputs_rejected(self):
        for entry in self.catalog['entries'][552:]:
            for suffix in ('%d', '%s', '%%', '\n', '\0', '(&Q)', '\tCtrl+Q', '\U0001f642'):
                with self.subTest(id=entry['string_id'], suffix=repr(suffix)):
                    with self.assertRaises((ValueError, UnicodeError)):
                        validate(entry['translation'] + suffix, entry['source_contract'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native codec unavailable')
    def test_native_cp950_candidates_lossless_original_prompts_lossy(self):
        for entry in self.review['changes']:
            self.assertEqual(native_cp950(entry['translation']), entry['native_cp950_bytes'])
            with self.assertRaises(ValueError):
                native_cp950(entry['source_anchor'])

    def test_version_pin_and_explicit_offline_boundary(self):
        expected = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'
        self.assertEqual(sha(self.raw), self.recipe['catalog_sha256'])
        self.assertEqual(output_hash(self.catalog), expected)
        self.assertEqual(self.versions['versions'][0]['expected_output_sha256'], expected)
        self.assertEqual(self.recipe['id'], 'm045-status-prompts-v1')
        self.assertEqual(self.recipe['text_locations'], 554)
        self.assertFalse(self.versions['versions'][0]['release_approved'])
        for field in ('runtime_seen', 'game_executed', 'production_can_apply', 'm039_formatter_enabled', 'm040_layout_included', 'packaged_tool_updated'):
            self.assertFalse(self.review[field])
        self.assertEqual(self.review['trial_default_profile'], 'm042')
        # The immutable m045 review describes its original offline-only delivery.
        # m047 now bundles that exact profile, without widening its runtime claim.
        from ld2patch.profiles import DEFAULT_TRIAL_PROFILE, PROFILE_IDS, profile_info
        self.assertEqual(DEFAULT_TRIAL_PROFILE, 'm045')
        self.assertIn('m045', PROFILE_IDS)
        current=profile_info('m045')
        self.assertEqual(current['expected_output_sha256'], expected)
        self.assertFalse(current['production_can_apply'])
        self.assertFalse(current['runtime_tested'])
        self.assertEqual(len(self.review['offscreen_measurements']), 8)
        self.assertTrue(all(not x['missing_glyphs'] for x in self.review['offscreen_measurements']))

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'), 'Licensed input absent; m045 rebuild SKIPPED')
    def test_licensed_twice_exact_hash_and_wrong_input_or_cross_profile_refused(self):
        path = Path(os.environ['LD2_TEST_EXE'])
        source = path.read_bytes()
        first = build_patch(source, self.raw, self.versions, self.recipe)
        second = build_patch(source, self.raw, self.versions, self.recipe)
        self.assertEqual(first, second)
        self.assertEqual(sha(first.output), output_hash(self.catalog))
        self.assertEqual(len(first.output), 7118848)
        self.assertFalse(first.metadata['production_can_apply'])
        old_raw, old_versions, old_recipe = profile('m042')
        for args in ((old_raw, self.versions, self.recipe), (self.raw, old_versions, self.recipe), (self.raw, self.versions, old_recipe)):
            with self.assertRaises(ValueError):
                build_patch(source, *args)
        corrupted = bytearray(source)
        corrupted[4096] ^= 1
        with self.assertRaises(ValueError):
            build_patch(bytes(corrupted), self.raw, self.versions, self.recipe)
        self.assertEqual(path.read_bytes(), source)

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'), 'Licensed input absent; m045 resource comparison SKIPPED')
    def test_licensed_only_two_strings_change_all_other_resources_stay_identical(self):
        source = Path(os.environ['LD2_TEST_EXE']).read_bytes()
        old = PE(build_patch(source, *profile('m042')).output)
        built = build_patch(source, self.raw, self.versions, self.recipe)
        new = PE(built.output)
        before = {tuple(r['path']): old.payload(r) for r in old.resources}
        after = {tuple(r['path']): new.payload(r) for r in new.resources}
        self.assertEqual(before.keys(), after.keys())
        self.assertEqual({k for k in before if before[k] != after[k]}, {(6, 3585, 1041)})
        a, b = string_block(before[(6, 3585, 1041)]), string_block(after[(6, 3585, 1041)])
        self.assertEqual([i for i in range(16) if a[i] != b[i]], [1, 2])
        self.assertEqual(b[0], 'LD95')
        self.assertTrue(all(s['unchanged'] for s in built.metadata['proof']['non_resource_sections']))
        self.assertEqual(before[(24, 1, 1033)], after[(24, 1, 1033)])

if __name__ == '__main__':
    unittest.main()
