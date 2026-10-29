"""m061: static discovery of dialog list-box/combo-box string sites (research only).

Requires capstone (optional dependency; not used by tests). Reads the pinned
original EXE, disassembles .text linearly, and reports every call to the MFC
CWnd::SendDlgItemMessage wrapper whose message is a string insert or read-back,
mapped to dialog resources through vtable -> constructor -> resource-ID links.
Output: IDs, VAs, message names and window hashes only. No text, no disassembly.
"""
import bisect, collections, hashlib, json, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import source_profile  # noqa: E402

BASE = 0x400000
WRAPPER_VA = 0x4ea671           # CWnd::SendDlgItemMessage (normal-HWND branch calls SendDlgItemMessageA)
WRAPPER_IAT_CALL_VA = 0x4ea689  # call [USER32!SendDlgItemMessageA]
SENDMESSAGEA_IAT = 0x525620
MESSAGES = {0x180: 'LB_ADDSTRING', 0x181: 'LB_INSERTSTRING', 0x143: 'CB_ADDSTRING', 0x14a: 'CB_INSERTSTRING',
            0x189: 'LB_GETTEXT', 0x18a: 'LB_GETTEXTLEN', 0x148: 'CB_GETLBTEXT', 0x149: 'CB_GETLBTEXTLEN'}
INSERTS = {'LB_ADDSTRING', 'LB_INSERTSTRING', 'CB_ADDSTRING', 'CB_INSERTSTRING'}
# Role labels by dialog resource ID (named from our own m045 zh-TW titles; no game text here).
ROLES = {137: 'shop-buy', 138: 'shop-sell', 139: 'shop-strengthen', 140: 'inn-commission', 142: 'info',
         143: 'tavern', 145: 'revive', 152: 'save-load', 153: 'save-store', 156: 'commission-info',
         157: 'pass', 159: 'storage', 160: 'party', 162: 'proposal', 165: 'display', 169: 'commission-list',
         172: 'item-distribute', 176: 'talk', 177: 'item-page-b', 178: 'item-page', 185: 'item-page-c',
         186: 'talk-b', 187: 'invite', 188: 'steal', 189: 'assault', 191: 'birthday', 225: 'item-arrange',
         438: 'list-pair-a', 456: 'chronicle', 457: 'records', 461: 'dark-guild', 463: 'education',
         464: 'wind-orb', 520: 'list-pair-b'}
PRIORITY_ROLES = {'shop-buy', 'shop-sell', 'shop-strengthen', 'inn-commission', 'tavern', 'commission-list', 'commission-info'}
WINDOW_BEFORE = 16


def dialogs(raw):
    for src in (HERE.parents[1] / 'src', HERE.parents[2] / 'ld2-zhtw-patch-m051' / 'src'):  # repo layout, then lab layout
        if (src / 'ld2patch' / 'pe_resources.py').is_file():
            sys.path.insert(0, str(src))
            break
    from ld2patch.pe_resources import PE, parse_dialog, u16, u32
    pe, out = PE(raw), {}
    for r in pe.resources:
        if r['path'][0] != 5:
            continue
        d = parse_dialog(pe.payload(r))
        items = []
        for it in d['items']:
            h = bytes.fromhex(it['header'])
            if d['extended']:
                style, cid = struct.unpack_from('<I', h, 8)[0], u32(h, 20)
            else:
                style, cid = struct.unpack_from('<I', h, 0)[0], u16(h, 16)
            cls = it['class'].get('ordinal')
            if cls in (0x83, 0x85):
                items.append(dict(id=cid, cls='LISTBOX' if cls == 0x83 else 'COMBOBOX', style=style))
        out[r['path'][1]] = items
    return out


