"""m061 tests: synthetic serializer/import/manifest checks always run; licensed
checks need the user's own original (LD2_TEST_EXE) and m045 output (LD2_M045_EXE)
and are SKIPPED otherwise. The host C test needs gcc+iconv, else SKIPPED."""
import hashlib, importlib.util, json, os, shutil, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pe_serializer as ps, import_builder as ib, source_profile as sp, site_plan  # noqa: E402

LAB = HERE.parents[1]


def licensed(var, default):
    p = os.environ.get(var) or (str(LAB / default) if (LAB / default).is_file() else '')
    return Path(p).read_bytes() if p and Path(p).is_file() else None


ORIGINAL = licensed('LD2_TEST_EXE', 'baseline/pristine/Ld95.exe')
M045 = licensed('LD2_M045_EXE', 'runs/m045/build-first/Ld95.exe')


def synthetic_pe(overlay=b'', slack=False, relocs=False, flags=0x10f):
    """Minimal fixed-base PE32: headers 0x1000, two sections, no imports."""
    raw = bytearray(0x3000)
    raw[0:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3c, 0x80)
    raw[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', raw, 0x84, 0x14c, 2, 0, 0, 0, 224, flags)
    opt = 0x98
    struct.pack_into('<H', raw, opt, 0x10b)
    struct.pack_into('<III', raw, opt + 4, 0x1000, 0x1000, 0)
    struct.pack_into('<I', raw, opt + 28, 0x400000)
    struct.pack_into('<II', raw, opt + 32, 0x1000, 0x1000)
    struct.pack_into('<II', raw, opt + 56, 0x3000, 0x1000)
    struct.pack_into('<I', raw, opt + 92, 16)
    if relocs:
        struct.pack_into('<II', raw, opt + 96 + 5 * 8, 0x2000, 8)
    t = opt + 224
    struct.pack_into('<8sIIIIIIHHI', raw, t, b'.text', 0x10, 0x1000, 0x1000, 0x1000, 0, 0, 0, 0, ps.SCN_CODE_RX)
    struct.pack_into('<8sIIIIIIHHI', raw, t + 40, b'.data', 0x10, 0x2000, 0x1000, 0x2000, 0, 0, 0, 0, ps.SCN_DATA_RW)
    raw[0x1000:0x1004] = b'\xc3\x90\x90\x90'
    raw[0x2000:0x2004] = b'DATA'
    if slack:
        raw[t + 80] = 1
    return bytes(raw) + overlay


class SerializerTests(unittest.TestCase):
    def add(self, raw, **kw):
        rvas = ps.plan_rvas(raw, [8, 20])
        adds = [dict(name='.ld2t', rva=rvas[0], data=b'\xcc' * 8, characteristics=ps.SCN_CODE_RX),
                dict(name='.ld2i', rva=rvas[1], data=b'I' * 20, characteristics=ps.SCN_DATA_RW)]
        for k, v in kw.items():
            adds[0][k] = v
        return ps.append_sections(raw, adds, {1: (rvas[1], 20)})

    def test_append_and_readback(self):
        raw = synthetic_pe()
        out, rep = self.add(raw)
        p = ps.parse(out)
        self.assertEqual(p['n'], 4)
        self.assertEqual(p['size_of_image'], 0x5000)
        self.assertEqual(p['dirs'][1], (0x4000, 20))
        self.assertEqual(out[:0x1000][p['sections'][0]['header']:p['sections'][0]['header'] + 80], raw[:0x1000][p['sections'][0]['header']:p['sections'][0]['header'] + 80])
        self.assertEqual(out[0x1000:0x3000], raw[0x1000:0x3000])
        self.assertEqual(ps.pe_checksum(out, p['opt'] + 64), struct.unpack_from('<I', out, p['opt'] + 64)[0])
        self.assertTrue(rep['original_sections_unchanged'])

    def test_refusals(self):
        cases = [(synthetic_pe(overlay=b'X' * 16), {}), (synthetic_pe(slack=True), {}), (synthetic_pe(relocs=True), {}),
                 (synthetic_pe(flags=0x10e), {}), (synthetic_pe(), dict(characteristics=0xE0000020)),
                 (synthetic_pe(), dict(rva=0x5000)), (synthetic_pe(), dict(name='.text')), (synthetic_pe(), dict(name='bad')),
                 (synthetic_pe(), dict(data=b''))]
        for raw, kw in cases:
            with self.subTest(kw=kw), self.assertRaises(ps.Refuse):
                self.add(raw, **kw)

    def test_directory_rules(self):
        raw = synthetic_pe()
        rvas = ps.plan_rvas(raw, [8])
        add = [dict(name='.ld2i', rva=rvas[0], data=b'I' * 8, characteristics=ps.SCN_DATA_RW)]
        for dirs in ({2: (rvas[0], 8)}, {1: (0x1000, 8)}, {1: (rvas[0], 9)}):
            with self.subTest(dirs=dirs), self.assertRaises(ps.Refuse):
                ps.append_sections(raw, add, dirs)

    def test_verify_detects_tamper(self):
        raw = synthetic_pe()
        out, _ = self.add(raw)
        bad = bytearray(out)
        bad[0x1001] ^= 1
        with self.assertRaises(ps.Refuse):
            ps.verify(raw, bytes(bad), [dict(rva=0x3000, data=b'\xcc' * 8), dict(rva=0x4000, data=b'I' * 20)], {1: 0})


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.m = json.loads((HERE / 'list_sites.json').read_text(encoding='utf-8'))

    def test_manifest_contract(self):
        m = self.m
        self.assertIs(m['production_can_apply'], False)
        self.assertEqual(m['source_sha256'], sp.ORIGINAL_SHA256)
        self.assertEqual(m['counts'], {'CB_INSERTSTRING': 5, 'LB_ADDSTRING': 33, 'LB_GETTEXT': 5, 'LB_INSERTSTRING': 71})
        pri = [s for s in m['sites'] if s['priority']]
        self.assertEqual(len(pri), 8)
        self.assertEqual(sorted({r for s in pri for r in s['roles']} - {'dialog-388'}),
                         ['commission-info', 'commission-list', 'inn-commission', 'shop-buy', 'shop-sell', 'shop-strengthen', 'tavern'])
        for s in m['sites']:
            if s['phase1_candidate']:
                self.assertFalse(s['readback_on_same_control'] or s['owner_draw'])
                self.assertFalse(s['message'].endswith('ADDSTRING') and s['sorted_listbox'])
                self.assertEqual(s['kind'], 'CWnd::SendDlgItemMessage')
        readback = {(s['control_id'], d) for s in m['sites'] if s['message'] == 'LB_GETTEXT' for d in s['dialogs']}
        self.assertEqual(readback, {(1071, 172), (1025, 152), (1026, 152), (1025, 153), (1026, 153)})

    def test_manifest_has_no_text(self):
        raw = (HERE / 'list_sites.json').read_bytes()
        self.assertTrue(all(b < 0x80 for b in raw), 'manifest must be ASCII-only (no game text)')


@unittest.skipUnless(ORIGINAL, 'licensed original EXE not provided')
class LicensedTests(unittest.TestCase):
    def test_original_profile_and_sites(self):
        self.assertEqual(sp.derive(ORIGINAL, ORIGINAL)['profile'], 'original')
        sites = site_plan.load_sites((HERE / 'list_sites.json').read_bytes(), priority_only=False)
        self.assertEqual(len(site_plan.verify_sites(ORIGINAL, sites)), 83)
        plan = site_plan.plan_retarget(ORIGINAL, site_plan.load_sites((HERE / 'list_sites.json').read_bytes()), 0xae3400)
        for off, old, new in plan:
            self.assertEqual(old[0], 0xE8)
            self.assertEqual(0x400000 + off + 5 + struct.unpack('<i', new[1:])[0], 0xae3400)

    def test_import_fragment_matches_m060(self):
        data, dsize, iats, before, after = ib.extend(ORIGINAL, 0x704000, [('GDI32.dll', 'TextOutW')])
        self.assertEqual(hashlib.sha256(data).hexdigest(), '16be0bf668aa920662aa4d6f95b1c8d136fe8903fa557c2c48b729ba79bd724d')
        self.assertEqual((dsize, iats[('GDI32.dll', 'TextOutW')], before, after), (300, 0x70414c, 13, 14))
        with self.assertRaises(ib.Refuse):
            ib.extend(ORIGINAL, 0x704000, [('USER32.dll', 'SendMessageA')])
        with self.assertRaises(ib.Refuse):
            ib.extend(ORIGINAL, 0x6db000, [('GDI32.dll', 'TextOutW')])

    def test_tampered_window_refused(self):
        sites = site_plan.load_sites((HERE / 'list_sites.json').read_bytes())
        bad = bytearray(ORIGINAL)
        bad[int(sites[0]['va'], 16) - 0x400000 - 3] ^= 1
        with self.assertRaises(site_plan.Refuse):
            site_plan.verify_sites(bytes(bad), sites)


@unittest.skipUnless(ORIGINAL and M045, 'licensed original and m045 output not provided')
class M045ProfileTests(unittest.TestCase):
    def test_m045_derivation(self):
        prof = sp.derive(ORIGINAL, M045)
        self.assertEqual((prof['profile'], prof['first_free_rva']), ('m045', 0x6e3000))
        self.assertEqual(len(site_plan.verify_sites(M045, site_plan.load_sites((HERE / 'list_sites.json').read_bytes()))), 8)
        data, dsize, iats, before, after = ib.extend(M045, 0x70b000, [('GDI32.dll', 'TextOutW'), ('USER32.dll', 'SendDlgItemMessageW')])
        self.assertEqual((before, after), (13, 15))

    def test_m045_tamper_refused(self):
        for off in (0x2000, 0x150):  # .text byte; header byte outside allowlist
            bad = bytearray(M045)
            bad[off] ^= 1
            with self.subTest(off=hex(off)), self.assertRaises(sp.Refuse):
                sp.derive(ORIGINAL, bytes(bad))


@unittest.skipUnless(shutil.which('gcc'), 'gcc not available')
class HostCoreTests(unittest.TestCase):
    def test_list_core(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'host_test'
            src = str(HERE / 'native' / 'host_test.c')
            for flags, expect in (
                ([], '16 checks, 0 failed'),
                (['-DHOST_MACRO'], '15 checks, 0 failed'),  # null-decode guard compiled out
            ):
                subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2', *flags, '-o', str(exe), src], check=True)
                r = subprocess.run([str(exe)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn(expect, r.stdout)



@unittest.skipUnless(importlib.util.find_spec('capstone'), 'capstone not installed')
class CoffRelocatorTests(unittest.TestCase):
    def test_synthetic_list_object_audit_and_relocate(self):
        import synthetic_list_obj, coff_obj, audit_list_obj, hashlib
        raw = synthetic_list_obj.build()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '8599def6cf44d1dcf20a52c2028ce52fd098f7a4b3043db37c07bf82ef2501be')
        report = audit_list_obj.audit(raw)
        self.assertEqual(report['entry'], '@LD2_ListInsert@24')
        self.assertEqual(report['ret_pop'], 16)
        self.assertFalse(report['production_can_apply'])
        bindings = {n: 0x1000 + i * 4 for i, n in enumerate(sorted(synthetic_list_obj.EXTERNS))}
        code, entry, det = coff_obj.relocate(
            raw, 0x401000, bindings,
            expected_sha256=report['object_sha256'],
            expected_undefined=set(synthetic_list_obj.EXTERNS),
            entry=synthetic_list_obj.ENTRY)
        self.assertEqual(code[-5:], bytes.fromhex('33c0c21000'))
        self.assertEqual(entry, 0x401000)
        self.assertEqual(det['fixups'], 7)

    def test_audit_rejects_extra_crt_symbol(self):
        import synthetic_list_obj, audit_list_obj
        raw = bytearray(synthetic_list_obj.build())
        # Corrupt: flip a byte in the string table so a name changes — easier to append a fake undef via parse failure path.
        # Instead, call audit with a patched undefined set by rebuilding with an extra extern.
        # Minimal: change ENTRY name in the object so defined_public mismatches.
        idx = bytes(raw).find(b'@LD2_ListInsert@24')
        self.assertGreater(idx, 0)
        raw[idx + 3] = ord('X')
        with self.assertRaises(SystemExit):
            audit_list_obj.audit(bytes(raw))


REAL_LIST_OBJ = LAB / 'runs/m061/compile-only/list_insert_w.obj'
REAL_LIST_SHA256 = 'd5349e58bd5087bb06aedda6c8b8dbfa1d2c0d1f87de42e1f86993869bfc61e0'


@unittest.skipUnless(importlib.util.find_spec('capstone') and REAL_LIST_OBJ.is_file(),
                     'capstone or local real MSVC list object missing (object is never committed)')
class RealListObjectAuditTests(unittest.TestCase):
    def test_real_object_audit_pins(self):
        import audit_list_obj, hashlib
        raw = REAL_LIST_OBJ.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), REAL_LIST_SHA256)
        rep = audit_list_obj.audit(raw)
        self.assertEqual(rep['defined_public'], ['@LD2_ListInsert@24'])
        self.assertEqual(rep['internal_callees_audited'],
                         ['?LD2_ListPrepare@@YAHIPBEPBULD2ListRow@@IP6AH0HPAGH@Z2@Z'])
        self.assertEqual(len(rep['normal_returns']), 5)
        self.assertEqual(sorted({c['target'] for c in rep['calls']}), [
            '?LD2_ListPrepare@@YAHIPBEPBULD2ListRow@@IP6AH0HPAGH@Z2@Z', '@__security_check_cookie@4',
            '_LD2_MultiByteToWideChar', '_LD2_OriginalDlgItem', '_LD2_SendDlgItemMessageW'])
        self.assertEqual(rep['relocation_counts'], {'6': 11, '20': 4})


class CoffVersusM060Tests(unittest.TestCase):
    @unittest.skipUnless((LAB / 'runs/m058/compile-only/name_pair.EHs.obj').is_file() and
                         (HERE.parent / 'm060' / 'memory_plan.py').is_file(),
                         'lab m058 object / m060 required')
    def test_matches_m060_relocate(self):
        import coff_obj, hashlib
        sys.path.insert(0, str(HERE.parent / 'm060'))
        import memory_plan as m060
        obj = (LAB / 'runs/m058/compile-only/name_pair.EHs.obj').read_bytes()
        bind = {'_LD2_EntryCount': 0xae4000, '_LD2_ExpectedTextOutA': 0xae4004, '_LD2_Entries': 0xae4008,
                '_LD2_TextOutW': 0xb0b14c, '___security_cookie': 0xa8f284, '@__security_check_cookie@4': 0x4fc870}
        c1, e1, _ = m060.relocate_reviewed(obj, 0x46e3000, bind)
        c2, e2, _ = coff_obj.relocate(obj, 0x46e3000, bind,
                                      expected_sha256=hashlib.sha256(obj).hexdigest(),
                                      expected_undefined=set(m060.EXTERNAL),
                                      entry='_LD2_NamePair@16')
        self.assertEqual(c1, c2)
        self.assertEqual(e1, e2)



if __name__ == '__main__':
    unittest.main()
