"""m062 -> m063: flow-sensitive static classification of adventurer-name draw sites.

Research only, read-only. Reads the pristine Ld95.exe ($LD2_TEST_EXE), never writes it and
emits only VAs, coordinates (immediates), counts, tags and short SHA-256 prefixes of code
bytes (no game text, no raw game bytes).

Supersedes the sink listing of adventurer_draw_trace.py with per-sink data flow:
  * function starts = call targets + first instruction after int3 padding (tighter than
    the old heuristic; e.g. old "0x4dc720" is the tail of 0x4dbcb0)
  * forward per-function ESP tracking (stdcall ret imm, cdecl cleanup incl. deferred
    `add esp`, wsprintfA via IAT or a register loaded from it, jump-target states)
  * CString slot events: GetName 0x44d870, copy (0x405b50/0x4054e0/0x412010), Append 0x405a20,
    wsprintfA (fmt "%s" = bare), operator+ (0x438f70/0x439030/0x443730) = composite
  * sink text argument -> nearest event on that slot -> tag
      name/bare/appended = the whole string is one adventurer name (whole-string lookup works)
      composite          = name concatenated with other text (needs substring design)
  * MANUAL overlay: three sink groups confirmed by hand (see MANUAL below)
  * install plan for bare TextOut sites: the 5-byte pair `mov R1,[cdc]; mov R2,[R1+0x5c]`
    -> `mov R2,imm32(@LD2_NameTextOut@24)`; checks adjacency, R1 dead until the call and
    no branch target inside (pair, call].
Usage: LD2_TEST_EXE=.../Ld95.exe python3 -I -B name_draw_sites.py [--json-out F]
"""
from __future__ import annotations
import argparse, bisect, collections, hashlib, json, os, re, sys
from pathlib import Path
import pefile
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adventurer_draw_trace as T  # sweep()

ins = []; idx = {}; st = []; funcs = {}; img = b''


def init(pe):
    global ins, idx, st, funcs, img
    ins = T.sweep(pe)
    idx = {a: k for k, (a, _, _) in enumerate(ins)}
    s = set()
    for k in range(1, len(ins)):
        if ins[k - 1][1] == 'int3' and ins[k][1] != 'int3':
            s.add(ins[k][0])
    for a, m, o in ins:
        if m == 'call' and o.startswith('0x'):
            s.add(int(o, 16))
    st = sorted(s)
    funcs = collections.defaultdict(list)
    for k, (a, m, o) in enumerate(ins):
        if a < GAME_END:
            funcs[fstart(a)].append(k)
    img = pe.get_memory_mapped_image()
    RETN.clear(); DCACHE.clear()


GETNAME=0x44d870; ASSIGN=0x405b50; WSPRINTF='dword ptr [0x5255ac]'; GAME_END=0x4e0000
SL={0x5c:('TextOut',2),0x60:('ExtTextOut',4),0x64:('TabbedTextOut',2),0x68:('DrawText',0),0x6c:('DrawTextEx',0)}
def fstart(v): return st[bisect.bisect_right(st,v)-1]
def is_boundary(k):
    m,o=ins[k][1],ins[k][2]
    if m=='call': return True
    if m=='add' and o.startswith('esp,') and ins[k-1][1]=='call': return True
    return False
RETN={}
def ret_imm(f):
    if f in RETN: return RETN[f]
    k=idx.get(f); r=0
    if k is not None:
        for j in range(k,min(k+3000,len(ins))):
            if ins[j][1]=='ret': r=int(ins[j][2],16) if ins[j][2] else 0; break
            if ins[j][1]=='jmp' and ins[j][2].startswith('0x') and j==k: r=ret_imm(int(ins[j][2],16)); break
    RETN[f]=r; return r
DCACHE={}
def fdeltas(f):
    if f in DCACHE: return DCACHE[f]
    k=idx.get(f)
    if k is None: DCACHE[f]={}; return {}
    D={}; d=0; at={}; pend=0; dead=False; wsr=set()
    nxt=st[bisect.bisect_right(st,f)] if bisect.bisect_right(st,f)<len(st) else 1<<40
    while k<len(ins) and ins[k][0]<nxt:
        a,m,o=ins[k]
        if a in at: d,pend=at[a]
        dead=False
        if m=='mov' and o.endswith('dword ptr [0x5255ac]'): wsr.add(o.split(',')[0])
        D[k]=d
        if m=='push': d+=4; pend+=4
        elif m=='pop': d-=4; pend=max(0,pend-4)
        elif m=='sub' and re.fullmatch(r'esp, (0x[0-9a-f]+|\d+)',o): d+=int(o[5:],0)
        elif m=='add' and re.fullmatch(r'esp, (0x[0-9a-f]+|\d+)',o): d-=int(o[5:],0); pend=0
        elif m=='call':
            if o.startswith('0x'): d-=ret_imm(int(o,16))
            else:
                cdecl=('0x5255ac' in o) or o in wsr
                for j in range(k+1,min(k+4,len(ins))):
                    if ins[j][1]=='add' and ins[j][2].startswith('esp,'): cdecl=True; break
                    if ins[j][1] in ('call','push','pop','ret') or ins[j][1].startswith('j'): break
                if not cdecl: d-=pend
            pend=0
        elif m.startswith('j'):
            if o.startswith('0x'): at.setdefault(int(o,16),(d,pend))
            if m=='jmp': dead=True; d-=pend; pend=0
        elif m=='ret': dead=True
        k+=1
    DCACHE[f]=D; return D
