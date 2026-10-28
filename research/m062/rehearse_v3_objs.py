"""m062: Linux REHEARSAL of the two v3 helper objects (clang via `python -m ziglang`).

NOT production objects. Only MSVC on Win11 (HANDOFF-COMPILE-M062 Stage A) may ever produce
objects that get pinned/merged. This exercises, before the user compiles:
  * list_insert_v3.cpp -> full m061b list audit with an added profile 'v3'
    (entry @LD2_ListInsertV3@24, Entries/EntryCount replaced by Catalog/CatalogBytes,
    no memcpy/memset/chkstk/CRT, ret 16 and preserved ESP/non-volatiles on every normal path)
  * name_pair_v3.cpp  -> undefined-symbol set, public symbol set, forbidden imports
The objects live in a temp dir only; never commit or pin them.
Usage: ~/venv-ld2/bin/python -I -B rehearse_v3_objs.py
       ~/venv-ld2/bin/python -I -B rehearse_v3_objs.py --list-obj X.obj --name-obj Y.obj   (audit returned MSVC objects)
"""
from __future__ import annotations
import argparse, hashlib, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
M061 = HERE.parent / 'm061'
sys.path.insert(0, str(M061))
import audit_list_obj, coff_obj, rehearse_list_obj  # noqa: E402

NATIVE = HERE / 'native-v3'
SECURITY = {'___security_cookie', '@__security_check_cookie@4'}
LIST_V3_UNDEFINED = (audit_list_obj.EXPECTED_UNDEFINED_U - {'_LD2_EntryCount', '_LD2_Entries'}) | {'_LD2_CatalogBytes', '_LD2_Catalog'}
NAME_V3_UNDEFINED = frozenset({'_LD2_CatalogBytes', '_LD2_Catalog', '_LD2_ExpectedTextOutA', '_LD2_TextOutW'} | SECURITY)
NAME_V3_PUBLIC = frozenset({'_LD2_NamePair@16', '_LD2_LoadMethod@4', '_LD2_OriginalOne@16', '_LD2_OriginalPair@12',
                            '_LD2_FindCopy@16', '_LD2_Wipe@8'})


def install_profile():
    audit_list_obj.PROFILES['v3'] = ('@LD2_ListInsertV3@24', frozenset(LIST_V3_UNDEFINED), audit_list_obj.CALLEE_CLEANUP_U)
    audit_list_obj.DATA_ONLY = audit_list_obj.DATA_ONLY | {'_LD2_CatalogBytes', '_LD2_Catalog'}


def build(src: Path, d: str) -> bytes:
    obj = Path(d) / (src.stem + '.obj')
    rehearse_list_obj.compile_obj(src, obj)
    return rehearse_list_obj.normalise(obj.read_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--list-obj', type=Path)
    ap.add_argument('--name-obj', type=Path)
    a = ap.parse_args()
    install_profile()
    msvc = bool(a.list_obj and a.name_obj)
    out = dict(rehearsal=not msvc, compiler='MSVC (returned objects)' if msvc else 'clang (ziglang, x86-windows-msvc)',
               production_object=False, may_pin=False, production_can_apply=False)
    if msvc:
        raw_list, raw_name = a.list_obj.read_bytes(), a.name_obj.read_bytes()
    else:
        with tempfile.TemporaryDirectory() as d:
            raw_list = build(NATIVE / 'list_insert_v3.cpp', d)
            raw_name = build(NATIVE / 'name_pair_v3.cpp', d)
    rep = audit_list_obj.audit(raw_list, 'v3')
    out['list_insert_v3'] = dict(entry=rep['entry'], undefined=rep['undefined'], normal_returns=len(rep['normal_returns']),
                                 normal_cfg_states=rep['normal_cfg_states'], calls=sorted({c['target'] for c in rep['calls']}),
                                 esp_and_nonvolatile_preserved_on_normal_paths=rep['esp_and_nonvolatile_preserved_on_normal_paths'],
                                 rehearsal_sha256=hashlib.sha256(raw_list).hexdigest())
    obj = coff_obj.parse(raw_name)
    und, pub = set(coff_obj.undefined(obj)), set(coff_obj.defined_external(obj))
    bad = sorted(n for n in und if n.startswith(audit_list_obj.FORBIDDEN_UNDEFINED_PREFIXES))
    if und != NAME_V3_UNDEFINED or pub != NAME_V3_PUBLIC or bad:
        raise SystemExit(f'REHEARSAL REFUSE name_pair_v3: undefined={sorted(und)} public={sorted(pub)} forbidden={bad}')
    out['name_pair_v3'] = dict(undefined=sorted(und), public=sorted(pub), rehearsal_sha256=hashlib.sha256(raw_name).hexdigest())
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
