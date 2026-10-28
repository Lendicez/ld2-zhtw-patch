"""m061b tests (list helper v2 / profile 'u'): Unicode-flip design, static only.

Always: synthetic profile-u COFF audit + relocation, audit profile separation, reviewed
import set. With gcc: host core test (miss accounting). With `python -m ziglang`:
i386 mock execution of the real v2 entry against fake APIs and a clang REHEARSAL COFF
audited under profile 'u' (never pinned). With the user's licensed EXEs (lab only):
in-memory dual merge + enable for profile 'u' — no file is written.
production_can_apply stays false everywhere."""
import hashlib, importlib.util, os, shutil, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import import_builder as ib  # noqa: E402

LAB = HERE.parents[1]
HAVE_CAPSTONE = importlib.util.find_spec('capstone') is not None
HAVE_ZIG = importlib.util.find_spec('ziglang') is not None


def licensed(var, default):
    p = os.environ.get(var) or (str(LAB / default) if (LAB / default).is_file() else '')
    return Path(p).read_bytes() if p and Path(p).is_file() else None


ORIGINAL = licensed('LD2_TEST_EXE', 'baseline/pristine/Ld95.exe')
M045 = licensed('LD2_M045_EXE', 'runs/m045/build-first/Ld95.exe')
TEXT_OBJ = LAB / 'runs/m058/compile-only/name_pair.EHs.obj'
CATALOG = LAB.parent / 'ld2-zhtw-patch-m051/research/translations/m051-items.zh-TW.json'
U_APIS_NEW = {('USER32.dll', 'IsWindowUnicode'), ('USER32.dll', 'GetWindowLongW'),
              ('USER32.dll', 'GetClassLongW'), ('USER32.dll', 'SetWindowLongW')}


class ReviewedApiTests(unittest.TestCase):
    def test_reviewed_set_is_exact(self):
        self.assertEqual(ib.REVIEWED_APIS, frozenset({('GDI32.dll', 'TextOutW'), ('USER32.dll', 'SendDlgItemMessageW')}) | U_APIS_NEW)

    def test_no_ansi_or_hooking_apis_reviewed(self):
        names = {a for _, a in ib.REVIEWED_APIS}
        for bad in ('SetWindowLongA', 'SetWindowsHookExA', 'SetWindowsHookExW', 'SetClassLongW', 'SetClassLongA',
                    'CallWindowProcW', 'SetWindowLongPtrW', 'VirtualProtect', 'LoadLibraryA', 'GetProcAddress'):
            self.assertNotIn(bad, names)


@unittest.skipUnless(HAVE_CAPSTONE, 'capstone not installed')
class ProfileUAuditTests(unittest.TestCase):
    def test_synthetic_u_audit_and_relocate(self):
        import synthetic_list_obj as so, audit_list_obj as al, coff_obj
        raw = so.build('u')
        rep = al.audit(raw, 'u')
        self.assertEqual(rep['entry'], '@LD2_ListInsertU@24')
        self.assertEqual(rep['profile'], 'u')
        self.assertEqual(len(rep['undefined']), 13)
        self.assertFalse(rep['production_can_apply'])
        bindings = {n: 0x1000 + i * 4 for i, n in enumerate(sorted(so.EXTERNS_U))}
        code, entry, det = coff_obj.relocate(raw, 0x401000, bindings, expected_sha256=rep['object_sha256'],
                                             expected_undefined=set(so.EXTERNS_U), entry=so.ENTRY_U)
        self.assertEqual(det['fixups'], 13)
        self.assertEqual(code[-5:], bytes.fromhex('33c0c21000'))

    def test_v1_synthetic_unchanged(self):
        import synthetic_list_obj as so
        self.assertEqual(hashlib.sha256(so.build()).hexdigest(),
                         '8599def6cf44d1dcf20a52c2028ce52fd098f7a4b3043db37c07bf82ef2501be')

    def test_profiles_do_not_cross(self):
        import synthetic_list_obj as so, audit_list_obj as al
        with self.assertRaises(SystemExit):
            al.audit(so.build('v1'), 'u')
        with self.assertRaises(SystemExit):
            al.audit(so.build('u'), 'v1')
        with self.assertRaises(SystemExit):
            al.audit(so.build('u'), 'nope')

    def test_call_through_data_binding_refused(self):
        import synthetic_list_obj as so, audit_list_obj as al
        raw = bytearray(so.build('u'))
        # Turn the first `mov eax, [_LD2_EntryCount]` (A1 abs32) into a 5-byte `call` whose
        # relocated field still names the data binding: the audit must refuse it.
        at = raw.find(bytes.fromhex('a100000000'))
        raw[at] = 0xE8
        with self.assertRaises(SystemExit):
            al.audit(bytes(raw), 'u')


