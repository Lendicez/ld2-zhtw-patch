"""m064 savelist_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import savelist_patch as S  # noqa: E402


class SaveListTests(unittest.TestCase):
    def test_model_tokens(self):
        got = S.model(' 971年 7月12日 アイウ  岩塊の町', {'アイウ': '甲乙丙', '岩塊の町': '岩塊鎮'})
        self.assertEqual(got, ' 971年 7月12日 甲乙丙  岩塊鎮')

    def test_model_big5_untouched(self):
        s = ' 971年 7月12日 達吉爾塔爾  岩塊鎮'
        self.assertEqual(S.model(s.encode('cp950').decode('cp932', 'replace') if False else s, {}), s)

    def test_model_kana_kept(self):
        self.assertEqual(S.model(' カナ', {}), ' カナ')   # cp950 有假名（C6xx 區）

    def test_stub_shape(self):
        code, dlen = S.build_stub(0xb28000, 0xb28140, 0x52537c, 0x525378)
        self.assertEqual(code[0], 0x60)                                   # pushad
        self.assertIn(bytes.fromhex('6aff6a03') [:0] + bytes.fromhex('6a036aff'), code)   # flags=3, ident=-1
        self.assertIn(bytes.fromhex('68a4030000'), code)                 # 932
        self.assertIn(bytes.fromhex('68b6030000'), code)                 # 950
        self.assertEqual(dlen, 0x340)
        self.assertLess(len(code), 0x140)


if __name__ == '__main__':
    unittest.main()
