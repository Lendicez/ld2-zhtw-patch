r"""存檔照護（1.0.5）：存檔前自動備份舊檔、自動存檔。

擁有者決定（2026-11-19）：
- 每次存檔前，把那一格的舊檔備份到存檔資料夾的 `_backup`（例 `USR\_backup\LUNAS003-1.LDP`，-1 最新），每格留 5 份。
- 自動存檔：固定用第 015 格（清單 16 格的最後一格）；時機＝「回到城鎮時」與「進入迷宮前」；
  015 是空的、或是上次自動存檔留下的才寫，玩家自己存在 015 的絕不覆蓋（狀態列提示）。
  安裝程式勾選、預設開（ld95.ini `[zhTW] AutoSave`，沒有這個鍵時視為開）。

量測（lab48 除錯版，jobs 1476–1483）：
- 存檔＝CMainFrame 0xE103 處理 0x488750 → 存檔對話框 → game(app+0xb0)->SaveGame(LPCTSTR 路徑) 0x4855b0（thiscall，ret 4）；
  SaveGame 經 CFile::Open（0x4e861f 的 call [CreateFileA]，GENERIC_WRITE、CREATE_ALWAYS）寫 `<遊戲>\USR\LUNASnnn.LDP`，
  結束時以 CWnd::MessageBox（0x4e3985）顯示「存檔完成／失敗」（0x485d19）、磁碟不足（0x48561b）。
- 可存檔條件（0x482d40）：主視窗模式 [frame+0x108] == 3（城鎮）。
- 主視窗模式切換 SetMode 0x489120（thiscall，ret 4；-1＝回上一個）：讀檔 0→3、新遊戲 0→2→3、進迷宮 3→4（0x489624）、
  前往其他城鎮 3→0→6→(10)→6→9…（旅行中）、城鎮戰鬥 3→5。
- 讀檔 LoadGame 0x4851c0；迷宮中不能讀檔（選單停用）。
- 存檔／讀檔清單只有 16 格（0x499bc8 `cmp eax,0x10`）。

修法（小段程式附加在 .ld2i 尾，0x1000 程式＋0x1000 資料）：
- B（0x4e861f）：CFile::Open 以寫入＋CREATE_ALWAYS 開 *.LDP 且檔案已存在 → 先輪替備份（-4→-5 … -1→-2，再複製現檔為 -1）。
  CopyFileA／MoveFileExA／CreateDirectoryA／IsDBCSLeadByte 以 GetProcAddress 取得（原 EXE 沒匯入）；路徑切割處理雙位元組字元。
- M（0x489120）：SetMode 包裝。模式進入 4（迷宮）或 6（旅行）記「離開城鎮」；進入 2（新遊戲）清除；
  模式變成 3 且之前離開過城鎮 → 用 SetTimer（主視窗、TimerProc）稍後自動存檔（等抵達訊息等對話框關掉：主視窗可用才做）。
- L（0x4851c0）：LoadGame 入口清除「離開城鎮」並取消待做的自動存檔（避免把剛讀的檔存進 015）。
- P（0x489586）：前往迷宮確認後、離開城鎮前（取代 call AfxGetModuleState）先自動存檔。
- X（0x485d19、0x48561b）：自動存檔時不顯示「存檔完成」等對話框（改在狀態列顯示）。
- 自動存檔：模式 3、遊戲物件存在、AutoSave≠0；路徑＝EXE 所在資料夾＋`USR\LUNAS015.LDP`；
  015 已存在時，大小與修改時間（低 31 位元）要等於 ld95.ini `[zhTW] AutoSaveSize／AutoSaveTime`（上次自動存檔記下的）才寫。

小段程式以 keystone 組譯；倉庫內存 `savecare_stub.json`（BASE0 的位元組與絕對位址重定位表）。`python savecare_patch.py --regen`。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))

IAT = {'GetFileAttributesA': 0x52515c, 'CreateFileA': 0x525260, 'FindFirstFileA': 0x525270, 'FindClose': 0x525274,
       'GetModuleFileNameA': 0x525264, 'GetModuleHandleA': 0x525300, 'GetProcAddress': 0x5252e4, 'lstrlenA': 0x525344,
       'lstrcpyA': 0x52532c, 'wsprintfA': 0x5255ac, 'SetTimer': 0x525560, 'KillTimer': 0x52555c,
       'IsWindowEnabled': 0x5255d4, 'SendMessageA': 0x525620, 'GetParent': 0x5255a8}
AFX_MODULE_STATE = 0x4e0fdb
APP_MAINWND, APP_GAME = 0x20, 0xb0
FRAME_MDICLIENT, FRAME_MODE = 0xd4, 0x108
GET_PROFILE_INT, WRITE_PROFILE_INT = 0x4f2e8f, 0x4f2ef8
SAVE_GAME, MSGBOX = 0x4855b0, 0x4e3985
SETMODE_BODY, LOADGAME_BODY = 0x489125, 0x4851c5
KEEP = 5
AUTO_SLOT = 15
TIMER_ID = 0x5A15

SITES = {   # va: (原位元組, 進入點, 'call'|'jmp')
    0x4e861f: (bytes.fromhex('ff1560525200'), 'hook_cf', 'call'),
    0x489120: (bytes.fromhex('5356578bf1'), 'sm_wrap', 'jmp'),
    0x4851c0: (bytes.fromhex('558bec6aff'), 'lg_wrap', 'jmp'),
    0x489586: (bytes.fromhex('e8507a0500'), 'hook_predungeon', 'call'),
    0x485d19: (bytes.fromhex('e867dc0500'), 'hook_msg', 'call'),
    0x48561b: (bytes.fromhex('e865e30500'), 'hook_msg', 'call'),
}

CODE_MAX = 0xC00          # 程式＋字串在前 0x1000；資料（全 0）在後 0x1000
STR_OFF = 0xA00
DATA_OFF = 0x1000
GROW = 0x2000


def _s(text: str) -> bytes:
    return text.encode('cp950') + b'\0'


STRINGS = {
    'S_SECTION': _s('zhTW'), 'S_KEY_AUTO': _s('AutoSave'), 'S_KEY_SIZE': _s('AutoSaveSize'), 'S_KEY_TIME': _s('AutoSaveTime'),
    'S_AUTONAME': _s('USR\\LUNAS%03d.LDP' % AUTO_SLOT), 'S_FMT_BKDIR': _s('%s_backup'), 'S_FMT_BK': _s('%s\\%s-%d.LDP'),
    'S_KERNEL32': _s('KERNEL32.DLL'), 'S_COPY': _s('CopyFileA'), 'S_MOVE': _s('MoveFileExA'),
    'S_MKDIR': _s('CreateDirectoryA'), 'S_LEAD': _s('IsDBCSLeadByte'),
    'S_MSG_OK': _s('已自動存檔（第 %03d 格）。' % AUTO_SLOT),
    'S_MSG_MINE': _s('第 %03d 格是您自己的存檔，未自動存檔。' % AUTO_SLOT),
    'S_MSG_FAIL': _s('自動存檔失敗。'),
}

DATA = {   # 名稱: (偏移, 大小)
    'V_AWAY': (0x00, 4), 'V_BUSY': (0x04, 4), 'FP_COPY': (0x10, 4), 'FP_MOVE': (0x14, 4), 'FP_MKDIR': (0x18, 4),
    'FP_LEAD': (0x1c, 4), 'WFD': (0x40, 0x140), 'PATHBUF': (0x200, 0x208), 'DIRBUF': (0x410, 0x208),
    'BASEBUF': (0x620, 0x108), 'BKDIR': (0x730, 0x208), 'SRCBUF': (0x940, 0x208), 'DSTBUF': (0xb50, 0x208),
}

ASM = r"""
; ===== B：CFile::Open 的 call [CreateFileA]（[ret][name][access][share][sec][disp]…） =====
hook_cf:
    test dword ptr [esp+8], 0x40000000
    jz cf_go
    cmp dword ptr [esp+0x14], 2
    jne cf_go
    pushad
    mov esi, [esp+0x24]
    push esi
    call dword ptr [{lstrlenA}]
    cmp eax, 5
    jb cf_done
    mov ecx, [esi+eax-4]
    or ecx, 0x20202000
    cmp ecx, 0x70646c2e
    jne cf_done
    push esi
    call dword ptr [{GetFileAttributesA}]
    cmp eax, -1
    je cf_done
    test al, 0x10
    jnz cf_done
    push esi
    call backup_rotate
