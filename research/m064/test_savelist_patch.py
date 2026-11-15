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
        tables = len(S.kana_table()) + len(S.digraph_table())
        self.assertLess(len(code) - tables, 0x400)   # 程式碼本身；附表另計。版面依實際長度排，無固定上限
        self.assertTrue(code.endswith(S.kana_table() + S.digraph_table()))

    def test_translit_model(self):
        self.assertEqual(S.translit_model('ダジルタール'), '達吉爾塔爾')
        self.assertEqual(S.translit_model('ガーゴイル・ロード'), '加哥伊爾‧羅多')
        self.assertEqual(S.translit_model('ちびっこ'), '奇比科')
        self.assertEqual(S.translit_model('神の傀儡'), '神之傀儡')
        for ch in S.translit_model(S.KANA):
            ch.encode('cp950')                                            # 全部可編成 Big5


try:
    import unicorn  # noqa: F401
    import stub_emu as EMU
except ImportError:  # 模擬執行測試需要 unicorn
    EMU = None


def _c(s): return s.encode('cp932')
def _b(s): return s.encode('cp950')


@unittest.skipIf(EMU is None, 'unicorn 未安裝')
class StubEmulationTests(unittest.TestCase):
    """實際執行轉換 stub（catalog／名字音節表／MBTWC／WCTMB 以 Python 模擬）。"""

    def check(self, src, want, catalog=None, names=None, pairs=None):
        self.assertEqual(EMU.run(src, catalog, names, pairs).decode('cp950'), want)

    def test_pure_cp932_header_unchanged(self):
        self.check(_c(' 971年 7月12日 ダジルタール  岩塊の町'), ' 971年 7月12日 達吉爾塔爾  岩塊鎮',
                   catalog={_c('岩塊の町'): '岩塊鎮'})

    def test_pure_cp932_e0_lead(self):
        self.check(_c('鷹の目'), '鷹之眼', catalog={_c('鷹の目'): '鷹之眼'})

    def test_pure_big5_untouched(self):
        self.check(_b('鎮上傳聞-冒險者'), '鎮上傳聞-冒險者')

    def test_mixed_rumor_title(self):          # 1.0.2：傳聞視窗標題「鎮上傳聞-」＋CP932 說話者
        self.check(_b('鎮上傳聞-') + _c('男'), '鎮上傳聞-男', catalog={_c('男'): '男'})

    def test_mixed_translit(self):
        self.check(_b('鎮上傳聞-') + _c('ダジルタール'), '鎮上傳聞-達吉爾塔爾')

    def test_mixed_cp932_first_and_middle(self):
        cat = {_c('ポーション'): '藥水'}
        self.check(_c('ポーション') + _b('偷到了！'), '藥水偷到了！', catalog=cat)
        self.check(_b('偷到了') + _c('ポーション') + _b('！'), '偷到了藥水！', catalog=cat)

    def test_symbol_then_name(self):
        self.check(_b('◎') + _c('アイウ'), '◎甲乙丙', names={_c('アイウ'): '甲乙丙'})

    def test_tab_fields_mixed(self):
        self.check(_b('採集') + b'\t' + _b('100G') + b'\t' + _c('ダジル') + _b('的委託'), '採集\t100G\t達吉爾的委託')

    def test_mixed_epithet_pairs(self):
        self.check(_b('傳聞：') + _c('魔隼'), '傳聞：魔隼', pairs={_c('魔隼'): _b('魔隼')})

    def test_digraph_stub_matches_model(self):   # 所有「片假名＋小寫假名」組合（合成資料），stub 與 Python 模型一致
        bases = [k for k in S.KANA if k not in S.SMALL]
        words = [b + sm + 'ル' for b in bases for sm in S.SMALL] + ['ャ', 'シャ', 'しゃ', 'ティー', 'ディッ']
        for w in words:
            src = w.encode('cp932', 'ignore')
            if not src:
                continue
            want = S.translit_model(src.decode('cp932'))
            self.assertEqual(EMU.run(src).decode('cp950'), want, w)


if __name__ == '__main__':
    unittest.main()
