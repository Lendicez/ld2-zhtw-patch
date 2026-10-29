"""m062: v3 merge plan — NamePair v3 + ListInsertV3 sharing ONE v3 catalog blob, in memory only.

Lab/research only. production_can_apply=false, release_approved=false. No file writer.

Layout of the new sections (appended after m045's last section, same as m061b):
  .ld2t  [name_pair_v3 code][int3 pad to 16][list_insert_v3 code]
  .ld2c  +0  CatalogBytes (u32, == len(blob))      <- _LD2_CatalogBytes (both helpers)
         +4  ExpectedTextOutA = 0x4e13d7           <- _LD2_ExpectedTextOutA (NamePair)
         +8  OriginalDlgItem  = 0x4ea671 (non-zero) <- _LD2_OriginalDlgItem (list)
         +12 ListMode (0/1/2)                      <- _LD2_ListMode (list)
         +16 v3 blob 'LD2C' (header+rows+pool)     <- _LD2_Catalog (both helpers)
  .ld2i  import fragment (existing descriptors + GDI32!TextOutW + 5 USER32 *W APIs)

Gates (all refuse = raise Refuse; nothing is built half-way):
  * both objects hash-locked (rehearse_v3_objs.*_SHA256) and exact undefined/public sets;
  * catalog review gate (review_gate): replaces m060.reviewed_catalog's len==24 rule;
  * capacity gate (capacity_gate): rows <= 8192, pool <= 1 MiB, blob decodes, the .ld2c
    section (16 + blob) fits pe_serializer.MAX_SECTION_BYTES and the planned RVA/raw
    extents (VirtualSize/RawSize, file alignment) — refuse rather than truncate;
  * OriginalDlgItem slot must read back non-zero (== CWnd::SendDlgItemMessage 0x4ea671).
"""
from pathlib import Path
import hashlib, json, struct, sys
HERE = Path(__file__).resolve().parent
M061 = HERE.parent / 'm061'
sys.path.insert(0, str(M061))
sys.path.insert(0, str(HERE))
import source_profile, import_builder, pe_serializer, coff_obj  # noqa: E402
import merge_plan as mp  # noqa: E402  (m061 constants: hook span, IAT slots, API sets)
import catalog_v3 as c3  # noqa: E402

NAME_V3_OBJECT_SHA256 = '8a70e6cde5254d65aae4bf9d65fce6ee2b8065807af5741bc7092f37776c0242'
LIST_V3_OBJECT_SHA256 = '5ceba5a64b6e43d8f0f2e519cd91c076280656c7c1d1dd52c0f7025a62c3a037'
NAME_V3_ENTRY = '_LD2_NamePair@16'
LIST_V3_ENTRY = '@LD2_ListInsertV3@24'
SECURITY = frozenset({'___security_cookie', '@__security_check_cookie@4'})
NAME_V3_UNDEFINED = frozenset({'_LD2_CatalogBytes', '_LD2_Catalog', '_LD2_ExpectedTextOutA', '_LD2_TextOutW'}) | SECURITY
LIST_V3_UNDEFINED = (mp.LIST_U_UNDEFINED - {'_LD2_EntryCount', '_LD2_Entries'}) | {'_LD2_CatalogBytes', '_LD2_Catalog'}
V3_APIS = mp.LIST_U_APIS
CAT_HDR = 16                 # policy words before the blob (keeps blob 16-byte aligned)
OFF_BYTES, OFF_EXPECTED, OFF_DLG, OFF_MODE = 0, 4, 8, 12
V3_BLOB_MAX = c3.V3_HEADER + c3.V3_MAX_ROWS * c3.V3_ROW + c3.V3_MAX_POOL   # what ld2c3_open accepts
SECTION_BUDGET = pe_serializer.MAX_SECTION_BYTES                          # what the serializer accepts

