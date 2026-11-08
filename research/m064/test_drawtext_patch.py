"""m064 drawtext_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawtext_patch as D  # noqa: E402


class DrawTextTests(unittest.TestCase):
    def test_model(self):
        self.assertEqual(D.model('なし'.encode('cp932'), -1), 'w')
        self.assertEqual(D.model('無'.encode('cp950'), -1), 'a')
        self.assertEqual(D.model(b'', -1), 'a')
        self.assertEqual(D.model(b'abc', 3), 'a')

    def test_stub(self):
        code, data = D.build_stub(0xb2a000, 0xb2a0f0, 0x52537c, 0x525300, 0x5252e4)
        self.assertTrue(code.endswith(bytes.fromhex('ff1534565200c21000')))
        self.assertIn(b'DrawTextW\0', data)
        self.assertIn(b'USER32.dll\0', data)
        self.assertLess(len(code), 0xf0)


if __name__ == '__main__':
    unittest.main()
