import json,os,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.catalog import validate_catalog,output_hash
from ld2patch.contracts import contract,validate,native_cp950
from ld2patch.patch_engine import build_patch,strict_json
from ld2patch.pe_resources import PE,parse_dialog,sha

def read_profile(name):
    d=ROOT/'patches'/name
    return ((d/'catalog.json').read_bytes(),strict_json((d/'versions.json').read_bytes()),
            strict_json((d/'recipe.json').read_bytes()))

class TravelPartyQuestProfile(unittest.TestCase):
    def setUp(self):
        self.raw,self.versions,self.recipe=read_profile('m038')
        self.cat=json.loads(self.raw)
        self.review=strict_json((ROOT/'patches/m038/review.json').read_bytes())
        self.dynamic=strict_json((ROOT/'patches/m038/dynamic-boundary.json').read_bytes())

    def test_profile_preserves_all_prior_entries_and_keeps_release_disabled(self):
        previous=json.loads(read_profile('m037')[0])
        self.assertEqual(self.cat['entries'][:271],previous['entries'])
        self.assertEqual(self.cat['dialog_fonts'][:20],previous['dialog_fonts'])
        self.assertEqual(validate_catalog(self.cat),295)
        self.assertEqual(len(self.cat['dialog_fonts']),24)
        self.assertEqual(len(self.review['changes']),24)
        self.assertEqual(len({r['translation'] for r in self.review['changes']}),22)
        self.assertEqual(self.recipe['catalog_sha256'],sha(self.raw))
        self.assertEqual(output_hash(self.cat),self.versions['versions'][0]['expected_output_sha256'])
        self.assertFalse(self.versions['versions'][0]['release_approved'])
        self.assertNotEqual(output_hash(self.cat),output_hash(previous))

    def test_new_positions_are_disjoint_and_source_contracts_are_preserved(self):
        rows={r['source_key']:r for r in self.review['changes']}
        old={(r['kind'],r['resource'],r.get('item_index')) for r in self.cat['entries'][:271]}
        new=self.cat['entries'][271:]
        self.assertEqual(set(rows),{e['source_key'] for e in new})
        self.assertEqual({e['resource'] for e in new},{154,170,172,292})
        for e in new:
            with self.subTest(key=e['source_key']):
                r=rows[e['source_key']]
                self.assertNotIn((e['kind'],e['resource'],e.get('item_index')),old)
                self.assertNotEqual(r['source_anchor'],r['translation'])
                self.assertEqual(sha(r['source_anchor'].encode('utf-16le')),e['source_utf16_sha256'])
                self.assertEqual(contract(r['source_anchor']),contract(e['translation']))
                validate(e['translation'],e['source_contract'])
                self.assertFalse(e['current_version_game_seen'])
                self.assertFalse(e['contract']['printf'])
        self.assertTrue(all(not x['counted_as_translation'] for x in self.review['identity_review_not_counted']))

    def test_new_translation_contract_rejects_control_and_parameter_injection(self):
        e=self.cat['entries'][271]
        for suffix in ('\0','\n','%d','%s','%%','\tCtrl+Q','(&Z)'):
            with self.subTest(suffix=repr(suffix)),self.assertRaises((ValueError,UnicodeError)):
                validate(e['translation']+suffix,e['source_contract'])

    @unittest.skipUnless(sys.platform=='win32','Windows CP950 unavailable')
    def test_native_cp950_new_text_and_dynamic_format_remain_distinct_encodings(self):
        for e in self.cat['entries'][271:]:
            self.assertEqual(native_cp950(e['translation']),len(e['translation'].encode('cp950')))
        fmt=self.dynamic['source_format_anchor']
        self.assertNotEqual(fmt.encode('cp932'),fmt.encode('cp950'))
        self.assertEqual(contract(fmt),contract('%d 天'))
        for n in (-2147483648,0,2147483647):
            self.assertEqual(native_cp950('%d 天'%n),len(('%d 天'%n).encode('cp950')))

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m038 rebuild SKIPPED')
    def test_licensed_rebuild_reproducible_and_profile_mix_refused(self):
        path=Path(os.environ['LD2_TEST_EXE']);source=path.read_bytes()
        a=build_patch(source,self.raw,self.versions,self.recipe)
        b=build_patch(source,self.raw,self.versions,self.recipe)
        self.assertEqual(a,b)
        self.assertEqual(sha(a.output),output_hash(self.cat))
        self.assertEqual(len(a.output),7106560)
        self.assertFalse(a.metadata['production_can_apply'])
        self.assertTrue(all(x['unchanged'] for x in a.metadata['proof']['non_resource_sections']))
        raw,v,r=read_profile('m037')
        self.assertEqual(sha(build_patch(source,raw,v,r).output),'1fada3e7081de0797101bd61388cee20f2f2b38d796d9ef3fd892dac82e179d4')
        for mixed in ((raw,self.versions,self.recipe),(self.raw,v,self.recipe),(self.raw,self.versions,r)):
            with self.assertRaises(ValueError):build_patch(source,*mixed)
        self.assertEqual(path.read_bytes(),source)

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; resource boundaries SKIPPED')
    def test_licensed_only_four_new_resource_payloads_and_dynamic_fields_unchanged(self):
        source=Path(os.environ['LD2_TEST_EXE']).read_bytes()
        old=PE(build_patch(source,*read_profile('m037')).output)
        new=PE(build_patch(source,self.raw,self.versions,self.recipe).output)
        oldmap={tuple(r['path']):old.payload(r) for r in old.resources}
        newmap={tuple(r['path']):new.payload(r) for r in new.resources}
        self.assertEqual(oldmap.keys(),newmap.keys())
        changed={k for k in oldmap if oldmap[k]!=newmap[k]}
        self.assertEqual(changed,{(5,n,1041) for n in (154,170,172,292)})
        for k in changed:
            before,after=parse_dialog(oldmap[k]),parse_dialog(newmap[k])
            self.assertEqual(before['header'],after['header'])
            self.assertEqual(before['font_header'],after['font_header'])
            changed_indices={r['item_index'] for r in self.review['changes']
                             if r['resource']==k[1] and r['kind']=='dialog_control'}
            for i,(x,y) in enumerate(zip(before['items'],after['items'])):
                self.assertEqual({n:x[n] for n in ('header','class','extra')},{n:y[n] for n in ('header','class','extra')})
                if i not in changed_indices:self.assertEqual(x['title'],y['title'])

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; static associations SKIPPED')
    def test_licensed_dialog_descriptor_and_command_bindings(self):
        b=Path(os.environ['LD2_TEST_EXE']).read_bytes();self.assertEqual(sha(b),self.cat['source_sha256']);pe=PE(b)
        def call(site,target):
            self.assertEqual(b[site],0xe8)
            self.assertEqual(site+5+struct.unpack_from('<i',b,site+1)[0],target)
        for r in self.review['routes']:
            kind,cls,rid=struct.unpack_from('<3I',b,0x6476c0+12*r['dispatch_index'])
            self.assertEqual((kind,rid),(5,r['dialog_resource']))
            co=pe.off(cls-pe.base);n=pe.off(struct.unpack_from('<I',b,co)[0]-pe.base)
            self.assertEqual(b[n:b.index(0,n)].decode(),r['class_name'])
            self.assertEqual(struct.unpack_from('<I',b,co+12)[0]-pe.base,int(r['factory_file_offset'],16))
            call(int(r['factory_call_file_offset'],16),int(r['constructor_file_offset'],16))
            site=int(r['dispatch_call_file_offset'],16)
            self.assertEqual(b[site-2:site],bytes([0x6a,r['dispatch_index']]))
            call(site,0xd0530)
            if 'command_id' in r:
                table=int(r['command_table_file_offset'],16)
                self.assertEqual(struct.unpack_from('<I',b,table+4*(r['command_id']-r['command_first']))[0]-pe.base,int(r['branch_file_offset'],16))
            else:
                self.assertEqual(struct.unpack_from('<I',b,int(r['parent_vtable_file_offset'],16)+r['virtual_slot'])[0]-pe.base,int(r['detail_handler_file_offset'],16))
                self.assertEqual(struct.unpack_from('<6I',b,int(r['parent_message_map_file_offset'],16)),(0x111,0,1,1,0x38,0x492000))
                call(int(r['populate_call_file_offset'],16),int(r['populate_function_file_offset'],16))

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; dynamic boundary SKIPPED')
    def test_licensed_dynamic_format_and_ansi_setter_are_unmodified(self):
        b=Path(os.environ['LD2_TEST_EXE']).read_bytes();d=self.dynamic
        at=int(d['format_file_offset'],16);raw=b[at:b.index(0,at)]
        self.assertEqual(sha(raw),d['source_bytes_sha256'])
        self.assertEqual(raw.decode('cp932'),d['source_format_anchor'])
        p=int(d['format_push_file_offset'],16)
        self.assertEqual(b[p],0x68);self.assertEqual(struct.unpack_from('<I',b,p+1)[0],0x400000+at)
        s=int(d['setter_call_file_offset'],16)
        self.assertEqual(b[s],0xe8)
        self.assertEqual(s+5+struct.unpack_from('<i',b,s+1)[0],int(d['setter_wrapper_file_offset'],16))
        self.assertEqual(struct.unpack_from('<I',b,0xea6b2)[0],int(d['setter_import_slot'],16))
        self.assertEqual(d['status'],'static_analysis_only_unmodified')

if __name__=='__main__':unittest.main()

