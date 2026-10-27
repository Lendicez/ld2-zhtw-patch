import copy,json,os,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.catalog import validate_catalog,output_hash
from ld2patch.contracts import contract,validate,native_cp950
from ld2patch.patch_engine import build_patch,strict_json
from ld2patch.pe_resources import PE,sha
from ld2patch.planner import _versions
from pe_fixture import bundle


def profile():
    d=ROOT/'patches/m037'
    return ((d/'catalog.json').read_bytes(),strict_json((d/'versions.json').read_bytes()),
            strict_json((d/'recipe.json').read_bytes()),strict_json((d/'review.json').read_bytes()))


class OfflineProfileV2(unittest.TestCase):
    def setUp(self):
        self.source,raw,versions,recipe,self.expected=bundle()
        cat=json.loads(raw);cat['schema_version']=2
        cat['expected_output_sha256']=cat.pop('historical_m020_sha256')
        v=versions['versions'][0]
        v['expected_output_sha256']=v.pop('historical_m020_sha256')
        v['expected_output_size']=v.pop('historical_m020_size')
        versions.update(schema_version=2,steam_app_id_status='synthetic')
        self.raw=json.dumps(cat).encode();self.versions=versions
        self.recipe=dict(recipe,schema_version=2,catalog_sha256=sha(self.raw))

    def build(self,**override):
        args=dict(source=self.source,catalog_bytes=self.raw,versions=self.versions,recipe=self.recipe)
        args.update(override);return build_patch(**args)

    def test_v2_exact_output_reproducible(self):
        a=self.build();b=self.build();self.assertEqual(a,b);self.assertEqual(a.output,self.expected)
        self.assertFalse(a.metadata['production_can_apply']);self.assertFalse(a.metadata['runtime_tested'])

    def test_old_profile_preserved_and_no_implicit_schema_mix(self):
        source,raw,versions,recipe,expected=bundle()
        self.assertEqual(build_patch(source,raw,versions,recipe).output,expected)
        for changes in ({'versions':versions},{'catalog_bytes':raw,'recipe':dict(self.recipe,catalog_sha256=sha(raw))},
                        {'recipe':dict(self.recipe,schema_version=1)}):
            with self.subTest(changes=changes.keys()),self.assertRaises(ValueError):self.build(**changes)

    def test_v2_not_accepted_by_production_planner(self):
        with self.assertRaisesRegex(ValueError,'unsupported_version_schema'):_versions(self.versions)

    def test_rebound_catalog_still_cannot_change_reviewed_output(self):
        cat=json.loads(self.raw);cat['entries'][0]['translation']='另一範例 %d';raw=json.dumps(cat).encode()
        with self.assertRaisesRegex(ValueError,'reviewed profile'):
            self.build(catalog_bytes=raw,recipe=dict(self.recipe,catalog_sha256=sha(raw)))

    def test_unknown_source_and_bad_output_size_refused(self):
        v=copy.deepcopy(self.versions);v['versions'][0]['expected_output_size']+=1
        with self.assertRaisesRegex(ValueError,'Reviewed output mismatch'):self.build(versions=v)
        with self.assertRaisesRegex(ValueError,'original hash'):self.build(source=self.source[:-1])

    def test_v2_whitelist_fields_release_and_hash_rejected(self):
        mutations=[('release_approved',True),('expected_output_sha256','0'*64),('expected_output_size',True),('unexpected','x')]
        for key,value in mutations:
            v=copy.deepcopy(self.versions);v['versions'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.build(versions=v)
        v=copy.deepcopy(self.versions);v['versions']*=2
        with self.assertRaises(ValueError):self.build(versions=v)

    def test_mixed_catalog_fields_and_bool_schema_refused(self):
        for mutation in [{'schema_version':True},{'schema_version':3},{'historical_m020_sha256':'0'*64}]:
            cat=json.loads(self.raw);cat.update(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate_catalog(cat)


class CombatCatalog(unittest.TestCase):
    def setUp(self):self.raw,self.versions,self.recipe,self.review=profile();self.cat=json.loads(self.raw)

    def test_exact_counts_preserve_prior_entries_and_fonts(self):
        old=json.loads((ROOT/'patches/ui-m020.zh-TW.json').read_bytes())
        self.assertEqual(self.cat['entries'][:239],old['entries'])
        self.assertEqual(self.cat['dialog_fonts'][:15],old['dialog_fonts'])
        self.assertEqual(validate_catalog(self.cat),271);self.assertEqual(len(self.cat['dialog_fonts']),20)
        self.assertEqual(len(self.review['changes']),32);self.assertEqual(self.review['new_locations'],32)
        self.assertEqual(self.review['identity_review_not_counted'][0]['text'],'特殊技能：')
        self.assertEqual(self.recipe['catalog_sha256'],sha(self.raw))
        self.assertEqual(output_hash(self.cat),self.versions['versions'][0]['expected_output_sha256'])
        self.assertFalse(self.versions['versions'][0]['release_approved'])

    def test_all_new_anchors_and_preserved_format_contracts(self):
        rows={r['source_key']:r for r in self.review['changes']}
        entries=self.cat['entries'][239:]
        self.assertEqual(set(rows),{e['source_key'] for e in entries})
        for e in entries:
            r=rows[e['source_key']]
            self.assertNotEqual(r['source_anchor'],r['translation'])
            self.assertEqual(e['source_utf16_sha256'],sha(r['source_anchor'].encode('utf-16le')))
            self.assertEqual(contract(r['source_anchor']),contract(e['translation']))
            validate(e['translation'],e['source_contract'])
            self.assertFalse(e['current_version_game_seen'])
        self.assertEqual(sum(bool(e['contract']['controls']) for e in entries),8)
        self.assertEqual(sum(bool(e['contract']['mnemonics']) for e in entries),5)

    @unittest.skipUnless(sys.platform=='win32','Windows CP950 unavailable')
    def test_all_new_native_cp950_roundtrips(self):
        for e in self.cat['entries'][239:]:self.assertEqual(native_cp950(e['translation']),len(e['translation'].encode('cp950')))

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m037 rebuild SKIPPED')
    def test_licensed_rebuild_and_old_reference_exact(self):
        source=Path(os.environ['LD2_TEST_EXE']).read_bytes();before=sha(source)
        a=build_patch(source,self.raw,self.versions,self.recipe);b=build_patch(source,self.raw,self.versions,self.recipe)
        self.assertEqual(a,b);self.assertEqual(sha(a.output),output_hash(self.cat))
        self.assertTrue(all(x['unchanged'] for x in a.metadata['proof']['non_resource_sections']))
        raw=(ROOT/'patches/ui-m020.zh-TW.json').read_bytes()
        old=build_patch(source,raw,strict_json((ROOT/'patches/versions.json').read_bytes()),strict_json((ROOT/'patches/m020-recipe.json').read_bytes()))
        self.assertEqual(sha(old.output),'a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81')
        self.assertEqual(before,sha(Path(os.environ['LD2_TEST_EXE']).read_bytes()))

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; static route anchors SKIPPED')
    def test_licensed_command_table_class_factory_anchors(self):
        b=Path(os.environ['LD2_TEST_EXE']).read_bytes();self.assertEqual(sha(b),self.cat['source_sha256']);pe=PE(b)
        self.assertEqual(struct.unpack_from('<6I',b,0x159e60),(0x111,0,0x8061,0x806b,0x3a,0x488350))
        for r in self.review['routes']:
            idx=r['dispatch_index'];cmd=r['command_id'];branch=int(r['branch_file_offset'],16);site=int(r['dispatch_call_file_offset'],16)
            self.assertEqual(struct.unpack_from('<I',b,0x88610+4*(cmd-32866))[0],pe.base+branch)
            self.assertEqual(b[site-2:site],bytes([0x6a,idx]));self.assertEqual(b[site],0xe8)
            self.assertEqual(site+5+struct.unpack_from('<i',b,site+1)[0],0xd0530)
            kind,cls,rid=struct.unpack_from('<3I',b,0x6476c0+12*idx)
            self.assertEqual((kind,rid),(5,r['dialog_resource']))
            off=pe.off(cls-pe.base);n=pe.off(struct.unpack_from('<I',b,off)[0]-pe.base)
            self.assertEqual(b[n:b.index(0,n)].decode(),r['class_name'])
            self.assertEqual(struct.unpack_from('<I',b,off+12)[0]-pe.base,int(r['factory_file_offset'],16))


if __name__=='__main__':unittest.main()
