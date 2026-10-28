"""m061: regular-import extension fragment (in-memory only).

Copies the existing import descriptors unchanged (original ILT/IAT RVAs keep
working) and appends one descriptor per requested DLL with fresh ILT/IAT words.
Generalises m057/m060 `add_textoutw` to a short reviewed API list.
"""
import re, struct

REVIEWED_APIS = frozenset([('GDI32.dll', 'TextOutW'), ('USER32.dll', 'SendDlgItemMessageW')])


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def align(v, n):
    return (v + n - 1) // n * n


class View:
    """RVA reader over a PE image plus one optional overlay fragment."""

    def __init__(self, raw, overlay_rva=None, overlay=b''):
        self.raw = raw
        pe = struct.unpack_from('<I', raw, 0x3c)[0]
        n = struct.unpack_from('<H', raw, pe + 6)[0]
        opt = pe + 24
        self.headers = struct.unpack_from('<I', raw, opt + 60)[0]
        self.size_of_image = struct.unpack_from('<I', raw, opt + 56)[0]
        self.dirs = [struct.unpack_from('<II', raw, opt + 96 + 8 * i) for i in range(16)]
        self.sections = []
        for i in range(n):
            _, vs, va, rs, rp = struct.unpack_from('<8sIIII', raw, opt + 224 + 40 * i)
            self.sections.append((va, max(vs, rs), rp, rs))
        self.overlay_rva, self.overlay = overlay_rva, overlay

    def read(self, rva, size):
        need(type(rva) is int and type(size) is int and rva >= 0 and size >= 0, 'Bad RVA request')
        if self.overlay_rva is not None and self.overlay_rva <= rva and rva + size <= self.overlay_rva + len(self.overlay):
            o = rva - self.overlay_rva
            return self.overlay[o:o + size]
        if self.overlay_rva is not None:
            need(rva + size <= self.overlay_rva or rva >= self.overlay_rva + len(self.overlay), 'Cross-overlay read')
        if rva + size <= self.headers:
            return self.raw[rva:rva + size]
        hits = [p + rva - v for v, span, p, length in self.sections if v <= rva and rva + size <= v + length]
        need(len(hits) == 1, 'RVA outside one raw section')
        return self.raw[hits[0]:hits[0] + size]


def cstring(view, rva):
    out = bytearray()
    for i in range(256):
        c = view.read(rva + i, 1)[0]
        if not c:
            need(out and all(32 <= x < 127 for x in out), 'Non-ASCII import name')
            return out.decode('ascii')
        out.append(c)
    raise Refuse('Import string limit')


def imports(view, directory):
    rva, size = directory
    need(rva and 20 <= size <= 128 * 20, 'Import descriptor limit')
    out = []
    for i in range(size // 20):
        row = view.read(rva + i * 20, 20)
        oft, stamp, fwd, name, iat = struct.unpack('<5I', row)
        if row == b'\0' * 20:
            return out
        need(stamp == 0 and fwd == 0 and name and iat, 'Bound/forwarded imports unsupported')
        dll = cstring(view, name)
        need(re.fullmatch(r'[A-Za-z0-9_.-]+\.(dll|drv)', dll, re.I), 'Import module basename')
        apis = []
        for j in range(4096):
            value = struct.unpack('<I', view.read((oft or iat) + 4 * j, 4))[0]
            need(value == struct.unpack('<I', view.read(iat + 4 * j, 4))[0], 'Bound/mismatched on-disk IAT unsupported')
            if not value:
                break
            if value & 0x80000000:
                need(value & 0x7fff0000 == 0 and value & 0xffff, 'Malformed ordinal')
                apis.append((iat + 4 * j, ('ordinal', value & 0xffff)))
            else:
                apis.append((iat + 4 * j, ('name', cstring(view, value + 2))))
        else:
            raise Refuse('Import thunk limit')
        out.append(dict(descriptor=row, dll=dll, apis=apis))
    raise Refuse('Missing import terminator')


def semantic(rows):
    return [(r['dll'].lower(), [(a, t) for a, t in r['apis']]) for r in rows]


def extend(raw, rva, wanted):
    """Return (fragment_bytes, directory_size, {api: iat_rva}, before, after)."""
    view = View(raw)
    need(type(rva) is int and rva >= view.size_of_image and rva % 0x1000 == 0, 'Import fragment location')
    need(view.dirs[11] == (0, 0), 'Bound regular imports unsupported')
    need(type(wanted) in (list, tuple) and wanted and len(set(wanted)) == len(wanted), 'API list')
    need(set(wanted) <= REVIEWED_APIS, 'Unreviewed API')
    before = imports(view, view.dirs[1])
    for dll, api in wanted:
        need(not any(r['dll'].lower() == dll.lower() and any(t == ('name', api) for _, t in r['apis']) for r in before), 'API already imported')
    groups = []
    for dll, api in wanted:
        for g in groups:
            if g[0].lower() == dll.lower():
                g[1].append(api)
                break
        else:
            groups.append((dll, [api]))
    dsize = (len(before) + len(groups) + 1) * 20
    buf = bytearray(dsize)
    for i, r in enumerate(before):
        buf[i * 20:i * 20 + 20] = r['descriptor']

    def put(data, boundary=1):
        off = align(len(buf), boundary)
        buf.extend(b'\0' * (off - len(buf)))
        buf.extend(data)
        return rva + off

    iats = {}
    for k, (dll, apis) in enumerate(groups):
        name = put(dll.encode('ascii') + b'\0')
        hints = [put(b'\0\0' + a.encode('ascii') + b'\0', 2) for a in apis]
        table = struct.pack('<%dI' % (len(hints) + 1), *hints, 0)
        ilt = put(table, 4)
        iat = put(table, 4)
        for j, a in enumerate(apis):
            iats[(dll, a)] = iat + 4 * j
        struct.pack_into('<5I', buf, (len(before) + k) * 20, ilt, 0, 0, name, iat)
    need(rva + len(buf) <= 0xffffffff, 'Import fragment overflow')
    data = bytes(buf)
    after = imports(View(raw, rva, data), (rva, dsize))
    need(semantic(after[:len(before)]) == semantic(before), 'Original import semantics changed')
    added = [(r['dll'], t[1]) for r in after[len(before):] for _, t in r['apis']]
    need(sorted(added) == sorted(wanted), 'New import mismatch')
    return data, dsize, iats, len(before), len(after)
