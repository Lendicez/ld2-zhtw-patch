import unittest
from pathlib import Path
from ld2patch.upload_limits import within_reviewed_text_size,REVIEWED_PATH,DEFAULT_TEXT_LIMIT
ROOT=Path(__file__).resolve().parents[1]
class UploadTextBudgetTests(unittest.TestCase):
 def test_only_exact_reviewed_large_catalog_has_a_size_exception(self):
  data=(ROOT/REVIEWED_PATH).read_bytes()
  self.assertTrue(within_reviewed_text_size(REVIEWED_PATH,data))
  self.assertFalse(within_reviewed_text_size('patches/m999/catalog.json',data))
  changed=bytearray(data);changed[-2]^=1
  self.assertFalse(within_reviewed_text_size(REVIEWED_PATH,bytes(changed)))
  self.assertFalse(within_reviewed_text_size(REVIEWED_PATH,data+b' '))
 def test_m045_exception_is_exact_and_not_interchangeable_with_m042(self):
  name='patches/m045/catalog.json';data=(ROOT/name).read_bytes()
  self.assertTrue(within_reviewed_text_size(name,data))
  self.assertFalse(within_reviewed_text_size(REVIEWED_PATH,data))
  self.assertFalse(within_reviewed_text_size(name,(ROOT/REVIEWED_PATH).read_bytes()))
  self.assertFalse(within_reviewed_text_size('patches/m999/catalog.json',data))
  changed=bytearray(data);changed[-2]^=1
  self.assertFalse(within_reviewed_text_size(name,bytes(changed)))
  self.assertFalse(within_reviewed_text_size(name,data+b' '))
 def test_unreviewed_oversize_text_binary_and_payload_are_not_exempted(self):
  for data in (b'A'*(DEFAULT_TEXT_LIMIT+1),b'MZ'+b'\0'*499728,b' '*499730):
   self.assertFalse(within_reviewed_text_size(REVIEWED_PATH,data))
  self.assertTrue(within_reviewed_text_size('synthetic.txt',b'A'*DEFAULT_TEXT_LIMIT))
if __name__=='__main__':unittest.main()
