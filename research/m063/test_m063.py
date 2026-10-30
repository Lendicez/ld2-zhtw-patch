"""m063a tests: three-helper merge plan + enable plan (25 pair5 + 1 tail8 + 18 list sites).

Synthetic tests always run (no game bytes: synthetic images are built from generic x86 encodings).
Rehearsal tests skip unless the `ziglang` module is importable; lab tests skip unless the pristine
EXE, m045 build and the locked MSVC v3 objects are present. Emits nothing but pass/fail."""
import hashlib, importlib.util, json, struct, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import enable_plan_m063 as em  # noqa: E402

SUMMARY = (HERE.parent / 'm062/name_draw_sites.summary.json').read_bytes()
MANIFEST = (HERE.parent / 'm061/list_sites.json').read_bytes()
BASE = 0x400000
TVA, CR = 0xae50d0, (0xae3000, 0xae6000)


def sha(b): return hashlib.sha256(b).hexdigest()


def synth_image():
    img = bytearray(b'\x90' * (em.TEXT_END + 0x100))
    rows, tail = em.load_textout_sites(SUMMARY)
    for r in rows:
        o = r['pair_va'] - BASE
        # R1 = eax unless the summary's 5-byte hash says R1 == R2 (0x48f442 / 0x4b958c shapes)
        for r1 in em.VOLATILE:
            pair = em.enc_load(r1, r['cdc']) + em.enc_load(r['r2'], r1, 0x5c)
            if sha(pair)[:8] == r['sha8']:
                break
        else:
            raise AssertionError('no generic encoding matches summary hash at %#x' % r['pair_va'])
        img[o:o + 5] = pair
        c = r['call_va'] - BASE
        img[c - 2:c + 2] = em.enc_mov_ecx(r['cdc']) + em.enc_call_reg(r['r2'])
    s = tail['start_va'] - BASE
    img[s:s + 8] = em.enc_shape(tail['shape'])
    return img


def mutate_summary(fn):
    s = json.loads(SUMMARY)
    fn(s)
    return json.dumps(s).encode()


def mutate_manifest(fn):
    m = json.loads(MANIFEST)
    fn(m)
    return json.dumps(m).encode()


class Enumeration(unittest.TestCase):
    def test_textout_sites(self):
        rows, tail = em.load_textout_sites(SUMMARY)
        self.assertEqual(len(rows), 25)
        self.assertEqual(sorted(r['call_va'] for r in rows), sorted(em.PAIR5_CALLS))
        self.assertEqual(sum(1 for r in rows if r['function'] == '0x438910'), 18)
        self.assertEqual({r['function'] for r in rows}, {'0x438910', '0x48f220', '0x4b92d0', '0x4d77a0', '0x4dbcb0'})
        self.assertEqual(tail['call_va'], 0x48f484)
        self.assertEqual(len({r['pair_va'] for r in rows}), 25)

    def test_list_sites(self):
        rows = em.load_list_sites(MANIFEST)
        vas = {int(s['va'], 16) for s in rows}
        self.assertEqual(len(rows), 18)
        self.assertEqual(vas, em.M061_PRIORITY_LIST | set(em.M063_LIST_EXTRA))
        msgs = [s['message'] for s in rows if int(s['va'], 16) in em.M063_LIST_EXTRA]
        self.assertEqual((msgs.count('LB_INSERTSTRING'), msgs.count('CB_INSERTSTRING')), (8, 2))
        self.assertNotIn(0x4b2d1f, em.M063_LIST_EXTRA)       # tavern already covered by m061b

    def test_deferred_not_enumerated(self):
        s = json.loads(SUMMARY)
        deferred = {int(t['va'], 16) for t in s['textout_sites'] if t['tag'] == 'composite'}
        deferred |= {int(t['va'], 16) for t in s['other_sites'] if t['tag'] == 'composite' or t['api'] != 'SendDlgItemMessage'}
        self.assertEqual(len(deferred), 4 + 4 + 3 + 2)
        planned = set(em.PAIR5_CALLS) | {em.TAIL8['call_va']} | set(em.M063_LIST_EXTRA)
        self.assertFalse(deferred & planned)


