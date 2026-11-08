"""m061b: Linux REHEARSAL of the list helper object (clang via `python -m ziglang`).

NOT the production object. MSVC 14.x on Win11 (HANDOFF-COMPILE-M061B Stage A) produces
the only object that may ever be pinned/merged. This script exists so the audit /
ABI rules for profile 'u' are exercised on Linux before asking the user to compile:

  1. compile native-u/list_insert_u.cpp for x86-windows-msvc (clang, -O2, stack protector)
  2. normalise section names to the MSVC shape the strict reader expects
     (.text -> .text$mn; EMPTY .data/.bss without relocations -> .voltbl placeholder;
     anything non-empty is refused)
  3. run audit_list_obj.audit(profile='u') and print a JSON summary

The rehearsal object is written to a temp dir only; never commit or pin it.
Usage: ~/venv-ld2/bin/python -I -B rehearse_list_obj.py [--source FILE] [--profile u|v1]
"""
from __future__ import annotations
import argparse, hashlib, json, struct, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_list_obj, coff_obj  # noqa: E402

FLAGS = ['-target', 'x86-windows-msvc', '-c', '-O2', '-g0', '-fstack-protector-strong', '-fno-exceptions',
         '-fno-rtti', '-ffreestanding', '-fno-addrsig', '-fno-jump-tables', '-fno-optimize-sibling-calls', '-Wall', '-Wextra', '-Werror',
         '-Wno-unused-command-line-argument', '-Wno-unused-function']
SOURCES = {'u': HERE / 'native-u' / 'list_insert_u.cpp', 'v1': HERE / 'native' / 'list_insert_w.cpp'}


def normalise(raw: bytes) -> bytes:
    out = bytearray(raw)
    n = struct.unpack_from('<H', raw, 2)[0]
    for j in range(n):
        at = 20 + j * 40
        name = raw[at:at + 8].rstrip(b'\0')
        size, nrel = struct.unpack_from('<I', raw, at + 16)[0], struct.unpack_from('<H', raw, at + 32)[0]
        if name == b'.text':
            out[at:at + 8] = b'.text$mn'
        elif name in (b'.data', b'.bss'):
            if size or nrel:
                raise SystemExit(f'REHEARSAL REFUSE: non-empty {name!r} (helper must not own data)')
            out[at:at + 8] = b'.voltbl\0'
    return bytes(out)


def compile_obj(src: Path, dst: Path) -> None:
    subprocess.run([sys.executable, '-m', 'ziglang', 'c++', *FLAGS, str(src), '-o', str(dst)], check=True,
                   cwd=str(src.parent))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=sorted(SOURCES), default='u')
    ap.add_argument('--source', type=Path)
    a = ap.parse_args()
    src = a.source or SOURCES[a.profile]
    with tempfile.TemporaryDirectory() as d:
        obj = Path(d) / 'rehearsal.obj'
        compile_obj(src, obj)
        raw = normalise(obj.read_bytes())
    rep = audit_list_obj.audit(raw, a.profile)
    print(json.dumps(dict(
        rehearsal=True, compiler='clang (ziglang, x86-windows-msvc)', production_object=False,
        may_pin=False, profile=a.profile, entry=rep['entry'], undefined=rep['undefined'],
        normal_returns=len(rep['normal_returns']), normal_cfg_states=rep['normal_cfg_states'],
        calls=sorted({c['target'] for c in rep['calls']}),
        esp_and_nonvolatile_preserved_on_normal_paths=rep['esp_and_nonvolatile_preserved_on_normal_paths'],
        rehearsal_sha256=hashlib.sha256(raw).hexdigest(), production_can_apply=False), indent=2))


if __name__ == '__main__':
    main()
