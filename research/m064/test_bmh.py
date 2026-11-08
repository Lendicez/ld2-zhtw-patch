"""m064 BMH codec tests: synthetic data only (no game assets). Real-file check runs only with LD2_RES_DIR."""
import os
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmh  # noqa: E402

TEMPLATE = struct.pack('<II', 0, 0) + b'HF\0\0' + struct.pack('<III', 0x10000, 8, 0)


def synthetic_dib(w=40, h=12, seed=1):
    rnd = random.Random(seed)
    hdr = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 8, 0, w * h, 0, 0, 256, 0)
    pal = bytes(rnd.randrange(256) for _ in range(1024))
    pix = bytes(rnd.choice((0, 0, 0, 1, 2, 7, 200)) for _ in range(w * h))
    return hdr + pal + pix


class BmhTests(unittest.TestCase):
    def test_raw_roundtrip(self):
        d = synthetic_dib()
        b = bmh.encode_raw(d, TEMPLATE)
        self.assertEqual(struct.unpack_from('<I', b, 0)[0], len(b))
        self.assertEqual(bmh.decode(b), d)

    def test_huffman_roundtrip_and_smaller(self):
        d = synthetic_dib(200, 100)
        b = bmh.encode_huffman(d, TEMPLATE)
        self.assertEqual(bmh.decode(b), d)
        self.assertLess(len(b), len(bmh.encode_raw(d, TEMPLATE)))

    def test_multiblock(self):
        d = synthetic_dib(300, 60, seed=3)
        b = bmh.encode_huffman(d, TEMPLATE, block=4096)
        self.assertEqual(bmh.decode(b), d)

    def test_single_symbol_block(self):
        d = b'\x05' * 777
        self.assertEqual(bmh.decode(bmh.encode_huffman(d, TEMPLATE)), d)

    def test_mixed_raw_and_huffman_blocks(self):
        d1, d2 = b'abc' * 50, bytes(range(256))
        body = struct.pack('<II', 0, len(d1)) + d1
        rest = bmh.encode_huffman(d2, TEMPLATE)[0x18:]
        b = bytes(bmh._header(TEMPLATE, len(body) + len(rest), len(d1) + len(d2))) + body + rest
        self.assertEqual(bmh.decode(b), d1 + d2)

    def test_not_hf_rejected(self):
        with self.assertRaises(ValueError):
            bmh.decode(b'\0' * 0x40)

    def test_real_files_optional(self):
        res = os.environ.get('LD2_RES_DIR')
        if not res:
            self.skipTest('LD2_RES_DIR not set (licensed input)')
        files = [p for p in Path(res).iterdir() if p.suffix.lower() == '.bmh']
        self.assertTrue(files)
        for p in files:
            raw = p.read_bytes()
            d = bmh.decode(raw)
            self.assertEqual(d[:4], b'\x28\0\0\0', p.name)
            self.assertEqual(bmh.decode(bmh.encode_huffman(d, raw)), d, p.name)


if __name__ == '__main__':
    unittest.main()
