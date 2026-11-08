r"""發行用差分包產生器：由使用者合法持有的原版遊戲資料夾與 lab 建置結果，產生「只含差異」的 payload。

payload 不含任何完整原檔：每個檔案以 COPY（取原檔區段）／LIT（新位元組：譯文、修補碼、重繪像素）
組成，安裝端必須先核對原檔 sha256 才能重建，重建後再核對目標 sha256。

格式（little-endian）：
  b'LD2ZHTW\x01' | u32 json_len | json(UTF-8) | ops…
  json = {"version", "files": [{"path", "src_sha256", "src_size", "dst_sha256", "dst_size", "ops_off", "ops_len"}]}
  ops  = 重複 { u8 kind(1=COPY,2=LIT) | u32 a | u32 b | (LIT: b 個位元組) }，COPY: a=原檔位移, b=長度；LIT: a=0, b=長度

  python make_delta.py --src <原版遊戲根> --dst <lab 遊戲根> --version 1.0.0 --out payload.bin [--report r.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

MAGIC = b'LD2ZHTW\x01'
MIN_COPY = 12
GRAM = 8
SKIP_DIRS = {'Usr'}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def diff(src: bytes, dst: bytes):
    """回傳 ops 清單 [('C', off, n) | ('L', bytes)]。"""
    index = None
    if len(src) <= 4 << 20:
        index = {}
        for i in range(len(src) - GRAM, -1, -1):
            index[src[i:i + GRAM]] = i
    ops, lit = [], bytearray()
    i, n = 0, len(dst)

    def flush():
        if lit:
            ops.append(('L', bytes(lit))); lit.clear()
    while i < n:
        best_off, best_len = -1, 0
        # 1) 同位置（原位修補的主要情形）
        if i < len(src) and src[i:i + MIN_COPY] == dst[i:i + MIN_COPY]:
            j = i
            while j < n and j < len(src) and src[j] == dst[j]:
                j += 1
            best_off, best_len = i, j - i
        # 2) 其他位置（BMH 重新壓縮、資源搬移）
        elif index is not None and i + GRAM <= n:
            o = index.get(dst[i:i + GRAM])
            if o is not None:
                j = 0
                while i + j < n and o + j < len(src) and src[o + j] == dst[i + j]:
                    j += 1
                if j >= MIN_COPY:
                    best_off, best_len = o, j
        if best_len >= MIN_COPY:
            flush(); ops.append(('C', best_off, best_len)); i += best_len
        else:
            lit.append(dst[i]); i += 1
    flush()
    return ops


def encode_ops(ops) -> bytes:
    out = bytearray()
    for op in ops:
        if op[0] == 'C':
            out += struct.pack('<BII', 1, op[1], op[2])
        else:
            out += struct.pack('<BII', 2, 0, len(op[1])) + op[1]
    return bytes(out)


def apply_ops(src: bytes, blob: bytes) -> bytes:
    """參考實作（安裝端 C# 同邏輯）。"""
    out, p = bytearray(), 0
    while p < len(blob):
        k, a, b = struct.unpack_from('<BII', blob, p); p += 9
        if k == 1:
            if a + b > len(src):
                raise ValueError('copy out of range')
            out += src[a:a + b]
        elif k == 2:
            out += blob[p:p + b]; p += b
        else:
            raise ValueError('bad op')
    return bytes(out)


def changed_files(src_root: Path, dst_root: Path):
    for root, dirs, files in os.walk(dst_root):
        dirs[:] = [d for d in dirs if not (Path(root) == dst_root and d in SKIP_DIRS)]
        for f in sorted(files):
            d = Path(root) / f
            rel = d.relative_to(dst_root)
            s = src_root / rel
            if not s.exists():
                raise SystemExit(f'新檔案不支援（需原檔）：{rel}')
            if s.stat().st_size == d.stat().st_size and s.read_bytes() == d.read_bytes():
                continue
            yield rel.as_posix()


def build(src_root: Path, dst_root: Path, version: str):
    files, blobs, off, report = [], [], 0, []
    for rel in sorted(changed_files(src_root, dst_root)):
        s = (src_root / rel).read_bytes(); d = (dst_root / rel).read_bytes()
        ops = diff(s, d); blob = encode_ops(ops)
        assert apply_ops(s, blob) == d, rel
        lit = sum(len(o[1]) for o in ops if o[0] == 'L')
        files.append({'path': rel, 'src_sha256': sha(s), 'src_size': len(s), 'dst_sha256': sha(d),
                      'dst_size': len(d), 'ops_off': off, 'ops_len': len(blob)})
        report.append({'path': rel, 'size': len(d), 'literal_bytes': lit, 'literal_ratio': round(lit / max(len(d), 1), 4)})
        blobs.append(blob); off += len(blob)
    meta = json.dumps({'version': version, 'files': files}, ensure_ascii=False).encode('utf-8')
    return MAGIC + struct.pack('<I', len(meta)) + meta + b''.join(blobs), report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True); ap.add_argument('--dst', required=True)
    ap.add_argument('--version', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--report')
    x = ap.parse_args(argv)
    payload, report = build(Path(x.src), Path(x.dst), x.version)
    Path(x.out).write_bytes(payload)
    summary = {'files': len(report), 'payload_bytes': len(payload), 'payload_sha256': sha(payload),
               'max_literal_ratio': max((r['literal_ratio'] for r in report), default=0)}
    if x.report:
        Path(x.report).write_text(json.dumps({'summary': summary, 'files': report}, ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
