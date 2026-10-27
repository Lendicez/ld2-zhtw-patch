import copy,json,os,re,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.catalog import validate_catalog,output_hash
from ld2patch.contracts import contract,validate,native_cp950
from ld2patch.patch_engine import build_patch,strict_json
from ld2patch.pe_resources import PE,parse_dialog,sha

def profile(name):
 d=ROOT/'patches'/name
 return ((d/'catalog.json').read_bytes(),strict_json((d/'versions.json').read_bytes()),strict_json((d/'recipe.json').read_bytes()))

def target(e):
 return (e['kind'],e['resource'],e['language'],tuple(e.get('locator',[])),e.get('item_index'),e.get('index'))

class FacilityProfileTests(unittest.TestCase):
 def setUp(self):
  self.raw,self.versions,self.recipe=profile('m041');self.cat=json.loads(self.raw)
  self.review=json.loads((ROOT/'patches/m041/review.json').read_bytes())

 def test_all_171_candidates_have_one_disjoint_disposition(self):
  old=json.loads(profile('m038')[0]);self.assertEqual(self.cat['entries'][:295],old['entries'])
  self.assertEqual(self.cat['dialog_fonts'][:24],old['dialog_fonts'])
  changed=self.review['changes'];same=self.review['identity_review_not_counted'];deferred=self.review['deferred']
  self.assertEqual((len(changed),len(same),len(deferred)),(123,39,9))
  keys=[(r['kind'],r['resource'],r.get('item_index'))for r in changed+same+deferred]
  self.assertEqual(len(keys),len(set(keys)));self.assertEqual(len(keys),171)
  self.assertEqual({r['resource']for r in deferred},{462,464})
  self.assertTrue(all(r['reason']for r in deferred))
  self.assertEqual(len({r['translation']for r in changed}),77)
  self.assertEqual(validate_catalog(self.cat),418)
  self.assertEqual(len(self.cat['dialog_fonts']),51)
  self.assertEqual(len({r['resource']for r in changed+same}),27)
  self.assertTrue(all(not r['counted_as_translation']for r in same))

 def test_source_anchor_contracts_padding_arrows_and_new_locations(self):
  old={target(r)for r in json.loads(profile('m038')[0])['entries']}
  rows={r['source_key']:r for r in self.review['changes']}
  for e in self.cat['entries'][295:]:
   with self.subTest(key=e['source_key']):
    r=rows[e['source_key']];self.assertNotIn(target(e),old)
    self.assertNotEqual(r['source_anchor'],e['translation'])
    self.assertEqual(sha(r['source_anchor'].encode('utf-16le')),e['source_utf16_sha256'])
    self.assertEqual(contract(r['source_anchor']),e['contract']);validate(e['translation'],e['source_contract'])
    self.assertEqual(re.findall(r'<<|>>',r['source_anchor']),re.findall(r'<<|>>',e['translation']))
    self.assertEqual(len(r['source_anchor'])-len(r['source_anchor'].rstrip(' ')),len(e['translation'])-len(e['translation'].rstrip(' ')))
    self.assertFalse(e['current_version_game_seen']);self.assertFalse(e['contract']['printf'])
    self.assertFalse(e['contract']['mnemonics'])

 def test_all_new_rows_reject_parameter_control_mnemonic_and_encoding_corruption(self):
  for e in self.cat['entries'][295:]:
   for suffix in ('%d','%s','%%','\n','\0','(&Q)','\tCtrl+Q','\U0001f642'):
    with self.subTest(key=e['source_key'],suffix=repr(suffix)),self.assertRaises((ValueError,UnicodeError)):
     validate(e['translation']+suffix,e['source_contract'])

 @unittest.skipUnless(sys.platform=='win32','Windows native CP950 unavailable')
 def test_native_cp950_all_new_text_is_reversible(self):
  for e in self.cat['entries'][295:]:self.assertEqual(native_cp950(e['translation']),len(e['translation'].encode('cp950')))

 def test_version_recipe_and_layout_candidate_are_separate(self):
  self.assertEqual(self.recipe['catalog_sha256'],sha(self.raw))
  self.assertEqual(output_hash(self.cat),self.versions['versions'][0]['expected_output_sha256'])
  self.assertEqual(output_hash(self.cat),'bedee9b18527f1f3a3a264ac175fa968ce24bf41beb6070a82988eeaf6cd5177')
  self.assertFalse(self.versions['versions'][0]['release_approved'])
  self.assertFalse(self.review['m040_layout_included']);self.assertFalse(self.review['production_can_apply'])
  self.assertNotIn(292,{e['resource']for e in self.cat['entries'][295:]})
  self.assertEqual(self.review['gdi_memory_only_measurements'],540)
  self.assertEqual(self.review['layout_flags'],0)

 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m041 rebuild SKIPPED')
 def test_licensed_rebuild_twice_and_profile_mix_refused(self):
  p=Path(os.environ['LD2_TEST_EXE']);b=p.read_bytes()
  a=build_patch(b,self.raw,self.versions,self.recipe);c=build_patch(b,self.raw,self.versions,self.recipe)
  self.assertEqual(a,c);self.assertEqual(len(a.output),7114752);self.assertEqual(sha(a.output),output_hash(self.cat))
  self.assertFalse(a.metadata['production_can_apply'])
  self.assertTrue(all(x['unchanged']for x in a.metadata['proof']['non_resource_sections']))
  raw,v,r=profile('m038')
  for args in ((raw,self.versions,self.recipe),(self.raw,v,self.recipe),(self.raw,self.versions,r)):
   with self.assertRaises(ValueError):build_patch(b,*args)
  changed=bytearray(b);changed[4096]^=1
  with self.assertRaises(ValueError):build_patch(bytes(changed),self.raw,self.versions,self.recipe)
  self.assertEqual(p.read_bytes(),b)

 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m041 resource proof SKIPPED')
 def test_licensed_only_27_dialog_payloads_change_no_geometry_or_m040_overlay(self):
  b=Path(os.environ['LD2_TEST_EXE']).read_bytes();old=PE(build_patch(b,*profile('m038')).output)
  new=PE(build_patch(b,self.raw,self.versions,self.recipe).output)
  x={tuple(r['path']):old.payload(r)for r in old.resources};y={tuple(r['path']):new.payload(r)for r in new.resources}
  self.assertEqual(x.keys(),y.keys());changed={k for k in x if x[k]!=y[k]}
  self.assertEqual(changed,{(5,r,1041)for r in self.review['reviewed_dialog_resources']})
  self.assertEqual(x[(5,292,1041)],y[(5,292,1041)])
  self.assertEqual(x[(5,462,1041)],y[(5,462,1041)]);self.assertEqual(x[(5,464,1041)],y[(5,464,1041)])
  for k in changed:
   a,c=parse_dialog(x[k]),parse_dialog(y[k]);self.assertEqual(a['header'],c['header']);self.assertEqual(a['font_header'],c['font_header'])
   indices={e['item_index']for e in self.review['changes']if e['kind']=='dialog_control'and e['resource']==k[1]}
   for i,(s,t)in enumerate(zip(a['items'],c['items'])):
    for field in ('header','class','extra'):self.assertEqual(s[field],t[field])
    if i not in indices:self.assertEqual(s['title'],t['title'])

 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m041 class/template bindings SKIPPED')
 def test_licensed_class_factory_constructor_template_bindings(self):
  b=Path(os.environ['LD2_TEST_EXE']).read_bytes();self.assertEqual(sha(b),self.cat['source_sha256']);p=PE(b)
  def call(site,target):
   self.assertEqual(b[site],0xe8);self.assertEqual(site+5+struct.unpack_from('<i',b,site+1)[0],target)
  for r in self.review['routes']:
   co=int(r['class_record_file_offset'],16);n=p.off(struct.unpack_from('<I',b,co)[0]-p.base)
   self.assertEqual(b[n:b.index(0,n)].decode(),r['class_name'])
   self.assertEqual(struct.unpack_from('<I',b,co+12)[0]-p.base,int(r['factory_file_offset'],16))
   call(int(r['factory_call_file_offset'],16),int(r['constructor_file_offset'],16))
   call(int(r['base_page_call_file_offset'],16),0x31860)
   at=int(r['resource_push_file_offset'],16);self.assertEqual(b[at],0x68)
   self.assertEqual(struct.unpack_from('<I',b,at+1)[0],r['dialog_resource'])
  dark=next(r for r in self.review['routes']if r['class_name']=='CShopDarkInfoPage')
  self.assertEqual(dark['dialog_resource'],142)
  call(0x318a8,0xf0d0e)

if __name__=='__main__':unittest.main()
