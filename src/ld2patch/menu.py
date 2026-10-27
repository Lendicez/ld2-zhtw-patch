"""Strict classic RT_MENU parser/writer. Retains flags, command IDs and trailing padding."""
import struct

def parse(raw):
    if len(raw)<4:raise ValueError('Truncated menu')
    version,offset=struct.unpack_from('<HH',raw)
    if version!=0:raise ValueError('MENUEX not supported')
    pos=4+offset;nodes=0
    def word():
        nonlocal pos
        if pos+2>len(raw):raise ValueError('Truncated menu word')
        v=struct.unpack_from('<H',raw,pos)[0];pos+=2;return v
    def text():
        start=pos
        while word()!=0:pass
        return raw[start:pos-2].decode('utf-16le')
    def level(depth):
        nonlocal nodes
        if depth>16:raise ValueError('Menu nesting budget')
        result=[]
        while True:
            nodes+=1
            if nodes>1000:raise ValueError('Menu node budget')
            flags=word();item={'flags':flags}
            if not flags&0x10:item['id']=word()
            item['text']=text()
            if flags&0x10:item['children']=level(depth+1)
            result.append(item)
            if flags&0x80:return result
    items=level(0)
    return {'header':raw[:4+offset].hex(),'items':items,'trailing':raw[pos:].hex()}

def encode(obj):
    out=bytearray.fromhex(obj['header'])
    def level(items):
        if not items:raise ValueError('Empty menu level')
        for i,item in enumerate(items):
            flags=item['flags']
            if bool(flags&0x80)!=(i==len(items)-1):raise ValueError('Menu END flag mismatch')
            out.extend(struct.pack('<H',flags))
            if not flags&0x10:out.extend(struct.pack('<H',item['id']))
            if '\0' in item['text']:raise ValueError('Embedded NUL')
            out.extend(item['text'].encode('utf-16le')+b'\0\0')
            if flags&0x10:level(item['children'])
    level(obj['items']);out.extend(bytes.fromhex(obj['trailing']));return bytes(out)

def structure(obj):
    def level(items):return [{k:(level(v) if k=='children' else v) for k,v in x.items() if k!='text'} for x in items]
    return level(obj['items'])