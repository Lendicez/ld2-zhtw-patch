"""m062: static trace of where adventurer names reach the screen (research only, read-only).

Reads the pristine Ld95.exe (path from $LD2_TEST_EXE), never writes it, emits only VAs,
counts and classifications (no game bytes, no game text).

Method
  1. linear-sweep disassembly of .text (capstone), function starts from call targets + padding
  2. GetName = 0x44d870 (thiscall(mgr, CString* out, int index): CString from character+8)
  3. for every function that calls GetName, list its text sinks:
       * CWnd::SendDlgItemMessage 0x4ea671 (joined with research/m061/list_sites.json:
         message, dialog role, whether m061/m061b retargets the site = `priority`)
       * CWnd::SetDlgItemText 0x4ea69f, CWnd::SetWindowText 0x4ea77e / 0x4f657f
       * CDC::TextOut via vtable slot 0x5c (`mov r,[vptr+0x5c]` ... `call r` with >= 4 pushes)
  4. functions with none of these are "no direct sink" (the CString is returned, stored or
     formatted into a longer sentence that is drawn elsewhere)
Usage: LD2_TEST_EXE=.../Ld95.exe python3 -I -B adventurer_draw_trace.py [--json-out F]
"""
from __future__ import annotations
import argparse, bisect, collections, hashlib, json, os, re, sys
from pathlib import Path
import capstone, pefile

HERE = Path(__file__).resolve().parent
BASE = 0x400000
PRISTINE_SHA256_PREFIX = '6c817a09'
GETNAME = 0x44d870
SEND_DLG = 0x4ea671
SET_DLG_TEXT = 0x4ea69f
SET_WINDOW_TEXT = {0x4ea77e, 0x4f657f}
NAMEPAIR_SITE = 0x46dca5        # m056/m058 hooked item-name TextOut pair (continuation VA)
TAVERN_SITE = 0x4b2d1f


def sweep(pe):
    img = pe.get_memory_mapped_image()
    text = next(s for s in pe.sections if s.Name.startswith(b'.text'))
    ts = BASE + text.VirtualAddress
    te = ts + text.Misc_VirtualSize
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    code = img[ts - BASE:te - BASE]
    ins, a = [], ts
    while a < te:
        got = False
        for i in md.disasm(code[a - ts:a - ts + 0x4000], a):
            ins.append((i.address, i.mnemonic, i.op_str))
            a = i.address + i.size
            got = True
            if a >= te:
                break
        if not got:
            a += 1
    return ins


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--json-out', type=Path)
    a = ap.parse_args()
    exe = Path(os.environ['LD2_TEST_EXE'])
    raw = exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if not sha.startswith(PRISTINE_SHA256_PREFIX):
        raise SystemExit('not the pristine Ld95.exe')
    pe = pefile.PE(data=raw)
    ins = sweep(pe)
    starts = set()
    for k in range(1, len(ins)):
        p = ins[k - 1]
        if p[1] in ('int3', 'ret', 'jmp') and ins[k][1] != 'int3' and (p[1] == 'int3' or ins[k][0] % 16 == 0):
            starts.add(ins[k][0])
    for i in ins:
        if i[1] == 'call' and i[2].startswith('0x'):
            starts.add(int(i[2], 16))
    starts = sorted(starts)
    func_of = lambda v: starts[bisect.bisect_right(starts, v) - 1]
    sites = {int(s['va'], 16): s for s in json.loads((HERE.parent / 'm061' / 'list_sites.json').read_text())['sites']}
    textout = []
    for k, i in enumerate(ins):
        mm = re.match(r'(e[a-d]x|e[sd]i|ebp), dword ptr \[(e[a-d]x|e[sd]i|ebp) \+ 0x5c\]$', i[2]) if i[1] == 'mov' else None
        if not mm:
            continue
        pushes = 0
        for j in range(k + 1, min(k + 12, len(ins))):
            if ins[j][1] == 'push':
                pushes += 1
            if ins[j][1] == 'call' and ins[j][2] == mm.group(1):
                if pushes >= 4:
                    textout.append(ins[j][0])
                break
    by_func = collections.defaultdict(list)
    for i in ins:
        by_func[func_of(i[0])].append(i)
    callers = collections.OrderedDict()
    for i in ins:
        if i[1] == 'call' and i[2] == hex(GETNAME):
            callers.setdefault(func_of(i[0]), []).append(i[0])
    tset = set(textout)
    rows = []
    for f, calls in callers.items():
        sinks = []
        for i in by_func[f]:
            t = int(i[2], 16) if i[1] == 'call' and i[2].startswith('0x') else None
            if t == SEND_DLG:
                s = sites.get(i[0])
                sinks.append(dict(va=hex(i[0]), api='SendDlgItemMessage', message=s and s['message'],
                                  roles=s and s['roles'], retargeted_by_m061b=bool(s and s['priority'])))
            elif t == SET_DLG_TEXT:
                sinks.append(dict(va=hex(i[0]), api='SetDlgItemText'))
            elif t in SET_WINDOW_TEXT:
                sinks.append(dict(va=hex(i[0]), api='SetWindowText'))
            elif i[0] in tset:
                sinks.append(dict(va=hex(i[0]), api='CDC::TextOut(vtable+0x5c)', hooked_by_namepair=(i[0] in (NAMEPAIR_SITE - 2, NAMEPAIR_SITE - 0x16))))
        rows.append(dict(function=hex(f), getname_calls=[hex(c) for c in calls], sinks=sinks))
    kinds = collections.Counter()
    for r in rows:
        k = {s['api'] for s in r['sinks']}
        kinds['list' if 'SendDlgItemMessage' in k else 'textout' if any(x.startswith('CDC') for x in k)
              else 'dialog_text' if k else 'no_direct_sink'] += 1
    lists = [dict(function=r['function'], **s) for r in rows for s in r['sinks'] if s['api'] == 'SendDlgItemMessage']
    out = dict(
        milestone='m062', kind='adventurer-name draw trace (static, read-only)', source_sha256=sha,
        getname_va=hex(GETNAME), getname_caller_functions=len(rows), classification=dict(kinds),
        tavern=dict(site=hex(TAVERN_SITE), function='0x4b2b10', message='LB_INSERTSTRING', control_id=1000, dialog_role='tavern',
                    string='wsprintfA("%s", name) = the bare name, one segment, no tab',
                    retargeted_by_m061b=bool(sites[TAVERN_SITE]['priority'])),
        name_list_sites=lists,
        name_list_sites_retargeted=[x['va'] for x in lists if x['retargeted_by_m061b']],
        name_dialog_text_sites=[dict(function=r['function'], **s) for r in rows for s in r['sinks'] if s['api'] in ('SetDlgItemText', 'SetWindowText')],
        name_textout_functions=sorted({r['function'] for r in rows for s in r['sinks'] if s['api'].startswith('CDC')}),
        textout_sites_total=len(textout), namepair_hook_continuation=hex(NAMEPAIR_SITE),
        rows=rows, production_can_apply=False)
    js = json.dumps(out, indent=1)
    if a.json_out:
        a.json_out.write_text(js + '\n', encoding='utf-8')
    summary = {k: v for k, v in out.items() if k != 'rows'}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
