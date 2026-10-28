"""Static checks for the public, sanitized m061 translation draft (no game files needed)."""
import json, re, unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TR = ROOT / 'research' / 'translations'
REGIONS = ('western', 'arabic', 'chinese', 'japanese')
FILES = ['m061-draft-consumables-tools.zh-TW.json'] + [f'm061-draft-adventurers-{r}.zh-TW.json' for r in REGIONS]
FULL_SHA = '477edfbaa16fb8ca74672fcec8006986fbd90f49dae7bd89fc95702454e14ec1'
M051_SLOTS = {('primary', s) for s in (0, 1, 2, 3, 5, 7, 9, 11, 15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 136, 296)}
KANA = re.compile(r'[\u3040-\u30ff\uff66-\uff9f]')
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def load():
    return {f: json.loads((TR / f).read_text(encoding='utf-8')) for f in FILES}


class M061TranslationDraft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = load()
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
            text = (TR / f).read_text(encoding='utf-8')
            for x in json.loads(text)['items']:
                self.assertFalse({'source_name_ja', 'source_name_cp932_hex'} & set(x))
            self.assertIsNone(KANA.search(text), f)
            self.assertNotIn('\r', text)
            self.assertLess(len(text.encode('utf-8')), 400000)

    def test_counts(self):
        c = Counter(x['category'] for x in self.items)
        self.assertEqual(c, {'adventurer': 1400, 'consumable': 55, 'tool': 17})
        t = Counter((x['table'], x.get('region')) for x in self.items if x['category'] == 'adventurer')
        for r in REGIONS:
            self.assertEqual(t[('adventurer_male_first', r)], 100)
            self.assertEqual(t[('adventurer_male_second', r)], 100)
            self.assertEqual(t[('adventurer_female', r)], 150)
        m = Counter(x.get('translation_method') for x in self.items if x['category'] == 'adventurer')
        self.assertEqual(m, {'kanji_traditionalized': 700, 'curated': 185, 'machine_translit_draft': 515})

    def test_items_no_m051_overlap_and_unique(self):
        keys = [(x['table'], x['slot']) for x in self.items if x['category'] != 'adventurer']
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(set(keys) & M051_SLOTS)
        adv = [(x['table'], x['region'], x['index']) for x in self.items if x['category'] == 'adventurer']
        self.assertEqual(len(adv), len(set(adv)))

    def test_hashes_real(self):
        for x in self.items:
            self.assertRegex(x['source_name_sha256'], HEX64)
            if x['category'] != 'adventurer':
                self.assertRegex(x['source_record_sha256'], HEX64)
                self.assertRegex(x['source_description_sha256'], HEX64)
                self.assertTrue(x['description_zh_tw'])
            else:
                self.assertIsNone(x['source_record_sha256'])

    def test_consistency_and_blocker_flags(self):
        by_src = defaultdict(set)
        for x in self.items:
            by_src[x['source_name_sha256']].add(x['name_zh_tw'])
            self.assertTrue(x['name_zh_tw'].strip())
            try:
                x['name_zh_tw'].encode('cp950')
                ok = True
            except UnicodeEncodeError:
                ok = False
            self.assertEqual(ok, x['name_cp950_encodable'])
            if x['category'] == 'adventurer':
                self.assertEqual(x['exact_match_usable'], x['table'] == 'adventurer_female')
                self.assertIs(x['ambiguity_blocked'], False)
        self.assertTrue(all(len(v) == 1 for v in by_src.values()))
        self.assertEqual(sum(not x['name_cp950_encodable'] for x in self.items), 8)


if __name__ == '__main__':
    unittest.main()
