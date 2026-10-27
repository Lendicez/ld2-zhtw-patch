import unittest,struct,hashlib,json,os,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch import menu
from ld2patch.contracts import contract,validate,verify_source,native_cp950
from ld2patch.catalog import validate_catalog,build_bytes
from ld2patch.pe_resources import parse_dialog,encode_dialog,string_block,encode_string_block,Builder,PE
from ld2patch.steam_vdf import parse,libraries,app_manifest
def synthetic_dialog():
    # Entirely invented classic dialog, not copied from any game resource.
    header=struct.pack('<IIHhhhh',0x40,0,1,0,0,100,50)
    field=lambda s:s.encode('utf-16le')+b'\0\0'
    b=header+b'\0\0'*2+field('Synthetic')+struct.pack('<H',12)+field('SyntheticFont')
    b+=b'\0'*((-len(b))%4)
    b+=struct.pack('<IIhhhhH',0,0,1,1,80,20,101)+b'\xff\xff\x82\0'+field('Example')+b'\0\0'
    return b
class Contracts(unittest.TestCase):
    def test_positive(self):
        for a,b in [('%d %s %%','數字 %d 名稱 %s %%'),('%1 to %2','%1 至 %2'),('A&&B(&A)\tCtrl+A','甲&&乙(&A)\tCtrl+A')]:validate(b,contract(a))
    def test_negative_contracts(self):
        for a,b in [('%d','%s'),('%04d','%d'),('%.2f','%.3f'),('%1 %2','%2 %1'),('%1!s!','%1!d!'),('%%','%'),('a\nb','ab'),('a(&A)','b(&B)'),('a\tCtrl+A','b\tCtrl+B'),('A&&B','AB')]:
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):validate(b,contract(a))
    def test_empty_nul_replacement_unicode(self):
        for text in ['', 'a\0b','\ufffd','\ud800','😀']:
            with self.subTest(text=repr(text)),self.assertRaises((ValueError,UnicodeError)):validate(text,contract('abc'))
    def test_capacity(self):
        with self.assertRaises(ValueError):validate('錄檔',contract('abc'),max_utf16_units=1)
    def test_source_hash(self):
        verify_source('synthetic',hashlib.sha256('synthetic'.encode('utf-16le')).hexdigest())
        with self.assertRaises(ValueError):verify_source('other','0'*64)
    def test_no_write_conversion(self):self.assertEqual(validate('錄檔',contract('abc')),4)
    @unittest.skipUnless(sys.platform=='win32','Windows native API unavailable')
    def test_windows_native(self):
        self.assertEqual(native_cp950('錄檔'),4)
        with self.assertRaises(ValueError):native_cp950('😀')
class Resources(unittest.TestCase):
    def test_synthetic_dialog_roundtrip(self):
        raw=synthetic_dialog();self.assertEqual(encode_dialog(parse_dialog(raw)),raw)
    def test_synthetic_dialog_long_text(self):
        d=parse_dialog(synthetic_dialog());header=d['items'][0]['header'];d['items'][0]['title']['text']='較長的記錄檔文字'
        result=parse_dialog(encode_dialog(d));self.assertEqual(result['items'][0]['header'],header);self.assertEqual(result['items'][0]['title']['text'],'較長的記錄檔文字')
    def test_string_block(self):
        data=['錄檔','%d %s %%']+['']*14;self.assertEqual(string_block(encode_string_block(data)),data)
        with self.assertRaises(ValueError):encode_string_block(['x'])
    def test_menu(self):
        d={'header':'00000000','items':[{'flags':128,'id':101,'text':'合成(&A)'}],'trailing':''}
        self.assertEqual(menu.parse(menu.encode(d)),d)
        with self.assertRaises(ValueError):menu.parse(b'\0')
    def test_bad_pe_version(self):
        with self.assertRaises(ValueError):Builder(b'synthetic','0'*64)
        with self.assertRaises(ValueError):PE(b'synthetic')
class Catalog(unittest.TestCase):
    def setUp(self):self.cat=json.loads((ROOT/'patches/ui-m020.zh-TW.json').read_text(encoding='utf-8'))
    def test_catalog(self):self.assertEqual(validate_catalog(self.cat),239)
    def test_duplicate_context(self):
        self.cat['entries'].append(copy.deepcopy(self.cat['entries'][0]))
        with self.assertRaises(ValueError):validate_catalog(self.cat)
    def test_no_source_assets(self):
        for e in self.cat['entries']:
            self.assertNotIn('original',e);self.assertNotIn('original_hex',e)
    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed game input not provided; integration SKIPPED')
    def test_private_game_in_memory(self):
        source=Path(os.environ['LD2_TEST_EXE']).read_bytes();a=build_bytes(source,self.cat);b=build_bytes(source,self.cat)
        self.assertEqual(a,b);self.assertEqual(hashlib.sha256(a).hexdigest(),self.cat['historical_m020_sha256'])
        with self.assertRaises(ValueError):build_bytes(source[:-1]+bytes([source[-1]^1]),self.cat)
class Steam(unittest.TestCase):
    def test_libraries_modern_and_legacy(self):
        self.assertEqual(libraries(parse('"libraryfolders" {"0" {"path" "C:\\\\SyntheticSteam"} "1" {"path" "D:\\\\SyntheticGames"}}')),['C:\\SyntheticSteam','D:\\SyntheticGames'])
        self.assertEqual(libraries(parse('"LibraryFolders" {"1" "D:\\\\SyntheticGames"}')),['D:\\SyntheticGames'])
    def test_synthetic_appid_not_real_game(self):
        self.assertEqual(app_manifest(parse('"AppState" {"appid" "1234567890" "installdir" "SyntheticGame"}'))['appid'],'1234567890')
    def test_unsafe_manifest(self):
        for folder in ['..','../x','C:\\x','a/b']:
            with self.subTest(folder=folder),self.assertRaises(ValueError):app_manifest({'AppState':{'appid':'1','installdir':folder}})
    def test_malformed_duplicate(self):
        for text in ['"a" {','"a" "b" "a" "c"','garbage','}']:
            with self.subTest(text=text),self.assertRaises(ValueError):parse(text)
if __name__=='__main__':unittest.main()
