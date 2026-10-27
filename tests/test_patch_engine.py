import copy,json,os,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.catalog import validate_catalog
from ld2patch.patch_engine import build_patch,build_to_paths,file_versions,metadata_bytes,resource_paths,strict_json,verify_resource_only
from ld2patch.pe_resources import Builder,PE,MAX_RESOURCE,parse_dialog,sha,string_block
from pe_fixture import bundle,synthetic_pe
from test_core import synthetic_dialog


class PatchEngine(unittest.TestCase):
    def setUp(self):
        self.source,self.catalog,self.versions,self.recipe,self.expected=bundle()

    def build(self,**changes):
        args=dict(source=self.source,catalog_bytes=self.catalog,versions=self.versions,recipe=self.recipe);args.update(changes)
        return build_patch(**args)

    def test_reproducible_build_and_code_data_proof(self):
        a=self.build();b=self.build()
        self.assertEqual(a.output,self.expected);self.assertEqual(a,b)
        self.assertEqual(metadata_bytes(a.metadata),metadata_bytes(b.metadata))
        self.assertEqual([x['name'] for x in a.metadata['proof']['non_resource_sections']],['.text','.data'])
        self.assertFalse(a.metadata['production_can_apply']);self.assertFalse(a.metadata['coverage_established'])
        self.assertEqual(file_versions(PE(a.output)),('1.2.3.4','1.2.3.0'))

    def test_unknown_original_even_same_version_refused(self):
        changed=bytearray(self.source);changed[600]^=1
        with self.assertRaisesRegex(ValueError,'original hash'):self.build(source=bytes(changed))

    def test_catalog_recipe_binding_refuses_injection(self):
        cat=json.loads(self.catalog);cat['entries'][0]['translation']='\u5176\u4ed6 %d'
        with self.assertRaisesRegex(ValueError,'recipe hash'):self.build(catalog_bytes=json.dumps(cat).encode())

    def test_rebound_catalog_still_must_match_historical_output(self):
        cat=json.loads(self.catalog);cat['entries'][0]['translation']='\u5176\u4ed6 %d'
        raw=json.dumps(cat).encode();recipe=dict(self.recipe,catalog_sha256=sha(raw))
        with self.assertRaisesRegex(ValueError,'reviewed m020'):self.build(catalog_bytes=raw,recipe=recipe)

    def test_pe_file_and_product_version_must_match(self):
        for key in ['file_version','product_version']:
            with self.subTest(key=key):
                versions=copy.deepcopy(self.versions);versions['versions'][0][key]='9.9.9.9'
                with self.assertRaisesRegex(ValueError,'PE version'):self.build(versions=versions)

    def test_recipe_counts_paths_and_schema_refused(self):
        for mutation in [{'schema_version':True},{'text_locations':2},{'catalog':'../synthetic.json'},{'engine':'arbitrary_patch'}]:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.build(recipe=dict(self.recipe,**mutation))

    def test_json_duplicate_key_and_budget_refused(self):
        for raw in [b'{"a":1,"a":2}',b'{"n":NaN}',b'\xff',b'x'*100]:
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError):strict_json(raw,limit=64)

    def test_catalog_negative_bool_duplicate_locator_and_raw_injection(self):
        original=json.loads(self.catalog)
        variants=[]
        for key,value in [('index',-1),('index',True),('resource',65536),('raw','unreviewed')]:
            c=copy.deepcopy(original);c['entries'][0][key]=value;variants.append(c)
        c=copy.deepcopy(original);c['entries'].append(dict(c['entries'][0],source_key='different-context'));variants.append(c)
        c=copy.deepcopy(original);c['schema_version']=True;variants.append(c)
        for c in variants:
            with self.subTest(entry=c['entries'][0]),self.assertRaises(ValueError):validate_catalog(c)

    def test_code_data_change_rejected_even_without_output_hash_gate(self):
        b=bytearray(self.expected);b[600]^=1
        with self.assertRaisesRegex(ValueError,'outside resource/header'):verify_resource_only(self.source,bytes(b),{(6,1,1041)})

    def test_unapproved_resource_type_or_path_refused(self):
        with self.assertRaisesRegex(ValueError,'Unapproved'):verify_resource_only(self.source,self.expected,set())

    def test_explicit_output_and_metadata_no_input_change(self):
        with tempfile.TemporaryDirectory(prefix='ld2-build-synthetic-') as tmp:
            root=Path(tmp).resolve();(root/'input').mkdir();(root/'build').mkdir()
            source=root/'input'/'original.exe';source.write_bytes(self.source)
            output=root/'build'/'patch.exe';metadata=root/'build'/'metadata.json'
            m=build_to_paths(source,output,metadata,self.catalog,self.versions,self.recipe)
            self.assertEqual(source.read_bytes(),self.source);self.assertEqual(output.read_bytes(),self.expected)
            self.assertEqual(json.loads(metadata.read_bytes()),m)
            with self.assertRaisesRegex(ValueError,'Existing output'):build_to_paths(source,output,metadata,self.catalog,self.versions,self.recipe)
            self.assertEqual(output.read_bytes(),self.expected)

    def test_inplace_original_directory_and_existing_metadata_refused(self):
        with tempfile.TemporaryDirectory(prefix='ld2-build-synthetic-') as tmp:
            root=Path(tmp).resolve();(root/'input').mkdir();(root/'build').mkdir()
            source=root/'input'/'original.exe';source.write_bytes(self.source)
            for output,metadata in [(source,source.with_suffix('.json')),(source.parent/'other.exe',source.parent/'other.json')]:
                with self.assertRaises(ValueError):build_to_paths(source,output,metadata,self.catalog,self.versions,self.recipe)
            output=root/'build'/'new.exe';metadata=root/'build'/'keep.json';metadata.write_bytes(b'KEEP')
            with self.assertRaises(ValueError):build_to_paths(source,output,metadata,self.catalog,self.versions,self.recipe)
            self.assertFalse(output.exists());self.assertEqual(metadata.read_bytes(),b'KEEP');self.assertEqual(source.read_bytes(),self.source)

    def test_failed_build_creates_no_output(self):
        with tempfile.TemporaryDirectory(prefix='ld2-build-synthetic-') as tmp:
            root=Path(tmp).resolve();(root/'input').mkdir();(root/'build').mkdir()
            source=root/'input'/'bad.exe';source.write_bytes(b'UNKNOWN')
            output=root/'build'/'out.exe';metadata=root/'build'/'out.json'
            with self.assertRaises(ValueError):build_to_paths(source,output,metadata,self.catalog,self.versions,self.recipe)
            self.assertFalse(output.exists());self.assertFalse(metadata.exists())


