"""m064 detail_name_patch 單元測試：只用合成 bytes，不含遊戲資料。"""
import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detail_name_patch as D  # noqa: E402


class PairTableTests(unittest.TestCase):
    def test_round_trip_and_miss(self):
        pairs = [(b'\x82\xa0\x82\xa2', b'\xa4\x40'), (b'\x41', b'\xa4\x41\xa4\x42'), (b'\x82\xa0\x82\xa2', b'\xa4\x40')]
        t = D.build_pairs(pairs)
        self.assertEqual(t[-1], 0)
        self.assertEqual(D.pair_lookup(t, b'\x41'), b'\xa4\x41\xa4\x42')
        self.assertEqual(D.pair_lookup(t, b'\x82\xa0\x82\xa2'), b'\xa4\x40')
        self.assertIsNone(D.pair_lookup(t, b'\x82\xa0'))
        self.assertEqual(len(t), (1 + 4 + 1 + 2) + (1 + 1 + 1 + 4) + 1)   # 重複鍵只存一次

    def test_ambiguous_and_bounds(self):
        with self.assertRaises(ValueError):
            D.build_pairs([(b'A', b'\xa4\x40'), (b'A', b'\xa4\x41')])
        with self.assertRaises(ValueError):
            D.build_pairs([(b'A\0', b'\xa4\x40')])


class StubTests(unittest.TestCase):
    def test_epi_stub_shape(self):
        s = D.build_epi_stub(0xb26000)
        self.assertEqual(s[:8], bytes.fromhex('ff742408ff742408'))      # 透傳 out／idx
        rel = struct.unpack_from('<i', s, 9)[0]
        self.assertEqual(D.EPI_STUB + 13 + rel, D.GET_EPI)
        self.assertEqual(s[-4:], bytes.fromhex('61c20800'))             # popad; ret 8
        self.assertIn(bytes([0xBB]) + struct.pack('<I', 0xb26000), s)
        self.assertLessEqual(D.EPI_STUB + len(s), D.NAME_STUB)

    def test_name_stub_shape(self):
        s = D.build_name_stub(0x525378)
        rel = struct.unpack_from('<i', s, 9)[0]
        self.assertEqual(D.NAME_STUB + 13 + rel, D.GET_NAME)
        self.assertIn(bytes.fromhex('ff1578535200'), s)                # call [WideCharToMultiByte]
        self.assertIn(bytes([0x68]) + struct.pack('<I', 950), s)
        self.assertEqual(s[-4:], bytes.fromhex('61c20800'))

    def test_menu_stub_uses_member_getter(self):
        s = D.build_name_stub(0x525378, origin=D.MENU_STUB, getter=D.GET_MEMBER)
        rel = struct.unpack_from('<i', s, 9)[0]
        self.assertEqual(D.MENU_STUB + 13 + rel, D.GET_MEMBER)
        self.assertLessEqual(D.NAME_STUB + len(D.build_name_stub(0x525378)), D.MENU_STUB)

    def test_golden(self):
        got = hashlib.sha256(D.build_epi_stub(0xb26000) + D.build_name_stub(0x525378)).hexdigest()
        self.assertEqual(got, 'ea7718e4f4d690bb212e00d5bf248de35a442a6d53a31316dce18f1e44d36329')


if __name__ == '__main__':
    unittest.main()
