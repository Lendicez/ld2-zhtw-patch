"""m063a: enable step for three helpers, in memory only (no file writer).

Input is an inert m063 image (merge_plan_m063). This module rewrites exactly:
  * the m061 40-byte hook span -> stdcall call into _LD2_NamePair@16 (unchanged from m061);
  * 18 list sites: rel32 of `call CWnd::SendDlgItemMessage` -> @LD2_ListInsertV3@24
      = the 8 m061 priority sites + 10 whole-name sites from name_draw_sites (m063 plan §2);
  * 25 TextOut "pair5" sites: `mov R1,[cdc]; mov R2,[R1+0x5c]` (5 B) -> `mov R2, imm32(@LD2_NameTextOut@24)`;
  * 1 "tail8" exception at 0x48f47e (call 0x48f484):
      `mov edx,[eax+0x5c]; push ecx; mov ecx,esi; call edx` (8 B)
   -> `push ecx; mov ecx,esi; call rel32 @LD2_NameTextOut@24` (8 B, same return address 0x48f486);
  * the PE CheckSum.
Nothing else may differ. production_can_apply / release_approved stay false.
Contains no game bytes: only VAs, hash prefixes and generic x86 encodings of the matched shapes.
"""
from pathlib import Path
import hashlib, json, struct, sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
import site_plan, pe_serializer, enable_plan as ep  # noqa: E402

BASE = 0x400000
TEXT_RVA, TEXT_END = site_plan.TEXT_RVA, site_plan.TEXT_END
SOURCE_SHA256 = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
REG = dict(eax=0, ecx=1, edx=2, ebx=3, esp=4, ebp=5, esi=6, edi=7)
VOLATILE = ('eax', 'ecx', 'edx')

# name_draw_sites.summary.json, pinned (call VA of each pair5 TextOut site)
PAIR5_CALLS = (
    0x438a1c, 0x438a4b, 0x438a61, 0x438ae7, 0x438b16, 0x438b2c, 0x438bb2, 0x438be1, 0x438bf7,
    0x438c80, 0x438cb2, 0x438ccb, 0x438d4f, 0x438d81, 0x438d9a, 0x438e1e, 0x438e50, 0x438e69,
    0x48f464, 0x4b9580, 0x4b9597, 0x4d9729, 0x4d98e1, 0x4ddcd9, 0x4dde91)
TAIL8 = dict(call_va=0x48f484, start_va=0x48f47e, length=8, ret_va=0x48f486,
             # mov edx,[eax+0x5c] | push ecx | mov ecx,esi | call edx
             shape=(('load', 'edx', 'eax', 0x5c), ('push', 'ecx'), ('movecx', 'esi'), ('callreg', 'edx')))
M061_PRIORITY_LIST = frozenset({0x492431, 0x4aaf19, 0x4ab0fe, 0x4b1153, 0x4b2d1f, 0x4b3477, 0x4b46e4, 0x4b4df1})
M063_LIST_EXTRA = (  # whole-name list sites not yet retargeted (8x LB_INSERTSTRING, 2x CB_INSERTSTRING)
    0x4735f6, 0x474ead, 0x47502c, 0x475bbe, 0x47c242, 0x481d42, 0x497a20, 0x4cb4b2, 0x46e73a, 0x47db6a)
LIST_EXTRA_MSG = {0x46e73a: 'CB_INSERTSTRING', 0x47db6a: 'CB_INSERTSTRING'}
EXPECTED_COUNTS = dict(pair5=25, tail8=1, list_sites=18, list_extra=10)


class Refuse(ValueError):
    pass


