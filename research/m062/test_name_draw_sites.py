"""m062->m063 name draw-site tests. Summary/source checks always run; the EXE re-run skips
unless LD2_TEST_EXE (pristine Ld95.exe) is set; the i386 mock skips unless the `ziglang`
module is importable. Emits nothing but pass/fail."""
import importlib.util, json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUMMARY = HERE / 'name_draw_sites.summary.json'
NATIVE = HERE / 'native-m063'
PARTY = 0x438910


class Summary(unittest.TestCase):
    def setUp(self):
        self.raw = SUMMARY.read_text(encoding='ascii')
        self.s = json.loads(self.raw)

    def test_ascii_and_flags(self):
        self.assertTrue(all(ord(c) < 0x80 for c in self.raw))
        self.assertIs(self.s['production_can_apply'], False)
        self.assertIs(self.s['release_approved'], False)
        self.assertIs(self.s['namepair_v3_covers'], False)
        self.assertEqual(self.s['proposed_helper'], '@LD2_NameTextOut@24')

    def test_counts_consistent(self):
        t = self.s['textout_sites']
        whole = [x for x in t if x['tag'] in ('name', 'bare', 'appended')]
        self.assertEqual(len(whole), self.s['textout_whole_name_sites'])
        self.assertEqual(sum(1 for x in whole if x['install']['kind'] == 'pair5'), self.s['textout_pair5_installable'])
        self.assertEqual(sum(1 for x in whole if x['install']['kind'] == 'manual'), self.s['textout_manual_install'])
        self.assertTrue(all(x['install'] is None for x in t if x['tag'] == 'composite'))
        n = sum(self.s['counts'].values())
        self.assertEqual(n, len(t) + len(self.s['other_sites']))

    def test_party_panel(self):
        p = [x for x in self.s['textout_sites'] if int(x['function'], 16) == PARTY]
        self.assertEqual(len(p), 18)
        xs = sorted({x['xy'][0] for x in p}); ys = sorted({x['xy'][1] for x in p})
        self.assertEqual(xs, [10, 11, 12, 282, 283, 284])
        self.assertEqual(ys, [232, 233, 262, 263, 292, 293])
        for x in p:
            i = x['install']
            self.assertEqual(i['kind'], 'pair5')
            self.assertEqual((i['cdc_reg'], i['branch_targets_inside']), ('esi', 0))
            self.assertLess(int(i['pair_va'], 16), int(x['va'], 16))
            self.assertLessEqual(int(x['va'], 16) - int(i['pair_va'], 16), 0x20)

    def test_pair_sites_unique_and_short(self):
        pairs = [int(x['install']['pair_va'], 16) for x in self.s['textout_sites']
                 if x['install'] and x['install']['kind'] == 'pair5']
        self.assertEqual(len(pairs), len(set(pairs)))
        for x in self.s['textout_sites']:
            i = x['install']
            if i and i['kind'] == 'pair5':
                self.assertTrue(re.fullmatch(r'[0-9a-f]{8}', i['orig_sha256_8']))
                self.assertIn(i['call_reg'], ('eax', 'edx'))


class Sources(unittest.TestCase):
    def test_helper_contract(self):
        src = (NATIVE / 'name_textout_v3.cpp').read_text(encoding='ascii')
        hdr = (NATIVE / 'name_textout_v3.h').read_text(encoding='ascii')
        self.assertIn('LD2C3_ALLOW_ANY|LD2C3_ALLOW_JOIN', src)
        self.assertIn('LD2C3_ANY_ID', src)
        self.assertIn('__fastcall LD2_NameTextOut', hdr)
        self.assertNotRegex(src, r'#include\s*<')           # no CRT/Windows headers
        self.assertNotRegex(src, r'\b(malloc|new |memcpy|memset|try|catch)\b')
        for sym in ('LD2_FindCopy(', 'LD2_Wipe(', 'LD2_NamePair('):  # no clash with NamePair v3
            self.assertNotIn(sym, src.replace('LD2N_', 'X'))


@unittest.skipUnless(importlib.util.find_spec('ziglang'), 'ziglang not installed')
class Mock(unittest.TestCase):
    def test_i386_mock(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'mock'
            subprocess.run([sys.executable, '-m', 'ziglang', 'c++', '-target', 'x86-linux-musl', '-fms-extensions',
                            '-fasm-blocks', '-D_M_IX86=600', '-w', str(NATIVE / 'name_textout_v3.cpp'),
                            str(NATIVE / 'name_textout_mock_v3.cpp'), '-o', str(exe)], check=True, cwd=d)
            out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(out.returncode, 0, out.stdout[-2000:])
            r = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertEqual(r['failed'], 0)
            self.assertFalse(r['game_or_gdi_called'])
            self.assertGreaterEqual(r['cases'], 25)


@unittest.skipUnless(os.environ.get('LD2_TEST_EXE'), 'licensed input not provided')
class Licensed(unittest.TestCase):
    def test_rerun_matches_summary(self):
        sys.path.insert(0, str(HERE))
        import hashlib, pefile
        import name_draw_sites as N
        raw = Path(os.environ['LD2_TEST_EXE']).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        got = N.summarize(N.run(pefile.PE(data=raw)), sha)
        self.assertEqual(json.loads(json.dumps(got)), json.loads(SUMMARY.read_text()))


if __name__ == '__main__':
    unittest.main()