def stmt_back(k):
    j=k-1; seq=[]
    f=fstart(ins[k][0]); D=fdeltas(f)
    while j>=0 and ins[j][0]>=f and not is_boundary(j) and k-j<40:
        seq.append(j); j-=1
    seq.reverse()
    deltas={j:D.get(j,0) for j in seq}
    return seq,deltas,D.get(k,0)
MEM=re.compile(r'(?:dword ptr )?\[(esp|ebp)(?: ([+-]) (0x[0-9a-f]+|\d+))?\]$')
EBP_FRAME=[False]
def slot_of(mem,delta):
    mm=MEM.match(mem)
    if not mm: return None
    off=int(mm.group(3),16) if mm.group(3) and mm.group(3).startswith('0x') else int(mm.group(3) or 0)
    if mm.group(2)=='-': off=-off
    if mm.group(1)=='ebp' and not EBP_FRAME[0]: return None
    return ('esp',off-delta) if mm.group(1)=='esp' else ('ebp',off)
def resolve(k_push, seq, deltas):
    """resolve value pushed at index k_push -> ('slotval',slot) data loaded from slot | ('slotaddr',slot) | ('imm',v) | ('other',txt)"""
    m,o=ins[k_push][1],ins[k_push][2]
    if re.fullmatch(r'-?0x[0-9a-f]+|-?\d+',o): return ('imm',int(o,0) if not o.startswith('-') else -int(o[1:],0))
    if o.startswith('dword ptr'):
        s=slot_of(o,deltas.get(k_push,0)); return ('slotval',s) if s else ('other',o)
    reg=o
    for j in reversed([x for x in seq if x<k_push]):
        mj,oj=ins[j][1],ins[j][2]
        if oj.startswith(reg+','):
            src=oj.split(', ',1)[1]
            if mj=='mov':
                if src=='dword ptr [eax]' and not any(ins[x][2].startswith('eax,') for x in seq if x<j):
                    b=(seq[0] if seq else k_push)-1
                    if ins[b][1]=='call' and ins[b][2]==hex(GETNAME):
                        a2,s2,d2=args_of_call(b); r=resolve(a2[0],s2,d2) if a2 else None
                        if r and r[0]=='slotaddr': return ('slotval',r[1])
                if src.startswith('dword ptr ['): 
                    s=slot_of(src,deltas[j]); 
                    if s: return ('slotval',s)
                    return ('other',src)
                if re.fullmatch(r'e[a-d]x|e[sd]i|ebp|ebx',src): reg=src; continue

                if src.startswith('0x'): return ('imm',int(src,16))
                return ('other',src)
            if mj=='lea':
                s=slot_of(src,deltas[j]); return ('slotaddr',s) if s else ('other',src)
            return ('other',mj+' '+oj)
    if reg=='eax':
        b=(seq[0] if seq else k_push)-1
        if ins[b][1]=='add' and ins[b][2].startswith('esp,') and ins[b-1][1]=='call': b-=1
        if ins[b][1]=='call' and ins[b][2] in (hex(GETNAME),hex(0x438f70),hex(0x439030),hex(0x443730)):
            a2,s2,d2=args_of_call(b); r=resolve(a2[0],s2,d2) if a2 else None
            if r and r[0]=='slotaddr': return r
        if ins[b][1]=='call' and ins[b][2] in (hex(ASSIGN),hex(0x4054e0)):
            a2,s2,d2=args_of_call(b); e=ecx_of_call(b,s2,d2)
            if e and e[0]=='slotaddr': return e
    if reg in ('ebx','esi','edi','ebp'):
        j=(seq[0] if seq else k_push)-1; f=fstart(ins[k_push][0]); n=0
        while j>=0 and ins[j][0]>=f and n<120:
            mj,oj=ins[j][1],ins[j][2]
            if oj.startswith(reg+',') or (mj=='pop' and oj==reg):
                if mj=='mov':
                    src=oj.split(', ',1)[1]
                    dj=fdeltas(fstart(ins[j][0])).get(j,0)
                    sl=slot_of(src,dj)
                    if sl: return ('slotval',sl)
                return ('other_far',mj+' '+oj)
            j-=1; n+=1
    return ('reg_outside_stmt',reg)
