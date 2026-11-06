r"""m064 lab：遊戲自訂替換符展開（%A–%Z）時把插入值轉 Big5。

`0x4014b0 Expand(fmt, dest, ctx)`（cdecl）逐字複製 fmt；遇 `%0`–`%9` 插入整數，遇 `%A`–`%Z` 插入
`ctx[ch-0x37]` 指向的字串（人名、地名、迷宮名、道具名…，來自世界資料／存檔，CP932）。
模板已原位改成 Big5，插入值仍是 CP932 → 同一句混兩種編碼，任何繪製路徑都會有一段亂碼。

修補：`0x401520 mov ecx,[ebx+edx*4-0xdc]; mov edx,esi; lea esp,[esp+0]`（16 B）→ `call CONV; nop×11`。
CONV 取出來源字串；若含 0x81–0x9F 位元組（CP932 日文）→ 查 v4 catalog（ANY|JOIN）→ 否則
MultiByteToWideChar(932) → WideCharToMultiByte(950) 到靜態緩衝，並以該緩衝取代來源。其他值不變。
程式碼附加在 .ld2i 檔尾（EXECUTE）。只寫 lab 複本；production_can_apply=false。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE

SITE = 0x401520
SITE_BYTES = bytes.fromhex('8b8c9324ffffff' '8bd6' '8da42400000000')
CAT_OPEN, CAT_FIND, CAT_BLOB, CAT_BYTES = 0xae5620, 0xae4f60, 0xae6010, 0xae6000
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020


def build_stub(origin, data, mbtwc_slot, wctmb_slot):
    ctx, wbuf, xbuf = data, data + 0x10, data + 0x220
    a = Asm(origin)
    a.emit(bytes.fromhex('8b8c9324ffffff'))                  # mov ecx,[ebx+edx*4-0xdc]（原指令）
    a.emit([0x60, 0x89, 0xCE])                                # pushad; mov esi,ecx
    a.emit([0x85, 0xF6]); a.jcc32(0x84, 'out')
    a.emit([0x31, 0xFF, 0x31, 0xD2])                          # edi=len=0; edx=flag=0
    a.label('L')
    a.emit([0x8A, 0x04, 0x3E, 0x84, 0xC0]); a.jcc8(0x74, 'Ld')   # al=[esi+edi]
    a.emit([0x3C, 0x81]); a.jcc8(0x72, 'n'); a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'n'); a.emit([0x42])
    a.label('n'); a.emit([0x47, 0x81, 0xFF], a.imm32(0x80)); a.jcc8(0x72, 'L')
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'out'))   # 過長 → 原樣
    a.label('Ld'); a.emit([0x85, 0xD2]); a.jcc32(0x84, 'out')
    a.emit([0x68], a.imm32(ctx), [0xFF, 0x35], a.imm32(CAT_BYTES), [0x68], a.imm32(CAT_BLOB))
    a.call_rel(CAT_OPEN)
    a.emit([0x83, 0xC4, 0x0C, 0x85, 0xC0]); a.jcc8(0x74, 'dec')
    a.emit([0x68], a.imm32(0x101), [0x68], a.imm32(wbuf), [0x6A, 0x03, 0x6A, 0xFF, 0x57, 0x56],
           [0x68], a.imm32(ctx))
    a.call_rel(CAT_FIND)
    a.emit([0x83, 0xC4, 0x1C])
    a.emit([0x8D, 0x50, 0xFF, 0x81, 0xFA], a.imm32(0xFF)); a.jcc8(0x76, 'conv')
    a.label('dec')
    a.emit([0x68], a.imm32(0x100), [0x68], a.imm32(wbuf), [0x57, 0x56, 0x6A, 0x00], [0x68], a.imm32(932))
    a.call_ind(mbtwc_slot)
    a.emit([0x85, 0xC0]); a.jcc8(0x74, 'out')
    a.label('conv')
    a.emit([0x6A, 0x00, 0x6A, 0x00, 0x68], a.imm32(0xFF), [0x68], a.imm32(xbuf), [0x50], [0x68], a.imm32(wbuf),
           [0x6A, 0x00], [0x68], a.imm32(950))
    a.call_ind(wctmb_slot)
    a.emit([0x85, 0xC0]); a.jcc8(0x74, 'out')
    a.emit([0xC6, 0x80], a.imm32(xbuf), [0x00])               # mov byte [eax+xbuf],0
    a.emit([0xC7, 0x44, 0x24, 0x18], a.imm32(xbuf))          # pushad 的 ecx ← xbuf
    a.label('out')
    a.emit([0x61, 0x8B, 0xD6, 0xC3])                          # popad; mov edx,esi（原指令）; ret
    return a.finish(), xbuf + 0x100 - data


def model(value: bytes, lookup: dict) -> bytes:
    if not value or len(value) >= 0x80 or not any(0x81 <= b <= 0x9F for b in value):
        return value
    ja = value.decode('cp932', 'replace')
    return lookup.get(ja, ja).encode('cp950', 'replace')


def patch(exe: bytes):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    so = va2off(secs, SITE)
    if exe[so:so + len(SITE_BYTES)] != SITE_BYTES:
        raise ValueError('Expand %A-%Z copy site mismatch')
    if exe[va2off(secs, 0x401513):va2off(secs, 0x401513) + 10] != bytes.fromhex('8ac880e941' '80f9197733'):
        raise ValueError('Expand letter branch mismatch')
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    code_va = BASE + i['va'] + i['rsz']
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    wctmb = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'WideCharToMultiByte')
    probe, _ = build_stub(code_va, code_va + 0x400, mbtwc, wctmb)
    data_va = code_va + ((len(probe) + 0xf) & ~0xf)
    code, dlen = build_stub(code_va, data_va, mbtwc, wctmb)
    blob = code + b'\0' * (data_va - code_va - len(code)) + b'\0' * dlen
    grow = (len(blob) + 0xfff) & ~0xfff
    out = bytearray(exe) + blob + b'\0' * (grow - len(blob))
    out[so] = 0xE8
    struct.pack_into('<i', out, so + 1, code_va - (SITE + 5))
    out[so + 5:so + 16] = b'\x90' * 11
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)
    ch = struct.unpack_from('<I', out, i['hdr'] + 36)[0]
    struct.pack_into('<I', out, i['hdr'] + 36, ch | IMAGE_SCN_EXEC)
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'site': hex(SITE), 'code_va': hex(code_va), 'code_len': len(code), 'data_va': hex(data_va)}
