r"""LD2 `.BMH` 圖檔編解碼（lab 工具；格式由 Ld95.exe 0x4716f0／0x471450 逆向）。

檔案 = 檔頭 0x18 bytes + 區塊序列
檔頭：u32 檔案大小、u32 輸出大小（packed DIB：BITMAPINFOHEADER＋調色盤＋像素）、'HF'、u16 0、u32×3（原樣保留）
區塊：u32 nbits、u32 count
  nbits == 0 → 原樣區塊：後接 count bytes
  否則       → u8 碼長[256]；碼字位元（共 sum(碼長) bits，MSB 優先，補齊到 byte）；
               資料位元流 nbits bits（MSB 優先）→ 解出 count 個符號
  碼字逐符號明列（不是 canonical 推導）；遊戲建樹時葉節點存「符號−256」。
輸出累積到「輸出大小」為止。

遊戲接受 nbits==0 的原樣區塊，所以 `encode_raw` 足以重新打包；`encode_huffman` 讓檔案接近原大小。
"""
from __future__ import annotations

import heapq
import struct


class _BitReader:
    def __init__(self, b: bytes, pos: int):
        self.b, self.pos, self.bit, self.cur = b, pos, -1, 0

    def get(self) -> int:
        self.bit -= 1
        if self.bit < 0:
            self.cur = self.b[self.pos]
            self.pos += 1
            self.bit = 7
        return (self.cur >> self.bit) & 1


class _BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.cur = 0
        self.n = 0
        self.total = 0

    def put(self, code: int, length: int):
        for i in range(length - 1, -1, -1):
            self.cur = (self.cur << 1) | ((code >> i) & 1)
            self.n += 1
            self.total += 1
            if self.n == 8:
                self.out.append(self.cur)
                self.cur = self.n = 0

    def flush(self) -> bytes:
        if self.n:
            self.out.append(self.cur << (8 - self.n))
            self.cur = self.n = 0
        return bytes(self.out)


def decode(b: bytes) -> bytes:
    if b[8:10] != b'HF':
        raise ValueError('not an HF/BMH file')
    out_size = struct.unpack_from('<I', b, 4)[0]
    out = bytearray()
    p = 0x18
    while len(out) < out_size:
        nbits, count = struct.unpack_from('<II', b, p)
        if nbits == 0:
            out += b[p + 8:p + 8 + count]
            p += 8 + count
            continue
        lens = b[p + 8:p + 8 + 256]
        left = [0x7fff] * 512
        right = [0x7fff] * 512
        nodes = 0
        br = _BitReader(b, p + 8 + 256)
        for sym in range(256):
            length = lens[sym]
            node = 0
            for i in range(length):
                arr = right if br.get() else left
                v = arr[node]
                if v == 0x7fff:
                    if i == length - 1:
                        arr[node] = sym - 256
                    else:
                        nodes += 1
                        if nodes >= 512:
                            raise ValueError('tree overflow')
                        arr[node] = nodes
                        node = nodes
                else:
                    if i == length - 1 or v < 0:
                        raise ValueError('code collision')
                    node = v
        hdr = 0x108 + (sum(lens) + 7) // 8
        br = _BitReader(b, p + hdr)
        for _ in range(count):
            node = 0
            while True:
                node = (right if br.get() else left)[node]
                if node < 0:
                    break
                if node == 0x7fff:
                    raise ValueError('invalid code in stream')
            out.append(node & 0xff)
        p += hdr + (nbits + 7) // 8
    return bytes(out[:out_size])


def _header(template: bytes, body_len: int, out_len: int) -> bytearray:
    h = bytearray(template[:0x18])
    if h[8:10] != b'HF':
        raise ValueError('template is not HF')
    struct.pack_into('<I', h, 0, 0x18 + body_len)
    struct.pack_into('<I', h, 4, out_len)
    return h


def encode_raw(data: bytes, template_header: bytes) -> bytes:
    body = struct.pack('<II', 0, len(data)) + data
    return bytes(_header(template_header, len(body), len(data))) + body


def _code_lengths(data: bytes) -> list[int]:
    freq = [0] * 256
    for x in data:
        freq[x] += 1
    heap = [(f, i, (s,)) for i, (s, f) in enumerate((s, f) for s, f in enumerate(freq) if f)]
    lens = [0] * 256
    if len(heap) == 1:
        lens[heap[0][2][0]] = 1
        return lens
    heapq.heapify(heap)
    uid = 256
    while len(heap) > 1:
        f1, _, a = heapq.heappop(heap)
        f2, _, b = heapq.heappop(heap)
        for s in a + b:
            lens[s] += 1
        heapq.heappush(heap, (f1 + f2, uid, a + b))
        uid += 1
    return lens


def _codes_from_lengths(lens: list[int]) -> dict[int, tuple[int, int]]:
    order = sorted((l, s) for s, l in enumerate(lens) if l)
    codes, code, prev = {}, 0, order[0][0]
    for l, s in order:
        code <<= (l - prev)
        prev = l
        codes[s] = (code, l)
        code += 1
    return codes


def encode_huffman(data: bytes, template_header: bytes, block: int = 1 << 20) -> bytes:
    body = bytearray()
    for start in range(0, len(data), block):
        chunk = data[start:start + block]
        lens = _code_lengths(chunk)
        if max(lens) > 24:  # 過深就退回原樣區塊
            body += struct.pack('<II', 0, len(chunk)) + chunk
            continue
        codes = _codes_from_lengths(lens)
        tw = _BitWriter()
        for s in range(256):
            if lens[s]:
                tw.put(*codes[s])
        table_bits = tw.flush()
        dw = _BitWriter()
        for x in chunk:
            dw.put(*codes[x])
        nbits = dw.total
        stream = dw.flush()
        body += struct.pack('<II', nbits, len(chunk)) + bytes(lens) + table_bits + stream
    return bytes(_header(template_header, len(body), len(data))) + bytes(body)
