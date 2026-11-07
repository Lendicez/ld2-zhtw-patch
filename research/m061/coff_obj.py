"""m061: bounded i386 COFF reader and in-memory relocator for a *pinned* helper object.

Generalizes m060 relocate_reviewed (which is locked to the m058 object) so a second
helper (the list shim) can be placed. Relocations resolve by symbol *index*, so static
functions, labels and section symbols in code sections work. Only code sections
(.text$mn) are placed; metadata sections must carry no relocations. Nothing is linked,
executed or written to disk.
"""
import hashlib, struct

CODE_SECTION = '.text$mn'
METADATA_SECTIONS = frozenset(['.drectve', '.debug$S', '.debug$T', '.voltbl', '.chks64'])
SCN_CNT_CODE, SCN_LNK_COMDAT = 0x20, 0x1000
REL_DIR32, REL_REL32 = 6, 20


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def align(v, n):
    return (v + n - 1) // n * n


def parse(raw):
    """Return dict(sections=[...], symbols={index: {...}}). Strict bounds; ASCII names only."""
    need(type(raw) is bytes and 20 <= len(raw) <= 1 << 20, 'COFF size')
    try:
        machine, n, _stamp, so, sn, opt, _flags = struct.unpack_from('<HHIIIHH', raw)
        need(machine == 0x14c and opt == 0 and 1 <= n <= 64, 'COFF header (i386 object)')
        need(so + sn * 18 + 4 <= len(raw), 'COFF symbol table bounds')
        strings = so + sn * 18
        slen = struct.unpack_from('<I', raw, strings)[0]
        need(4 <= slen and strings + slen <= len(raw), 'COFF string table')
        symbols, i = {}, 0
        while i < sn:
            name, value, section, kind, storage, aux = struct.unpack_from('<8sIhHBB', raw, so + i * 18)
            need(i + aux < sn, 'COFF aux bounds')
            if name[:4] == b'\0' * 4:
                off = struct.unpack_from('<I', name, 4)[0]
                need(4 <= off < slen, 'Symbol string offset')
                end = raw.find(b'\0', strings + off, strings + slen)
                need(end != -1, 'Symbol terminator')
                name = raw[strings + off:end]
            else:
                name = name.rstrip(b'\0')
            sym = dict(index=i, name=name.decode('ascii'), value=value, section=section, kind=kind, storage=storage, selection=None)
            if aux and section > 0 and storage == 3 and value == 0:
                sym['selection'] = raw[so + (i + 1) * 18 + 14]
            symbols[i] = sym
            i += 1 + aux
        sections = []
        for j in range(n):
            name, _vs, _va, size, pointer, rp, _lp, nr, _nl, attrs = struct.unpack_from('<8sIIIIIIHHI', raw, 20 + j * 40)
            need(pointer + size <= len(raw) and rp + nr * 10 <= len(raw), 'COFF section bounds')
            rel = []
            for k in range(nr):
                off, idx, typ = struct.unpack_from('<IIH', raw, rp + k * 10)
                need(idx in symbols, 'Relocation symbol index')
                need(off + 4 <= size, 'Relocation field outside section')
                rel.append(dict(offset=off, symbol=idx, name=symbols[idx]['name'], type=typ))
            sname = name.rstrip(b'\0').decode('ascii')
            sel = next((s['selection'] for s in symbols.values() if s['section'] == j + 1 and s['storage'] == 3 and s['name'] == sname and s['selection'] is not None), 0)
            sections.append(dict(index=j + 1, name=sname, data=raw[pointer:pointer + size], rel=rel, attrs=attrs, selection=sel))
        return dict(sections=sections, symbols=symbols)
    except (struct.error, UnicodeError):
        raise Refuse('Malformed COFF') from None


def undefined(obj):
    return {s['name'] for s in obj['symbols'].values() if s['section'] == 0 and s['storage'] == 2}


def defined_external(obj):
    return {s['name'] for s in obj['symbols'].values() if s['section'] > 0 and s['storage'] == 2}


def code_sections(obj):
    out = []
    for s in obj['sections']:
        if s['name'] == CODE_SECTION:
            need(s['attrs'] & SCN_CNT_CODE, 'Code section without CNT_CODE')
            need(s['selection'] in (0, 1, 2), 'Unsupported COMDAT selection')
            out.append(s)
        else:
            need(s['name'] in METADATA_SECTIONS, f"Unknown runtime section {s['name']!r}")
            need(not s['rel'], 'Metadata section with relocations')
            if s['name'] == '.drectve':
                need(not s['data'].strip(b' \0'), 'Link directives present (e.g. DEFAULTLIB)')
    need(out, 'No code sections')
    return out


def layout(obj):
    offsets, length = {}, 0
    for s in code_sections(obj):
        offsets[s['index']] = align(length, 16)
        length = offsets[s['index']] + len(s['data'])
    return offsets, length


def relocate(raw, code_va, bindings, *, expected_sha256, expected_undefined, entry):
    """Place all code sections at code_va (16-byte aligned, int3 fill) and apply fixups.

    The caller must pin the object hash and the exact undefined set. Returns
    (code, entry_va, details)."""
    need(type(raw) is bytes and sha(raw) == expected_sha256, 'Object hash not pinned/accepted')
    need(type(bindings) is dict and set(bindings) == set(expected_undefined), 'Binding set mismatch')
    need(all(type(v) is int and 0 <= v <= 0xffffffff for v in bindings.values()), 'Binding width')
    need(type(code_va) is int and 0 <= code_va and code_va + 0x100000 <= 1 << 32, 'Code VA')
    obj = parse(raw)
    need(undefined(obj) == set(expected_undefined), 'Undefined symbol set mismatch')
    offsets, length = layout(obj)
    need(length <= 0x4000, 'Code fragment size limit')
    out = bytearray(b'\xcc' * length)
    for s in code_sections(obj):
        out[offsets[s['index']]:offsets[s['index']] + len(s['data'])] = s['data']

    def target(idx):
        sym = obj['symbols'][idx]
        if sym['section'] == 0:
            need(sym['storage'] == 2 and sym['name'] in bindings, f"Unbound symbol {sym['name']}")
            return bindings[sym['name']]
        need(sym['section'] in offsets, f"Reference into non-code section ({sym['name']})")
        return code_va + offsets[sym['section']] + sym['value']

    fields, fixups = [], 0
    for s in code_sections(obj):
        base = offsets[s['index']]
        for r in s['rel']:
            at = base + r['offset']
            fields.append((at, at + 4))
            t = target(r['symbol'])
            if r['type'] == REL_DIR32:
                v = t + struct.unpack_from('<I', out, at)[0]
                need(v <= 0xffffffff, 'DIR32 overflow')
                struct.pack_into('<I', out, at, v)
            elif r['type'] == REL_REL32:
                v = t + struct.unpack_from('<i', out, at)[0] - (code_va + at + 4)
                need(-(1 << 31) <= v < (1 << 31), 'REL32 overflow')
                struct.pack_into('<i', out, at, v)
            else:
                raise Refuse(f"Relocation type {r['type']} unsupported")
            fixups += 1
    fields.sort()
    need(all(a[1] <= b[0] for a, b in zip(fields, fields[1:])), 'Overlapping fixups')
    ent = [s for s in obj['symbols'].values() if s['name'] == entry and s['section'] in offsets and s['storage'] == 2]
    need(len(ent) == 1, 'Entry symbol')
    entry_va = code_va + offsets[ent[0]['section']] + ent[0]['value']
    return bytes(out), entry_va, dict(fixups=fixups, code_bytes=length, sections=len(offsets))
