"""Bounded PE32 resource core for hash-locked offline builds, not a loader."""
import struct
import hashlib

MAX_FILE = 32 * 1024 * 1024
MAX_RESOURCE = 2 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def need(b, p, size):
    if type(p) is not int or type(size) is not int or p < 0 or size < 0 or p + size > len(b):
        raise ValueError('Truncated or invalid byte range')


def align(n, a=4):
    if type(a) is not int or a <= 0 or a & (a-1):
        raise ValueError('Invalid alignment')
    return (n+a-1)//a*a


def u16(b, p):
    need(b,p,2); return struct.unpack_from('<H',b,p)[0]


def u32(b, p):
    need(b,p,4); return struct.unpack_from('<I',b,p)[0]


def zfield(b, p):
    start=p
    if u16(b,p)==65535:
        return {'ordinal':u16(b,p+2),'raw':b[p:p+4].hex()},p+4
    while u16(b,p):
        p+=2
        if p-start>65535*2:raise ValueError('Resource text budget')
    return {'text':b[start:p].decode('utf-16le'),'raw':b[start:p+2].hex()},p+2


def field_bytes(field):
    if 'text' in field:
        if '\0' in field['text']:raise ValueError('Embedded NUL in resource text')
        raw=field['text'].encode('utf-16le')
        if len(raw)>65535*2:raise ValueError('Resource text budget')
        return raw+b'\0\0'
    return bytes.fromhex(field['raw'])


class PE:
    def __init__(self,b):
        if not isinstance(b,(bytes,bytearray)) or not 256<=len(b)<=MAX_FILE or b[:2]!=b'MZ':
            raise ValueError('PE size/signature')
        self.b=b=bytes(b);self.pe=u32(b,60)
        need(b,self.pe,24)
        if self.pe<64 or b[self.pe:self.pe+4]!=b'PE\0\0' or u16(b,self.pe+4)!=0x14c:
            raise ValueError('Expected x86 PE')
        count=u16(b,self.pe+6);optional_size=u16(b,self.pe+20)
        if not 1<=count<=96 or optional_size!=224:
            raise ValueError('Unsupported section count/optional header')
        self.opt=self.pe+24;need(b,self.opt,224)
        if u16(b,self.opt)!=0x10b or u32(b,self.opt+92)!=16:
            raise ValueError('Expected PE32 with 16 directories')
        self.file_alignment=u32(b,self.opt+36);self.section_alignment=u32(b,self.opt+32)
        if not 512<=self.file_alignment<=65536 or not self.file_alignment<=self.section_alignment<=16*1024*1024:
            raise ValueError('Unsupported PE alignment')
        align(0,self.file_alignment);align(0,self.section_alignment)
        headers=u32(b,self.opt+60);table=self.opt+optional_size
        need(b,table,count*40)
        if headers<table+count*40 or headers>len(b) or headers%self.file_alignment:
            raise ValueError('Invalid SizeOfHeaders')
        self.sections=[];names=set()
        for i in range(count):
            p=table+i*40;vs,va,rs,rp=struct.unpack_from('<IIII',b,p+8)
            try:name=b[p:p+8].rstrip(b'\0').decode('ascii')
            except UnicodeError as exc:raise ValueError('Invalid section name') from exc
            if not name or '\0' in name or name in names or not vs or not rs:
                raise ValueError('Unsupported/duplicate section')
            names.add(name)
            if rp<headers or rp%self.file_alignment or rs%self.file_alignment or va%self.section_alignment or va<align(headers,self.section_alignment):
                raise ValueError('Section alignment/header overlap')
            need(b,rp,rs)
            if va+max(vs,rs)>0x100000000:raise ValueError('Section RVA overflow')
            self.sections.append(dict(name=name,vs=vs,va=va,rs=rs,rp=rp,header=p))
        for intervals in (sorted((s['rp'],s['rp']+s['rs']) for s in self.sections),
                          sorted((s['va'],s['va']+max(s['vs'],s['rs'])) for s in self.sections)):
            if any(a[1]>c[0] for a,c in zip(intervals,intervals[1:])):
                raise ValueError('Overlapping sections')
        image_size=u32(b,self.opt+56)
        if image_size%self.section_alignment or image_size<max(align(s['va']+max(s['vs'],s['rs']),self.section_alignment) for s in self.sections):
            raise ValueError('Invalid SizeOfImage')
        self.base=u32(b,self.opt+28)
        self.resource_rva=u32(b,self.opt+112);self.resource_size=u32(b,self.opt+116)
        s=self.sections[-1]
        if s['name']!='.rsrc' or self.resource_rva!=s['va'] or not 16<=self.resource_size<=min(s['vs'],s['rs']):
            raise ValueError('Unsupported resource section/directory range')
        self.rb=self.off(self.resource_rva,self.resource_size)
        self.resources=[];self._visited=set();self._metadata=[];self._named=set();self._entry_count=0
        self.walk(0,[])
        paths=[tuple(r['path']) for r in self.resources]
        if len(paths)!=len(set(paths)):raise ValueError('Duplicate resource path')
        intervals=sorted(self._metadata+[(r['offset'],r['offset']+r['size']) for r in self.resources if r['size']])
        if any(a[1]>c[0] for a,c in zip(intervals,intervals[1:])):
            raise ValueError('Overlapping resource metadata/payload')

    def off(self,rv,size=1):
        if type(rv) is not int or type(size) is not int or rv<0 or size<0 or rv+size>0x100000000:
            raise ValueError('Invalid RVA range')
        for s in self.sections:
            if s['va']<=rv<s['va']+s['rs'] and rv+size<=s['va']+s['rs']:
                p=s['rp']+rv-s['va'];need(self.b,p,size);return p
        raise ValueError('RVA is not wholly backed by section bytes')

    def va(self,p):
        for s in self.sections:
            if s['rp']<=p<s['rp']+s['rs']:return self.base+s['va']+p-s['rp']
        raise ValueError('Unmapped offset')

    def _range(self,rel,size):
        if rel<0 or size<0 or rel+size>self.resource_size:raise ValueError('Resource directory range')
        return self.rb+rel

    def _reserve(self,rel,size):
        p=self._range(rel,size);self._metadata.append((p,p+size));return p

    def walk(self,rel,path):
        if len(path)>2 or rel in self._visited:raise ValueError('Resource tree depth/cycle')
        self._visited.add(rel);p=self._range(rel,16)
        named=u16(self.b,p+12);count=named+u16(self.b,p+14)
        self._entry_count+=count
        if self._entry_count>20000:raise ValueError('Resource entry budget')
        self._reserve(rel,16+count*8)
        seen=set()
        for i in range(count):
            n,t=struct.unpack_from('<II',self.b,p+16+8*i)
            if bool(n&0x80000000)!=(i<named):raise ValueError('Named resource ordering')
            if n&0x80000000:
                name_rel=n&0x7fffffff;q=self._range(name_rel,2);length=u16(self.b,q)
                self._range(name_rel,2+length*2)
                if name_rel not in self._named:self._reserve(name_rel,2+length*2);self._named.add(name_rel)
                n=self.b[q+2:q+2+length*2].decode('utf-16le')
            if n in seen:raise ValueError('Duplicate resource sibling')
            seen.add(n)
            if t&0x80000000:
                self.walk(t&0x7fffffff,path+[n])
            else:
                if len(path)!=2 or len(self.resources)>=10000:raise ValueError('Resource leaf depth/budget')
                q=self._reserve(t,16);rv,size,cp,reserved=struct.unpack_from('<IIII',self.b,q)
                if size>MAX_RESOURCE or reserved:raise ValueError('Resource size/reserved field')
                off=self.off(rv,size)
                self._range(off-self.rb,size)
                self.resources.append(dict(path=path+[n],offset=off,size=size,codepage=cp,entry=q))

    def payload(self,r):
        need(self.b,r['offset'],r['size']);return self.b[r['offset']:r['offset']+r['size']]


