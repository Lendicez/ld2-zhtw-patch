"""m063c: merge plan for the three v4 helpers sharing ONE catalog v4 blob. In memory only.

Lab/research only. production_can_apply=false, release_approved=false. No file writer.

Same layout/bindings as merge_plan_m063 (m063a), but every helper is the v4 build:
  .ld2t  [name_pair_v4][int3 pad 16][list_insert_v4 (2 entries)][int3 pad 16][name_textout_v4]
  .ld2c  +0 CatalogBytes | +4 ExpectedTextOutA=0x4e13d7 | +8 OriginalDlgItem=0x4ea671 | +12 ListMode
         +16 v4 blob 'LD2C' version 4              (no new policy word: flags are per entry point)
  .ld2i  import fragment (m062 set: GDI32!TextOutW + 5 USER32 *W).
list_insert_v4.obj exports TWO fastcall entries; both are reported so the enable plan can route
item/unclassified sites to @LD2_ListInsertV4@24 and name sites to @LD2_ListInsertNameV4@24.

Fail closed both ways: v3 objects (pinned m062 / any m063a textout pin) are refused here, a v3 blob
is refused by capacity_gate_v4, and the pinned v3 helpers refuse a v4 blob at run time.
Object lock: no v4 object has been compiled by MSVC (m063b needs the user's consent), so all
three pins are None; a build needs explicit rehearsal pins and is marked rehearsal=True /
handoff_eligible=False. Such a build must never be packaged.
"""
from pathlib import Path
import struct, sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import source_profile, import_builder, pe_serializer, coff_obj  # noqa: E402
import merge_plan_m063 as mm  # noqa: E402
import catalog_v4 as c4  # noqa: E402

mv, mp = mm.mv, mm.mv.mp
Refuse, need, sha = mm.Refuse, mm.need, mm.sha
BASE = mm.BASE

# Pending m063b (Win11 MSVC compile + COFF audits via rehearse_v4_objs.py --list-obj/...).
NAME_V4_OBJECT_SHA256 = None
LIST_V4_OBJECT_SHA256 = None
TEXTOUT_V4_OBJECT_SHA256 = None
NAME_V4_ENTRY = mv.NAME_V3_ENTRY                       # '_LD2_NamePair@16' (same symbol names as v3)
NAME_V4_UNDEFINED = mv.NAME_V3_UNDEFINED
NAME_V4_PUBLIC = frozenset({'_LD2_NamePair@16', '_LD2_LoadMethod@4', '_LD2_OriginalOne@16',
                            '_LD2_OriginalPair@12', '_LD2_FindCopy@16', '_LD2_Wipe@8'})
LIST_V4_ENTRY_ITEM = '@LD2_ListInsertV4@24'          # item_list / unclassified_list: ANY|JOIN
LIST_V4_ENTRY_NAME = '@LD2_ListInsertNameV4@24'      # name: ANY|JOIN|NAME_ONLY
LIST_V4_PUBLIC = frozenset({LIST_V4_ENTRY_ITEM, LIST_V4_ENTRY_NAME})
LIST_V4_UNDEFINED = mv.LIST_V3_UNDEFINED
TEXTOUT_V4_ENTRY = mm.TEXTOUT_ENTRY
TEXTOUT_V4_UNDEFINED = mm.TEXTOUT_UNDEFINED
TEXTOUT_V4_PUBLIC = mm.TEXTOUT_PUBLIC
V3_PINS = frozenset(p for p in (mv.NAME_V3_OBJECT_SHA256, mv.LIST_V3_OBJECT_SHA256, mm.TEXTOUT_OBJECT_SHA256) if p)
V4_BLOB_MAX = c4.V4_HEADER + c4.V4_MAX_ROWS * c4.V4_ROW + c4.V4_MAX_POOL   # what ld2c4_open accepts
SLOTS = ('name', 'list', 'textout')
LOCKED = dict(name=NAME_V4_OBJECT_SHA256, list=LIST_V4_OBJECT_SHA256, textout=TEXTOUT_V4_OBJECT_SHA256)
SHAPES = dict(name=(NAME_V4_UNDEFINED, NAME_V4_PUBLIC), list=(LIST_V4_UNDEFINED, LIST_V4_PUBLIC),
              textout=(TEXTOUT_V4_UNDEFINED, TEXTOUT_V4_PUBLIC))


