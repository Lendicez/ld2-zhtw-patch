r"""m064 lab：角色詳情視窗名字欄（稱號＋名字）繁中化。

詳情視窗繪製函式（0x4d77a0 起）以
    call 0x44dab0   ; 稱號 getter：CString ← 角色記錄 +0x19（CP932，生成時由稱號表複製）
    call 0x44d870   ; 名字 getter：CString ← 角色記錄 +0x08（CP932）
組成「稱號 名字」後經 CDC::TextOut（字型 A，charset_patch 後為 CHINESEBIG5）繪製，原文會亂碼。
稱號與名字都存在角色記錄（存檔）裡，所以不在稱號表原位改字（避免把 Big5 寫進存檔），
改在這兩個 getter 呼叫點後轉換 CString：
    0x4d78a1 call 0x44dab0 → call EPI_STUB：查「CP932 稱號→Big5」對照表（附加在 .ld2i 尾端）
    0x4d78bc call 0x44d870 → call NAME_STUB：FindCopyNorm（v4 人名＋半形正規化）→ CP950
查無 → 原樣保留。兩個 stub 都是 thiscall 透傳（ret 8），只動 getter 回傳的 CString（SetString 0x405990）。
只寫 lab 複本；production_can_apply=false。輸入須已套 tab_title_patch（FindCopyNorm 已裝）。
"""
import hashlib, struct
from tab_title_patch import Asm, sections, va2off, iat_slot, NORM, BASE

SITE_EPI, GET_EPI = 0x4d78a1, 0x44dab0
SITE_NAME, GET_NAME = 0x4d78bc, 0x44d870
SET_STRING = 0x405990                 # CSimpleStringT::SetString(const char*, int)，thiscall ret 8
SET_STRING_HEAD = bytes.fromhex('53568b74241085f68bd9')
GETTER_TAILS = {GET_EPI: 0x19, GET_NAME: 0x08}   # getter 內 `add ecx,+X`（記錄欄位）
EPI_STUB, NAME_STUB = 0xae5d40, 0xae5dc0
WBUF2, ABUF2 = 0xb25e80, 0xb25f80     # .ld2i：128 UTF-16 units／128 bytes
CP950 = 950


def build_pairs(pairs) -> bytes:
    """[(cp932, big5)] → [u8 n][n bytes][u8 m][m bytes]…，0 結尾。鍵唯一。"""
    out, seen = bytearray(), {}
    for k, v in pairs:
        if not (0 < len(k) < 256 and 0 < len(v) < 128 and b'\0' not in k + v):
            raise ValueError('pair bounds')
        if k in seen:
            if seen[k] != v:
                raise ValueError(f'ambiguous key {k.hex()}')
            continue
        seen[k] = v
        out += bytes([len(k)]) + k + bytes([len(v)]) + v
    return bytes(out + b'\0')


def pair_lookup(table: bytes, key: bytes):
    """Python 模型（與 stub 行為一致，測試用）。"""
    i = 0
    while table[i]:
        n = table[i]; k = table[i + 1:i + 1 + n]; m = table[i + 1 + n]
        if k == key:
            return table[i + 2 + n:i + 2 + n + m]
        i += 2 + n + m
    return None


def _passthrough_head(a, getter):
    # [esp]=ret [esp+4]=out [esp+8]=idx → 原樣轉呼叫 getter（ecx=this 不動）
    a.emit([0xFF, 0x74, 0x24, 0x08, 0xFF, 0x74, 0x24, 0x08])
    a.call_rel(getter)
    a.emit([0x60])                                   # pushad
    a.emit([0x89, 0xC7, 0x8B, 0x37, 0x8B, 0x4E, 0xF4])   # edi=CString*；esi=buf；ecx=len([buf-0xc])
    a.emit([0x85, 0xC9]); a.jcc32(0x84, 'done')
    a.emit([0x81, 0xF9], a.imm32(0x40)); a.jcc32(0x87, 'done')


def _tail(a):
    a.label('done'); a.emit([0x61, 0xC2, 0x08, 0x00])   # popad; ret 8


def build_epi_stub(table_va, origin=EPI_STUB):
    a = Asm(origin)
    _passthrough_head(a, GET_EPI)
    a.emit([0xBB], a.imm32(table_va))                # ebx = table
    a.label('loop')
    a.emit([0x0F, 0xB6, 0x03, 0x85, 0xC0]); a.jcc32(0x84, 'done')   # movzx eax,[ebx]; test
    a.emit([0x39, 0xC8]); a.jcc8(0x75, 'next')       # cmp eax,ecx; jne next
    a.emit([0x56, 0x51, 0x8D, 0x7B, 0x01, 0xFC, 0xF3, 0xA6, 0x59, 0x5E])  # push esi/ecx; edi=ebx+1; repe cmpsb; pop
    a.jcc8(0x75, 'next')
    a.emit([0x8D, 0x54, 0x0B, 0x01])                 # edx = ebx+1+ecx（big5 長度位元組）
    a.emit([0x0F, 0xB6, 0x02, 0x42])                 # movzx eax,[edx]; inc edx
    a.emit([0x8B, 0x7C, 0x24, 0x00])                 # edi = pushad 的 edi（CString*）
    a.emit([0x50, 0x52, 0x89, 0xF9])                 # push len; push ptr; mov ecx,edi
    a.call_rel(SET_STRING)
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'done'))
    a.label('next')
    a.emit([0x8D, 0x5C, 0x03, 0x01])                 # ebx = ebx+1+eax
    a.emit([0x0F, 0xB6, 0x03, 0x8D, 0x5C, 0x03, 0x01])   # eax=[ebx]; ebx=ebx+1+eax
    a.emit([0xE9, 0, 0, 0, 0]); a.fix32.append((len(a.b) - 4, 'loop'))
    _tail(a)
    return a.finish()