class TextOutPlan(unittest.TestCase):
    def setUp(self):
        self.img = synth_image()

    def test_plan_ok(self):
        p = em.plan_textout(bytes(self.img), TVA, CR, SUMMARY)
        self.assertEqual([x['kind'] for x in p].count('pair5'), 25)
        self.assertEqual([x['kind'] for x in p].count('tail8'), 1)
        for x in p:
            if x['kind'] == 'pair5':
                self.assertEqual(len(x['new']), 5)
                self.assertEqual(struct.unpack('<I', x['new'][1:])[0], TVA)
                self.assertEqual(x['new'][0] & 0xf8, 0xB8)
            else:
                self.assertEqual(x['new'][:3], b'\x51\x8b\xce')
                self.assertEqual(0x48f486 + struct.unpack('<i', x['new'][4:])[0], TVA)
        em.check_disjoint([(x['off'], x['off'] + len(x['old']), x['kind']) for x in p])

    def test_textout_va_outside_ld2t_refused(self):
        for va in (CR[0] - 1, CR[1], 0x4e13d7):
            with self.assertRaises(em.Refuse):
                em.plan_textout(bytes(self.img), va, CR, SUMMARY)

    def test_corrupt_pair_refused(self):
        r = em.load_textout_sites(SUMMARY)[0][3]
        self.img[r['pair_va'] - BASE + 4] ^= 1
        with self.assertRaises(em.Refuse):
            em.plan_textout(bytes(self.img), TVA, CR, SUMMARY)

    def test_wrong_call_register_refused(self):
        r = em.load_textout_sites(SUMMARY)[0][20]
        self.img[r['call_va'] - BASE + 1] ^= 0x01
        with self.assertRaises(em.Refuse):
            em.plan_textout(bytes(self.img), TVA, CR, SUMMARY)

    def test_tail_mismatch_refused(self):
        self.img[em.TAIL8['start_va'] - BASE + 3] = 0x52     # push edx instead of push ecx
        with self.assertRaises(em.Refuse):
            em.plan_textout(bytes(self.img), TVA, CR, SUMMARY)

    def test_summary_drift_refused(self):
        bad = [
            lambda s: s.update(production_can_apply=True),
            lambda s: s.update(release_approved=True),
            lambda s: s.update(source_sha256='0' * 64),
            lambda s: s['textout_sites'].pop(0),                                   # missing pair5
            lambda s: s['textout_sites'].append(dict(s['textout_sites'][0])),      # duplicate pair5
            lambda s: s['textout_sites'][0]['install'].update(branch_targets_inside=1),
            lambda s: s['textout_sites'][0]['install'].update(call_reg='esi'),
            lambda s: [t.update(install=None) for t in s['textout_sites'] if t['va'] == '0x48f484'],
            lambda s: [t.update(install=dict(kind='pair5')) for t in s['textout_sites'] if t['tag'] == 'composite'],
        ]
        for fn in bad:
            with self.assertRaises((em.Refuse, KeyError, TypeError)):
                em.plan_textout(bytes(self.img), TVA, CR, mutate_summary(fn))

    def test_overlap_refused(self):
        with self.assertRaises(em.Refuse):
            em.check_disjoint([(10, 15, 'a'), (14, 19, 'b')])
        em.check_disjoint([(10, 15, 'a'), (15, 19, 'b')])


class ListManifest(unittest.TestCase):
    def test_drift_refused(self):
        bad = [
            lambda m: m.update(production_can_apply=True),
            lambda m: m['sites'].remove(next(s for s in m['sites'] if s['va'] == '0x47c242')),
            lambda m: next(s for s in m['sites'] if s['va'] == '0x46e73a').update(message='LB_INSERTSTRING'),
            lambda m: next(s for s in m['sites'] if s['va'] == '0x4735f6').update(message='LB_GETTEXT'),
            lambda m: next(s for s in m['sites'] if s['va'] == '0x4735f6').update(readback_on_same_control=True),
            lambda m: next(s for s in m['sites'] if s['va'] == '0x4735f6').update(priority=True),
            lambda m: next(s for s in m['sites'] if s['va'] == '0x4b2d1f').update(priority=False),
            lambda m: m['sites'].append(dict(m['sites'][0])),
        ]
        for fn in bad:
            with self.assertRaises(em.Refuse):
                em.load_list_sites(mutate_manifest(fn))


class Layout(unittest.TestCase):
    def setUp(self):
        import merge_plan_m063 as mm
        self.mm = mm

    def test_three_slots(self):
        offs, span = self.mm.plan_code_layout([3008, 3700, 2485])
        self.assertEqual(offs, [0, 3008, 6720])
        self.assertEqual(span, 6720 + 2485)

    def test_bad_layouts_refused(self):
        mm = self.mm
        for lens in ([0, 10, 10], [10, 10], [10, 10, 10, 10], [10, mm.MAX_FRAGMENT + 1, 10], [10, 10, -1]):
            with self.assertRaises(mm.Refuse):
                mm.plan_code_layout(lens)
        with self.assertRaises(mm.Refuse):
            mm.plan_code_layout([10, 10, 10], slot_align=24)
        for offs, lens, span in (([0, 8, 32], [16, 16, 16], 48),     # overlap + misaligned
                                 ([0, 16, 32], [16, 20, 16], 48),    # list runs into textout
                                 ([16, 32, 48], [16, 16, 16], 64),   # first slot not at start
                                 ([0, 16, 32], [16, 16, 16], 64)):   # span drift
            with self.assertRaises(mm.Refuse):
                mm.check_code_layout(offs, lens, span)

    def test_unlocked_textout_refused(self):
        mm = self.mm
        self.assertIsNone(mm.TEXTOUT_OBJECT_SHA256)
        with self.assertRaises(mm.Refuse):
            mm.build_inert_m063(b'', b'', b'', b'', b'', b'')

    def test_textout_object_pin(self):
        mm = self.mm
        with self.assertRaises(mm.Refuse):
            mm.check_textout_object(b'x' * 64, sha(b'y'))
        with self.assertRaises(mm.Refuse):
            mm.check_textout_object(b'x', mm.mv.NAME_V3_OBJECT_SHA256)

    def test_fixed_image_base(self):
        mm = self.mm
        h = bytearray(0x400)
        struct.pack_into('<I', h, 0x3c, 0xf0)
        struct.pack_into('<H', h, 0xf0 + 22, 0x103)
        struct.pack_into('<I', h, 0xf0 + 24 + 28, BASE)
        mm.check_image_base(bytes(h))
        for patch in ((0xf0 + 22, 0x102, '<H'), (0xf0 + 24 + 70, 0x40, '<H'), (0xf0 + 24 + 28, 0x10000000, '<I')):
            g = bytearray(h)
            struct.pack_into(patch[2], g, patch[0], patch[1])
            with self.assertRaises(mm.Refuse):
                mm.check_image_base(bytes(g))


