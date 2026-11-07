"""m062: v3 merge/capacity/review-gate tests. Synthetic tests always run; lab tests skip
unless the pristine EXE, m045, the locked MSVC v3 objects and the m051 catalog are present."""
import hashlib, json, struct, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import merge_plan_v3 as mv  # noqa: E402
import catalog_v3 as c3  # noqa: E402


def sha(b): return hashlib.sha256(b).hexdigest()


def cat(items, **top):
    d = dict(source_sha256=c3.SOURCE, production_can_apply=False, items=items)
    d.update(top)
    raw = json.dumps(d).encode()
    return raw, sha(raw)


def big_rows(n, units):
    return [(c3.FULL_ANY, c3.ANY_ID, b'N%07d' % i, '%07d' % i + '譯' * (units - 7)) for i in range(n)]


class ReviewGate(unittest.TestCase):
    def test_draft_refused_under_reviewed(self):
        with self.assertRaises(mv.Refuse):
            mv.review_gate([cat([dict(name_status='translated', review_status='mina_draft')])], 'reviewed')

    def test_draft_lab_preview_not_release_eligible(self):
        s = mv.review_gate([cat([dict(name_status='translated', review_status='mina_draft')])], 'lab_preview')
        self.assertFalse(s['release_eligible'])

    def test_human_reviewed_release_eligible(self):
        s = mv.review_gate([cat([dict(name_status='identity_preserved', review_status='human_reviewed')] * 30)], 'reviewed')
        self.assertTrue(s['release_eligible'])   # no 24-item cap any more
        self.assertEqual(s['catalogs'][0]['items'], 30)

    def test_missing_status_only_for_pinned_m051(self):
        with self.assertRaises(mv.Refuse):
            mv.review_gate([cat([dict(name_status='translated')])], 'reviewed')

    def test_bad_name_status_and_flags(self):
        for items, top in (([dict(name_status='todo', review_status='approved')], {}),
                           ([dict(name_status='translated', review_status='approved')], dict(release_approved=True)),
                           ([dict(name_status='translated', review_status='approved')], dict(production_can_apply=True))):
            with self.assertRaises(mv.Refuse):
                mv.review_gate([cat(items, **top)], 'lab_preview')

    def test_hash_pin(self):
        raw, _ = cat([dict(name_status='translated', review_status='approved')])
        with self.assertRaises(mv.Refuse):
            mv.review_gate([(raw, '0' * 64)])
        with self.assertRaises(mv.Refuse):
            mv.review_gate([(raw, sha(raw))], 'anything')


class CapacityGate(unittest.TestCase):
    def test_8192_rows_small_text_fits(self):
        blob = c3.encode_v3(big_rows(8192, 8))
        r = mv.capacity_gate(blob)
        self.assertEqual(r['rows'], 8192)
        self.assertLessEqual(r['section_bytes'], r['section_budget'])

    def test_8193_rows_refused(self):
        with self.assertRaises(c3.Refuse):
            c3.encode_v3(big_rows(8193, 8))
        blob = bytearray(c3.encode_v3(big_rows(10, 8)))
        struct.pack_into('<I', blob, 8, 8193)
        with self.assertRaises(c3.Refuse):
            mv.capacity_gate(bytes(blob))

    def test_blob_valid_for_helper_but_too_big_for_section_refused(self):
        blob = c3.encode_v3(big_rows(8192, 55))
        self.assertLessEqual(len(blob), mv.V3_BLOB_MAX)            # ld2c3_open would accept it
        self.assertGreater(mv.CAT_HDR + len(blob), mv.SECTION_BUDGET)
        with self.assertRaises(mv.Refuse):
            mv.capacity_gate(blob)

    def test_custom_budget_refuses_not_truncates(self):
        blob = c3.encode_v3(big_rows(100, 8))
        with self.assertRaises(mv.Refuse):
            mv.capacity_gate(blob, section_budget=mv.CAT_HDR + len(blob) - 1)
        self.assertEqual(mv.capacity_gate(blob, section_budget=mv.CAT_HDR + len(blob))['headroom_bytes'], 0)

    def test_corrupt_blob_refused(self):
        blob = bytearray(c3.encode_v3(big_rows(10, 8)))
        blob[0] ^= 1
        with self.assertRaises(c3.Refuse):
            mv.capacity_gate(bytes(blob))


