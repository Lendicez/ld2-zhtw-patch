"""m062 tests. Synthetic tests always run. Licensed-input tests skip unless
LD2_TEST_EXE (pristine Ld95.exe) and LD2_M051_CATALOG are set; the Mina draft
cross-check also needs LD2_M062_DRAFT + LD2_M062_DRAFT_SHA (lab only)."""
import hashlib, json, os, random, shutil, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog_v3 as c3
import sidecar_plan as sp

KATA = [bytes([0x83, b]) for b in range(0x40, 0x97) if b != 0x7F]  # CP932 katakana


def kname(rng, lo=1, hi=4):
    return b''.join(rng.choice(KATA) for _ in range(rng.randint(lo, hi)))


def synthetic_rows(n_items=300, n_any=200, n_frag=150, seed=62):
    rng, rows, used = random.Random(seed), [], set()
    def fresh(kind, lo=2, hi=5):
        while True:
            a = kname(rng, lo, hi)
            if (kind, a) not in used:
                used.add((kind, a)); return a
    for i in range(n_items):
        a = fresh(c3.FULL_ID)
        for s in [b''] + [(' +%d' % k).encode() for k in range(1, 11)]:
            rows.append((c3.FULL_ID, i % 446, a + s, '品%d' % i + s.decode()))
    for i in range(n_any):
        rows.append((c3.FULL_ANY, c3.ANY_ID, fresh(c3.FULL_ANY), '女%d' % i))
    for i in range(n_frag):
        rows.append((c3.PREFIX, c3.ANY_ID, fresh(c3.PREFIX, 1, 3), '前%d' % i))
        rows.append((c3.SUFFIX, c3.ANY_ID, fresh(c3.SUFFIX, 1, 3), '後%d' % i))
    return rows


def cases(look, rows, rng, extra=400):
    probes = set()
    for kind, ident, ansi, text in rows[::3]:
        probes.add((ansi, ident if kind == c3.FULL_ID else c3.ANY_ID, 1))
        probes.add((ansi, c3.ANY_ID, 0))
    pre = [r[2] for r in rows if r[0] == c3.PREFIX]; suf = [r[2] for r in rows if r[0] == c3.SUFFIX]
    for _ in range(extra):
        probes.add((rng.choice(pre) + rng.choice(suf), c3.ANY_ID, 1))
        probes.add((kname(rng, 1, 6), rng.choice([c3.ANY_ID, 3, 7]), 1))
    probes.add((b'\x83', c3.ANY_ID, 1))  # truncated lead byte
    out = []
    for ansi, ident, join in sorted(probes):
        if not 0 < len(ansi) <= 64:
            continue
        got = look.find(ansi, ident, bool(join))
        out.append('%s %d %d %s' % (ansi.hex(), ident, join, got.encode('utf-16le').hex() if got else '-'))
    return out


