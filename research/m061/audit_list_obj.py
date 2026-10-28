"""m061: static COFF audit for list_insert_w.obj (Linux; never loads or runs code).

Pins the undefined-symbol set (5 helper bindings + 2 security-cookie symbols),
rejects any other CRT / heap / EH / chkstk symbol, checks that the sole public
entry `_LD2_ListInsert@24` returns with `ret 16` on every normal CFG path, and
that ESP and non-volatiles are preserved. Capstone CFG walk; no native execution.

Usage: python3 -I -B audit_list_obj.py path/to/list_insert_w.obj
Requires: pinned object sha256 via --expect-sha256 once a Windows compile is in.
Until then the script still audits whatever object is given and prints its hash.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coff_obj  # noqa: E402

ENTRY = '_LD2_ListInsert@24'
EXPECTED_UNDEFINED = frozenset([
    '_LD2_EntryCount',
    '_LD2_Entries',
    '_LD2_OriginalDlgItem',
    '_LD2_SendDlgItemMessageW',
    '_LD2_MultiByteToWideChar',
    '___security_cookie',
    '@__security_check_cookie@4',
])
FORBIDDEN_UNDEFINED_PREFIXES = (
    '_memcpy', '_memset', '_memmove', '_chkstk', '__chkstk', '_alloca',
    '__Cxx', '___Cxx', '__EH', '___EH', '_malloc', '_free', '_realloc',
    '_operator', '??2', '??3', '__imp_', '_printf', '_sprintf', '_strlen',
    '_strcpy', '_strcat', '_wcscpy', '_wcslen',
)
CALLEE_CLEANUP = {
    '@__security_check_cookie@4': 0,          # fastcall, ret 0
    '_LD2_SendDlgItemMessageW': 20,           # stdcall 5 args
    '_LD2_MultiByteToWideChar': 24,           # stdcall 6 args
    '_LD2_OriginalDlgItem': 16,               # fastcall + 4 stack DWORDs, ret 16
}


def need(ok, msg):
    if not ok:
        raise SystemExit('AUDIT FAIL: ' + msg)


def audit(raw: bytes) -> dict:
    obj = coff_obj.parse(raw)
    undefined = coff_obj.undefined(obj)
    need(undefined == EXPECTED_UNDEFINED, f'undefined={sorted(undefined)} expected={sorted(EXPECTED_UNDEFINED)}')
    for name in undefined:
        for p in FORBIDDEN_UNDEFINED_PREFIXES:
            need(not name.startswith(p), f'forbidden CRT/EH symbol {name}')
    defined = coff_obj.defined_external(obj)
    need(ENTRY in defined, f'missing entry {ENTRY}; defined={sorted(defined)}')
    need(defined == {ENTRY}, f'unexpected public symbols {sorted(defined - {ENTRY})}')

    for s in obj['sections']:
        if s['name'] == '.drectve':
            text = s['data'].decode('ascii', errors='replace')
            need('DEFAULTLIB' not in text.upper(), f'directive DEFAULTLIB: {text!r}')
            need(not text.strip(), f'non-empty .drectve: {text!r}')

    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError as e:  # pragma: no cover
        raise SystemExit('capstone required (venv ~/venv-ld2)') from e
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    # Collect all code sections as one contiguous image at local VA 0 with 16-byte gaps (int3).
    code_secs = coff_obj.code_sections(obj)
    offsets, length = coff_obj.layout(obj)
    image = bytearray(b'\xcc' * length)
    for s in code_secs:
        image[offsets[s['index']]:offsets[s['index']] + len(s['data'])] = s['data']
    # Relocation map: local offset -> symbol name (for call targets).
    reloc_at = {}
    for s in code_secs:
        base = offsets[s['index']]
        for r in s['rel']:
            reloc_at[base + r['offset']] = r['name']
            need(r['type'] in (6, 20), f'reloc type {r["type"]}')

    ent = next(s for s in obj['symbols'].values() if s['name'] == ENTRY and s['section'] in offsets)
    entry_off = offsets[ent['section']] + ent['value']
    ins = list(md.disasm(bytes(image), 0))
    by = {i.address: i for i in ins}
    need(entry_off in by, 'entry not at instruction boundary')
    need(all('fs:' not in i.op_str for i in ins), 'FS segment used (SEH registration?)')
    need(not any(i.mnemonic in ('std', 'enter', 'leave') for i in ins), 'banned mnemonic')

    # CFG walk from entry, only through reachable code of this object.
    initial = {r: r + '_entry' for r in ('ebx', 'ebp', 'esi', 'edi')}
    todo = [(entry_off, 0, None, initial, {})]
    seen, normal, calls = set(), [], []
    while todo:
        address, sp, fp, regs, stack = todo.pop()
        state = (address, sp, fp, tuple(sorted(regs.items())), tuple(sorted(stack.items())))
        if state in seen:
            continue
        seen.add(state)
        need(len(seen) < 20000, 'CFG explosion')
        need(address in by, f'fallthrough into non-instruction at {address:#x}')
        i = by[address]
        mn, op, nxt = i.mnemonic, i.op_str, address + i.size
        regs, stack = dict(regs), dict(stack)
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
            # REL32: reloc sits on the displacement (last 4 of 5-byte call).
            rr = next((reloc_at[o] for o in range(address + 1, nxt) if o in reloc_at), None)
            target = rr if rr else op
            if target in CALLEE_CLEANUP:
                pop = CALLEE_CLEANUP[target]
            elif target == ENTRY:
                pop = 16
            else:
                raise SystemExit(f'AUDIT FAIL: unreviewed call at {address:#x} -> {target}')
            calls.append(dict(offset=hex(address), target=target, pop_bytes=pop))
            sp += pop
        elif mn == 'ret':
            need(op == '0x10' or op == '16', f'ret operand {op!r} (want 16)')
            need(sp == 0, f'ESP mismatch at ret {address:#x}: {sp}')
            need(regs == initial, f'nonvolatile mismatch at ret {address:#x}: {regs}')
            normal.append(hex(address))
            continue
        elif mn == 'mov' and op.split(', ')[0] in regs:
            regs[op.split(', ')[0]] = 'modified'
        elif mn in ('lea', 'xor', 'add', 'sub', 'inc', 'dec', 'movzx') and op.split(', ')[0] in regs:
            regs[op.split(', ')[0]] = 'modified'
        if mn == 'mov' and op.startswith('dword ptr [ebp '):
            m = re.match(r'dword ptr \[ebp ([+-]) (0x[0-9a-f]+|[0-9]+)\],', op)
            if m and fp is not None:
                at = fp + (1 if m[1] == '+' else -1) * int(m[2], 0)
                if at in stack:
                    stack[at] = 'local_store'

        def put(dst):
            todo.append((dst, sp, fp, regs, stack))

        if mn.startswith('j'):
            need(op.startswith('0x'), f'indirect jump {op}')
            put(int(op, 0))
            if mn == 'jmp':
                continue
        if nxt in by:
            put(nxt)

    need(normal, 'no normal return')
    # Every ret in the whole image that is reachable must pop 16; unreachable rets ignored.
    return dict(
        object_sha256=hashlib.sha256(raw).hexdigest(),
        object_bytes=len(raw),
        entry=ENTRY,
        ret_pop=16,
        undefined=sorted(undefined),
        defined_public=sorted(defined),
        normal_returns=sorted(set(normal)),
        normal_cfg_states=len(seen),
        esp_and_nonvolatile_preserved_on_normal_paths=True,
        calls=[dict(t) for t in sorted({tuple(sorted(c.items())) for c in calls})],
        relocation_counts={
            str(t): sum(1 for s in code_secs for r in s['rel'] if r['type'] == t)
            for t in sorted({r['type'] for s in code_secs for r in s['rel']})
        },
        no_default_crt_link=True,
        no_memcpy_memset_heap_chkstk_eh_symbols=True,
        native_executed=False,
        linked=False,
        production_can_apply=False,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('object', type=Path)
    ap.add_argument('--expect-sha256', default='', help='refuse unless object matches this sha256')
    ap.add_argument('--json-out', type=Path)
    args = ap.parse_args()
    raw = args.object.read_bytes()
    if args.expect_sha256:
        got = hashlib.sha256(raw).hexdigest()
        need(got == args.expect_sha256.lower(), f'sha256 {got} != {args.expect_sha256}')
    report = audit(raw)
    text = json.dumps(report, ensure_ascii=True, indent=2)
    print(text)
    if args.json_out:
        args.json_out.write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