cf_done:
    popad
cf_go:
    jmp dword ptr [{CreateFileA}]

; ===== 輪替備份（stdcall 1：存檔完整路徑） =====
backup_rotate:
    pushad
    call resolve_k32
    test eax, eax
    jz br_out
    mov esi, [esp+0x24]
    push esi
    push {DIRBUF}
    call dword ptr [{lstrcpyA}]
    push {DIRBUF}
    call dir_end
    mov edi, eax
    push edi
    push {BASEBUF}
    call dword ptr [{lstrcpyA}]
    mov byte ptr [edi], 0
    push {BASEBUF}
    call dword ptr [{lstrlenA}]
    cmp eax, 4
    jbe br_out
    mov byte ptr [eax+{BASEBUF}-4], 0
    push {DIRBUF}
    push {S_FMT_BKDIR}
    push {BKDIR}
    call dword ptr [{wsprintfA}]
    add esp, 12
    push 0
    push {BKDIR}
    call dword ptr [{FP_MKDIR}]
    mov ebx, {KEEP}
br_rot:
    cmp ebx, 1
    jle br_copy
    push ebx
    push {BASEBUF}
    push {BKDIR}
    push {S_FMT_BK}
    push {DSTBUF}
    call dword ptr [{wsprintfA}]
    add esp, 20
    lea eax, [ebx-1]
    push eax
    push {BASEBUF}
    push {BKDIR}
    push {S_FMT_BK}
    push {SRCBUF}
    call dword ptr [{wsprintfA}]
    add esp, 20
    push 1
    push {DSTBUF}
    push {SRCBUF}
    call dword ptr [{FP_MOVE}]
    dec ebx
    jmp br_rot
