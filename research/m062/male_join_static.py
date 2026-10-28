"""m062 lab-only: static audit of the male adventurer two-part join.
Reads the pristine EXE and Mina's draft (both lab-local). Prints/writes COUNTS
ONLY, no source text, so the summary JSON may be published."""
import argparse, collections, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_v3 as c3

ap = argparse.ArgumentParser()
ap.add_argument('--exe', required=True); ap.add_argument('--draft', required=True)
ap.add_argument('--draft-sha', required=True); ap.add_argument('--m051', required=True)
ap.add_argument('--out')
a = ap.parse_args()
original = Path(a.exe).read_bytes(); draft = Path(a.draft).read_bytes(); m051 = Path(a.m051).read_bytes()
rows, stats = c3.verified_rows(original, [(m051, c3.M051_CATALOG), (draft, a.draft_sha)])
look = c3.Lookup(rows)
items = json.loads(draft)['items']
parts = collections.defaultdict(dict)  # (region, kind) -> index -> (ansi, text)
for it in items:
    if it['category'] != 'adventurer':
        continue
    r = c3.adventurer_row(original, it)
    parts[(it['region'], r[0])][it['index']] = (r[2], r[3])
res = collections.Counter(); review = []; max_units = 0; strings = collections.defaultdict(set)
for region in c3.REGIONS:
    firsts, seconds = parts[(region, c3.PREFIX)], parts[(region, c3.SUFFIX)]
    for i, (fa, ft) in firsts.items():
        for j, (sa, st) in seconds.items():
            full, want = fa + sa, ft + st
            res['combinations'] += 1
            strings[full].add(want)
            max_units = max(max_units, len(want.encode('utf-16le')) // 2)
            if len(full) > c3.MAX_ANSI: res['over_64_bytes'] += 1
            ex = look.exact(full)
            if ex is not None:
                res['exact_row_wins'] += 1
                res['exact_row_wins_same_text' if ex == want else 'exact_row_wins_different_text'] += 1
                if ex != want: review.append(dict(region=region, first=i, second=j, reason='exact_row_wins', join_text=want, shown_text=ex))
                continue
            got = look.find(full)
            if got == want: res['join_ok'] += 1
            elif got is None:
                res['join_ambiguous_or_missing'] += 1
                review.append(dict(region=region, first=i, second=j, reason='ambiguous_split_falls_back_to_original', join_text=want))
            else: res['join_wrong_text'] += 1
res['distinct_full_strings'] = len(strings)
res['full_strings_with_conflicting_translations'] = sum(1 for v in strings.values() if len(v) > 1)
v3 = c3.encode_v3(rows)
summary = dict(milestone='m062', production_can_apply=False, release_approved=False,
               note='Counts only; no source text. Lab inputs: pristine EXE + Mina draft (hash below).',
               draft_sha256=a.draft_sha, m051_catalog_sha256=c3.M051_CATALOG, rows_by_category=stats,
               rows_after_dedupe=len(rows), rows_by_kind=dict(collections.Counter(c3.KIND_NAMES[r[0]] for r in rows)),
               v1_capacity=c3.V1_MAX_ROWS, v1_fits=len([r for r in rows if r[0] == c3.FULL_ID]) <= c3.V1_MAX_ROWS,
               v3_bytes=len(v3), v3_sha256=hashlib.sha256(v3).hexdigest(), v3_vs_v1_row_table_bytes=len(rows) * c3.V1_ROW,
               male_join=dict(res, max_joined_utf16_units=max_units), review=review)
text = json.dumps(summary, ensure_ascii=False, indent=1) + '\n'
print(text)
if a.out: Path(a.out).write_text(text, encoding='utf-8')
