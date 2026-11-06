r"""m064 lab：讀檔／存檔清單（存檔標頭說明）繁中化。

存檔檔頭存有存檔當下組好的說明字串（CP932，例「 971年 7月12日 ダジルタール  岩塊の町」），
清單以 `SendDlgItemMessage(id, LB_INSERTSTRING, -1, s)`（0x4ea671；存檔框 0x460974 → 0x422、讀檔框 0x476a0e → 0x401）放進 ANSI 清單 → ACP 950 下亂碼。存檔內容**不改**，只在插入清單時轉換顯示字串：

    以空白切詞；含 0x81–0x9F 位元組的詞（CP932 日文）→ 先查 v4 catalog（ANY|JOIN，人名、地名）
    → 查無則 MultiByteToWideChar(932) → 一律 WideCharToMultiByte(950) 寫入靜態緩衝；其他位元組原樣複製。

遊戲之後只用清單索引（不讀回文字比對），前綴「NNN:」為 ASCII 不變。
.ld2t 已滿，程式碼與緩衝附加在 .ld2i 檔尾（該區段加上 EXECUTE 屬性；lab 限定）。
地名 catalog 列（CP932 鍵）由 `place_rows()` 在建置時由使用者 EXE 產生，不入庫。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE

SEND_DLG_ITEM_MSG = 0x4ea671
# (call 位址, 呼叫前的位元組簽章)：兩處都是 SendDlgItemMessage(id, LB_INSERTSTRING, -1, s)
SITES = (
    (0x460974, '516aff688101000068220400008bcb'),      # push ecx; push -1; push 0x181; push 0x422; mov ecx,ebx
    (0x476a0e, '8b4c241c536aff68810100006801040000'),  # 另一處標頭清單：mov ecx,[esp+0x1c]; push ebx; push -1; push 0x181; push 0x401
    # 讀檔／存檔框的檔案清單（_findfirst 列舉後 0x47f980 組「NNN:」＋標頭 → LB_ADDSTRING 0x401）
    (0x480150, '526a0068800100006801040000' + '8bcd'),
    (0x480403, '526a0068800100006801040000' + '8bcd'),
)
SITE = SITES[0][0]
CAT_OPEN, CAT_FIND, CAT_BLOB, CAT_BYTES = 0xae5620, 0xae4f60, 0xae6010, 0xae6000
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020


def build_stub(origin, data, mbtwc_slot, wctmb_slot):
    ctx, catok, wbuf, sbuf = data, data + 0x10, data + 0x20, data + 0x240
    a = Asm(origin)
    a.emit([0x60])                                            # pushad
    a.emit([0x8B, 0x74, 0x24, 0x30])                          # esi = lParam（[esp+0x20+0x10]）
    a.emit([0x85, 0xF6]); a.jcc32(0x84, 'noswap')
    # 整串先掃：沒有 0x81–0x9F → 原樣
    a.emit([0x89, 0xF1])                                      # mov ecx,esi
    a.label('q'); a.emit([0x8A, 0x01, 0x41, 0x84, 0xC0]); a.jcc32(0x84, 'noswap')
    a.emit([0x3C, 0x81]); a.jcc8(0x72, 'q'); a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'q')
    a.emit([0xBF], a.imm32(sbuf), [0x8D, 0x9F], a.imm32(0xFE))   # edi=sbuf; ebx=sbuf+0xfe
    a.emit([0x68], a.imm32(ctx), [0xFF, 0x35], a.imm32(CAT_BYTES), [0x68], a.imm32(CAT_BLOB))
    a.call_rel(CAT_OPEN)
    a.emit([0x83, 0xC4, 0x0C, 0xA3], a.imm32(catok))          # add esp,0xc; mov [catok],eax
    a.label('tok')
    a.emit([0x8A, 0x06, 0x84, 0xC0]); a.jcc32(0x84, 'fin')    # al=[esi]; 0 → fin
    a.emit([0x3C, 0x20]); a.jcc8(0x75, 'word')
    a.emit([0x39, 0xDF]); a.jcc32(0x83, 'fin')                # cmp edi,ebx; jae
    a.emit([0x88, 0x07, 0x47, 0x46]); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'tok'))
    a.label('word'); a.emit([0x89, 0xF5])                     # ebp = esi
    a.label('w1'); a.emit([0x8A, 0x45, 0x00, 0x84, 0xC0]); a.jcc8(0x74, 'w2')
    a.emit([0x3C, 0x20]); a.jcc8(0x74, 'w2'); a.emit([0x45]); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'w1'))
    a.label('w2'); a.emit([0x89, 0xF1])                       # ecx = esi
    a.label('w3'); a.emit([0x39, 0xE9]); a.jcc32(0x83, 'raw')
    a.emit([0x8A, 0x01, 0x41, 0x3C, 0x81]); a.jcc8(0x72, 'w3'); a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'w3')
    a.emit([0x89, 0xE9, 0x29, 0xF1])                          # ecx = ebp-esi
    a.emit([0x83, 0xF9, 0x40]); a.jcc32(0x87, 'raw')
    a.emit([0x83, 0x3D], a.imm32(catok), [0x00]); a.jcc8(0x74, 'dec')
    a.emit([0x51])                                            # push ecx（保存 len）
    a.emit([0x68], a.imm32(0x101), [0x68], a.imm32(wbuf), [0x6A, 0x03, 0x6A, 0xFF, 0x51, 0x56],
           [0x68], a.imm32(ctx))
    a.call_rel(CAT_FIND)
    a.emit([0x83, 0xC4, 0x1C, 0x59])                          # add esp,0x1c; pop ecx
    a.emit([0x8D, 0x50, 0xFF, 0x81, 0xFA], a.imm32(0xFF)); a.jcc8(0x76, 'conv')
    a.label('dec')
    a.emit([0x68], a.imm32(0x100), [0x68], a.imm32(wbuf), [0x51, 0x56, 0x6A, 0x00], [0x68], a.imm32(932))
    a.call_ind(mbtwc_slot)
    a.emit([0x85, 0xC0]); a.jcc8(0x74, 'raw')
    a.label('conv')
    a.emit([0x89, 0xDA, 0x29, 0xFA])                          # edx = ebx-edi
    a.jcc32(0x8E, 'fin')                                      # 剩餘 <= 0 → 結束（cb=0 會回傳所需長度）
    a.emit([0x6A, 0x00, 0x6A, 0x00, 0x52, 0x57, 0x50], [0x68], a.imm32(wbuf), [0x6A, 0x00], [0x68], a.imm32(950))
    a.call_ind(wctmb_slot)
    a.emit([0x01, 0xC7, 0x89, 0xEE])                          # add edi,eax; mov esi,ebp
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'tok'))
    a.label('raw')
    a.emit([0x39, 0xEE]); a.jcc32(0x83, 'tok')                # cmp esi,ebp; jae tok
    a.emit([0x39, 0xDF]); a.jcc8(0x73, 'fin')
    a.emit([0x8A, 0x06, 0x88, 0x07, 0x46, 0x47]); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'raw'))
    a.label('fin')
    a.emit([0xC6, 0x07, 0x00, 0x61])                          # mov byte [edi],0; popad
    a.emit([0xC7, 0x44, 0x24, 0x10], a.imm32(sbuf))           # lParam = sbuf
    a.emit([0xE9]); a.emit(struct.pack('<i', SEND_DLG_ITEM_MSG - (a.here() + 4)))
    a.label('noswap'); a.emit([0x61, 0xE9]); a.emit(struct.pack('<i', SEND_DLG_ITEM_MSG - (a.here() + 4)))
    return a.finish(), sbuf + 0x100 - data


def model(header: str, lookup: dict) -> str:
    """Python 模型：以空白切詞，CP932 日文詞查表或照字形轉 cp950（kana → ?）。"""
    raw = header.encode('cp932')
    if not any(0x81 <= b <= 0x9F for b in raw):
        return raw.decode('cp950', 'replace')
    out = []
    for part in raw.split(b' '):
        if any(0x81 <= b <= 0x9F for b in part) and len(part) <= 0x40:
            w = lookup.get(part.decode('cp932'), part.decode('cp932'))
            out.append(w.encode('cp950', 'replace'))
        else:
            out.append(part)
    return b' '.join(out).decode('cp950', 'replace')


def place_rows(pristine_exe: bytes, places_items):
    """lab-places 的地名 offset → (FULL_ANY 列) CP932 鍵、繁中值。"""
    rows = []
    for it in places_items:
        off = int(it['file_offset'])
        src = pristine_exe[off:pristine_exe.index(b'\0', off)]
        if src and any(0x81 <= b <= 0x9F for b in src):
            rows.append((2, -1, src, it['text_zh_tw'], 0))
    return rows


def patch(exe: bytes):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    offs = []
    for site, sig in SITES:
        so = va2off(secs, site)
        if exe[so] != 0xE8 or site + 5 + struct.unpack_from('<i', exe, so + 1)[0] != SEND_DLG_ITEM_MSG:
            raise ValueError(f'list insert site {site:#x} mismatch')
        sig = bytes.fromhex(sig)
        if exe[so - len(sig):so] != sig:
            raise ValueError(f'list insert args mismatch at {site:#x}')
        offs.append((so, site))
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
    for so, site in offs:
        struct.pack_into('<i', out, so + 1, code_va - (site + 5))
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)
    ch = struct.unpack_from('<I', out, i['hdr'] + 36)[0]
    struct.pack_into('<I', out, i['hdr'] + 36, ch | IMAGE_SCN_EXEC)
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'sites': [hex(x) for x, _ in SITES], 'code_va': hex(code_va), 'code_len': len(code), 'data_va': hex(data_va)}
