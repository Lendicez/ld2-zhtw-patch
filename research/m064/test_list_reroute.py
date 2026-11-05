"""m064 list_reroute：合成 call 位元組。"""
import struct, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import list_reroute as L  # noqa: E402


def call(buf, va, tgt):
    o = va - L.BASE; buf[o] = 0xE8; struct.pack_into('<i', buf, o + 1, tgt - (va + 5))


class RerouteTests(unittest.TestCase):
    def setUp(self):
        self.b = bytearray(0x200000)
        self.item, self.name = 0x5e4d40, 0x5e4b20
        call(self.b, L.KNOWN['item'], self.item); call(self.b, L.KNOWN['name'], self.name)
        call(self.b, 0x46e73a, self.name); call(self.b, 0x46bacb, L.WRAPPER)

    def test_reroute_to_item(self):
        out, info = L.reroute(bytes(self.b), [0x46e73a, 0x46bacb], 'item')
        self.assertEqual(L.target(out, 0x46e73a), self.item)
        self.assertEqual(L.target(out, 0x46bacb), self.item)
        diff = [i for i in range(len(out)) if out[i] != self.b[i]]
        self.assertTrue(all(0x6e73b <= i < 0x6e73f or 0x6bacc <= i < 0x6bad0 for i in diff))

    def test_unexpected_target_refused(self):
        call(self.b, 0x47db6a, 0x123456)
        with self.assertRaises(ValueError):
            L.reroute(bytes(self.b), [0x47db6a], 'item')

    def test_pristine_refused(self):
        call(self.b, L.KNOWN['item'], L.WRAPPER)
        with self.assertRaises(ValueError):
            L.reroute(bytes(self.b), [0x46e73a], 'item')


if __name__ == '__main__':
    unittest.main()
