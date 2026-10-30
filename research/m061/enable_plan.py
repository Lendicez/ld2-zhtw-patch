"""m061: enable step — TextOutW hook stub + 8 list-site retargets, in memory only.

Input is an *inert* merged image (helpers already placed in .ld2t, imports in
.ld2i). This module rewrites exactly:
  * the reviewed 40-byte span RVA 0x6dc7d..0x6dca5 with a stdcall call into
    `_LD2_NamePair@16(CDC*=EBP, ansi=[F+0x14], bytes=ESI, stored_id=[F+0x18])`
    followed by `jmp` to the original continuation 0x46dca5 and int3 padding;
  * the rel32 of each pinned priority list site (call CWnd::SendDlgItemMessage
    -> call @LD2_ListInsert@24, same 5-byte length, same thiscall/ret 0x10 shape);
  * the PE CheckSum.
Nothing else may differ. It has no file writer. production_can_apply stays false.
Contains no game bytes: only hashes, offsets and the stub encoding.
"""
import hashlib, struct
import site_plan, pe_serializer

BASE = 0x400000
HOOK_SPAN = (0x6dc7d, 0x6dca5)
HOOK_SPAN_SHA256 = '8870b605ccc0777ce5ac0080acc0a1df36623064a509585b13b34bff9925db77'
CONTINUATION_VA = BASE + HOOK_SPAN[1]


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def hook_stub(name_pair_va):
    """40 bytes. ESP==F on entry (original reads [esp+0x14] as the name CString)."""
    span_va = BASE + HOOK_SPAN[0]
    s = bytearray()
    s += b'\xff\x74\x24\x18'          # push dword [esp+0x18]   ; stored_id  = [F+0x18]
    s += b'\x56'                      # push esi                ; byte_count
    s += b'\xff\x74\x24\x1c'          # push dword [esp+0x1c]   ; ansi       = [F+0x14]
    s += b'\x55'                      # push ebp                ; CDC*
    call_va = span_va + len(s)
    s += b'\xe8' + struct.pack('<i', name_pair_va - (call_va + 5))  # call _LD2_NamePair@16 (ret 16)
    jmp_va = span_va + len(s)
    s += b'\xe9' + struct.pack('<i', CONTINUATION_VA - (jmp_va + 5))  # jmp 0x46dca5
    need(len(s) <= HOOK_SPAN[1] - HOOK_SPAN[0], 'stub too long')
    s += b'\xcc' * (HOOK_SPAN[1] - HOOK_SPAN[0] - len(s))
    return bytes(s)


def _checksum_offset(img):
    pe = struct.unpack_from('<I', img, 0x3c)[0]
    return pe + 24 + 64


def apply_enabled(inert, name_pair_va, list_entry_va, sites):
    need(type(inert) is bytes, 'image')
    a, b = HOOK_SPAN
    need(sha(inert[a:b]) == HOOK_SPAN_SHA256, 'Inert hook span must be original')
    plan = site_plan.plan_retarget(inert, sites, list_entry_va)
    need(len(plan) == len(sites) == 8, 'Expected 8 priority sites')
    out = bytearray(inert)
    out[a:b] = hook_stub(name_pair_va)
    for o, old, new in plan:
        need(out[o:o + 5] == old and old[0] == 0xE8 == new[0], 'site bytes')
        out[o:o + 5] = new
    co = _checksum_offset(out)
    struct.pack_into('<I', out, co, 0)
    struct.pack_into('<I', out, co, pe_serializer.pe_checksum(bytes(out), co))
    out = bytes(out)
    changed = [i for i in range(len(inert)) if inert[i] != out[i]] if len(out) == len(inert) else None
    need(changed is not None, 'size changed')
    allowed = set(range(a, b)) | set(range(co, co + 4)) | {o + k for o, _, _ in plan for k in range(1, 5)}
    need(set(changed) <= allowed, 'Unexpected byte change outside hook/sites/checksum')
    return out, dict(
        hook_span=[hex(a), hex(b)], hook_stub_sha256=sha(out[a:b]), name_pair_va=hex(name_pair_va),
        list_entry_va=hex(list_entry_va),
        sites=[dict(va=hex(BASE + o), old=old.hex(), new=new.hex()) for o, old, new in plan],
        changed_bytes=len(changed), checksum=hex(struct.unpack_from('<I', out, co)[0]),
        hook_enabled=True, list_sites_retargeted=True, file_written=False, production_can_apply=False)
