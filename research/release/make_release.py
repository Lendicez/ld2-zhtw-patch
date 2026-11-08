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


def compile_installer(version: str, payload: Path, out: Path) -> Path:
    parts = (version.split('.') + ['0'] * 4)[:4]
    ver_cs = out / 'Version.cs'
    ver_cs.write_text('namespace LD2ZhTW { static partial class Ver { public const string Assembly = "%s"; } }\n'
                      % '.'.join(parts), 'utf-8')
    exe = out / f'LD2-zhTW-Patch-{version}.exe'
    cmd = [find_csc(), '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+', '/codepage:65001',
           f'/out:{exe}', f'/resource:{payload},payload.bin', '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
           str(HERE / 'installer' / 'LD2ZhTWSetup.cs'), str(ver_cs)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise SystemExit('csc 失敗：\n' + r.stdout[-3000:] + r.stderr[-1000:])
    return exe


def run_cli(exe: Path, verb: str, game: Path):
    # winexe 的 stdout 需經管線才拿得到
    r = subprocess.run([str(exe), verb, str(game)], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=300)
    return r.returncode, r.stdout.strip()


def selftest(exe: Path, pristine: Path, st: Path, files, out: Path):
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
    return ok and refused, log


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pristine', required=True); ap.add_argument('--lab', required=True)
    ap.add_argument('--manual-zh'); ap.add_argument('--version', required=True); ap.add_argument('--out', required=True)
    x = ap.parse_args(argv)
    pristine, lab, out = Path(x.pristine), Path(x.lab), Path(x.out)
    for p in (pristine, lab):
        if out.resolve() == p.resolve() or p.resolve() in out.resolve().parents:
            raise SystemExit('輸出資料夾不可在原版或 lab 資料夾內')
    out.mkdir(parents=True, exist_ok=True)
    st = stage(pristine, lab, Path(x.manual_zh) if x.manual_zh else None, out)
    payload, report = make_delta.build(pristine, st, x.version)
    pp = out / 'payload.bin'; pp.write_bytes(payload)
    meta = make_delta.read_meta(payload)
    exe = compile_installer(x.version, pp, out)
    ok, log = selftest(exe, pristine, st, meta['files'], out)
    rel = {'version': x.version, 'installer': exe.name, 'installer_sha256': sha(exe), 'installer_bytes': exe.stat().st_size,
           'payload_sha256': hashlib.sha256(payload).hexdigest(), 'payload_bytes': len(payload),
           'files': [{k: f[k] for k in ('path', 'src_sha256', 'src_size', 'dst_sha256', 'dst_size')} for f in meta['files']],
           'literal_report': report, 'selftest_ok': ok, 'selftest': log}
    (out / 'release.json').write_text(json.dumps(rel, ensure_ascii=False, indent=1), 'utf-8')
    print(json.dumps({k: rel[k] for k in ('version', 'installer', 'installer_sha256', 'installer_bytes', 'payload_bytes',
                                          'selftest_ok')} | {'files': len(rel['files'])}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
