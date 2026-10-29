"""m063c: enable step for the three v4 helpers, in memory only (no file writer).

Input is an inert v4 image (merge_plan_v4). Same rewrites as enable_plan_m063 (hook span ->
_LD2_NamePair@16, 25 pair5 + 1 tail8 TextOut sites -> @LD2_NameTextOut@24, 18 list sites, PE
CheckSum), except that each list site's rel32 is routed by catalog_v4.LIST_SITE_CLASS:
  * 'item_list' / 'unclassified_list' (shop x4, commission x3) -> @LD2_ListInsertV4@24
      (ALLOW_ANY|ALLOW_JOIN = m062 v3 behaviour)
  * 'name' (tavern + 10 m063 whole-name sites)                -> @LD2_ListInsertNameV4@24
      (ALLOW_ANY|ALLOW_JOIN|NAME_ONLY)
NameTextOut sites are class 'name' and NamePair is 'item_by_id' by construction of the helpers
(flags compiled in), so they need no routing here. Nothing else may differ.
production_can_apply / release_approved stay false.
"""
from pathlib import Path
import struct, sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE))
import site_plan, pe_serializer  # noqa: E402
import enable_plan_m063 as em  # noqa: E402
import catalog_v4 as c4  # noqa: E402

ep, BASE, Refuse, need, sha = em.ep, em.BASE, em.Refuse, em.need, em.sha
ROUTE = {'item_list': 'item', 'unclassified_list': 'item', 'name': 'name'}
EXPECTED_ROUTES = dict(item=7, name=11)


def route_list_sites(rows):
    """rows: em.load_list_sites output -> {'item': [rows], 'name': [rows]}. Refuses any gap/drift."""
    vas = [int(s['va'], 16) for s in rows]
    need(set(vas) == set(c4.LIST_SITE_CLASS), 'LIST_SITE_CLASS must cover exactly the 18 list sites')
    need(c4.SITE_FLAGS['item_list'] == c4.SITE_FLAGS['unclassified_list'] == (c4.ALLOW_ANY | c4.ALLOW_JOIN), 'item flags')
    need(c4.SITE_FLAGS['name'] == (c4.ALLOW_ANY | c4.ALLOW_JOIN | c4.NAME_ONLY), 'name flags')
    need(c4.TEXTOUT_SITE_CLASS == 'name' and c4.NAMEPAIR_SITE_CLASS == 'item_by_id', 'helper classes')
    out = dict(item=[], name=[])
    for s, va in zip(rows, vas):
        cls = c4.LIST_SITE_CLASS[va]
        need(cls in ROUTE, f'List site {va:#x} has no list route ({cls})')
        out[ROUTE[cls]].append(s)
    need({k: len(v) for k, v in out.items()} == EXPECTED_ROUTES, 'List route counts (7 item / 11 name)')
    need(any(int(s['va'], 16) == 0x4b2d1f for s in out['name']), 'Tavern must use the name entry')
    return out


def apply_enabled_v4(inert, name_pair_va, list_item_va, list_name_va, textout_va, code_range, list_manifest, draw_summary):
    need(type(inert) is bytes, 'image')
    entries = (name_pair_va, list_item_va, list_name_va, textout_va)
    for va in entries:
        need(type(va) is int and code_range[0] <= va < code_range[1], 'Helper entry outside .ld2t')
    need(len(set(entries)) == 4, 'Helper entries distinct')
    a, b = ep.HOOK_SPAN
    need(sha(inert[a:b]) == ep.HOOK_SPAN_SHA256, 'Inert hook span must be original')
    routes = route_list_sites(em.load_list_sites(list_manifest))
    lplan = []
    for key, va in (('item', list_item_va), ('name', list_name_va)):
        for o, old, new in site_plan.plan_retarget(inert, routes[key], va):
            lplan.append((o, old, new, key))
    lplan.sort()
    need(len(lplan) == em.EXPECTED_COUNTS['list_sites'], 'Expected 18 list sites')
    tplan = em.plan_textout(inert, textout_va, code_range, draw_summary)
    windows = [(a, b, 'hook')] + [(o, o + 5, f'list@{BASE + o:#x}') for o, _, _, _ in lplan] + \
              [(p['off'], p['off'] + len(p['old']), f"{p['kind']}@{BASE + p['off']:#x}") for p in tplan]
    em.check_disjoint(windows)
    out = bytearray(inert)
    out[a:b] = ep.hook_stub(name_pair_va)
    for o, old, new, key in lplan:
        need(out[o:o + 5] == old and old[0] == 0xE8 == new[0], 'list site bytes')
        tgt = BASE + o + 5 + struct.unpack('<i', new[1:])[0]
        need(tgt == (list_item_va if key == 'item' else list_name_va), 'list route target')
        out[o:o + 5] = new
    for p in tplan:
        n = len(p['old'])
        need(out[p['off']:p['off'] + n] == p['old'] and len(p['new']) == n, 'textout site bytes')
        out[p['off']:p['off'] + n] = p['new']
    co = ep._checksum_offset(out)
    struct.pack_into('<I', out, co, 0)
    struct.pack_into('<I', out, co, pe_serializer.pe_checksum(bytes(out), co))
    out = bytes(out)
    need(len(out) == len(inert), 'size changed')
    changed = [i for i in range(len(inert)) if inert[i] != out[i]]
    allowed = set(range(a, b)) | set(range(co, co + 4)) | {o + k for o, _, _, _ in lplan for k in range(1, 5)} | \
        {p['off'] + k for p in tplan for k in range(len(p['old']))}
    need(set(changed) <= allowed, 'Unexpected byte change outside hook/sites/checksum')
    return out, dict(
        hook_span=[hex(a), hex(b)], hook_stub_sha256=sha(out[a:b]), name_pair_va=hex(name_pair_va),
        list_item_entry_va=hex(list_item_va), list_name_entry_va=hex(list_name_va), textout_entry_va=hex(textout_va),
        sites=[dict(va=hex(BASE + o), old=old.hex(), new=new.hex(), route=key,
                    site_class=c4.LIST_SITE_CLASS[BASE + o]) for o, old, new, key in lplan],
        counts=dict(pair5=sum(p['kind'] == 'pair5' for p in tplan), tail8=sum(p['kind'] == 'tail8' for p in tplan),
                    list_sites=len(lplan), list_item=len(routes['item']), list_name=len(routes['name'])),
        textout_sites=[dict(kind=p['kind'], va=hex(BASE + p['off']), call_va=hex(p['call_va']),
                            old_sha256_8=sha(p['old'])[:8], new=p['new'].hex()) for p in tplan],
        changed_bytes=len(changed), checksum=hex(struct.unpack_from('<I', out, co)[0]), catalog_version=4,
        hook_enabled=True, list_sites_retargeted=True, textout_sites_patched=True,
        file_written=False, production_can_apply=False, release_approved=False)
