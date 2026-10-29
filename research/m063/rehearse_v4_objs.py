"""m063c: Linux REHEARSAL of the three v4 helper objects (clang via `python -m ziglang`).

NOT production objects. Only MSVC on Win11 (future m063b compile, needs user consent) may ever
produce objects that get pinned/merged. Objects live in a temp dir only; never commit or pin them.
  * native-v4/list_insert_v4.cpp  -> audit_list_obj_v4 (both entries walked)
  * native-v4/name_textout_v4.cpp -> m063 audit_name_textout (same public/undefined set as v3)
  * native-v4/name_pair_v4.cpp    -> symbol sets (rehearsal) / m062 audit_name_pair_v3 full CFG (MSVC objects)
v3 and v4 objects share symbol names on purpose; they are told apart by sha256 pins and by the
blob version each refuses (v3 helpers refuse v4 blobs and vice versa).
Usage: python -I -B rehearse_v4_objs.py
       python -I -B rehearse_v4_objs.py --list-obj L.obj --textout-obj T.obj --name-obj N.obj  (audit returned MSVC objects)
"""
from __future__ import annotations
import argparse, hashlib, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import coff_obj, rehearse_list_obj  # noqa: E402
import audit_list_obj_v4, audit_name_textout, audit_name_pair_v3  # noqa: E402

NATIVE = HERE / 'native-v4'
# Pins stay None until a consented Win11 MSVC compile (m063b) returns objects that pass these audits.
LIST_V4_OBJECT_SHA256 = None
TEXTOUT_V4_OBJECT_SHA256 = None
NAME_V4_OBJECT_SHA256 = None


def build(src: Path, d: str) -> bytes:
    obj = Path(d) / (src.stem + '.obj')
    rehearse_list_obj.compile_obj(src, obj)
    return rehearse_list_obj.normalise(obj.read_bytes())


def rehearse(objs=None) -> dict:
    msvc = objs is not None
    if not msvc:
        with tempfile.TemporaryDirectory() as d:
            objs = {k: build(NATIVE / f'{k}.cpp', d) for k in ('list_insert_v4', 'name_textout_v4', 'name_pair_v4')}
    out = dict(rehearsal=not msvc, compiler='MSVC (returned objects)' if msvc else 'clang (ziglang, x86-windows-msvc)',
               production_object=False, may_pin=False, production_can_apply=False)
    rl = audit_list_obj_v4.audit(objs['list_insert_v4'])
    out['list_insert_v4'] = dict(entries=rl['entries'], undefined=rl['undefined'], public=rl['defined_public'],
                                 rehearsal_sha256=rl['object_sha256'])
    rt = audit_name_textout.audit(objs['name_textout_v4'])
    out['name_textout_v4'] = dict(public=sorted(audit_name_textout.PUBLIC), undefined=sorted(audit_name_textout.UNDEFINED),
                                  audit='full_cfg_audit', rehearsal_sha256=hashlib.sha256(objs['name_textout_v4']).hexdigest())
    raw = objs['name_pair_v4']
    if msvc:
        audit_name_pair_v3.audit(raw)  # full CFG audit (same rule set the pinned m062 v3 object passed)
        depth = 'full_cfg_audit'
    else:
        # clang inlines OriginalOne's legacy `call eax` into NamePair, which the MSVC-shaped v3 audit
        # (rightly) refuses outside OriginalOne; the m062 rehearsal likewise only checks symbol sets.
        obj = coff_obj.parse(raw)
        und, pub = set(coff_obj.undefined(obj)), set(coff_obj.defined_external(obj))
        bad = sorted(n for n in und if n.startswith(audit_list_obj_v4.walker.FORBIDDEN_UNDEFINED_PREFIXES))
        if und != set(audit_name_pair_v3.UNDEFINED) or pub != set(audit_name_pair_v3.PUBLIC) or bad:
            raise SystemExit(f'REHEARSAL REFUSE name_pair_v4: undefined={sorted(und)} public={sorted(pub)} forbidden={bad}')
        depth = 'symbol_sets_only (full CFG audit runs on the MSVC object)'
    out['name_pair_v4'] = dict(public=sorted(audit_name_pair_v3.PUBLIC), undefined=sorted(audit_name_pair_v3.UNDEFINED),
                               audit=depth, rehearsal_sha256=hashlib.sha256(raw).hexdigest())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--list-obj', type=Path)
    ap.add_argument('--textout-obj', type=Path)
    ap.add_argument('--name-obj', type=Path)
    a = ap.parse_args()
    given = [a.list_obj, a.textout_obj, a.name_obj]
    if any(given) and not all(given):
        raise SystemExit('give all three objects or none')
    objs = None
    if all(given):
        objs = dict(list_insert_v4=a.list_obj.read_bytes(), name_textout_v4=a.textout_obj.read_bytes(),
                    name_pair_v4=a.name_obj.read_bytes())
    print(json.dumps(rehearse(objs), indent=2))


if __name__ == '__main__':
    main()
