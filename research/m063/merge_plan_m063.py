"""m063a: merge plan with a THIRD helper slot (LD2_NameTextOut) next to NamePair v3 and
ListInsertV3, all three sharing ONE v3 catalog blob. In memory only; no file writer.

Lab/research only. production_can_apply=false, release_approved=false.

Layout (appended after m045's last section, same family as m061b/m062):
  .ld2t  [name_pair_v3][int3 pad 16][list_insert_v3][int3 pad 16][name_textout_v3]
  .ld2c  +0 CatalogBytes | +4 ExpectedTextOutA=0x4e13d7 | +8 OriginalDlgItem=0x4ea671 | +12 ListMode
         +16 v3 blob 'LD2C'                      (unchanged from m062: no new policy word)
  .ld2i  import fragment (m062 set: GDI32!TextOutW + 5 USER32 *W). NameTextOut adds NO import.

NameTextOut bindings == NamePair v3 bindings (same addresses, asserted):
  _LD2_CatalogBytes, _LD2_Catalog, _LD2_ExpectedTextOutA, _LD2_TextOutW, /GS cookie pair.

Object lock: the NameTextOut MSVC object is NOT compiled yet (m063b). TEXTOUT_OBJECT_SHA256 is
None, so build_inert_m063 refuses unless the caller passes an explicit rehearsal pin; such a
build is marked rehearsal=True / handoff_eligible=False and must never be packaged.
"""
from pathlib import Path
import hashlib, struct, sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
import source_profile, import_builder, pe_serializer, coff_obj  # noqa: E402
import merge_plan_v3 as mv  # noqa: E402
import catalog_v3 as c3  # noqa: E402

mp = mv.mp
Refuse = mv.Refuse
need, sha, align = mv.need, mv.sha, mv.align

TEXTOUT_OBJECT_SHA256 = None            # pending m063b (Win11 MSVC compile + COFF audit)
TEXTOUT_ENTRY = '@LD2_NameTextOut@24'
TEXTOUT_UNDEFINED = mv.NAME_V3_UNDEFINED  # identical binding set to NamePair v3
TEXTOUT_PUBLIC = frozenset({TEXTOUT_ENTRY, '_LD2N_FindCopy@12', '_LD2N_Wipe@8'})
SLOT_ALIGN = 16
MAX_FRAGMENT = 0x4000                   # coff_obj.relocate limit per object
BASE = 0x400000


def plan_code_layout(lengths, slot_align=SLOT_ALIGN):
    """lengths: [name, list, textout] fragment bytes -> (offsets, span). Refuses bad layouts."""
    need(isinstance(lengths, (list, tuple)) and len(lengths) == 3, 'Three helper slots')
    need(all(type(n) is int and 0 < n <= MAX_FRAGMENT for n in lengths), 'Fragment length')
    need(type(slot_align) is int and slot_align >= 16 and slot_align & (slot_align - 1) == 0, 'Slot alignment')
    offs, at = [], 0
    for n in lengths:
        offs.append(at)
        at = align(at + n, slot_align)
    span = offs[-1] + lengths[-1]
    check_code_layout(offs, lengths, span, slot_align)
    return offs, span


def check_code_layout(offs, lengths, span, slot_align=SLOT_ALIGN):
    need(len(offs) == len(lengths) == 3, 'Three helper slots')
    need(offs[0] == 0, 'First slot at .ld2t start')
    for o, n in zip(offs, lengths):
        need(o % slot_align == 0, 'Slot not aligned')
        need(0 < n <= MAX_FRAGMENT and o + n <= span, 'Slot outside .ld2t span')
    for (a, n), b in zip(zip(offs, lengths), offs[1:]):
        need(a + n <= b, 'Helper slots overlap')
    need(span == offs[-1] + lengths[-1], 'Span drift')


def check_textout_object(raw, pin):
    need(type(raw) is bytes, 'NameTextOut object bytes')
    need(type(pin) is str and len(pin) == 64 and sha(raw) == pin, 'NameTextOut object sha256 not pinned')
    need(pin not in (mv.NAME_V3_OBJECT_SHA256, mv.LIST_V3_OBJECT_SHA256), 'NameTextOut pin reuses another object')
    obj = coff_obj.parse(raw)
    need(set(coff_obj.undefined(obj)) == set(TEXTOUT_UNDEFINED), 'NameTextOut undefined set')
    need(set(coff_obj.defined_external(obj)) == set(TEXTOUT_PUBLIC), 'NameTextOut public set')
    return coff_obj.layout(obj)[1]


def check_image_base(candidate):
    """imm32 site rewrites need a fixed image base: relocations stripped, no DYNAMIC_BASE."""
    pe = struct.unpack_from('<I', candidate, 0x3c)[0]
    chars = struct.unpack_from('<H', candidate, pe + 22)[0]
    dllch = struct.unpack_from('<H', candidate, pe + 24 + 70)[0]
    base = struct.unpack_from('<I', candidate, pe + 24 + 28)[0]
    need(base == BASE and chars & 1 and not dllch & 0x40, 'Fixed image base required (imm32 helper VA)')


