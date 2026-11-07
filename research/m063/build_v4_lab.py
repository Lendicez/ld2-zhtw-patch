"""m063d lab-only: build the v4 three-helper inert + enabled images IN MEMORY from m045 with the m063b
MSVC objects (pinned; audited 2026-10-31) and verify them statically. Writes only JSON to stdout
(deltas for the Win11 handoff come from make_v4_delta.py). Never writes an EXE.
production_can_apply=false, release_approved=false.

Catalog policies:
  reviewed     m051 (264 rows) only                         -> release-eligible catalog, few visible names
  lab_preview  m051 + m063d v4 lab_preview (1817 rows, Kris) -> release-INELIGIBLE, lab observation only
Inputs (lab-local, never committed): LAB/baseline/pristine/Ld95.exe, LAB/runs/m045/build-first/Ld95.exe,
  $LD2_M063B_RETURN/{name_pair_v4,list_insert_v4,name_textout_v4}.obj (default ROOT/m063b-return),
  $LD2_M063D_PREVIEW (default ROOT/zhTW_lab/research/m063/lab-v4/m063-draft5-v4-lab-preview.zh-TW.json).

  ~/venv-ld2/bin/python -I -B build_v4_lab.py [--catalog reviewed|lab_preview] [--modes 2,0]
"""
import argparse, collections, hashlib, json, os, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import build_v3_lab as b3, build_enabled_lab as bl  # noqa: E402
import build_m063_lab as bm  # noqa: E402
import merge_plan_v4 as m4, enable_plan_v4 as e4, catalog_v4 as c4, rehearse_v4_objs as rv4  # noqa: E402
import import_builder as ib, pe_serializer  # noqa: E402
import pefile  # noqa: E402

LAB = HERE.parents[1]; ROOT = LAB.parent
BASE = 0x400000
OBJ_DIR = Path(os.environ.get('LD2_M063B_RETURN', ROOT / 'm063b-return'))
PREVIEW = Path(os.environ.get('LD2_M063D_PREVIEW', ROOT / 'zhTW_lab/research/m063/lab-v4/m063-draft5-v4-lab-preview.zh-TW.json'))
PREVIEW_SHA = 'fe9d11034a6339542ce6d36c32c587564c8f1db1b87f7cf00f59d760c636d5e8'   # build_lab_preview_v4.py output (1817 rows)
MANIFEST = HERE.parent / 'm061/list_sites.json'
SUMMARY = HERE.parent / 'm062/name_draw_sites.summary.json'
OBJ_NAMES = ('name_pair_v4', 'list_insert_v4', 'name_textout_v4')
KRIS = ('extended', 28)


def sha(b): return hashlib.sha256(b).hexdigest()


def inputs(catalog='reviewed'):
    o = (LAB / 'baseline/pristine/Ld95.exe').read_bytes()
    m = (LAB / 'runs/m045/build-first/Ld95.exe').read_bytes()
    objs = [(OBJ_DIR / f'{k}.obj').read_bytes() for k in OBJ_NAMES]
    for k, raw in zip(OBJ_NAMES, objs):
        assert sha(raw) == rv4.PINS[k], f'{k}: not the pinned m063b MSVC object'
    cats = [(b3.M051.read_bytes(), b3.mv.M051_SHA)]
    if catalog == 'lab_preview':
        raw = PREVIEW.read_bytes()
        assert sha(raw) == PREVIEW_SHA, 'v4 lab_preview pin'
        cats.append((raw, PREVIEW_SHA))
    review = b3.mv.review_gate(cats, catalog)
    rows, stats = c4.verified_rows(o, cats)
    blob = c4.encode_v4(rows)
    return o, m, objs, blob, dict(policy=catalog, review=review, rows=len(rows),
                                  rows_by_kind=dict(collections.Counter(c4.c3.KIND_NAMES[r[0]] for r in rows))), cats


