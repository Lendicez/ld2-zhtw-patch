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


if __name__ == '__main__':
    unittest.main()