def build_name_stub(wctmb_slot, origin=NAME_STUB, norm=NORM):
    a = Asm(origin)
    _passthrough_head(a, GET_NAME)
    a.emit([0x68], a.imm32(WBUF2), [0x51, 0x56])     # FindCopyNorm(esi, ecx, WBUF2)
    a.call_rel(norm)
    a.emit([0x85, 0xC0]); a.jcc32(0x84, 'done')
    # k = WideCharToMultiByte(950, 0, WBUF2, units, ABUF2, 127, 0, 0)
    a.emit([0x6A, 0x00, 0x6A, 0x00, 0x6A, 0x7F], [0x68], a.imm32(ABUF2), [0x50], [0x68], a.imm32(WBUF2),
           [0x6A, 0x00], [0x68], a.imm32(CP950))
    a.call_ind(wctmb_slot)
    a.emit([0x85, 0xC0]); a.jcc32(0x84, 'done')
    a.emit([0x50], [0x68], a.imm32(ABUF2), [0x89, 0xF9])   # push k; push ABUF2; mov ecx,edi
    a.call_rel(SET_STRING)
    _tail(a)
    return a.finish()


def _check_call(exe, secs, site, target):
    o = va2off(secs, site)
    if exe[o] != 0xE8 or site + 5 + struct.unpack_from('<i', exe, o + 1)[0] != target:
        raise ValueError(f'site {site:#x} is not call {target:#x}')
    return o


def patch(exe: bytes, pairs):
    secs, pe = sections(exe)
    t, i = secs['.ld2t'], secs['.ld2i']
    if exe[va2off(secs, NORM):va2off(secs, NORM) + 4] != bytes.fromhex('558bec60'):
        raise ValueError('FindCopyNorm not installed (run tab_title_patch first)')
    if exe[va2off(secs, SET_STRING):va2off(secs, SET_STRING) + len(SET_STRING_HEAD)] != SET_STRING_HEAD:
        raise ValueError('SetString prologue mismatch')
    for g, fld in GETTER_TAILS.items():
        body = exe[va2off(secs, g):va2off(secs, g) + 0x80]
        if bytes([0x83, 0xC1, fld]) not in body:
            raise ValueError(f'getter {g:#x} field mismatch')
    so_e, so_n = _check_call(exe, secs, SITE_EPI, GET_EPI), _check_call(exe, secs, SITE_NAME, GET_NAME)
    # .ld2i 為最後一個區段：在檔尾附加對照表
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    if any(exe[va2off(secs, WBUF2):va2off(secs, ABUF2) + 0x80]):
        raise ValueError('.ld2i WBUF2/ABUF2 not free')
    table = build_pairs(pairs)
    table_va = BASE + i['va'] + i['rsz']
    grow = (len(table) + 0xfff) & ~0xfff
    wctmb = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'WideCharToMultiByte')
    es, ns = build_epi_stub(table_va), build_name_stub(wctmb)
    if EPI_STUB + len(es) > NAME_STUB or NAME_STUB + len(ns) - BASE > t['va'] + t['rsz']:
        raise ValueError('stub size')
    for va, code in ((EPI_STUB, es), (NAME_STUB, ns)):
        o = va2off(secs, va)
        if any(exe[o:o + len(code)]):
            raise ValueError(f'cave {va:#x} not free')
    out = bytearray(exe) + table + b'\0' * (grow - len(table))
    out[va2off(secs, EPI_STUB):va2off(secs, EPI_STUB) + len(es)] = es
    out[va2off(secs, NAME_STUB):va2off(secs, NAME_STUB) + len(ns)] = ns
    struct.pack_into('<i', out, so_e + 1, EPI_STUB - (SITE_EPI + 5))
    struct.pack_into('<i', out, so_n + 1, NAME_STUB - (SITE_NAME + 5))
    struct.pack_into('<I', out, t['hdr'] + 8, max(t['vsz'], NAME_STUB + len(ns) - BASE - t['va']))
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)          # VirtualSize
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)         # SizeOfRawData
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'epi_stub': hex(EPI_STUB), 'epi_len': len(es), 'name_stub': hex(NAME_STUB),
                        'name_len': len(ns), 'table_va': hex(table_va), 'table_bytes': len(table),
                        'sites': [hex(SITE_EPI), hex(SITE_NAME)],
                        'stub_sha256': hashlib.sha256(es + ns).hexdigest()}