class MalformedPE(unittest.TestCase):
    def setUp(self):
        self.source,_=synthetic_pe();self.pe=PE(self.source)

    def altered(self,offset,value,size=4):
        b=bytearray(self.source);struct.pack_into('<I' if size==4 else '<H',b,offset,value);return bytes(b)

    def test_truncation_and_header_count_offset_budgets(self):
        cases=[self.source[:256],self.source[:-1],self.altered(60,0xffffffff),self.altered(self.pe.pe+6,65535,2),self.altered(self.pe.opt,0x20b,2),self.altered(self.pe.opt+36,0)]
        for b in cases:
            with self.subTest(size=len(b)),self.assertRaises(ValueError):PE(b)

    def test_raw_and_virtual_section_overlap(self):
        second=self.pe.sections[1];first=self.pe.sections[0]
        for offset,value in [(second['header']+20,first['rp']),(second['header']+12,first['va'])]:
            with self.subTest(offset=offset),self.assertRaisesRegex(ValueError,'Overlapping'):PE(self.altered(offset,value))

    def test_virtual_only_bytes_are_not_file_backed(self):
        second=self.pe.sections[1];pe=PE(self.altered(second['header']+8,1024))
        with self.assertRaisesRegex(ValueError,'backed'):pe.off(second['va']+700)

    def test_cycle_duplicate_sibling_and_entry_budget(self):
        rb=self.pe.rb
        for offset,value,size in [(rb+20,0x80000000,4),(rb+24,6,4),(rb+14,65535,2)]:
            with self.subTest(offset=offset),self.assertRaises(ValueError):PE(self.altered(offset,value,size))

    def test_resource_overlap_outside_section_and_size_limit(self):
        a,b=self.pe.resources
        for offset,value in [(b['entry'],self.pe.resource_rva+a['offset']-self.pe.rb),(a['entry'],0x1000),(a['entry']+4,MAX_RESOURCE+1),(a['entry']+4,len(self.source))]:
            with self.subTest(offset=offset,value=value),self.assertRaises(ValueError):PE(self.altered(offset,value))

    def test_resource_directory_truncation_and_leaf_depth(self):
        for offset,value in [(self.pe.opt+116,16),(self.pe.rb+20,self.pe.resources[0]['entry']-self.pe.rb)]:
            with self.subTest(offset=offset),self.assertRaises(ValueError):PE(self.altered(offset,value))

    def test_dialog_and_string_lengths_are_bounded(self):
        d=bytearray(synthetic_dialog());struct.pack_into('<H',d,8,65535)
        for raw,parse in [(bytes(d),parse_dialog),(synthetic_dialog()[:-10],parse_dialog),(b'\xff\xff',string_block)]:
            with self.assertRaises(ValueError):parse(raw)

    def test_builder_code_patch_overlap_and_append_budget_refused(self):
        b=Builder(self.source,sha(self.source))
        with self.assertRaises(ValueError):b.patch(512,self.source[512:520],b'12345678','code')
        r=self.pe.resources[0];raw=self.pe.payload(r)+b'\0\0'
        b.resource(r['path'],raw)
        with self.assertRaises(ValueError):b.resource(r['path'],raw)
        with self.assertRaises(ValueError):b.append(b'x'*(MAX_RESOURCE+1))


class LicensedPatch(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; offline engine integration SKIPPED')
    def test_real_m020_exact_and_resource_only(self):
        source=Path(os.environ['LD2_TEST_EXE']).read_bytes()
        catalog=(ROOT/'patches/ui-m020.zh-TW.json').read_bytes()
        versions=strict_json((ROOT/'patches/versions.json').read_bytes());recipe=strict_json((ROOT/'patches/m020-recipe.json').read_bytes())
        a=build_patch(source,catalog,versions,recipe);b=build_patch(source,catalog,versions,recipe)
        self.assertEqual(a,b);self.assertEqual(len(a.output),7102464)
        self.assertEqual(sha(a.output),'a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81')
        self.assertEqual(a.metadata['text_locations'],239);self.assertEqual(a.metadata['font_locations'],15)
        self.assertTrue(all(x['unchanged'] for x in a.metadata['proof']['non_resource_sections']))
        self.assertEqual(sha(source),a.metadata['source_sha256'])


if __name__=='__main__':unittest.main()
