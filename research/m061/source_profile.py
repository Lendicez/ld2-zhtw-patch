"""m061: source profiles for the helper merge chain (original vs m045 resource output).

Read-only. Proves that a candidate input differs from the pinned original only in
.rsrc and in an exact allowlist of PE header fields, so that code/data VAs reviewed
on the original remain valid. No writer, no bypass switch.
"""
import hashlib, struct

ORIGINAL_SHA256 = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
PROFILES = {
    'original': dict(sha256=ORIGINAL_SHA256, size=7090176, size_of_image=0x6dc000),
    # m045 resource-only output (554 positions); pinned in patches/m045/versions.json.
    'm045': dict(sha256='4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7',
                 size=7118848, size_of_image=0x6e3000),
}
# Section raw bytes that must be identical to the original (name -> sha256).
SHARED_SECTIONS = {
    '.text': '0c64261748ccf8c836211fa5454f1f6892ada0f5d71b98422b2e3e900b234c3d',
    '.rdata': 'a7047964cd12523472814c115a557a95525ffb618aa76d7bd205a6effe930690',
    '.data': '9c7723e804a85f5b6d829a6d633439a461e945774e83d47f3d2879e4320e79db',
}
# Header fields a resource-only rebuild may change: (offset-from-optional-header, width, label).
OPT_FIELDS = {8: 'SizeOfInitializedData', 56: 'SizeOfImage', 64: 'CheckSum', 96 + 2 * 8 + 4: 'ResourceDirectorySize'}
SECTION_FIELDS = {8: 'VirtualSize', 16: 'SizeOfRawData'}


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def headers(raw):
    need(type(raw) is bytes and len(raw) >= 0x400 and raw[:2] == b'MZ', 'DOS header')
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    need(raw[pe:pe + 4] == b'PE\0\0' and struct.unpack_from('<H', raw, pe + 4)[0] == 0x14c, 'PE32 x86')
    n = struct.unpack_from('<H', raw, pe + 6)[0]
    opt = pe + 24
    optsize = struct.unpack_from('<H', raw, pe + 20)[0]
    need(struct.unpack_from('<H', raw, opt)[0] == 0x10b, 'PE32 magic')
    secs = []
    for i in range(n):
        h = opt + optsize + 40 * i
        name, vs, va, rs, rp = struct.unpack_from('<8sIIII', raw, h)
        secs.append(dict(name=name.rstrip(b'\0').decode('ascii'), vs=vs, va=va, rs=rs, rp=rp, header=h))
    return pe, opt, optsize, secs


def derive(original, candidate):
    """Return a profile dict for `candidate` after proving it is the pinned original
    or a resource-only derivative with identical code/data sections."""
    need(sha(original) == ORIGINAL_SHA256, 'Unsupported original hash')
    digest = sha(candidate)
    names = [k for k, v in PROFILES.items() if v['sha256'] == digest]
    need(len(names) == 1, 'Unsupported candidate hash')
    name = names[0]
    prof = PROFILES[name]
    need(len(candidate) == prof['size'], 'Candidate size')
    if name == 'original':
        need(candidate == original, 'Original identity')
    pa, oa, osa, sa = headers(original)
    pb, ob, osb, sb = headers(candidate)
    need((pa, oa, osa) == (pb, ob, osb) and len(sa) == len(sb) == 4, 'Header layout')
    need([s['name'] for s in sa] == [s['name'] for s in sb] == ['.text', '.rdata', '.data', '.rsrc'], 'Section names')
    allowed = set()
    for off, label in OPT_FIELDS.items():
        allowed.update(range(oa + off, oa + off + 4))
    rs = sa[3]['header']
    for off in SECTION_FIELDS:
        allowed.update(range(rs + off, rs + off + 4))
    first_raw = min(s['rp'] for s in sa)
    diffs = [i for i in range(first_raw) if original[i] != candidate[i]]
    need(set(diffs) <= allowed, 'Header change outside allowlist')
    for a, b in zip(sa[:3], sb[:3]):
        need((a['vs'], a['va'], a['rs'], a['rp']) == (b['vs'], b['va'], b['rs'], b['rp']), 'Shared section geometry')
        ra = original[a['rp']:a['rp'] + a['rs']]
        rb = candidate[b['rp']:b['rp'] + b['rs']]
        need(ra == rb and sha(ra) == SHARED_SECTIONS[a['name']], 'Shared section bytes')
    need(sa[3]['va'] == sb[3]['va'] and sa[3]['rp'] == sb[3]['rp'], 'Resource section start')
    need(len(candidate) == sb[3]['rp'] + sb[3]['rs'], 'Trailing overlay unsupported')
    soi = struct.unpack_from('<I', candidate, ob + 56)[0]
    need(soi == prof['size_of_image'], 'SizeOfImage pin')
    need(soi >= sb[3]['va'] + max(sb[3]['vs'], sb[3]['rs']), 'Resource extent')
    return dict(profile=name, sha256=digest, size_of_image=soi, first_free_rva=soi,
                shared_sections_identical=True, header_diff_offsets=len(diffs), can_apply=False)
