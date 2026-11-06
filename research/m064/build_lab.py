r"""m064 lab：一次建出完整 lab EXE＋圖檔（6 步）。只寫 --lab 目錄的遊戲副本；production_can_apply=false。

  python build_lab.py --enabled <m063d 啟用版 Ld95.exe> --pristine <pristine 遊戲根> --lab <lab 遊戲根>
                      --apply-images <apply_images.py> --img-dirs out_zh out_zh_bmh out_zh_maps [--work <暫存目錄>]

1 rdata_ansi（m063 draft*＋lab-extra-*＋lab-places）  2 charset_patch  3 list_reroute（裝備下拉→item）
4 catalog_patch（hook-rows-equip）  5 tab_title_patch  5b detail_name_patch（詳情視窗稱號＋名字）  5c cdc_textout_patch（CDC::TextOut 含 CP932 lead 0x81–0x9F → catalog 查表或日文 TextOutW；取代 nto_fallback_patch）
→ 寫 lab\Ld95.exe  6 apply_images（RES＋EXE RT_BITMAP）
"""
import argparse, glob, hashlib, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import rdata_ansi, charset_patch, list_reroute, catalog_patch, tab_title_patch  # noqa: E402
import detail_name_patch, gen_lab_detail, cdc_textout_patch, savelist_patch  # noqa: E402

EQUIP_SITES = [0x46e73a, 0x47db6a, 0x46bacb, 0x46c46c]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--enabled', required=True); ap.add_argument('--pristine', required=True)
    ap.add_argument('--lab', required=True); ap.add_argument('--apply-images')
    ap.add_argument('--img-dirs', nargs='*', default=[]); ap.add_argument('--manifest')
    ap.add_argument('--tab-debug', action='store_true', help='tab_title_patch 偵錯版（.ld2i 紀錄）')
    ap.add_argument('--charset-only', help='只修補這些 LOGFONT 點（逗號分隔檔案偏移，如 0x31dbe）')
    x = ap.parse_args(argv)
    lab = Path(x.lab)
    if 'pristine' in str(lab).lower() or 'baseline' in str(lab).lower():
        print('refuse: lab path looks like baseline', file=sys.stderr); return 2
    exe = Path(x.enabled).read_bytes(); log = {'enabled_sha256': hashlib.sha256(exe).hexdigest()}
    epi_pairs = gen_lab_detail.epithet_pairs(exe)   # 必須在 rdata 套用前，由原文 .rdata 取得
    place_rows = savelist_patch.place_rows(exe, json.loads((HERE / 'lab-places.zh-TW.json').read_text('utf-8'))['items'])
    cats = [str(ROOT / 'research/translations/m063-draft*.json'), str(HERE / 'lab-extra-*.json'), str(HERE / 'lab-places.zh-TW.json'), str(HERE / 'lab-detail.zh-TW.json'), str(ROOT / 'research/translations/m064-tx-*.json')]
    p = rdata_ansi.plan(exe, rdata_ansi.load_items(cats))
    if p['skipped']:
        print(json.dumps([r for r in p['rows'] if not r['ok']], default=str)[:2000], file=sys.stderr); return 3
    exe = rdata_ansi.apply(exe, p); log['rdata_rows'] = p['ok']
    only = {int(v, 0) for v in x.charset_only.split(',')} if x.charset_only else None
    exe, log['charset'] = charset_patch.patch(exe, only)
    exe, info = list_reroute.reroute(exe, EQUIP_SITES, 'item'); log['reroute'] = info['sites']
    exe, log['catalog'] = catalog_patch.patch(exe, catalog_patch.load_rows(HERE / 'hook-rows-equip.json') + place_rows)
    exe, info = tab_title_patch.patch(exe, debug=x.tab_debug); log['tab_sites'] = info['sites']; log['norm'] = info.get('norm')
    exe, log['detail_name'] = detail_name_patch.patch(exe, epi_pairs)
    exe, log['cdc_textout'] = cdc_textout_patch.patch(exe)
    exe, log['savelist'] = savelist_patch.patch(exe)
    (lab / 'Ld95.exe').write_bytes(exe); log['pre_image_sha256'] = hashlib.sha256(exe).hexdigest()
    if x.apply_images:
        r = subprocess.run([sys.executable, x.apply_images, x.pristine, str(lab)] + x.img_dirs,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        log['images'] = r.stdout.strip()[-600:]
        if r.returncode:
            print(r.stderr[-1500:], file=sys.stderr); return 4
    log['final_sha256'] = hashlib.sha256((lab / 'Ld95.exe').read_bytes()).hexdigest()
    log.update(lab_only=True, production_can_apply=False, release_approved=False)
    text = json.dumps(log, ensure_ascii=False, indent=1, default=str)
    if x.manifest:
        Path(x.manifest).write_text(text, 'utf-8')
    print(text); return 0


if __name__ == '__main__':
    sys.exit(main())