@unittest.skipUnless(importlib.util.find_spec('ziglang') and importlib.util.find_spec('capstone'), 'ziglang/capstone not installed')
class Rehearsal(unittest.TestCase):
    def test_textout_rehearsal_object(self):
        import merge_plan_m063 as mm, audit_name_textout as ant
        raw = ant.rehearsal_textout_obj()
        self.assertGreater(mm.check_textout_object(raw, sha(raw)), 0)
        rep = ant.audit(raw)
        self.assertTrue(rep['esp_and_nonvolatile_preserved_on_normal_paths'])
        self.assertEqual(rep['functions']['@LD2_NameTextOut@24']['ret_pop'], 16)


try:
    import build_v3_lab as b3
    LAB_OK = all(p.is_file() for p in (b3.LAB / 'baseline/pristine/Ld95.exe', b3.LAB / 'runs/m045/build-first/Ld95.exe',
                                       b3.OBJ_DIR / 'name_pair_v3.obj', b3.OBJ_DIR / 'list_insert_v3.obj', b3.M051)) \
        and importlib.util.find_spec('ziglang') is not None
except Exception:
    LAB_OK = False


@unittest.skipUnless(LAB_OK, 'lab inputs missing')
class LabBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_m063_lab as bm
        cls.bm = bm
        cls.pre = b3.inputs('reviewed')
        cls.tobj = bm.rehearsal_textout_obj()

    def test_build_and_verify_mode2(self):
        o, m, inert, rep, en, erep = self.bm.build(2, self.pre, self.tobj, sha(self.tobj))
        v = self.bm.verify(o, inert, rep, en, erep, self.pre[2], self.pre[3], self.tobj)
        self.assertEqual(erep['counts'], dict(pair5=25, tail8=1, list_sites=18))
        self.assertEqual(v['textout_sites']['branch_hits'], [])
        self.assertTrue(rep['textout_rehearsal'])
        self.assertFalse(rep['handoff_eligible'] or rep['production_can_apply'] or rep['release_approved'])
        self.assertFalse(erep['production_can_apply'] or erep['release_approved'] or erep['file_written'])
        self.assertEqual(rep['textout_bindings'], rep['bindings'])

    def test_bad_objects_refused(self):
        import merge_plan_m063 as mm
        o, m, no, lo, blob, _ = self.pre
        t = self.tobj
        cases = [(no, lo, t, None),            # NameTextOut not locked
                 (lo, no, t, sha(t)),          # NamePair/List swapped
                 (no, lo, no, sha(no)),        # NamePair object in the textout slot (pin reuse)
                 (no, lo, lo, sha(lo)),        # List object in the textout slot
                 (no, lo, t[:-1] + bytes([t[-1] ^ 1]), sha(t))]   # tampered rehearsal object
        for a, b, c, pin in cases:
            with self.assertRaises(mm.Refuse):
                mm.build_inert_m063(o, m, a, b, c, blob, textout_pin=pin)

    def test_enable_refuses_bad_entries(self):
        o, m, no, lo, blob, _ = self.pre
        import merge_plan_m063 as mm
        inert, rep = mm.build_inert_m063(o, m, no, lo, self.tobj, blob, textout_pin=sha(self.tobj))
        cr = tuple(int(x, 16) for x in rep['code_range'])
        np_, li, tx = (int(rep[k], 16) for k in ('entry_va', 'list_entry_va', 'textout_entry_va'))
        for args in ((np_, li, cr[1]), (np_, li, li), (np_, li, 0x4e13d7)):
            with self.assertRaises(em.Refuse):
                em.apply_enabled_m063(inert, *args, cr, MANIFEST, SUMMARY)
        with self.assertRaises(Exception):   # an enabled image is not a valid inert input (hook span changed)
            en, _ = em.apply_enabled_m063(inert, np_, li, tx, cr, MANIFEST, SUMMARY)
            em.apply_enabled_m063(en, np_, li, tx, cr, MANIFEST, SUMMARY)


if __name__ == '__main__':
    unittest.main()
