r"""發行組裝（Windows 本機執行）：lab 建置結果 → 差分 payload → 以內建 csc.exe 編譯安裝程式 → 自我測試。

  python make_release.py --pristine <原版遊戲根> --lab <lab 遊戲根> --manual-zh <說明書譯本資料夾>
                         --version 1.0.0 --out <發行輸出資料夾>

步驟：
1. 暫存區 = lab 與原版不同的檔案（Usr 除外）＋說明書譯本（`マニュアル\*.html`、`_index_root.html`→`index.html`）。
2. make_delta.build（原版 → 暫存區）產生 payload.bin（只含差異）。
3. 產生 Version.cs，csc 編譯 `LD2-zhTW-Patch-<版號>.exe`（內嵌 payload）。
4. 自我測試：把 payload 涉及的原版檔複製到 selftest\game，依序 /status → /install（核對每檔 = 暫存區）
   → /install（應不重複）→ /uninstall（核對每檔 = 原版）。
5. release.json：版號、安裝程式 sha256、每檔來源／目標 sha256、自我測試結果。
另：「免系統管理員權限啟動」模式＝Ld95.exe 的 RT_MANIFEST 內 level="requireAdministrator" 等長改為
level="asInvoker"（後補空白）。位置依 PE 資源結構求出，寫入內嵌的 variants.json；自我測試涵蓋兩種模式。
不寫入原版或 lab 資料夾。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_delta  # noqa: E402

MANUAL_DIR = 'マニュアル'
MODE_EXE = 'Ld95.exe'
MAN_ADMIN = b'level="requireAdministrator"'
MAN_INVOKER = b'level="asInvoker"'.ljust(len(MAN_ADMIN), b' ')


def _u16(b, o): return int.from_bytes(b[o:o + 2], 'little')
def _u32(b, o): return int.from_bytes(b[o:o + 4], 'little')


def manifest_ranges(exe: bytes):
    """RT_MANIFEST（類型 24）各資料項在檔案中的 (offset, size)，依 PE 資源目錄求出。"""
    pe = _u32(exe, 0x3C)
    if exe[pe:pe + 4] != b'PE\0\0':
        raise ValueError('不是 PE 檔')
    nsec, opt_size = _u16(exe, pe + 6), _u16(exe, pe + 20)
    opt = pe + 24
    if _u16(exe, opt) != 0x10B:
        raise ValueError('只支援 32 位元 PE')
    rsrc_rva = _u32(exe, opt + 96 + 2 * 8)
    secs = []
    for i in range(nsec):
        o = opt + opt_size + 40 * i
        secs.append((_u32(exe, o + 12), max(_u32(exe, o + 8), _u32(exe, o + 16)), _u32(exe, o + 20)))

    def off(rva):
        for va, vs, raw in secs:
            if va <= rva < va + vs:
                return raw + rva - va
        raise ValueError('RVA 不在任何區段')
    base = off(rsrc_rva)

    def entries(d):
        n = _u16(exe, base + d + 12) + _u16(exe, base + d + 14)
        for i in range(n):
            e = base + d + 16 + 8 * i
            yield _u32(exe, e), _u32(exe, e + 4)
    out = []
    for tid, tptr in entries(0):
        if tid != 24 or not tptr & 0x80000000:
            continue
        for _, nptr in entries(tptr & 0x7FFFFFFF):
            for _, lptr in (entries(nptr & 0x7FFFFFFF) if nptr & 0x80000000 else [(0, nptr)]):
                de = base + (lptr & 0x7FFFFFFF)
                out.append((off(_u32(exe, de)), _u32(exe, de + 4)))
    return out


def mode_variant(exe: bytes):
    """(offset, 免系統管理員模式內容)。manifest 內 requireAdministrator 必須剛好一次。"""
    hits = []
    for o, n in manifest_ranges(exe):
        blob = exe[o:o + n]
        i = blob.find(MAN_ADMIN)
        while i >= 0:
            hits.append(o + i); i = blob.find(MAN_ADMIN, i + 1)
    if len(hits) != 1:
        raise SystemExit(f'manifest 內 requireAdministrator 應剛好一處，實際 {len(hits)}')
    b = bytearray(exe); b[hits[0]:hits[0] + len(MAN_ADMIN)] = MAN_INVOKER
    return hits[0], bytes(b)


def write_variants(st: Path, previous, out: Path) -> tuple[Path, str]:
    exe = (st / MODE_EXE).read_bytes()
    o, alt = mode_variant(exe)
    old = {}
    for pv in previous:
        for f in pv.get('files', []):
            if f.get('path') == MODE_EXE and f.get('noadmin_dst_sha256'):
                old[f['noadmin_dst_sha256']] = pv['version']
    alt_sha = hashlib.sha256(alt).hexdigest()
    doc = {'path': MODE_EXE, 'offset': o, 'admin': MAN_ADMIN.decode(), 'invoker': MAN_INVOKER.decode(),
           'noadmin_dst_sha256': alt_sha, 'old_noadmin': old}
    p = out / 'variants.json'; p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), 'utf-8')
    return p, alt_sha


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stage(pristine: Path, lab: Path, manual: Path | None, out: Path) -> Path:
    st = out / 'staging'
    if st.exists():
        raise SystemExit(f'暫存區已存在，請換新的輸出資料夾：{st}')
    for rel in make_delta.changed_files(pristine, lab):
        d = st / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(lab / rel, d)
    if manual:
        for f in sorted(manual.glob('*.html')):
            name = 'index.html' if f.name == '_index_root.html' else f'{MANUAL_DIR}/{f.name}'
            if not (pristine / name).exists():
                raise SystemExit(f'說明書譯本沒有對應原檔：{name}')
            d = st / name; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, d)
    return st


def find_csc() -> str:
    c = sorted(glob.glob(r'C:\Windows\Microsoft.NET\Framework64\v4*\csc.exe')) or \
        sorted(glob.glob(r'C:\Windows\Microsoft.NET\Framework\v4*\csc.exe'))
    if not c:
        raise SystemExit('找不到 .NET Framework 4 csc.exe')
    return c[-1]


def compile_installer(version: str, payload: Path, out: Path, variants: Path | None = None) -> Path:
    parts = (version.split('.') + ['0'] * 4)[:4]
    ver_cs = out / 'Version.cs'
    ver_cs.write_text('namespace LD2ZhTW { static partial class Ver { public const string Assembly = "%s"; } }\n'
                      % '.'.join(parts), 'utf-8')
    exe = out / f'LD2-zhTW-Patch-{version}.exe'
    cmd = [find_csc(), '/nologo', '/target:winexe', '/platform:x86', '/optimize+', '/codepage:65001',
           f'/out:{exe}', f'/resource:{payload},payload.bin'] + ([f'/resource:{variants},variants.json'] if variants else []) + [
           '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
           str(HERE / 'installer' / 'LD2ZhTWSetup.cs'), str(ver_cs)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise SystemExit('csc 失敗：\n' + r.stdout[-3000:] + r.stderr[-1000:])
    return exe


def run_cli(exe: Path, verb: str, game: Path, *extra: str):
    # winexe 的 stdout 需經管線才拿得到
    r = subprocess.run([str(exe), verb, str(game), *extra], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=300)
    return r.returncode, r.stdout.strip()


def selftest(exe: Path, pristine: Path, st: Path, files, out: Path, alt_sha: str | None = None):
    game = out / 'selftest' / 'game'
    if game.exists():
        raise SystemExit(f'自我測試資料夾已存在：{game}')
    for f in files:
        d = game / f['path']; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(pristine / f['path'], d)
    log = []

    def check(label, want):
        bad = [f['path'] for f in files if sha(game / f['path']) != f[want]]
        log.append({'step': label, 'mismatch': bad[:10], 'mismatch_n': len(bad)})
        return not bad
    ok = True
    for verb, want in (('/status', 'src_sha256'), ('/install', 'dst_sha256'), ('/install', 'dst_sha256'),
                       ('/uninstall', 'src_sha256')):
        rc, text = run_cli(exe, verb, game)
        log.append({'verb': verb, 'rc': rc, 'out': text[-400:]})
        ok = ok and rc == 0 and check(verb, want)
    # 未知版本：改 1 byte 後應拒絕且不寫入
    t = game / files[0]['path']; b = bytearray(t.read_bytes()); b[0] ^= 0xFF; t.write_bytes(bytes(b))
    before = sha(t)
    rc, text = run_cli(exe, '/install', game)
    refused = rc != 0 and sha(t) == before and all(
        sha(game / f['path']) == f['src_sha256'] for f in files[1:])
    log.append({'verb': '/install (unknown version)', 'rc': rc, 'refused_without_writes': refused, 'out': text[-200:]})
    b[0] ^= 0xFF; t.write_bytes(bytes(b))
    if alt_sha:   # 免系統管理員模式：安裝 → 切換 → 再安裝（維持模式）→ 解除安裝
        want = {f['path']: f['dst_sha256'] for f in files}
        alt = dict(want); alt[MODE_EXE] = alt_sha
        steps = ((('/install', '/noadmin'), alt, 'mode=noadmin'), (('/setmode', 'admin'), want, 'mode=admin'),
                 (('/setmode', 'noadmin'), alt, 'mode=noadmin'), (('/install',), alt, 'mode=noadmin'),
                 (('/install', '/admin'), want, 'mode=admin'), (('/setmode', 'noadmin'), alt, 'mode=noadmin'),
                 (('/uninstall',), {f['path']: f['src_sha256'] for f in files}, 'mode=-'))
        for args, exp, mode in steps:
            rc, text = run_cli(exe, args[0], game, *args[1:])
            bad = [p for p, h in exp.items() if sha(game / p) != h]
            good = rc == 0 and not bad and mode in text
            log.append({'verb': ' '.join(args) + ' (mode)', 'rc': rc, 'ok': good, 'mismatch': bad[:5], 'out': text[-200:]})
            ok = ok and good
    return ok and refused, log


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pristine', required=True); ap.add_argument('--lab', required=True)
    ap.add_argument('--manual-zh'); ap.add_argument('--version', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--fulltest', action='store_true', help='另建完整原版副本並以安裝程式安裝（供回歸）')
    ap.add_argument('--previous', nargs='*', default=[], help='可直接升級的舊版 release.json（含每檔 src／dst sha256）')
    ap.add_argument('--upgrade-from', help='已安裝舊版的遊戲資料夾（含 _zhTW_backup），用來測試直接升級')
    x = ap.parse_args(argv)
    pristine, lab, out = Path(x.pristine), Path(x.lab), Path(x.out)
    for p in (pristine, lab):
        if out.resolve() == p.resolve() or p.resolve() in out.resolve().parents:
            raise SystemExit('輸出資料夾不可在原版或 lab 資料夾內')
    out.mkdir(parents=True, exist_ok=True)
    st = stage(pristine, lab, Path(x.manual_zh) if x.manual_zh else None, out)
    previous = [json.loads(Path(pv).read_text('utf-8')) for pv in x.previous]
    payload, report = make_delta.build(pristine, st, x.version, previous)
    pp = out / 'payload.bin'; pp.write_bytes(payload)
    meta = make_delta.read_meta(payload)
    variants, alt_sha = write_variants(st, previous, out)
    exe = compile_installer(x.version, pp, out, variants)
    ok, log = selftest(exe, pristine, st, meta['files'], out, alt_sha)
    if ok and x.upgrade_from:   # 舊版 → 本版直接升級 → 解除安裝
        up = out / 'selftest' / 'upgrade'
        src_dir = Path(x.upgrade_from)
        paths = {f['path'] for f in meta['files']} | {f['path'] for pv in meta.get('previous', []) for f in pv['files']}
        for rel in paths:
            if (src_dir / rel).exists():
                d = up / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src_dir / rel, d)
        shutil.copytree(src_dir / '_zhTW_backup', up / '_zhTW_backup')
        for verb in ('/status', '/install', '/install', '/uninstall'):
            rc, text = run_cli(exe, verb, up)
            log.append({'verb': 'upgrade ' + verb, 'rc': rc, 'out': text[-160:]})
            if rc:
                ok = False
            if verb == '/status':
                ok = ok and ' older=0 ' not in text
            elif verb == '/install':
                ok = ok and all(sha(up / f['path']) == f['dst_sha256'] for f in meta['files'])
            else:
                ok = ok and all(sha(up / f['path']) == f['src_sha256'] for f in meta['files'])
    if ok and x.fulltest:   # 完整原版副本 → 安裝程式安裝 → 供 harness 回歸（實際出貨內容的端對端驗證）
        full = out / 'fulltest' / 'game'
        shutil.copytree(pristine, full)
        rc, text = run_cli(exe, '/install', full)
        log.append({'verb': 'fulltest /install', 'rc': rc, 'out': text[-200:], 'game': str(full)})
        ok = rc == 0 and all(sha(full / f['path']) == f['dst_sha256'] for f in meta['files'])
    rel = {'version': x.version, 'installer': exe.name, 'installer_sha256': sha(exe), 'installer_bytes': exe.stat().st_size,
           'payload_sha256': hashlib.sha256(payload).hexdigest(), 'payload_bytes': len(payload),
           'files': [{k: f[k] for k in ('path', 'src_sha256', 'src_size', 'dst_sha256', 'dst_size')} |
                     ({'noadmin_dst_sha256': alt_sha} if f['path'] == MODE_EXE else {}) for f in meta['files']],
           'literal_report': report, 'selftest_ok': ok, 'selftest': log}
    (out / 'release.json').write_text(json.dumps(rel, ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps({k: rel[k] for k in ('version', 'installer', 'installer_sha256', 'installer_bytes', 'payload_bytes',
                                          'selftest_ok')} | {'files': len(rel['files'])}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
