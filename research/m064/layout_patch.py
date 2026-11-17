r"""視窗狀態（1.0.4）：主視窗最大化還原、子視窗限制在可見範圍內。

擁有者需求（2026-11-18）：主視窗調小後，有些子視窗跑到範圍外看不到，必須拉大主視窗才出現；希望記住玩家的
視窗狀態與子視窗位置（例：視窗化 1920×1080、視窗化最大化；不考慮全螢幕）。

量測：
- 主視窗：原版已把位置大小寫入 ld95.ini `[Settings] FrameWindowPos`，下次會還原；但「最大化」只在啟動參數
  剛好是 SW_SHOWNORMAL 時才沿用（0x48b54e：`cmp eax,1 ; je ; mov [wp.showCmd],eax`），其他啟動方式
  （SW_SHOWDEFAULT 等）一律變回一般視窗（job 1433）。
- 子視窗（場景、地圖、資訊、隊伍…）的位置，遊戲本來就記在**存檔**裡（LUNAS00x.LDP 偏移 0x184 起的
  WINDOWPLACEMENT，例：資訊 (895,225)），讀檔後以 CWnd::SetWindowPos 放回（0x4d03b3，job 1451）。
  所以位置已會依存檔記住；問題是存檔時主視窗比較大，之後主視窗較小時就落在工作區外（job 1434）。

修法（小段程式附加在 .ld2i 尾）：
- C（0x48b54e）：啟動要求最小化（2／6／7）才照辦；否則用存下的 showCmd，但存下的是最小化時改回一般／最大化
  （依 WPF_RESTORETOMAXIMIZED）。
- G（0x4ea888，CWnd::SetWindowPos 內的 call [SetWindowPos]）：視窗的父視窗是 MDI 工作區、且有移動（沒有
  SWP_NOMOVE）時，把 x、y 限制在工作區內（大小用 cx／cy；SWP_NOSIZE 時用目前大小；太大則靠左上）。
  只改位置參數，不改大小、不改存檔；玩家用滑鼠拖曳的視窗不經這裡，不受影響。

小段程式以 keystone 組譯；倉庫內存 `layout_stub.json`（在 BASE0 組譯的位元組與絕對位址重定位表），
建置時不需 keystone。`python layout_patch.py --regen` 重新產生。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))

# 本版 Ld95.exe（Steam 1.0.3.16）固定位址
IAT = {'SetWindowPos': 0x525534, 'GetClientRect': 0x525618, 'GetWindowRect': 0x52561c, 'GetParent': 0x5255a8}
AFX_MODULE_STATE = 0x4e0fdb          # call → eax；[eax+4] = 目前的 CWinApp
FRAME_MDICLIENT = 0xd4               # CMDIFrameWnd::m_hWndMDIClient
APP_MAINWND = 0x20                   # CWinThread::m_pMainWnd

SITES = {   # va: (原位元組, 種類)
    0x48b54e: (bytes.fromhex('83f801740489442424'), 'C'),   # cmp eax,1 ; je +4 ; mov [esp+0x24],eax
    0x4ea888: (bytes.fromhex('ff1534555200'), 'G'),         # CWnd::SetWindowPos：call [SetWindowPos]
}

ASM = r"""
; ===== G：CWnd::SetWindowPos 的 call [SetWindowPos]（堆疊 [ret][hwnd][after][x][y][cx][cy][flags]） =====
hook_swp:
    pushad
    lea ebp, [esp+0x24]                 ; 第一個參數（hwnd）
    test dword ptr [ebp+0x18], 2        ; SWP_NOMOVE
    jnz g_done
    mov eax, {AFX}
    call eax
    mov eax, [eax+4]
    mov eax, [eax+{MAINWND}]
    test eax, eax
    jz g_done
    mov ebx, [eax+{MDICLIENT}]          ; MDI 工作區
    test ebx, ebx
    jz g_done
    push dword ptr [ebp]
    call dword ptr [{GetParent}]
    cmp eax, ebx
    jne g_done
    sub esp, 0x20                       ; [esp]=工作區 rect  [esp+0x10]=視窗 rect
    lea eax, [esp]
    push eax
    push ebx
    call dword ptr [{GetClientRect}]
    test eax, eax
    jz g_free
    mov esi, [ebp+0x10]                 ; cx
    mov edi, [ebp+0x14]                 ; cy
    test dword ptr [ebp+0x18], 1        ; SWP_NOSIZE → 用目前大小
    jz g_size
    lea eax, [esp+0x10]
    push eax
    push dword ptr [ebp]
    call dword ptr [{GetWindowRect}]
    test eax, eax
    jz g_free
    mov esi, [esp+0x18]
    sub esi, [esp+0x10]
    mov edi, [esp+0x1c]
    sub edi, [esp+0x14]
g_size:
    mov eax, [ebp+8]                    ; x
    mov edx, [esp+8]                    ; 工作區寬
    sub edx, esi
    cmp eax, edx
    jle g_x1
    mov eax, edx
g_x1:
    test eax, eax
    jge g_x2
    xor eax, eax
g_x2:
    mov [ebp+8], eax
    mov eax, [ebp+0xc]                  ; y
    mov edx, [esp+0xc]                  ; 工作區高
    sub edx, edi
    cmp eax, edx
    jle g_y1
    mov eax, edx
g_y1:
    test eax, eax
    jge g_y2
    xor eax, eax
g_y2:
    mov [ebp+0xc], eax
