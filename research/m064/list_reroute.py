r"""m064 lab：把 m063d 啟用版 EXE 的清單填入呼叫點（call rel32）改導到 v4 ListInsert 的另一個入口。

m063 依 catalog_v4.LIST_SITE_CLASS 把 18 個 SendDlgItemMessage 包裝呼叫導向 item 入口或 name 入口
（name 入口帶 NAME_ONLY，不查道具列）。lab 觀察：裝備視窗下拉（道具名）未翻 → 候選點改導 item 入口。
入口位址由已知點讀出（item：商店 0x4aaf19；name：教育 0x4735f6），不寫死。
每點先核對原 call 目標 ∈ {原包裝 0x4ea671, item, name}；只改 rel32。lab only。
  python list_reroute.py --exe in.exe --out out.exe --to item --sites 0x46e73a,0x47db6a,0x46bacb,0x46c46c
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path

BASE = 0x400000
WRAPPER = 0x4ea671
KNOWN = {'item': 0x4aaf19, 'name': 0x4735f6}


def target(exe, va):
    o = va - BASE
    if exe[o] != 0xE8:
        raise ValueError(f'{va:#x}: not a call rel32')
    return va + 5 + struct.unpack_from('<i', exe, o + 1)[0]


def reroute(exe: bytes, sites, to: str):
    entries = {k: target(exe, v) for k, v in KNOWN.items()}
    if entries['item'] == WRAPPER or entries['name'] == WRAPPER or entries['item'] == entries['name']:
        raise ValueError('input is not an enabled v4 image')
    dest = entries[to]
    buf = bytearray(exe); out = []
    for va in sites:
        cur = target(buf, va)
        if cur not in (WRAPPER, entries['item'], entries['name']):
            raise ValueError(f'{va:#x}: unexpected call target {cur:#x}')
        struct.pack_into('<i', buf, va - BASE + 1, dest - (va + 5))
        out.append({'va': hex(va), 'from': hex(cur), 'to': hex(dest)})
    return bytes(buf), {'entries': {k: hex(v) for k, v in entries.items()}, 'sites': out}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--to', choices=('item', 'name'), required=True); ap.add_argument('--sites', required=True)
    x = ap.parse_args(argv)
    if Path(x.exe).resolve() == Path(x.out).resolve():
        print('拒絕覆寫輸入 EXE', file=sys.stderr); return 2
    exe = Path(x.exe).read_bytes()
    out, info = reroute(exe, [int(s, 0) for s in x.sites.split(',')], x.to)
    Path(x.out).write_bytes(out)
    info.update(input_sha256=hashlib.sha256(exe).hexdigest(), output_sha256=hashlib.sha256(out).hexdigest(), lab_only=True)
    print(json.dumps(info, ensure_ascii=False)); return 0


if __name__ == '__main__':
    sys.exit(main())
