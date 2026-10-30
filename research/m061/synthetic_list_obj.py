"""Build a minimal i386 COFF stand-in for list_insert_w.obj (audit + dual-merge tests).

This is NOT the real MSVC output. It exports `@LD2_ListInsert@24` with `ret 16`
and references the seven expected undefined symbols. Replace with the Windows
compile-only artifact once HANDOFF-COMPILE Stage A succeeds; pin that sha256.
"""
import struct


ENTRY = '@LD2_ListInsert@24'
EXTERNS = [
    '_LD2_EntryCount', '_LD2_Entries', '_LD2_OriginalDlgItem',
    '_LD2_SendDlgItemMessageW', '_LD2_MultiByteToWideChar',
    '___security_cookie', '@__security_check_cookie@4',
]
# m061b profile 'u': v1 externs + policy word + GetDlgItem + four USER32 *W window APIs.
ENTRY_U = '@LD2_ListInsertU@24'
EXTERNS_U = EXTERNS + [
    '_LD2_ListMode', '_LD2_GetDlgItem', '_LD2_IsWindowUnicode',
    '_LD2_GetWindowLongW', '_LD2_GetClassLongW', '_LD2_SetWindowLongW',
]


def build(profile: str = 'v1') -> bytes:
    if profile == 'u':
        return _build(ENTRY_U, EXTERNS_U)
    if profile != 'v1':
        raise ValueError(profile)
    return _build(ENTRY, EXTERNS)


def _build(ENTRY, EXTERNS) -> bytes:
    code = bytearray()
    relocs_spec = []
    for name in EXTERNS:
        relocs_spec.append((len(code) + 1, name))
        code += b'\xA1\x00\x00\x00\x00'  # mov eax, [abs32]
    code += b'\x33\xC0\xC2\x10\x00'       # xor eax,eax; ret 16
    code = bytes(code)

    payload, str_off = b'', {}
    for n in ['.text$mn', ENTRY] + EXTERNS:
        if len(n) > 8:
            str_off[n] = 4 + len(payload)
            payload += n.encode('ascii') + b'\0'
    strings = struct.pack('<I', 4 + len(payload)) + payload

    def name8(n):
        if len(n) <= 8:
            return n.encode('ascii').ljust(8, b'\0')
        return struct.pack('<II', 0, str_off[n])

    sn = 1 + 1 + 1 + len(EXTERNS)
    sec_data_off = 20 + 40
    reloc_off = sec_data_off + len(code)
    sym_off = reloc_off + len(relocs_spec) * 10
    sym_index = {ENTRY: 2}
    for i, n in enumerate(EXTERNS):
        sym_index[n] = 3 + i
    reloc_bytes = b''.join(struct.pack('<IIH', off, sym_index[name], 6) for off, name in relocs_spec)
    sec_hdr = b'.text$mn' + struct.pack('<IIIIIIHHI', len(code), 0, len(code), sec_data_off, reloc_off, 0, len(relocs_spec), 0, 0x60500020)
    header = struct.pack('<HHIIIHH', 0x14c, 1, 0, sym_off, sn, 0, 0)
    aux = bytearray(18)
    struct.pack_into('<I', aux, 0, len(code))
    struct.pack_into('<H', aux, 4, len(relocs_spec))
    aux[14] = 1
    sym_bytes = name8('.text$mn') + struct.pack('<IhHBB', 0, 1, 0, 3, 1) + bytes(aux)
    sym_bytes += name8(ENTRY) + struct.pack('<IhHBB', 0, 1, 0x20, 2, 0)
    for n in EXTERNS:
        sym_bytes += name8(n) + struct.pack('<IhHBB', 0, 0, 0, 2, 0)
    return header + sec_hdr + code + reloc_bytes + sym_bytes + strings