def args_of_call(k):
    """list of pushed arg indices (last push first = arg0) within statement"""
    seq,deltas,_=stmt_back(k)
    pushes=[j for j in seq if ins[j][1]=='push']
    return list(reversed(pushes)),seq,deltas
def ecx_of_call(k,seq,deltas):
    for j in reversed(seq):
        if ins[j][2].startswith('ecx,'):
            src=ins[j][2].split(', ',1)[1]
            if ins[j][1]=='lea': s=slot_of(src,deltas[j]); return ('slotaddr',s)
            if ins[j][1]=='mov' and re.fullmatch(r'e[a-d]x|e[sd]i|ebp|ebx',src):
                # follow reg
                for i2 in reversed([x for x in seq if x<j]):
                    if ins[i2][2].startswith(src+',') :
                        s2=ins[i2][2].split(', ',1)[1]
                        if ins[i2][1]=='lea': return ('slotaddr',slot_of(s2,deltas[i2]))
                        break
                return ('reg',src)
            return ('other',ins[j][2])
    return None

def cstr(va):
    o=va-0x400000; e=img.find(b'\0',o); return bytes(img[o:e]) if 0<=o<len(img) else None
def fmt_class(va):
    s=cstr(va)
    if s is None: return 'unknown'
    if s==b'%s': return 'bare'
    return 'ascii_fmt' if all(c<0x80 for c in s) else 'sentence'
SET_DLG=0x4ea69f; SET_WIN={0x4ea77e,0x4f657f}; SEND_DLG=0x4ea671
def vslot(k):
    m,o=ins[k][1],ins[k][2]
    if m!='call': return None
    mm=re.match(r'dword ptr \[(e[a-d]x|e[sd]i|ebp|ebx) \+ (0x[0-9a-f]+)\]$',o)
    if mm: return int(mm.group(2),16)
    if re.fullmatch(r'e[a-d]x|e[sd]i|ebp|ebx',o):
        for j in range(k-1,max(k-16,0),-1):
            mj,oj=ins[j][1],ins[j][2]
            if oj.startswith(o+','):
                mm=re.match(o+r', dword ptr \[(e[a-d]x|e[sd]i|ebp|ebx) \+ (0x[0-9a-f]+)\]$',oj)
                return int(mm.group(2),16) if mm and mj=='mov' else None
    return None

APPEND=0x405a20; CTOR=0x412010; PLUS=0x438f70; SETSTR=0x405990
NAMEY=('name','bare','appended')
def events_of(ks):
    ev=[]  # (k, dest_slot, kind, srcs, extra)
    for k in ks:
        a,m,o=ins[k]
        if m!='call': continue
        args,seq,d=args_of_call(k)
        R=[resolve(j,seq,d) for j in args]
        e=ecx_of_call(k,seq,d)
        ecx=e[1] if e and e[0]=='slotaddr' else None
        if o==hex(GETNAME) and R and R[0][0]=='slotaddr': ev.append((k,R[0][1],'name',[],None)); continue
        if o==hex(ASSIGN) and ecx: ev.append((k,ecx,'copy',[R[0][1]] if R and R[0][0]=='slotaddr' else [],None)); continue
        if o==hex(APPEND) and ecx: ev.append((k,ecx,'append',[R[0][1]] if R and R[0][0]=='slotval' else [],None)); continue
        if o==WSPRINTF and R and R[0][0]=='slotaddr':
            fc=fmt_class(R[1][1]) if len(R)>1 and R[1][0]=='imm' else 'unknown'
            ev.append((k,R[0][1],'fmt',[r[1] for r in R[2:] if r[0] in('slotval','slotaddr')],fc)); continue
        if o==hex(CTOR) and ecx: ev.append((k,ecx,'copy',[R[0][1]] if R and R[0][0]=='slotaddr' else [],None)); continue
        if o==hex(PLUS) and R and R[0][0]=='slotaddr': ev.append((k,R[0][1],'plus',[r[1] for r in R[1:] if r[0]=='slotaddr'],None)); continue
        if o==hex(0x4054e0) and ecx: ev.append((k,ecx,'copy',[R[0][1]] if R and R[0][0]=='slotaddr' else [],None)); continue
        if o==hex(0x439030) and R and R[0][0]=='slotaddr': ev.append((k,R[0][1],'plus',[R[1][1]] if len(R)>1 and R[1][0]=='slotaddr' else [],None)); continue
        if o==hex(0x443730) and R and R[0][0]=='slotaddr': ev.append((k,R[0][1],'plus',[R[2][1]] if len(R)>2 and R[2][0]=='slotaddr' else [],None)); continue
        if o in (hex(0x404f20),hex(0x405500)): continue
        if ecx and o!=hex(GETNAME): ev.append((k,ecx,'other',[],None))

    return ev
