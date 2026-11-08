"""m063c: static COFF audit for list_insert_v4.obj (two fastcall entries; Linux, never runs code).

Reuses the m062 v3 list walker (audit_list_obj_v3: capstone CFG walk, EBP spill tracking, ret 16,
ESP + EBX/EBP/ESI/EDI preserved on every normal path, internal static callees walked as __cdecl)
once per entry point. The v3 walker insists on a single public symbol, so this wrapper:
  * first checks the REAL public set == {@LD2_ListInsertV4@24, @LD2_ListInsertNameV4@24}
  * then audits each entry with the walker seeing only that entry as public
  * clang cookie-failure tails (call @__security_check_cookie@4 abutting the next function) end
    a path (walker opt-in COOKIE_NORETURN_TAILS; same rule as m063 audit_name_textout)
  * undefined set == m062 v3 list set (Catalog/CatalogBytes + ListMode + 5 USER32 + 2 cookie)
  * data bindings (_LD2_Catalog*, _LD2_ListMode, cookie) are never call targets
Usage: python3 -I -B audit_list_obj_v4.py OBJ [--expect-sha256 H] [--json-out F]
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
import coff_obj  # noqa: E402
import audit_list_obj_v3 as walker  # noqa: E402

ENTRY_ITEM = '@LD2_ListInsertV4@24'   # item_list + unclassified_list (ALLOW_ANY|ALLOW_JOIN)
ENTRY_NAME = '@LD2_ListInsertNameV4@24'  # name_list (ALLOW_ANY|ALLOW_JOIN|NAME_ONLY)
ENTRIES = (ENTRY_ITEM, ENTRY_NAME)
UNDEFINED = frozenset((walker.EXPECTED_UNDEFINED_U - {'_LD2_EntryCount', '_LD2_Entries'})
                      | {'_LD2_CatalogBytes', '_LD2_Catalog'})
DATA_ONLY = frozenset(walker.DATA_ONLY | {'_LD2_CatalogBytes', '_LD2_Catalog'})


def need(ok, msg):
    if not ok:
        raise SystemExit('AUDIT FAIL: ' + msg)


class _OnePublic:
    """coff_obj proxy: identical except defined_external() reports one entry (already verified)."""
    def __init__(self, entry):
        self.entry = entry

    def __getattr__(self, name):
        return getattr(coff_obj, name)

    def defined_external(self, obj):
        real = coff_obj.defined_external(obj)
        need(set(real) == set(ENTRIES), f'public={sorted(real)}')
        return {self.entry}


def audit(raw: bytes) -> dict:
    obj = coff_obj.parse(raw)
    pub = set(coff_obj.defined_external(obj))
    need(pub == set(ENTRIES), f'public={sorted(pub)} expected={sorted(ENTRIES)}')
    und = set(coff_obj.undefined(obj))
    need(und == UNDEFINED, f'undefined={sorted(und)} expected={sorted(UNDEFINED)}')
    saved = (walker.coff_obj, dict(walker.PROFILES), walker.DATA_ONLY, walker.COOKIE_NORETURN_TAILS)
    per = {}
    try:
        walker.DATA_ONLY = DATA_ONLY
        walker.COOKIE_NORETURN_TAILS = True
        for e in ENTRIES:
            walker.PROFILES['v4'] = (e, UNDEFINED, walker.CALLEE_CLEANUP_U)
            walker.coff_obj = _OnePublic(e)
            r = walker.audit(raw, 'v4')
            per[e] = dict(normal_returns=len(r['normal_returns']), normal_cfg_states=r['normal_cfg_states'],
                          internal_callees_audited=r['internal_callees_audited'],
                          calls=sorted({c['target'] for c in r['calls']}), binding_spills=r['binding_spills'],
                          frame_leas_while_spilled=r['frame_leas_while_spilled'], ret_pop=16,
                          cookie_noreturn_tails=sorted(set(walker.NORETURN_TAILS)),
                          esp_and_nonvolatile_preserved_on_normal_paths=True)
    finally:
        walker.coff_obj, walker.DATA_ONLY, walker.COOKIE_NORETURN_TAILS = saved[0], saved[2], saved[3]
        walker.PROFILES.clear()
        walker.PROFILES.update(saved[1])
    return dict(object_sha256=hashlib.sha256(raw).hexdigest(), object_bytes=len(raw), entries=per,
                undefined=sorted(und), defined_public=sorted(pub), no_default_crt_link=True,
                native_executed=False, linked=False, production_can_apply=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('object', type=Path)
    ap.add_argument('--expect-sha256', default='')
    ap.add_argument('--json-out', type=Path)
    a = ap.parse_args()
    raw = a.object.read_bytes()
    if a.expect_sha256:
        need(hashlib.sha256(raw).hexdigest() == a.expect_sha256.lower(), 'sha256 mismatch')
    text = json.dumps(audit(raw), indent=2, ensure_ascii=True)
    print(text)
    if a.json_out:
        a.json_out.write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
