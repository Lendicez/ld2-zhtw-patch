"""m063c tests: catalog v4 model + C core cross-check (synthetic only, no game bytes).
The C host test is built with the system C compiler when present, else skipped."""
import os, random, shutil, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog_v4 as c4  # noqa: E402

FI, FA, P, S = c4.FULL_ID, c4.FULL_ANY, c4.PREFIX, c4.SUFFIX
NAME = c4.SITE_FLAGS['name']
LIST = c4.SITE_FLAGS['item_list']


def kata(*codes):
    """Synthetic CP932 katakana run (0x83 0x40..0x96), not taken from the game."""
    return b''.join(bytes((0x83, 0x40 + c)) for c in codes)


A, B, C, D, E = kata(1), kata(2), kata(3), kata(4), kata(5)


def rows_basic():
    return [
        # Kris-like: item and female name share bytes.
        (FI, 28, A + B, '短劍X', 0), (FA, -1, A + B, '女名X', 0),
        # Halberd-like: item bytes equal a same-region male join.
        (FI, 99, C + D + E, '長柄X', 0), (P, -1, C, '前甲', 2), (S, -1, D + E, '後甲', 2),
        # Cross-region false split: true join is (A|B+C) in region 1; prefix A+B exists only
        # in region 3 and suffix C only in region 4, so v3 also sees (A+B|C).
        (P, -1, A, '前一', 1), (S, -1, B + C, '後一', 1),
        (P, -1, A + B, '前三', 3), (S, -1, C, '後四', 4),
    ]


class Model(unittest.TestCase):
    def setUp(self):
        self.look = c4.Lookup(c4.decode_v4(c4.encode_v4(rows_basic())))
        self.v3 = c4.lookup_v3_equivalent(rows_basic())

    def test_kris_name_site_gets_female_name(self):
        self.assertEqual(self.v3.find(A + B), '短劍X')                    # v3 blocker
        self.assertEqual(self.look.find(A + B, -1, NAME), '女名X')
        self.assertEqual(self.look.find(A + B, 28, c4.SITE_FLAGS['item_by_id']), '短劍X')
        self.assertEqual(self.look.find(A + B, -1, LIST), '短劍X')         # shop list unchanged

    def test_halberd_join_not_taken_by_item(self):
        self.assertEqual(self.v3.find(C + D + E), '長柄X')                 # v3 blocker
        self.assertEqual(self.look.find(C + D + E, -1, NAME), '前甲後甲')
        self.assertEqual(self.look.find(C + D + E, 99, 0), '長柄X')

    def test_cross_region_false_split_resolved(self):
        self.assertIsNone(self.v3.find(A + B + C))                         # v3 falls back
        self.assertEqual(self.look.find(A + B + C, -1, NAME), '前一後一')

    def test_same_region_ambiguity_still_falls_back(self):
        rows = rows_basic() + [(P, -1, A + B, '前一b', 1), (S, -1, C, '後一b', 1)]
        self.assertIsNone(c4.Lookup(rows).find(A + B + C, -1, NAME))

    def test_name_only_with_id_refused(self):
        self.assertIsNone(self.look.find(A + B, 28, NAME))

    def test_unknown_flags_refused(self):
        self.assertIsNone(self.look.find(A + B, -1, 8))

    def test_region_contract(self):
        for bad in [(P, -1, A, 'x', 0), (S, -1, A, 'x', 5), (FI, 1, A, 'x', 1), (FA, -1, A, 'x', 2)]:
            with self.assertRaises(c4.Refuse):
                c4.make_row(*bad)

    def test_same_fragment_two_regions_may_differ(self):
        rows = [(P, -1, A, '甲', 1), (P, -1, A, '乙', 2), (S, -1, B, '丙', 1), (S, -1, C, '丁', 2)]
        look = c4.Lookup(c4.decode_v4(c4.encode_v4(rows)))
        self.assertEqual(look.find(A + B, -1, NAME), '甲丙')
        self.assertEqual(look.find(A + C, -1, NAME), '乙丁')

    def test_version_fences(self):
        blob = c4.encode_v4(rows_basic())
        self.assertEqual(struct.unpack_from('<H', blob, 4)[0], 4)
        v3 = c4.c3.encode_v3([r[:4] for r in rows_basic() if r[0] in (FI, FA)])
        with self.assertRaises(c4.Refuse):
            c4.decode_v4(v3)
        with self.assertRaises(c4.Refuse):
            c4.c3.decode_v3(blob)

    def test_deterministic(self):
        rows = rows_basic()
        self.assertEqual(c4.encode_v4(rows), c4.encode_v4(list(reversed(rows))))


def random_rows(rng):
    rows, seen = [], set()
    for _ in range(rng.randint(20, 80)):
        kind = rng.choice((FI, FA, P, S))
        ansi = kata(*[rng.randint(0, 6) for _ in range(rng.randint(1, 3))])
        ident = rng.randint(0, 5) if kind == FI else -1
        region = rng.randint(1, 4) if kind in (P, S) else 0
        if (kind, ident, ansi, region) in seen:
            continue
        seen.add((kind, ident, ansi, region))
        rows.append((kind, ident, ansi, rng.choice(['甲', '乙', '丙', '丁戊']), region))
    return rows