def state(ev,slot,k,depth=0):
    if depth>8: return None
    best=None
    for e in ev:
        if e[0]<k and e[1]==slot and (best is None or e[0]>best[0]): best=e
    if not best: return None
    _,_,kind,srcs,extra=best
    if kind=='name': return 'name'
    if kind in('other','other_arg'): return None
    ss=[state(ev,s,best[0],depth+1) for s in srcs]
    if kind=='copy': return ss[0] if ss else None
    if kind=='append': return 'appended' if ss and ss[0] in NAMEY else None
    if kind=='fmt':
        if any(x in NAMEY for x in ss): return 'bare' if extra=='bare' and len(srcs)==1 else 'composite'
        if any(x=='composite' for x in ss): return 'composite'
        return None
    if kind=='plus': return 'composite' if any(x in NAMEY+('composite',) for x in ss) else None
def analyze(f):
    ks=funcs[f]
    EBP_FRAME[0]=any(ins[k][1]=='mov' and ins[k][2]=='ebp, esp' for k in ks[:6])
    ev=events_of(ks)
    getname=[hex(ins[e[0]][0]) for e in ev if e[2]=='name']
    sinks=[]
    for k in ks:
        a,m,o=ins[k]
        if m!='call': continue
        api=None
        s=vslot(k)
        if s in SL: api,ti=SL[s]
        elif o==hex(SET_DLG): api,ti='SetDlgItemText',1
        elif o.startswith('0x') and int(o,16) in SET_WIN: api,ti='SetWindowText',0
        elif o==hex(SEND_DLG): api,ti='SendDlgItemMessage',3
        if api is None: continue
        args,seq,d=args_of_call(k)
        if ti>=len(args): sinks.append(dict(va=hex(a),api=api,tag='unresolved')); continue
        r=resolve(args[ti],seq,d)
        t=state(ev,r[1],k) if r[0] in('slotval','slotaddr') and r[1] else None
        xy=None
        if api in('TextOut','ExtTextOut','TabbedTextOut'):
            xy=[resolve(args[i],seq,d) for i in (0,1)]; xy=[v[1] if v[0]=='imm' else None for v in xy]
        msg=None
        if api=='SendDlgItemMessage':
            mr=resolve(args[1],seq,d); msg=mr[1] if mr[0]=='imm' else None
        sinks.append(dict(va=hex(a),api=api,tag=t or ('unresolved' if r[0].startswith('reg') else 'other'),xy=xy,msg=msg))
    return getname,sinks


MANUAL = {
    # 0x48f220: slot = fresh empty CString (StringMgr nil via vtable+0xc) then Append(name)
    '0x48f464': ('bare', 'empty+append(name)'), '0x48f484': ('bare', 'empty+append(name)'),
    # 0x4d77a0 / 0x4dbcb0 footer: default ctor 0x405490, then Append(name) when the index
    # != -1, else Append(literal placeholder 0x52f80c) on the same slot (branch join)
    '0x4d9729': ('bare', 'empty+append(name)|placeholder'), '0x4d98e1': ('bare', 'empty+append(name)|placeholder'),
    '0x4ddcd9': ('bare', 'empty+append(name)|placeholder'), '0x4dde91': ('bare', 'empty+append(name)|placeholder'),
}
REGS = ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi', 'ebp')


def jump_targets(f):
    out = set()
    for k in funcs[f]:
        m, o = ins[k][1], ins[k][2]
        if m.startswith('j') and o.startswith('0x'):
            out.add(int(o, 16))
    return out


