"""Static checks for the public, sanitized m062 Mina draft3 (no game files needed)."""
import json, re, unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D2 = ROOT / 'research' / 'm062' / 'draft3'
REGIONS = ('western', 'arabic', 'chinese', 'japanese')
FILES = ['m062-draft3-consumables-tools.zh-TW.json', 'm062-draft3-weapons.zh-TW.json', 'm062-draft3-armor.zh-TW.json'] + \
        [f'm062-draft3-adventurers-{r}.zh-TW.json' for r in REGIONS]
FULL_SHA = 'd0e162f3e31c75552536d6d80849b45ccc720e1cdc7a256f2ed9539836ecde25'
M051_SLOTS = {('primary', s) for s in (0, 1, 2, 3, 5, 7, 9, 11, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 136, 296)}
BLOCKED = {('extended', 28)} | {('extended', s) for s in range(139, 144)}   # Kris byte collision; placeholders
KANA = re.compile(r'[\u3040-\u30ff\uff66-\uff9f]')
HEX64 = re.compile(r'^[0-9a-f]{64}$')


class M062Draft3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {f: json.loads((D2 / f).read_text(encoding='utf-8')) for f in FILES}
        cls.items = [x for d in cls.docs.values() for x in d['items']]

    def test_flags_and_meta(self):
        for f, d in self.docs.items():
            self.assertIs(d['production_can_apply'], False, f)
            self.assertIs(d['release_approved'], False, f)
            self.assertIs(d['rendering_verified'], False, f)
            self.assertIs(d['preview_only'], True, f)
            self.assertEqual(d['lab_full_draft_sha256'], FULL_SHA)
            self.assertEqual(d['item_count'], len(d['items']))
            self.assertEqual(sorted(d['stripped_fields']), ['source_name_cp932_hex', 'source_name_ja'])

    def test_no_japanese_source_fields_or_kana(self):
        for f in FILES:
            text = (D2 / f).read_text(encoding='utf-8')
            for x in json.loads(text)['items']:
                self.assertFalse({'source_name_ja', 'source_name_cp932_hex'} & set(x))
            self.assertIsNone(KANA.search(text), f)
            self.assertNotIn('\r', text)
            self.assertLess(len(text.encode('utf-8')), 400000)

    def test_counts(self):
        self.assertEqual(Counter(x['category'] for x in self.items),
                         {'adventurer': 1400, 'consumable': 55, 'tool': 72, 'weapon': 161, 'armor': 128})
        t = Counter((x['table'], x.get('region')) for x in self.items if x['category'] == 'adventurer')
        for r in REGIONS:
            self.assertEqual((t[('adventurer_male_first', r)], t[('adventurer_male_second', r)], t[('adventurer_female', r)]), (100, 100, 150))
        m = Counter(x.get('translation_method') for x in self.items if x['category'] == 'adventurer')
        self.assertEqual(m, {'kanji_traditionalized': 700, 'curated': 180, 'curated_v2': 122,
                             'join_unified_m062': 15, 'curated_v3': 371, 'machine_translit_draft': 12})
        rs = Counter(x['review_status'] for x in self.items)
        self.assertEqual(rs, {'mina_draft': 72, 'mina_draft2': 1337, 'mina_draft3': 371, 'mina_draft2_label_desc_mismatch': 24, 'machine_needs_review': 12})
        self.assertFalse({'human_reviewed', 'approved'} & set(rs))   # nothing promoted in this batch

    def test_items_no_overlap_unique_blocked(self):
        keys = [(x['table'], x['slot']) for x in self.items if x['category'] != 'adventurer']
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(set(keys) & (M051_SLOTS | BLOCKED))
        adv = [(x['table'], x['region'], x['index']) for x in self.items if x['category'] == 'adventurer']
        self.assertEqual(len(adv), len(set(adv)))

    def test_hashes_and_consistency(self):
        by_src = defaultdict(set)
        for x in self.items:
            self.assertRegex(x['source_name_sha256'], HEX64)
            if x['category'] != 'adventurer':
                self.assertRegex(x['source_record_sha256'], HEX64)
                self.assertRegex(x['source_description_sha256'], HEX64)
                self.assertTrue(x['description_zh_tw'])
            else:
                self.assertIsNone(x['source_record_sha256'])
                self.assertEqual(x['exact_match_usable'], x['table'] == 'adventurer_female')
                self.assertIs(x['ambiguity_blocked'], False)
            by_src[x['source_name_sha256']].add(x['name_zh_tw'])
            try:
                x['name_zh_tw'].encode('cp950'); ok = True
            except UnicodeEncodeError:
                ok = False
            self.assertEqual(ok, x['name_cp950_encodable'])
        self.assertTrue(all(len(v) == 1 for v in by_src.values()))
        self.assertEqual(sum(not x['name_cp950_encodable'] for x in self.items), 8)

    def test_review_summaries_counts_only(self):
        s = json.loads((D2 / 'draft3-review.summary.json').read_text(encoding='utf-8'))
        self.assertIs(s['production_can_apply'], False); self.assertIs(s['release_approved'], False)
        self.assertEqual(s['items_failed'], []); self.assertEqual(s['items_verified_vs_exe'], 416)
        self.assertIs(s['lab_preview']['review_gate']['release_eligible'], False)
        for f in D2.glob('*.summary.json'):
            self.assertIsNone(KANA.search(f.read_text(encoding='utf-8')), f.name)


if __name__ == '__main__':
    unittest.main()
