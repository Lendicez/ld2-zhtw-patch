r"""m064 lab：把批次譯文（[{id: "0x…", zh: "…"}]）轉成 rdata_ansi 目錄（只含繁中＋原文槽 sha／合約）。

原文槽長度、sha256、合約由使用者的 pristine EXE 讀出，本庫不含日文原文。
已在其他目錄（m063 drafts、lab-*.json）出現的 offset 會略過，避免重複列。

  python gen_lab_tx.py --exe pristine\Ld95.exe --out ..\translations\m064-tx-dialogue.zh-TW.json "out-*.json" "fix-*.json"
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rdata_ansi as R  # noqa: E402

HERE = Path(__file__).resolve().parent
OTHER = [str(HERE.parent / 'translations' / 'm063-draft*.json'), str(HERE / 'lab-*.json')]


def known_offsets(skip_name: str | None = None) -> set[int]:
    out = set()
    for pat in OTHER:
        for p in glob.glob(pat):
            if skip_name and Path(p).name == skip_name:
                continue
            for it in json.loads(Path(p).read_text('utf-8-sig'))['items']:
                out.add(int(it['file_offset']))
    return out


import re as _re
_WEIRD = _re.compile(r'[\ue000-\uf8ff\ufffd@`<>&=\\{}|^~\[\]\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
_HALF = _re.compile(r'[\uff61-\uff9f]')
_FULL = _re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
_ASCII_LETTER = _re.compile(r'[A-Za-z?]')
JUNK_RDATA_FROM = 0x174000
NOT_TEXT = {0x12c338}   # 字型名「ＭＳ ゴシック」（LOGFONT face；由 charset_patch.face_patch 改 MingLiU）   # .rdata 此後為二進位表（浮點常數、圖表資料），偶然可解成 CP932 → 一律不碰


def is_junk(ja: str, off: int) -> bool:
    """二進位資料偶然解碼成 CP932 的假字串（覆寫會破壞資料表 → 攻擊時閃退的根因）。"""
    if off in NOT_TEXT:
        return True
    if 0x125000 <= off < 0x195000 and off >= JUNK_RDATA_FROM:
        return True
    if _WEIRD.search(ja):
        return True
    core = ja.strip(' \u3000')
    if len(core) <= 3 and (_HALF.search(core) and _FULL.search(core) or _ASCII_LETTER.search(core)):
        return True
    return False


def keep_edges(ja: str, zh: str, cap: int) -> str:
    """保留原文前後的半形／全形空白（版面對齊用），容量允許時補回。"""
    lead = ja[:len(ja) - len(ja.lstrip(' \u3000'))]
    trail = ja[len(ja.rstrip(' \u3000')):]
    core = zh.strip(' \u3000')
    for cand in (lead + core + trail, lead + core, core + trail, zh):
        if len(cand.encode('cp950')) <= cap:
            return cand
    return zh


def build(exe: bytes, rows, skip=frozenset(), sub='dialogue'):
    items, rejected = [], []
    for r in rows:
        off, zh = int(r['id'], 16), r['zh']
        if off in skip:
            rejected.append((r['id'], 'already_cataloged')); continue
        if off <= 0 or exe[off - 1] != 0:
            rejected.append((r['id'], 'not_string_start')); continue
        end = exe.index(b'\0', off)
        src = exe[off:end]
        try:
            ja = src.decode('cp932')
            if is_junk(ja, off):
                rejected.append((r['id'], 'junk_binary')); continue
            enc = zh.encode('cp950')
        except UnicodeError:
            rejected.append((r['id'], 'encoding')); continue
        if len(enc) > len(src) or not enc:
            rejected.append((r['id'], 'over_capacity')); continue
        zh = keep_edges(ja, zh, len(src))
        enc = zh.encode('cp950')
        c = R.zh_contract(ja)
        if R._norm_contract(R.zh_contract(zh)) != R._norm_contract(c):
            rejected.append((r['id'], 'contract_mismatch')); continue
        if zh.count('?') > ja.count('?') + ja.count('？'):
            rejected.append((r['id'], 'question_marks')); continue
        items.append({
            'category': 'runtime_ansi', 'subcategory': f'tx_{sub}', 'file_offset': off, 'file_offset_hex': hex(off),
            'source_bytes_len': len(src), 'source_name_sha256': hashlib.sha256(src).hexdigest(),
            'source_name_contract': c, 'text_zh_tw': zh, 'text_cp950_bytes_len': len(enc),
            'text_cp950_hex': enc.hex(), 'name_cp950_encodable': True, 'fits_capacity': True,
            'capacity_slack_bytes': len(src) - len(enc), 'review_status': 'codex_draft_claude_checked',
            'translation_method': 'codex+validator', 'site_binding': 'static (not yet seen on screen)'})
    items.sort(key=lambda it: it['file_offset'])
    doc = {'schema_version': 1, 'milestone': f'm064-tx-{sub}', 'source_sha256': hashlib.sha256(exe).hexdigest(),
           'production_can_apply': False, 'release_approved': False, 'rendering_verified': False,
           'preview_only': True, 'draft_owner': 'Codex (validated by Claude)',
           'note': 'Static translation of runtime ANSI strings not yet reached by the harness.',
           'item_count': len(items), 'mona_approved_candidate': False, 'site_binding_confirmed': False,
           'items': items}
    return doc, rejected


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--sub', default='dialogue')
    ap.add_argument('batches', nargs='+')
    x = ap.parse_args(argv)
    merged = {}   # 依參數順序合併，後者覆蓋前者（例：out-*.json 之後給 fix-*.json）
    for pat in x.batches:
        for p in sorted(glob.glob(pat)):
            for r in json.loads(Path(p).read_text('utf-8')):
                merged[r['id']] = {'id': r['id'], 'zh': r['zh']}
    rows = list(merged.values())
    doc, rej = build(Path(x.exe).read_bytes(), rows, known_offsets(Path(x.out).name), x.sub)
    Path(x.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps({'items': doc['item_count'], 'rejected': len(rej),
                      'reasons': {k: sum(1 for _, r in rej if r == k) for k in {r for _, r in rej}}}, ensure_ascii=False))
    for i, r in rej[:40]:
        print(' ', i, r)
    return 0


if __name__ == '__main__':
    sys.exit(main())