g_free:
    add esp, 0x20
g_done:
    popad
    jmp dword ptr [{SetWindowPos}]

; ===== C：啟動時決定 showCmd（取代 cmp eax,1 / je / mov [esp+0x24],eax；eax=nCmdShow；wp 在呼叫端 esp+0x1c） =====
hook_show:
    cmp eax, 2
    je hs_set
    cmp eax, 6
    je hs_set
    cmp eax, 7
    je hs_set
    mov eax, [esp+0x28]                 ; 存下的 showCmd
    cmp eax, 2
    je hs_fix
    cmp eax, 6
    je hs_fix
    cmp eax, 7
    jne hs_ret
hs_fix:
    mov eax, 1
    test byte ptr [esp+0x24], 2         ; WPF_RESTORETOMAXIMIZED
    jz hs_set
    mov eax, 3
hs_set:
    mov [esp+0x28], eax
hs_ret:
    ret
"""

ENTRIES = {'C': 'hook_show', 'G': 'hook_swp'}
BASE0, BASE1 = 0x10000000, 0x20000000
STUB_JSON = HERE / 'layout_stub.json'


def _asm_text():
    return ASM.format(AFX=hex(AFX_MODULE_STATE), MAINWND=hex(APP_MAINWND), MDICLIENT=hex(FRAME_MDICLIENT),
                      GetParent=hex(IAT['GetParent']), GetClientRect=hex(IAT['GetClientRect']),
                      GetWindowRect=hex(IAT['GetWindowRect']), SetWindowPos=hex(IAT['SetWindowPos']))


def regen():
    """以 keystone 在兩個基底組譯，比對差異得到絕對位址重定位表（只允許 +Δ 的 4 位元組欄位）。"""
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    src = '\n'.join(l.split(';')[0].rstrip() for l in _asm_text().splitlines())
    a, b = (bytes(ks.asm(src, base)[0]) for base in (BASE0, BASE1))
    assert len(a) == len(b)
    delta, relocs, i = BASE1 - BASE0, [], 0
    while i < len(a):
        if a[i] != b[i]:
            for k in range(4):
                p = i - k
                if p >= 0 and (struct.unpack_from('<I', b, p)[0] - struct.unpack_from('<I', a, p)[0]) & 0xffffffff == delta:
                    relocs.append(p); i = p + 4; break
            else:
                raise ValueError(f'非絕對位址差異 @ {i}')
            continue
        i += 1
    syms = {}
    for name in ENTRIES.values():
        enc, _ = ks.asm(src + f'\n__probe: mov eax, {name}\n', BASE0)
        syms[name] = struct.unpack_from('<I', bytes(enc), len(enc) - 4)[0] - BASE0
    doc = {'base0': BASE0, 'hex': a.hex(), 'relocs': relocs, 'symbols': syms}
    STUB_JSON.write_text(json.dumps(doc, indent=1) + '\n', 'utf-8')
    return doc


def load_stub(base: int):
    doc = json.loads(STUB_JSON.read_text('utf-8'))
    code = bytearray(bytes.fromhex(doc['hex']))
    for p in doc['relocs']:
        v = struct.unpack_from('<I', code, p)[0]
        struct.pack_into('<I', code, p, (v - doc['base0'] + base) & 0xffffffff)
    return bytes(code), {k: base + v for k, v in doc['symbols'].items()}


def _va2off(exe: bytes, va: int) -> int:
    pe = struct.unpack_from('<I', exe, 0x3C)[0]
    nsec, opt_size = struct.unpack_from('<H', exe, pe + 6)[0], struct.unpack_from('<H', exe, pe + 20)[0]
    base = struct.unpack_from('<I', exe, pe + 24 + 28)[0]
    for i in range(nsec):
        o = pe + 24 + opt_size + 40 * i
        vs, rva, rs, raw = struct.unpack_from('<IIII', exe, o + 8)
        if rva <= va - base < rva + max(vs, rs):
            return raw + va - base - rva
    raise ValueError('VA 不在任何區段')


def patch(exe: bytes):
    from ld2patch.pe_resources import PE
    pe = PE(exe)
    last = max(pe.sections, key=lambda s: s['rp'])
    if last['name'] != '.ld2i' or len(exe) != last['rp'] + last['rs']:
        raise ValueError('.ld2i is not the file tail')
    stub_va = pe.base + last['va'] + last['rs']
    code, sym = load_stub(stub_va)
    out = bytearray(exe)
    for va, (old, kind) in SITES.items():
        o = _va2off(exe, va)
        if bytes(out[o:o + len(old)]) != old:
            raise ValueError(f'{hex(va)} 內容與預期不符')
        new = b'\xe8' + struct.pack('<i', sym[ENTRIES[kind]] - (va + 5))
        out[o:o + len(old)] = new + b'\x90' * (len(old) - 5)
    grow = 0x1000
    assert len(code) < grow
    out += code + b'\xcc' * (grow - len(code))
    hdr = last['header']
    struct.pack_into('<I', out, hdr + 8, last['rs'] + grow)
    struct.pack_into('<I', out, hdr + 16, last['rs'] + grow)
    salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
    struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'stub_va': hex(stub_va), 'bytes': len(code), 'sites': [hex(v) for v in SITES]}


if __name__ == '__main__':
    if '--regen' in sys.argv:
        d = regen(); print(len(d['hex']) // 2, 'bytes', len(d['relocs']), 'relocs', d['symbols'])
