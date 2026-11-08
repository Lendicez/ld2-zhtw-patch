"""m061: bounded PE32 section/import-directory serializer (in-memory only).

Appends new sections after the last section of a fixed-base PE32 image and
optionally repoints the regular import directory. It never moves, resizes or
rewrites existing sections, never touches relocations/delay/bound/IAT/TLS/
resource directories, and refuses images with overlays or non-zero header slack.
There is no file writer here; callers receive bytes and a report.
"""
import hashlib, struct

SCN_CODE_RX = 0x60000020
SCN_RDATA_R = 0x40000040
SCN_DATA_RW = 0xC0000040
ALLOWED_CHARACTERISTICS = frozenset([SCN_CODE_RX, SCN_RDATA_R, SCN_DATA_RW])
ALLOWED_DIRECTORIES = frozenset([1])  # regular import directory only
MAX_NEW_SECTIONS = 4
MAX_SECTION_BYTES = 1 << 20


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def align(v, n):
    return (v + n - 1) // n * n


def pe_checksum(raw, checksum_offset):
    total = 0
    data = raw + (b'\0' if len(raw) % 2 else b'')
    for i in range(0, len(data), 2):
        if checksum_offset <= i < checksum_offset + 4:
            continue
        total += data[i] | (data[i + 1] << 8)
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (total + len(raw)) & 0xffffffff


def parse(raw):
    need(type(raw) is bytes and 0x200 <= len(raw) <= 32 * 1024 * 1024 and raw[:2] == b'MZ', 'Image shape')
    try:
        pe = struct.unpack_from('<I', raw, 0x3c)[0]
        need(raw[pe:pe + 4] == b'PE\0\0', 'PE signature')
        machine, n, _, _, _, optsize, flags = struct.unpack_from('<HHIIIHH', raw, pe + 4)
        need(machine == 0x14c and 1 <= n <= 16 and optsize == 224, 'PE32 x86 header')
        opt = pe + 24
        need(struct.unpack_from('<H', raw, opt)[0] == 0x10b, 'PE32 magic')
        sect_align, file_align = struct.unpack_from('<II', raw, opt + 32)
        size_of_image, size_of_headers = struct.unpack_from('<II', raw, opt + 56)
        need(sect_align == 0x1000 and file_align in (0x200, 0x1000), 'Alignment contract')
        nrva = struct.unpack_from('<I', raw, opt + 92)[0]
        need(nrva == 16, 'Data directory count')
        dirs = [struct.unpack_from('<II', raw, opt + 96 + 8 * i) for i in range(16)]
        table = opt + optsize
        secs = []
        for i in range(n):
            h = table + 40 * i
            name, vs, va, rs, rp = struct.unpack_from('<8sIIII', raw, h)
            ch = struct.unpack_from('<I', raw, h + 36)[0]
            secs.append(dict(name=name, vs=vs, va=va, rs=rs, rp=rp, ch=ch, header=h))
    except struct.error:
        raise Refuse('Truncated PE') from None
    return dict(pe=pe, opt=opt, n=n, flags=flags, sect_align=sect_align, file_align=file_align,
                size_of_image=size_of_image, size_of_headers=size_of_headers, dirs=dirs, table=table, sections=secs)


def plan_rvas(raw, sizes):
    """Return the RVAs the serializer will assign for sections of the given sizes."""
    p = parse(raw)
    out, rva = [], p['size_of_image']
    need(rva % p['sect_align'] == 0, 'SizeOfImage alignment')
    for s in sizes:
        need(type(s) is int and 0 < s <= MAX_SECTION_BYTES, 'Section size')
        out.append(rva)
        rva += align(s, p['sect_align'])
    return out


