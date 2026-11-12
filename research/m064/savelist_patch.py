r"""m064 lab：讀檔／存檔清單（存檔標頭說明）繁中化。

存檔檔頭存有存檔當下組好的說明字串（CP932，例「 971年 7月12日 ダジルタール  岩塊の町」），
清單以 `SendDlgItemMessage(id, LB_INSERTSTRING, -1, s)`（0x4ea671；存檔框 0x460974 → 0x422、讀檔框 0x476a0e → 0x401）放進 ANSI 清單 → ACP 950 下亂碼。存檔內容**不改**，只在插入清單時轉換顯示字串：

    以空白切詞；含 0x81–0x9F 位元組的詞（CP932 日文）→ 先查 v4 catalog（ANY|JOIN，人名、地名）
    → 查無則 FindCopyNorm（人名音節表）→ 再無則 MultiByteToWideChar(932) → 一律 WideCharToMultiByte(950) 寫入靜態緩衝；其他位元組原樣複製。

遊戲之後只用清單索引（不讀回文字比對），前綴「NNN:」為 ASCII 不變。
.ld2t 已滿，程式碼與緩衝附加在 .ld2i 檔尾（該區段加上 EXECUTE 屬性；lab 限定）。
地名 catalog 列（CP932 鍵）由 `place_rows()` 在建置時由使用者 EXE 產生，不入庫。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE, NORM

SEND_DLG_ITEM_MSG = 0x4ea671
# (call 位址, 呼叫前的位元組簽章)：兩處都是 SendDlgItemMessage(id, LB_INSERTSTRING, -1, s)
SITES = (
    (0x460974, '516aff688101000068220400008bcb'),      # push ecx; push -1; push 0x181; push 0x422; mov ecx,ebx
    (0x476a0e, '8b4c241c536aff68810100006801040000'),  # 另一處標頭清單：mov ecx,[esp+0x1c]; push ebx; push -1; push 0x181; push 0x401
    # 讀檔／存檔框的檔案清單（_findfirst 列舉後 0x47f980 組「NNN:」＋標頭 → LB_ADDSTRING 0x401）
    (0x480150, '526a0068800100006801040000' + '8bcd'),
    (0x480403, '526a0068800100006801040000' + '8bcd'),
    # 戰鬥「選擇攻擊目標」清單（對話框 120，清單 0x429）：「●」＋怪物名（CP932）
    (0x4a79df, '6aff688101000068290400008bcd'), (0x4a80cf, '6aff688101000068290400008bcd'),
    (0x4a878f, '6aff688101000068290400008bce'), (0x4a885a, '6aff688101000068290400008bce'),
    (0x4a8923, '6aff688101000068290400008bce'), (0x4a89f0, '6aff688101000068290400008bce'),
    (0x4c6c3c, '6aff688101000068290400008bcf'), (0x4c6c86, '6aff688101000068290400008bcf'),
    # 同型「◎／○／●＋單位名」清單（其他對話框：清單 0x415、0x408、0x3f0）
    (0x4a8d08, '556aff688101000068150400008bce'), (0x47c4b8, '556aff688101000068080400008bce'),
    (0x482108, '556aff688101000068f00300008bce'),
    # 委託清單（旅館委託頁、黑暗公會，清單 0x3e8）：「◎／○」標記＋報酬＋期限＋委託人（NPC 名為 CP932）
    (0x457985, '30526aff688101000068e8030000'), (0x4582f6, '6aff688101000068e80300008bcd'),
    (0x459005, '6aff688101000068e80300008bcd'), (0x4595a5, '30526aff688101000068e8030000'),
    # 1.0.1：旅館委託頁清單（'%s\t%6s\t%5s\t%-12s\t%2s'：種類、報酬、期限、委託人、未／引）與其他 0x3e8 清單
    (0x4ac730, '526aff688101000068e80300008bcd'), (0x4abcab, '526aff688101000068e80300008bcd'),
    (0x496611, '526aff688101000068e80300008bce'), (0x4ac010, '526aff688101000068e80300008bcf'),
    (0x4b1ff3, '506aff688101000068e80300008bcf'),
)
# 片假名（U+30A1–U+30F6；平假名先 +0x60）→ 音譯用漢字；'' ＝略去（促音）。長音「ー」略去，「・」→「‧」。
# 只在 catalog、FindCopyNorm 都查不到時使用（例：遊戲隨機產生的人名／首領名，CP950 無假名會變成「?」）。
KANA = 'ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ'
HANZI = ('亞阿伊伊烏烏艾艾歐歐卡加奇基克格克蓋科哥薩札西吉斯茲賽澤索佐塔達奇吉', '', '茲茲特德托多納尼努涅諾'
         '哈巴帕希比皮夫布普赫貝佩霍波波馬米姆梅莫亞亞尤尤約約拉里爾雷羅瓦瓦伊艾歐恩維卡克')


def kana_table() -> bytes:
    zh = [c for c in HANZI[0]] + [''] + [c for c in HANZI[1] + HANZI[2]]
    assert len(KANA) == len(zh) == 0x56, (len(KANA), len(zh))
    assert all(ord(k) == 0x30A1 + i for i, k in enumerate(KANA))
    return b''.join(struct.pack('<H', ord(z) if z else 0) for z in zh)


def translit_model(text: str) -> str:
    """stub 音譯的 Python 對照模型（測試用）。"""
    out = []
    for ch in text:
        c = ord(ch)
        if c in (0x30FC, 0x30C3, 0x3063):
            continue
        if c == 0x30FB:
            out.append('\u2027'); continue
        if c == 0x306E:
            out.append('之'); continue
        if 0x3041 <= c <= 0x3096:
            c += 0x60
        if 0x30A1 <= c <= 0x30F6:
            v = struct.unpack_from('<H', kana_table(), (c - 0x30A1) * 2)[0]
            if v:
                out.append(chr(v))
            continue
        out.append(chr(c))
    return ''.join(out)
SITE = SITES[0][0]
CAT_OPEN, CAT_FIND, CAT_BLOB, CAT_BYTES = 0xae5620, 0xae4f60, 0xae6010, 0xae6000
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020


def build_stub(origin, data, mbtwc_slot, wctmb_slot, arg_esp=0x10, target=None, target_ind=None, norm=NORM,
               translit=True, _table_va=None, pairs_va=None):
    """arg_esp：入口時字串參數相對 esp 的位移；target＝相對跳轉目標，target_ind＝經 IAT 間接跳轉。
    translit：catalog／Norm 皆查不到時把假名音譯成漢字（表附在程式碼後）。"""
    if translit and _table_va is None:   # 兩遍：先量程式碼長度，再以表位址重建（長度不變）
        n = len(build_stub(origin, data, mbtwc_slot, wctmb_slot, arg_esp, target, target_ind, norm, True, -1,
                           pairs_va)[0])
        tva = origin + ((n + 1) & ~1)
        code, dlen = build_stub(origin, data, mbtwc_slot, wctmb_slot, arg_esp, target, target_ind, norm, True, tva,
                                pairs_va)
        assert len(code) == n
        return code + b'\0' * (tva - origin - n) + kana_table(), dlen
    if target is None and target_ind is None:
        target = SEND_DLG_ITEM_MSG
    ctx, catok, wbuf, sbuf = data, data + 0x10, data + 0x20, data + 0x240
    a = Asm(origin)
    a.emit([0x60])                                            # pushad
    a.emit([0x8B, 0x74, 0x24, 0x20 + arg_esp])                # esi = 字串參數（pushad 後 +0x20）
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
    a.emit([0x3C, 0x20]); a.jcc8(0x74, 'sep')                 # 分隔：空白或 TAB（清單欄位以 TAB 分欄）
    a.emit([0x3C, 0x09]); a.jcc8(0x75, 'word')
    a.label('sep')
    a.emit([0x39, 0xDF]); a.jcc32(0x83, 'fin')                # cmp edi,ebx; jae
    a.emit([0x88, 0x07, 0x47, 0x46]); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'tok'))
    a.label('word')
    # Big5 符號（lead 0xA1，例如原位改寫的「●」）整個字原樣複製，不併入後面的 CP932 名字
    a.emit([0x3C, 0xA1]); a.jcc8(0x75, 'w0')
    a.emit([0x8D, 0x57, 0x01, 0x39, 0xDA]); a.jcc32(0x83, 'fin')   # lea edx,[edi+1]; cmp edx,ebx; jae fin
    a.emit([0x66, 0x8B, 0x06, 0x66, 0x89, 0x07, 0x83, 0xC6, 0x02, 0x83, 0xC7, 0x02])
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'tok'))
    a.label('w0'); a.emit([0x89, 0xF5])                       # ebp = esi
    a.label('w1'); a.emit([0x8A, 0x45, 0x00, 0x84, 0xC0]); a.jcc8(0x74, 'w2')
    a.emit([0x3C, 0x20]); a.jcc8(0x74, 'w2'); a.emit([0x3C, 0x09]); a.jcc8(0x74, 'w2'); a.emit([0x45]); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'w1'))
    a.label('w2'); a.emit([0x89, 0xF1])                       # ecx = esi
    a.label('w3'); a.emit([0x39, 0xE9]); a.jcc32(0x83, 'raw')
    a.emit([0x8A, 0x01, 0x41, 0x3C, 0x81]); a.jcc8(0x72, 'w3'); a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'w3')
    a.emit([0x89, 0xE9, 0x29, 0xF1])                          # ecx = ebp-esi
    a.emit([0x83, 0xF9, 0x40]); a.jcc32(0x87, 'raw')
    if pairs_va is not None:   # 稱號對照表（detail_name_patch 的 [n][CP932][m][Big5]… 0 結尾）整詞比對
        a.emit([0x51, 0xBA], a.imm32(pairs_va))                       # push ecx; edx = table
        a.label('p0'); a.emit([0x0F, 0xB6, 0x02, 0x85, 0xC0]); a.jcc32(0x84, 'p9')
        a.emit([0x39, 0xC8]); a.jcc32(0x85, 'p8')                     # 長度不同 → 下一筆
        a.emit([0x56, 0x57, 0x51, 0x8D, 0x7A, 0x01, 0xFC, 0xF3, 0xA6, 0x59, 0x5F, 0x5E]); a.jcc32(0x85, 'p8')
        a.emit([0x8D, 0x54, 0x0A, 0x01, 0x0F, 0xB6, 0x02, 0x42])      # edx = Big5 值；eax = 長度
        a.emit([0x8D, 0x0C, 0x07, 0x39, 0xD9]); a.jcc32(0x87, 'p9')   # 放不下 → 不用
        a.emit([0x56, 0x89, 0xD6, 0x89, 0xC1, 0xF3, 0xA4, 0x5E])      # 複製到 edi
        a.emit([0x59, 0x89, 0xEE]); a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'tok'))
        a.label('p8'); a.emit([0x8D, 0x54, 0x02, 0x01, 0x0F, 0xB6, 0x02, 0x8D, 0x54, 0x02, 0x01])
        a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'p0'))
        a.label('p9'); a.emit([0x59])
    a.emit([0x83, 0x3D], a.imm32(catok), [0x00]); a.jcc8(0x74, 'dec')
    a.emit([0x51])                                            # push ecx（保存 len）
    a.emit([0x68], a.imm32(0x101), [0x68], a.imm32(wbuf), [0x6A, 0x03, 0x6A, 0xFF, 0x51, 0x56],
           [0x68], a.imm32(ctx))
    a.call_rel(CAT_FIND)
    a.emit([0x83, 0xC4, 0x1C, 0x59])                          # add esp,0x1c; pop ecx
    a.emit([0x8D, 0x50, 0xFF, 0x81, 0xFA], a.imm32(0xFF)); a.jcc32(0x86, 'conv')
    a.label('dec')
    if norm is not None:   # 人名（存檔中的 CP932 角色名）→ FindCopyNorm 名字音節表（與詳情視窗同一路徑）
        a.emit([0x51, 0x68], a.imm32(wbuf), [0x51, 0x56])   # push ecx; push wbuf; push ecx; push esi
        a.call_rel(norm)
        a.emit([0x59, 0x85, 0xC0]); a.jcc32(0x85, 'conv')   # pop ecx; test eax,eax; jnz conv
    a.emit([0x68], a.imm32(0x100), [0x68], a.imm32(wbuf), [0x51, 0x56, 0x6A, 0x00], [0x68], a.imm32(932))
    a.call_ind(mbtwc_slot)
    a.emit([0x85, 0xC0]); a.jcc32(0x84, 'raw')
    if translit:   # wbuf 內假名 → 漢字（就地壓縮；eax = 新長度）
        a.emit([0x56, 0x57, 0xBE], a.imm32(wbuf), [0xBF], a.imm32(wbuf), [0x8D, 0x14, 0x45], a.imm32(wbuf))
        a.label('k0'); a.emit([0x39, 0xD6]); a.jcc8(0x73, 'k9')                  # cmp esi,edx; jae
        a.emit([0x0F, 0xB7, 0x06, 0x83, 0xC6, 0x02])                             # movzx eax,word[esi]; add esi,2
        a.emit([0x3D], a.imm32(0x30FC)); a.jcc8(0x74, 'k0')                      # 長音 → 略
        a.emit([0x3D], a.imm32(0x30FB)); a.jcc8(0x75, 'k1')
        a.emit([0xB8], a.imm32(0x2027)); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'k8'))
        a.label('k1'); a.emit([0x3D], a.imm32(0x306E)); a.jcc8(0x75, 'kn')        # 平假名「の」→「之」
        a.emit([0xB8], a.imm32(0x4E4B)); a.emit([0xEB, 0]); a.fix8.append((len(a.b) - 1, 'k8'))
        a.label('kn'); a.emit([0x8D, 0x88], a.imm32((-0x3041) & 0xFFFFFFFF), [0x83, 0xF9, 0x55]); a.jcc8(0x77, 'k2')
        a.emit([0x83, 0xC0, 0x60])                                               # 平假名 → 片假名
        a.label('k2'); a.emit([0x8D, 0x88], a.imm32((-0x30A1) & 0xFFFFFFFF), [0x83, 0xF9, 0x55]); a.jcc8(0x77, 'k8')
        a.emit([0x0F, 0xB7, 0x04, 0x4D], a.imm32(max(_table_va, 0)))                     # movzx eax,word[ecx*2+tbl]
        a.emit([0x85, 0xC0]); a.jcc8(0x74, 'k0')                                 # 0 → 略（促音）
        a.label('k8'); a.emit([0x66, 0x89, 0x07, 0x83, 0xC7, 0x02, 0xEB, 0]); a.fix8.append((len(a.b) - 1, 'k0'))
        a.label('k9'); a.emit([0x89, 0xF8, 0x2D], a.imm32(wbuf), [0xD1, 0xE8, 0x5F, 0x5E])
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
    a.emit([0xC7, 0x44, 0x24, arg_esp], a.imm32(sbuf))        # 字串參數 = sbuf

    def tail():
        if target_ind is not None:
            a.emit([0xFF, 0x25], a.imm32(target_ind))         # jmp [IAT]
        else:
            a.emit([0xE9]); a.emit(struct.pack('<i', target - (a.here() + 4)))
    tail()
    a.label('noswap'); a.emit([0x61]); tail()
    code = a.finish()
    return code, sbuf + 0x100 - data


def model(header: str, lookup: dict) -> str:
    """Python 模型（僅空白分隔的情形；stub 另以 TAB 分隔）：以空白切詞，CP932 日文詞查表或照字形轉 cp950（kana → ?）。"""
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


def patch(exe: bytes, pairs_va=None):
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
    probe, _ = build_stub(code_va, code_va + 0x400, mbtwc, wctmb, pairs_va=pairs_va)
    data_va = code_va + ((len(probe) + 0xf) & ~0xf)
    code, dlen = build_stub(code_va, data_va, mbtwc, wctmb, pairs_va=pairs_va)
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
