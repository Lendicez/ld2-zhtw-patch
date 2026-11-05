r"""m064 lab：CDC::TextOut 全域日文後備（charset_patch 副作用的通用解）。

MFC `CDC::TextOut(int x, int y, LPCSTR s, int n)`（0x4e13d7，CDC／CPaintDC／CClientDC／CWindowDC
四個 vtable 的 +0x5c 都指向它）原本直接 `TextOutA(m_hDC, …)`。字型改 CHINESEBIG5 後，未翻譯的 CP932
字串（物品名、技能名、NPC 名…）會以 Big5 解讀而亂碼。

本修補把該函式開頭改成 `jmp TO_HOOK`：
    若 1 ≤ n ≤ 255、TextOutW 指標（v4 helper 於 .ld2i 0xb25160 解析）存在、且字串含 0x81–0x9F 位元組
    → MultiByteToWideChar(932) 後 TextOutW（以日文原文正確顯示）
    否則 → 原樣 TextOutA（Big5 譯文、ASCII、半形不受影響）
判斷依據同 nto_fallback_patch：cp950 繁中字串不含 0x80–0xA0 的位元組。只寫 lab 複本。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot

CDC_TEXTOUT = 0x4e13d7
CDC_TEXTOUT_BODY = bytes.fromhex('ff742410ff742410ff742410ff742410ff7104ff1558505200c21000')  # → TextOutA 0x525058; ret 0x10
TEXTOUTA_IAT = 0x525058
TEXTOUTW_PTR = 0xb25160
TO_HOOK = 0xae5f10
CP932 = 932


def build_stub(mbtwc_slot, origin=TO_HOOK):
    a = Asm(origin)
    a.emit([0x55, 0x8B, 0xEC, 0x56, 0x57])                    # push ebp; mov ebp,esp; push esi; push edi
    a.emit([0x8B, 0x75, 0x10, 0x8B, 0x7D, 0x14])              # esi=s; edi=n
    a.emit([0x85, 0xF6]); a.jcc8(0x74, 'orig')
    a.emit([0x8D, 0x47, 0xFF, 0x3D], a.imm32(0xFE)); a.jcc8(0x77, 'orig')   # (n-1) > 254 → orig
    a.emit([0x83, 0x3D], a.imm32(TEXTOUTW_PTR), [0x00]); a.jcc8(0x74, 'orig')
    a.emit([0x31, 0xD2])                                      # xor edx,edx
    a.label('scan')
    a.emit([0x39, 0xFA]); a.jcc8(0x73, 'orig')                # cmp edx,edi; jae
    a.emit([0x8A, 0x04, 0x16, 0x42])                          # mov al,[esi+edx]; inc edx
    a.emit([0x3C, 0x81]); a.jcc8(0x72, 'scan')
    a.emit([0x3C, 0x9F]); a.jcc8(0x77, 'scan')
    a.emit([0x81, 0xEC], a.imm32(0x200), [0x89, 0xE2])        # sub esp,0x200; mov edx,esp
    a.emit([0x51])                                            # push ecx（CDC*）
    a.emit([0x68], a.imm32(0x100), [0x52, 0x57, 0x56, 0x6A, 0x00], [0x68], a.imm32(CP932))
    a.call_ind(mbtwc_slot)
    a.emit([0x59])                                            # pop ecx
    a.emit([0x85, 0xC0]); a.jcc8(0x74, 'unwind')
    a.emit([0x89, 0xE2])                                      # mov edx,esp（wbuf）
    a.emit([0x50, 0x52, 0xFF, 0x75, 0x0C, 0xFF, 0x75, 0x08, 0xFF, 0x71, 0x04])   # n,w,y,x,hdc
    a.emit([0xFF, 0x15], a.imm32(TEXTOUTW_PTR))               # call [TextOutW]
    a.emit([0x81, 0xC4], a.imm32(0x200))
    a.emit([0x5F, 0x5E, 0x5D, 0xC2, 0x10, 0x00])              # pop edi; pop esi; pop ebp; ret 0x10
    a.label('unwind'); a.emit([0x81, 0xC4], a.imm32(0x200))
    a.label('orig'); a.emit([0x5F, 0x5E, 0x5D])
    a.emit(bytes.fromhex('ff742410ff742410ff742410ff742410ff7104'))   # 原函式本體
    a.call_ind(TEXTOUTA_IAT)
    a.emit([0xC2, 0x10, 0x00])
    return a.finish()


def model(s: bytes, n: int, have_w=True):
    """Python 模型：'w'（CP932→TextOutW）或 'a'（原 TextOutA）。"""
    if not s or not 1 <= n <= 255 or not have_w:
        return 'a'
    return 'w' if any(0x81 <= b <= 0x9F for b in s[:n]) else 'a'


def patch(exe: bytes):
    secs, pe = sections(exe)
    t = secs['.ld2t']
    fo = va2off(secs, CDC_TEXTOUT)
    if exe[fo:fo + len(CDC_TEXTOUT_BODY)] != CDC_TEXTOUT_BODY:
        raise ValueError('CDC::TextOut body mismatch')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    if iat_slot(exe, secs, pe, 'GDI32.dll', 'TextOutA') != TEXTOUTA_IAT:
        raise ValueError('TextOutA IAT slot moved')
    code = build_stub(mbtwc)
    so = va2off(secs, TO_HOOK)
    end_rva = TO_HOOK + len(code) - 0x400000
    if end_rva > t['va'] + t['rsz'] or any(exe[so:so + len(code)]):
        raise ValueError('.ld2t cave not free for TO_HOOK')
    out = bytearray(exe)
    out[so:so + len(code)] = code
    out[fo] = 0xE9
    struct.pack_into('<i', out, fo + 1, TO_HOOK - (CDC_TEXTOUT + 5))
    struct.pack_into('<I', out, t['hdr'] + 8, max(t['vsz'], end_rva - t['va']))
    return bytes(out), {'to_hook': hex(TO_HOOK), 'len': len(code), 'hex': code.hex()}
