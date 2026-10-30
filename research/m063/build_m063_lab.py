"""Lab-only (m063a): build the three-helper inert + enabled images in memory from m045 and verify
them statically. NameTextOut is a Linux clang REHEARSAL object (temp dir, never pinned/committed)
until m063b returns the MSVC object; the report is marked rehearsal=True / handoff_eligible=False.
Writes only JSON to stdout. Never writes an EXE. production_can_apply=false, release_approved=false.

  ~/venv-ld2/bin/python -I -B build_m063_lab.py [--catalog reviewed|lab_preview] [--modes 2,0]
                                                [--textout-obj X.obj --textout-sha256 H]
"""
import argparse, hashlib, json, os, struct, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE.parent / 'm062'))
sys.path.insert(0, str(HERE))
import build_v3_lab as b3, merge_plan_m063 as mm, enable_plan_m063 as em  # noqa: E402
import rehearse_list_obj, coff_obj, import_builder as ib, site_plan  # noqa: E402
import audit_name_textout as ant  # noqa: E402
import capstone, pefile  # noqa: E402

BASE = 0x400000
SUMMARY = HERE.parent / 'm062/name_draw_sites.summary.json'
LIST_SITES = HERE.parent / 'm061/list_sites.json'


def sha(b): return hashlib.sha256(b).hexdigest()


rehearsal_textout_obj = ant.rehearsal_textout_obj


def build(mode, pre, tobj, tpin):
    o, m, no, lo, blob, binfo = pre
    inert, rep = mm.build_inert_m063(o, m, no, lo, tobj, blob, list_mode=mode, textout_pin=tpin)
    cr = tuple(int(x, 16) for x in rep['code_range'])
    en, erep = em.apply_enabled_m063(inert, int(rep['entry_va'], 16), int(rep['list_entry_va'], 16),
                                     int(rep['textout_entry_va'], 16), cr, LIST_SITES.read_bytes(), SUMMARY.read_bytes())
    rep['catalog_build'] = binfo
    return o, m, inert, rep, en, erep


