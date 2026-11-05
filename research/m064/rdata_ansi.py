r"""m064：runtime ANSI 字串 `.rdata` 原位替換（lab 配線工具）。

背景：lab 機系統 ANSI code page = 950（zh-TW）。遊戲以 ANSI API（MessageBoxA／SetWindowTextA／
wsprintfA…）顯示 `.rdata` 內的 CP932 字串，在 CP950 下本來就是亂碼；在原位址改寫為 Big5（CP950）
位元組即可直接顯示繁中，不需 hook。

只做 lab：輸入一個 Ld95.exe 複本，輸出另一個路徑的 EXE＋manifest。絕不覆寫輸入檔。

每列檢查（任一不符 → 該列 skip 並記錄原因；--strict 時整批中止）：
  1. 原文槽 `exe[off:off+len]` 的 sha256 == `source_name_sha256`（UTF-16LE 原文雜湊無法在此驗，
     catalog 的 source_name_sha256 為 CP932 bytes 雜湊；見 `slot_sha256`）。
  2. 槽尾 `exe[off+len] == 0`（確認是 NUL 結尾字串，不越界）。
  3. `text_zh_tw` 可嚴格編成 CP950，且 == `text_cp950_hex`，長度 <= `source_bytes_len`。
  4. 譯文格式合約（printf／indexed／other_percent／controls／mnemonics／literal_ampersands）
     == catalog 的 `source_name_contract`。
  5. 槽位互不重疊。
寫入：`cp950 bytes + NUL × (source_bytes_len − len)`；指標與相鄰字串不動。

用法（Windows 或 Linux 皆可）：
  python rdata_ansi.py check --exe Ld95.exe --catalog research\translations\m063-draft10-*.json
  python rdata_ansi.py apply --exe in\Ld95.exe --out lab\Ld95.exe --catalog ... [--only 0x168dd4,...] [--strict]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
from pathlib import Path

PRINTF = re.compile(r'%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:I64|I32|hh|ll|[hlLjztw])?[diuoxXfFeEgGaAcCsSpn%]')
GAME_PLACEHOLDER = r'%[A-Z]'  # 遊戲自訂替換符（%A..%Z），與 printf 依出現順序合併
TOKEN = re.compile('(?:' + PRINTF.pattern + ')|' + GAME_PLACEHOLDER)
INDEXED = re.compile(r'%[1-9][0-9]*(?:![^!\r\n]+!)?')
CONTROL_NAMES = {'\t': 'TAB', '\n': 'LF', '\r': 'CR'}

SCHEMA = 'm064-rdata-ansi-manifest/1'


def zh_contract(text: str) -> dict:
    """與 m063 catalog `source_name_contract` 相同形狀的合約。"""
    printf = [t for t in TOKEN.findall(text) if t != '%%']
    rest = TOKEN.sub('', text)
    indexed = INDEXED.findall(rest)
    rest = INDEXED.sub('', rest)
    controls = []
    for c in text:
        if c in CONTROL_NAMES:
            controls.append(CONTROL_NAMES[c])
        elif ord(c) < 0x20 or ord(c) == 0x7f:
            controls.append(f'U+{ord(c):04X}')
    no_lit = text.replace('&&', '')
    return dict(
        printf=printf,
        indexed=indexed,
        other_percent=rest.count('%'),
        controls=controls,
        mnemonics=re.findall(r'&([^&])', no_lit),
        literal_ampersands=text.count('&&'),
        shortcuts=0,
    )


def _norm_contract(c: dict) -> dict:
    c = dict(c)
    sc = c.get('shortcuts', 0)
    c['shortcuts'] = len(sc) if isinstance(sc, list) else int(sc or 0)
    return c


def slot_sha256(exe: bytes, off: int, n: int) -> str:
    return hashlib.sha256(exe[off:off + n]).hexdigest()


def load_items(patterns: list[str]) -> list[dict]:
    paths: list[str] = []
    for p in patterns:
        hit = sorted(glob.glob(p))
        if not hit:
            raise FileNotFoundError(f'catalog 找不到：{p}')
        paths.extend(hit)
    items, seen = [], {}
    for p in dict.fromkeys(paths):
        doc = json.loads(Path(p).read_text('utf-8-sig'))
        for flag in ('production_can_apply', 'release_approved'):
            if doc.get(flag) is not False:
                raise ValueError(f'{p}: {flag} 必須為 false')
        for it in doc.get('items', []):
            if it.get('category') != 'runtime_ansi':
                continue
            off = int(it['file_offset'])
            if off in seen:
                raise ValueError(f'offset 重複 {off:#x}：{seen[off]} 與 {p}')
            seen[off] = Path(p).name
            items.append({**it, '_catalog': Path(p).name, '_source_sha256': doc.get('source_sha256')})
    items.sort(key=lambda it: int(it['file_offset']))
    return items


def check_item(exe: bytes, it: dict) -> tuple[bytes | None, str | None]:
    off, n = int(it['file_offset']), int(it['source_bytes_len'])
    if off < 0 or off + n >= len(exe):
        return None, 'out_of_range'
    if slot_sha256(exe, off, n) != it['source_name_sha256']:
        return None, 'source_slot_sha_mismatch'
    if exe[off + n] != 0:
        return None, 'slot_not_nul_terminated'
    zh = it['text_zh_tw']
    if not isinstance(zh, str) or not zh or '\0' in zh:
        return None, 'bad_translation_text'
    try:
        enc = zh.encode('cp950', 'strict')
    except UnicodeEncodeError:
        return None, 'not_cp950_encodable'
    if enc.decode('cp950') != zh:
        return None, 'cp950_not_reversible'
    if it.get('text_cp950_hex') and enc.hex() != it['text_cp950_hex'].lower():
        return None, 'cp950_hex_mismatch'
    if b'\0' in enc:
        return None, 'nul_in_encoded'
    if len(enc) > n:
        return None, 'over_capacity'
    if _norm_contract(zh_contract(zh)) != _norm_contract(it['source_name_contract']):
        return None, 'contract_mismatch'
    return enc + b'\0' * (n - len(enc)), None


def plan(exe: bytes, items: list[dict], only: set[int] | None = None) -> dict:
    rows, last_end = [], -1
    for it in items:
        off = int(it['file_offset'])
        if only is not None and off not in only:
            continue
        payload, reason = check_item(exe, it)
        n = int(it['source_bytes_len'])
        if reason is None and off < last_end:
            payload, reason = None, 'overlap'
        if reason is None:
            last_end = off + n + 1
        rows.append({'offset': off, 'offset_hex': f'{off:#x}', 'len': n, 'catalog': it['_catalog'],
                     'subcategory': it.get('subcategory'), 'ok': reason is None, 'reason': reason,
                     'payload': payload})
    return {'rows': rows, 'ok': sum(r['ok'] for r in rows), 'skipped': sum(not r['ok'] for r in rows)}


def apply(exe: bytes, p: dict) -> bytes:
    buf = bytearray(exe)
    for r in p['rows']:
        if r['ok']:
            o, n = r['offset'], r['len']
            assert len(r['payload']) == n
            buf[o:o + n] = r['payload']
    out = bytes(buf)
    # 事後核對：只有 ok 列的槽位改變
    diff = [i for i in range(len(exe)) if exe[i] != out[i]] if len(exe) < 64 * 1024 * 1024 else []
    allowed = set()
    for r in p['rows']:
        if r['ok']:
            allowed.update(range(r['offset'], r['offset'] + r['len']))
    if any(i not in allowed for i in diff):
        raise AssertionError('寫入範圍超出允許槽位')
    return out


def manifest(exe_in: bytes, exe_out: bytes | None, p: dict, args: dict) -> dict:
    by_reason: dict[str, int] = {}
    for r in p['rows']:
        if not r['ok']:
            by_reason[r['reason']] = by_reason.get(r['reason'], 0) + 1
    return {
        'schema': SCHEMA,
        'lab_only': True,
        'production_can_apply': False,
        'release_approved': False,
        'rendering_verified': False,
        'input_sha256': hashlib.sha256(exe_in).hexdigest(),
        'output_sha256': hashlib.sha256(exe_out).hexdigest() if exe_out is not None else None,
        'args': args,
        'rows_total': len(p['rows']),
        'rows_applied': p['ok'],
        'rows_skipped': p['skipped'],
        'skipped_by_reason': by_reason,
        'rows': [{k: v for k, v in r.items() if k != 'payload'} for r in p['rows']],
    }


def _parse_only(s: str | None) -> set[int] | None:
    if not s:
        return None
    return {int(x, 0) for x in s.split(',') if x.strip()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='cmd', required=True)
    for name in ('check', 'apply'):
        a = sp.add_parser(name)
        a.add_argument('--exe', required=True)
        a.add_argument('--catalog', required=True, action='append')
        a.add_argument('--only')
        a.add_argument('--strict', action='store_true')
        a.add_argument('--manifest')
        if name == 'apply':
            a.add_argument('--out', required=True)
    x = ap.parse_args(argv)
    exe_path = Path(x.exe)
    exe = exe_path.read_bytes()
    items = load_items(x.catalog)
    p = plan(exe, items, _parse_only(x.only))
    out = None
    if x.strict and p['skipped']:
        print(json.dumps(manifest(exe, None, p, vars(x))['skipped_by_reason'], ensure_ascii=False))
        print('strict：有列被 skip，中止', file=sys.stderr)
        return 2
    if x.cmd == 'apply':
        outp = Path(x.out)
        if outp.resolve() == exe_path.resolve():
            print('拒絕覆寫輸入 EXE', file=sys.stderr)
            return 2
        out = apply(exe, p)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_bytes(out)
    m = manifest(exe, out, p, {k: v for k, v in vars(x).items()})
    text = json.dumps(m, ensure_ascii=False, indent=1)
    if x.manifest:
        Path(x.manifest).write_text(text, 'utf-8')
    summary = {k: m[k] for k in ('input_sha256', 'output_sha256', 'rows_total', 'rows_applied', 'rows_skipped', 'skipped_by_reason')}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
