"""m064 nto_fallback_patch 單元測試：只用合成 bytes。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nto_fallback_patch as N  # noqa: E402


class FallbackTests(unittest.TestCase):
    def test_big5_never_decoded(self):
        for zh in ('廣場', '無裝備', '速戰速決的', '伊爾塔爾國 岩塊鎮', '可購買張數為%d～%d張'):
            self.assertIsNone(N.model(zh.encode('cp950')), zh)

    def test_japanese_decoded(self):
        for ja in ('グルメ', 'なし', '軍刀', 'ダジルタール'):
            self.assertEqual(N.model(ja.encode('cp932')), 'ja', ja)

    def test_ascii_and_halfwidth_left_alone(self):
        self.assertIsNone(N.model(b'HP 65/65'))
        self.assertIsNone(N.model('ﾀﾞｼﾞﾙ'.encode('cp932')))
        self.assertEqual(N.model(b'x', hit=True), 'hit')

    def test_all_cp950_bytes_outside_0x80_0xa0(self):
        """cp950 的一般字（非 EUDC）lead／trail 都不在 0x80–0xA0。"""
        for lead in range(0xA1, 0xFA):
            for trail in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
                try:
                    bytes([lead, trail]).decode('cp950')
                except UnicodeDecodeError:
                    continue
                self.assertFalse(0x80 <= trail <= 0xA0)

    def test_stub_shape(self):
        s = N.build_stub(0x52537c)
        self.assertEqual(s[:4], bytes.fromhex('558bec56'))
        self.assertEqual(s[-5:], bytes.fromhex('5e5dc20c00'))
        self.assertIn(bytes.fromhex('ff157c535200'), s)
        self.assertIn(bytes.fromhex('68a4030000'), s)       # push 932


if __name__ == '__main__':
    unittest.main()
