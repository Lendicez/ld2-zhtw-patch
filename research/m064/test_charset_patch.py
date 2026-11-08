"""m064 charset_patch：合成 bytes。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import charset_patch as C  # noqa: E402


class CharsetPatchTests(unittest.TestCase):
    def _exe(self):
        b = bytearray(0x100000)
        for off, want, _ in C.SITES:
            b[off:off + len(want)] = want
        return bytes(b)

    def test_patch_only_last_byte(self):
        exe = self._exe(); out, done = C.patch(exe)
        diff = [i for i in range(len(exe)) if exe[i] != out[i]]
        self.assertEqual(diff, sorted(off + len(w) - 1 for off, w, _ in C.SITES))
        self.assertTrue(all(out[i] == C.BIG5 for i in diff))
        self.assertEqual(C.patch(out)[0], out)  # idempotent

    def test_unexpected_bytes_refused(self):
        exe = bytearray(self._exe()); exe[C.SITES[0][0]] = 0x90
        with self.assertRaises(ValueError):
            C.patch(bytes(exe))


class FaceTests(unittest.TestCase):
    def _exe(self):
        b = bytearray(0x140000)
        b[C.FACE_OFF:C.FACE_OFF + 14] = 'ＭＳ ゴシック'.encode('cp932') + b'\0'
        b[C.FACE_LEN_SITE:C.FACE_LEN_SITE + 7] = C.FACE_LEN_WANT
        return bytes(b)

    def test_face(self):
        out, info = C.face_patch(self._exe())
        self.assertEqual(out[C.FACE_OFF:C.FACE_OFF + 14], '微軟正黑體'.encode('cp950') + b'\0' * 4)
        self.assertEqual(out[C.FACE_LEN_SITE + 1], 10)
        self.assertEqual(C.face_patch(out)[1]['status'], 'already')

    def test_face_mismatch(self):
        b = bytearray(self._exe()); b[C.FACE_OFF] = 0x41
        with self.assertRaises(ValueError):
            C.face_patch(bytes(b))

if __name__ == '__main__':
    unittest.main()
