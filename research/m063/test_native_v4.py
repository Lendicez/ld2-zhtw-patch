"""m063c tests: v4 native helpers (sources, mocks, rehearsal objects) + merge_plan_v4 / enable_plan_v4.

Synthetic/static tests always run (no game bytes). Mock + rehearsal tests skip unless `ziglang`
(and `capstone`) are importable; lab tests skip unless the pristine EXE, m045 build, m051 catalog
and lab-only m061 modules are present. Objects/binaries go to temp dirs only. Emits pass/fail only."""
import hashlib, importlib.util, json, os, re, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import catalog_v4 as c4  # noqa: E402

NATIVE = HERE / 'native-v4'
MANIFEST = (HERE.parent / 'm061/list_sites.json').read_bytes()
SUMMARY = (HERE.parent / 'm062/name_draw_sites.summary.json').read_bytes()
HAVE_ZIG = importlib.util.find_spec('ziglang') is not None
HAVE_CS = importlib.util.find_spec('capstone') is not None


def sha(b): return hashlib.sha256(b).hexdigest()


# m063b Win11 MSVC objects (compile-v4-run1). The .obj files are never committed; set
# LD2_M063B_RETURN to a local directory holding them to run the MSVC lab build below.
MSVC_V4_PINS = dict(list_insert_v4='cb74d585c9936f41debc831c863e1eb91dd652770ba4911660e16dd4e3c72b35',
                    name_textout_v4='76d0adb7cecc82e54c1e0543a2d5f8b932f3b2d9f82a255ac6941390385cc0f6',
                    name_pair_v4='bf33cfc674f28fd6f8bb069d76176f45d1309a8ab3198f068fc31c3ed87792e6')


def _msvc_objs():
    d = os.environ.get('LD2_M063B_RETURN')
    if not d:
        return None
    try:
        objs = {k: (Path(d) / f'{k}.obj').read_bytes() for k in MSVC_V4_PINS}
    except OSError:
        return None
    return objs if all(sha(objs[k]) == v for k, v in MSVC_V4_PINS.items()) else None


def tiny_blob():
    return c4.encode_v4([c4.make_row(c4.FULL_ANY, -1, b'\x83\x41', '\u611b'),
                         c4.make_row(c4.PREFIX, -1, b'\x83\x4a', '\u963f', 1),
                         c4.make_row(c4.SUFFIX, -1, b'\x83\x4c', '\u5e03', 1)])


class Sources(unittest.TestCase):
    """Call-site classification is compiled into each helper; lock it at the source level."""
    def text(self, n):
        return (NATIVE / n).read_text(encoding='utf-8')

    def test_list_two_entries(self):
        s = self.text('list_insert_v4.cpp')
        self.assertEqual(len(re.findall(r'extern "C" __declspec\(noinline\)', s)), 2)
        self.assertRegex(s, r'LD2_ListInsertV4\([^)]*\)\s*\{[^}]*LD2_LIST_FLAGS_ITEM\)')
        self.assertRegex(s, r'LD2_ListInsertNameV4\([^)]*\)\s*\{[^}]*LD2_LIST_FLAGS_NAME\)')
        h = self.text('list_core_v4.h')
        self.assertIn('#define LD2_LIST_FLAGS_ITEM (LD2C4_ALLOW_ANY | LD2C4_ALLOW_JOIN)', h)
        self.assertIn('#define LD2_LIST_FLAGS_NAME (LD2C4_ALLOW_ANY | LD2C4_ALLOW_JOIN | LD2C4_NAME_ONLY)', h)

    def test_textout_name_only(self):
        self.assertIn('#define LD2N4_FLAGS (LD2C4_ALLOW_ANY|LD2C4_ALLOW_JOIN|LD2C4_NAME_ONLY)', self.text('name_textout_v4.h'))

    def test_name_pair_flags_zero(self):
        s = self.text('name_pair_v4.cpp')
        self.assertRegex(s, r'LD2C4_Lookup\(&view,[^;]*,id,0u,destination,257u\)')

    def test_no_v3_core(self):
        for n in ('list_insert_v4.cpp', 'name_textout_v4.cpp', 'name_pair_v4.cpp', 'list_core_v4.h',
                  'name_textout_v4.h', 'name_pair_v4.h', 'list_bindings_v4.h'):
            s = self.text(n)
            self.assertNotIn('catalog_core_v3', s, n)
            self.assertNotIn('LD2C3_', s, n)

    def test_site_classes(self):
        self.assertEqual(c4.SITE_FLAGS['name'], 7)
        self.assertEqual(c4.SITE_FLAGS['item_list'], 3)
        self.assertEqual(c4.SITE_FLAGS['item_by_id'], 0)
        name = {va for va, c in c4.LIST_SITE_CLASS.items() if c == 'name'}
        self.assertEqual(len(name), 11)
        self.assertIn(0x4b2d1f, name)
        self.assertEqual({va for va, c in c4.LIST_SITE_CLASS.items() if c == 'item_list'}, {0x4aaf19, 0x4ab0fe, 0x4b46e4, 0x4b4df1})
        self.assertEqual({va for va, c in c4.LIST_SITE_CLASS.items() if c == 'unclassified_list'}, {0x492431, 0x4b1153, 0x4b3477})


