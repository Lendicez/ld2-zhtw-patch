r"""視窗狀態記憶（1.0.4）：主視窗最大化還原、子視窗位置記憶＋限制在可見範圍內。

擁有者需求（2026-11-18）：主視窗調小後，有些子視窗跑到範圍外看不到，必須拉大主視窗才出現；希望記住玩家的
視窗狀態與子視窗位置（例：視窗化 1920×1080、視窗化最大化；不考慮全螢幕）。

量測：
- 主視窗：原版已把位置大小寫入 ld95.ini `[Settings] FrameWindowPos`，下次會還原；但「最大化」只在啟動參數
  剛好是 SW_SHOWNORMAL 時才沿用（0x48b54e：`cmp eax,1 ; je ; mov [wp.showCmd],eax`），其他啟動方式
  （SW_SHOWDEFAULT 等）一律變回一般視窗（job 1433）。
- 子視窗（場景、地圖、資訊、隊伍、商店…）每次都建立在寫死的位置，與主視窗大小無關（job 1434／1435：
  主視窗 1000×700 時「資訊」x=897–1187、「地圖」y=548–885，超出 MDI 工作區 984×584）。建立走 MFC
  CMDIChildWnd::Create 的 `SendMessage(MDI client, WM_MDICREATE, 0, &MDICREATESTRUCT)`（0x4ec0dd）。

修法（小段程式附加在 .ld2i 尾）：
- C（0x48b54e）：啟動要求最小化（2／6／7）才照辦；否則用存下的 showCmd，但存下的是最小化時改回一般／最大化
  （依 WPF_RESTORETOMAXIMIZED）。
- A（0x4ec0dd，WM_MDICREATE 前）：以視窗標題為鍵讀 `[ChildWindows] 標題.x／標題.y`（CWinApp::GetProfileInt，
  與 FrameWindowPos 同一個 ld95.ini），有就套用；再把位置限制在 MDI 工作區內（尺寸不變，太大則靠左上）。
- D（0x4ebb80，WM_MDIDESTROY 前）：記下要關閉的子視窗位置（CWinApp::WriteProfileInt）。
- B（0x48a2e0，結束時寫 FrameWindowPos 之前）：記下所有開著的子視窗位置。
最小化／最大化中的子視窗不記。沒有標題的子視窗只做範圍限制。

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
IAT = {'SendMessageA': 0x525620, 'GetClientRect': 0x525618, 'GetWindowRect': 0x52561c, 'MapWindowPoints': 0x525608,
       'GetWindowTextA': 0x525484, 'GetWindow': 0x5254e0, 'IsIconic': 0x5254d8, 'IsZoomed': 0x525564, 'wsprintfA': 0x5255ac}
AFX_MODULE_STATE = 0x4e0fdb          # call → eax；[eax+4] = 目前的 CWinApp
GET_PROFILE_INT = 0x4f2e8f           # CWinApp::GetProfileInt(section, entry, default)   thiscall
WRITE_PROFILE_INT = 0x4f2ef8         # CWinApp::WriteProfileInt(section, entry, value)  thiscall
WRITE_PROFILE_STRING = 0x4f2f7f      # CWinApp::WriteProfileString（結束時寫 FrameWindowPos）
FRAME_MDICLIENT = 0xd4               # CMDIFrameWnd::m_hWndMDIClient
APP_MAINWND = 0x20                   # CWinThread::m_pMainWnd

SITES = {   # va: (原位元組, 種類)
    0x4ec0dd: (bytes.fromhex('ffb6d4000000ffd3'), 'A'),       # push [esi+0xd4] ; call ebx(SendMessageA)  — WM_MDICREATE
    0x4ebb80: (bytes.fromhex('ff1520565200'), 'D'),           # call [SendMessageA]                      — WM_MDIDESTROY
    0x48a2e0: (bytes.fromhex('e89a8c0600'), 'B'),             # call 0x4f2f7f（WriteProfileString FrameWindowPos）
    0x48b54e: (bytes.fromhex('83f801740489442424'), 'C'),  # cmp eax,1 ; je +4 ; mov [esp+0x24],eax
}

ASM = r"""
; ===== 共用：save_one(child=[esp+4], client=[esp+8])  stdcall，保留 ebx/esi/edi/ebp =====
save_one:
    push ebp
    push esi
    push edi
    push ebx
    sub esp, 0x90                       ; [esp]=title(0x40) [esp+0x40]=key(0x40) [esp+0x80]=rect
    mov esi, [esp+0x90+0x14]            ; child
    mov edi, [esp+0x90+0x18]            ; client
    push esi
    call dword ptr [{IsIconic}]
    test eax, eax
    jnz so_done
    push esi
    call dword ptr [{IsZoomed}]
    test eax, eax
    jnz so_done
    push 0x40
    lea eax, [esp+4]
    push eax
    push esi
    call dword ptr [{GetWindowTextA}]
    test eax, eax
    jz so_done
    lea eax, [esp+0x80]
    push eax
    push esi
    call dword ptr [{GetWindowRect}]
    push 2
    lea eax, [esp+0x84]
    push eax
    push edi
    push 0
    call dword ptr [{MapWindowPoints}]
    mov ebx, 0