# ---------------------------------------------------------------- review gate
M051_SHA = c3.M051_CATALOG
NAME_STATUS_OK = frozenset({'translated', 'identity_preserved'})
REVIEW_OK = frozenset({'human_reviewed', 'approved'})          # release-eligible review states
REVIEW_LAB_PREVIEW = REVIEW_OK | {'mina_draft'}                 # lab-only preview, never release
POLICIES = {'reviewed': REVIEW_OK, 'lab_preview': REVIEW_LAB_PREVIEW}


class Refuse(source_profile.Refuse):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def align(v, n=16):
    return (v + n - 1) // n * n


def review_gate(catalogs, policy='reviewed'):
    """catalogs: [(raw_json_bytes, pinned_sha256)]. Replaces the m060 `len(items)==24` rule.

    Every item of every catalog must pass (catalog-level, no silent filtering):
      * name_status in {translated, identity_preserved};
      * review_status in POLICIES[policy]. The pinned m051 catalog predates review_status
        and is the reviewed baseline: items without the field are accepted ONLY there.
    Returns a summary; 'lab_preview' marks the build release-ineligible."""
    need(policy in POLICIES, 'Unknown review policy')
    ok = POLICIES[policy]
    summary = dict(policy=policy, catalogs=[], release_eligible=(policy == 'reviewed'))
    for raw, pinned in catalogs:
        need(type(raw) is bytes and sha(raw) == pinned, 'Catalog hash pin')
        cat = json.loads(raw)
        need(cat.get('production_can_apply') is False and cat.get('release_approved', False) is False, 'Catalog boundary flags')
        items = cat.get('items')
        need(isinstance(items, list) and items, 'Catalog items')
        counts = {}
        for it in items:
            need(it.get('name_status') in NAME_STATUS_OK, 'name_status not reviewable')
            rs = it.get('review_status')
            if rs is None:
                need(pinned == M051_SHA, 'review_status missing outside the pinned m051 baseline')
                rs = 'm051_baseline'
            else:
                need(rs in ok, f'review_status {rs!r} not allowed by policy {policy!r}')
                if rs not in REVIEW_OK:
                    summary['release_eligible'] = False
            counts[rs] = counts.get(rs, 0) + 1
        summary['catalogs'].append(dict(sha256=pinned, items=len(items), review_status=counts))
    return summary


def build_blob(original, catalogs, policy='reviewed'):
    review = review_gate(catalogs, policy)
    rows, stats = c3.verified_rows(original, catalogs)
    blob = c3.encode_v3(rows)
    return blob, dict(review=review, rows=len(rows), row_stats=stats)


# ---------------------------------------------------------------- capacity gate
def capacity_gate(blob, section_budget=SECTION_BUDGET):
    """Refuse (never truncate) when the v3 blob cannot be carried by .ld2c."""
    need(type(blob) is bytes and len(blob) >= c3.V3_HEADER, 'v3 blob shape')
    rows = c3.decode_v3(blob)                                  # header/extents/order/strict text
    need(1 <= len(rows) <= c3.V3_MAX_ROWS, 'v3 row capacity (<=8192)')
    pool = struct.unpack_from('<I', blob, 24)[0]
    need(pool <= c3.V3_MAX_POOL, 'v3 pool capacity (<=1 MiB)')
    need(len(blob) <= V3_BLOB_MAX, 'v3 blob exceeds helper ld2c3_open limit')
    section = CAT_HDR + len(blob)
    need(section <= section_budget, f'.ld2c section {section} B exceeds budget {section_budget} B')
    return dict(rows=len(rows), blob_bytes=len(blob), pool_bytes=pool, section_bytes=section,
                section_budget=section_budget, headroom_bytes=section_budget - section,
                helper_blob_max=V3_BLOB_MAX)


