import copy,json,os,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.deadline_layout import (EDITS,RESOURCE,M038_SHA256,OUTPUT_SHA256,
    edit_geometry,layout_payload,build_layout,overlaps)
from ld2patch.pe_resources import PE,parse_dialog,sha
from ld2patch.patch_engine import build_patch


def fixture():
    # Entirely synthetic headers and text, not an embedded game resource.
    def item(cid,cls,rect,text='synthetic'):
        return dict(header=struct.pack('<II4hH',0x50020000,0,*rect,cid).hex(),
                    title={'text':text},**{'class':{'ordinal':cls}},extra='')
    d=dict(extended=False,header=struct.pack('<IIH4h',0,0,17,0,0,149,148).hex(),
           font={'text':'MingLiU'},font_header='0e00',items=[])
    for i in range(17):d['items'].append(item(2000+i,130,(i*8,20,5,8)))
    for i,cid,cls,old,new in EDITS:d['items'][i]=item(cid,cls,old,'' if i==8 else 'synthetic')
    return d


class DeadlineLayoutTests(unittest.TestCase):
    def test_geometry_only_preserves_ids_styles_order_text_and_input(self):
        d=fixture();snapshot=copy.deepcopy(d);out=edit_geometry(d)
        self.assertEqual(d,snapshot)
        h=bytearray.fromhex(out['header']);struct.pack_into('<h',h,16,148)
        self.assertEqual(h.hex(),d['header'])
        for i,(a,b) in enumerate(zip(d['items'],out['items'])):
            old=bytes.fromhex(a['header']);new=bytearray.fromhex(b['header'])
            new[8:16]=old[8:16]
            self.assertEqual(new,old)
            self.assertEqual({k:v for k,v in a.items()if k!='header'},
                             {k:v for k,v in b.items()if k!='header'})
        self.assertEqual(struct.unpack_from('<4h',bytes.fromhex(out['items'][8]['header']),8),(30,117,115,8))

    def test_unknown_shape_font_identity_or_style_refused_without_mutation(self):
        mutations=[lambda d:d.update(extended=True),lambda d:d['items'].pop(),
          lambda d:d['font'].update(text='Other'),lambda d:d.update(font_header='0c00'),
          lambda d:d['items'][8]['class'].update(ordinal=129),
          lambda d:d['items'][8]['title'].update(text='unexpected'),
          lambda d:d['items'][8].update(header='00')]
        for mutate in mutations:
            d=fixture();mutate(d);before=copy.deepcopy(d)
            with self.assertRaises(ValueError):edit_geometry(d)
            self.assertEqual(d,before)

    def test_unexpected_neighbor_in_new_row_or_outside_bounds_refused(self):
        for rect in [(35,120,10,8),(148,20,5,8),(-1,20,5,8)]:
            d=fixture();h=bytearray.fromhex(d['items'][3]['header'])
            struct.pack_into('<4h',h,8,*rect);d['items'][3]['header']=h.hex()
            with self.assertRaises(ValueError):edit_geometry(d)

    def test_adjacent_edges_are_not_overlap(self):
        self.assertFalse(overlaps((5,117,25,8),(30,117,115,8)))
        self.assertFalse(overlaps((30,117,115,8),(30,127,113,8)))
        self.assertTrue(overlaps((5,117,26,8),(30,117,115,8)))

    def test_arbitrary_payload_and_original_are_rejected(self):
        for raw in (b'',b'synthetic',None,bytearray(b'x')):
            with self.assertRaises(ValueError):layout_payload(raw)
            with self.assertRaises(ValueError):build_layout(raw,b'',{}, {})

    @unittest.skipUnless(os.environ.get('LD2_TEST_EXE'),'Licensed input unavailable; m040 layout rebuild SKIPPED')
    def test_licensed_rebuild_reproducible_only_one_resource_geometry_changes(self):
        p=Path(os.environ['LD2_TEST_EXE']);source=p.read_bytes();d=ROOT/'patches/m038'
        args=((d/'catalog.json').read_bytes(),json.loads((d/'versions.json').read_bytes()),json.loads((d/'recipe.json').read_bytes()))
        base=build_patch(source,*args);a=build_layout(source,*args);b=build_layout(source,*args)
        self.assertEqual(a,b);self.assertEqual(sha(a.output),OUTPUT_SHA256)
        self.assertEqual(sha(base.output),M038_SHA256);self.assertEqual(p.read_bytes(),source)
        self.assertFalse(a.metadata['production_can_apply']);self.assertFalse(a.metadata['dynamic_text_integrated'])
        old,new=PE(base.output),PE(a.output)
        om={tuple(r['path']):old.payload(r)for r in old.resources}
        nm={tuple(r['path']):new.payload(r)for r in new.resources}
        self.assertEqual(om.keys(),nm.keys());self.assertEqual({k for k in om if om[k]!=nm[k]},{RESOURCE})
        x,y=parse_dialog(om[RESOURCE]),parse_dialog(nm[RESOURCE])
        changed={i for i in range(17)if x['items'][i]['header']!=y['items'][i]['header']}
        self.assertEqual(changed,{e[0]for e in EDITS})
        restored=copy.deepcopy(y);restored['header']=x['header']
        for i in changed:restored['items'][i]['header']=x['items'][i]['header']
        self.assertEqual(restored,x)
        self.assertTrue(all(e['unchanged']for e in a.metadata['m038_to_layout_proof']['non_resource_sections']))
        with self.assertRaises(ValueError):build_layout(base.output,*args)
        bad=bytearray(source);bad[4096]^=1
        with self.assertRaises(ValueError):build_layout(bytes(bad),*args)

if __name__=='__main__':unittest.main()
