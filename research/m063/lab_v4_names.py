"""m063c lab-only: catalog v4 semantics on the real draft (counts only, publishable).
Inputs (lab-local, never committed): pristine Ld95.exe, Mina's full draft, m051 catalog.
Prints/writes COUNTS and hashes only: no source text, no translated names, no blob.
Optional --kris-proposal adds the extended-28 item row with a HYPOTHETICAL text so the
Kris collision can be exercised (historical, before draft5). Since draft5 the real extended-28
row (user decision via Mina) is in the draft and the Kris checks run on it automatically."""
import argparse, collections, hashlib, json, os, shutil, struct, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog_v4 as c4  # noqa: E402
c3 = c4.c3
NAME, LIST, BYID = c4.SITE_FLAGS['name'], c4.SITE_FLAGS['item_list'], c4.SITE_FLAGS['item_by_id']


def kris_rows(original, proposal):
    base, _ = c3.ITEM_TABLES['extended']
    rec = original[base + 216 * 28:base + 216 * 29]
    name = rec[4:40].split(b'\0', 1)[0]
    sid = struct.unpack_from('<i', rec)[0]
    return name, [c4.make_row(c4.FULL_ID, sid, name + s, proposal + s.decode('ascii')) for s in c3.suffixes(original)]


def c_check(blob, cases):
    cc = shutil.which('gcc') or shutil.which('cc')
    if not cc:
        return 'skipped (no C compiler)'
    with tempfile.TemporaryDirectory(prefix='ld2c4lab-') as t:
        exe = os.path.join(t, 'c4')
        subprocess.run([cc, '-std=c99', '-O2', '-o', exe, str(HERE / 'native-v4' / 'catalog_v4_host_test.c')], check=True)
        Path(t, 'b').write_bytes(blob)
        Path(t, 'c').write_text('open 1\n' + ''.join(
            f"{a.hex()} {i} {f} {w.encode('utf-16le').hex() if w else '-'}\n" for a, i, f, w in cases))
        r = subprocess.run([exe, os.path.join(t, 'b'), os.path.join(t, 'c')], capture_output=True, text=True)
        return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else f'error {r.returncode}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True); ap.add_argument('--draft', required=True)
    ap.add_argument('--draft-sha', required=True); ap.add_argument('--m051', required=True)
    ap.add_argument('--kris-proposal'); ap.add_argument('--out')
    a = ap.parse_args()
    original = Path(a.exe).read_bytes(); draft = Path(a.draft).read_bytes(); m051 = Path(a.m051).read_bytes()
    cats = [(m051, c3.M051_CATALOG), (draft, a.draft_sha)]
    rows4, stats = c4.verified_rows(original, cats)
    rows3, _ = c3.verified_rows(original, cats)
    out = dict(milestone='m063c-lab', counts_only=True, production_can_apply=False, release_approved=False,
               draft_sha256=a.draft_sha, m051_catalog_sha256=c3.M051_CATALOG,
               note='Counts only. Full draft + m051 (not the lab_preview subset). No source text or names.')
    kris = None
    if a.kris_proposal:
        kname, krows = kris_rows(original, a.kris_proposal)
        rows4 = c4.dedupe(rows4 + krows)
        kris = (kname, krows)
    elif any(i.get('table') == 'extended' and i.get('slot') == 28 for i in json.loads(draft)['items']):
        # draft5+: the real extended-28 row (Mina/user decision) is in the draft; exercise it the same way
        base, _ = c3.ITEM_TABLES['extended']
        kname = original[base + 216 * 28 + 4:base + 216 * 28 + 40].split(b'\0', 1)[0]
        krows = [r for r in rows4 if r[0] == c4.FULL_ID and r[2] == kname]
        kris = (kname, krows) if krows else None
    l4, l3 = c4.Lookup(rows4), c3.Lookup(rows3)
    blob = c4.encode_v4(rows4)
    out['v4'] = dict(rows=len(rows4), rows_by_kind=dict(collections.Counter(c3.KIND_NAMES[r[0]] for r in rows4)),
                     bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), v3_rows=len(rows3),
                     kris_hypothetical_rows_included=bool(a.kris_proposal), kris_draft_row_included=bool(kris) and not a.kris_proposal)
    items = json.loads(draft)['items']
    parts, female = collections.defaultdict(dict), []
    for it in items:
        if it['category'] != 'adventurer':
            continue
        r = c4.adventurer_row(original, it)
        if r[0] == c4.FULL_ANY:
            female.append((r[2], r[3]))
        else:
            parts[(it['region'], r[0])][it['index']] = (r[2], r[3])
    cases, res3, res4 = [], collections.Counter(), collections.Counter()
    for region in c3.REGIONS:
        for fa, ft in parts[(region, c4.PREFIX)].values():
            for sa, st in parts[(region, c4.SUFFIX)].values():
                full, want = fa + sa, ft + st
                g3, g4 = l3.find(full), l4.find(full, -1, NAME)
                res3['ok' if g3 == want else 'fallback' if g3 is None else 'wrong'] += 1
                res4['ok' if g4 == want else 'fallback' if g4 is None else 'wrong'] += 1
                cases.append((full, -1, NAME, g4))
    out['male_join_40000'] = dict(v3_list_flags=dict(res3), v4_name_only=dict(res4))
    f3, f4 = collections.Counter(), collections.Counter()
    for ansi, want in female:
        g3, g4 = l3.find(ansi), l4.find(ansi, -1, NAME)
        f3['ok' if g3 == want else 'fallback' if g3 is None else 'wrong'] += 1
        f4['ok' if g4 == want else 'fallback' if g4 is None else 'wrong'] += 1
        cases.append((ansi, -1, NAME, g4))
    out['female_600'] = dict(v3_list_flags=dict(f3), v4_name_only=dict(f4))
    it = collections.Counter()
    for kind, ident, ansi, text, _ in rows4:
        if kind != c4.FULL_ID:
            continue
        g_id, g_list = l4.find(ansi, ident, BYID), l4.find(ansi, -1, LIST)
        it['rows'] += 1
        it['by_id_ok'] += g_id == text
        if kris and ansi.startswith(kris[0]) and ansi[len(kris[0]):] in {s for s in c3.suffixes(original)}:
            it['kris_list_rows'] += 1
            it['kris_list_shows_item'] += g_list == text
        else:
            it['list_same_as_v3'] += g_list == l3.find(ansi)
        g_name = l4.find(ansi, -1, NAME)
        it['name_only_returns_item_text'] += g_name == text   # must be 0: names never read full_id
        it['name_only_hits_a_name'] += g_name is not None       # item bytes that are also a name
        cases += [(ansi, ident, BYID, g_id), (ansi, -1, LIST, g_list)]
    out['items_full_id'] = dict(it)
    if kris:
        fem = [w for f, w in female if f == kris[0]]
        out['kris'] = dict(female_rows_same_bytes=len(fem),
                           name_site_shows_female=bool(fem) and l4.find(kris[0], -1, NAME) == fem[0],
                           item_by_id_shows_item=l4.find(kris[0], kris[1][0][1], BYID) == kris[1][0][3],
                           v3_name_site_would_show_item=c3.Lookup([r[:4] for r in rows4]).find(kris[0]) == kris[1][0][3])
    out['c_core_cross_check'] = dict(cases=len(cases), result=c_check(blob, cases))
    text = json.dumps(out, ensure_ascii=False, indent=1) + '\n'
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