def check_section_extents(merged, cat_rva, catalog):
    """Read back the .ld2c header from the merged image: VirtualSize/RawSize/file alignment."""
    p = pe_serializer.parse(merged)
    hit = [s for s in p['sections'] if s['va'] == cat_rva]
    need(len(hit) == 1, '.ld2c section located once')
    s = hit[0]
    need(s['vs'] == len(catalog), '.ld2c VirtualSize == catalog bytes')
    need(s['rs'] >= len(catalog) and s['rs'] % p['file_align'] == 0 and s['rp'] % p['file_align'] == 0, '.ld2c RawSize/file alignment')
    need(s['rp'] + s['rs'] <= len(merged), '.ld2c raw extent inside file')
    need(merged[s['rp']:s['rp'] + len(catalog)] == catalog, '.ld2c readback')
    need(merged[s['rp'] + len(catalog):s['rp'] + s['rs']] == b'\0' * (s['rs'] - len(catalog)), '.ld2c tail zero')
    return dict(virtual_size=s['vs'], raw_size=s['rs'], raw_pointer=hex(s['rp']), file_align=p['file_align'])


# ---------------------------------------------------------------- merge
def build_inert_v3(original, candidate, name_obj, list_obj, blob, list_mode=mp.DEFAULT_LIST_MODE):
    """Inert v3 image (hook span + list sites untouched). Returns (image, report)."""
    need(type(list_mode) is int and list_mode in mp.LIST_MODES, 'List mode')
    need(sha(name_obj) == NAME_V3_OBJECT_SHA256, 'name_pair_v3 object sha256 not locked')
    need(sha(list_obj) == LIST_V3_OBJECT_SHA256, 'list_insert_v3 object sha256 not locked')
    cap = capacity_gate(blob)
    prof = source_profile.derive(original, candidate)
    before = sha(candidate)
    base = 0x400000
    need(struct.unpack_from('<I', candidate, 0x3c)[0] == 0xf0, 'PE offset')
    need(sha(candidate[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]]) == mp.HOOK_SPAN_SHA256, 'Hook span hash')
    view = import_builder.View(candidate)
    need(view.dirs[13] == (0x192c7c, 64) and sha(view.read(0x192c7c, 64)) == mp.DELAY_DESCRIPTOR_SHA256, 'Delay descriptor passthrough')
    need(mp.iat_name(view, mp.GETDLGITEM_IAT_VA - base) == ('USER32.dll', 'GetDlgItem'), 'GetDlgItem IAT slot')
    need(mp.iat_name(view, mp.MULTIBYTETOWIDECHAR_IAT_VA - base) == ('KERNEL32.dll', 'MultiByteToWideChar'), 'MultiByteToWideChar IAT slot')
    need(mp.WRAPPER_VA != 0, 'OriginalDlgItem must be non-zero')

    catalog = struct.pack('<IIII', len(blob), mp.TEXTOUTA_HELPER_VA, mp.WRAPPER_VA, list_mode) + blob
    need(len(catalog) == cap['section_bytes'], 'catalog layout')

    lay = lambda raw: coff_obj.layout(coff_obj.parse(raw))[1]
    name_len, list_len = lay(name_obj), lay(list_obj)
    code_span = align(name_len) + list_len
    code_rva, cat_rva, imp_rva = pe_serializer.plan_rvas(candidate, [code_span, len(catalog), 0x1000])
    need(cat_rva >= code_rva + code_span and imp_rva >= cat_rva + len(catalog), 'Planned sections overlap')
    frag, dsize, iats, nbefore, nafter = import_builder.extend(candidate, imp_rva, list(V3_APIS))

    C = base + cat_rva
    shared = {'_LD2_CatalogBytes': C + OFF_BYTES, '_LD2_Catalog': C + CAT_HDR,
              '___security_cookie': mp.COOKIE_VA, '@__security_check_cookie@4': mp.CHECK_COOKIE_VA}
    name_bindings = dict(shared, **{'_LD2_ExpectedTextOutA': C + OFF_EXPECTED,
                                    '_LD2_TextOutW': base + iats[('GDI32.dll', 'TextOutW')]})
    list_bindings = dict(shared, **{
        '_LD2_OriginalDlgItem': C + OFF_DLG, '_LD2_ListMode': C + OFF_MODE,
        '_LD2_SendDlgItemMessageW': base + iats[('USER32.dll', 'SendDlgItemMessageW')],
        '_LD2_MultiByteToWideChar': mp.MULTIBYTETOWIDECHAR_IAT_VA, '_LD2_GetDlgItem': mp.GETDLGITEM_IAT_VA,
        '_LD2_IsWindowUnicode': base + iats[('USER32.dll', 'IsWindowUnicode')],
        '_LD2_GetWindowLongW': base + iats[('USER32.dll', 'GetWindowLongW')],
        '_LD2_GetClassLongW': base + iats[('USER32.dll', 'GetClassLongW')],
        '_LD2_SetWindowLongW': base + iats[('USER32.dll', 'SetWindowLongW')]})
    name_va = base + code_rva
    list_va = name_va + align(name_len)
    name_code, name_entry, name_details = coff_obj.relocate(
        name_obj, name_va, name_bindings, expected_sha256=NAME_V3_OBJECT_SHA256,
        expected_undefined=NAME_V3_UNDEFINED, entry=NAME_V3_ENTRY)
    list_code, list_entry, list_details = coff_obj.relocate(
        list_obj, list_va, list_bindings, expected_sha256=LIST_V3_OBJECT_SHA256,
        expected_undefined=LIST_V3_UNDEFINED, entry=LIST_V3_ENTRY)
    need(len(name_code) == name_len and len(list_code) == list_len, 'Code length drift')
    code = name_code + b'\xcc' * (align(name_len) - name_len) + list_code

    merged, ser = pe_serializer.append_sections(candidate, [
        dict(name='.ld2t', rva=code_rva, data=code, characteristics=pe_serializer.SCN_CODE_RX),
        dict(name='.ld2c', rva=cat_rva, data=catalog, characteristics=pe_serializer.SCN_RDATA_R),
        dict(name='.ld2i', rva=imp_rva, data=frag, characteristics=pe_serializer.SCN_DATA_RW),
    ], {1: (imp_rva, dsize)})
    need(merged[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]] == candidate[mp.HOOK_SPAN[0]:mp.HOOK_SPAN[1]], 'Hook span must stay original (inert)')
    after = import_builder.imports(import_builder.View(merged), (imp_rva, dsize))
    need(import_builder.semantic(after[:nbefore]) == import_builder.semantic(import_builder.imports(view, view.dirs[1])), 'Merged import semantics')
    extents = check_section_extents(merged, cat_rva, catalog)
    mv = import_builder.View(merged)
    dlg = struct.unpack('<I', mv.read(cat_rva + OFF_DLG, 4))[0]
    need(dlg == mp.WRAPPER_VA and dlg != 0, 'OriginalDlgItem slot must read back non-zero (0x4ea671)')
    need(struct.unpack('<I', mv.read(cat_rva + OFF_BYTES, 4))[0] == len(blob), 'CatalogBytes readback')
    need(c3.decode_v3(mv.read(cat_rva + CAT_HDR, len(blob))) == c3.decode_v3(blob), 'Blob readback decodes identically')
    need(sha(candidate) == before and sha(original) == source_profile.ORIGINAL_SHA256, 'Inputs mutated')
    hx = lambda d: {k: hex(v) for k, v in sorted(d.items())}
    return merged, dict(
        profile=prof['profile'], source_sha256=before,
        name_object_sha256=NAME_V3_OBJECT_SHA256, list_object_sha256=LIST_V3_OBJECT_SHA256,
        blob_sha256=sha(blob), capacity=cap, catalog_section=extents, code_sha256=sha(code),
        entry_va=hex(name_entry), list_entry_va=hex(list_entry),
        name_code_va=hex(name_va), list_code_va=hex(list_va),
        bindings=hx(name_bindings), list_bindings=hx(list_bindings),
        name_details=name_details, list_details=list_details,
        original_dlgitem_va=hex(mp.WRAPPER_VA), original_dlgitem_slot_va=hex(C + OFF_DLG),
        list_mode=list_mode, list_mode_slot_va=hex(C + OFF_MODE),
        new_imports=[f'{d}!{a}' for d, a in V3_APIS], import_descriptors=[nbefore, nafter],
        serializer=ser, hook_span_patched=False, list_sites_retargeted=False, inert=True,
        file_written=False, production_can_apply=False, release_approved=False)