br_copy:
    push 1
    push {BASEBUF}
    push {BKDIR}
    push {S_FMT_BK}
    push {DSTBUF}
    call dword ptr [{wsprintfA}]
    add esp, 20
    push 0
    push {DSTBUF}
    push esi
    call dword ptr [{FP_COPY}]
br_out:
    popad
    ret 4

; ===== 取 kernel32 的 CopyFileA／MoveFileExA／CreateDirectoryA／IsDBCSLeadByte；eax=0 失敗 =====
resolve_k32:
    push ebx
    cmp dword ptr [{FP_COPY}], 0
    jne rk_ok
    push {S_KERNEL32}
    call dword ptr [{GetModuleHandleA}]
    test eax, eax
    jz rk_fail
    mov ebx, eax
    push {S_MOVE}
    push ebx
    call dword ptr [{GetProcAddress}]
    test eax, eax
    jz rk_fail
    mov [{FP_MOVE}], eax
    push {S_MKDIR}
    push ebx
    call dword ptr [{GetProcAddress}]
    test eax, eax
    jz rk_fail
    mov [{FP_MKDIR}], eax
    push {S_LEAD}
    push ebx
    call dword ptr [{GetProcAddress}]
    test eax, eax
    jz rk_fail
    mov [{FP_LEAD}], eax
    push {S_COPY}
    push ebx
    call dword ptr [{GetProcAddress}]
    test eax, eax
    jz rk_fail
    mov [{FP_COPY}], eax