def textout_site_checks(o, inert, en, rep, erep):
    """Disassemble every patched TextOut window in the enabled image; branch-target scans on the original."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    tva = int(rep['textout_entry_va'], 16)
    rows, tail = em.load_textout_sites(SUMMARY.read_bytes())
    out = []
    windows = []
    for r in rows:
        a, c = r['pair_va'], r['call_va']
        new = list(md.disasm(en[a - BASE:c + 2 - BASE], a))
        old = list(md.disasm(o[a - BASE:c + 2 - BASE], a))
        assert (new[0].mnemonic, new[0].op_str) == ('mov', f"{r['r2']}, {hex(tva)}"), (hex(a), new[0].op_str)
        assert new[0].size == 5 and new[1].address == old[2].address
        assert [(i.mnemonic, i.op_str) for i in new[1:]] == [(i.mnemonic, i.op_str) for i in old[2:]], hex(a)
        assert (new[-2].mnemonic, new[-2].op_str, new[-1].mnemonic, new[-1].op_str) == ('mov', f"ecx, {r['cdc']}", 'call', r['r2'])
        # R2 (now = helper VA) must not be written between the rewrite and the call; ECX = cdc at the call
        for i in new[1:-1]:
            _, w = i.regs_access()
            assert r['r2'] not in {i.reg_name(x) for x in w}, (hex(i.address), r['r2'])
        pushes = sum(1 for i in new[1:-1] if i.mnemonic == 'push')
        assert pushes == 4, (hex(a), pushes)           # x, y, s, n -> helper ret 16
        windows.append((a, a + 5))
        out.append(dict(pair_va=hex(a), call_va=hex(c), new=f'mov {r["r2"]}, {hex(tva)}', pushes=pushes))
    s = tail['start_va']
    new = list(md.disasm(en[s - BASE:s + 8 - BASE], s))
    assert [(i.mnemonic, i.op_str) for i in new] == [('push', 'ecx'), ('mov', 'ecx, esi'), ('call', hex(tva))], new
    assert new[-1].address + new[-1].size == tail['ret_va']
    old = list(md.disasm(o[s - 0x20 - BASE:s + 8 - BASE], s - 0x20))
    windows.append((s, s + 8))
    out.append(dict(tail8_va=hex(s), call_va=hex(tail['call_va']), new='push ecx; mov ecx, esi; call ' + hex(tva)))
    # branch targets into any patched window interior: rel32 raw scan of .text + per-function linear disasm
    text = o[0x1000:0x124c39]
    hits = []
    interior = set()
    for a, b in windows:
        interior |= set(range(a + 1, b))
    for k in range(len(text) - 6):
        op = text[k]
        if op in (0xE8, 0xE9):
            t = 0x401000 + k + 5 + struct.unpack_from('<i', text, k + 1)[0]
        elif op == 0x0F and 0x80 <= text[k + 1] <= 0x8F:
            t = 0x401000 + k + 6 + struct.unpack_from('<i', text, k + 2)[0]
        else:
            continue
        if t in interior:
            hits.append(f'rel32@{0x401000 + k:#x}->{t:#x}')
    md2 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    funcs = sorted({int(t['function'], 16) for t in json.loads(SUMMARY.read_text())['textout_sites']})
    for f in funcs:
        for i in md2.disasm(o[f - BASE:f - BASE + 0x2800], f):
            if (i.mnemonic.startswith('j') or i.mnemonic in ('call', 'loop')) and i.op_str.startswith('0x'):
                if int(i.op_str, 16) in interior:
                    hits.append(f'{i.address:#x} {i.mnemonic} {i.op_str}')
    # absolute DWORDs pointing into the windows (jump tables / EH)
    abs_hits = [k for k in range(0, len(o) - 4) if struct.unpack_from('<I', o, k)[0] in interior]
    # rel32 raw scanning has false positives in data; only report confirmed instruction-level hits
    return dict(sites=out, windows=len(windows), branch_hits=hits, abs_dword_hits=len(abs_hits))


def verify(o, inert, rep, en, erep, no, lo, tobj):
    r = b3.verify(o, inert, rep, en, erep, no, lo)   # m061/m062 checks: hook stub, 18 list sites, objects, fixups, bindings
    r['fixups_textout'] = b3.fixup_audit(en, tobj, int(rep['textout_code_va'], 16), {k: int(v, 16) for k, v in rep['textout_bindings'].items()})
    assert rep['textout_bindings'] == rep['bindings'], 'textout must share NamePair bindings'
    r['textout_audit'] = {k: v for k, v in ant.audit(tobj).items() if k in ('object_sha256', 'entry', 'cookie_noreturn_tails',
                                                                         'esp_and_nonvolatile_preserved_on_normal_paths')}
    r['textout_sites'] = textout_site_checks(o, inert, en, rep, erep)
    assert not r['textout_sites']['branch_hits'], r['textout_sites']['branch_hits']
    assert len(erep['sites']) == 18 and erep['counts'] == dict(pair5=25, tail8=1, list_sites=18)
    # every enabled-image difference vs inert is inside hook/sites/checksum (enable plan asserts) and .ld2t is untouched
    cr = [int(x, 16) for x in rep['code_range']]
    v1, v2 = ib.View(inert), ib.View(en)
    assert v1.read(cr[0] - BASE, cr[1] - cr[0]) == v2.read(cr[0] - BASE, cr[1] - cr[0])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default='reviewed', choices=sorted(b3.mv.POLICIES))
    ap.add_argument('--modes', default='2,0')
    ap.add_argument('--textout-obj', type=Path)
    ap.add_argument('--textout-sha256')
    a = ap.parse_args()
    if a.textout_obj:
        tobj = a.textout_obj.read_bytes(); tpin = a.textout_sha256 or mm.TEXTOUT_OBJECT_SHA256
    else:
        tobj = rehearsal_textout_obj(); tpin = sha(tobj)
    pre = b3.inputs(a.catalog)
    out = dict(milestone='m063a', catalog=a.catalog, textout_object_sha256=tpin,
               textout_rehearsal=tpin != mm.TEXTOUT_OBJECT_SHA256, production_can_apply=False, release_approved=False, modes={})
    for mode in map(int, a.modes.split(',')):
        o, m, inert, rep, en, erep = build(mode, pre, tobj, tpin)
        v = verify(o, inert, rep, en, erep, pre[2], pre[3], tobj)
        out['blob_sha256'] = rep['blob_sha256']; out['capacity'] = rep['capacity']; out['slots'] = rep['slots']
        out['modes'][str(mode)] = dict(inert_sha256=sha(inert), enabled_sha256=sha(en), size=len(en),
                                       entry_va=rep['entry_va'], list_entry_va=rep['list_entry_va'], textout_entry_va=rep['textout_entry_va'],
                                       code_range=rep['code_range'], changed_bytes_inert_to_enabled=erep['changed_bytes'],
                                       counts=erep['counts'], handoff_eligible=rep['handoff_eligible'],
                                       textout_fixups=v['fixups_textout'], textout_audit=v['textout_audit'],
                                       textout_site_windows=v['textout_sites']['windows'],
                                       branch_hits=len(v['textout_sites']['branch_hits']),
                                       abs_dword_hits_into_windows=v['textout_sites']['abs_dword_hits'],
                                       pefile_checksum_ok=v['pefile_checksum_ok'], new_imports_vs_pristine=v['new_imports_vs_pristine'])
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