def string_block(d):
    strings, p = [], 0
    for _ in range(16):
        ln = u16(d,p); p += 2
        need(d,p,ln*2)
        strings.append(d[p:p+ln*2].decode('utf-16le')); p += ln*2
    if p != len(d):
        raise ValueError('Unexpected string table trailing bytes')
    return strings

def encode_string_block(strings):
    if len(strings) != 16:
        raise ValueError('String block must contain 16 entries')
    result = bytearray()
    for s in strings:
        raw = s.encode('utf-16le')
        if len(raw)//2 > 65535 or '\0' in s:
            raise ValueError('Invalid resource string length/NUL')
        result += struct.pack('<H', len(raw)//2)+raw
    return bytes(result)

def parse_dialog(d):
    if len(d)>MAX_RESOURCE:raise ValueError('Dialog size budget')
    ext = d[:4] == b'\x01\0\xff\xff'
    style = u32(d,12 if ext else 0)
    count = u16(d,16 if ext else 8)
    p = 26 if ext else 18
    need(d,0,p)
    if count>4096:raise ValueError('Dialog control budget')
    obj = dict(extended=ext, header=d[:p].hex(), items=[])
    for key in ['menu','class','title']:
        obj[key],p = zfield(d,p)
    if style & 64:
        n = 6 if ext else 2
        need(d,p,n)
        obj['font_header'] = d[p:p+n].hex(); p += n
        obj['font'],p = zfield(d,p)
    for _ in range(count):
        q = align(p); item = {'padding': d[p:q].hex()}; p=q
        n = 24 if ext else 18
        need(d,p,n)
        item['header'] = d[p:p+n].hex(); p+=n
        item['class'],p = zfield(d,p)
        item['title'],p = zfield(d,p)
        n = u16(d,p)
        if n:
            raise ValueError('Nonempty dialog creation data needs explicit support')
        item['extra'] = d[p:p+2].hex(); p+=2
        obj['items'].append(item)
    obj['trailing'] = d[p:].hex()
    return obj

def encode_dialog(obj):
    out = bytearray.fromhex(obj['header'])
    for k in ['menu','class','title']:
        out += field_bytes(obj[k])
    if 'font' in obj:
        out += bytes.fromhex(obj['font_header'])+field_bytes(obj['font'])
    for item in obj['items']:
        needed = align(len(out))-len(out)
        pad = bytes.fromhex(item['padding'])
        out += pad if len(pad)==needed else b'\0'*needed
        out += bytes.fromhex(item['header'])+field_bytes(item['class'])+field_bytes(item['title'])+bytes.fromhex(item['extra'])
    out += bytes.fromhex(obj['trailing'])
    return bytes(out)

def checksum(b, opt):
    struct.pack_into('<I',b,opt+64,0)
    total=0
    for p in range(0,len(b),2):
        word=b[p] | (b[p+1]<<8 if p+1<len(b) else 0)
        total+=word; total=(total&65535)+(total>>16)
    total=(total&65535)+(total>>16)
    struct.pack_into('<I',b,opt+64,(total+len(b))&0xffffffff)

class Builder:

    def __init__(self, b, expected_sha256):
        if sha(b) != expected_sha256:
            raise ValueError('Unsupported EXE SHA-256')
        self.pe = PE(b)
        self.b = bytearray(b)
        self.changes = []
        self.intervals = []
        self.touched = set()
        self.s = self.pe.sections[-1]
        if self.s['name'] != '.rsrc' or self.s['rp'] + self.s['rs'] != len(b):
            raise ValueError('Unexpected last section/overlay')
        if any(struct.unpack_from('<II', b, self.pe.opt + 128)):
            raise ValueError('Signed executable requires separate approval/design')

    def patch(self, p, old, new, reason):
        need(self.b,p,len(old))
        if len(old)!=8 or p not in {r['entry'] for r in self.pe.resources}:
            raise ValueError('Only resource data-entry relocation is allowed')
        if len(old) != len(new) or self.b[p:p + len(old)] != old:
            raise ValueError('Patch size/source bytes mismatch')
        if any((p < e and p + len(old) > s for s, e in self.intervals)):
            raise ValueError('Overlapping patches')
        self.intervals.append((p, p + len(old)))
        self.b[p:p + len(old)] = new
        self.changes.append(dict(offset=p, old_hex=old.hex(), new_hex=new.hex(), reason=reason))

    def append(self, raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_RESOURCE or align(len(self.b))+len(raw)>MAX_FILE:
            raise ValueError('Resource append budget/type')
        self.b += b'\x00' * (align(len(self.b)) - len(self.b))
        p = len(self.b)
        self.b += raw
        return (p, self.s['va'] + p - self.s['rp'])

    def resource(self, path, raw):
        if tuple(path) in self.touched:raise ValueError('Duplicate resource replacement')
        self.touched.add(tuple(path))
        matches = [r for r in self.pe.resources if r['path'] == path]
        if len(matches) != 1:
            raise ValueError('Resource path not unique/found')
        r = matches[0]
        if raw == self.pe.payload(r):
            return
        p, rv = self.append(raw)
        self.patch(r['entry'], self.pe.b[r['entry']:r['entry'] + 8], struct.pack('<II', rv, len(raw)), 'resource ' + str(path))
        self.changes.append(dict(append_offset=p, size=len(raw), sha256=sha(raw), resource=path))

    def finish(self):
        if not self.changes:
            return bytes(self.b)
        if len(self.b) > len(self.pe.b):
            vs = len(self.b) - self.s['rp']
            rs = align(vs, u32(self.b, self.pe.opt + 36))
            if self.s['rp']+rs>MAX_FILE:raise ValueError('Output size budget')
            self.b += b'\x00' * (self.s['rp'] + rs - len(self.b))
            struct.pack_into('<I', self.b, self.s['header'] + 8, vs)
            struct.pack_into('<I', self.b, self.s['header'] + 16, rs)
            struct.pack_into('<I', self.b, self.pe.opt + 56, align(self.s['va'] + vs, u32(self.b, self.pe.opt + 32)))
            struct.pack_into('<I', self.b, self.pe.opt + 8, u32(self.pe.b, self.pe.opt + 8) + rs - self.s['rs'])
            struct.pack_into('<I', self.b, self.pe.opt + 116, vs)
        checksum(self.b, self.pe.opt)
        return bytes(self.b)
