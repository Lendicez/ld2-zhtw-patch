r"""迷宮：用選單／鍵盤下移動指令時，結束滑鼠連續行走模式（1.0.4）。

問題（擁有者回報 2026-11-18，job 1413–1419 重現）：在「場景視窗」點畫面箭頭讓角色連續行走後，只要游標還停在
場景視窗上，鍵盤（以及選單「往南移動」等）都沒有作用；點一下其他視窗才恢復。

原因：場景物件（app→[+0xb0]→[+0x2c60]）的 `+0xf160` 是「滑鼠行走模式」旗標，點擊畫面時設 1，之後場景視窗的
OnMouseMove（0x4cc540 一帶）每次都依游標位置呼叫 0x466910(1..4) 重新指定連續行走方向，蓋掉選單／鍵盤送來的
單步指令（0x466910(5..8)）；游標離開場景視窗時才清為 0。

修法：0x466910（寫入指令 `+0xf154`）原本只在指令＝0（停止）時清 `+0xf160`；改為「指令不是 1..4（滑鼠連續行走）
就清」，即選單／鍵盤的單步、調查、等待都會結束滑鼠行走模式。原函式 0x466910..0x46693f 共 48 位元組（含尾端 int3），
原位改寫，不需額外空間；其餘行為（`+0x101a0` 忙碌時忽略、記錄前一指令 `+0xf158`）不變。
"""
from __future__ import annotations

VA = 0x466910
OLD = bytes.fromhex('83b9a00101000075208b8154f10000898158f100008b44240485c0898154f100007506898160f10000c20400cccccccc')
NEW = bytes.fromhex(
    '83b9a001010000'      # cmp dword [ecx+0x101a0], 0
    '7523'                # jne done
    '8b8154f10000'        # mov eax, [ecx+0xf154]
    '898158f10000'        # mov [ecx+0xf158], eax
    '8b442404'            # mov eax, [esp+4]
    '898154f10000'        # mov [ecx+0xf154], eax
    '48'                  # dec eax
    '83f803'              # cmp eax, 3
    '7607'                # jbe done          ; 指令 1..4（滑鼠連續行走）保留旗標
    '83a160f1000000'      # and dword [ecx+0xf160], 0
    'c20400'              # done: ret 4
    'cc')                 # 補齊
assert len(OLD) == len(NEW) == 48


def _off(exe: bytes, va: int) -> int:
    import struct
    pe = struct.unpack_from('<I', exe, 0x3C)[0]
    nsec, opt_size = struct.unpack_from('<HH', exe, pe + 6)[0], struct.unpack_from('<H', exe, pe + 20)[0]
    base = struct.unpack_from('<I', exe, pe + 24 + 28)[0]
    for i in range(nsec):
        o = pe + 24 + opt_size + 40 * i
        vs, rva, rs, raw = struct.unpack_from('<IIII', exe, o + 8)
        if rva <= va - base < rva + max(vs, rs):
            return raw + va - base - rva
    raise ValueError('VA 不在任何區段')


def patch(exe: bytes):
    o = _off(exe, VA)
    cur = exe[o:o + len(OLD)]
    if cur == NEW:
        return exe, {'already': True}
    if cur != OLD:
        raise ValueError('0x466910 內容與預期不符')
    out = bytearray(exe); out[o:o + len(NEW)] = NEW
    return bytes(out), {'va': hex(VA), 'offset': hex(o), 'bytes': len(NEW)}
