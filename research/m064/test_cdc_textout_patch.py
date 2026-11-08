"""m064 cdc_textout_patch 單元測試：只用合成 bytes。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdc_textout_patch as C  # noqa: E402


class TextOutFallbackTests(unittest.TestCase):
    def test_model(self):
        self.assertEqual(C.model('軍刀'.encode('cp932'), 4), 'w')
        self.assertEqual(C.model('軍刀'.encode('cp950'), 4), 'a')
        self.assertEqual(C.model(b'65/ 65', 6), 'a')
        self.assertEqual(C.model('グルメ'.encode('cp932'), 6, have_w=False), 'a')
        self.assertEqual(C.model(b'', 0), 'a')
        self.assertEqual(C.model('あ'.encode('cp932') * 40, 80), 'a')      # 過長 → 原路徑

    def test_stub_tail_is_original_body(self):
        s = C.build_stub(0x52537c)
        self.assertTrue(s.endswith(C.CDC_TEXTOUT_BODY))
        self.assertEqual(s[:5], bytes.fromhex('558bec5657'))
        self.assertIn(bytes.fromhex('ff156051b200'), s)    # call [TextOutW ptr 0xb25160]
        self.assertLess(C.TO_HOOK + len(s), 0xae6000)


if __name__ == '__main__':
    unittest.main()