def build_inert_m063(original, candidate, name_obj, list_obj, textout_obj, blob,
                     list_mode=mp.DEFAULT_LIST_MODE, textout_pin=None):
    """Inert three-helper image (hook span + all sites untouched). Returns (image, report)."""
    pin = textout_pin or TEXTOUT_OBJECT_SHA256
    need(pin is not None, 'NameTextOut object not locked (m063b MSVC compile pending)')
    rehearsal = TEXTOUT_OBJECT_SHA256 is None or pin != TEXTOUT_OBJECT_SHA256
    need(type(list_mode) is int and list_mode in mp.LIST_MODES, 'List mode')
    need(sha(name_obj) == mv.NAME_V3_OBJECT_SHA256, 'name_pair_v3 object sha256 not locked')
    need(sha(list_obj) == mv.LIST_V3_OBJECT_SHA256, 'list_insert_v3 object sha256 not locked')
    t_len = check_textout_object(textout_obj, pin)
    cap = mv.capacity_gate(blob)
    prof = source_profile.derive(original, candidate)
    check_image_base(candidate)
    before = sha(candidate)
    need(struct.unpack_from('<I', candidate, 0x3c)[0] == 0xf0, 'PE offset')
    need(sha(candidate[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]]) == mp.HOOK_SPAN_SHA256, 'Hook span hash')
    view = import_builder.View(candidate)
    need(view.dirs[13] == (0x192c7c, 64) and sha(view.read(0x192c7c, 64)) == mp.DELAY_DESCRIPTOR_SHA256, 'Delay descriptor passthrough')
    need(mp.iat_name(view, mp.GETDLGITEM_IAT_VA - BASE) == ('USER32.dll', 'GetDlgItem'), 'GetDlgItem IAT slot')
    need(mp.iat_name(view, mp.MULTIBYTETOWIDECHAR_IAT_VA - BASE) == ('KERNEL32.dll', 'MultiByteToWideChar'), 'MultiByteToWideChar IAT slot')
    need(mp.WRAPPER_VA != 0, 'OriginalDlgItem must be non-zero')

    catalog = struct.pack('<IIII', len(blob), mp.TEXTOUTA_HELPER_VA, mp.WRAPPER_VA, list_mode) + blob
    need(len(catalog) == cap['section_bytes'], 'catalog layout')
    lay = lambda raw: coff_obj.layout(coff_obj.parse(raw))[1]
    lens = [lay(name_obj), lay(list_obj), t_len]
    offs, code_span = plan_code_layout(lens)
    code_rva, cat_rva, imp_rva = pe_serializer.plan_rvas(candidate, [code_span, len(catalog), 0x1000])
    need(cat_rva >= code_rva + code_span and imp_rva >= cat_rva + len(catalog), 'Planned sections overlap')
    frag, dsize, iats, nbefore, nafter = import_builder.extend(candidate, imp_rva, list(mv.V3_APIS))

    C = BASE + cat_rva
    shared = {'_LD2_CatalogBytes': C + mv.OFF_BYTES, '_LD2_Catalog': C + mv.CAT_HDR,
              '___security_cookie': mp.COOKIE_VA, '@__security_check_cookie@4': mp.CHECK_COOKIE_VA}
    name_bindings = dict(shared, **{'_LD2_ExpectedTextOutA': C + mv.OFF_EXPECTED,
                                    '_LD2_TextOutW': BASE + iats[('GDI32.dll', 'TextOutW')]})
    textout_bindings = dict(name_bindings)
    need(textout_bindings == name_bindings and set(textout_bindings) == set(TEXTOUT_UNDEFINED), 'NameTextOut shares NamePair bindings')
    list_bindings = dict(shared, **{
        '_LD2_OriginalDlgItem': C + mv.OFF_DLG, '_LD2_ListMode': C + mv.OFF_MODE,
        '_LD2_SendDlgItemMessageW': BASE + iats[('USER32.dll', 'SendDlgItemMessageW')],
        '_LD2_MultiByteToWideChar': mp.MULTIBYTETOWIDECHAR_IAT_VA, '_LD2_GetDlgItem': mp.GETDLGITEM_IAT_VA,
        '_LD2_IsWindowUnicode': BASE + iats[('USER32.dll', 'IsWindowUnicode')],
        '_LD2_GetWindowLongW': BASE + iats[('USER32.dll', 'GetWindowLongW')],
        '_LD2_GetClassLongW': BASE + iats[('USER32.dll', 'GetClassLongW')],
        '_LD2_SetWindowLongW': BASE + iats[('USER32.dll', 'SetWindowLongW')]})
    code_va = BASE + code_rva
    name_va, list_va, textout_va = (code_va + o for o in offs)
    name_code, name_entry, name_details = coff_obj.relocate(
        name_obj, name_va, name_bindings, expected_sha256=mv.NAME_V3_OBJECT_SHA256,
        expected_undefined=mv.NAME_V3_UNDEFINED, entry=mv.NAME_V3_ENTRY)
    list_code, list_entry, list_details = coff_obj.relocate(
        list_obj, list_va, list_bindings, expected_sha256=mv.LIST_V3_OBJECT_SHA256,
        expected_undefined=mv.LIST_V3_UNDEFINED, entry=mv.LIST_V3_ENTRY)
    t_code, t_entry, t_details = coff_obj.relocate(
        textout_obj, textout_va, textout_bindings, expected_sha256=pin,
        expected_undefined=TEXTOUT_UNDEFINED, entry=TEXTOUT_ENTRY)
    need([len(name_code), len(list_code), len(t_code)] == lens, 'Code length drift')
    ranges = [(name_va, name_va + lens[0]), (list_va, list_va + lens[1]), (textout_va, textout_va + lens[2])]
    for e, (lo, hi) in zip((name_entry, list_entry, t_entry), ranges):
        need(lo <= e < hi, 'Entry outside its slot')
    need(len({name_entry, list_entry, t_entry}) == 3, 'Entries must be distinct')
    pad = lambda n: b'\xcc' * n
    code = (name_code + pad(offs[1] - lens[0]) + list_code + pad(offs[2] - offs[1] - lens[1]) + t_code)
    need(len(code) == code_span, 'Code span')

    merged, ser = pe_serializer.append_sections(candidate, [
        dict(name='.ld2t', rva=code_rva, data=code, characteristics=pe_serializer.SCN_CODE_RX),
        dict(name='.ld2c', rva=cat_rva, data=catalog, characteristics=pe_serializer.SCN_RDATA_R),
        dict(name='.ld2i', rva=imp_rva, data=frag, characteristics=pe_serializer.SCN_DATA_RW),
    ], {1: (imp_rva, dsize)})
    need(merged[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]] == candidate[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]], 'Hook span must stay original (inert)')
    need(merged[:len(candidate)][0x1000:0x124c39] == candidate[0x1000:0x124c39], 'Inert: .text untouched')
    after = import_builder.imports(import_builder.View(merged), (imp_rva, dsize))
    need(import_builder.semantic(after[:nbefore]) == import_builder.semantic(import_builder.imports(view, view.dirs[1])), 'Merged import semantics')
    extents = mv.check_section_extents(merged, cat_rva, catalog)
    mvw = import_builder.View(merged)
    need(mvw.read(code_rva, code_span) == code, '.ld2t readback')
    dlg = struct.unpack('<I', mvw.read(cat_rva + mv.OFF_DLG, 4))[0]
    need(dlg == mp.WRAPPER_VA and dlg != 0, 'OriginalDlgItem slot must read back non-zero (0x4ea671)')
    need(struct.unpack('<I', mvw.read(cat_rva + mv.OFF_BYTES, 4))[0] == len(blob), 'CatalogBytes readback')
    need(c3.decode_v3(mvw.read(cat_rva + mv.CAT_HDR, len(blob))) == c3.decode_v3(blob), 'Blob readback decodes identically')
    need(sha(candidate) == before and sha(original) == source_profile.ORIGINAL_SHA256, 'Inputs mutated')
    hx = lambda d: {k: hex(v) for k, v in sorted(d.items())}
    return merged, dict(
        profile=prof['profile'], source_sha256=before,
        name_object_sha256=mv.NAME_V3_OBJECT_SHA256, list_object_sha256=mv.LIST_V3_OBJECT_SHA256,
        textout_object_sha256=pin, textout_rehearsal=rehearsal, handoff_eligible=not rehearsal,
        blob_sha256=sha(blob), capacity=cap, catalog_section=extents, code_sha256=sha(code),
        code_range=[hex(code_va), hex(code_va + code_span)],
        slots=dict(offsets=offs, lengths=lens, align=SLOT_ALIGN),
        entry_va=hex(name_entry), list_entry_va=hex(list_entry), textout_entry_va=hex(t_entry),
        name_code_va=hex(name_va), list_code_va=hex(list_va), textout_code_va=hex(textout_va),
        bindings=hx(name_bindings), list_bindings=hx(list_bindings), textout_bindings=hx(textout_bindings),
        name_details=name_details, list_details=list_details, textout_details=t_details,
        original_dlgitem_va=hex(mp.WRAPPER_VA), original_dlgitem_slot_va=hex(C + mv.OFF_DLG),
        list_mode=list_mode, list_mode_slot_va=hex(C + mv.OFF_MODE),
        new_imports=[f'{d}!{a}' for d, a in mv.V3_APIS], import_descriptors=[nbefore, nafter],
        serializer=ser, hook_span_patched=False, list_sites_retargeted=False, textout_sites_patched=False,
        inert=True, file_written=False, production_can_apply=False, release_approved=False)