try:
    import build_v3_lab as b3
    LAB_OK = all(p.is_file() for p in (b3.LAB / 'baseline/pristine/Ld95.exe', b3.LAB / 'runs/m045/build-first/Ld95.exe',
                                       b3.OBJ_DIR / 'name_pair_v3.obj', b3.OBJ_DIR / 'list_insert_v3.obj', b3.M051))
except Exception:  # capstone/pefile missing outside the lab venv
    LAB_OK = False

# Pinned 2026-10-29 (Asia/Taipei) lab build, reviewed catalog (m051 24 items -> 264 rows).
PIN = {2: ('99f4ae547a3405f98e042d382b2d2fc0f962ae6029df206f7407f57ec6825e47', '67ef9baccfa1437af68d0b2feb3648f9a1a80a7fbc98579fb841b0099b08c01a'),
       0: ('043efdd62ac7c8e05580e6a74cd458ef3e0edafe0ba4b55188dae09132c1c140', '7a51d870b5431a57e28ae13401e60a6dea424ebfcf9918641b36269aa64715be')}
BLOB_REVIEWED = '2879e445a1e40977e4ec21818df0317d82c3ee516a7d8d173b744458a0247abf'


@unittest.skipUnless(LAB_OK, 'lab inputs missing')
class LabMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre = b3.inputs('reviewed')

    def test_reviewed_blob(self):
        self.assertEqual(sha(self.pre[4]), BLOB_REVIEWED)

    def test_build_and_verify_pinned(self):
        for mode, (inert_sha, en_sha) in PIN.items():
            o, m, inert, rep, en, erep = b3.build(mode, 'reviewed', self.pre)
            self.assertEqual((sha(inert), sha(en)), (inert_sha, en_sha))
            v = b3.verify(o, inert, rep, en, erep, self.pre[2], self.pre[3])
            self.assertEqual(v['binding_targets']['original_dlgitem_value'], '0x4ea671')
            self.assertTrue(v['binding_targets']['shared_catalog'])
            self.assertFalse(rep['production_can_apply'] or rep['release_approved'])

    def test_zero_original_dlgitem_refused(self):
        o, m, no, lo, blob, _ = self.pre
        keep = mv.mp.WRAPPER_VA
        try:
            mv.mp.WRAPPER_VA = 0
            with self.assertRaises(mv.Refuse):
                mv.build_inert_v3(o, m, no, lo, blob)
        finally:
            mv.mp.WRAPPER_VA = keep

    def test_unlocked_object_refused(self):
        o, m, no, lo, blob, _ = self.pre
        with self.assertRaises(mv.Refuse):
            mv.build_inert_v3(o, m, no[:-1] + bytes([no[-1] ^ 1]), lo, blob)
        with self.assertRaises(mv.Refuse):
            mv.build_inert_v3(o, m, lo, no, blob)

    def test_oversize_section_refused_before_build(self):
        o, m, no, lo, _, _ = self.pre
        with self.assertRaises(mv.Refuse):
            mv.build_inert_v3(o, m, no, lo, c3.encode_v3(big_rows(8192, 55)))

    def test_draft_needs_lab_preview(self):
        if not b3.MINA.is_file():
            self.skipTest('draft missing')
        with self.assertRaises(mv.Refuse):
            mv.build_blob(self.pre[0], [(b3.M051.read_bytes(), mv.M051_SHA), (b3.MINA.read_bytes(), b3.MINA_SHA)], 'reviewed')


if __name__ == '__main__':
    unittest.main()