@unittest.skipUnless(shutil.which('gcc'), 'gcc not available')
class HostCoreUTests(unittest.TestCase):
    def test_list_core_u(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'host_test_u'
            src = str(HERE / 'native-u' / 'host_test_u.c')
            for flags, expect in (([], '25 checks, 0 failed'), (['-DHOST_MACRO'], '24 checks, 0 failed')):
                subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2', *flags, '-o', str(exe), src], check=True)
                r = subprocess.run([str(exe)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn(expect, r.stdout)


@unittest.skipUnless(HAVE_ZIG, 'ziglang not installed (pip install ziglang)')
class I386MockTests(unittest.TestCase):
    """Executes LD2_ListInsertU (clang, i386 Linux ABI: fastcall entry, stdcall fakes)."""
    def test_mock_u(self):
        n = HERE / 'native-u'
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'mock_u'
            subprocess.run([sys.executable, '-m', 'ziglang', 'c++', '-target', 'x86-linux-musl', '-fms-extensions',
                            '-D_M_IX86=600', '-O2', '-fstack-protector-strong', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', '-Wno-unused-command-line-argument',
                            str(n / 'list_insert_u.cpp'), str(n / 'list_mock_test_u.cpp'), '-o', str(exe)],
                           check=True, capture_output=True)
            r = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('cases=22 assertions=1116 failed=0 game_or_user32_called=false', r.stdout)


@unittest.skipUnless(HAVE_ZIG and HAVE_CAPSTONE, 'ziglang/capstone not installed')
class RehearsalObjectTests(unittest.TestCase):
    def test_rehearsal_u_passes_profile_u(self):
        r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'rehearse_list_obj.py')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('"may_pin": false', r.stdout)
        self.assertIn('"esp_and_nonvolatile_preserved_on_normal_paths": true', r.stdout)
        for api in ('_LD2_GetDlgItem', '_LD2_IsWindowUnicode', '_LD2_GetWindowLongW', '_LD2_GetClassLongW', '_LD2_SetWindowLongW'):
            self.assertIn(api, r.stdout)


def rehearsal_object():
    import rehearse_list_obj as rl
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'u.obj'
        rl.compile_obj(rl.SOURCES['u'], p)
        return rl.normalise(p.read_bytes())


@unittest.skipUnless(ORIGINAL and M045 and TEXT_OBJ.is_file() and CATALOG.is_file() and HAVE_CAPSTONE
                     and (HERE / 'merge_plan.py').is_file(),
                     'licensed EXEs / m058 object / catalog / lab-only merge_plan.py missing')
class LicensedMergeUTests(unittest.TestCase):
    def build(self, mode=None, apis=None, obj=None):
        import merge_plan as mp, synthetic_list_obj as so
        lo = obj or so.build('u')
        return mp.build_inert(ORIGINAL, M045, TEXT_OBJ.read_bytes(), CATALOG.read_bytes(), apis=apis or mp.LIST_U_APIS,
                              list_object_bytes=lo, list_object_sha256=hashlib.sha256(lo).hexdigest(),
                              list_profile='u', list_mode=mode)

    def test_inert_u_bindings_and_mode_word(self):
        import merge_plan as mp
        merged, rep = self.build()
        self.assertEqual(rep['list_profile'], 'u')
        self.assertEqual(rep['list_mode'], 2)
        b = rep['list_bindings']
        self.assertEqual(b['_LD2_GetDlgItem'], '0x525498')
        self.assertEqual(b['_LD2_MultiByteToWideChar'], '0x52537c')
        self.assertEqual(int(b['_LD2_ListMode'], 16), int(rep['original_dlgitem_slot_va'], 16) + 4)
        self.assertEqual(set(rep['new_imports']), {f'{d}!{a}' for d, a in mp.LIST_U_APIS})
        self.assertFalse(rep['hook_span_patched'] or rep['list_sites_retargeted'] or rep['production_can_apply'])
        view = ib.View(merged)
        for key, api in (('_LD2_IsWindowUnicode', 'IsWindowUnicode'), ('_LD2_GetWindowLongW', 'GetWindowLongW'),
                         ('_LD2_GetClassLongW', 'GetClassLongW'), ('_LD2_SetWindowLongW', 'SetWindowLongW'),
                         ('_LD2_SendDlgItemMessageW', 'SendDlgItemMessageW'), ('_LD2_GetDlgItem', 'GetDlgItem')):
            self.assertEqual(mp.iat_name(view, int(b[key], 16) - 0x400000), ('USER32.dll', api), key)
        mode_rva = int(b['_LD2_ListMode'], 16) - 0x400000
        self.assertEqual(struct.unpack('<I', view.read(mode_rva, 4))[0], 2)

    def test_modes_and_refusals(self):
        import merge_plan as mp, source_profile
        for m in (0, 1, 2):
            merged, rep = self.build(mode=m)
            rva = int(rep['list_bindings']['_LD2_ListMode'], 16) - 0x400000
            self.assertEqual(struct.unpack('<I', ib.View(merged).read(rva, 4))[0], m)
        for bad in (3, -1, True, '2'):
            with self.assertRaises(source_profile.Refuse):
                self.build(mode=bad)
        with self.assertRaises(source_profile.Refuse):
            self.build(apis=mp.LIST_APIS)

    @unittest.skipUnless(HAVE_ZIG, 'ziglang not installed')
    def test_enable_in_memory_with_rehearsal_object(self):
        import enable_plan as ep, site_plan
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        inert, rep = self.build(obj=rehearsal_object())
        sites = site_plan.load_sites((HERE / 'list_sites.json').read_bytes())
        en, erep = ep.apply_enabled(inert, int(rep['entry_va'], 16), int(rep['list_entry_va'], 16), sites)
        self.assertEqual(len(erep['sites']), 8)
        self.assertFalse(erep['file_written'] or erep['production_can_apply'])
        view = ib.View(en)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        targets = set()
        for s in erep['sites']:
            va = int(s['va'], 16)
            i = next(md.disasm(view.read(va - 0x400000, 5), va))
            targets.add(int(i.op_str, 16))
        self.assertEqual(targets, {int(rep['list_entry_va'], 16)})
        # Every indirect call inside the placed v2 helper goes through a reviewed slot.
        allowed = {int(v, 16) for k, v in rep['list_bindings'].items() if k not in ('_LD2_EntryCount', '_LD2_Entries', '_LD2_ListMode', '___security_cookie')}
        entry = int(rep['list_entry_va'], 16)
        code = view.read(entry - 0x400000, int(rep['list_details']['code_bytes']))
        seen = set()
        for i in md.disasm(code, entry):
            if i.mnemonic == 'call' and i.op_str.startswith('dword ptr ['):
                seen.add(int(i.op_str[len('dword ptr ['):-1], 16))
        self.assertTrue(seen)
        self.assertLessEqual(seen, allowed)


if __name__ == '__main__':
    unittest.main()
