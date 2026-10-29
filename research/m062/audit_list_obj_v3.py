"""m062 copy of m061 audit_list_obj.py + EBP spill-slot tracking for MSVC v3 objects.

m061: static COFF audit for list_insert_w.obj (Linux; never loads or runs code).

Pins the undefined-symbol set (5 helper bindings + 2 security-cookie symbols),
rejects any other CRT / heap / EH / chkstk symbol, checks that the sole public
entry `@LD2_ListInsert@24` returns with `ret 16` on every normal CFG path, and
that ESP and non-volatiles are preserved. Capstone CFG walk; no native execution.

Usage: python3 -I -B audit_list_obj.py path/to/list_insert_w.obj
       python3 -I -B audit_list_obj.py --profile u path/to/list_insert_u.obj   (m061b)
Requires: pinned object sha256 via --expect-sha256 once a Windows compile is in.
Until then the script still audits whatever object is given and prints its hash.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coff_obj  # noqa: E402

LEAS_WHILE_SPILLED = set()  # m062: other frame addresses taken while a spill is live
SPILLS = set()  # m062: (offset, slot, binding) spills observed during the last audit()
# m063c opt-in (default off = m062 behaviour unchanged): a `call @__security_check_cookie@4` whose
# fall-through is another function's first instruction / int3 / nop / outside the image is a clang
# cookie-failure tail (noreturn in practice); stop that path instead of walking into the next function.
COOKIE_NORETURN_TAILS = False
NORETURN_TAILS = []  # m063c: tails observed during the last audit() when the opt-in is on

ENTRY = '@LD2_ListInsert@24'
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

# m061b profile 'u' (native-u/list_insert_u.cpp): v1 + 5 USER32 window bindings + 1 data word.
ENTRY_U = '@LD2_ListInsertU@24'
EXPECTED_UNDEFINED_U = EXPECTED_UNDEFINED | frozenset([
    '_LD2_ListMode',
    '_LD2_GetDlgItem',
    '_LD2_IsWindowUnicode',
    '_LD2_GetWindowLongW',
    '_LD2_GetClassLongW',
    '_LD2_SetWindowLongW',
])
CALLEE_CLEANUP_U = dict(CALLEE_CLEANUP, **{
    '_LD2_GetDlgItem': 8,                     # stdcall (HWND, int)
    '_LD2_IsWindowUnicode': 4,                # stdcall (HWND)
    '_LD2_GetWindowLongW': 8,                 # stdcall (HWND, int)
    '_LD2_GetClassLongW': 8,                  # stdcall (HWND, int)
    '_LD2_SetWindowLongW': 12,                # stdcall (HWND, int, LONG)
})
# Data-only bindings: may be read, never called.
DATA_ONLY = frozenset(['_LD2_EntryCount', '_LD2_Entries', '_LD2_ListMode', '___security_cookie'])
PROFILES = {
    'v1': (ENTRY, EXPECTED_UNDEFINED, CALLEE_CLEANUP),
    'u': (ENTRY_U, EXPECTED_UNDEFINED_U, CALLEE_CLEANUP_U),
}


def need(ok, msg):
    if not ok:
        raise SystemExit('AUDIT FAIL: ' + msg)


def audit(raw: bytes, profile: str = 'v1') -> dict:
    need(profile in PROFILES, f'unknown profile {profile!r}')
    ENTRY, EXPECTED_UNDEFINED, CALLEE_CLEANUP = PROFILES[profile]
    SPILLS.clear()
    LEAS_WHILE_SPILLED.clear()
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

    # Internal (static, non-public) functions this object defines in its own code
    # sections. A REL32 call to one is audited recursively as __cdecl (`ret`, caller
    # cleans up): ESP and non-volatiles must be preserved on every normal path.
    internal = {}
    for sym in obj['symbols'].values():
        if sym['kind'] == 0x20 and sym['storage'] == 3 and sym['section'] in offsets:
            internal[sym['name']] = offsets[sym['section']] + sym['value']
    seen, normal, calls, walked = set(), [], [], {}
    NORETURN_TAILS.clear()
    starts = {offsets[sym['section']] + sym['value'] for sym in obj['symbols'].values()
              if sym['kind'] == 0x20 and sym['section'] in offsets}

    def walk(name, depth):
        need(depth <= 4, f'internal call depth at {name}')
        if name in walked:
            need(walked[name] is not None, f'recursive internal call {name}')
            return walked[name]
        walked[name] = None
        if name == ENTRY:
            want_pop = 16
            start_off = entry_off
        else:
            need('@@YA' in name, f'internal callee {name} is not __cdecl')
            want_pop = 0
            start_off = internal[name]
        need(start_off in by, f'{name} not at instruction boundary')
        initial = {r: r + '_entry' for r in ('ebx', 'ebp', 'esi', 'edi')}
        todo = [(start_off, 0, None, initial, {}, ())]
        fn_seen = set()
        while todo:
            address, sp, fp, regs, stack, srcs = todo.pop()
            state = (address, sp, fp, tuple(sorted(regs.items())), tuple(sorted(stack.items())), srcs)
            if state in fn_seen:
                continue
            fn_seen.add(state)
            seen.add((name,) + state)
            need(len(fn_seen) < 200000, 'CFG explosion')
            need(address in by, f'fallthrough into non-instruction at {address:#x}')
            i = by[address]
            mn, op, nxt = i.mnemonic, i.op_str, address + i.size
            regs, stack, srcs = dict(regs), dict(stack), dict(srcs)
            # Track `mov reg, dword ptr [abs32]` loads of a relocated pointer so that a
            # later `call reg` resolves to that binding (e.g. LD2_OriginalDlgItem).
            dst0 = op.split(', ')[0] if op else ''
            if dst0 in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi') and mn != 'call':
                if dst0 != 'esp' and mn not in ('push', 'cmp', 'test') and ',' in op:
                    srcs.pop(dst0, None)
                    if mn == 'mov' and op.endswith(']') and '[' in op.split(', ')[1] and not any(
                            r in op.split(', ')[1] for r in ('eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp', 'esp')):
                        ld = next((reloc_at[o] for o in range(address + 1, nxt) if o in reloc_at), None)
                        if ld:
                            srcs[dst0] = ld
            elif mn == 'pop' and op in srcs:
                srcs.pop(op, None)
            # m062: MSVC may spill a loaded binding pointer to an EBP frame slot and later
            # `call dword ptr [ebp - X]`. Track spills only via exact `mov [ebp - X], reg`
            # from a tracked register; ANY other instruction naming that slot (store, lea /
            # address-taken, arithmetic) drops it. Indexed stores into ebp-relative arrays are
            # checked separately against the slot by audit_v3_spill_slots().
            if op and '[ebp' in op:
                mslot = re.search(r'dword ptr \[ebp - (0x[0-9a-f]+|[0-9]+)\]', op)
                slot = mslot.group(0) if mslot else None
                if slot:
                    parts = op.split(', ')
                    if mn == 'mov' and parts[0] == slot and len(parts) == 2 and parts[1] in srcs:
                        srcs[slot] = srcs[parts[1]]
                        SPILLS.add((hex(address), slot, srcs[slot]))
                    elif mn == 'call' or (mn in ('mov', 'push', 'cmp', 'test') and parts[0] != slot):
                        pass  # read-only use of the slot
                    else:
                        srcs.pop(slot, None)
                if mn == 'lea':
                    ml = re.search(r'\[ebp - (0x[0-9a-f]+|[0-9]+)\]', op)
                    for k in [k for k in srcs if k.startswith('dword ptr [ebp')]:
                        if not ml or k.endswith('[ebp - ' + ml.group(1) + ']'):
                            srcs.pop(k, None)  # the spill slot's own address escaped
                        else:
                            LEAS_WHILE_SPILLED.add((hex(address), op, k))  # reviewed against frame layout
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
                target = rr if rr else srcs.get(op, op)
                for v in ('eax', 'ecx', 'edx'):
                    srcs.pop(v, None)  # volatile across the call
                need(target not in DATA_ONLY, f'call through data binding {target} at {address:#x}')
                if target in CALLEE_CLEANUP:
                    pop = CALLEE_CLEANUP[target]
                elif target in internal:
                    pop = walk(target, depth + 1)
                else:
                    raise SystemExit(f'AUDIT FAIL: unreviewed call at {address:#x} -> {target}')
                calls.append(dict(offset=hex(address), target=target, pop_bytes=pop))
                sp += pop
                if COOKIE_NORETURN_TAILS and target == '@__security_check_cookie@4' and (
                        nxt in starts or nxt not in by or by[nxt].mnemonic in ('nop', 'int3')):
                    NORETURN_TAILS.append(f'{name}:{address:#x}')
                    continue
            elif mn == 'ret':
                got_pop = int(op, 0) if op else 0
                need(got_pop == want_pop, f'{name}: ret operand {op!r} (want {want_pop})')
                need(sp == 0, f'{name}: ESP mismatch at ret {address:#x}: {sp}')
                need(regs == initial, f'{name}: nonvolatile mismatch at ret {address:#x}: {regs}')
                normal.append(f'{name}:{address:#x}')
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
                todo.append((dst, sp, fp, regs, stack, tuple(sorted(srcs.items()))))

            if mn.startswith('j'):
                need(op.startswith('0x'), f'indirect jump {op}')
                put(int(op, 0))
                if mn == 'jmp':
                    continue
            if nxt in by:
                put(nxt)
        walked[name] = want_pop
        return want_pop

    walk(ENTRY, 0)
    need(normal, 'no normal return')
    # Every ret in the whole image that is reachable must pop 16; unreachable rets ignored.
    return dict(
        object_sha256=hashlib.sha256(raw).hexdigest(),
        object_bytes=len(raw),
        profile=profile,
        entry=ENTRY,
        ret_pop=16,
        undefined=sorted(undefined),
        defined_public=sorted(defined),
        normal_returns=sorted(set(normal)),
        normal_cfg_states=len(seen),
        internal_callees_audited=sorted(k for k in walked if k != ENTRY),
        esp_and_nonvolatile_preserved_on_normal_paths=True,
        calls=[dict(t) for t in sorted({tuple(sorted(c.items())) for c in calls})],
        relocation_counts={
            str(t): sum(1 for s in code_secs for r in s['rel'] if r['type'] == t)
            for t in sorted({r['type'] for s in code_secs for r in s['rel']})
        },
        binding_spills=sorted(SPILLS),
        frame_leas_while_spilled=sorted(LEAS_WHILE_SPILLED),
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
    ap.add_argument('--profile', choices=sorted(PROFILES), default='v1',
                    help="v1 = m061 list_insert_w.obj; u = m061b list_insert_u.obj")
    args = ap.parse_args()
    raw = args.object.read_bytes()
    if args.expect_sha256:
        got = hashlib.sha256(raw).hexdigest()
        need(got == args.expect_sha256.lower(), f'sha256 {got} != {args.expect_sha256}')
    report = audit(raw, args.profile)
    text = json.dumps(report, ensure_ascii=True, indent=2)
    print(text)
    if args.json_out:
        args.json_out.write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
