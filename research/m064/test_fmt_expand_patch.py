"""m064 fmt_expand_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fmt_expand_patch as F  # noqa: E402


class ExpandTests(unittest.TestCase):
    def test_model(self):
        self.assertEqual(F.model('アイウ'.encode('cp932'), {'アイウ': '甲乙丙'}), '甲乙丙'.encode('cp950'))
        self.assertEqual(F.model('岩塊鎮'.encode('cp950'), {}), '岩塊鎮'.encode('cp950'))   # 已是 Big5 → 不動
        self.assertEqual(F.model(b'1234', {}), b'1234')
        self.assertEqual(F.model('漢字'.encode('cp932'), {}), '漢字'.encode('cp950'))       # 查無 → 照字形

    def test_stub_shape(self):
        code, dlen = F.build_stub(0xb29000, 0xb290e0, 0x52537c, 0x525378)
        self.assertTrue(code.startswith(F.SITE_BYTES[:7]))          # 原 mov ecx,[ebx+edx*4-0xdc]
        self.assertTrue(code.endswith(bytes.fromhex('618bd6c3')))   # popad; mov edx,esi; ret
        self.assertIn(bytes.fromhex('6a036aff'), code)
        self.assertEqual(dlen, 0x320)


if __name__ == '__main__':
    unittest.main()
