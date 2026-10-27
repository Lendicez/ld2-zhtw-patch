"""Reviewed resource-only laboratory core; not a production installer parser."""
import struct
import hashlib

def sha(data):
    return hashlib.sha256(data).hexdigest()

def align(n, a=4):
    return (n+a-1)//a*a

def u16(b, p):
    return struct.unpack_from('<H', b, p)[0]

def u32(b, p):
    return struct.unpack_from('<I', b, p)[0]

def zfield(b, p):
    start = p
    if u16(b, p) == 65535:
        return {'ordinal': u16(b, p+2), 'raw': b[p:p+4].hex()}, p+4
    while u16(b, p):
        p += 2
    return {'text': b[start:p].decode('utf-16le'), 'raw': b[start:p+2].hex()}, p+2

def field_bytes(field):
    if 'text' in field:
        if '\0' in field['text']:
            raise ValueError('Embedded NUL in resource text')
        return field['text'].encode('utf-16le') + b'\0\0'
    return bytes.fromhex(field['raw'])

class PE:
    def __init__(self, b):
        if len(b)<256 or len(b)>32*1024*1024 or b[:2]!=b"MZ":
            raise ValueError("PE size/signature")
        self.b = bytes(b)
        self.pe = u32(b, 60)
        if b[self.pe:self.pe+4] != b'PE\0\0' or u16(b, self.pe+4) != 0x14c:
            raise ValueError('Expected x86 PE')
        self.opt = self.pe+24
        self.sections = []
        table = self.opt+u16(b, self.pe+20)
        for i in range(u16(b, self.pe+6)):
            p = table+40*i
            vs, va, rs, rp = struct.unpack_from('<IIII', b, p+8)
            self.sections.append(dict(name=b[p:p+8].rstrip(b'\0').decode(), vs=vs, va=va, rs=rs, rp=rp, header=p))
        self.base = u32(b, self.opt+28)
        self.resource_rva = u32(b, self.opt+112)
        self.rb = self.off(self.resource_rva)
        self.resources = []
        self._visited = set()
        self.walk(0, [])

    def off(self, rv):
        for s in self.sections:
            if s['va'] <= rv < s['va']+max(s['vs'], s['rs']):
                p = s['rp']+rv-s['va']
                if p >= len(self.b):
                    raise ValueError('RVA beyond file')
                return p
        raise ValueError('Unmapped RVA '+hex(rv))

    def va(self, p):
        for s in self.sections:
            if s['rp'] <= p < s['rp']+s['rs']:
                return self.base+s['va']+p-s['rp']
        raise ValueError('Unmapped offset')

    def walk(self, rel, path):
        if len(path)>2 or rel in self._visited or len(self.resources)>10000:
            raise ValueError("Resource tree budget/cycle")
        self._visited.add(rel)
        p = self.rb+rel
        for i in range(u16(self.b,p+12)+u16(self.b,p+14)):
            n, t = struct.unpack_from('<II', self.b, p+16+8*i)
            if n & 0x80000000:
                q = self.rb+(n & 0x7fffffff)
                n = self.b[q+2:q+2+u16(self.b,q)*2].decode('utf-16le')
            if t & 0x80000000:
                self.walk(t & 0x7fffffff, path+[n])
            else:
                q = self.rb+t
                rv, size, cp, _ = struct.unpack_from('<IIII', self.b, q)
                off = self.off(rv)
                if off+size > len(self.b):
                    raise ValueError('Resource outside file')
                self.resources.append(dict(path=path+[n], offset=off, size=size, codepage=cp, entry=q))

    def payload(self, r):
        return self.b[r['offset']:r['offset']+r['size']]

def string_block(d):
    strings, p = [], 0
    for _ in range(16):
        ln = u16(d,p); p += 2
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
    ext = d[:4] == b'\x01\0\xff\xff'
    style = u32(d,12 if ext else 0)
    count = u16(d,16 if ext else 8)
    p = 26 if ext else 18
    obj = dict(extended=ext, header=d[:p].hex(), items=[])
    for key in ['menu','class','title']:
        obj[key],p = zfield(d,p)
    if style & 64:
        n = 6 if ext else 2
        obj['font_header'] = d[p:p+n].hex(); p += n
        obj['font'],p = zfield(d,p)
    for _ in range(count):
        q = align(p); item = {'padding': d[p:q].hex()}; p=q
        n = 24 if ext else 18
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
        self.s = self.pe.sections[-1]
        if self.s['name'] != '.rsrc' or self.s['rp'] + self.s['rs'] != len(b):
            raise ValueError('Unexpected last section/overlay')
        if any(struct.unpack_from('<II', b, self.pe.opt + 128)):
            raise ValueError('Signed executable requires separate approval/design')

    def patch(self, p, old, new, reason):
        if len(old) != len(new) or self.b[p:p + len(old)] != old:
            raise ValueError('Patch size/source bytes mismatch')
        if any((p < e and p + len(old) > s for s, e in self.intervals)):
            raise ValueError('Overlapping patches')
        self.intervals.append((p, p + len(old)))
        self.b[p:p + len(old)] = new
        self.changes.append(dict(offset=p, old_hex=old.hex(), new_hex=new.hex(), reason=reason))

    def append(self, raw):
        self.b += b'\x00' * (align(len(self.b)) - len(self.b))
        p = len(self.b)
        self.b += raw
        return (p, self.s['va'] + p - self.s['rp'])

    def resource(self, path, raw):
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
            self.b += b'\x00' * (self.s['rp'] + rs - len(self.b))
            struct.pack_into('<I', self.b, self.s['header'] + 8, vs)
            struct.pack_into('<I', self.b, self.s['header'] + 16, rs)
            struct.pack_into('<I', self.b, self.pe.opt + 56, align(self.s['va'] + vs, u32(self.b, self.pe.opt + 32)))
            struct.pack_into('<I', self.b, self.pe.opt + 8, u32(self.pe.b, self.pe.opt + 8) + rs - self.s['rs'])
            struct.pack_into('<I', self.b, self.pe.opt + 116, vs)
        checksum(self.b, self.pe.opt)
        return bytes(self.b)
