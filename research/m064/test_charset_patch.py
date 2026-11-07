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


if __name__ == '__main__':
    unittest.main()
