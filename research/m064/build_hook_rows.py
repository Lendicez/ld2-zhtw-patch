r"""m064 lab：由 runtime ANSI catalog 產生 v4 hook 用 FULL_ANY 列（catalog_patch.py 的 --rows 輸入）。

每列輸出兩把鍵：原文槽 CP932 位元組（讀自 --exe）與新 Big5 位元組（text_cp950_hex），值皆為 text_zh_tw。
  python build_hook_rows.py --exe pristine\Ld95.exe --catalog research\translations\m063-draft*.json --subcategory place_ui --out rows.json
"""
import argparse, glob, json, sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--catalog', action='append', required=True)
    ap.add_argument('--subcategory', action='append', required=True)
    ap.add_argument('--strip', action='store_true', help='同時加入去除前後空白的鍵／值')
    ap.add_argument('--out', required=True)
    x = ap.parse_args(argv)
    exe = Path(x.exe).read_bytes()
    rows, seen = [], set()

    def add(key, zh):
        if key and (key, zh) not in seen:
            seen.add((key, zh))
            rows.append({'ansi_hex': key.hex(), 'zh': zh})
    for pat in x.catalog:
        for f in sorted(glob.glob(pat)):
            for it in json.loads(Path(f).read_text('utf-8-sig')).get('items', []):
                if it.get('subcategory') not in x.subcategory:
                    continue
                off, n = int(it['file_offset']), int(it['source_bytes_len'])
                src = exe[off:off + n].split(b'\0', 1)[0]
                zh = it['text_zh_tw']
                big5 = bytes.fromhex(it['text_cp950_hex'])
                add(src, zh)
                add(big5, zh)
                if x.strip:
                    add(src.strip(b' '), zh.strip())
                    add(big5.strip(b' '), zh.strip())
    Path(x.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), 'utf-8')
    print(len(rows), 'rows')
    return 0


if __name__ == '__main__':
    sys.exit(main())
