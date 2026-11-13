r"""m064：把審查建議（fixes.json：[{file, file_offset, old, new, reason, …}]）套用到 rdata_ansi 目錄。

逐筆驗證後才改：現譯必須等於 old；new 以 CP950 編碼不超過原文槽長；格式合約（%d／%s／%A–%Z、換行）以使用者的
原版 EXE 原文重新計算（不信任目錄內既有欄位）且 new 必須相符。不符者列入 rejected，不套用。

  python apply_fixes.py --repo <repo 根> --exe <原版 Ld95.exe> --fixes fixes.json [--dry-run]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rdata_ansi as R  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True); ap.add_argument('--exe', required=True)
    ap.add_argument('--fixes', required=True); ap.add_argument('--dry-run', action='store_true')
    x = ap.parse_args(argv)
    exe = Path(x.exe).read_bytes()
    by_file = collections.defaultdict(list)
    for f in json.loads(Path(x.fixes).read_text('utf-8')):
        by_file[f['file'].replace('\\', '/')].append(f)
    applied, rejected = 0, []
    for rel, fixes in sorted(by_file.items()):
        p = Path(x.repo) / rel
        raw = p.read_text('utf-8-sig')
        doc = json.loads(raw)
        second = raw.split('\n', 2)[1] if '\n' in raw else ''
        indent = (len(second) - len(second.lstrip(' '))) or None      # 沿用原檔縮排，避免無關的格式差異
        items = {int(it['file_offset']): it for it in doc.get('items', []) if 'file_offset' in it}
        changed = False
        for f in fixes:
            off = int(f['file_offset'])
            it = items.get(off)
            if it is None or 'source_bytes_len' not in it:
                rejected.append((rel, hex(off), 'no such in-place item')); continue
            if it['text_zh_tw'] != f['old']:
                rejected.append((rel, hex(off), 'old mismatch')); continue
            src = exe[off:off + it['source_bytes_len']]
            ja = src.decode('cp932')
            try:
                enc = f['new'].encode('cp950')
            except UnicodeError:
                rejected.append((rel, hex(off), 'not cp950')); continue
            if not enc or len(enc) > len(src):
                rejected.append((rel, hex(off), 'over capacity')); continue
            c = R.zh_contract(ja)
            if R._norm_contract(R.zh_contract(f['new'])) != R._norm_contract(c):
                rejected.append((rel, hex(off), 'contract mismatch')); continue
            it.update(text_zh_tw=f['new'], text_cp950_bytes_len=len(enc), text_cp950_hex=enc.hex(),
                      capacity_slack_bytes=len(src) - len(enc), source_name_contract=c)
            applied += 1; changed = True
        if changed and not x.dry_run:
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else ''), 'utf-8')
    print(json.dumps({'applied': applied, 'rejected': len(rejected)}, ensure_ascii=False))
    for r in rejected:
        print(' ', *r)
    return 0


if __name__ == '__main__':
    sys.exit(main())
