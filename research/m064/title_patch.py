r"""m064 lab：視窗標題（訊息框說話者名字等）CP932 → Big5。

戰鬥／事件訊息框（`Afx:…:b:` 彈出視窗）的標題是說話者名字（怪物、NPC，來自世界資料，CP932），
以 ANSI 標題顯示 → ACP 950 下亂碼（例：「□□?□□?」）。修補 MFC 的三個 USER32 呼叫點：

    0x4e3507  call [CreateWindowExA]   （CWnd::CreateEx；標題 = [esp+0xc]，dwStyle = [esp+0x10]）
    0x4ea7b5  call [SetWindowTextA]    （CWnd::SetWindowText；文字 = [esp+8]）
    0x4f65fe  call [SetWindowTextA]    （AfxSetWindowText）

各改成 `call 前置; nop`。前置：子視窗（WS_CHILD，含編輯框、控制項）一律原樣（避免改到之後會被讀回
寫入存檔的文字）；頂層／彈出視窗才交給 savelist 的轉換 stub（以空白切詞 → catalog 或照字形 → cp950），
最後 `jmp [IAT]`。程式碼附加在 .ld2i 檔尾（EXECUTE）。只寫 lab 複本。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE
import savelist_patch as S

WS_CHILD = 0x40000000
GWL_STYLE = -16
SITES = (  # (位址, API, 字串參數位移, 判斷子視窗的方式)
    (0x4e3507, 'CreateWindowExA', 0x0C, 'style_arg'),
    (0x4ea7b5, 'SetWindowTextA', 0x08, 'hwnd'),
    (0x4f65fe, 'SetWindowTextA', 0x08, 'hwnd'),
)


def build_front(origin, conv, iat, mode, getwl):
    a = Asm(origin)
    if mode == 'style_arg':
        a.emit([0xF7, 0x44, 0x24, 0x10], a.imm32(WS_CHILD))       # test dword [esp+0x10],WS_CHILD
    else:
        a.emit([0x6A, 0xF0, 0xFF, 0x74, 0x24, 0x08])               # push -16; push [esp+8]（hwnd）
        a.call_ind(getwl)
        a.emit([0xA9], a.imm32(WS_CHILD))                          # test eax,WS_CHILD
    a.jcc8(0x75, 'direct')
    a.emit([0xE9]); a.emit(struct.pack('<i', conv - (a.here() + 4)))
    a.label('direct'); a.emit([0xFF, 0x25], a.imm32(iat))
    return a.finish()


def patch(exe: bytes):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    wctmb = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'WideCharToMultiByte')
    getwl = iat_slot(exe, secs, pe, 'USER32.dll', 'GetWindowLongA')
    base = BASE + i['va'] + i['rsz']
    blob, cur, info = bytearray(), base, []
    # 共用資料區（ctx／wbuf／sbuf）放最前面
    data = cur; cur += 0x340
    sites = []
    for site, api, arg, mode in SITES:
        iat = iat_slot(exe, secs, pe, 'USER32.dll', api)
        so = va2off(secs, site)
        if exe[so:so + 6] != b'\xff\x15' + struct.pack('<I', iat):
            raise ValueError(f'{site:#x} is not call [{api}]')
        conv_va = cur
        conv, _ = S.build_stub(conv_va, data, mbtwc, wctmb, arg_esp=arg, target_ind=iat)
        cur += (len(conv) + 0xf) & ~0xf
        front_va = cur
        front = build_front(front_va, conv_va, iat, mode, getwl)
        cur += (len(front) + 0xf) & ~0xf
        sites.append((so, site, front_va, conv_va, conv, front))
        info.append({'site': hex(site), 'api': api, 'front': hex(front_va)})
    blob = bytearray(cur - base)
    for so, site, fva, cva, conv, front in sites:
        blob[cva - base:cva - base + len(conv)] = conv
        blob[fva - base:fva - base + len(front)] = front
    grow = (len(blob) + 0xfff) & ~0xfff
    out = bytearray(exe) + blob + b'\0' * (grow - len(blob))
    for so, site, fva, *_ in sites:
        out[so] = 0xE8
        struct.pack_into('<i', out, so + 1, fva - (site + 5))
        out[so + 5] = 0x90
    struct.pack_into('<I', out, i['hdr'] + 8, i['rsz'] + grow)
    struct.pack_into('<I', out, i['hdr'] + 16, i['rsz'] + grow)
    ch = struct.unpack_from('<I', out, i['hdr'] + 36)[0]
    struct.pack_into('<I', out, i['hdr'] + 36, ch | S.IMAGE_SCN_EXEC)
    opt = pe + 24
    salign = struct.unpack_from('<I', out, opt + 32)[0]
    struct.pack_into('<I', out, opt + 56, (i['va'] + i['rsz'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'sites': info, 'data_va': hex(data)}