class Synthetic(unittest.TestCase):
    def test_v1_matches_m060_layout_and_cap(self):
        rows = [(c3.FULL_ID, 5, b'\x83\x41', '甲'), (c3.FULL_ID, 445, b'\x83\x41 +1', '甲 +1')]
        enc = c3.encode_v1(rows)
        want = b''.join(struct.pack('<iI64sI514s2x', i, len(a), a, len(t.encode('utf-16le')) // 2, t.encode('utf-16le') + b'\0\0') for _, i, a, t in rows)
        self.assertEqual(enc, want)
        m060 = HERE.parent / 'm060' / 'memory_plan.py'
        if m060.exists():
            sys.path.insert(0, str(m060.parent)); import memory_plan
            self.assertEqual(enc, memory_plan.encode_entries([(i, a, t) for _, i, a, t in rows]))
        big = [(c3.FULL_ID, i % 446, b'\x83\x41' + str(i).encode(), 'x') for i in range(265)]
        self.assertEqual(len(c3.encode_v1(big[:264])), 264 * 592)
        with self.assertRaises(c3.Refuse): c3.encode_v1(big)
        with self.assertRaises(c3.Refuse): c3.encode_v1([(c3.FULL_ANY, -1, b'\x83\x41', 'x')])

    def test_v3_beyond_264_roundtrip_sorted_deterministic(self):
        rows = synthetic_rows()
        self.assertGreater(len(rows), 3000)
        a, b = c3.encode_v3(rows), c3.encode_v3(list(reversed(rows)))
        self.assertEqual(a, b)
        dec = c3.decode_v3(a)
        self.assertEqual(sorted(c3.dedupe(rows), key=c3.sort_key), dec)
        self.assertLess(len(a), len(rows) * c3.V1_ROW // 5)

    def test_v3_limits_and_corruption(self):
        with self.assertRaises(c3.Refuse): c3.encode_v3([])
        with self.assertRaises(c3.Refuse): c3.encode_v3([(c3.FULL_ID, 1, b'\x83', 'x')])          # truncated CP932
        with self.assertRaises(c3.Refuse): c3.encode_v3([(c3.FULL_ANY, 3, b'\x83\x41', 'x')])     # id on any-row
        with self.assertRaises(c3.Refuse): c3.encode_v3([(c3.FULL_ID, 1, b'A' * 65, 'x')])
        with self.assertRaises(c3.Refuse): c3.encode_v3([(c3.FULL_ID, 1, b'A', 'x'), (c3.FULL_ID, 1, b'A', 'y')])
        blob = bytearray(c3.encode_v3(synthetic_rows(5, 5, 5)))
        for off, val in [(0, 0), (4, 2), (8, 0), (28, 0)]:
            bad = bytearray(blob); bad[off] = val
            with self.assertRaises(c3.Refuse): c3.decode_v3(bytes(bad))

    def test_lookup_semantics(self):
        P, S = c3.PREFIX, c3.SUFFIX
        rows = [(c3.FULL_ID, 7, b'\x83A', '劍'), (c3.FULL_ID, 8, b'\x83A', '刀'),
                (c3.FULL_ANY, -1, b'\x83B\x83C', '女名'), (P, -1, b'\x83B', '前'), (S, -1, b'\x83C', '後'),
                (P, -1, b'\x83D', '迪'), (S, -1, b'\x83E\x83F', '奧爾'), (P, -1, b'\x83D\x83E', '迪奧'), (S, -1, b'\x83F', '魯'),
                (P, -1, b'\x83G', '甲'), (S, -1, b'\x83H', '乙')]
        L = c3.Lookup(c3.decode_v3(c3.encode_v3(rows)))
        self.assertEqual(L.find(b'\x83A', 7), '劍')
        self.assertIsNone(L.find(b'\x83A'))                 # two ids, two texts: ambiguous
        self.assertIsNone(L.find(b'\x83A', 9))              # key exists for other ids: no fallthrough
        self.assertEqual(L.find(b'\x83B\x83C'), '女名')      # exact beats join
        self.assertEqual(L.find(b'\x83G\x83H'), '甲乙')      # two-part join
        self.assertIsNone(L.find(b'\x83G\x83H', allow_join=False))
        self.assertIsNone(L.find(b'\x83D\x83E\x83F'))       # two splits disagree -> original path
        self.assertIsNone(L.find(b'\x83G'))                 # fragments never match whole strings
        self.assertIsNone(L.find(b'\x83G\x83'))             # truncated lead byte

    def test_c_core_agrees_with_python(self):
        gcc = shutil.which('gcc') or shutil.which('cc')
        if not gcc: self.skipTest('no C compiler')
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / 't'
            subprocess.run([gcc, '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2', '-o', str(exe), str(HERE / 'native-v3' / 'catalog_v3_host_test.c')], check=True)
            rows = synthetic_rows(); blob = c3.encode_v3(rows)
            look = c3.Lookup(c3.decode_v3(blob))
            (Path(td) / 'c.bin').write_bytes(blob)
            (Path(td) / 'cases.txt').write_text('open 1\n' + '\n'.join(cases(look, rows, random.Random(1))) + '\n')
            r = subprocess.run([str(exe), str(Path(td) / 'c.bin'), str(Path(td) / 'cases.txt')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout); self.assertIn('FAIL 0', r.stdout)
            bad = bytearray(blob); bad[28] = 0
            (Path(td) / 'b.bin').write_bytes(bytes(bad)); (Path(td) / 'b.txt').write_text('open 0\n')
            r = subprocess.run([str(exe), str(Path(td) / 'b.bin'), str(Path(td) / 'b.txt')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_sidecar_batches_and_adventurer_validator(self):
        meta = dict(production_can_apply=False, release_approved=False)
        items = [dict(table='primary', slot=s, category='tool') for s in range(72)]
        b = sp.split_items(dict(meta, items=items))
        self.assertEqual([len(x['items']) for x in b], [30, 30, 12])
        with self.assertRaises(ValueError): sp.split_items(dict(meta, items=items), limit=31)
        adv = dict(table='adventurer_female', region='western', index=0, slot=None, stored_id=None, source_record_sha256=None,
                   category='adventurer', exact_match_usable=True, name_status='translated', name_zh_tw='瑪莉亞',
                   name_cp950_encodable=True, source_name_sha256='0' * 64)
        self.assertEqual(sp.validate_adventurers(dict(meta, items=[adv])), {'adventurer_female': 1})
        for k, v in [('exact_match_usable', False), ('index', 150), ('name_cp950_encodable', False), ('stored_id', 3)]:
            with self.assertRaises(ValueError): sp.validate_adventurers(dict(meta, items=[dict(adv, **{k: v})]))
        male = dict(adv, table='adventurer_male_first', exact_match_usable=False)
        with self.assertRaises(ValueError): sp.validate_adventurers(dict(meta, items=[adv, dict(male, name_zh_tw='別名')]))
        pub = sp.public_copy(dict(meta, items=[dict(adv, source_name_ja='x', source_name_cp932_hex='00')]))
        self.assertNotIn('source_name_ja', pub['items'][0]); self.assertNotIn('source_name_cp932_hex', pub['items'][0])


@unittest.skipUnless(os.environ.get('LD2_TEST_EXE') and os.environ.get('LD2_M051_CATALOG'), 'licensed inputs not provided')
class Licensed(unittest.TestCase):
    def setUp(self):
        self.exe = Path(os.environ['LD2_TEST_EXE']).read_bytes()
        self.m051 = Path(os.environ['LD2_M051_CATALOG']).read_bytes()

    def test_m051_golden_v1(self):
        rows, stats = c3.verified_rows(self.exe, [(self.m051, c3.M051_CATALOG)])
        enc = c3.encode_v1(rows)
        self.assertEqual((len(rows), len(enc), hashlib.sha256(enc).hexdigest()), (264, 156288, c3.M051_V1_ENTRIES))
        m060 = HERE.parent / 'm060' / 'memory_plan.py'
        if m060.exists():
            sys.path.insert(0, str(m060.parent)); import memory_plan
            self.assertEqual(memory_plan.reviewed_catalog(self.exe, self.m051), (enc, 264))
        self.assertEqual(c3.Lookup(c3.decode_v3(c3.encode_v3(rows))).by.keys(), c3.Lookup(rows).by.keys())

    @unittest.skipUnless(os.environ.get('LD2_M062_DRAFT') and os.environ.get('LD2_M062_DRAFT_SHA'), 'draft not provided')
    def test_draft_v3_and_c_cross_check(self):
        draft = Path(os.environ['LD2_M062_DRAFT']).read_bytes()
        rows, stats = c3.verified_rows(self.exe, [(self.m051, c3.M051_CATALOG), (draft, os.environ['LD2_M062_DRAFT_SHA'])])
        self.assertGreater(len(rows), c3.V1_MAX_ROWS)
        with self.assertRaises(c3.Refuse): c3.encode_v1([r for r in rows if r[0] == c3.FULL_ID])
        blob = c3.encode_v3(rows); look = c3.Lookup(c3.decode_v3(blob))
        gcc = shutil.which('gcc') or shutil.which('cc')
        if not gcc: return
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / 't'
            subprocess.run([gcc, '-std=c99', '-O2', '-o', str(exe), str(HERE / 'native-v3' / 'catalog_v3_host_test.c')], check=True)
            (Path(td) / 'c.bin').write_bytes(blob)
            (Path(td) / 'cases.txt').write_text('open 1\n' + '\n'.join(cases(look, rows, random.Random(2), 4000)) + '\n')
            r = subprocess.run([str(exe), str(Path(td) / 'c.bin'), str(Path(td) / 'cases.txt')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == '__main__':
    unittest.main()
