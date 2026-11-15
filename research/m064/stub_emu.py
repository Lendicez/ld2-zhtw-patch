"""savelist_patch 轉換 stub 的模擬執行（測試用；需要 unicorn）。

把 catalog（CAT_OPEN／CAT_FIND）、名字音節表（FindCopyNorm）、MultiByteToWideChar(932)、
WideCharToMultiByte(950) 換成 Python 實作，實際執行 build_stub 產生的 x86 程式碼，回傳轉換後的位元組。
"""
import struct

import savelist_patch as S
from tab_title_patch import NORM

ORIGIN, DATA = 0xB28000, 0xB2A000
MBTWC_SLOT, WCTMB_SLOT = 0x52537C, 0x525378
HOOK_MBTWC, HOOK_WCTMB = 0x700000, 0x700010
STACK, STR = 0x200000, 0x300000


def run(src: bytes, catalog=None, names=None, pairs=None, mixw=False):
    """src：送進 stub 的原始位元組（不含結尾 0）。catalog／names：{CP932 bytes: 中文 str}。pairs：稱號對照 {CP932 bytes: Big5 bytes}。
    mixw＝True：改執行混合解碼常式 MIXW（mixdec_patch），回傳 UTF-16 解碼後的 str。"""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
    catalog, names, pairs = catalog or {}, names or {}, pairs or {}
    pairs_va = 0xB2C000 if pairs else None
    if mixw:
        import mixdec_patch as M
        code = M.build(ORIGIN, DATA, MBTWC_SLOT, pairs_va)
    else:
        code, dlen = S.build_stub(ORIGIN, DATA, MBTWC_SLOT, WCTMB_SLOT, pairs_va=pairs_va)
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    pages = set()
    for base, size in ((0xB28000, 0x8000), (0x525000, 0x1000), (0x700000, 0x1000), (0xAE4000, 0x3000),
                       (NORM & ~0xFFF, 0x1000), (S.SEND_DLG_ITEM_MSG & ~0xFFF, 0x1000), (STACK, 0x10000), (STR, 0x1000)):
        pages.update(range(base, base + size, 0x1000))
    for p in sorted(pages):
        uc.mem_map(p, 0x1000)
    uc.mem_write(ORIGIN, code)
    uc.mem_write(MBTWC_SLOT, struct.pack('<I', HOOK_MBTWC)); uc.mem_write(WCTMB_SLOT, struct.pack('<I', HOOK_WCTMB))
    if pairs:
        blob = b''.join(bytes([len(k)]) + k + bytes([len(v)]) + v for k, v in pairs.items()) + b'\0'
        uc.mem_write(pairs_va, blob)
    uc.mem_write(STR, src + b'\0')
    esp = STACK + 0x8000
    if mixw:   # MIXW(src, len) stdcall：返回位址設在 SendDlgItemMessage 頁（命中即停）
        uc.mem_write(esp, struct.pack('<3I', S.SEND_DLG_ITEM_MSG, STR, len(src)))
    else:
        uc.mem_write(esp, struct.pack('<5I', 0xDEAD, 0, 0, 0, STR))   # [esp+0x10] = 字串參數
    uc.reg_write(UC_X86_REG_ESP, esp)
    state = {'done': False}

    def rd(a, n): return bytes(uc.mem_read(a, n))
    def arg(i): return struct.unpack('<I', rd(uc.reg_read(UC_X86_REG_ESP) + 4 + 4 * i, 4))[0]
    def ret(val, nargs):
        sp = uc.reg_read(UC_X86_REG_ESP); ra = struct.unpack('<I', rd(sp, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, val & 0xFFFFFFFF); uc.reg_write(UC_X86_REG_ESP, sp + 4 + 4 * nargs)
        uc.reg_write(UC_X86_REG_EIP, ra)
    def put_w(buf, text):
        uc.mem_write(buf, text.encode('utf-16-le')); return len(text.encode('utf-16-le')) // 2

    def hook(uc_, addr, size, _):
        if addr == S.SEND_DLG_ITEM_MSG:
            state['done'] = True; uc_.emu_stop()
        elif addr == S.CAT_OPEN:
            ret(1, 0)                                        # cdecl：呼叫端自行 add esp
        elif addr == S.CAT_FIND:
            s, n, wbuf = arg(1), arg(2), arg(5)
            key = rd(s, n)
            ret(put_w(wbuf, catalog[key]) if key in catalog else 0, 0)
        elif addr == NORM:
            s, n, wbuf = arg(0), arg(1), arg(2)
            key = rd(s, n)
            ret(put_w(wbuf, names[key]) if key in names else 0, 3)
        elif addr == HOOK_MBTWC:
            cp, s, n, wbuf = arg(0), arg(2), arg(3), arg(4)
            ret(put_w(wbuf, rd(s, n).decode(f'cp{cp}', 'replace')), 6)
        elif addr == HOOK_WCTMB:
            wbuf, cch, dst, cb = arg(2), arg(3), arg(4), arg(5)
            b = rd(wbuf, cch * 2).decode('utf-16-le').encode('cp950', 'replace')[:cb]
            uc.mem_write(dst, b); ret(len(b), 8)
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(ORIGIN, 0, count=200000)
    assert state['done'], 'stub 沒有跳到目標'
    if mixw:
        import mixdec_patch as M
        n = uc.reg_read(UC_X86_REG_EAX)
        assert n, 'MIXW 回傳 0（失敗）'
        return rd(M.layout(DATA)[2], n * 2).decode('utf-16-le')
    p = struct.unpack('<I', rd(esp + 0x10, 4))[0]
    out = rd(p, 0x200)
    return out[:out.index(b'\0')]
