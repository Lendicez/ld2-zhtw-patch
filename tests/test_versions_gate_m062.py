"""m062: versions.json gates per profile (m020 != m045). Linux-only, no game.

Only repository JSON and invented in-memory bytes are used. No write, install,
registry, process or game execution. release_approved / production_can_apply
stay false; these tests fail if anyone flips them.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from ld2patch.discovery import EvidenceError, discover
from ld2patch.planner import ProcessEvidence, _versions, plan_install
from ld2patch.profiles import (DEFAULT_TRIAL_PROFILE, PINS, PROFILE_IDS, planner_config,
                               profile_info)
from fake_steam import ORIGINAL, example

PATCHES = ROOT / 'patches'
M020_OUT = 'a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81'
M045_OUT = '4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7'


def top_level():
    return json.loads((PATCHES / 'versions.json').read_text(encoding='utf-8'))


class ProfileVersionPins(unittest.TestCase):
    def test_m020_and_m045_outputs_are_distinct_pins(self):
        self.assertEqual(PINS['m020']['output_hash'], M020_OUT)
        self.assertEqual(PINS['m045']['output_hash'], M045_OUT)
        self.assertNotEqual(M020_OUT, M045_OUT)
        self.assertNotEqual(PINS['m020']['output_size'], PINS['m045']['output_size'])
        # Every profile has its own output hash; sizes alone are NOT unique
        # (m042 and m045 are both 7,118,848 bytes), so hash must decide.
        hashes = [PINS[p]['output_hash'] for p in PROFILE_IDS]
        self.assertEqual(len(set(hashes)), len(hashes))
        self.assertEqual(PINS['m042']['output_size'], PINS['m045']['output_size'])

    def test_each_profile_planner_config_matches_its_own_pin(self):
        for p in PROFILE_IDS:
            with self.subTest(profile=p):
                config = planner_config(p, PATCHES)
                (v,) = config['versions']
                self.assertEqual(config['schema_version'], 1)
                self.assertEqual(v['historical_m020_sha256'], PINS[p]['output_hash'])
                self.assertEqual(v['historical_m020_size'], PINS[p]['output_size'])
                self.assertEqual(v['id'], PINS[p]['recipe']['version_id'])
                self.assertIs(v['release_approved'], False)
                self.assertIs(profile_info(p)['production_can_apply'], False)
                _versions(config)

    def test_default_profile_is_m045_and_not_the_top_level_m020_record(self):
        self.assertEqual(DEFAULT_TRIAL_PROFILE, 'm045')
        default = planner_config(DEFAULT_TRIAL_PROFILE, PATCHES)['versions'][0]
        legacy = top_level()['versions'][0]
        self.assertEqual(default['historical_m020_sha256'], M045_OUT)
        self.assertNotEqual(default['historical_m020_sha256'], legacy['historical_m020_sha256'])
        self.assertNotEqual(default['id'], legacy['id'])
        # Same licensed source on both sides; only the expected output differs.
        self.assertEqual(default['source_sha256'], legacy['source_sha256'])

    def test_m020_planner_config_equals_top_level_versions_json(self):
        self.assertEqual(planner_config('m020', PATCHES), top_level())

    def test_top_level_still_pins_m020_until_release_gate(self):
        # Tripwire: deliberately unchanged by m062. Repointing the top-level
        # allowlist belongs to the release-gate milestone after Win11 acceptance.
        legacy = top_level()
        self.assertEqual(legacy['versions'][0]['historical_m020_sha256'], M020_OUT)
        self.assertTrue(all(v['release_approved'] is False for v in legacy['versions']))

    def test_no_profile_versions_file_is_release_approved(self):
        files = [PATCHES / 'versions.json'] + [PATCHES / p / 'versions.json' for p in PROFILE_IDS if p != 'm020']
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                data = json.loads(f.read_text(encoding='utf-8'))
                self.assertTrue(all(v['release_approved'] is False for v in data['versions']))


class MixedRecordsRejected(unittest.TestCase):
    def test_m020_and_m045_cannot_share_one_allowlist(self):
        # Same source hash in two entries is ambiguous: planner must refuse
        # rather than pick whichever output happens to be listed first.
        merged = copy.deepcopy(top_level())
        merged['versions'].append(planner_config('m045', PATCHES)['versions'][0])
        with self.assertRaises(EvidenceError) as ctx:
            _versions(merged)
        self.assertEqual(ctx.exception.code, 'invalid_or_ambiguous_version_hash')

    def _tampered(self, mutate):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(PATCHES / 'm045', tmp / 'm045')
        path = tmp / 'm045' / 'versions.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        mutate(data['versions'][0])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return tmp

    def test_tampered_profile_records_are_refused(self):
        mutations = {
            'release_approved_true': lambda v: v.update(release_approved=True),
            'm020_output_in_m045_record': lambda v: v.update(expected_output_sha256=M020_OUT,
                                                              expected_output_size=PINS['m020']['output_size']),
            'm020_version_id': lambda v: v.update(id='ld95-1.0.3.16'),
            'size_only_changed': lambda v: v.update(expected_output_size=v['expected_output_size'] + 1),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name), self.assertRaises(ValueError):
                planner_config('m045', self._tampered(mutate))

    def test_unknown_profile_refused(self):
        for bad in ('m046', 'm061', '../m045', None):
            with self.subTest(profile=bad), self.assertRaises(ValueError):
                planner_config(bad, PATCHES)


class PlannerUsesSelectedProfileRecord(unittest.TestCase):
    """Invented bytes stand in for m020/m045 outputs of one synthetic source."""

    OUT_M020 = b'SYNTHETIC M020-LIKE OUTPUT (239 locations)'
    OUT_M045 = b'SYNTHETIC M045-LIKE OUTPUT (554 locations, different bytes)'

    def _plan(self, body, output):
        fs, _, install, config = example()
        fs.add(install + r'\Ld95.exe', body)
        v = config['versions'][0]
        v['historical_m020_sha256'] = hashlib.sha256(output).hexdigest()
        v['historical_m020_size'] = len(output)
        v['release_approved'] = False
        return plan_install(discover([r'C:\Synthetic Steam'], config['steam_app_id'], fs), config, fs, ProcessEvidence(True))

    def test_m045_record_does_not_recognise_m020_output(self):
        plan = self._plan(self.OUT_M020, self.OUT_M045)
        self.assertEqual(plan.status, 'blocked')
        self.assertEqual(plan.issues[0].code, 'unsupported_hash')
        self.assertFalse(plan.can_apply); self.assertEqual(plan.proposed_changes, [])

    def test_m045_record_recognises_m045_output_as_already_patched(self):
        plan = self._plan(self.OUT_M045, self.OUT_M045)
        self.assertEqual(plan.status, 'already_patched')
        self.assertEqual(plan.expected_output_sha256, hashlib.sha256(self.OUT_M045).hexdigest())
        self.assertFalse(plan.can_apply)

    def test_original_still_stops_at_release_gate(self):
        plan = self._plan(ORIGINAL, self.OUT_M045)
        self.assertEqual(plan.issues[0].code, 'release_not_approved')
        self.assertEqual(plan.proposed_changes[0]['after_sha256'], hashlib.sha256(self.OUT_M045).hexdigest())
        self.assertFalse(plan.can_apply)


if __name__ == '__main__':
    unittest.main()