so_axis:
    mov eax, esp                        ; key = title + (.x/.y)
    push eax
    mov eax, fmt_x
    test ebx, ebx
    jz so_fx
    mov eax, fmt_y
so_fx:
    push eax
    lea eax, [esp+0x48]
    push eax
    call dword ptr [{wsprintfA}]
    add esp, 0xc
    push dword ptr [esp+0x80+ebx*4]     ; rect.left / rect.top
    lea eax, [esp+0x44]
    push eax
    mov edx, section
    push edx
    mov eax, {AFX}
    call eax
    mov ecx, [eax+4]
    mov eax, {WPI}
    call eax
    inc ebx
    cmp ebx, 2
    jl so_axis
so_done:
    add esp, 0x90
    pop ebx
    pop edi
    pop esi
    pop ebp
    ret 8

; ===== A：WM_MDICREATE 前（由 call 進入；堆疊 [ret][0x220][0][&mcs]；esi=CMDIFrameWnd、ebx=SendMessageA） =====
hook_create:
    pushad
    mov ebp, [esp+0x2c]                 ; &MDICREATESTRUCT
    mov ebx, [esi+{MDICLIENT}]          ; MDI client
    sub esp, 0x60                       ; [esp]=key(0x40) [esp+0x40]=client rect
    mov eax, [ebp+4]                    ; szTitle
    test eax, eax
    jz hc_clamp
    cmp byte ptr [eax], 0
    jz hc_clamp
    xor edi, edi                        ; 0=x 1=y；讀到的值暫存在 [esp+0x50+edi*4]
hc_axis:
    push dword ptr [ebp+4]
    mov eax, fmt_x
    test edi, edi
    jz hc_fx
    mov eax, fmt_y
hc_fx:
    push eax
    lea eax, [esp+8]
    push eax
    call dword ptr [{wsprintfA}]
    add esp, 0xc
    push 0x80000000
    lea eax, [esp+4]
    push eax
    mov edx, section
    push edx
    mov eax, {AFX}
    call eax
    mov ecx, [eax+4]
    mov eax, {GPI}
    call eax
    cmp eax, 0x80000000
    je hc_clamp
    mov [esp+0x50+edi*4], eax
    inc edi
    cmp edi, 2
    jl hc_axis
    mov eax, [esp+0x50]
    mov [ebp+0xc], eax
    mov eax, [esp+0x54]
    mov [ebp+0x10], eax
hc_clamp:
    lea eax, [esp+0x40]
    push eax
    push ebx
    call dword ptr [{GetClientRect}]
    test eax, eax
    jz hc_done
    xor edi, edi                        ; 0=x 1=y
hc_c:
    mov eax, [ebp+0xc+edi*4]            ; x / y
    cmp eax, 0x80000000
    je hc_done
    mov ecx, [ebp+0x14+edi*4]           ; cx / cy
    cmp ecx, 0x80000000
    je hc_done
    mov edx, [esp+0x48+edi*4]           ; client right / bottom
    sub edx, ecx                        ; 最大位置
    cmp eax, edx
    jle hc_c1
    mov eax, edx
hc_c1:
    test eax, eax
    jge hc_c2
    xor eax, eax
hc_c2:
    mov [ebp+0xc+edi*4], eax
    inc edi
    cmp edi, 2
    jl hc_c
