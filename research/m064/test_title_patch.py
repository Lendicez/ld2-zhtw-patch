"""m064 title_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import title_patch as T  # noqa: E402
import savelist_patch as S  # noqa: E402


class TitleTests(unittest.TestCase):
    def test_front_style_arg(self):
        f = T.build_front(0xb28490, 0xb28100, 0x525554, 'style_arg', 0x525538)
        self.assertTrue(f.startswith(bytes.fromhex('f744241000000040')))
        self.assertTrue(f.endswith(bytes.fromhex('ff2554555200')))

    def test_front_hwnd(self):
        f = T.build_front(0xb28600, 0xb28100, 0x525414, 'hwnd', 0x525538)
        self.assertTrue(f.startswith(bytes.fromhex('6af0ff742408ff1538555200')))

    def test_conv_tail_indirect(self):
        c, _ = S.build_stub(0xb28100, 0xb28000, 0x52537c, 0x525378, arg_esp=8, target_ind=0x525414)
        self.assertIn(bytes.fromhex('8b742428'), c)                 # esi=[esp+0x28]
        self.assertIn(bytes.fromhex('61ff2514545200'), c[:-len(S.kana_table())])  # popad; jmp [SetWindowTextA]（音譯表之前）
        self.assertIn(bytes.fromhex('c7442408'), c)                 # [esp+8] = sbuf


if __name__ == '__main__':
    unittest.main()