class Plans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import merge_plan_v4 as m4, enable_plan_v4 as e4, enable_plan_m063 as em
        cls.m4, cls.e4, cls.em = m4, e4, em

    def test_capacity_gate(self):
        rep = self.m4.capacity_gate_v4(tiny_blob())
        self.assertEqual((rep['rows'], rep['catalog_version']), (3, 4))
        bad3 = bytearray(tiny_blob())
        struct.pack_into('<H', bad3, 4, 3)
        for b in (bytes(bad3), tiny_blob()[:-1], b'', tiny_blob() + b'\0' * 4):
            with self.assertRaises(self.m4.Refuse):
                self.m4.capacity_gate_v4(b)
        import catalog_v3 as c3
        with self.assertRaises(self.m4.Refuse):
            self.m4.capacity_gate_v4(c3.encode_v3([(c3.FULL_ANY, -1, b'\x83\x41', '\u611b')]))

    def test_pins(self):
        m4 = self.m4
        locked = dict(name=MSVC_V4_PINS['name_pair_v4'], list=MSVC_V4_PINS['list_insert_v4'],
                      textout=MSVC_V4_PINS['name_textout_v4'])
        self.assertEqual((m4.NAME_V4_OBJECT_SHA256, m4.LIST_V4_OBJECT_SHA256, m4.TEXTOUT_V4_OBJECT_SHA256),
                         (locked['name'], locked['list'], locked['textout']))
        import rehearse_v4_objs as rv4
        self.assertEqual(rv4.PINS, MSVC_V4_PINS)
        pins, rehearsal = m4.resolve_pins()
        self.assertEqual((pins, rehearsal), (locked, False))
        good = dict(name='1' * 64, list='2' * 64, textout='3' * 64)
        pins, rehearsal = m4.resolve_pins(good)
        self.assertTrue(rehearsal)
        for bad in (dict(good, list=m4.mv.LIST_V3_OBJECT_SHA256), dict(good, name=m4.mv.NAME_V3_OBJECT_SHA256),
                    dict(good, textout=good['name']), dict(good, extra='4' * 64), dict(good, list='x')):
            with self.assertRaises(m4.Refuse):
                m4.resolve_pins(bad)
        with self.assertRaises(m4.Refuse):
            m4.build_inert_v4(b'', b'', b'', b'', b'', b'')

    def test_routes(self):
        routes = self.e4.route_list_sites(self.em.load_list_sites(MANIFEST))
        item = {int(s['va'], 16) for s in routes['item']}
        self.assertEqual(item, {0x4aaf19, 0x4ab0fe, 0x4b46e4, 0x4b4df1, 0x492431, 0x4b1153, 0x4b3477})
        self.assertEqual({int(s['va'], 16) for s in routes['name']}, {0x4b2d1f} | set(self.em.M063_LIST_EXTRA))

    def test_route_drift_refused(self):
        rows = self.em.load_list_sites(MANIFEST)
        saved = dict(c4.LIST_SITE_CLASS)
        try:
            for mut in (lambda d: d.update({0x4b2d1f: 'item_list'}), lambda d: d.pop(0x4735f6),
                        lambda d: d.update({0x4735f6: 'item_by_id'}), lambda d: d.update({0x400000: 'name'})):
                c4.LIST_SITE_CLASS.clear()
                c4.LIST_SITE_CLASS.update(saved)
                mut(c4.LIST_SITE_CLASS)
                with self.assertRaises(self.e4.Refuse):
                    self.e4.route_list_sites(rows)
        finally:
            c4.LIST_SITE_CLASS.clear()
            c4.LIST_SITE_CLASS.update(saved)

    def test_enable_entry_checks(self):
        e4, cr = self.e4, (0xae3000, 0xae6000)
        img = bytes(0x200000)
        for args in ((0xae3000, 0xae4000, 0xae4000, 0xae5000), (0xae3000, 0xae4000, 0xae4100, cr[1]),
                     (0xae3000, 0xae4000, 0x4ea671, 0xae5000)):
            with self.assertRaises(e4.Refuse):
                e4.apply_enabled_v4(img, *args, cr, MANIFEST, SUMMARY)


