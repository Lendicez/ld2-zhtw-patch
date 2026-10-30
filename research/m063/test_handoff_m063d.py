"""m063d handoff consistency (no lab inputs needed): the PowerShell pins, the committed delta manifests and the
docs agree; nothing release-like is claimed; no delta .bin / EXE sits in the handoff folder."""
import hashlib, json, re, unittest
from pathlib import Path

H = Path(__file__).resolve().parent / 'HANDOFF-ENABLE-M063D'
PS = H / 'WINDOWS-ENABLE-M063D.ps1'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


class HandoffM063D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps = PS.read_bytes().decode('utf-8-sig')
        cls.mans = {m: json.loads((H / f'm063d-v4-lab_preview-mode{m}.delta.json').read_text(encoding='utf-8')) for m in (2, 0)}

    def block(self, mode):
        a = self.ps.index('if ($Mode0) {'); b = self.ps.index('} else {', a); c = self.ps.index('}', b + 8)
        txt = self.ps[a:b] if mode == 0 else self.ps[b:c]
        return dict(re.findall(r"\$(\w+) = '([0-9a-f]{64})'", txt))

    def test_bom_for_windows_powershell(self):
        self.assertTrue(PS.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_pins_match_manifests(self):
        for m, man in self.mans.items():
            k = self.block(m)
            self.assertEqual(k['OUT_SHA'], man['out_sha256'])
            self.assertEqual(k['INERT_SHA'], man['inert_sha256'])
            self.assertEqual(k['DELTA_SHA'], man['delta_sha256'])
            self.assertEqual(k['DELTA_JSON_SHA'], sha(H / f'm063d-v4-lab_preview-mode{m}.delta.json'))
            self.assertEqual(man['list_mode'], m)
            for key in ('NAME_OBJ_SHA', 'LIST_OBJ_SHA', 'TEXTOUT_OBJ_SHA', 'BLOB_SHA', 'M045_SHA'):
                self.assertIn(key, self.ps)
            for f, key in (('name_object_sha256', 'NAME_OBJ_SHA'), ('list_object_sha256', 'LIST_OBJ_SHA'),
                           ('textout_object_sha256', 'TEXTOUT_OBJ_SHA'), ('blob_sha256', 'BLOB_SHA'), ('base_sha256', 'M045_SHA')):
                self.assertIn(f"${key} = '{man[f]}'", self.ps)
            self.assertIn(f"$DELTA_SIZE = {man['delta_size']}", self.ps)
            self.assertIn(f"$OUT_SIZE = {man['out_size']}", self.ps)
            self.assertIn(f"$OUT_SIZE_OF_IMAGE = {man['size_of_image']}", self.ps)
            self.assertIn(f"$LIST_MODE_SLOT_VA = {man['list_mode_slot_va']}", self.ps)

    def test_allowed_code_runs_exact(self):
        allowed = set(re.findall(r"'(0x[0-9a-f]+:\d+)'", self.ps[self.ps.index('$ALLOWED_CODE_RUNS'):self.ps.index('$IAT_PROBES')]))
        for man in self.mans.values():
            code = {'0x%x:%d' % (r['offset'], r['length']) for r in man['runs'] if r['kind'] == 'code'}
            self.assertEqual(code, allowed)
            self.assertEqual(len(code), 45)
            self.assertEqual(sum(r['length'] for r in man['runs'] if r['kind'] == 'code'), 245)
            self.assertEqual(sum(r['length'] for r in man['runs']), man['delta_size'])
            self.assertTrue(all(r['offset'] + r['length'] <= 0x1000 for r in man['runs'] if r['kind'] == 'header'))
            app = [r for r in man['runs'] if r['kind'] == 'append']
            self.assertEqual(len(app), 1); self.assertEqual(app[0]['offset'], man['base_size'])

    def test_never_release(self):
        for man in self.mans.values():
            self.assertIs(man['production_can_apply'], False); self.assertIs(man['release_approved'], False)
            self.assertIs(man['release_eligible_catalog'], False); self.assertEqual(man['catalog_policy'], 'lab_preview')
        self.assertNotIn('production_can_apply = $true', self.ps)
        self.assertNotIn('release_approved = $true', self.ps)

    def test_inert_first_gate(self):
        self.assertIn("if ($done -notcontains 'L1') { Stop-Run", self.ps)
        self.assertIn("@('ok', 'soft-warn-exit1') -notcontains [string]$l1.exit_policy", self.ps)
        self.assertIn("if ($done -notcontains 'E') { Stop-Run", self.ps)

    def test_folder_has_no_binaries(self):
        for p in H.iterdir():
            self.assertNotIn(p.suffix.lower(), ('.bin', '.exe', '.zip', '.ldp', '.dmp', '.obj'), p.name)

    def test_docs_say_not_run(self):
        for n in ('README.zh-TW.md', 'PLAN-ACCEPTANCE.zh-TW.md'):
            self.assertIn('未在 Win11 執行', (H / n).read_text(encoding='utf-8'))
        steps = (H / 'USER-STEPS.zh-TW.md').read_text(encoding='utf-8')
        for sw in ('-CheckOnly', '-LaunchInert', '-Enable', '-LaunchEnabled', '-Finalize', '-Pack'):
            self.assertIn(sw, steps)
            self.assertIn(f'[switch]${sw[1:]}', self.ps)


if __name__ == '__main__':
    unittest.main()