def capacity_gate_v4(blob, section_budget=mv.SECTION_BUDGET):
    """Refuse (never truncate) when the v4 blob cannot be carried by .ld2c. A v3 blob is refused."""
    need(type(blob) is bytes and len(blob) >= c4.V4_HEADER, 'v4 blob shape')
    need(struct.unpack_from('<H', blob, 4)[0] == c4.V4_VERSION, 'Catalog version must be 4 (v3 blob refused)')
    try:
        rows = c4.decode_v4(blob)
    except c4.Refuse as e:
        raise Refuse(f'v4 blob: {e}') from None
    need(1 <= len(rows) <= c4.V4_MAX_ROWS, 'v4 row capacity (<=8192)')
    pool = struct.unpack_from('<I', blob, 24)[0]
    need(pool <= c4.V4_MAX_POOL, 'v4 pool capacity (<=1 MiB)')
    need(len(blob) <= V4_BLOB_MAX, 'v4 blob exceeds helper ld2c4_open limit')
    section = mv.CAT_HDR + len(blob)
    need(section <= section_budget, f'.ld2c section {section} B exceeds budget {section_budget} B')
    return dict(rows=len(rows), blob_bytes=len(blob), pool_bytes=pool, section_bytes=section,
                section_budget=section_budget, headroom_bytes=section_budget - section,
                helper_blob_max=V4_BLOB_MAX, catalog_version=4)


def resolve_pins(pins=None):
    """pins: optional {slot: sha256} rehearsal pins. Returns (pins, rehearsal). Refuses v3 pins."""
    pins = dict(pins or {})
    need(set(pins) <= set(SLOTS), 'Unknown pin slot')
    out = {s: pins.get(s) or LOCKED[s] for s in SLOTS}
    for s, p in out.items():
        need(p is not None, f'{s}_v4 object not locked (m063b MSVC compile pending)')
        need(type(p) is str and len(p) == 64, f'{s}_v4 pin shape')
        need(p not in V3_PINS, f'{s}_v4 pin is a v3 object (v3 helpers cannot read a v4 blob)')
    need(len(set(out.values())) == 3, 'v4 pins must be three distinct objects')
    rehearsal = any(LOCKED[s] is None or out[s] != LOCKED[s] for s in SLOTS)
    return out, rehearsal


def check_object(slot, raw, pin):
    need(type(raw) is bytes and sha(raw) == pin, f'{slot}_v4 object sha256 not pinned')
    obj = coff_obj.parse(raw)
    und, pub = SHAPES[slot]
    need(set(coff_obj.undefined(obj)) == set(und), f'{slot}_v4 undefined set')
    need(set(coff_obj.defined_external(obj)) == set(pub), f'{slot}_v4 public set')
    return coff_obj.layout(obj)[1]


