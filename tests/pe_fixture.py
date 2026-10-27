"""Generate a tiny invented PE-shaped fixture. Never execute it; no game bytes."""
import json
import struct
from ld2patch.contracts import contract
from ld2patch.pe_resources import Builder,PE,align,checksum,encode_string_block,sha


def synthetic_pe():
    field=lambda s:s.encode('utf-16le')+b'\0\0'
    version=bytearray(struct.pack('<HHH',0,52,0)+field('VS_VERSION_INFO'))
    version+=b'\0'*(align(len(version))-len(version))
    version+=struct.pack('<13I',0xfeef04bd,0x10000,0x00010002,0x00030004,0x00010002,0x00030000,0,0,0,0,0,0,0)
    struct.pack_into('<H',version,0,len(version))
    old_text='Synthetic example %d'
    tree={6:{1:{1041:encode_string_block([old_text]+['']*15)}},16:{1:{1041:bytes(version)}}}
    resource=bytearray();leaves=[]
    def allocate(size):
        resource.extend(b'\0'*(align(len(resource))-len(resource)))
        start=len(resource);resource.extend(b'\0'*size);return start
    def directory(obj):
        start=allocate(16+8*len(obj));struct.pack_into('<H',resource,start+14,len(obj))
        for i,(key,value) in enumerate(sorted(obj.items())):
            if isinstance(value,dict):target=0x80000000|directory(value)
            else:target=allocate(16);leaves.append((target,value))
            struct.pack_into('<II',resource,start+16+8*i,key,target)
        return start
    assert directory(tree)==0
    for entry,payload in leaves:
        at=allocate(len(payload));resource[at:at+len(payload)]=payload
        struct.pack_into('<IIII',resource,entry,0x3000+at,len(payload),1200,0)
    resource_size=len(resource);raw_size=align(resource_size,512)
    pe_offset=0x80;opt=pe_offset+24;table=opt+224
    b=bytearray(1536+raw_size);b[:2]=b'MZ';struct.pack_into('<I',b,60,pe_offset)
    b[pe_offset:pe_offset+4]=b'PE\0\0';struct.pack_into('<HHIIIHH',b,pe_offset+4,0x14c,3,0,0,0,224,0x010f)
    struct.pack_into('<H',b,opt,0x10b)
    for offset,value in {4:512,8:512+raw_size,28:0x400000,32:4096,36:512,56:0x4000,60:512,92:16,112:0x3000,116:resource_size}.items():
        struct.pack_into('<I',b,opt+offset,value)
    sections=[('.text',b'SYNTHETIC NONEXECUTABLE CODE',0x1000,512,512),('.data',b'SYNTHETIC DATA',0x2000,512,1024),('.rsrc',bytes(resource),0x3000,raw_size,1536)]
    for i,(name,raw,va,size,pointer) in enumerate(sections):
        h=table+i*40;b[h:h+8]=name.encode().ljust(8,b'\0')
        struct.pack_into('<IIII',b,h+8,len(raw),va,size,pointer)
        b[pointer:pointer+len(raw)]=raw
    checksum(b,opt)
    return bytes(b),old_text


def bundle():
    source,old=synthetic_pe();translation='\u5408\u6210\u7bc4\u4f8b %d'
    builder=Builder(source,sha(source));builder.resource([6,1,1041],encode_string_block([translation]+['']*15));expected=builder.finish()
    cat={'schema_version':1,'source_sha256':sha(source),'historical_m020_sha256':sha(expected),
         'encoding_scope':'Synthetic fixture only','coverage_established':False,'dialog_fonts':[],
         'entries':[{'source_key':'synthetic:string:0','kind':'string','resource':1,'language':1041,'index':0,'string_id':0,
                     'source_utf16_sha256':sha(old.encode('utf-16le')),'translation':translation,
                     'source_contract':contract(old),'contract':contract(translation),'status':'synthetic',
                     'current_version_game_seen':False,'prior_observation_scope':'none'}]}
    raw=(json.dumps(cat,ensure_ascii=True,sort_keys=True)+'\n').encode()
    versions={'schema_version':1,'steam_app_id':None,'versions':[{'id':'synthetic-v1','filename':'Ld95.exe',
              'file_version':'1.2.3.4','product_version':'1.2.3.0','source_sha256':sha(source),'source_size':len(source),
              'historical_m020_sha256':sha(expected),'historical_m020_size':len(expected),'catalog':'synthetic.json','release_approved':False}]}
    recipe={'schema_version':1,'id':'synthetic-resource-v1','engine':'resource_append_v1','version_id':'synthetic-v1',
            'catalog':'synthetic.json','catalog_sha256':sha(raw),'text_locations':1,'font_locations':0}
    return source,raw,versions,recipe,expected
