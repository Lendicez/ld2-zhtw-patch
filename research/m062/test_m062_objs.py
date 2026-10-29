"""m062: audit tests for the locked Win11 MSVC v3 helper objects (lab-only inputs; skip if absent).
LD2_M062_OBJ_DIR defaults to ./compile-return-run1 (never committed)."""
import hashlib, os, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rehearse_v3_objs as rv  # noqa: E402
import audit_name_pair_v3 as anp  # noqa: E402
rv.install_profile()
A = rv.audit_list_obj
D = Path(os.environ.get('LD2_M062_OBJ_DIR', HERE / 'compile-return-run1'))
LIST, NAME = D / 'list_insert_v3.obj', D / 'name_pair_v3.obj'
SPILL = bytes.fromhex('8985f0fdffff')  # mov [ebp-0x210], eax  (LD2_OriginalDlgItem spill)


@unittest.skipUnless(LIST.exists() and NAME.exists(), 'lab objects not present')
class LockedObjects(unittest.TestCase):
    def setUp(self):
        self.list, self.name = LIST.read_bytes(), NAME.read_bytes()

    def test_hashes_locked(self):
        self.assertEqual(hashlib.sha256(self.list).hexdigest(), rv.LIST_V3_OBJECT_SHA256)
        self.assertEqual(hashlib.sha256(self.name).hexdigest(), rv.NAME_V3_OBJECT_SHA256)

    def test_list_profile_v3_passes_with_spill(self):
        rep = A.audit(self.list, 'v3')
        self.assertTrue(rep['esp_and_nonvolatile_preserved_on_normal_paths'])
        self.assertIn('_LD2_OriginalDlgItem', {s[2] for s in rep['binding_spills']})
        self.assertFalse(rep['production_can_apply'])

    def test_spill_from_untracked_register_refused(self):
        self.assertEqual(self.list.count(SPILL), 1)
        bad = self.list.replace(SPILL, bytes.fromhex('898df0fdffff'))  # store ecx (= lp) instead
        with self.assertRaises(SystemExit) as cm:
            A.audit(bad, 'v3')
        self.assertIn('unreviewed call', str(cm.exception))

    def test_name_pair_v3_passes(self):
        rep = anp.audit(self.name)
        self.assertEqual(rep['object_sha256'], rv.NAME_V3_OBJECT_SHA256)
        self.assertEqual(rep['functions']['_LD2_NamePair@16']['ret_pop'], 16)

    def test_name_pair_wrong_ret_refused(self):
        i = self.name.find(bytes.fromhex('c20800'))  # first `ret 8` (LD2_Wipe@8)
        self.assertGreater(i, 0)
        bad = self.name[:i] + bytes.fromhex('c20c00') + self.name[i + 3:]
        with self.assertRaises(SystemExit):
            anp.audit(bad)


if __name__ == '__main__':
    unittest.main()
