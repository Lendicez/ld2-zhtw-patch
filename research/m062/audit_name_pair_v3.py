"""m062: static COFF audit for MSVC name_pair_v3.obj (Linux; never loads, links or runs code).

Ports the m056 name_pair audit to the v3 symbol set:
  * undefined == {_LD2_CatalogBytes,_LD2_Catalog,_LD2_ExpectedTextOutA,_LD2_TextOutW} + cookie pair
  * public == NamePair@16 / LoadMethod@4 / OriginalOne@16 / OriginalPair@12 / FindCopy@16 / Wipe@8
  * every public function: `ret N` with N = its stdcall bytes; ESP + EBX/EBP/ESI/EDI preserved on
    every normal CFG path; internal static callees (ld2c3_*, LD2C3_Lookup) walked recursively as
    __cdecl (`ret` 0, caller cleanup)
  * no FS (SEH) use, no std/enter/leave, reloc types only DIR32/REL32, empty .drectve (no DEFAULTLIB)
  * TextOutW = stdcall ret 20; OriginalOne's `call eax` = legacy virtual method ret 16
  * data bindings (_LD2_Catalog*, _LD2_ExpectedTextOutA, cookie) are never call targets
Usage: ~/venv-ld2/bin/python -I -B audit_name_pair_v3.py OBJ [--expect-sha256 H] [--json-out F]
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
import coff_obj  # noqa: E402
from audit_list_obj import FORBIDDEN_UNDEFINED_PREFIXES  # noqa: E402

PUBLIC = {'_LD2_NamePair@16': 16, '_LD2_LoadMethod@4': 4, '_LD2_OriginalOne@16': 16,
          '_LD2_OriginalPair@12': 12, '_LD2_FindCopy@16': 16, '_LD2_Wipe@8': 8}
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

    def walk(name, depth):
        need(depth <= 6, f'call depth at {name}')
        if name in walked:
            need(walked[name] is not None, f'recursion {name}')
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
                rr = next((reloc_at[o] for o in range(a + 1, nxt) if o in reloc_at), None)
                target = rr or op
                need(target not in DATA_ONLY, f'call through data binding {target}')
                if target in EXTERNAL_CLEANUP:
                    pop = EXTERNAL_CLEANUP[target]
                elif target in func_at:
                    pop = walk(target, depth + 1)
                elif name == '_LD2_OriginalOne@16' and op == 'eax':
                    pop = 16
                else:
                    raise SystemExit(f'AUDIT FAIL: {name}: unreviewed call at {a:#x} -> {target}')
                calls.add((target, pop))
                sp += pop
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
    one = report['_LD2_OriginalOne@16']['calls']
    need('eax (pop 16)' in one, 'OriginalOne must call the legacy method via eax, ret 16')
    pair = report['_LD2_OriginalPair@12']['calls']
    need(pair == ['_LD2_OriginalOne@16 (pop 16)'], f'OriginalPair calls {pair}')
    return dict(object_sha256=hashlib.sha256(raw).hexdigest(), object_bytes=len(raw), entry='_LD2_NamePair@16',
                undefined=sorted(und), public=sorted(pub), internal_callees_audited=sorted(internal & set(report)),
                functions=report, relocation_counts={str(k): v for k, v in sorted(reloc_types.items())},
                drectve_empty=True, no_fs_seh=True, esp_and_nonvolatile_preserved_on_normal_paths=True,
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