@unittest.skipUnless(shutil.which('gcc') or shutil.which('cc'), 'no host C compiler')
class CrossCheck(unittest.TestCase):
    """Python model and C core agree on random synthetic catalogs and probes."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ld2c4-')
        cls.exe = os.path.join(cls.tmp, 'c4test')
        cc = shutil.which('gcc') or shutil.which('cc')
        subprocess.run([cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-o', cls.exe,
                        str(HERE / 'native-v4' / 'catalog_v4_host_test.c')], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_cases(self, blob, cases, opened=1):
        b, c = os.path.join(self.tmp, 'b.bin'), os.path.join(self.tmp, 'c.txt')
        Path(b).write_bytes(blob)
        lines = [f'open {opened}']
        for ansi, ident, flags, want in cases:
            lines.append(f"{ansi.hex()} {ident} {flags} {want.encode('utf-16le').hex() if want else '-'}")
        Path(c).write_text('\n'.join(lines) + '\n')
        return subprocess.run([self.exe, b, c], capture_output=True, text=True)

    def test_basic(self):
        rows = rows_basic()
        look = c4.Lookup(rows)
        probes = [A + B, C + D + E, A + B + C, A, B + C, kata(9)]
        cases = [(p, i, f, look.find(p, i, f)) for p in probes for i in (-1, 28, 99) for f in range(8)]
        r = self.run_cases(c4.encode_v4(rows), cases)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_random(self):
        rng = random.Random(0x4c4432)
        total = 0
        for _ in range(60):
            rows = random_rows(rng)
            look = c4.Lookup(rows)
            probes = {r[2] for r in rows} | {a + b for a in {r[2] for r in rows if r[0] == P}
                                            for b in {r[2] for r in rows if r[0] == S}}
            cases = [(p, i, f, look.find(p, i, f)) for p in sorted(probes)[:120] for i in (-1, 0, 3) for f in range(8)]
            total += len(cases)
            r = self.run_cases(c4.encode_v4(rows), cases)
            self.assertEqual(r.returncode, 0, r.stdout)
        self.assertGreater(total, 5000)

    def test_v3_blob_refused(self):
        v3 = c4.c3.encode_v3([(FA, -1, A, 'x')])
        self.assertIn('refused as expected', self.run_cases(v3, [], opened=0).stdout)

    def test_bad_region_tag_fails_closed(self):
        blob = bytearray(c4.encode_v4([(P, -1, A, '甲', 1), (S, -1, B, '乙', 1)]))
        blob[32 + 7] = 0                                   # prefix row loses its region
        r = self.run_cases(bytes(blob), [(A + B, -1, NAME, None)])
        self.assertEqual(r.returncode, 0, r.stdout)



class SiteClasses(unittest.TestCase):
    def test_cover_enable_plan_exactly(self):
        import enable_plan_m063 as ep
        self.assertEqual(set(c4.LIST_SITE_CLASS), set(ep.M061_PRIORITY_LIST) | set(ep.M063_LIST_EXTRA))
        self.assertEqual(len(c4.LIST_SITE_CLASS), ep.EXPECTED_COUNTS['list_sites'])
        self.assertTrue(set(c4.LIST_SITE_CLASS.values()) <= set(c4.SITE_FLAGS))
        self.assertEqual(c4.TEXTOUT_SITE_CLASS, 'name')
        self.assertEqual(c4.SITE_FLAGS[c4.NAMEPAIR_SITE_CLASS], 0)
        counts = {k: list(c4.LIST_SITE_CLASS.values()).count(k) for k in set(c4.LIST_SITE_CLASS.values())}
        self.assertEqual(counts, {'name': 11, 'item_list': 4, 'unclassified_list': 3})

    def test_only_name_sites_skip_items(self):
        for k, f in c4.SITE_FLAGS.items():
            self.assertEqual(bool(f & c4.NAME_ONLY), k == 'name')


LAB = os.environ.get('LD2_M063C_LAB')  # dir with Ld95.exe, draft json + .sha256, m051 json


@unittest.skipUnless(LAB, 'licensed lab inputs not provided (LD2_M063C_LAB)')
class LabSummary(unittest.TestCase):
    def test_lab_summary_reproduces(self):
        import json
        d = Path(LAB)
        draft = next(d.glob('*draft*.json'))
        r = subprocess.run([sys.executable, '-B', str(HERE / 'lab_v4_names.py'), '--exe', str(d / 'Ld95.exe'),
                            '--draft', str(draft), '--draft-sha', (d / 'draft.sha256').read_text().split()[0],
                            '--m051', str(next(d.glob('m051*.json')))], capture_output=True, text=True, check=True)
        got = json.loads(r.stdout)
        want = json.loads((HERE / 'lab_v4_names.summary.json').read_text())
        self.assertEqual(got, want)


if __name__ == '__main__':
    unittest.main()
