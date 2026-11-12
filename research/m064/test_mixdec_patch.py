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
        self.assertEqual(M.model(raw), '偷到了コンディションパウダー！')

    def test_model_pure(self):
        self.assertEqual(M.model('朗報を待ってるよ。'.encode('cp932')), '朗報を待ってるよ。')
        self.assertEqual(M.model('等你的好消息。 3300G'.encode('cp950')), '等你的好消息。 3300G')
        self.assertEqual(M.model('◎和良'.encode('cp950')), '◎和良')

    def test_code_shape(self):
        c = M.build(0xb2c000, 0xb2c200, 0x52537c)
        self.assertTrue(c.startswith(bytes.fromhex('60fc8b7424248b5c242801f3')))
        self.assertTrue(c.endswith(bytes.fromhex('894424 1c61c20800'.replace(' ', ''))))
        self.assertLess(len(c), 0x200)

    def test_textout_hook_fits_cave(self):
        c = T.build_stub(0x52537c, mix=(0xb2c000, 0xb2c220))
        self.assertLessEqual(T.TO_HOOK + len(c), 0xae6000)
        self.assertIn(bytes.fromhex('5756e8'), c)


if __name__ == '__main__':
    unittest.main()
