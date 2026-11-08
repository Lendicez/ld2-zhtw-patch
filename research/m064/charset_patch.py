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
    (0xd0bf3, bytes.fromhex('c644242f80'), 'mov byte [esp+0x2f],0x80 (third LOGFONT, height -12, same function)'),
]
# 字型名：上述 LOGFONT 與設定預設值都取 .rdata 0x12c338「ＭＳ ゴシック」（CP932 13 B）。
# 字集改 Big5 後此名稱在 ACP 950 下是亂碼 → 由系統替代（多半變細明體）。改為「微軟正黑體」（Win10/11 內建、
# 繁中 Windows 預設 UI 字型；英文名 18 B 放不下 13 B 槽，故用 CP950 名稱，本補丁本就要求 ACP 950）。
# 設定預設值的長度參數 13 → 10。
FACE_OFF, FACE_SHA_LEN = 0x12c338, 13
FACE_NEW = '微軟正黑體'.encode('cp950')
FACE_SRC_SHA256 = '482a053efd81f4f02ee6989471a88c7a01842fa50249e6afc83470afbf81a01f'
FACE_LEN_SITE, FACE_LEN_WANT = 0x31b43, bytes.fromhex('6a0d6838c35200')


def face_patch(exe: bytes):
    import hashlib as _h
    buf = bytearray(exe)
    src = bytes(buf[FACE_OFF:FACE_OFF + FACE_SHA_LEN + 1])
    if src[:len(FACE_NEW) + 1] == FACE_NEW + b'\0':
        return bytes(buf), {'status': 'already'}
    if src[-1] != 0 or _h.sha256(src[:-1]).hexdigest() != FACE_SRC_SHA256:
        raise ValueError('face name slot mismatch')
    got = bytes(buf[FACE_LEN_SITE:FACE_LEN_SITE + len(FACE_LEN_WANT)])
    if got != FACE_LEN_WANT:
        raise ValueError(f'{FACE_LEN_SITE:#x}: unexpected bytes {got.hex()}')
    buf[FACE_OFF:FACE_OFF + FACE_SHA_LEN + 1] = FACE_NEW + b'\0' * (FACE_SHA_LEN + 1 - len(FACE_NEW))
    buf[FACE_LEN_SITE + 1] = len(FACE_NEW)
    return bytes(buf), {'status': 'patched', 'face': FACE_NEW.decode('cp950')}
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
