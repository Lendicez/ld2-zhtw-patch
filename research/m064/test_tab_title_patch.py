"""m064 tab_title_patch：stub 位元組（golden；v2 半形→全形正規化；2026-11-05 以 capstone 反組譯逐條核對）。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tab_title_patch as T  # noqa: E402

GOLDEN = ('8bce6089fe56ff154453520085c00f84e300000083f8400f87da0000006880000000688058b20050566a0068a4030000'
          'ff157c53520085c00f84b90000006880000000688059b20050688058b20068000080006811040000ff15d051520085c0'
          '0f84910000006a006a006a4868805ab20050688059b2006a0068a4030000ff157853520085c00f846b00000083f8400f'
          '8762000000c680805ab20000680054b2005068805ab200e834feffff85c00f84430000008b1d1056b2004383e307891d'
          '1056b2006bdb4881c32056b2006a006a006a475350680054b2006a0068b6030000ff157853520085c00f8408000000c6'
          '04030089dfeb0289f78b44241c89781461c3')


class StubTests(unittest.TestCase):
    def test_golden(self):
        self.assertEqual(T.build_stub(0x525344, 0x525378, 0x52537c, 0x5251d0).hex(), GOLDEN)

    def test_structure(self):
        s = T.build_stub(0x525344, 0x525378, 0x52537c, 0x5251d0)
        self.assertEqual(s[:3], bytes.fromhex('8bce60'))       # mov ecx,esi ; pushad
        self.assertEqual(s[-2:], bytes.fromhex('61c3'))        # popad ; ret
        self.assertLess(T.STUB - T.BASE + len(s), 0x6e3000 + 0x3000)
        self.assertLessEqual(T.ABUF + T.SLOTS * T.SLOT_BYTES, 0xb26000)

    def test_relocates(self):
        a, b = T.build_stub(1, 2, 3, 4), T.build_stub(1, 2, 3, 4, origin=T.STUB + 0x10)
        self.assertEqual(len(a), len(b))
        self.assertNotEqual(a, b)   # call rel32 to FindCopy depends on origin


if __name__ == '__main__':
    unittest.main()
