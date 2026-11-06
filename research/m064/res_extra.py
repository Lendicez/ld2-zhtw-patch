r"""m064 lab：m020 之後仍為日文的資源（RT_MENU／RT_DIALOG／RT_STRING）繁中化。

m020 已審 239 處；其餘選單（右鍵選單 130／131）、對話框（除錯用、彩票、名字輸入…）、字串表（狀態列提示、
MFC 系統訊息、錯誤訊息）仍是日文。本工具：

  extract：由使用者的 EXE 列出仍含假名的資源文字 → JSON（含日文，只放 lab，不入庫）
  apply  ：依目錄（只含繁中＋原文 UTF-16 sha256＋定位）改寫資源；新內容不大於原大小就原位覆寫並更新
           資料項大小，否則附加在 .ld2i 檔尾並改指 RVA。對話框字型一併改成 m020 使用的字型。

目錄格式（入庫）：{"entries": [{"kind": "menu|dialog_title|dialog_control|string", "resource": 130,
"language": 1041, "locator": [0, 2] | "item_index": 3 | "string_id": 57602, "source_utf16_sha256": "...",
"translation": "..."}], "dialog_font": "新細明體"}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ld2patch.pe_resources import PE, string_block, encode_string_block, parse_dialog, encode_dialog  # noqa: E402
from ld2patch import menu  # noqa: E402

JA = re.compile(r'[぀-ヿｦ-ﾟ]')
IMAGE_SCN_EXEC = 0x20000000 | 0x00000020


def sha16(t: str) -> str:
    return hashlib.sha256(t.encode('utf-16le')).hexdigest()


def _walk_menu(items, path=()):
    for i, it in enumerate(items):
        yield path + (i,), it
        if 'children' in it:
            yield from _walk_menu(it['children'], path + (i,))


def extract(exe: bytes):
    pe = PE(exe)
    out = []
    for r in pe.resources:
        typ, rid, lang = r['path']
        d = pe.payload(r)
        if typ == 4:
            for loc, it in _walk_menu(menu.parse(d)['items']):
                if JA.search(it['text']):
                    out.append({'kind': 'menu', 'resource': rid, 'language': lang, 'locator': list(loc),
                                'command_id': it.get('id'), 'ja': it['text']})
        elif typ == 5:
            o = parse_dialog(d)
            if 'text' in o['title'] and JA.search(o['title']['text']):
                out.append({'kind': 'dialog_title', 'resource': rid, 'language': lang, 'ja': o['title']['text']})
            for k, it in enumerate(o['items']):
                if 'text' in it['title'] and JA.search(it['title']['text']):
                    out.append({'kind': 'dialog_control', 'resource': rid, 'language': lang, 'item_index': k,
                                'ja': it['title']['text']})
        elif typ == 6:
            for k, s in enumerate(string_block(d)):
                if s and JA.search(s):
                    out.append({'kind': 'string', 'resource': rid, 'language': lang, 'string_id': (rid - 1) * 16 + k,
                                'ja': s})
    for e in out:
        e['source_utf16_sha256'] = sha16(e['ja'])
    return out


def _contract(t: str):
    return (re.findall(r'%[-+ #0-9.]*[a-zA-Z%]', t), t.count('\n'), t.count('\t'), t.count('&') - 2 * t.count('&&'))


def apply(exe: bytes, cat: dict):
    pe = PE(exe)
    raw = {tuple(r['path']): r for r in pe.resources}
    objs = {}

    def get(typ, rid, lang):
        key = (typ, rid, lang)
        if key not in objs:
            objs[key] = {4: menu.parse, 5: parse_dialog, 6: string_block}[typ](pe.payload(raw[key]))
        return objs[key]
    applied, skipped = 0, []
    for e in cat['entries']:
        typ = {'menu': 4, 'string': 6}.get(e['kind'], 5)
        key = (typ, e['resource'], e['language'])
        if key not in raw:
            skipped.append((e.get('string_id') or e['resource'], 'no resource')); continue
        o = get(*key)
        if e['kind'] == 'menu':
            node = {'children': o['items']}
            for i in e['locator']:
                node = node['children'][i]
            holder, k = node, 'text'
        elif e['kind'] == 'string':
            holder, k = o, e['string_id'] % 16
        elif e['kind'] == 'dialog_title':
            holder, k = o['title'], 'text'
        else:
            holder, k = o['items'][e['item_index']]['title'], 'text'
        old = holder[k]
        if sha16(old) != e['source_utf16_sha256']:
            skipped.append((e.get('string_id') or e['resource'], 'source sha mismatch')); continue
        if _contract(old) != _contract(e['translation']):
            skipped.append((e.get('string_id') or e['resource'], 'contract mismatch')); continue
        holder[k] = e['translation']; applied += 1
    font = cat.get('dialog_font')
    if font:
        for (typ, rid, lang), o in objs.items():
            if typ == 5 and 'font' in o and 'text' in o['font'] and JA.search(o['font']['text']) is None \
                    and any(ord(c) > 0x7f for c in o['font']['text']):
                o['font']['text'] = font                     # 日文字型名（ＭＳ ゴシック等）→ 繁中字型
    # 寫回
    out = bytearray(exe)
    secs = pe.sections
    last = max(secs, key=lambda s: s['rp'])
    if last['name'] != '.ld2i' or len(exe) != last['rp'] + last['rs']:
        raise ValueError('.ld2i is not the file tail')
    tail = bytearray()
    tail_rva = last['va'] + last['rs']
    moved = inplace = 0
    for key, o in objs.items():
        r = raw[key]
        new = {4: menu.encode, 5: encode_dialog, 6: encode_string_block}[key[0]](o)
        if new == pe.payload(r):
            continue
        if len(new) <= r['size']:
            out[r['offset']:r['offset'] + r['size']] = new + b'\0' * (r['size'] - len(new))
            struct.pack_into('<I', out, r['entry'] + 4, len(new)); inplace += 1
        else:
            tail += b'\0' * (-len(tail) % 4)
            struct.pack_into('<II', out, r['entry'], tail_rva + len(tail), len(new))
            tail += new; moved += 1
    if tail:
        grow = (len(tail) + 0xfff) & ~0xfff
        out += tail + b'\0' * (grow - len(tail))
        hdr = last['header']
        struct.pack_into('<I', out, hdr + 8, last['rs'] + grow)
        struct.pack_into('<I', out, hdr + 16, last['rs'] + grow)
        salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
        struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + grow + salign - 1) // salign * salign)
    return bytes(out), {'applied': applied, 'skipped': skipped[:20], 'skipped_n': len(skipped),
                        'inplace': inplace, 'moved': moved}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('extract'); a.add_argument('--exe', required=True); a.add_argument('--out', required=True)
    b = sub.add_parser('apply'); b.add_argument('--exe', required=True); b.add_argument('--out', required=True)
    b.add_argument('--catalog', required=True)
    x = ap.parse_args(argv)
    exe = Path(x.exe).read_bytes()
    if x.cmd == 'extract':
        items = extract(exe)
        Path(x.out).write_text(json.dumps(items, ensure_ascii=False, indent=1), 'utf-8')
        print(len(items))
    else:
        if Path(x.exe).resolve() == Path(x.out).resolve():
            print('拒絕覆寫輸入', file=sys.stderr); return 2
        o, info = apply(exe, json.loads(Path(x.catalog).read_text('utf-8')))
        Path(x.out).write_bytes(o); print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
