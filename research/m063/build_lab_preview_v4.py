"""m063d lab-only: v4 lab_preview catalog = the m062 draft5 v3 lab_preview subset (Mona policy, 1816 rows)
PLUS the one row v3 had to exclude: extended/28 Kris (user_decided, 波刃短劍). v4 NAME_ONLY keeps the item
row and the female name with the same CP932 bytes apart, so v4 needs no exclusion.

Reads lab-local files only (both contain Japanese source fields; never committed) and writes ONE lab-local
JSON at --out (refused inside a git checkout). Prints counts/hashes only. No EXE is read or written here.
production_can_apply=false, release_approved=false; review_status of every row stays 'mina_draft'
(lab-only preview status, never release). Same transform as the draft5 v3 subset:
  * review_status -> 'mina_draft', original kept in mina_review_status
  * description: hiragana U+304F -> bopomofo U+3111 (same shape, CP950-encodable; same edit as the public JSON)
  * collision_note: the Japanese name is replaced by its row key (adventurer_female/western/92)

  ~/venv-ld2/bin/python -I -B build_lab_preview_v4.py --v3-preview P --v3-preview-sha H \
      --full F --full-sha H --out OUT.json
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

KRIS = ('extended', 28)
V3_PREVIEW_SHA = '5ed26c16'          # prefix recorded in m062/draft3/REVIEW (draft5 v3 subset, 1816 rows)
FULL_SHA = 'f896db35'                # prefix of the Mona full draft5 lab file (1817 rows)


def sha(b): return hashlib.sha256(b).hexdigest()


def key(it): return (it['category'], it.get('table'), it.get('slot'), it.get('region'), it.get('index'))


def build(v3raw, fullraw):
    v3, full = json.loads(v3raw), json.loads(fullraw)
    for d in (v3, full):
        assert d['production_can_apply'] is False and d.get('release_approved', False) is False and d['preview_only'] is True
    assert len(v3['items']) == 1816 and len(full['items']) == 1817
    assert {i['review_status'] for i in v3['items']} == {'mina_draft'}
    fk = [key(i) for i in full['items']]
    missing = [k for k in fk if k not in {key(i) for i in v3['items']}]
    assert missing == [('weapon',) + KRIS + (None, None)], missing
    kris = dict(next(i for i in full['items'] if (i.get('table'), i.get('slot')) == KRIS))
    assert kris['review_status'] == 'user_decided' and kris['name_zh_tw'] == '\u6ce2\u5203\u77ed\u528d'   # 波刃短劍
    assert '\u304f' in kris['description_zh_tw']
    kris['description_zh_tw'] = kris['description_zh_tw'].replace('\u304f', '\u3111')
    ja = kris['source_name_ja']
    assert ja in kris['collision_note']
    kris['collision_note'] = kris['collision_note'].replace(ja, 'adventurer_female/western/92', 1)
    kris['mina_review_status'] = kris['review_status']; kris['review_status'] = 'mina_draft'
    pos = fk.index(key(kris))
    items = list(v3['items']); items.insert(pos, kris)
    assert [key(i) for i in items] == fk
    out = dict({k: v for k, v in v3.items() if k != 'items'}, milestone='m063d-draft5-v4-lab-preview-mona',
               note='Mona v4 lab_preview: m062 draft5 v3 lab_preview subset (1816) + extended/28 Kris (user_decided -> mina_draft). '
                    'v4 NAME_ONLY separates the item row from the female name with the same bytes, so v4 excludes nothing. '
                    'Lab-only preview status, never release. Lab-local; contains JA source fields.',
               v3_lab_preview_sha256=sha(v3raw), mona_full_sha256=sha(fullraw), items=items)
    return (json.dumps(out, ensure_ascii=False, indent=1) + '\n').encode(), pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v3-preview', type=Path, required=True); ap.add_argument('--v3-preview-sha', required=True)
    ap.add_argument('--full', type=Path, required=True); ap.add_argument('--full-sha', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    v3raw, fullraw = a.v3_preview.read_bytes(), a.full.read_bytes()
    assert sha(v3raw) == a.v3_preview_sha and a.v3_preview_sha.startswith(V3_PREVIEW_SHA), 'v3 preview pin'
    assert sha(fullraw) == a.full_sha and a.full_sha.startswith(FULL_SHA), 'full draft pin'
    raw, pos = build(v3raw, fullraw)
    probe = a.out.resolve().parent
    assert subprocess.run(['git', '-C', str(probe), 'rev-parse'], capture_output=True).returncode != 0, \
        f'{probe} is inside a git checkout; the lab preview must stay lab-local'
    a.out.write_bytes(raw)
    print(json.dumps(dict(milestone='m063d', items=1817, kris_index=pos, sha256=sha(raw),
                          production_can_apply=False, release_approved=False), indent=1))


if __name__ == '__main__':
    main()