def build(mode, pre):
    o, m, objs, blob, binfo, _ = pre
    inert, rep = m4.build_inert_v4(o, m, *objs, blob, list_mode=mode)        # no rehearsal pins: locked MSVC pins
    assert rep['handoff_eligible'] and not rep['rehearsal']
    cr = tuple(int(x, 16) for x in rep['code_range'])
    va = [int(rep[k], 16) for k in ('entry_va', 'list_item_entry_va', 'list_name_entry_va', 'textout_entry_va')]
    en, erep = e4.apply_enabled_v4(inert, *va, cr, MANIFEST.read_bytes(), SUMMARY.read_bytes())
    rep['catalog_build'] = binfo
    return inert, rep, en, erep


def windows(erep):
    """Byte windows of the existing image that the enable step may rewrite (file offset = RVA here)."""
    a, b = e4.ep.HOOK_SPAN
    w = [(a, b, 'hook')]
    w += [(int(s['va'], 16) - BASE + 1, int(s['va'], 16) - BASE + 5, 'list_' + s['route']) for s in erep['sites']]
    w += [(int(t['va'], 16) - BASE, int(t['va'], 16) - BASE + len(bytes.fromhex(t['new'])), t['kind']) for t in erep['textout_sites']]
    return sorted(w)


def verify(o, m, inert, rep, en, erep, objs):
    r = {}
    # m061 checks (hook stub, site disasm old->new, pefile, slot values), once per list route
    for route, key in (('item', 'list_item_entry_va'), ('name', 'list_name_entry_va')):
        rr = dict(rep, list_entry_va=rep[key])
        er = dict(erep, sites=[s for s in erep['sites'] if s['route'] == route])
        v = bl.verify(o, inert, rr, en, er)
        assert not v['branches_into_span_interior'], v['branches_into_span_interior']
        r[f'sites_{route}'] = v['sites']
        r.update({k: v[k] for k in ('hook_stub_disasm', 'pefile_checksum_ok', 'sections', 'import_count', 'entry_point',
                                     'size_of_image', 'original_dlgitem_slot_value', 'expected_textouta_value')})
    assert len(r['sites_item']) == 7 and len(r['sites_name']) == 11
    assert any(s['va'] == '0x4b2d1f' for s in r['sites_name']), 'tavern must use the name entry'
    no, lo, to = objs
    cv = lambda d: {k: int(x, 16) for k, x in d.items()}
    r['fixups_name'] = b3.fixup_audit(en, no, int(rep['name_code_va'], 16), cv(rep['bindings']))
    r['fixups_list'] = b3.fixup_audit(en, lo, int(rep['list_code_va'], 16), cv(rep['list_bindings']))
    r['fixups_textout'] = b3.fixup_audit(en, to, int(rep['textout_code_va'], 16), cv(rep['textout_bindings']))
    r['binding_targets'] = b3.binding_targets(en, rep)
    r['indirect_calls'] = b3.indirect_calls(en, rep)
    ts = bm.textout_site_checks(o, inert, en, rep, erep)
    assert not ts['branch_hits'], ts['branch_hits']
    r['textout_site_windows'] = ts['windows']; r['textout_abs_dword_hits'] = ts['abs_dword_hits']
    r['object_audits'] = rv4.rehearse(dict(list_insert_v4=lo, name_textout_v4=to, name_pair_v4=no))
    assert all(r['object_audits']['matches_m063b_pins'].values())
    pe = pefile.PE(data=en)
    assert pe.verify_checksum()
    imps = {(d.dll.decode(), (i.name or b'').decode()) for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports}
    base = {(d.dll.decode(), (i.name or b'').decode()) for d in pefile.PE(data=o).DIRECTORY_ENTRY_IMPORT for i in d.imports}
    new = sorted(f'{a}!{b}' for a, b in imps - base)
    bad = [x for x in new if x.split('!')[1] in ('SetWindowLongA', 'CallWindowProcW', 'CallWindowProcA', 'SetWindowsHookExW',
           'SetWindowsHookExA', 'VirtualProtect', 'LoadLibraryW', 'LoadLibraryA', 'GetProcAddress', 'SetClassLongW', 'SetClassLongA')]
    assert not bad, bad
    r['new_imports_vs_pristine'] = new
    # inert really is inert (vs m045) and enabled differs from inert only inside the windows + PE CheckSum
    w = windows(erep)
    body = [i for i in range(0x1000, len(m)) if inert[i] != m[i]]
    assert not body, f'inert changed {len(body)} m045 body bytes'
    r['inert_vs_m045_body_changed_bytes'] = 0
    co = e4.ep._checksum_offset(en)
    allowed = {i for a, b, _ in w for i in range(a, b)} | set(range(co, co + 4))
    diff = [i for i in range(len(en)) if en[i] != inert[i]]
    assert set(diff) <= allowed and len(en) == len(inert)
    for a, b, _ in w:
        assert inert[a:b] == m[a:b], 'inert window must equal m045 bytes'
    r['enable_windows'] = len(w)
    r['inert_to_enabled_changed_bytes'] = len(diff)
    r['checksum_offset'] = co
    r['checksum_inert'] = hex(struct.unpack_from('<I', inert, co)[0])
    r['checksum_enabled'] = hex(struct.unpack_from('<I', en, co)[0])
    # catalog readback: the blob inside the image decodes to the same rows
    view = ib.View(en)
    cat_va = int(rep['list_bindings']['_LD2_Catalog'], 16)
    blob = view.read(cat_va - BASE, rep['capacity']['blob_bytes'])
    assert sha(blob) == rep['blob_sha256']
    r['catalog_rows_readback'] = len(c4.decode_v4(blob))
    return r


