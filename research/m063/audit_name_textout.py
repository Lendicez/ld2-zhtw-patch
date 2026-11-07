"""m063a: static COFF audit for name_textout_v3.obj (Linux; never loads, links or runs code).

Port of m062 audit_name_pair_v3.py to the NameTextOut symbol set (same bindings as NamePair v3):
  * undefined == {_LD2_CatalogBytes,_LD2_Catalog,_LD2_ExpectedTextOutA,_LD2_TextOutW} + cookie pair
  * public == @LD2_NameTextOut@24 (fastcall, ret 16) / _LD2N_FindCopy@12 / _LD2N_Wipe@8
  * every public function: `ret N` with N = its stdcall bytes; ESP + EBX/EBP/ESI/EDI preserved on
    every normal CFG path; internal static callees (ld2c3_*, LD2C3_Lookup) walked recursively as
    __cdecl (`ret` 0, caller cleanup)
  * no FS (SEH) use, no std/enter/leave, reloc types only DIR32/REL32, empty .drectve (no DEFAULTLIB)
  * TextOutW = stdcall ret 20 (direct, or via a register loaded from the binding); any other
    register call/tail-jump inside @LD2_NameTextOut@24 = legacy CDC::TextOut (thiscall ret 16)
  * data bindings (_LD2_Catalog*, _LD2_ExpectedTextOutA, cookie) are never call targets
Usage: ~/venv-ld2/bin/python -I -B audit_name_textout.py OBJ [--expect-sha256 H] [--json-out F]
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
import coff_obj  # noqa: E402
from audit_list_obj import FORBIDDEN_UNDEFINED_PREFIXES  # noqa: E402

ENTRY = '@LD2_NameTextOut@24'
PUBLIC = {ENTRY: 16, '_LD2N_FindCopy@12': 12, '_LD2N_Wipe@8': 8}
UNDEFINED = frozenset({'_LD2_CatalogBytes', '_LD2_Catalog', '_LD2_ExpectedTextOutA', '_LD2_TextOutW',
                       '___security_cookie', '@__security_check_cookie@4'})
EXTERNAL_CLEANUP = {'@__security_check_cookie@4': 0, '_LD2_TextOutW': 20}
DATA_ONLY = frozenset({'_LD2_CatalogBytes', '_LD2_Catalog', '_LD2_ExpectedTextOutA', '___security_cookie'})
NONVOL = ('ebx', 'ebp', 'esi', 'edi')


def need(ok, msg):
    if not ok:
        raise SystemExit('AUDIT FAIL: ' + msg)


def audit(raw: bytes) -> dict:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    obj = coff_obj.parse(raw)
    und, pub = set(coff_obj.undefined(obj)), set(coff_obj.defined_external(obj))
    need(und == UNDEFINED, f'undefined={sorted(und)}')
    need(pub == set(PUBLIC), f'public={sorted(pub)}')
    need(not [n for n in und if n.startswith(FORBIDDEN_UNDEFINED_PREFIXES)], 'forbidden CRT/EH symbol')
    drectve = [s['data'].decode('ascii', 'replace') for s in obj['sections'] if s['name'] == '.drectve']
    need(all(not d.strip() for d in drectve), f'non-empty .drectve {drectve!r}')
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    offsets, length = coff_obj.layout(obj)
    image = bytearray(b'\xcc' * length)
    reloc_at, reloc_types = {}, {}
    for s in coff_obj.code_sections(obj):
        base = offsets[s['index']]
        image[base:base + len(s['data'])] = s['data']
        for r in s['rel']:
            reloc_at[base + r['offset']] = r['name']
            reloc_types[r['type']] = reloc_types.get(r['type'], 0) + 1
    need(set(reloc_types) <= {6, 20}, f'reloc types {reloc_types}')
    ins = list(md.disasm(bytes(image), 0))
    by = {i.address: i for i in ins}
    need(all('fs:' not in i.op_str for i in ins), 'FS segment used')
    need(not any(i.mnemonic in ('std', 'enter', 'leave') for i in ins), 'banned mnemonic')
    func_at = {}
    for sym in obj['symbols'].values():
        if sym['kind'] == 0x20 and sym['section'] in offsets:
            func_at[sym['name']] = offsets[sym['section']] + sym['value']
    internal = {n for n in func_at if n not in PUBLIC}
    need(all('@@YA' in n for n in internal), f'non-cdecl internal {sorted(internal)}')
    walked, report, states_total = {}, {}, [0]
    starts, noreturn_tails = set(func_at.values()), []

    def walk(name, depth):
        need(depth <= 6, f'call depth at {name}')
        if name in walked:
            need(walked[name] is not None, f"recursion {name} from {sorted(k for k,v in walked.items() if v is None)}")
            return walked[name]
        walked[name] = None
        want = PUBLIC.get(name, 0)
        initial = {r: r + '_entry' for r in NONVOL}
        todo = [(func_at[name], 0, None, initial, {}, ())]
        seen, normal, calls = set(), [], set()
        while todo:
            a, sp, fp, regs, stack, srcs = todo.pop()
            st = (a, sp, fp, tuple(sorted(regs.items())), tuple(sorted(stack.items())), srcs)
            if st in seen:
                continue
            seen.add(st)
            need(len(seen) < 200000, 'CFG explosion')
            need(a in by, f'{name}: fallthrough into non-instruction {a:#x}')
            i = by[a]
            mn, op, nxt = i.mnemonic, i.op_str, a + i.size
            regs, stack, srcs = dict(regs), dict(stack), dict(srcs)
            dst0 = op.split(', ')[0] if op else ''
            if dst0 in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi') and mn not in ('call', 'push', 'cmp', 'test') and ',' in op:
                srcs.pop(dst0, None)
            rl = next((reloc_at[o] for o in range(a + 1, nxt) if o in reloc_at), None)
            if mn == 'mov' and rl in EXTERNAL_CLEANUP and op.startswith(dst0 + ', dword ptr ['):
                srcs[dst0] = rl
            if mn == 'push':
                sp -= 4
                stack[sp] = regs.get(op, 'temporary')
            elif mn == 'pop':
                if op in regs:
                    regs[op] = stack.get(sp, 'unknown')
                sp += 4
            elif mn == 'sub' and op.startswith('esp, '):
                sp -= int(op.split(', ')[1], 0)
            elif mn == 'add' and op.startswith('esp, '):
                sp += int(op.split(', ')[1], 0)
            elif mn == 'mov' and op == 'ebp, esp':
                fp = sp
                regs['ebp'] = 'frame'
            elif mn == 'mov' and op == 'esp, ebp':
                need(fp is not None, 'esp,ebp without frame')
                sp = fp
            elif mn == 'call':
                target = rl or srcs.get(op) or op
                need(target not in DATA_ONLY, f'call through data binding {target}')
                if target in EXTERNAL_CLEANUP:
                    pop = EXTERNAL_CLEANUP[target]
                elif target in func_at:
                    pop = walk(target, depth + 1)
                elif name == ENTRY and op in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi'):
                    pop = 16                       # legacy CDC::TextOut (thiscall, ret 16)
                    target = 'legacy:' + op
                else:
                    raise SystemExit(f'AUDIT FAIL: {name}: unreviewed call at {a:#x} -> {target}')
                calls.add((target, pop))
                sp += pop
                if target == '@__security_check_cookie@4' and (nxt in starts or nxt not in by or by[nxt].mnemonic in ('nop', 'int3')):
                    # clang rehearsal: cookie-failure block ends in a (noreturn) check call that
                    # abuts the next function; do not fall through into it.
                    noreturn_tails.append(f'{name}:{a:#x}')
                    continue
            elif mn == 'ret':
                got = int(op, 0) if op else 0
                need(got == want, f'{name}: ret {got} want {want}')
                need(sp == 0, f'{name}: ESP mismatch at {a:#x}: {sp}')
                need(regs == initial, f'{name}: nonvolatile mismatch at {a:#x}: {regs}')
                normal.append(hex(a - func_at[name]))
                continue
            elif mn in ('mov', 'lea', 'xor', 'add', 'sub', 'inc', 'dec', 'movzx', 'or', 'and', 'shl', 'shr', 'sar', 'imul', 'neg', 'not', 'movsx', 'cmovne', 'cmove') and dst0 in regs:
                regs[dst0] = 'modified'
            else:
                w = {r for r in NONVOL if r == dst0} if mn not in ('cmp', 'test', 'push', 'jmp') and not mn.startswith('j') else set()
                for r in w:
                    regs[r] = 'modified'
            if mn == 'mov' and op.startswith('dword ptr [ebp - ') and fp is not None:
                try:
                    at = fp - int(op.split('[ebp - ')[1].split(']')[0], 0)
                    if at in stack:
                        stack[at] = 'local_store'
                except ValueError:
                    pass
            tsrcs = tuple(sorted(srcs.items()))
            if mn == 'jmp' and not op.startswith('0x'):
                # tail call into the legacy method: callee pops our 16 stack bytes and returns to our caller
                need(name == ENTRY and op in ('eax', 'ecx', 'edx') and srcs.get(op) is None, f'{name}: indirect jump {op}')
                need(sp == 0 and regs == initial, f'{name}: tail jump with unbalanced frame at {a:#x}')
                calls.add(('legacy-tail:' + op, 16))
                normal.append(hex(a - func_at[name]) + '(tail)')
                continue
            if mn.startswith('j'):
                need(op.startswith('0x'), f'{name}: indirect jump {op}')
                todo.append((int(op, 0), sp, fp, regs, stack, tsrcs))
                if mn == 'jmp':
                    continue
            if nxt in by:
                todo.append((nxt, sp, fp, regs, stack, tsrcs))
        need(normal, f'{name}: no normal return')
        states_total[0] += len(seen)
        report[name] = dict(ret_pop=want, normal_returns=sorted(set(normal)), cfg_states=len(seen),
                            calls=sorted(f'{t} (pop {p})' for t, p in calls))
        walked[name] = want
        return want

    for p in sorted(PUBLIC):
        walk(p, 0)
    ent = report[ENTRY]['calls']
    need(any(c.startswith('legacy') and c.endswith('(pop 16)') for c in ent), 'NameTextOut must reach the legacy method (ret 16)')
    need('_LD2_TextOutW (pop 20)' in ent, 'NameTextOut must call TextOutW (stdcall ret 20)')
    need('_LD2N_FindCopy@12 (pop 12)' in ent, 'NameTextOut must call LD2N_FindCopy')
    return dict(object_sha256=hashlib.sha256(raw).hexdigest(), object_bytes=len(raw), entry=ENTRY,
                undefined=sorted(und), public=sorted(pub), internal_callees_audited=sorted(internal & set(report)),
                functions=report, relocation_counts={str(k): v for k, v in sorted(reloc_types.items())},
                drectve_empty=True, no_fs_seh=True, cookie_noreturn_tails=sorted(set(noreturn_tails)), esp_and_nonvolatile_preserved_on_normal_paths=True,
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



def rehearsal_textout_obj():
    """Linux clang (ziglang) REHEARSAL of native-m063/name_textout_v3.cpp, normalised COFF bytes.
    Not an MSVC object: never pin it as TEXTOUT_OBJECT_SHA256, never package it."""
    import tempfile
    import rehearse_list_obj
    src = Path(__file__).resolve().parents[1] / 'm062/native-m063/name_textout_v3.cpp'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'name_textout_v3.obj'
        rehearse_list_obj.compile_obj(src, p)
        return rehearse_list_obj.normalise(p.read_bytes())


if __name__ == '__main__':
    main()