def discover(raw):
    import capstone
    need = source_profile.need
    need(source_profile.sha(raw) == source_profile.ORIGINAL_SHA256, 'Discovery runs on the pinned original only')
    text = raw[0x1000:0x1000 + 0x123c39]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.skipdata = True
    ins = list(md.disasm(text, BASE + 0x1000))
    idx = {i.address: k for k, i in enumerate(ins)}
    tlo, thi = BASE + 0x1000, BASE + 0x1000 + len(text)

    def imm(s):
        try:
            return int(s, 16) if s.startswith('0x') else (int(s) if s.lstrip('-').isdigit() else None)
        except ValueError:
            return None
    targets = set()
    for i in ins:
        if i.mnemonic == 'call' and imm(i.op_str) is not None:
            targets.add(imm(i.op_str))
    rdata = raw[0x125000:0x195000]
    slots = collections.defaultdict(list)
    for o in range(0, len(rdata) - 3, 4):
        v = struct.unpack_from('<I', rdata, o)[0]
        if tlo <= v < thi:
            slots[v].append(BASE + 0x125000 + o)
    starts = sorted(targets | set(slots))

    def fstart(a):
        return starts[bisect.bisect_right(starts, a) - 1]
    callers = collections.defaultdict(set)
    vt_writes = collections.defaultdict(list)
    for i in ins:
        if i.mnemonic == 'call' and imm(i.op_str) is not None:
            callers[imm(i.op_str)].add(fstart(i.address))
        if i.mnemonic == 'mov' and i.op_str.startswith('dword ptr [') and '+' not in i.op_str.split(']')[0]:
            v = imm(i.op_str.split(', ')[-1])
            if v is not None and BASE + 0x125000 <= v < BASE + 0x195000:
                vt_writes[v].append(i.address)
    vbases = sorted(vt_writes)

    def ctor_resource(fa):
        k = idx.get(fa)
        for i in ins[k:k + 30] if k is not None else []:
            if i.mnemonic == 'ret':
                break
            v = imm(i.op_str) if i.mnemonic == 'push' else None
            if v is not None and (100 <= v <= 600 or v == 30721):
                return v
        return None

    def resources(func, depth=0, seen=None):
        seen = seen if seen is not None else set()
        if func in seen or depth > 4:
            return set()
        seen.add(func)
        res = set()
        for slot in slots.get(func, []):
            j = bisect.bisect_right(vbases, slot) - 1
            if j >= 0 and slot - vbases[j] < 0x200:
                for w in vt_writes[vbases[j]]:
                    r = ctor_resource(fstart(w))
                    if r:
                        res.add(r)
        if not res:
            for c in callers.get(func, ()):
                res |= resources(c, depth + 1, seen)
        return res

    def pushes(k, n):
        out, j = [], k - 1
        while j >= 0 and len(out) < n and k - j < 40:
            i = ins[j]
            if i.mnemonic in ('ret', 'jmp', 'call'):
                break
            if i.mnemonic == 'push':
                out.append(i.op_str)
            j -= 1
        return out
    dlg = dialogs(raw)
    sites, unresolved = [], []
    for i in ins:
        direct = i.mnemonic == 'call' and i.op_str == f'dword ptr [{SENDMESSAGEA_IAT:#x}]'
        if not (i.mnemonic == 'call' and (i.op_str == f'{WRAPPER_VA:#x}' or direct)):
            continue
        p = pushes(idx[i.address], 4)
        msg = imm(p[1]) if len(p) > 1 else None
        if msg is None:
            if not direct:
                unresolved.append(hex(i.address))
            continue
        if msg not in MESSAGES:
            continue
        cid = imm(p[0]) if not direct else None
        f = fstart(i.address)
        res = sorted(resources(f))
        if not res and cid is not None:
            res = sorted(k for k, items in dlg.items() if any(x['id'] == cid for x in items) and
                         sum(any(x['id'] == cid for x in v) for v in dlg.values()) == 1)
        ctl = [dict(resource=r, **x) for r in res for x in dlg.get(r, []) if x['id'] == cid]
        o = i.address - BASE
        sites.append(dict(va=hex(i.address), kind='SendMessageA' if direct else 'CWnd::SendDlgItemMessage',
                          message=MESSAGES[msg], control_id=cid, function_va=hex(f), dialogs=res,
                          roles=sorted({ROLES.get(r, f'dialog-{r}') for r in res}),
                          control_styles=sorted({hex(c['style']) for c in ctl}),
                          sorted_listbox=any(c['cls'] == 'LISTBOX' and c['style'] & 2 for c in ctl),
                          owner_draw=any(c['style'] & 0x30 for c in ctl),
                          window_sha256=hashlib.sha256(raw[o - WINDOW_BEFORE:o + 5]).hexdigest()))
    readback = {(s['control_id'], d) for s in sites if s['message'] not in INSERTS for d in s['dialogs']}
    for s in sites:
        s['readback_on_same_control'] = any((s['control_id'], d) in readback for d in s['dialogs'])
        s['phase1_candidate'] = (s['message'] in INSERTS and s['kind'] != 'SendMessageA' and bool(s['dialogs'])
                                 and not s['readback_on_same_control'] and not s['owner_draw']
                                 and not (s['message'].endswith('ADDSTRING') and s['sorted_listbox']))
        s['priority'] = s['phase1_candidate'] and bool(PRIORITY_ROLES & set(s['roles']))
    c = collections.Counter(s['message'] for s in sites)
    return dict(source_sha256=source_profile.ORIGINAL_SHA256, wrapper_va=hex(WRAPPER_VA),
                wrapper_iat_call_va=hex(WRAPPER_IAT_CALL_VA), window_bytes_before_call=WINDOW_BEFORE,
                counts=dict(sorted(c.items())), unresolved_wrapper_message_sites=len(unresolved),
                phase1_candidates=sum(s['phase1_candidate'] for s in sites),
                priority_sites=sum(s['priority'] for s in sites),
                imports_present=dict(LoadStringA=False, MultiByteToWideChar_iat='0x52537c', SendDlgItemMessageW=False),
                sites=sites, production_can_apply=False)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: list_sites.py <licensed original Ld95.exe> (m045 reuses it via site_plan.verify_sites)')
    raw = Path(sys.argv[1]).read_bytes()
    print(json.dumps(discover(raw), ensure_ascii=False, indent=1))
