r"""m064 lab：把遊戲建立 SHIFTJIS_CHARSET（128）字型的 LOGFONT 指令改為 CHINESEBIG5_CHARSET（136）。

背景：資訊視窗等處以 lfCharSet=128 建字型，TextOutA 會把位元組當 CP932 解讀（與系統 ACP 無關），
所以 `.rdata` 原位改成 Big5 的字串在這些視窗變亂碼（lab：地點欄〈ｼｮｳ･〉）。改成 136 後該字型以 Big5 解讀。
代價：這些視窗內仍是 CP932 的字串會變亂碼 → 需與對應字串翻譯一起上。

修補點（pristine Ld95.exe 檔案偏移；m063d 啟用版相同位置）：每點核對原指令位元組後只改最後 1 byte。
只寫 lab 複本；production_can_apply=false。
  python charset_patch.py --exe in\Ld95.exe --out lab\Ld95.exe [--only 0xd0b5c,...]
"""
import argparse, hashlib, json, sys
from pathlib import Path

SITES = [
    # (file offset, expected bytes, note)
    (0xd0b5c, bytes.fromhex('c644243380'), 'mov byte [esp+0x33],0x80 -> CreateFontIndirectA @0x4d0b6a'),
    (0xd0bbc, bytes.fromhex('c644243380'), 'mov byte [esp+0x33],0x80 (second LOGFONT, same function)'),
    (0x31dbe, bytes.fromhex('c686cf00000080'), 'mov byte [esi+0xcf],0x80 -> CreateFontIndirectA @0x431df7'),
]
SJIS, BIG5 = 0x80, 0x88


def patch(exe: bytes, only=None):
    buf = bytearray(exe); done = []
    for off, want, note in SITES:
        if only and off not in only:
            continue
        got = bytes(buf[off:off + len(want)])
        if got == want[:-1] + bytes([BIG5]):
            done.append({'offset': hex(off), 'status': 'already'}); continue
        if got != want:
            raise ValueError(f'{off:#x}: unexpected bytes {got.hex()}')
        buf[off + len(want) - 1] = BIG5
        done.append({'offset': hex(off), 'status': 'patched', 'note': note})
    return bytes(buf), done


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True); ap.add_argument('--out', required=True); ap.add_argument('--only')
    x = ap.parse_args(argv)
    src, dst = Path(x.exe), Path(x.out)
    if src.resolve() == dst.resolve():
        print('拒絕覆寫輸入 EXE', file=sys.stderr); return 2
    only = {int(v, 0) for v in x.only.split(',')} if x.only else None
    exe = src.read_bytes(); out, done = patch(exe, only)
    dst.write_bytes(out)
    print(json.dumps({'sites': done, 'input_sha256': hashlib.sha256(exe).hexdigest(),
                      'output_sha256': hashlib.sha256(out).hexdigest(), 'lab_only': True,
                      'production_can_apply': False}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
