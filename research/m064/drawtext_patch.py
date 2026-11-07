r"""m064 lab：CDC::DrawText 日文後備（比照 cdc_textout_patch）。

MFC `CDC::DrawText(LPCSTR s, int n, LPRECT r, UINT fmt)`（0x4e1450，四個 CDC vtable 共用）原本直接 DrawTextA。
未翻譯的 CP932 字串在 CHINESEBIG5 字型或 ACP 950 下會亂碼。開頭改 `jmp DT_HOOK`：
    n == -1 時自行計算長度（上限 0x3ff）；字串含 0x81–0x9F 位元組 → MultiByteToWideChar(932) → DrawTextW
    （DrawTextW 未匯入：第一次以 GetModuleHandleA("USER32.dll")＋GetProcAddress 取得並快取）
    其他 → 原 DrawTextA。程式碼與資料附加在 .ld2i 檔尾（EXECUTE）。只寫 lab 複本。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE

CDC_DRAWTEXT = 0x4e1450
BODY = bytes.fromhex('ff742410' * 4 + 'ff7104' + 'ff1534565200' + 'c21000')   # → DrawTextA 0x525634
DRAWTEXTA_IAT = 0x525634
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020


def build_stub(origin, data, mbtwc, gmh, gpa):
    pfn, s_user, s_dtw, wbuf = data, data + 0x10, data + 0x20, data + 0x40
    a = Asm(origin)
    a.emit([0x55, 0x8B, 0xEC, 0x56, 0x57, 0x8B, 0x75, 0x08, 0x8B, 0x7D, 0x0C])   # esi=s; edi=n
    a.emit([0x85, 0xF6]); a.jcc32(0x84, 'orig')
    a.emit([0x83, 0xFF, 0xFF]); a.jcc8(0x75, 'have_n')                          # n != -1
    a.emit([0x31, 0xFF])
    a.label('len'); a.emit([0x80, 0x3C, 0x3E, 0x00]); a.jcc8(0x74, 'have_n')
    a.emit([0x47, 0x81, 0xFF], a.imm32(0x400)); a.jcc8(0x72, 'len')
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'orig'))
    a.label('have_n')
    a.emit([0x85, 0xFF]); a.jcc32(0x8E, 'orig')                                 # n <= 0
    a.emit([0x81, 0xFF], a.imm32(0x3FF)); a.jcc32(0x87, 'orig')
    a.emit([0x31, 0xD2])
    a.label('scan'); a.emit([0x39, 0xFA]); a.jcc32(0x83, 'orig')
    a.emit([0x8A, 0x04, 0x16, 0x42, 0x3C, 0x81]); a.jcc8(0x72, 'scan'); a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'scan')
    a.emit([0xA1], a.imm32(pfn), [0x85, 0xC0]); a.jcc8(0x75, 'conv')            # 已快取 DrawTextW
    a.emit([0x51, 0x68], a.imm32(s_user)); a.call_ind(gmh)
    a.emit([0x85, 0xC0]); a.jcc8(0x74, 'popfail')
    a.emit([0x68], a.imm32(s_dtw), [0x50]); a.call_ind(gpa)
    a.emit([0xA3], a.imm32(pfn))
    a.label('popfail'); a.emit([0x59, 0x85, 0xC0]); a.jcc32(0x84, 'orig')
    a.label('conv')
    a.emit([0x51, 0x68], a.imm32(0x3FF), [0x68], a.imm32(wbuf), [0x57, 0x56, 0x6A, 0x00, 0x68], a.imm32(932))
    a.call_ind(mbtwc)
    a.emit([0x59, 0x85, 0xC0]); a.jcc32(0x84, 'orig')
    a.emit([0xFF, 0x75, 0x14, 0xFF, 0x75, 0x10, 0x50, 0x68], a.imm32(wbuf), [0xFF, 0x71, 0x04])
    a.emit([0xFF, 0x15], a.imm32(pfn))                                          # DrawTextW(hdc, w, n, r, fmt)
    a.emit([0x5F, 0x5E, 0x5D, 0xC2, 0x10, 0x00])
    a.label('orig'); a.emit([0x5F, 0x5E, 0x5D])
    a.emit(bytes.fromhex('ff742410' * 4 + 'ff7104'))
    a.call_ind(DRAWTEXTA_IAT)
    a.emit([0xC2, 0x10, 0x00])
    data_blob = bytearray(0x40 + 0x800)
    data_blob[0x10:0x10 + 11] = b'USER32.dll\0'
    data_blob[0x20:0x20 + 10] = b'DrawTextW\0'
    return a.finish(), bytes(data_blob)


def model(s: bytes, n: int) -> str:
    if n == -1:
        n = len(s)
    if not s or not 1 <= n <= 0x3FF:
        return 'a'
    return 'w' if any(0x81 <= b <= 0x9F for b in s[:n]) else 'a'


def patch(exe: bytes):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    fo = va2off(secs, CDC_DRAWTEXT)
    if exe[fo:fo + len(BODY)] != BODY:
        raise ValueError('CDC::DrawText body mismatch')
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    gmh = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'GetModuleHandleA')
    gpa = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'GetProcAddress')
    code_va = BASE + i['va'] + i['rsz']
    probe, _ = build_stub(code_va, code_va + 0x400, mbtwc, gmh, gpa)
    data_va = code_va + ((len(probe) + 0xf) & ~0xf)
    code, data = build_stub(code_va, data_va, mbtwc, gmh, gpa)
    blob = code + b'\0' * (data_va - code_va - len(code)) + data
    grow = (len(blob) + 0xfff) & ~0xfff
    out = bytearray(exe) + blob + b'\0' * (grow - len(blob))
    out[fo] = 0xE9
    struct.pack_into('<i', out, fo + 1, code_va - (CDC_DRAWTEXT + 5))
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)
    ch = struct.unpack_from('<I', out, i['hdr'] + 36)[0]
    struct.pack_into('<I', out, i['hdr'] + 36, ch | IMAGE_SCN_EXEC)
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'hook': hex(code_va), 'code_len': len(code), 'data_va': hex(data_va)}