def zig(*args, cwd=NATIVE):
    subprocess.run([sys.executable, '-m', 'ziglang', 'c++', *args], check=True, cwd=str(cwd),
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


@unittest.skipUnless(HAVE_ZIG, 'ziglang not installed')
class Mocks(unittest.TestCase):
    """Logic + i386 ABI on Linux (x86-linux-musl); NOT the MSVC object."""
    def run_mock(self, srcs, asm):
        with tempfile.TemporaryDirectory(prefix='ld2v4mock-') as d:
            exe = Path(d) / 'm'
            zig('-target', 'x86-linux-musl', '-fms-extensions', *(['-fasm-blocks'] if asm else []),
                '-D_M_IX86=600', *srcs, '-o', str(exe))
            r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])
        return r.stdout.strip().splitlines()[-1]

    def test_list_mock(self):
        last = self.run_mock(['list_insert_v4.cpp', 'list_mock_test_v4.cpp'], False)
        m = re.fullmatch(r'cases=(\d+) assertions=(\d+) failed=0 game_or_user32_called=false', last)
        self.assertIsNotNone(m, last)
        self.assertGreaterEqual(int(m[1]), 54)

    def test_textout_mock(self):
        d = json.loads(self.run_mock(['name_textout_v4.cpp', 'name_textout_mock_v4.cpp'], True))
        self.assertEqual((d['failed'], d['catalog_version'], d['flags'], d['game_or_gdi_called']),
                         (0, 4, 'ALLOW_ANY|ALLOW_JOIN|NAME_ONLY', False))
        self.assertGreaterEqual(d['cases'], 36)

    def test_name_pair_mock(self):
        d = json.loads(self.run_mock(['name_pair_v4.cpp', 'name_pair_mock_v4.cpp'], True))
        self.assertEqual((d['failed'], d['catalog_version'], d['flags'], d['game_or_gdi_called']), (0, 4, 0, False))
        self.assertGreaterEqual(d['cases'], 45)


