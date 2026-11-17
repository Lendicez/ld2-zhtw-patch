import unittest
import accel_patch as A

ORIG = [(0xb, 0x4e, 57600), (0xb, 0x4f, 57601), (0x3, 0x70, 57670)]


class T(unittest.TestCase):
    def test_roundtrip_and_last_flag(self):
        raw = A.encode(ORIG)
        self.assertEqual(len(raw), 24)
        self.assertEqual(raw[16] & A.FLAST, A.FLAST)   # 只有最後一筆有結尾旗標
        self.assertEqual(raw[0] & A.FLAST, 0)
        self.assertEqual(A.parse(raw), ORIG)
        self.assertEqual(A.parse(raw + b'junk-after-end'), ORIG)

    def test_add_keys(self):
        new = A.add_keys(ORIG)
        self.assertEqual(new[:3], ORIG)
        self.assertEqual(len(new), 3 + 12)
        cmds = {k: c for f, k, c in new[3:]}
        self.assertEqual(cmds[A.VK_UP], A.NORTH); self.assertEqual(cmds[A.VK_NUMPAD[9]], A.NORTH)
        self.assertEqual(cmds[A.VK_NUMPAD[3]], A.EAST); self.assertEqual(cmds[A.VK_NUMPAD[1]], A.SOUTH)
        self.assertEqual(cmds[A.VK_NUMPAD[7]], A.WEST)
        self.assertTrue(all(f == A.FVIRTKEY for f, _, _ in new[3:]))
        raw = A.encode(new)
        self.assertEqual(A.parse(raw), new)

    def test_refuse_duplicate(self):
        with self.assertRaises(ValueError):
            A.add_keys(ORIG + [(A.FVIRTKEY, A.VK_UP, 1)])

    def test_missing_end_flag(self):
        import struct
        with self.assertRaises(ValueError):
            A.parse(struct.pack('<HHHH', 1, 2, 3, 0))


if __name__ == '__main__':
    unittest.main()