def install_plan(va, raw_img):
    """5-byte vtable-pair replacement check for one TextOut call site."""
    k = idx[va]
    call_reg = ins[k][2]
    if call_reg not in REGS:
        return dict(kind='manual', reason='call_not_register')
    f = fstart(va)
    j = k - 1
    cdc = None
    while j > k - 12:
        if ins[j][1] == 'mov' and ins[j][2].startswith('ecx, ') and cdc is None:
            cdc = ins[j][2].split(', ')[1]
        mm = re.fullmatch(r'(e\w\w), dword ptr \[(e\w\w) \+ 0x5c\]', ins[j][2])
        if ins[j][1] == 'mov' and mm and mm.group(1) == call_reg:
            break
        j -= 1
    else:
        return dict(kind='manual', reason='no_slot_load')
    r1 = mm.group(2)
    p = j - 1
    first_ok = ins[p][1] == 'mov' and ins[p][2] == f'{r1}, dword ptr [{cdc}]'
    pair_start = ins[p][0] if first_ok else ins[j][0]
    pair_len = (ins[j + 1][0] - ins[p][0]) if first_ok else None
    between = [ins[x] for x in range(j + 1, k)]
    r1_read = any(r1 in o.split(', ', 1)[-1] or (m == 'push' and o == r1) for _, m, o in between
                  if not o.startswith(r1 + ','))
    tg = [t for t in jump_targets(f) if pair_start < t <= va]
    ok = first_ok and pair_len == 5 and not r1_read and not tg and r1 in ('eax', 'ecx', 'edx')
    d = dict(kind='pair5' if ok else 'manual', pair_va=hex(pair_start), slot_load_va=hex(ins[j][0]),
             cdc_reg=cdc, call_reg=call_reg, adjacent=first_ok, r1_read_before_call=r1_read,
             branch_targets_inside=len(tg))
    if ok:
        d['orig_sha256_8'] = hashlib.sha256(bytes(raw_img[pair_start - 0x400000:pair_start - 0x400000 + 5])).hexdigest()[:8]
    elif not first_ok:
        d['reason'] = 'pair_not_adjacent'
    return d


def run(pe):
    init(pe)
    out = {}
    for f in sorted(funcs):
        g, s = analyze(f)
        for x in s:
            if x['va'] in MANUAL:
                x['tag'], x['manual'] = MANUAL[x['va']]
        hits = [x for x in s if x['tag'] in NAMEY + ('composite',)]
        if g or hits:
            out[hex(f)] = dict(getname=g, name_sinks=hits, text_sinks=len(s),
                               unresolved=sum(1 for x in s if x['tag'] == 'unresolved'))
    for v in out.values():
        for x in v['name_sinks']:
            if x['api'] == 'TextOut' and x['tag'] in NAMEY:
                x['install'] = install_plan(int(x['va'], 16), img)
    return out


def summarize(out, sha):
    c = collections.Counter((x['api'], 'whole' if x['tag'] in NAMEY else x['tag'])
                            for v in out.values() for x in v['name_sinks'])
    tex = [dict(function=f, va=x['va'], xy=x['xy'], tag=x['tag'], install=x.get('install'))
           for f, v in out.items() for x in v['name_sinks'] if x['api'] == 'TextOut']
    lists = [dict(function=f, va=x['va'], api=x['api'], msg=x.get('msg'), tag=x['tag'])
             for f, v in out.items() for x in v['name_sinks'] if x['api'] != 'TextOut']
    return dict(
        milestone='m062->m063', kind='name_draw_sites', source_sha256=sha,
        getname_caller_functions=len(out),
        functions_with_name_sink=sum(1 for v in out.values() if v['name_sinks']),
        counts={f'{a}:{t}': n for (a, t), n in sorted(c.items())},
        textout_whole_name_sites=sum(1 for t in tex if t['tag'] in NAMEY),
        textout_pair5_installable=sum(1 for t in tex if (t['install'] or {}).get('kind') == 'pair5'),
        textout_manual_install=sum(1 for t in tex if (t['install'] or {}).get('kind') == 'manual'),
        textout_sites=tex, other_sites=lists,
        namepair_v3_covers=False,
        namepair_v3_reason='fixed (57,21)/(56,21), id=stored_id, flags 0 (no full_any, no join)',
        proposed_helper='@LD2_NameTextOut@24', production_can_apply=False, release_approved=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--json-out', type=Path)
    a = ap.parse_args()
    exe = Path(os.environ['LD2_TEST_EXE'])
    raw = exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if not sha.startswith(T.PRISTINE_SHA256_PREFIX):
        sys.exit('not the pristine Ld95.exe')
    summ = summarize(run(pefile.PE(data=raw)), sha)
    txt = json.dumps(summ, indent=1, ensure_ascii=True)
    if a.json_out:
        a.json_out.write_text(txt + '\n')
    print(json.dumps({k: summ[k] for k in ('getname_caller_functions', 'functions_with_name_sink', 'counts',
                      'textout_whole_name_sites', 'textout_pair5_installable', 'textout_manual_install')}))


if __name__ == '__main__':
    main()
