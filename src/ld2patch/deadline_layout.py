"""One reviewed dialog geometry experiment; no runtime text integration or installer."""
from copy import deepcopy
from dataclasses import dataclass
import struct

from .pe_resources import PE, Builder, parse_dialog, encode_dialog, sha
from .patch_engine import build_patch, verify_resource_only

SOURCE_SHA256 = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
M038_SHA256 = '8730f5731730afcf8a20e245958744d2b227dde4fa260d861eae296001ef65b2'
DIALOG_SHA256 = '7be3cb5c4f5356cccdfc0346dd591710146ef3d3fb51f32e9564e8840f2461d8'
OUTPUT_SHA256 = '2afdc14391cf6e700f31c593e738d59cf66a6cc13f3b56b1fdbf9448e72313e1'
RESOURCE = (5, 292, 1041)
# index, control ID, class ordinal, exact old rectangle, new rectangle
EDITS = (
    (0, 1, 128, (102,131,43,14), (102,141,43,14)),
    (1, 1012, 128, (5,131,43,14), (5,141,43,14)),
    (2, 1056, 128, (53,131,43,14), (53,141,43,14)),
    (8, 1050, 130, (30,117,20,8), (30,117,115,8)),
    (10, 65535, 130, (63,117,25,8), (5,127,25,8)),
    (16, 1054, 130, (87,117,56,8), (30,127,113,8)),
)


def _rect(header, offset):
    return struct.unpack_from('<4h', bytes.fromhex(header), offset)


def _with_rect(header, offset, rect):
    b=bytearray.fromhex(header)
    struct.pack_into('<4h', b, offset, *rect)
    return b.hex()


def overlaps(a, b):
    return (a[0]<b[0]+b[2] and b[0]<a[0]+a[2]
            and a[1]<b[1]+b[3] and b[1]<a[1]+a[3])


def edit_geometry(dialog):
    """Pure, strict geometry transform; hash lock is applied by layout_payload."""
    before=deepcopy(dialog)
    try:
        if before['extended'] or len(before['items'])!=17:
            raise ValueError('Unsupported dialog type/count')
        if len(bytes.fromhex(before['header']))!=18 or _rect(before['header'],10)!=(0,0,149,148):
            raise ValueError('Unexpected dialog rectangle')
        if before['font']['text']!='MingLiU' or before['font_header']!='0e00':
            raise ValueError('Unexpected font or point size')
        for index,cid,cls,old,new in EDITS:
            item=before['items'][index];h=bytes.fromhex(item['header'])
            if len(h)!=18 or struct.unpack_from('<H',h,16)[0]!=cid or item['class']['ordinal']!=cls or _rect(item['header'],8)!=old:
                raise ValueError('Unexpected control identity/rectangle')
        target=before['items'][8]
        if target['title'].get('text')!='' or int.from_bytes(bytes.fromhex(target['header'])[:4],'little')!=0x50020000:
            raise ValueError('Unexpected deadline text/style')
        after=deepcopy(before)
        after['header']=_with_rect(before['header'],10,(0,0,149,158))
        for index,cid,cls,old,new in EDITS:
            after['items'][index]['header']=_with_rect(before['items'][index]['header'],8,new)
        for item in after['items']:
            x,y,w,h=_rect(item['header'],8)
            if min(x,y)<0 or min(w,h)<=0 or x+w>149 or y+h>158:
                raise ValueError('Control outside dialog')
        # Existing unrelated overlaps are reported, not silently fixed here.
        changed={x[0] for x in EDITS}
        for i,a in enumerate(after['items']):
            for j,b in enumerate(after['items'][:i]):
                if (i in changed or j in changed) and overlaps(_rect(a['header'],8),_rect(b['header'],8)):
                    raise ValueError('Layout introduces/retains overlap at changed control')
        return after
    except (KeyError,IndexError,TypeError,struct.error) as exc:
        raise ValueError('Malformed dialog geometry input') from exc


def layout_payload(raw):
    if not isinstance(raw,bytes) or sha(raw)!=DIALOG_SHA256:
        raise ValueError('Unreviewed dialog payload')
    return encode_dialog(edit_geometry(parse_dialog(raw)))


@dataclass(frozen=True)
class LayoutBuild:
    output: bytes
    metadata: dict


def build_layout(source, catalog_bytes, versions, recipe):
    if not isinstance(source,bytes) or sha(source)!=SOURCE_SHA256:
        raise ValueError('Unsupported original version')
    baseline=build_patch(source,catalog_bytes,versions,recipe)
    if sha(baseline.output)!=M038_SHA256:
        raise ValueError('Expected reviewed m038 profile')
    pe=PE(baseline.output)
    resource=next(r for r in pe.resources if tuple(r['path'])==RESOURCE)
    builder=Builder(baseline.output,M038_SHA256)
    builder.resource(list(RESOURCE),layout_payload(pe.payload(resource)))
    output=builder.finish()
    if sha(output)!=OUTPUT_SHA256:raise ValueError('Layout output differs from reviewed candidate')
    proof=verify_resource_only(baseline.output,output,{RESOURCE})
    return LayoutBuild(output,dict(
        candidate='m040-layout-only',source_sha256=SOURCE_SHA256,
        intermediate_m038_sha256=M038_SHA256,output_sha256=sha(output),
        output_bytes=len(output),source_to_m038_proof=baseline.metadata['proof'],
        m038_to_layout_proof=proof,geometry_control_edits=len(EDITS),
        dialog_height_dlu=[148,158],deadline_width_dlu=[20,115],
        translations_added=0,dynamic_text_integrated=False,runtime_tested=False,
        production_can_apply=False,release_approved=False))
