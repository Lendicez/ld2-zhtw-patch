import json,os,re,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ld2patch.catalog import validate_catalog,output_hash
from ld2patch.contracts import contract,validate,native_cp950
from ld2patch.patch_engine import build_patch,strict_json
from ld2patch.pe_resources import PE,parse_dialog,string_block,sha
from ld2patch import menu
def profile(name):
 p=ROOT/'patches'/name
 return (p/'catalog.json').read_bytes(),strict_json((p/'versions.json').read_bytes()),strict_json((p/'recipe.json').read_bytes())
def target(e):return(e['kind'],e['resource'],tuple(e.get('locator',[])),e.get('item_index'),e.get('index'))
class StaticClosureProfileTests(unittest.TestCase):
 def setUp(self):
  self.raw,self.v,self.recipe=profile('m042');self.cat=json.loads(self.raw);self.review=json.loads((ROOT/'patches/m042/review.json').read_bytes())
 def test_all_210_candidates_disjoint_and_prior_profiles_preserved(self):
  old=json.loads(profile('m041')[0]);self.assertEqual(self.cat['entries'][:418],old['entries']);self.assertEqual(self.cat['dialog_fonts'][:51],old['dialog_fonts'])
  groups=[self.review[k]for k in ['changes','identity_review_not_counted','preserved_identifiers','deferred']]
  self.assertEqual(list(map(len,groups)),[134,33,8,35]);keys=[target(x)for g in groups for x in g];self.assertEqual(len(set(keys)),210)
  self.assertEqual(validate_catalog(self.cat),552);self.assertEqual(len(self.cat['dialog_fonts']),71)
  self.assertEqual(len({e['translation']for e in groups[0]}),108)
  self.assertTrue(all(x['reason']for g in groups[1:]for x in g))
  self.assertEqual({(x['resource']-1)*16+x['index']for x in groups[2]},{32775,32777,32778,32779,32780,32781,32782,32783})
 def test_source_contracts_newline_roles_padding_and_arrows(self):
  rows={e['source_key']:e for e in self.review['changes']};old={target(x)for x in json.loads(profile('m041')[0])['entries']}
  for e in self.cat['entries'][418:]:
   with self.subTest(key=e['source_key']):
    s=rows[e['source_key']]['source_anchor'];t=e['translation'];self.assertNotIn(target(e),old);self.assertNotEqual(s,t)
    self.assertEqual(sha(s.encode('utf-16le')),e['source_utf16_sha256']);self.assertEqual(contract(s),e['contract']);validate(t,e['source_contract'])
    self.assertEqual(s.count('\n'),t.count('\n'));self.assertEqual(re.findall(r'<<|>>',s),re.findall(r'<<|>>',t))
    self.assertEqual(len(s)-len(s.rstrip(' ')),len(t)-len(t.rstrip(' ')));self.assertFalse(e['current_version_game_seen'])
 def test_1072_corrupted_translation_contracts_rejected(self):
  for e in self.cat['entries'][418:]:
   for suffix in ('%d','%s','%%','\n','\0','(&Q)','\tCtrl+Q','\U0001f642'):
    with self.subTest(key=e['source_key'],suffix=repr(suffix)),self.assertRaises((ValueError,UnicodeError)):validate(e['translation']+suffix,e['source_contract'])
 @unittest.skipUnless(sys.platform=='win32','Windows native conversion unavailable')
 def test_native_cp950_134_new_positions(self):
  for e in self.cat['entries'][418:]:self.assertEqual(native_cp950(e['translation']),len(e['translation'].encode('cp950')))
 def test_version_pin_and_runtime_limits(self):
  self.assertEqual(sha(self.raw),self.recipe['catalog_sha256']);self.assertEqual(output_hash(self.cat),'9fea1172e92167d435a8ec26baf085ab45a2a56468690bf7bfec1f8ba29dc367')
  self.assertEqual(output_hash(self.cat),self.v['versions'][0]['expected_output_sha256']);self.assertFalse(self.v['versions'][0]['release_approved'])
  self.assertFalse(self.review['m040_layout_included']);self.assertFalse(self.review['production_can_apply']);self.assertFalse(self.review['runtime_seen'])
  self.assertEqual(self.review['offscreen_fixed_measurements'],340);self.assertEqual(self.review['offscreen_intrinsic_measurements'],336)
  self.assertEqual(self.review['menu_accelerators'][0]['new_conflicts'],0)
 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m042 rebuild SKIPPED')
 def test_licensed_twice_reproducible_and_cross_profile_rejected(self):
  p=Path(os.environ['LD2_TEST_EXE']);b=p.read_bytes();a=build_patch(b,self.raw,self.v,self.recipe);z=build_patch(b,self.raw,self.v,self.recipe)
  self.assertEqual(a,z);self.assertEqual(len(a.output),7118848);self.assertEqual(sha(a.output),output_hash(self.cat));self.assertFalse(a.metadata['production_can_apply'])
  self.assertTrue(all(x['unchanged']for x in a.metadata['proof']['non_resource_sections']))
  raw,v,recipe=profile('m041')
  for args in [(raw,self.v,self.recipe),(self.raw,v,self.recipe),(self.raw,self.v,recipe)]:
   with self.assertRaises(ValueError):build_patch(b,*args)
  c=bytearray(b);c[4096]^=1
  with self.assertRaises(ValueError):build_patch(bytes(c),self.raw,self.v,self.recipe)
  self.assertEqual(p.read_bytes(),b)
 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m042 resource structure SKIPPED')
 def test_licensed_only_allowed_text_fonts_change_and_deferred_stay_exact(self):
  b=Path(os.environ['LD2_TEST_EXE']).read_bytes();a=PE(build_patch(b,*profile('m041')).output);z=PE(build_patch(b,self.raw,self.v,self.recipe).output)
  x={tuple(r['path']):a.payload(r)for r in a.resources};y={tuple(r['path']):z.payload(r)for r in z.resources};self.assertEqual(x.keys(),y.keys())
  changed={k for k in x if x[k]!=y[k]};self.assertEqual(changed,{tuple(k)for k in self.review['resources_changed_vs_m041']});self.assertEqual(x[(5,292,1041)],y[(5,292,1041)])
  for k in changed:
   if k[0]==4:self.assertEqual(menu.structure(menu.parse(x[k])),menu.structure(menu.parse(y[k])))
   if k[0]==5:
    aa,bb=parse_dialog(x[k]),parse_dialog(y[k]);self.assertEqual(aa['header'],bb['header']);self.assertEqual(aa['font_header'],bb['font_header'])
    title_keys={e['item_index']for e in self.review['changes']if e['kind']=='dialog_control' and e['resource']==k[1]}
    for i,(s,t)in enumerate(zip(aa['items'],bb['items'])):
     for key in ('header','class','extra'):self.assertEqual(s[key],t[key])
     if i not in title_keys:self.assertEqual(s['title'],t['title'])
   if k[0]==6:
    aa,bb=string_block(x[k]),string_block(y[k]);indices={e['index']for e in self.review['changes']if e['kind']=='string' and e['resource']==k[1]}
    for i in range(16):
     if i not in indices:self.assertEqual(aa[i],bb[i])
  for e in self.review['deferred']+self.review['preserved_identifiers']:
   kind=e['kind'];k=(6 if kind=='string' else 5,e['resource'],1041)
   if kind=='string':aa,bb=string_block(x[k])[e['index']],string_block(y[k])[e['index']]
   else:
    a,z=parse_dialog(x[k]),parse_dialog(y[k]);aa=a['title']if kind=='dialog_title'else a['items'][e['item_index']]['title'];bb=z['title']if kind=='dialog_title'else z['items'][e['item_index']]['title']
   self.assertEqual(aa,bb)
 @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m042 bounded binding proof SKIPPED')
 def test_licensed_descriptor_constructor_and_string_binding_evidence(self):
  b=Path(os.environ['LD2_TEST_EXE']).read_bytes();self.assertEqual(sha(b),self.cat['source_sha256']);p=PE(b);ev=self.review['binding_evidence']
  def call(site,target):
   s=int(site,16);self.assertEqual(b[s],0xe8);self.assertEqual(s+5+struct.unpack_from('<i',b,s+1)[0],int(target,16))
  for x in ev['descriptor_bindings']:
   k,cl,rid=struct.unpack_from('<3I',b,int(x['descriptor_file_offset'],16));self.assertEqual((k,rid),(x['kind'],x['dialog_resource']));self.assertEqual(p.off(cl-p.base),int(x['class_record_file_offset'],16));call(x['factory_call_file_offset'],x['constructor_file_offset'])
  for x in ev['page_bindings']+ev['direct_dialog_bindings']:
   s=int(x['resource_push_file_offset'],16);self.assertEqual(b[s],0x68);self.assertEqual(struct.unpack_from('<I',b,s+1)[0],x['dialog_resource']);call(x['base_call_file_offset'],x['base_function'])
  for x in ev['string_loads']:
   s=int(x['push_file_offset'],16);self.assertEqual(b[s],0x68);self.assertEqual(struct.unpack_from('<I',b,s+1)[0],x['string_id']);call(x['load_call_file_offset'],x['loader'])
  for x in ev['caption_stores']:self.assertEqual(struct.unpack_from('<I',b,int(x['store_file_offset'],16)+6)[0],x['string_id'])
if __name__=='__main__':unittest.main()
