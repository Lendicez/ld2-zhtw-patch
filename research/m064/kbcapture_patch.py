r"""迷宮鍵盤操作：滑鼠點過場景視窗後方向鍵失效的修正（1.0.4）。

擁有者回報（2026-11-18）：在「場景視窗」用滑鼠點箭頭移動後，鍵盤移動失效，點一下其他視窗才恢復。

量測（job 1429，lab 除錯版在選單命令處理 0x489c90 計數）：點擊前按 ↑，命令處理被呼叫；點擊後按 ↓ 不被呼叫，
但直接送 WM_COMMAND（選單）仍會被呼叫 → 是 TranslateAccelerator 這一層沒有送出命令。
原因：場景視窗的 OnMouseMove（0x4cc666 一帶）在游標停在場景上時呼叫 SetCapture（用來偵測游標離開），
滑鼠擷取（capture）期間 Windows 的 TranslateAccelerator 不送出對應選單項目的加速鍵命令；點其他視窗會讓
游標離開場景、ReleaseCapture，所以恢復。

修法：把 MFC 內三處 `call [TranslateAcceleratorA]` 改為呼叫小段程式：若是方向鍵（VK 0x25–0x28）或
數字鍵 1–9（VK 0x61–0x69）的 WM_KEYDOWN，且目前有滑鼠擷取，就先 ReleaseCapture，再原樣跳到
TranslateAcceleratorA。游標若仍在場景上，下一次滑鼠移動時遊戲會自己重新 SetCapture，行為不變。
小段程式附加在 .ld2i 檔尾（可執行）。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.pe_resources import PE  # noqa: E402

EXPECT_SITES = 3


def imports(exe: bytes, pe: PE):
    """{函式名: IAT 位址（VA）}，只解析名稱匯入。"""
    rva = struct.unpack_from('<I', exe, pe.opt + 104)[0]
    out = {}
    p = pe.off(rva)
    while True:
        oft, _, _, name_rva, ft = struct.unpack_from('<IIIII', exe, p)
        if not (oft or ft):
            break
        t = pe.off(oft or ft); k = 0
        while True:
            th = struct.unpack_from('<I', exe, t + 4 * k)[0]
            if not th:
                break
            if not th & 0x80000000:
                q = pe.off(th + 2); e = exe.index(b'\0', q)
                out[exe[q:e].decode('ascii')] = pe.base + ft + 4 * k
            k += 1
        p += 20
    return out


def stub(iat_ta: int, iat_getcap: int, iat_relcap: int) -> bytes:
    a = bytearray()
    lab, fix = {}, []

    def jcc(op, target):
        a.extend([op, 0]); fix.append((len(a) - 1, target))
    a += bytes.fromhex('8b44240c')                    # mov eax, [esp+0xc]   ; lpMsg
    a += bytes.fromhex('817804') + struct.pack('<I', 0x100)   # cmp dword [eax+4], WM_KEYDOWN
    jcc(0x75, 'go')                                   # jne go
    a += bytes.fromhex('8b4008')                      # mov eax, [eax+8]     ; wParam（虛擬鍵）
    a += bytes.fromhex('83f825'); jcc(0x72, 'go')     # cmp eax, VK_LEFT ; jb go
    a += bytes.fromhex('83f828'); jcc(0x76, 'rel')    # cmp eax, VK_DOWN ; jbe rel
    a += bytes.fromhex('83f861'); jcc(0x72, 'go')     # cmp eax, VK_NUMPAD1 ; jb go
    a += bytes.fromhex('83f869'); jcc(0x77, 'go')     # cmp eax, VK_NUMPAD9 ; ja go
    lab['rel'] = len(a)
    a += bytes.fromhex('ff15') + struct.pack('<I', iat_getcap)    # call [GetCapture]
    a += bytes.fromhex('85c0'); jcc(0x74, 'go')                   # test eax, eax ; jz go
    a += bytes.fromhex('ff15') + struct.pack('<I', iat_relcap)    # call [ReleaseCapture]
    lab['go'] = len(a)
    a += bytes.fromhex('ff25') + struct.pack('<I', iat_ta)        # jmp [TranslateAcceleratorA]
    for pos, t in fix:
        rel = lab[t] - (pos + 1)
        assert -128 <= rel <= 127
        a[pos] = rel & 0xff
    return bytes(a)


def patch(exe: bytes):
    pe = PE(exe)
    imp = imports(exe, pe)
    ta, gc, rc = imp['TranslateAcceleratorA'], imp['GetCapture'], imp['ReleaseCapture']
    text = next(s for s in pe.sections if s['name'] == '.text')
    pat = b'\xff\x15' + struct.pack('<I', ta)
    seg = exe[text['rp']:text['rp'] + text['rs']]
    sites, i = [], seg.find(pat)
    while i >= 0:
        sites.append(text['rp'] + i); i = seg.find(pat, i + 1)
    if len(sites) != EXPECT_SITES:
        raise ValueError(f'TranslateAcceleratorA 呼叫點應為 {EXPECT_SITES} 處，實際 {len(sites)}')
    last = max(pe.sections, key=lambda s: s['rp'])
    if last['name'] != '.ld2i' or len(exe) != last['rp'] + last['rs']:
        raise ValueError('.ld2i is not the file tail')
    code = stub(ta, gc, rc)
    stub_va = pe.base + last['va'] + last['rs']
    out = bytearray(exe)
    for p in sites:
        va = pe.base + text['va'] + p - text['rp']
        out[p:p + 6] = b'\xe8' + struct.pack('<i', stub_va - (va + 5)) + b'\x90'
    grow = 0x1000
    out += code + b'\xcc' * (grow - len(code))
    hdr = last['header']
    struct.pack_into('<I', out, hdr + 8, last['rs'] + grow)
    struct.pack_into('<I', out, hdr + 16, last['rs'] + grow)
    salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
    struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'sites': [hex(pe.base + text['va'] + p - text['rp']) for p in sites], 'stub_va': hex(stub_va),
                        'stub_bytes': len(code)}