@unittest.skipUnless(HAVE_ZIG and HAVE_CS, 'ziglang/capstone not installed')
class Rehearsal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import rehearse_v4_objs as rv4
        cls.rv4 = rv4
        with tempfile.TemporaryDirectory() as d:
            cls.objs = {k: rv4.build(NATIVE / f'{k}.cpp', d) for k in ('list_insert_v4', 'name_textout_v4', 'name_pair_v4')}
            cls.v3_list = rv4.build(HERE.parent / 'm062/native-v3/list_insert_v3.cpp', d)

    def test_audits(self):
        import audit_list_obj_v4 as al4
        rep = al4.audit(self.objs['list_insert_v4'])
        self.assertEqual(set(rep['entries']), {al4.ENTRY_ITEM, al4.ENTRY_NAME})
        for e in rep['entries'].values():
            self.assertTrue(e['esp_and_nonvolatile_preserved_on_normal_paths'])
            self.assertGreater(e['normal_returns'], 0)
            self.assertNotIn('_LD2_Catalog', e['calls'])
        import audit_name_textout as ant
        self.assertTrue(ant.audit(self.objs['name_textout_v4'])['esp_and_nonvolatile_preserved_on_normal_paths'])

    def test_v3_list_object_refused_by_v4_audit(self):
        import audit_list_obj_v4 as al4
        with self.assertRaises(SystemExit):
            al4.audit(self.v3_list)

    def test_walker_default_unchanged(self):
        import audit_list_obj_v3 as w
        self.assertFalse(w.COOKIE_NORETURN_TAILS)

    def test_merge_object_checks(self):
        import merge_plan_v4 as m4
        o = self.objs
        for slot, k in (('list', 'list_insert_v4'), ('textout', 'name_textout_v4'), ('name', 'name_pair_v4')):
            self.assertGreater(m4.check_object(slot, o[k], sha(o[k])), 0)
        with self.assertRaises(m4.Refuse):
            m4.check_object('list', self.v3_list, sha(self.v3_list))
        with self.assertRaises(m4.Refuse):
            m4.check_object('list', o['name_textout_v4'], sha(o['name_textout_v4']))
        with self.assertRaises(m4.Refuse):
            m4.check_object('textout', o['list_insert_v4'], sha(o['list_insert_v4']))


def _lab_ok():
    try:
        import build_v3_lab as b3
        return all(p.is_file() for p in (b3.LAB / 'baseline/pristine/Ld95.exe', b3.LAB / 'runs/m045/build-first/Ld95.exe',
                                          b3.OBJ_DIR / 'name_pair_v3.obj', b3.OBJ_DIR / 'list_insert_v3.obj', b3.M051)) \
            and HAVE_ZIG and HAVE_CS
    except Exception:
        return False