rk_ok:
    mov eax, 1
    pop ebx
    ret
rk_fail:
    xor eax, eax
    pop ebx
    ret

; ===== 傳回路徑中最後一個「\」之後的位置（stdcall 1；處理雙位元組字元） =====
dir_end:
    push esi
    push ebx
    call resolve_k32
    mov esi, [esp+0xc]
    mov ebx, esi
de_loop:
    movzx eax, byte ptr [esi]
    test eax, eax
    jz de_done
    cmp eax, 0x5c
    jne de_lead
    lea ebx, [esi+1]
    inc esi
    jmp de_loop
de_lead:
    cmp eax, 0x80
    jb de_one
    cmp dword ptr [{FP_LEAD}], 0
    je de_one
    push eax
    call dword ptr [{FP_LEAD}]
    test eax, eax
    jz de_one
    cmp byte ptr [esi+1], 0
    je de_one
    inc esi
de_one:
    inc esi
    jmp de_loop
de_done:
    mov eax, ebx
    pop ebx
    pop esi
    ret 4

; ===== M：SetMode 包裝（[ret][mode]） =====
sm_wrap:
    push dword ptr [ecx+{MODE}]
    push ecx
    push dword ptr [esp+0xc]
    call sm_orig
    pop ecx
    pop edx
    push eax
    mov eax, [ecx+{MODE}]
    cmp eax, 4
    je sm_away
    cmp eax, 6
    je sm_away
    cmp eax, 2
    je sm_clear
    cmp eax, 3
    jne sm_ret
    cmp edx, 3
    je sm_ret
    cmp dword ptr [{V_AWAY}], 0
    je sm_ret
    mov dword ptr [{V_AWAY}], 0
    call get_frame_hwnd
    test eax, eax
    jz sm_ret
    mov edx, timer_proc
    push edx
    push 400
    push {TIMER_ID}
    push eax
    call dword ptr [{SetTimer}]
    jmp sm_ret
sm_away:
    mov dword ptr [{V_AWAY}], 1
    jmp sm_ret
sm_clear:
    mov dword ptr [{V_AWAY}], 0
sm_ret:
    pop eax
    ret 4
sm_orig:
    push ebx
    push esi
    push edi
    mov esi, ecx
    push {SETMODE_BODY}
    ret

; ===== L：LoadGame 入口 =====
lg_wrap:
    pushad
    mov dword ptr [{V_AWAY}], 0
    call get_frame_hwnd
    test eax, eax
    jz lg_go
    push {TIMER_ID}
    push eax
    call dword ptr [{KillTimer}]
lg_go:
    popad
    push ebp
    mov ebp, esp
    push -1
    push {LOADGAME_BODY}
    ret

; ===== 主視窗 hwnd（MDI 工作區的父視窗）；eax=0 表示沒有 =====
get_frame_hwnd:
    mov eax, {AFX}
    call eax
    mov eax, [eax+4]
    mov eax, [eax+{MAINWND}]
    test eax, eax
    jz gf_ret
    mov eax, [eax+{MDICLIENT}]
    test eax, eax
    jz gf_ret
    push eax
    call dword ptr [{GetParent}]
gf_ret:
    ret

; ===== TimerProc(hwnd, msg, id, time)：主視窗可用（沒有對話框）時才自動存檔 =====
timer_proc:
    push dword ptr [esp+4]
    call dword ptr [{IsWindowEnabled}]
    test eax, eax
    jz tp_ret
    push {TIMER_ID}
    push dword ptr [esp+8]
    call dword ptr [{KillTimer}]
    call autosave
tp_ret:
    ret 0x10

; ===== P：前往迷宮確認後（取代 call AfxGetModuleState） =====
hook_predungeon:
    call autosave
    mov eax, {AFX}
    jmp eax

