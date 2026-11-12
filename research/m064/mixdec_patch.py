r"""m064 lab：混合編碼解碼常式 MIXW（Big5 譯文＋CP932 原文混在同一字串 → UTF-16）。

譯文樣板（Big5）以 %s 代入存檔／資料表中的 CP932 名稱（道具、人名）時，整串既不是 Big5 也不是 CP932；
舊的後備「含 0x81–0x9F 就整串當 CP932」會把 Big5 部分拆壞（KNOWN-ISSUES #10：「偷到了○○！」「請把○○送到…」）。

MIXW(src, len)（stdcall @8，保留所有暫存器，eax＝UTF-16 單元數，0＝失敗；結果在 WOUT）逐段解碼：
    < 0x80                → ASCII
    lead 0x81–0x9F        → CP932 段（連續的 0x81–0x9F／0xE0–0xEA lead，每字 2 位元組）：
                            ≤ 0x40 位元組先查稱號對照表 → v4 catalog（ANY|JOIN）→ 名字音節表（FindCopyNorm）→ 再無則 CP932 原文
    lead 0xA1–0xF9        → Big5 一字（Big5 的 trail 不會落在 0x81–0x9F，所以分段不會錯位）
    其他                  → 單一位元組以 CP932 解（半形片假名）
CDC::TextOut／CDC::DrawText 的後備改呼叫本常式後以 TextOutW／DrawTextW 繪出。程式碼＋資料附加在 .ld2i 檔尾。
"""
import struct
from tab_title_patch import Asm, sections, iat_slot, BASE, NORM

CAT_OPEN, CAT_FIND, CAT_BLOB, CAT_BYTES = 0xae5620, 0xae4f60, 0xae6010, 0xae6000
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020
WOUT_BYTES, GUARD = 0x1000, 0xE00      # 每輪最多再寫 0x100 單元（0x200 位元組）
DATA_BYTES = 0x20 + WOUT_BYTES


def layout(data):
    return data, data + 0x10, data + 0x20   # ctx、catok、WOUT


