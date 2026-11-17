r"""迷宮鍵盤操作（1.0.4 候選）：在主選單的加速鍵表（RT_ACCELERATOR 128）加上方向鍵／數字鍵 → 既有的「迷宮」選單移動命令。

量測（2026-11-17，job 1379）：迷宮選單「往北／東／西／南移動」（32851／32852／32853／32854）每次只動一格；
方向與目前面向不同時第一次只轉向、再按才前進（遊戲原本行為）。畫面上北＝右上、東＝右下、南＝左下、西＝左上。

對應：
  ↑／數字鍵 8／數字鍵 9 → 北　　→／數字鍵 6／數字鍵 3 → 東
  ↓／數字鍵 2／數字鍵 1 → 南　　←／數字鍵 4／數字鍵 7 → 西
（方向鍵依選單與地圖的東西南北；數字鍵 9／3／1／7 依畫面斜向。）

只送既有選單命令：MFC 對加速鍵命令會先檢查命令是否可用（不在迷宮時「迷宮」選單停用，按鍵不會有作用），
與玩家從選單點選完全相同，不新增遊戲邏輯。表內原有 9 筆（Ctrl+N 等）保留。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.pe_resources import PE  # noqa: E402

RT_ACCELERATOR, ACCEL_ID = 9, 128
FVIRTKEY, FLAST = 0x01, 0x80
NORTH, EAST, WEST, SOUTH = 32851, 32852, 32853, 32854
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
VK_NUMPAD = {n: 0x60 + n for n in range(10)}
KEYS = [(VK_UP, NORTH), (VK_RIGHT, EAST), (VK_DOWN, SOUTH), (VK_LEFT, WEST),
        (VK_NUMPAD[8], NORTH), (VK_NUMPAD[6], EAST), (VK_NUMPAD[2], SOUTH), (VK_NUMPAD[4], WEST),
        (VK_NUMPAD[9], NORTH), (VK_NUMPAD[3], EAST), (VK_NUMPAD[1], SOUTH), (VK_NUMPAD[7], WEST)]


def parse(raw: bytes):
    """ACCELTABLEENTRY：u16 旗標、u16 鍵、u16 命令、u16 填充；最後一筆旗標含 0x80。"""
    out = []
    for p in range(0, len(raw) - 7, 8):
        f, k, c, _ = struct.unpack_from('<HHHH', raw, p)
        out.append((f & ~FLAST, k, c))
        if f & FLAST:
            break
    else:
        raise ValueError('加速鍵表沒有結尾旗標')
    return out


def encode(entries) -> bytes:
    if not entries:
        raise ValueError('空的加速鍵表')
    return b''.join(struct.pack('<HHHH', f | (FLAST if i == len(entries) - 1 else 0), k, c, 0)
                    for i, (f, k, c) in enumerate(entries))


def add_keys(entries, keys=KEYS):
    """加入（虛擬鍵、無修飾鍵）→ 命令；同一按鍵組合已存在就拒絕（不覆蓋原有快捷鍵）。"""
    have = {(f, k) for f, k, _ in entries}
    new = list(entries)
    for vk, cmd in keys:
        if (FVIRTKEY, vk) in have:
            raise ValueError(f'按鍵 0x{vk:02x} 已有對應')
        new.append((FVIRTKEY, vk, cmd)); have.add((FVIRTKEY, vk))
    return new


def patch(exe: bytes):
    pe = PE(exe)
    rs = [r for r in pe.resources if r['path'][0] == RT_ACCELERATOR and r['path'][1] == ACCEL_ID]
    if len(rs) != 1:
        raise ValueError('找不到唯一的加速鍵表 128')
    r = rs[0]
    old = parse(pe.payload(r))
    new = encode(add_keys(old))
    out = bytearray(exe)
    secs = pe.sections
    last = max(secs, key=lambda s: s['rp'])
    if last['name'] != '.ld2i' or len(exe) != last['rp'] + last['rs']:
        raise ValueError('.ld2i is not the file tail')
    # 附加在 .ld2i 尾端（與 res_extra 相同做法），改指資料項 RVA 與大小
    grow = 0x1000
    tail_rva = last['va'] + last['rs']
    struct.pack_into('<II', out, r['entry'], tail_rva, len(new))
    out += new + b'\0' * (grow - len(new))
    hdr = last['header']
    struct.pack_into('<I', out, hdr + 8, last['rs'] + grow)
    struct.pack_into('<I', out, hdr + 16, last['rs'] + grow)
    salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
    struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'old_entries': len(old), 'added': len(KEYS), 'rva': hex(tail_rva)}