; ===== X：自動存檔時不顯示 SaveGame 的對話框（取代 call CWnd::MessageBox，thiscall ret 0xc） =====
hook_msg:
    cmp dword ptr [{V_BUSY}], 0
    jne hm_skip
    mov eax, {MSGBOX}
    jmp eax
hm_skip:
    mov eax, 1
    ret 0xc

; ===== 狀態列訊息（stdcall 1：文字） =====
status_text:
    call get_frame_hwnd
    test eax, eax
    jz st_ret
    push dword ptr [esp+4]
    push 0
    push 0x362
    push eax
    call dword ptr [{SendMessageA}]
st_ret:
    ret 4

; ===== 自動存檔（保留全部暫存器） =====
autosave:
    pushad
    cmp dword ptr [{V_BUSY}], 0
    jne as_out
    mov eax, {AFX}
    call eax
    mov esi, [eax+4]
    cmp dword ptr [esi+{GAME}], 0
    je as_out
    mov eax, [esi+{MAINWND}]
    test eax, eax
    jz as_out
    cmp dword ptr [eax+{MODE}], 3
    jne as_out
    push 1
    push {S_KEY_AUTO}
    push {S_SECTION}
    mov ecx, esi
    mov eax, {GETINT}
    call eax
    test eax, eax
    jz as_out
    push 0x104
    push {PATHBUF}
    push 0
    call dword ptr [{GetModuleFileNameA}]
    test eax, eax
    jz as_out
    push {PATHBUF}
    call dir_end
    push {S_AUTONAME}
    push eax
    call dword ptr [{lstrcpyA}]
    push {WFD}
    push {PATHBUF}
    call dword ptr [{FindFirstFileA}]
    cmp eax, -1
    je as_save
    push eax
    call dword ptr [{FindClose}]
    push 0
    push {S_KEY_SIZE}
    push {S_SECTION}
    mov ecx, esi
    mov eax, {GETINT}
    call eax
    cmp eax, [{WFD}+0x20]
    jne as_mine
    push 0
    push {S_KEY_TIME}
    push {S_SECTION}
    mov ecx, esi
    mov eax, {GETINT}
    call eax
    mov edx, [{WFD}+0x14]
    and edx, 0x7fffffff
    cmp eax, edx
    jne as_mine
as_save:
    mov dword ptr [{V_BUSY}], 1
    mov ecx, [esi+{GAME}]
    push {PATHBUF}
    mov eax, {SAVEGAME}
    call eax
    mov dword ptr [{V_BUSY}], 0
    cmp eax, 1
    jne as_fail
    push {WFD}
    push {PATHBUF}
    call dword ptr [{FindFirstFileA}]
    cmp eax, -1
    je as_fail
    push eax
    call dword ptr [{FindClose}]
    push dword ptr [{WFD}+0x20]
    push {S_KEY_SIZE}
    push {S_SECTION}
    mov ecx, esi
    mov eax, {WRITEINT}
    call eax
    mov edx, [{WFD}+0x14]
    and edx, 0x7fffffff
    push edx
    push {S_KEY_TIME}
    push {S_SECTION}
    mov ecx, esi
    mov eax, {WRITEINT}
    call eax
    push {S_MSG_OK}
    jmp as_msg
as_mine:
    push {S_MSG_MINE}
    jmp as_msg
as_fail:
    push {S_MSG_FAIL}
as_msg:
    call status_text
as_out:
    popad
    ret