def semantics(o, cats, blob):
    """Kris/NAME_ONLY spot checks on the blob actually merged (counts/booleans only, no text)."""
    rows = c4.decode_v4(blob)
    lk = c4.Lookup(rows)
    base, _ = c4.c3.ITEM_TABLES['extended']
    rec = o[base + 216 * 28:base + 216 * 29]
    kname, kid = rec[4:40].split(b'\0', 1)[0], struct.unpack_from('<i', rec)[0]
    item = [r for r in rows if r[0] == c4.FULL_ID and r[2] == kname]
    fem = [r for r in rows if r[0] == c4.FULL_ANY and r[2] == kname]
    out = dict(kris_item_rows=len(item), kris_female_rows=len(fem))
    if item and fem:
        out.update(name_site_shows_female=lk.find(kname, -1, c4.SITE_FLAGS['name']) == fem[0][3],
                   item_by_id_shows_item=lk.find(kname, kid, c4.SITE_FLAGS['item_by_id']) == item[0][3],
                   item_list_shows_item=lk.find(kname, -1, c4.SITE_FLAGS['item_list']) == item[0][3])
        assert out['name_site_shows_female'] and out['item_by_id_shows_item']
    return out


def run(catalog, modes):
    pre = inputs(catalog)
    o, m, objs, blob, binfo, cats = pre
    out = dict(milestone='m063d', catalog=catalog, base='m045', base_sha256=sha(m),
               objects={k: rv4.PINS[k] for k in OBJ_NAMES}, production_can_apply=False, release_approved=False,
               release_eligible_catalog=binfo['review']['release_eligible'], modes={})
    out['catalog_build'] = binfo
    out['blob_sha256'] = sha(blob)
    out['semantics'] = semantics(o, cats, blob)
    built = {}
    for mode in modes:
        inert, rep, en, erep = build(mode, pre)
        v = verify(o, m, inert, rep, en, erep, objs)
        out['capacity'] = rep['capacity']; out['catalog_section'] = rep['catalog_section']
        out['modes'][str(mode)] = dict(
            inert_sha256=sha(inert), enabled_sha256=sha(en), size=len(en), size_of_image=v['size_of_image'],
            entry_va=rep['entry_va'], list_item_entry_va=rep['list_item_entry_va'], list_name_entry_va=rep['list_name_entry_va'],
            textout_entry_va=rep['textout_entry_va'], code_range=rep['code_range'], code_sha256=rep['code_sha256'],
            list_mode_slot_va=rep['list_mode_slot_va'], original_dlgitem_slot_va=rep['original_dlgitem_slot_va'],
            hook_stub_sha256=erep['hook_stub_sha256'], counts=erep['counts'], handoff_eligible=rep['handoff_eligible'],
            verify=v)
        built[mode] = (inert, rep, en, erep)
    return out, pre, built


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default='reviewed', choices=sorted(b3.mv.POLICIES))
    ap.add_argument('--modes', default='2,0')
    a = ap.parse_args()
    out, _, _ = run(a.catalog, [int(x) for x in a.modes.split(',')])
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