hc_done:
    add esp, 0x60
    popad
    pop eax                             ; 回到呼叫點的位址
    push dword ptr [esi+{MDICLIENT}]
    push eax
    jmp ebx                             ; SendMessageA(client, WM_MDICREATE, 0, &mcs)

; ===== D：WM_MDIDESTROY 前（取代 call [SendMessageA]；堆疊 [ret][client][0x221][child][0]） =====
hook_destroy:
    push dword ptr [esp+4]              ; client
    push dword ptr [esp+0x10]           ; child（[esp+0xc] 再加剛 push 的 4）
    call save_one
    jmp dword ptr [{SendMessageA}]

; ===== B：結束時寫 FrameWindowPos 之前（取代 call 0x4f2f7f；ecx=app） =====
hook_exit:
    pushad
    mov eax, [ecx+{MAINWND}]
    test eax, eax
    jz he_done
    mov ebx, [eax+{MDICLIENT}]
    test ebx, ebx
    jz he_done
    push 5                              ; GW_CHILD
    push ebx
    call dword ptr [{GetWindow}]
he_loop:
    test eax, eax
    jz he_done
    mov esi, eax
    push ebx
    push esi
    call save_one
    push 2                              ; GW_HWNDNEXT
    push esi
    call dword ptr [{GetWindow}]
    jmp he_loop
he_done:
    popad
    mov eax, {WPS}
    jmp eax

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

section: .ascii "ChildWindows"
    .byte 0
fmt_x: .ascii "%s.x"
    .byte 0
fmt_y: .ascii "%s.y"
    .byte 0
"""

ENTRIES = {'A': 'hook_create', 'D': 'hook_destroy', 'B': 'hook_exit', 'C': 'hook_show'}
BASE0, BASE1 = 0x10000000, 0x20000000
STUB_JSON = HERE / 'layout_stub.json'


def _asm_text():
    return ASM.format(IsIconic=hex(IAT['IsIconic']), IsZoomed=hex(IAT['IsZoomed']), GetWindowTextA=hex(IAT['GetWindowTextA']),
                      GetWindowRect=hex(IAT['GetWindowRect']), MapWindowPoints=hex(IAT['MapWindowPoints']),
                      wsprintfA=hex(IAT['wsprintfA']), GetClientRect=hex(IAT['GetClientRect']), GetWindow=hex(IAT['GetWindow']),
                      SendMessageA=hex(IAT['SendMessageA']), AFX=hex(AFX_MODULE_STATE), WPI=hex(WRITE_PROFILE_INT),
                      GPI=hex(GET_PROFILE_INT), WPS=hex(WRITE_PROFILE_STRING), MDICLIENT=hex(FRAME_MDICLIENT),
                      MAINWND=hex(APP_MAINWND))


def regen():
    """以 keystone 在兩個基底組譯，比對差異得到絕對位址重定位表（只允許 +Δ 的 4 位元組欄位）。"""
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    src = '\n'.join(l.split(';')[0].rstrip() for l in _asm_text().splitlines())
    out = []
    for base in (BASE0, BASE1):
        enc, _ = ks.asm(src, base)
        out.append(bytes(enc))
    a, b = out
    assert len(a) == len(b)
    delta = BASE1 - BASE0
    relocs, i = [], 0
    while i < len(a):
        if a[i] != b[i]:
            j = i - (i % 1)
            # 找出包含差異的 4 位元組欄位：向前試 0..3
            for k in range(0, 4):
                p = i - k
                if p >= 0 and (struct.unpack_from('<I', b, p)[0] - struct.unpack_from('<I', a, p)[0]) & 0xffffffff == delta:
                    relocs.append(p); i = p + 4; break
            else:
                raise ValueError(f'非絕對位址差異 @ {i}')
            continue
        i += 1
    # 符號位址：逐一組譯「到該標籤為止」取長度
    syms = {}
    for name in list(ENTRIES.values()) + ['save_one', 'section', 'fmt_x', 'fmt_y']:
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
        if out[o:o + len(old)] != old:
            raise ValueError(f'{hex(va)} 內容與預期不符')
        tgt = sym[ENTRIES[kind]]
        new = b'\xe8' + struct.pack('<i', tgt - (va + 5))
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