def need(ok, msg):
    if not ok:
        raise Refuse(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------ generic x86 encoders (32-bit)
def enc_load(dst, base, disp=None):
    """mov dst, dword [base(+disp8)] ; base must not be esp/ebp (no SIB / no ebp quirk)."""
    need(base not in ('esp', 'ebp') and dst in REG and base in REG, 'load shape')
    if disp is None:
        return bytes([0x8B, (REG[dst] << 3) | REG[base]])
    need(0 <= disp < 0x80, 'disp8')
    return bytes([0x8B, 0x40 | (REG[dst] << 3) | REG[base], disp])


def enc_mov_ecx(src):
    return bytes([0x8B, 0xC8 | REG[src]])


def enc_call_reg(r):
    return bytes([0xFF, 0xD0 | REG[r]])


def enc_push(r):
    return bytes([0x50 | REG[r]])


def enc_mov_imm(r, imm):
    return bytes([0xB8 | REG[r]]) + struct.pack('<I', imm)


def enc_shape(shape):
    out = b''
    for op in shape:
        out += {'load': lambda o: enc_load(o[1], o[2], o[3]), 'push': lambda o: enc_push(o[1]),
                'movecx': lambda o: enc_mov_ecx(o[1]), 'callreg': lambda o: enc_call_reg(o[1])}[op[0]](op)
    return out


TAIL8_SHA8 = sha(enc_shape(TAIL8['shape']))[:8]


# ------------------------------------------------------------ site loading
def load_textout_sites(summary_bytes):
    """name_draw_sites.summary.json -> (pair5 rows, tail8 row). Refuses any drift from the pins."""
    s = json.loads(summary_bytes)
    need(s.get('source_sha256') == SOURCE_SHA256, 'Summary source identity')
    need(s.get('production_can_apply') is False and s.get('release_approved') is False, 'Summary boundary flags')
    need(s.get('proposed_helper') == '@LD2_NameTextOut@24', 'Summary helper')
    whole = [t for t in s['textout_sites'] if t['tag'] in ('name', 'bare', 'appended')]
    pair = [t for t in whole if (t.get('install') or {}).get('kind') == 'pair5']
    manual = [t for t in whole if (t.get('install') or {}).get('kind') == 'manual']
    need(all(t['install'] is None for t in s['textout_sites'] if t['tag'] == 'composite'), 'Composite sites must stay unpatched')
    calls = [int(t['va'], 16) for t in pair]
    need(len(calls) == len(set(calls)) and tuple(sorted(calls)) == tuple(sorted(PAIR5_CALLS)), 'pair5 site set drift')
    need([int(t['va'], 16) for t in manual] == [TAIL8['call_va']], 'tail8 exception set drift')
    rows = []
    for t in sorted(pair, key=lambda t: int(t['va'], 16)):
        i = t['install']
        need(i['adjacent'] is True and i['r1_read_before_call'] is False and i['branch_targets_inside'] == 0, 'pair5 preconditions')
        need(i['cdc_reg'] in REG and i['cdc_reg'] not in ('esp', 'ebp') and i['call_reg'] in VOLATILE, 'pair5 registers')
        need(int(i['slot_load_va'], 16) == int(i['pair_va'], 16) + 2, 'pair5 adjacency')
        rows.append(dict(call_va=int(t['va'], 16), pair_va=int(i['pair_va'], 16), cdc=i['cdc_reg'],
                         r2=i['call_reg'], sha8=i['orig_sha256_8'], function=t['function'], xy=t['xy']))
    m = manual[0]['install']
    need(int(m['slot_load_va'], 16) == TAIL8['start_va'] and m['branch_targets_inside'] == 0, 'tail8 preconditions')
    return rows, dict(TAIL8)


def load_list_sites(manifest_bytes):
    """m061 list_sites.json -> the 8 priority sites + the 10 m063 whole-name sites (18)."""
    m = json.loads(manifest_bytes)
    need(m.get('wrapper_va') == hex(site_plan.WRAPPER_VA) and m.get('production_can_apply') is False, 'Manifest identity')
    need(m.get('source_sha256') == SOURCE_SHA256, 'Manifest source identity')
    by = {}
    for s in m['sites']:
        need(s['va'] not in by, 'Duplicate manifest VA')
        by[s['va']] = s
    prio = [s for s in m['sites'] if s['priority']]
    need({int(s['va'], 16) for s in prio} == M061_PRIORITY_LIST, 'm061 priority set drift')
    need(not set(M063_LIST_EXTRA) & M061_PRIORITY_LIST, 'Extra sites overlap priority')
    extra = []
    for va in M063_LIST_EXTRA:
        s = by.get(hex(va))
        need(s is not None, f'List site {va:#x} missing from manifest')
        need(s['kind'] == 'CWnd::SendDlgItemMessage', 'List site kind')
        need(s['message'] == LIST_EXTRA_MSG.get(va, 'LB_INSERTSTRING'), f'List site message {va:#x}')
        need(s['readback_on_same_control'] is False, f'List site readback {va:#x}')
        extra.append(s)
    rows = prio + extra
    need(len(rows) == EXPECTED_COUNTS['list_sites'] and len({s['va'] for s in rows}) == len(rows), 'List site count')
    return rows


# ------------------------------------------------------------ planning
def _text_off(va, n):
    o = va - BASE
    need(TEXT_RVA <= o and o + n <= TEXT_END, 'Site outside .text')
    return o


def plan_pair5(image, rows, textout_va):
    plan = []
    for r in rows:
        o = _text_off(r['pair_va'], 5)
        c = _text_off(r['call_va'], 2)
        need(7 <= r['call_va'] - r['pair_va'] <= 0x40, 'pair5 distance')
        old = bytes(image[o:o + 5])
        need(sha(old)[:8] == r['sha8'], f"pair5 bytes hash {r['pair_va']:#x}")
        r1 = next((k for k in VOLATILE if enc_load(k, r['cdc']) + enc_load(r['r2'], k, 0x5c) == old), None)
        need(r1 is not None, f"pair5 shape {r['pair_va']:#x}")
        need(bytes(image[c - 2:c + 2]) == enc_mov_ecx(r['cdc']) + enc_call_reg(r['r2']), f"pair5 call shape {r['call_va']:#x}")
        plan.append(dict(kind='pair5', off=o, old=old, new=enc_mov_imm(r['r2'], textout_va), call_va=r['call_va'], r1=r1))
    return plan


def plan_tail8(image, tail, textout_va):
    o = _text_off(tail['start_va'], tail['length'])
    old = bytes(image[o:o + 8])
    need(old == enc_shape(tail['shape']) and sha(old)[:8] == TAIL8_SHA8, 'tail8 bytes')
    need(tail['start_va'] + 8 == tail['ret_va'] == tail['call_va'] + 2, 'tail8 return address')
    rel = textout_va - tail['ret_va']
    need(-(1 << 31) <= rel < (1 << 31), 'REL32 range')
    new = enc_push('ecx') + enc_mov_ecx('esi') + b'\xe8' + struct.pack('<i', rel)
    need(len(new) == 8, 'tail8 length')
    return dict(kind='tail8', off=o, old=old, new=new, call_va=tail['call_va'])


def check_disjoint(windows):
    """windows: [(start_off, end_off, label)] -> refuse any overlap."""
    w = sorted(windows)
    for (a0, a1, la), (b0, b1, lb) in zip(w, w[1:]):
        need(a1 <= b0, f'Patched windows overlap: {la} / {lb}')


def plan_textout(image, textout_va, code_range, summary_bytes):
    lo, hi = code_range
    need(type(textout_va) is int and lo <= textout_va < hi, 'NameTextOut VA outside .ld2t')
    rows, tail = load_textout_sites(summary_bytes)
    pairs = plan_pair5(image, rows, textout_va)
    t8 = plan_tail8(image, tail, textout_va)
    need(len(pairs) == EXPECTED_COUNTS['pair5'], 'Expected 25 pair5 sites')
    return pairs + [t8]


def apply_enabled_m063(inert, name_pair_va, list_entry_va, textout_va, code_range, list_manifest, draw_summary):
    need(type(inert) is bytes, 'image')
    for va in (name_pair_va, list_entry_va, textout_va):
        need(code_range[0] <= va < code_range[1], 'Helper entry outside .ld2t')
    need(len({name_pair_va, list_entry_va, textout_va}) == 3, 'Helper entries distinct')
    a, b = ep.HOOK_SPAN
    need(sha(inert[a:b]) == ep.HOOK_SPAN_SHA256, 'Inert hook span must be original')
    lsites = load_list_sites(list_manifest)
    lplan = site_plan.plan_retarget(inert, lsites, list_entry_va)
    need(len(lplan) == EXPECTED_COUNTS['list_sites'], 'Expected 18 list sites')
    tplan = plan_textout(inert, textout_va, code_range, draw_summary)
    windows = [(a, b, 'hook')] + [(o, o + 5, f'list@{BASE + o:#x}') for o, _, _ in lplan] + \
              [(p['off'], p['off'] + len(p['old']), f"{p['kind']}@{BASE + p['off']:#x}") for p in tplan]
    check_disjoint(windows)
    out = bytearray(inert)
    out[a:b] = ep.hook_stub(name_pair_va)
    for o, old, new in lplan:
        need(out[o:o + 5] == old and old[0] == 0xE8 == new[0], 'list site bytes')
        out[o:o + 5] = new
    for p in tplan:
        n = len(p['old'])
        need(out[p['off']:p['off'] + n] == p['old'] and len(p['new']) == n, 'textout site bytes')
        out[p['off']:p['off'] + n] = p['new']
    co = ep._checksum_offset(out)
    struct.pack_into('<I', out, co, 0)
    struct.pack_into('<I', out, co, pe_serializer.pe_checksum(bytes(out), co))
    out = bytes(out)
    need(len(out) == len(inert), 'size changed')
    changed = [i for i in range(len(inert)) if inert[i] != out[i]]
    allowed = set(range(a, b)) | set(range(co, co + 4)) | {o + k for o, _, _ in lplan for k in range(1, 5)} | \
        {p['off'] + k for p in tplan for k in range(len(p['old']))}
    need(set(changed) <= allowed, 'Unexpected byte change outside hook/sites/checksum')
    return out, dict(
        hook_span=[hex(a), hex(b)], hook_stub_sha256=sha(out[a:b]), name_pair_va=hex(name_pair_va),
        list_entry_va=hex(list_entry_va), textout_entry_va=hex(textout_va),
        sites=[dict(va=hex(BASE + o), old=old.hex(), new=new.hex()) for o, old, new in lplan],
        list_sites_m061=8, list_sites_m063=len(lplan) - 8,
        textout_sites=[dict(kind=p['kind'], va=hex(BASE + p['off']), call_va=hex(p['call_va']),
                            old_sha256_8=sha(p['old'])[:8], new=p['new'].hex()) for p in tplan],
        counts=dict(pair5=sum(p['kind'] == 'pair5' for p in tplan), tail8=sum(p['kind'] == 'tail8' for p in tplan),
                    list_sites=len(lplan)),
        changed_bytes=len(changed), checksum=hex(struct.unpack_from('<I', out, co)[0]),
        hook_enabled=True, list_sites_retargeted=True, textout_sites_patched=True,
        file_written=False, production_can_apply=False, release_approved=False)