def append_sections(raw, additions, directories=None):
    directories = dict(directories or {})
    p = parse(raw)
    need(type(additions) in (list, tuple) and 1 <= len(additions) <= MAX_NEW_SECTIONS, 'Addition count')
    need(set(directories) <= ALLOWED_DIRECTORIES, 'Directory not allowed')
    need(p['dirs'][5] == (0, 0) and p['flags'] & 1, 'Fixed-base (relocations stripped) image only')
    need(p['dirs'][11] == (0, 0), 'Bound imports unsupported')
    secs = p['sections']
    last = max(secs, key=lambda s: s['va'])
    need(p['size_of_image'] == align(last['va'] + max(last['vs'], last['rs']), p['sect_align']), 'SizeOfImage consistency')
    end_raw = max(s['rp'] + s['rs'] for s in secs)
    need(len(raw) == end_raw and end_raw % p['file_align'] == 0, 'Overlay/trailing bytes unsupported')
    table_end = p['table'] + 40 * p['n']
    new_end = table_end + 40 * len(additions)
    first_raw = min(s['rp'] for s in secs)
    need(new_end <= p['size_of_headers'] <= first_raw, 'Header room')
    need(raw[table_end:new_end] == b'\0' * (new_end - table_end), 'Header slack not zero')
    names = {s['name'].rstrip(b'\0') for s in secs}
    out = bytearray(raw)
    rva = p['size_of_image']
    report = []
    size_code = size_init = 0
    for i, a in enumerate(additions):
        need(set(a) <= {'name', 'rva', 'data', 'characteristics'} and {'name', 'rva', 'data', 'characteristics'} <= set(a), 'Addition shape')
        name = a['name']
        need(type(name) is str and name.startswith('.') and 2 <= len(name) <= 8 and name.isascii() and name.isprintable(), 'Section name')
        need(name.encode() not in names, 'Duplicate section name')
        names.add(name.encode())
        data = a['data']
        need(type(data) is bytes and 0 < len(data) <= MAX_SECTION_BYTES, 'Section data')
        need(a['characteristics'] in ALLOWED_CHARACTERISTICS, 'Section characteristics')
        need(a['rva'] == rva, 'Section RVA must equal planned placement')
        rs = align(len(data), p['file_align'])
        rp = len(out)
        struct.pack_into('<8sIIIIIIHHI', out, table_end + 40 * i, name.encode().ljust(8, b'\0'),
                         len(data), rva, rs, rp, 0, 0, 0, 0, a['characteristics'])
        out.extend(data + b'\0' * (rs - len(data)))
        if a['characteristics'] == SCN_CODE_RX:
            size_code += rs
        else:
            size_init += rs
        report.append(dict(name=name, rva=hex(rva), virtual_size=len(data), raw_size=rs, raw_pointer=hex(rp),
                           characteristics=hex(a['characteristics']), sha256=sha(data)))
        rva += align(len(data), p['sect_align'])
    opt = p['opt']
    struct.pack_into('<H', out, p['pe'] + 6, p['n'] + len(additions))
    for off, add in ((4, size_code), (8, size_init)):
        v = struct.unpack_from('<I', out, opt + off)[0] + add
        need(v <= 0xffffffff, 'Size field overflow')
        struct.pack_into('<I', out, opt + off, v)
    struct.pack_into('<I', out, opt + 56, rva)
    for idx, (drva, dsize) in directories.items():
        need(type(drva) is int and type(dsize) is int and dsize > 0, 'Directory shape')
        hit = [r for r in report if int(r['rva'], 16) <= drva and drva + dsize <= int(r['rva'], 16) + r['virtual_size']]
        need(len(hit) == 1, 'Directory must lie inside one new section')
        struct.pack_into('<II', out, opt + 96 + 8 * idx, drva, dsize)
    struct.pack_into('<I', out, opt + 64, 0)
    struct.pack_into('<I', out, opt + 64, pe_checksum(bytes(out), opt + 64))
    result = bytes(out)
    verify(raw, result, additions, directories)
    return result, dict(sections=report, size_of_image=hex(rva), checksum=hex(struct.unpack_from('<I', result, opt + 64)[0]),
                        output_sha256=sha(result), output_bytes=len(result), original_sections_unchanged=True)


def verify(before, after, additions, directories):
    a, b = parse(before), parse(after)
    need(b['n'] == a['n'] + len(additions), 'Section count')
    need(after[:len(before)][a['sections'][0]['rp']:] == before[a['sections'][0]['rp']:], 'Original section bytes changed')
    for x, y in zip(a['sections'], b['sections']):
        need(x == y, 'Original section header changed')
    opt = a['opt']
    allowed = set(range(a['pe'] + 6, a['pe'] + 8))
    for off in (4, 8, 56, 64):
        allowed.update(range(opt + off, opt + off + 4))
    for idx in directories:
        allowed.update(range(opt + 96 + 8 * idx, opt + 104 + 8 * idx))
    table_end = a['table'] + 40 * a['n']
    allowed.update(range(table_end, table_end + 40 * len(additions)))
    first = a['sections'][0]['rp']
    diffs = {i for i in range(first) if before[i] != after[i]}
    need(diffs <= allowed, 'Header change outside allowlist')
    for i in range(16):
        if i not in directories:
            need(a['dirs'][i] == b['dirs'][i], 'Untouched directory changed')
    for add, s in zip(additions, b['sections'][a['n']:]):
        need(after[s['rp']:s['rp'] + len(add['data'])] == add['data'] and s['va'] == add['rva'], 'New section readback')
    need(pe_checksum(after, opt + 64) == struct.unpack_from('<I', after, opt + 64)[0], 'Checksum')
