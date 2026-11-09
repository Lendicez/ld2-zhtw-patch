"""m064 title_patch 單元測試：只用合成資料。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import title_patch as T  # noqa: E402
import savelist_patch as S  # noqa: E402


class TitleTests(unittest.TestCase):
    def test_sites_cover_children(self):
        apis = [a for _, a, _ in T.SITES]
        self.assertIn('SetDlgItemTextA', apis)
        self.assertFalse(hasattr(T, 'build_front'))          # 1.0.1：子視窗不再略過

    def test_pairs_lookup_emitted(self):
        c, _ = S.build_stub(0xb28100, 0xb28000, 0x52537c, 0x525378, arg_esp=0xc, target_ind=0x52541c,
                            pairs_va=0xb26000)
        self.assertIn(bytes.fromhex('51ba0060b200'), c)            # push ecx; mov edx,table

    def test_conv_tail_indirect(self):
        c, _ = S.build_stub(0xb28100, 0xb28000, 0x52537c, 0x525378, arg_esp=8, target_ind=0x525414)
        self.assertIn(bytes.fromhex('8b742428'), c)                 # esi=[esp+0x28]
        self.assertIn(bytes.fromhex('61ff2514545200'), c[:-len(S.kana_table())])  # popad; jmp [SetWindowTextA]（音譯表之前）
        self.assertIn(bytes.fromhex('c7442408'), c)                 # [esp+8] = sbuf


if __name__ == '__main__':
    unittest.main()
