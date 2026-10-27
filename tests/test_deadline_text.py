import dataclasses,json,os,random,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.deadline_text import (
    BoundaryObservation,DEADLINE_FORMAT,INT32_MIN,INT32_MAX,
    boundary_blockers,format_deadline,preview_deadline,signed_days_from_word,utf16z_single_line,
)
from ld2patch.contracts import contract
from ld2patch.pe_resources import PE,parse_dialog,sha

def observed(**updates):
    values=dict(dialog_resource=292,control_id=1050,class_name='STATIC',branch='numeric_deadline',
                is_unicode=True,is_alive=True,same_ui_thread=True,plain_win32_control=True,
                buffer_lifetime_proven=True,layout_fit_proven=True)
    values.update(updates)
    return BoundaryObservation(**values)

class DeadlineFormatterTests(unittest.TestCase):
    def test_plain_numbers_zero_and_negative_are_not_reinterpreted(self):
        for n,want in ((0,'0 天'),(1,'1 天'),(30,'30 天'),(-1,'-1 天')):
            self.assertEqual(format_deadline(n),want)

    def test_int32_extremes_and_inclusive_capacity(self):
        for n,want,units in ((INT32_MIN,'-2147483648 天',14),(INT32_MAX,'2147483647 天',13)):
            result=preview_deadline(n)
            self.assertEqual(result.text,want);self.assertEqual(result.required_units,units)
            self.assertEqual(result.utf16le_z[:-2].decode('utf-16le'),want)
        with self.assertRaises(ValueError):preview_deadline(INT32_MIN,capacity_units=13)

    def test_out_of_range_has_no_wrap_or_clamp(self):
        for n in (INT32_MIN-1,INT32_MAX+1,1<<100,-(1<<100)):
            with self.subTest(n=n),self.assertRaises(ValueError):format_deadline(n)

    def test_no_implicit_coercion_or_format_string_input(self):
        for n in (True,False,None,1.0,1.5,'1','%d','%s','%%','%d%d',b'1'):
            with self.subTest(n=n),self.assertRaises(TypeError):format_deadline(n)

    def test_explicit_word_interpretation_matches_signed_x86_words(self):
        values=[0,1,0x7fffffff,0x80000000,0xffffffff]
        rng=random.Random(39);values += [rng.randrange(1<<32) for _ in range(128)]
        for word in values:
            expected=struct.unpack('<i',struct.pack('<I',word))[0]
            self.assertEqual(signed_days_from_word(word),expected)
        for bad in (-1,1<<32):
            with self.assertRaises(ValueError):signed_days_from_word(bad)
        for bad in (True,None,'4294967295'):
            with self.assertRaises(TypeError):signed_days_from_word(bad)

    def test_one_signed_placeholder_contract_is_preserved(self):
        original=json.loads((ROOT/'patches/m038/dynamic-boundary.json').read_bytes())['source_format_anchor']
        self.assertEqual(contract(original),contract(DEADLINE_FORMAT))
        for wrong in ('%s 天','%u 天','%% 天','%d %d 天','%d 天\n'):
            self.assertNotEqual(contract(wrong),contract(DEADLINE_FORMAT))

    def test_bmp_characters_are_not_restricted_to_legacy_encoding(self):
        raw=utf16z_single_line('錄檔',3)
        self.assertEqual(raw[:-2].decode('utf-16le'),'錄檔')
        self.assertEqual(raw[-2:],b'\0\0');self.assertEqual(len(raw),6)

    def test_surrogate_pair_counts_as_two_units_without_splitting(self):
        text='錄檔\U0001f642'
        self.assertEqual(len(utf16z_single_line(text,5)),10)
        with self.assertRaises(ValueError):utf16z_single_line(text,4)

    def test_invalid_controls_and_unpaired_surrogates_are_rejected(self):
        for text in ('a\0b','a\nb','a\rb','a\tb','a\x1fb','a\x7fb'):
            with self.subTest(text=repr(text)),self.assertRaises(ValueError):utf16z_single_line(text,14)
        for text in ('\ud800','\udc00'):
            with self.assertRaises(UnicodeError):utf16z_single_line(text,14)

    def test_capacity_and_input_types_are_explicit(self):
        self.assertEqual(utf16z_single_line('',1),b'\0\0')
        for capacity in (0,-1,4097):
            with self.assertRaises(ValueError):utf16z_single_line('x',capacity)
        for capacity in (True,2.0,None):
            with self.assertRaises(TypeError):utf16z_single_line('x',capacity)
        with self.assertRaises(TypeError):utf16z_single_line(b'x',2)

    def test_unknown_target_has_no_executable_result(self):
        result=preview_deadline(30)
        self.assertFalse(result.can_apply)
        self.assertEqual(result.blockers,('live_target_not_observed','runtime_integration_not_implemented'))

    def test_even_complete_synthetic_facts_cannot_enable_integration(self):
        result=preview_deadline(30,observed())
        self.assertEqual(result.blockers,('runtime_integration_not_implemented',))
        self.assertFalse(result.can_apply)
        with self.assertRaises((AttributeError,dataclasses.FrozenInstanceError)):result.can_apply=True

    def test_wrong_dialog_control_class_and_alternate_branch_are_blocked(self):
        for updates,reason in [
            ({'dialog_resource':291},'wrong_dialog_resource'),
            ({'dialog_resource':True},'wrong_dialog_resource'),
            ({'control_id':1049},'wrong_control_id'),
            ({'class_name':'EDIT'},'wrong_control_class'),
            ({'branch':'preformatted_record_text'},'non_numeric_branch'),
        ]:
            with self.subTest(updates=updates):
                self.assertIn(reason,preview_deadline(30,observed(**updates)).blockers)

    def test_unknown_or_false_liveness_unicode_thread_lifetime_and_layout_are_blocked(self):
        fields=['is_unicode','is_alive','same_ui_thread','plain_win32_control','buffer_lifetime_proven','layout_fit_proven']
        for field in fields:
            for value in (None,False):
                with self.subTest(field=field,value=value):
                    reasons=boundary_blockers(observed(**{field:value}))
                    self.assertEqual(len(reasons),2)
                    self.assertTrue(reasons[0].endswith('_unknown' if value is None else '_not_proven'))
            with self.assertRaises(TypeError):boundary_blockers(observed(**{field:1}))
        with self.assertRaises(TypeError):boundary_blockers({})

    def test_returned_data_is_immutable_and_independent_of_later_previews(self):
        a=preview_deadline(3);original=a.utf16le_z
        b=preview_deadline(2147483647)
        self.assertEqual(a.utf16le_z,original)
        self.assertNotEqual(a.utf16le_z,b.utf16le_z)
        with self.assertRaises(dataclasses.FrozenInstanceError):a.text='modified'

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m039 static evidence SKIPPED')
    def test_licensed_field_to_signed_format_and_control_identity(self):
        b=Path(os.environ['LD2_TEST_EXE']).read_bytes()
        self.assertEqual(sha(b),'6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2')
        # These are bounded operand/identity checks, not disassembly or game execution.
        self.assertEqual(b[0x9d0ea],0x2c)
        self.assertEqual(struct.unpack_from('<H',b,0x9d0ec)[0],4)
        self.assertEqual(b[0x643d1],0xe8)
        self.assertEqual(0x643d6+struct.unpack_from('<i',b,0x643d2)[0],0x9d0e0)
        self.assertEqual(b[0x643d9],0x2c)
        self.assertEqual(b[0x6451f],0x2c)
        self.assertEqual(struct.unpack_from('<I',b,0x6454d)[0],1050)
        self.assertEqual(b[0x64553],0xe8)
        self.assertEqual(0x64558+struct.unpack_from('<i',b,0x64554)[0],0xea69f)
        self.assertEqual(struct.unpack_from('<H',b,0x6476e)[0],8)
        p=PE(b);r=next(r for r in p.resources if r['path']==[5,292,1041])
        d=parse_dialog(p.payload(r))
        matches=[x for x in d['items'] if int.from_bytes(bytes.fromhex(x['header'])[-2:],'little')==1050]
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['class']['ordinal'],0x82)
        self.assertEqual(struct.unpack_from('<hhhh',bytes.fromhex(matches[0]['header']),8),(30,117,20,8))
        self.assertEqual(matches[0]['title']['text'],'')

if __name__=='__main__':unittest.main()