@unittest.skipUnless(_lab_ok(), 'lab inputs missing')
class LabBuildV4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_v3_lab as b3, rehearse_v4_objs as rv4, merge_plan_v4 as m4, enable_plan_v4 as e4
        cls.b3, cls.m4, cls.e4 = b3, m4, e4
        o = (b3.LAB / 'baseline/pristine/Ld95.exe').read_bytes()
        m = (b3.LAB / 'runs/m045/build-first/Ld95.exe').read_bytes()
        rows, _ = c4.verified_rows(o, [(b3.M051.read_bytes(), b3.mv.M051_SHA)])
        cls.blob = c4.encode_v4(rows)
        cls.o, cls.m = o, m
        with tempfile.TemporaryDirectory() as d:
            cls.objs = [rv4.build(NATIVE / f'{k}.cpp', d) for k in ('name_pair_v4', 'list_insert_v4', 'name_textout_v4')]
        cls.pins = dict(zip(('name', 'list', 'textout'), (sha(x) for x in cls.objs)))
        cls.v3 = ((b3.OBJ_DIR / 'name_pair_v3.obj').read_bytes(), (b3.OBJ_DIR / 'list_insert_v3.obj').read_bytes())

    def build(self, mode=2):
        inert, rep = self.m4.build_inert_v4(self.o, self.m, *self.objs, self.blob, list_mode=mode, pins=self.pins)
        cr = tuple(int(x, 16) for x in rep['code_range'])
        va = [int(rep[k], 16) for k in ('entry_va', 'list_item_entry_va', 'list_name_entry_va', 'textout_entry_va')]
        en, erep = self.e4.apply_enabled_v4(inert, *va, cr, MANIFEST, SUMMARY)
        return inert, rep, en, erep, va

    def test_build_mode2(self):
        inert, rep, en, erep, va = self.build(2)
        self.assertTrue(rep['rehearsal'])
        self.assertFalse(rep['handoff_eligible'] or rep['production_can_apply'] or rep['release_approved'])
        self.assertEqual(rep['catalog_version'], 4)
        self.assertEqual(erep['counts'], dict(pair5=25, tail8=1, list_sites=18, list_item=7, list_name=11))
        self.assertFalse(erep['production_can_apply'] or erep['release_approved'] or erep['file_written'])
        for s in erep['sites']:
            o = int(s['va'], 16) - 0x400000
            tgt = int(s['va'], 16) + 5 + struct.unpack_from('<i', en, o + 1)[0]
            want = va[2] if c4.LIST_SITE_CLASS[int(s['va'], 16)] == 'name' else va[1]
            self.assertEqual(tgt, want, s['va'])
        tav = next(s for s in erep['sites'] if s['va'] == '0x4b2d1f')
        self.assertEqual(tav['route'], 'name')

    def test_v3_inputs_refused(self):
        m4 = self.m4
        n3, l3 = self.v3
        import catalog_v3 as c3
        v3blob = c3.encode_v3([(c3.FULL_ANY, -1, b'\x83\x41', '\u611b')])
        cases = [((n3, self.objs[1], self.objs[2], self.blob), dict(self.pins, name=sha(n3))),
                 ((self.objs[0], l3, self.objs[2], self.blob), dict(self.pins, list=sha(l3))),
                 ((self.objs[0], self.objs[1], self.objs[2], v3blob), self.pins),
                 ((self.objs[1], self.objs[0], self.objs[2], self.blob), dict(self.pins, name=self.pins['list'], list=self.pins['name'])),
                 ((self.objs[0], self.objs[1][:-1] + bytes([self.objs[1][-1] ^ 1]), self.objs[2], self.blob), self.pins)]
        for args, pins in cases:
            with self.assertRaises(m4.Refuse):
                m4.build_inert_v4(self.o, self.m, *args, pins=pins)

    @unittest.skipUnless(_msvc_objs(), 'm063b MSVC objects not available locally (LD2_M063B_RETURN)')
    def test_build_msvc_pinned(self):
        o = _msvc_objs()
        objs = (o['name_pair_v4'], o['list_insert_v4'], o['name_textout_v4'])
        inert, rep = self.m4.build_inert_v4(self.o, self.m, *objs, self.blob, list_mode=2)
        self.assertFalse(rep['rehearsal'])
        self.assertTrue(rep['handoff_eligible'])
        self.assertFalse(rep['production_can_apply'] or rep['release_approved'])
        cr = tuple(int(x, 16) for x in rep['code_range'])
        va = [int(rep[k], 16) for k in ('entry_va', 'list_item_entry_va', 'list_name_entry_va', 'textout_entry_va')]
        en, erep = self.e4.apply_enabled_v4(inert, *va, cr, MANIFEST, SUMMARY)
        self.assertEqual(erep['counts'], dict(pair5=25, tail8=1, list_sites=18, list_item=7, list_name=11))
        self.assertFalse(erep['production_can_apply'] or erep['release_approved'] or erep['file_written'])

    def test_enable_refuses_swapped_or_enabled(self):
        inert, rep, en, erep, va = self.build(2)
        cr = tuple(int(x, 16) for x in rep['code_range'])
        with self.assertRaises(self.e4.Refuse):
            self.e4.apply_enabled_v4(inert, va[0], va[1], va[1], va[3], cr, MANIFEST, SUMMARY)
        with self.assertRaises(Exception):
            self.e4.apply_enabled_v4(en, *va, cr, MANIFEST, SUMMARY)


if __name__ == '__main__':
    unittest.main()
