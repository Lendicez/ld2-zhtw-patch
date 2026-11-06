"""m064 res_extra 單元測試：目錄格式與合約（不含遊戲資料）。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import res_extra as R  # noqa: E402

HERE = Path(__file__).resolve().parent


class ResExtraTests(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(R._contract('%1 から %2'), R._contract('從 %1 到 %2'))
        self.assertNotEqual(R._contract('説明\nヘルプ'), R._contract('說明'))
        self.assertEqual(R._contract('ヘルプ(&H)'), R._contract('說明(&H)'))

    def test_catalog_has_no_japanese(self):
        p = HERE / 'res-extra.zh-TW.json'
        if not p.exists():
            self.skipTest('no catalog')
        d = json.loads(p.read_text('utf-8'))
        self.assertFalse(d['production_can_apply'])
        for e in d['entries']:
            self.assertNotIn('ja', e)
            self.assertIsNone(R.JA.search(e['translation']))
            e['translation'].encode('cp950')


if __name__ == '__main__':
    unittest.main()