def build(origin, data, mbtwc, pairs_va=None):
    ctx, catok, wout = layout(data)
    a = Asm(origin)

    def jmp(name):
        a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, name))
    a.emit([0x60, 0xFC])                                          # pushad; cld
    a.emit([0x8B, 0x74, 0x24, 0x24, 0x8B, 0x5C, 0x24, 0x28, 0x01, 0xF3])   # esi=src; ebx=src+len
    a.emit([0xBF], a.imm32(wout))
    a.emit([0x68], a.imm32(ctx), [0xFF, 0x35], a.imm32(CAT_BYTES), [0x68], a.imm32(CAT_BLOB))
    a.call_rel(CAT_OPEN)
    a.emit([0x83, 0xC4, 0x0C, 0xA3], a.imm32(catok))
    a.label('L')
    a.emit([0x39, 0xDE]); a.jcc32(0x83, 'done')                   # cmp esi,ebx; jae
    a.emit([0x81, 0xFF], a.imm32(wout + GUARD)); a.jcc32(0x83, 'fail')
    a.emit([0x0F, 0xB6, 0x06, 0x3C, 0x80]); a.jcc32(0x83, 'hi')
    a.emit([0x66, 0xAB, 0x46]); jmp('L')                          # stosw; inc esi
    a.label('hi')
    a.emit([0x3C, 0x81]); a.jcc32(0x82, 'single')
    a.emit([0x3C, 0x9F]); a.jcc32(0x87, 'big')
    a.emit([0x89, 0xF5])                                          # ebp = esi（段尾掃描）
    a.label('r1')
    a.emit([0x39, 0xDD]); a.jcc8(0x73, 'r2')
    a.emit([0x8A, 0x45, 0x00, 0x3C, 0x81]); a.jcc8(0x72, 'r2')
    a.emit([0x3C, 0x9F]); a.jcc8(0x76, 'r1a')
    a.emit([0x3C, 0xE0]); a.jcc8(0x72, 'r2')
    a.emit([0x3C, 0xEA]); a.jcc8(0x77, 'r2')
    a.label('r1a'); a.emit([0x83, 0xC5, 0x02, 0xEB, 0]); a.fix8.append((len(a.b) - 1, 'r1'))
    a.label('r2'); a.emit([0x39, 0xDD]); a.jcc8(0x76, 'r3'); a.emit([0x89, 0xDD])
    a.label('r3'); a.emit([0x89, 0xE9, 0x29, 0xF1])               # ecx = 段長
    a.emit([0x83, 0xF9, 0x40]); a.jcc32(0x87, 'dec')
    if pairs_va is not None:   # 稱號對照表（detail_name_patch：[n][CP932][m][Big5]…0）整段比對 → Big5 值轉 UTF-16
        a.emit([0x51, 0xBA], a.imm32(pairs_va))
        a.label('p0'); a.emit([0x0F, 0xB6, 0x02, 0x85, 0xC0]); a.jcc32(0x84, 'p9')
        a.emit([0x39, 0xC8]); a.jcc32(0x85, 'p8')
        a.emit([0x56, 0x57, 0x51, 0x8D, 0x7A, 0x01, 0xF3, 0xA6, 0x59, 0x5F, 0x5E]); a.jcc32(0x85, 'p8')
        a.emit([0x8D, 0x54, 0x0A, 0x01, 0x0F, 0xB6, 0x02, 0x42, 0x59])       # edx=值；eax=長度；pop ecx
        a.emit([0x68], a.imm32(0x100), [0x57, 0x50, 0x52, 0x6A, 0x00, 0x68], a.imm32(950)); a.call_ind(mbtwc)
        a.emit([0x85, 0xC0]); a.jcc32(0x85, 'got'); jmp('fail')
        a.label('p8'); a.emit([0x8D, 0x54, 0x02, 0x01, 0x0F, 0xB6, 0x02, 0x8D, 0x54, 0x02, 0x01]); jmp('p0')
        a.label('p9'); a.emit([0x59])
    a.emit([0x83, 0x3D], a.imm32(catok), [0x00]); a.jcc32(0x84, 'nrm')
    a.emit([0x51, 0x68], a.imm32(0x101), [0x57, 0x6A, 0x03, 0x6A, 0xFF, 0x51, 0x56, 0x68], a.imm32(ctx))
    a.call_rel(CAT_FIND)
    a.emit([0x83, 0xC4, 0x1C, 0x59])
    a.emit([0x8D, 0x50, 0xFF, 0x81, 0xFA], a.imm32(0xFF)); a.jcc32(0x86, 'got')
    a.label('nrm')
    a.emit([0x51, 0x57, 0x51, 0x56]); a.call_rel(NORM)
    a.emit([0x59, 0x85, 0xC0]); a.jcc32(0x85, 'got')
    a.label('dec')
    a.emit([0x68], a.imm32(0x100), [0x57, 0x51, 0x56, 0x6A, 0x00, 0x68], a.imm32(932)); a.call_ind(mbtwc)
    a.emit([0x85, 0xC0]); a.jcc32(0x84, 'fail')
    a.label('got'); a.emit([0x8D, 0x3C, 0x47, 0x89, 0xEE]); jmp('L')
    a.label('big')
    a.emit([0x3C, 0xA1]); a.jcc32(0x82, 'single')
    a.emit([0x3C, 0xF9]); a.jcc32(0x87, 'single')
    a.emit([0x8D, 0x56, 0x01, 0x39, 0xDA]); a.jcc32(0x83, 'single')
    a.emit([0x6A, 0x01, 0x57, 0x6A, 0x02, 0x56, 0x6A, 0x00, 0x68], a.imm32(950)); a.call_ind(mbtwc)
    a.emit([0x85, 0xC0]); a.jcc8(0x75, 'b1'); a.emit([0x66, 0xC7, 0x07, 0x3F, 0x00])
    a.label('b1'); a.emit([0x83, 0xC7, 0x02, 0x83, 0xC6, 0x02]); jmp('L')
    a.label('single')
    a.emit([0x6A, 0x01, 0x57, 0x6A, 0x01, 0x56, 0x6A, 0x00, 0x68], a.imm32(932)); a.call_ind(mbtwc)
    a.emit([0x85, 0xC0]); a.jcc8(0x75, 's1'); a.emit([0x66, 0xC7, 0x07, 0x3F, 0x00])
    a.label('s1'); a.emit([0x83, 0xC7, 0x02, 0x46]); jmp('L')
    a.label('done'); a.emit([0x89, 0xF8, 0x2D], a.imm32(wout), [0xD1, 0xE8, 0xEB, 0]); a.fix8.append((len(a.b) - 1, 'store'))
    a.label('fail'); a.emit([0x31, 0xC0])
    a.label('store'); a.emit([0x89, 0x44, 0x24, 0x1C, 0x61, 0xC2, 0x08, 0x00])
    return a.finish()


def model(raw: bytes, lookup=None) -> str:
    """Python 模型（測試用；catalog／音節表以 lookup dict 代替）。"""
    lookup = lookup or {}
    out, i, n = [], 0, len(raw)
    while i < n:
        b = raw[i]
        if b < 0x80:
            out.append(chr(b)); i += 1
        elif 0x81 <= b <= 0x9F:
            j = i
            while j < n and (0x81 <= raw[j] <= 0x9F or 0xE0 <= raw[j] <= 0xEA):
                j += 2
            j = min(j, n)
            seg = raw[i:j]
            out.append(lookup.get(seg) or seg.decode('cp932', 'replace')); i = j
        elif 0xA1 <= b <= 0xF9 and i + 1 < n:
            out.append(raw[i:i + 2].decode('cp950', 'replace')[:1] or '?'); i += 2
        else:
            out.append(raw[i:i + 1].decode('cp932', 'replace')); i += 1
    return ''.join(out)


def patch(exe: bytes, pairs_va=None):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    code_va = BASE + i['va'] + i['rsz']
    probe = build(code_va, code_va + 0x400, mbtwc, pairs_va)
    data_va = code_va + ((len(probe) + 0xf) & ~0xf)
    code = build(code_va, data_va, mbtwc, pairs_va)
    blob = code + b'\0' * (data_va - code_va - len(code)) + b'\0' * DATA_BYTES
    grow = (len(blob) + 0xfff) & ~0xfff
    out = bytearray(exe) + blob + b'\0' * (grow - len(blob))
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)
    ch = struct.unpack_from('<I', out, i['hdr'] + 36)[0]
    struct.pack_into('<I', out, i['hdr'] + 36, ch | IMAGE_SCN_EXEC)
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'mixw': code_va, 'wout': layout(data_va)[2], 'code_len': len(code)}
