r"""m064 lab：在 m063d 啟用版 EXE 的 `.ld2c` v4 catalog blob 追加 FULL_ANY 列（不重建 helper）。

用途：經 v4 TextOut／List hook 顯示的字串（地點、路名、城鎮名…），`.rdata`／`.data` 原位改成 Big5 後，
hook 會以 CP932 解碼而出現亂碼。在 catalog 加一列「鍵＝新 Big5 位元組、值＝繁中 UTF-16」，
hook 查表命中即輸出繁中。另可加「鍵＝原 CP932 位元組」列，未原位替換的點也能顯示繁中。

`.ld2c` 版面（merge_plan_v3／v4）：+0 CatalogBytes（u32，必須 == blob 長度，helper 據此開 blob；不符即
整份 catalog 失效、退回原文）｜+4 ExpectedTextOutA｜+8 OriginalDlgItem｜+12 ListMode｜+16 blob。本工具會同步更新
CatalogBytes 與區段 VirtualSize（== 0x10 + blob）。

格式與排序和 `research/m063/catalog_v4.encode_v4` 相同（header 32、row 16、pool 對齊），
差別只在不要求鍵為合法 CP932（native helper 只做位元組比對）。blob 必須放得進 `.ld2c` 原始大小；
必要時調大該區段 VirtualSize（不超過 raw 大小，不移動任何區段）。

只寫 lab 複本；輸入檔不覆寫；production_can_apply=false。

  python catalog_patch.py --exe in\Ld95.exe --out lab\Ld95.exe --rows rows.json [--manifest m.json]
  rows.json: [{"ansi_hex": "...", "zh": "廣場"}, ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

MAGIC, VERSION, HEADER, ROW = 0x43324C44, 4, 32, 16  # 'DL2C'
FULL_ANY, ANY_ID = 2, -1
MAX_ROWS, MAX_POOL, MAX_ANSI, MAX_UNITS = 8192, 1 << 20, 255, 255


def sections(exe: bytes):
    pe = struct.unpack_from('<I', exe, 0x3c)[0]
    n = struct.unpack_from('<H', exe, pe + 6)[0]
    so = struct.unpack_from('<H', exe, pe + 20)[0]
    base = pe + 24 + so
    out = []
    for i in range(n):
        name, vsz, va, rsz, raw = struct.unpack_from('<8sIIII', exe, base + 40 * i)
        out.append({'name': name.rstrip(b'\0').decode('latin1'), 'vsz': vsz, 'va': va, 'rsz': rsz, 'raw': raw,
                    'hdr': base + 40 * i})
    return out


def find_blob(exe: bytes):
    sec = next(s for s in sections(exe) if s['name'] == '.ld2c')
    i = exe.find(struct.pack('<I', MAGIC), sec['raw'], sec['raw'] + sec['rsz'])
    if i < 0:
        raise ValueError('no v4 blob in .ld2c')
    magic, ver, hsize, count, rsize, roff, poff, plen, flags = struct.unpack_from('<IHHIIIIII', exe, i)
    if (ver, hsize, rsize, roff, flags) != (VERSION, HEADER, ROW, HEADER, 1) or poff != roff + count * rsize:
        raise ValueError('unexpected v4 header')
    if i != sec['raw'] + 16 or struct.unpack_from('<I', exe, sec['raw'])[0] != poff + plen:
        raise ValueError('.ld2c prefix (CatalogBytes) does not match blob')
    return sec, i, poff + plen


def decode(blob: bytes):
    _, _, _, count, _, roff, poff, plen, _ = struct.unpack_from('<IHHIIIIII', blob)
    pool, rows = blob[poff:poff + plen], []
    for k in range(count):
        alen, units, ident, kind, region, a, w = struct.unpack_from('<HHhBBII', blob, roff + k * ROW)
        rows.append((kind, ident, bytes(pool[a:a + alen]), pool[w:w + units * 2].decode('utf-16le'), region))
    return rows


def sort_key(r):
    kind, ident, ansi, text, region = r
    return (kind, len(ansi), ansi, region, ident)


def encode(rows) -> bytes:
    if not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError('row count')
    seen = {}
    uniq = []
    for r in rows:
        key = (r[0], r[1], r[2], r[4])
        if key in seen:
            if seen[key] != r[3]:
                raise ValueError(f'ambiguous key {r[2].hex()}')
            continue
        seen[key] = r[3]
        uniq.append(r)
    uniq.sort(key=sort_key)
    pool, ansi_at, wide_at, table = bytearray(), {}, {}, bytearray()

    def put(b, cache, align):
        if b in cache:
            return cache[b]
        pool.extend(b'\0' * (-len(pool) % align))
        cache[b] = len(pool)
        pool.extend(b)
        return cache[b]
    for kind, ident, ansi, text, region in uniq:
        if not (0 < len(ansi) <= MAX_ANSI and b'\0' not in ansi):
            raise ValueError('ansi bounds')
        wide = text.encode('utf-16le')
        if not 0 < len(wide) // 2 <= MAX_UNITS:
            raise ValueError('text bounds')
        a = put(ansi + b'\0', ansi_at, 1)
        w = put(wide + b'\0\0', wide_at, 2)
        table.extend(struct.pack('<HHhBBII', len(ansi), len(wide) // 2, ident, kind, region, a, w))
    pool.extend(b'\0' * (-len(pool) % 4))
    if len(pool) > MAX_POOL:
        raise ValueError('pool limit')
    header = struct.pack('<IHHIIIIII', MAGIC, VERSION, HEADER, len(uniq), ROW, HEADER, HEADER + len(table), len(pool), 1)
    return header + bytes(table) + bytes(pool)


def patch(exe: bytes, new_rows) -> tuple[bytes, dict]:
    sec, off, old_len = find_blob(exe)
    old = decode(exe[off:off + old_len])
    existing = {(r[0], r[1], r[2], r[4]) for r in old}
    add = [r for r in new_rows if (r[0], r[1], r[2], r[4]) not in existing]
    blob = encode(old + add)
    end = off + len(blob)
    limit = sec['raw'] + sec['rsz']
    if end > limit:
        raise ValueError(f'blob {len(blob)} B does not fit .ld2c (room {limit - off} B)')
    buf = bytearray(exe)
    buf[off:off + max(old_len, len(blob))] = blob + b'\0' * max(0, old_len - len(blob))
    struct.pack_into('<I', buf, sec['raw'], len(blob))          # CatalogBytes
    need_vsz = end - sec['raw']
    vsz_changed = need_vsz != sec['vsz']
    struct.pack_into('<I', buf, sec['hdr'] + 8, need_vsz)       # VirtualSize == 0x10 + blob
    if decode(bytes(buf[off:off + len(blob)])) != sorted(
            {(r[0], r[1], r[2], r[4]): r for r in old + add}.values(), key=sort_key):
        raise AssertionError('round trip')
    info = {'rows_before': len(old), 'rows_added': len(add), 'rows_after': len(old) + len(add),
            'blob_before': old_len, 'blob_after': len(blob), 'room': limit - off, 'vsz_changed': vsz_changed}
    return bytes(buf), info


def load_rows(path: Path):
    out = []
    for r in json.loads(path.read_text('utf-8-sig')):
        out.append((FULL_ANY, ANY_ID, bytes.fromhex(r['ansi_hex']), r['zh'], 0))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--rows', required=True)
    ap.add_argument('--manifest')
    x = ap.parse_args(argv)
    src, dst = Path(x.exe), Path(x.out)
    if src.resolve() == dst.resolve():
        print('拒絕覆寫輸入 EXE', file=sys.stderr)
        return 2
    exe = src.read_bytes()
    out, info = patch(exe, load_rows(Path(x.rows)))
    dst.write_bytes(out)
    info.update(input_sha256=hashlib.sha256(exe).hexdigest(), output_sha256=hashlib.sha256(out).hexdigest(),
                lab_only=True, production_can_apply=False, release_approved=False)
    if x.manifest:
        Path(x.manifest).write_text(json.dumps(info, ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
