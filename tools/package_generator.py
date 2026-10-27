"""Build an unelevated Windows generator; never execute it or its outputs."""
import argparse
import importlib.metadata
import json
import os
import re
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BUDGET = 1_000_000_000


def usage(root):
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack-root', type=Path, required=True, help='Dedicated existing environment/cache/build/dist/temp root')
    parser.add_argument('--build-tag', default='', help='New version subdirectory, e.g. m031')
    parser.add_argument('--mode', choices=['onedir', 'onefile'], required=True)
    args = parser.parse_args()
    root = args.pack_root
    if not root.is_absolute() or '..' in root.parts or root.is_symlink():
        raise ValueError('Explicit dedicated absolute packaging root required')
    root = root.resolve(strict=True)
    if os.name != 'nt' or sys.version_info[:2] != (3, 14) or struct.calcsize('P') != 8:
        raise ValueError('Pinned build requires existing Windows CPython 3.14 x64')
    if Path(sys.prefix).resolve() != root / 'venv':
        raise ValueError('Use the dedicated packaging venv')
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('Do not build or run this generator as administrator')
    dependencies = json.loads((ROOT / 'packaging/dependency-sources.json').read_text())
    for item in dependencies['packages']:
        if importlib.metadata.version(item['name']) != item['version']:
            raise ValueError('Installed package differs from lock: ' + item['name'])
    if usage(root) + 350_000_000 >= BUDGET:
        raise ValueError('Insufficient remaining 1 GB build budget; stop for review')
    if args.build_tag and not re.fullmatch('[a-z0-9-]{1,32}', args.build_tag):
        raise ValueError('Invalid build tag')
    work, dist = root / 'build' / args.build_tag / args.mode, root / 'dist' / args.build_tag / args.mode
    if work.exists() or dist.exists():
        raise ValueError('Fresh work/dist paths required; existing builds are preserved')
    env = dict(os.environ)
    env.update(TEMP=str(root / 'temp'), TMP=str(root / 'temp'),
               PYINSTALLER_CONFIG_DIR=str(root / 'cache'), LD2_BUNDLE_MODE=args.mode,
               PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    command = [sys.executable, '-I', '-B', '-m', 'PyInstaller', '--noconfirm',
               '--distpath', str(dist), '--workpath', str(work), str(ROOT / 'packaging/generator.spec')]
    log = root / 'evidence' / ((args.build_tag + '-' if args.build_tag else '') + args.mode + '-build.log')
    with log.open('xb') as output:
        process = subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT)
        peak = usage(root)
        while process.poll() is None:
            peak = max(peak, usage(root))
            if peak > BUDGET - 50_000_000:
                # Only this child builder is stopped; existing work is retained.
                process.terminate()
                process.wait()
                raise RuntimeError('Packaging approached budget limit; stopped with files retained')
            time.sleep(1)
    if process.returncode:
        raise RuntimeError(f'Build failed ({process.returncode}); inspect retained log: {log}')
    print(json.dumps({'mode': args.mode, 'build_exit': process.returncode,
                      'bytes': usage(root), 'sampled_peak_bytes': peak, 'budget_bytes': BUDGET,
                      'executable_run': False, 'log': str(log)}))


if __name__ == '__main__':
    main()
