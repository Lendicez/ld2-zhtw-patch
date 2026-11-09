r"""m064 lab：視窗標題（訊息框說話者名字等）CP932 → Big5。

戰鬥／事件訊息框（`Afx:…:b:` 彈出視窗）的標題是說話者名字（怪物、NPC，來自世界資料，CP932），
以 ANSI 標題顯示 → ACP 950 下亂碼（例：「□□?□□?」）。修補 MFC 的三個 USER32 呼叫點：

    0x4e3507  call [CreateWindowExA]   （CWnd::CreateEx；標題 = [esp+0xc]，dwStyle = [esp+0x10]）
    0x4ea7b5  call [SetWindowTextA]    （CWnd::SetWindowText；文字 = [esp+8]）
    0x4f65fe  call [SetWindowTextA]    （AfxSetWindowText）

各改成 `call 轉換; nop`，另加對話框 SetDlgItemTextA 唯一呼叫點（文字 = [esp+0xc]）。轉換＝savelist 的
stub（含 0x81–0x9F 才動；以空白切詞 → 稱號對照 → catalog → 名字音節表 → 假名音譯 → cp950），最後 `jmp [IAT]`。
1.0.1 起子視窗（編輯框、靜態文字）也轉換：委託人等 NPC 名、創角預設名／稱號原本是 CP932 → CP950 下空白或「?」
（KNOWN-ISSUES #3 #4 #6）。代價：玩家沿用預設名／稱號時，存檔內為 Big5（與自行輸入中文名相同）。
程式碼附加在 .ld2i 檔尾（EXECUTE）。只寫 lab 複本。
"""
import struct
from tab_title_patch import Asm, sections, va2off, iat_slot, BASE
import savelist_patch as S

SITES = (  # (位址；None＝依 IAT 搜唯一呼叫點, API, 字串參數位移)
    (0x4e3507, 'CreateWindowExA', 0x0C),
    (0x4ea7b5, 'SetWindowTextA', 0x08),
    (0x4f65fe, 'SetWindowTextA', 0x08),
    (None, 'SetDlgItemTextA', 0x0C),
)


def _find_call(exe, secs, iat):
    t = secs['.text']
    code = exe[t['raw']:t['raw'] + t['rsz']]
    pat = b'\xff\x15' + struct.pack('<I', iat)
    i = code.find(pat)
    if i < 0 or code.find(pat, i + 1) >= 0:
        raise ValueError(f'call [{iat:#x}] not unique')
    return BASE + t['va'] + i


def patch(exe: bytes, pairs_va=None):
    secs, pe = sections(exe)
    i = secs['.ld2i']
    last = max(secs.values(), key=lambda s: s['raw'])
    if last is not i or len(exe) != i['raw'] + i['rsz']:
        raise ValueError('.ld2i is not the file tail')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    wctmb = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'WideCharToMultiByte')
    base = BASE + i['va'] + i['rsz']
    blob, cur, info = bytearray(), base, []
    # 共用資料區（ctx／wbuf／sbuf）放最前面
    data = cur; cur += 0x340
    sites = []
    for site, api, arg in SITES:
        iat = iat_slot(exe, secs, pe, 'USER32.dll', api)
        if site is None:
            site = _find_call(exe, secs, iat)
        so = va2off(secs, site)
        if exe[so:so + 6] != b'\xff\x15' + struct.pack('<I', iat):
            raise ValueError(f'{site:#x} is not call [{api}]')
        conv_va = cur
        conv, _ = S.build_stub(conv_va, data, mbtwc, wctmb, arg_esp=arg, target_ind=iat, pairs_va=pairs_va)
        cur += (len(conv) + 0xf) & ~0xf
        sites.append((so, site, conv_va, conv_va, conv, b''))
        info.append({'site': hex(site), 'api': api, 'conv': hex(conv_va)})
    blob = bytearray(cur - base)
    for so, site, fva, cva, conv, front in sites:
        blob[cva - base:cva - base + len(conv)] = conv
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
