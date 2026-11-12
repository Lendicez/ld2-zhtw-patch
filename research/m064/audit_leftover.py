r"""m064：建置後「找漏網」稽核（1.0.2 工作 1）。輸入使用者的原版與 lab EXE，輸出 JSON 報表（不含原文以外的資產；
報表含日文原文片段，只放 lab，不入庫）。

1. strings：.rdata／.data 中仍與原版相同（未原位翻譯）、不是 catalog 鍵、且在 CP950 下無法正確顯示的文字。
   起始條件放寬為「前一位元組是 NUL／控制碼／0xFF」（記錄內嵌字串）。分類：
     kana        含假名（對話、名稱）
     kanji_bad   純漢字／符號但含 CP950 無法編碼的字（例「竜」），或全形數字
     kanji_ok    純漢字且每字 CP950 都有（顯示後備照字形轉即可，風險低；僅統計）
2. list_sites：所有經 MFC SendDlgItemMessage（0x4ea671）送出 LB_ADDSTRING／LB_INSERTSTRING／CB_ADDSTRING／
   CB_INSERTSTRING 的呼叫點，及其在 lab 的去向：orig（未接轉換）／m063（整串查表 hook）／conv（逐詞轉換 stub）。

  python audit_leftover.py --pristine <原版 Ld95.exe> --lab <lab Ld95.exe> --out report.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tab_title_patch import sections, BASE  # noqa: E402
from gen_lab_tx import is_junk  # noqa: E402
import catalog_patch  # noqa: E402

TEXT = re.compile(rb'(?:[\x20-\x7e]|[\xa1-\xdf]|[\x81-\x9f\xe0-\xea][\x40-\x7e\x80-\xfc])+\x00')
KANA = re.compile('[ぁ-ヿｦ-ﾟ]')
SEND = 0x4ea671
MSGS = {0x180: 'LB_ADDSTRING', 0x181: 'LB_INSERTSTRING', 0x143: 'CB_ADDSTRING', 0x14a: 'CB_INSERTSTRING'}
M063_HOOKS = (0xae4000, 0xae5c00)        # v4 helper 的清單 hook 範圍（.ld2t 前段）
PLACEHOLDER = '追加アイテム未定義'.encode('cp932')


def cp950_ok(t: str) -> bool:
    try:
        t.encode('cp950')
    except UnicodeError:
        return False
    return not re.search('[０-９Ａ-ｚ]', t)   # 全形英數在 CP932 位元組下仍讀不出


def scan_strings(p: bytes, lab: bytes):
    secs, _ = sections(p)
    _, off, ln = catalog_patch.find_blob(lab)
    keys = {r[2] for r in catalog_patch.decode(lab[off:off + ln])}
    out = collections.defaultdict(list)
    placeholder = 0
    for name in ('.rdata', '.data'):
        s = secs[name]
        for m in TEXT.finditer(p, s['raw'], s['raw'] + s['rsz']):
            o, raw = m.start(), m.group(0)[:-1]
            prev = p[o - 1]
            if not (prev == 0 or prev < 0x20 or prev == 0xFF) or len(raw) < 2:
                continue
            if not any(b >= 0x80 for b in raw) or lab[o:o + len(raw)] != raw or raw in keys:
                continue
            if raw == PLACEHOLDER:
                placeholder += 1; continue
            try:
                t = raw.decode('cp932')
            except UnicodeError:
                continue
            if is_junk(t, o) or not re.search('[ぁ-ヿ一-鿿０-ｚｦ-ﾟ]', t):
                continue
            kind = 'kana' if KANA.search(t) else ('kanji_ok' if cp950_ok(t) else 'kanji_bad')
            out[kind].append({'offset': hex(o), 'section': name, 'bytes': len(raw), 'prev': prev, 'ja': t})
    return out, placeholder


def scan_sites(p: bytes, lab: bytes):
    secs, _ = sections(p)
    t = secs['.text']
    code = p[t['raw']:t['raw'] + t['rsz']]
    rows = []
    for i in range(len(code) - 5):
        if code[i] != 0xE8:
            continue
        va = BASE + t['va'] + i
        if va + 5 + struct.unpack_from('<i', code, i + 1)[0] != SEND:
            continue
        win = code[max(0, i - 14):i]
        m = re.search(rb'\x68(....)\x68(....)(?:\x8b.)?$', win, re.S)
        if not m:
            continue
        msg, cid = struct.unpack('<I', m.group(1))[0], struct.unpack('<I', m.group(2))[0]
        if msg not in MSGS:
            continue
        tgt = va + 5 + struct.unpack_from('<i', lab, t['raw'] + i + 1)[0]
        route = 'orig' if tgt == SEND else 'm063' if M063_HOOKS[0] <= tgt < M063_HOOKS[1] else 'conv'
        rows.append({'site': hex(va), 'msg': MSGS[msg], 'ctrl_id': hex(cid), 'lab_target': hex(tgt), 'route': route})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pristine', required=True); ap.add_argument('--lab', required=True); ap.add_argument('--out', required=True)
    x = ap.parse_args(argv)
    p, lab = Path(x.pristine).read_bytes(), Path(x.lab).read_bytes()
    strings, placeholder = scan_strings(p, lab)
    sites = scan_sites(p, lab)
    summary = {'strings': {k: len(v) for k, v in strings.items()}, 'placeholder_item_slots': placeholder,
               'list_sites': dict(collections.Counter(r['route'] for r in sites))}
    Path(x.out).write_text(json.dumps({'summary': summary, 'strings': strings, 'list_sites': sites},
                                      ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