"""

ENTRIES = sorted({e for _, e, _ in SITES.values()})
BASE0, BASE1 = 0x10000000, 0x20000000
STUB_JSON = HERE / 'savecare_stub.json'


def _layout_strings(base: int):
    addr, blob, off = {}, bytearray(), 0
    for k, v in STRINGS.items():
        addr[k] = base + STR_OFF + off; blob += v; off += len(v)
    return addr, bytes(blob)


def _asm_text(base: int) -> str:
    sa, _ = _layout_strings(base)
    m = {k: hex(v) for k, v in IAT.items()}
    m.update({k: hex(v) for k, v in sa.items()})
    m.update({k: hex(base + DATA_OFF + o) for k, (o, _) in DATA.items()})
    m.update(AFX=hex(AFX_MODULE_STATE), MAINWND=hex(APP_MAINWND), GAME=hex(APP_GAME), MDICLIENT=hex(FRAME_MDICLIENT),
             MODE=hex(FRAME_MODE), GETINT=hex(GET_PROFILE_INT), WRITEINT=hex(WRITE_PROFILE_INT), SAVEGAME=hex(SAVE_GAME),
             MSGBOX=hex(MSGBOX), SETMODE_BODY=hex(SETMODE_BODY), LOADGAME_BODY=hex(LOADGAME_BODY), KEEP=str(KEEP),
             TIMER_ID=hex(TIMER_ID))
    src = ASM.format(**m)
    return '\n'.join(l.split(';')[0].rstrip() for l in src.splitlines())


def regen():
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    a = bytes(ks.asm(_asm_text(BASE0), BASE0)[0])
    b = bytes(ks.asm(_asm_text(BASE1), BASE1)[0])
    assert len(a) == len(b) and len(a) <= STR_OFF, len(a)
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
    for name in ENTRIES:
        enc, _ = ks.asm(_asm_text(BASE0) + f'\n__probe: mov eax, {name}\n', BASE0)
        syms[name] = struct.unpack_from('<I', bytes(enc), len(enc) - 4)[0] - BASE0
    _, blob = _layout_strings(BASE0)
    assert STR_OFF + len(blob) <= CODE_MAX
    doc = {'base0': BASE0, 'hex': a.hex(), 'relocs': relocs, 'symbols': syms, 'strings_hex': blob.hex()}
    STUB_JSON.write_text(json.dumps(doc, indent=1) + '\n', 'utf-8')
    return doc


def load_stub(base: int):
    """傳回整段 GROW 位元組（程式＋字串＋全 0 資料區）與進入點位址。"""
    doc = json.loads(STUB_JSON.read_text('utf-8'))
    code = bytearray(bytes.fromhex(doc['hex']))
    for p in doc['relocs']:
        v = struct.unpack_from('<I', code, p)[0]
        struct.pack_into('<I', code, p, (v - doc['base0'] + base) & 0xffffffff)
    page = bytearray(GROW)
    page[:len(code)] = code
    page[len(code):STR_OFF] = b'\xcc' * (STR_OFF - len(code))
    blob = bytes.fromhex(doc['strings_hex'])
    page[STR_OFF:STR_OFF + len(blob)] = blob
    return bytes(page), {k: base + v for k, v in doc['symbols'].items()}


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
    page, sym = load_stub(stub_va)
    out = bytearray(exe)
    for va, (old, entry, kind) in SITES.items():
        o = _va2off(exe, va)
        if bytes(out[o:o + len(old)]) != old:
            raise ValueError(f'{hex(va)} 內容與預期不符')
        new = (b'\xe8' if kind == 'call' else b'\xe9') + struct.pack('<i', sym[entry] - (va + 5))
        out[o:o + len(old)] = new + b'\x90' * (len(old) - 5)
    out += page
    hdr = last['header']
    struct.pack_into('<I', out, hdr + 8, last['rs'] + GROW)
    struct.pack_into('<I', out, hdr + 16, last['rs'] + GROW)
    salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
    struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + GROW + salign - 1) // salign * salign)
    return bytes(out), {'stub_va': hex(stub_va), 'sites': [hex(v) for v in SITES], 'symbols': {k: hex(v) for k, v in sym.items()}}


if __name__ == '__main__':
    if '--regen' in sys.argv:
        d = regen(); print(len(d['hex']) // 2, 'bytes', len(d['relocs']), 'relocs', d['symbols'])