def build_inert_v4(original, candidate, name_obj, list_obj, textout_obj, blob,
                   list_mode=mp.DEFAULT_LIST_MODE, pins=None):
    """Inert three-helper v4 image (hook span + all sites untouched). Returns (image, report)."""
    pins, rehearsal = resolve_pins(pins)
    need(type(list_mode) is int and list_mode in mp.LIST_MODES, 'List mode')
    objs = dict(name=name_obj, list=list_obj, textout=textout_obj)
    lens = [check_object(s, objs[s], pins[s]) for s in SLOTS]
    cap = capacity_gate_v4(blob)
    prof = source_profile.derive(original, candidate)
    mm.check_image_base(candidate)
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
    offs, code_span = mm.plan_code_layout(lens)
    code_rva, cat_rva, imp_rva = pe_serializer.plan_rvas(candidate, [code_span, len(catalog), 0x1000])
    need(cat_rva >= code_rva + code_span and imp_rva >= cat_rva + len(catalog), 'Planned sections overlap')
    frag, dsize, iats, nbefore, nafter = import_builder.extend(candidate, imp_rva, list(mv.V3_APIS))

    C = BASE + cat_rva
    shared = {'_LD2_CatalogBytes': C + mv.OFF_BYTES, '_LD2_Catalog': C + mv.CAT_HDR,
              '___security_cookie': mp.COOKIE_VA, '@__security_check_cookie@4': mp.CHECK_COOKIE_VA}
    name_bindings = dict(shared, **{'_LD2_ExpectedTextOutA': C + mv.OFF_EXPECTED,
                                    '_LD2_TextOutW': BASE + iats[('GDI32.dll', 'TextOutW')]})
    textout_bindings = dict(name_bindings)
    list_bindings = dict(shared, **{
        '_LD2_OriginalDlgItem': C + mv.OFF_DLG, '_LD2_ListMode': C + mv.OFF_MODE,
        '_LD2_SendDlgItemMessageW': BASE + iats[('USER32.dll', 'SendDlgItemMessageW')],
        '_LD2_MultiByteToWideChar': mp.MULTIBYTETOWIDECHAR_IAT_VA, '_LD2_GetDlgItem': mp.GETDLGITEM_IAT_VA,
        '_LD2_IsWindowUnicode': BASE + iats[('USER32.dll', 'IsWindowUnicode')],
        '_LD2_GetWindowLongW': BASE + iats[('USER32.dll', 'GetWindowLongW')],
        '_LD2_GetClassLongW': BASE + iats[('USER32.dll', 'GetClassLongW')],
        '_LD2_SetWindowLongW': BASE + iats[('USER32.dll', 'SetWindowLongW')]})
    need(set(list_bindings) == set(LIST_V4_UNDEFINED) and set(textout_bindings) == set(TEXTOUT_V4_UNDEFINED), 'Binding sets')
    code_va = BASE + code_rva
    name_va, list_va, textout_va = (code_va + o for o in offs)
    name_code, name_entry, name_details = coff_obj.relocate(
        name_obj, name_va, name_bindings, expected_sha256=pins['name'],
        expected_undefined=NAME_V4_UNDEFINED, entry=NAME_V4_ENTRY)
    list_code, item_entry, list_details = coff_obj.relocate(
        list_obj, list_va, list_bindings, expected_sha256=pins['list'],
        expected_undefined=LIST_V4_UNDEFINED, entry=LIST_V4_ENTRY_ITEM)
    list_code2, name_list_entry, _ = coff_obj.relocate(
        list_obj, list_va, list_bindings, expected_sha256=pins['list'],
        expected_undefined=LIST_V4_UNDEFINED, entry=LIST_V4_ENTRY_NAME)
    need(list_code2 == list_code, 'List relocation not deterministic')
    t_code, t_entry, t_details = coff_obj.relocate(
        textout_obj, textout_va, textout_bindings, expected_sha256=pins['textout'],
        expected_undefined=TEXTOUT_V4_UNDEFINED, entry=TEXTOUT_V4_ENTRY)
    need([len(name_code), len(list_code), len(t_code)] == lens, 'Code length drift')
    ranges = dict(name=(name_va, name_va + lens[0]), list=(list_va, list_va + lens[1]),
                  textout=(textout_va, textout_va + lens[2]))
    for e, slot in ((name_entry, 'name'), (item_entry, 'list'), (name_list_entry, 'list'), (t_entry, 'textout')):
        need(ranges[slot][0] <= e < ranges[slot][1], 'Entry outside its slot')
    need(len({name_entry, item_entry, name_list_entry, t_entry}) == 4, 'Entries must be distinct')
    pad = lambda n: b'\xcc' * n
    code = name_code + pad(offs[1] - lens[0]) + list_code + pad(offs[2] - offs[1] - lens[1]) + t_code
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
    need(c4.decode_v4(mvw.read(cat_rva + mv.CAT_HDR, len(blob))) == c4.decode_v4(blob), 'Blob readback decodes identically')
    need(sha(candidate) == before and sha(original) == source_profile.ORIGINAL_SHA256, 'Inputs mutated')
    hx = lambda d: {k: hex(v) for k, v in sorted(d.items())}
    return merged, dict(
        profile=prof['profile'], source_sha256=before, catalog_version=4,
        name_object_sha256=pins['name'], list_object_sha256=pins['list'], textout_object_sha256=pins['textout'],
        rehearsal=rehearsal, textout_rehearsal=rehearsal, handoff_eligible=not rehearsal,
        blob_sha256=sha(blob), capacity=cap, catalog_section=extents, code_sha256=sha(code),
        code_range=[hex(code_va), hex(code_va + code_span)],
        slots=dict(offsets=offs, lengths=lens, align=mm.SLOT_ALIGN),
        entry_va=hex(name_entry), list_item_entry_va=hex(item_entry), list_name_entry_va=hex(name_list_entry),
        textout_entry_va=hex(t_entry),
        name_code_va=hex(name_va), list_code_va=hex(list_va), textout_code_va=hex(textout_va),
        bindings=hx(name_bindings), list_bindings=hx(list_bindings), textout_bindings=hx(textout_bindings),
        name_details=name_details, list_details=list_details, textout_details=t_details,
        original_dlgitem_va=hex(mp.WRAPPER_VA), original_dlgitem_slot_va=hex(C + mv.OFF_DLG),
        list_mode=list_mode, list_mode_slot_va=hex(C + mv.OFF_MODE),
        new_imports=[f'{d}!{a}' for d, a in mv.V3_APIS], import_descriptors=[nbefore, nafter],
        serializer=ser, hook_span_patched=False, list_sites_retargeted=False, textout_sites_patched=False,
        inert=True, file_written=False, production_can_apply=False, release_approved=False)
