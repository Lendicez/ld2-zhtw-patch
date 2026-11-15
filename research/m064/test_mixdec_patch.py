"""m064 mixdec_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mixdec_patch as M  # noqa: E402
import cdc_textout_patch as T  # noqa: E402


class MixTests(unittest.TestCase):
    def test_model_mixed(self):
        item = 'コンディションパウダー'.encode('cp932')
        raw = '偷到了'.encode('cp950') + item + '！'.encode('cp950')
        self.assertEqual(M.model(raw, {item: '狀態粉'}), '偷到了狀態粉！')
        self.assertEqual(M.model(raw), '偷到了科恩迪蕭恩帕烏達！')   # 1.0.2：查不到的整段片假名 → 音譯（與控制項一致）
        self.assertEqual(M.model('鎮上傳聞-'.encode('cp950') + 'シャル'.encode('cp932')), '鎮上傳聞-夏爾')

    def test_model_pure(self):
        self.assertEqual(M.model('朗報を待ってるよ。'.encode('cp932')), '朗報を待ってるよ。')
        self.assertEqual(M.model('等你的好消息。 3300G'.encode('cp950')), '等你的好消息。 3300G')
        self.assertEqual(M.model('◎和良'.encode('cp950')), '◎和良')

    def test_code_shape(self):
        c = M.build(0xb2c000, 0xb2c200, 0x52537c)
        tables = M.S.kana_table() + M.S.digraph_table()
        self.assertTrue(c.startswith(bytes.fromhex('60fc8b7424248b5c242801f3')))
        self.assertTrue(c.endswith(tables))                             # 音譯表附在程式碼後
        code = c[:len(c) - len(tables)]
        self.assertIn(bytes.fromhex('8944241c61c20800'), code[-10:])   # mov [esp+1c],eax; popad; ret 8（後面可能有 1 位元組對齊）
        self.assertLess(len(code), 0x300)

    def test_textout_hook_fits_cave(self):
        c = T.build_stub(0x52537c, mix=(0xb2c000, 0xb2c220))
        self.assertLessEqual(T.TO_HOOK + len(c), 0xae6000)
        self.assertIn(bytes.fromhex('5756e8'), c)


try:
    import unicorn  # noqa: F401
    import stub_emu as EMU
except ImportError:
    EMU = None


@unittest.skipIf(EMU is None, 'unicorn 未安裝')
class MixwEmulationTests(unittest.TestCase):
    """實際執行 MIXW，結果須與 Python 模型一致。"""

    def test_cases(self):
        c, b = (lambda s: s.encode('cp932')), (lambda s: s.encode('cp950'))
        item = c('コンディションパウダー')
        cases = [
            (b('鎮上傳聞-') + c('シャル'), {}),                    # 查不到的片假名名字 → 音譯（拗音）
            (b('偷到了') + item + b('！'), {item: '狀態粉'}),       # catalog 命中
            (b('偷到了') + item + b('！'), {}),
            (c('朗報を待ってるよ。'), {}),                          # 含漢字／平假名的句子 → 維持原文
            (b('等你的好消息。 3300G'), {}),
            (b('◎') + c('ティス・レベラ'), {}),
            (c('岩塊の町'), {c('岩塊の町'): '岩塊鎮'}),
        ]
        for src, cat in cases:
            self.assertEqual(EMU.run(src, catalog=cat, mixw=True), M.model(src, cat), src)


if __name__ == '__main__':
    unittest.main()
