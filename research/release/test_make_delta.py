import os, random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import make_delta as M


class DeltaTests(unittest.TestCase):
    def test_roundtrip_inplace_and_tail(self):
        r = random.Random(1); src = bytes(r.randrange(256) for _ in range(5000))
        dst = bytearray(src); dst[100:110] = b'X' * 10; dst += b'tail' * 50
        ops = M.diff(src, bytes(dst)); blob = M.encode_ops(ops)
        self.assertEqual(M.apply_ops(src, blob), bytes(dst))
        self.assertLess(sum(len(o[1]) for o in ops if o[0] == 'L'), 260)

    def test_roundtrip_shifted(self):
        r = random.Random(2); src = bytes(r.randrange(256) for _ in range(3000))
        dst = b'abc' + src[:1000] + b'zz' + src[1000:]
        self.assertEqual(M.apply_ops(src, M.encode_ops(M.diff(src, dst))), dst)

    def test_build_only_changed(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, 'a'), Path(t, 'b')
            for p in (a, b):
                (p / 'RES').mkdir(parents=True); (p / 'Usr').mkdir()
                (p / 'same.txt').write_bytes(b'same'); (p / 'Usr' / 's.dat').write_bytes(b'1' if p == a else b'2')
            (a / 'RES' / 'x.bmp').write_bytes(b'0' * 100); (b / 'RES' / 'x.bmp').write_bytes(b'0' * 50 + b'1' * 50)
            payload, rep = M.build(a, b, '0.0.1')
            self.assertTrue(payload.startswith(M.MAGIC))
            self.assertEqual([x['path'] for x in rep], ['RES/x.bmp'])
            self.assertEqual(M.read_meta(payload)['files'][0]['dst_size'], 100)


    def test_bmh_pixel_delta(self):
        r = random.Random(3); dib = bytes(r.randrange(4) for _ in range(4000))
        hdr = bytearray(0x18); hdr[8:10] = b'HF'
        src = M.bmh.encode_huffman(dib, bytes(hdr))
        new = bytearray(dib); new[1000:1010] = b'\x07' * 10
        dst_lab = M.bmh.encode_huffman(bytes(new), src)
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, 'a'), Path(t, 'b'); a.mkdir(); b.mkdir()
            (a / 'X.BMH').write_bytes(src); (b / 'X.BMH').write_bytes(dst_lab)
            payload, rep = M.build(a, b, '0')
            f = M.read_meta(payload)['files'][0]
            self.assertEqual(f['kind'], 'bmh')
            self.assertLess(rep[0]['literal_bytes'], 40)
            ops = payload[12 + int.from_bytes(payload[8:12], 'little'):]
            out = M.apply_file('bmh', src, ops[f['ops_off']:f['ops_off'] + f['ops_len']])
            self.assertEqual(M.bmh.decode(out), bytes(new))


if __name__ == '__main__':
    unittest.main()
