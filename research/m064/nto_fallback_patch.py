r"""m064 lab：NameTextOut 查無時的日文後備顯示。

charset_patch 把字型 A／B 改成 CHINESEBIG5 後，NameTextOut（m063 v4）查表**查無**的字串會走原
CDC::TextOutA，以 Big5 解讀 CP932 → 亂碼（例：詳情視窗「特殊技能」值、物品名）。
本修補在 NameTextOut 唯一的查表呼叫（0xae598d，tab_title_patch 已導向 FindCopyNorm）外再包一層：

    units = FindCopyNorm(ansi, n, dest)
    if units == 0 and 字串含 0x81–0x9F 的位元組:
        units = MultiByteToWideChar(932, 0, ansi, n, dest, 128)   # 以日文原文顯示（TextOutW）

判斷依據：cp950 編出的繁中（lead 0xA1–0xF9、trail 0x40–0x7E／0xA1–0xFE）**不會**出現 0x80–0xA0 的位元組；
CP932 日文（平假名／片假名／大部分漢字）幾乎都含 lead 0x81–0x9F。所以原位改成 Big5 的字串不會被誤解碼；
純半形片假名字串不判定（交給 FindCopyNorm 的半形→全形）。只寫 lab 複本；production_can_apply=false。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, NORM, NTO_FINDCOPY_CALL

NTO_FB = 0xae5ec0
CP932, MAX_UNITS = 932, 128


def build_stub(mbtwc_slot, origin=NTO_FB, norm=NORM):
    a = Asm(origin)
    a.emit([0x55, 0x8B, 0xEC, 0x56])                         # push ebp; mov ebp,esp; push esi
    a.emit([0xFF, 0x75, 0x10, 0xFF, 0x75, 0x0C, 0xFF, 0x75, 0x08])
    a.call_rel(norm)
    a.emit([0x85, 0xC0]); a.jcc8(0x75, 'out')                # 命中 → 原樣回傳
    a.emit([0x8B, 0x75, 0x08, 0x8B, 0x4D, 0x0C])             # esi=ansi; ecx=n
    a.label('scan')
    a.emit([0x85, 0xC9]); a.jcc8(0x74, 'miss')
    a.emit([0x8A, 0x06, 0x46, 0x49])                         # mov al,[esi]; inc esi; dec ecx
    a.emit([0x3C, 0x81]); a.jcc8(0x72, 'scan')               # cmp al,0x81; jb
    a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'scan')               # cmp al,0x9f; ja
    a.emit([0x68], a.imm32(MAX_UNITS), [0xFF, 0x75, 0x10, 0xFF, 0x75, 0x0C, 0xFF, 0x75, 0x08],
           [0x6A, 0x00], [0x68], a.imm32(CP932))
    a.call_ind(mbtwc_slot)
    a.jcc8(0xEB, 'out')
    a.label('miss'); a.emit([0x31, 0xC0])
    a.label('out'); a.emit([0x5E, 0x5D, 0xC2, 0x0C, 0x00])  # pop esi; pop ebp; ret 0xc
    return a.finish()


def model(ansi: bytes, hit=None):
    """Python 模型：回傳 'hit'／'ja'（以 CP932 解碼顯示）／None（原路徑）。"""
    if hit:
        return 'hit'
    return 'ja' if any(0x81 <= b <= 0x9F for b in ansi) else None


def patch(exe: bytes):
    secs, pe = sections(exe)
    t = secs['.ld2t']
    co = va2off(secs, NTO_FINDCOPY_CALL)
    if exe[co] != 0xE8 or NTO_FINDCOPY_CALL + 5 + struct.unpack_from('<i', exe, co + 1)[0] != NORM:
        raise ValueError('NameTextOut lookup call is not routed to FindCopyNorm (run tab_title_patch first)')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    code = build_stub(mbtwc)
    so = va2off(secs, NTO_FB)
    end_rva = NTO_FB + len(code) - 0x400000
    if end_rva > t['va'] + t['rsz'] or any(exe[so:so + len(code)]):
        raise ValueError('.ld2t cave not free for NTO_FB')
    out = bytearray(exe)
    out[so:so + len(code)] = code
    struct.pack_into('<i', out, co + 1, NTO_FB - (NTO_FINDCOPY_CALL + 5))
    struct.pack_into('<I', out, t['hdr'] + 8, max(t['vsz'], end_rva - t['va']))
    return bytes(out), {'nto_fb': hex(NTO_FB), 'len': len(code), 'hex': code.hex()}
