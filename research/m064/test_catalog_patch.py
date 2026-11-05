"""m064 catalog_patch：與 m063 catalog_v4.encode_v4 位元組相容（合成資料）。"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'm063'))
sys.path.insert(0, str(HERE.parent / 'm062'))
import catalog_patch as P  # noqa: E402
import catalog_v4 as c4  # noqa: E402


class CatalogPatchTests(unittest.TestCase):
    rows = [(c4.FULL_ANY, -1, 'アイウ'.encode('cp932'), '甲乙', 0),
            (c4.FULL_ANY, -1, 'エ'.encode('cp932'), '丙', 0),
            (c4.FULL_ID, 7, 'オカ'.encode('cp932'), '丁戊', 0)]

    def test_encode_matches_catalog_v4(self):
        self.assertEqual(P.encode(self.rows), c4.encode_v4(self.rows))

    def test_roundtrip_with_big5_key(self):
        big5 = '廣場'.encode('cp950')
        rows = self.rows + [(P.FULL_ANY, -1, big5, '廣場', 0)]
        blob = P.encode(rows)
        self.assertEqual(sorted(P.decode(blob), key=P.sort_key), sorted(rows, key=P.sort_key))

    def test_ambiguous_key_rejected(self):
        with self.assertRaises(ValueError):
            P.encode(self.rows + [(c4.FULL_ANY, -1, 'エ'.encode('cp932'), '別', 0)])


if __name__ == '__main__':
    unittest.main()
