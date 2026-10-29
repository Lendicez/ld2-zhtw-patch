"""Lab-only (m062): build v3 inert ("disabled") + enabled images in memory from m045 with the
hash-locked MSVC name_pair_v3.obj + list_insert_v3.obj sharing one v3 catalog blob, and verify
them statically (object audits, independent fixup re-derivation, binding-target readback,
indirect-call scan with EBP-spill tracking, m061 hook/site/checksum checks, pefile).
Writes only JSON to stdout (and optional lab deltas via make_v3_delta.py). Never writes an EXE.
production_can_apply=false, release_approved=false.

  ~/venv-ld2/bin/python -I -B build_v3_lab.py [--catalog reviewed|lab_preview] [--modes 2,0]
"""
import argparse, hashlib, json, os, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'm061'))
sys.path.insert(0, str(HERE))
import merge_plan_v3 as mv, merge_plan as mp, enable_plan as ep, site_plan, import_builder as ib, coff_obj  # noqa: E402
import build_enabled_lab as bl  # noqa: E402
import rehearse_v3_objs as rv, audit_name_pair_v3 as anp  # noqa: E402
import capstone, pefile  # noqa: E402

LAB = HERE.parents[1]; ROOT = LAB.parent
OBJ_DIR = Path(os.environ.get('LD2_M062_OBJ_DIR', HERE / 'compile-return-run1'))
M051 = ROOT / 'ld2-zhtw-patch-m051/research/translations/m051-items.zh-TW.json'
MINA = ROOT / 'mina-translation/m061-consumables-adventurers.zh-TW.json'
MINA_SHA = '477edfbaa16fb8ca74672fcec8006986fbd90f49dae7bd89fc95702454e14ec1'
BASE = 0x400000
DATA_ONLY = ('_LD2_Catalog', '_LD2_CatalogBytes', '_LD2_ListMode', '_LD2_ExpectedTextOutA', '___security_cookie')


def sha(b): return hashlib.sha256(b).hexdigest()


def inputs(catalog='reviewed'):
    o = (LAB / 'baseline/pristine/Ld95.exe').read_bytes()
    m = (LAB / 'runs/m045/build-first/Ld95.exe').read_bytes()
    no, lo = (OBJ_DIR / 'name_pair_v3.obj').read_bytes(), (OBJ_DIR / 'list_insert_v3.obj').read_bytes()
    cats = [(M051.read_bytes(), mv.M051_SHA)]
    if catalog == 'lab_preview':
        cats.append((MINA.read_bytes(), MINA_SHA))
    blob, binfo = mv.build_blob(o, cats, policy=catalog)
    return o, m, no, lo, blob, binfo


def build(mode=2, catalog='reviewed', pre=None):
    o, m, no, lo, blob, binfo = pre or inputs(catalog)
    inert, rep = mv.build_inert_v3(o, m, no, lo, blob, list_mode=mode)
    sites = site_plan.load_sites((HERE.parent / 'm061/list_sites.json').read_bytes())
    en, erep = ep.apply_enabled(inert, int(rep['entry_va'], 16), int(rep['list_entry_va'], 16), sites)
    rep['catalog_build'] = binfo
    return o, m, inert, rep, en, erep


def object_audits(no, lo):
    rv.install_profile()
    lrep = rv.audit_list_obj.audit(lo, 'v3')
    assert lrep['esp_and_nonvolatile_preserved_on_normal_paths']
    nrep = anp.audit(no)
    assert nrep['object_sha256'] == mv.NAME_V3_OBJECT_SHA256
    return dict(list_normal_cfg_states=lrep['normal_cfg_states'], list_binding_spills=[list(s) for s in lrep['binding_spills']],
                name_functions=sorted(nrep['functions']))


def fixup_audit(img, raw, code_va, bindings):
    """Independently re-derive every relocation field from the object and compare with the image."""
    obj = coff_obj.parse(raw)
    offsets, length = coff_obj.layout(obj)
    view = ib.View(img)
    code = view.read(code_va - BASE, length)
    seen = {}
    n = 0
    for s in coff_obj.code_sections(obj):
        for r in s['rel']:
            at = offsets[s['index']] + r['offset']
            sym = obj['symbols'][r['symbol']]
            tgt = bindings[sym['name']] if sym['section'] == 0 else code_va + offsets[sym['section']] + sym['value']
            add = struct.unpack_from('<i' if r['type'] == coff_obj.REL_REL32 else '<I', s['data'], r['offset'])[0]
            got = struct.unpack_from('<i' if r['type'] == coff_obj.REL_REL32 else '<I', code, at)[0]
            exp = tgt + add - (code_va + at + 4) if r['type'] == coff_obj.REL_REL32 else (tgt + add) & 0xffffffff
            assert got == exp, (hex(code_va + at), sym['name'])
            if sym['section'] == 0:
                seen[sym['name']] = seen.get(sym['name'], 0) + 1
            n += 1
        # non-fixup bytes must equal the object bytes
        fields = {r['offset'] + k for r in s['rel'] for k in range(4)}
        blk = code[offsets[s['index']]:offsets[s['index']] + len(s['data'])]
        assert all(blk[i] == s['data'][i] for i in range(len(blk)) if i not in fields), 'code bytes drift'
    assert set(seen) == set(bindings), sorted(set(bindings) - set(seen))
    return dict(fixups=n, external_refs=seen)


def binding_targets(img, rep):
    view = ib.View(img)
    rd = lambda va: struct.unpack('<I', view.read(int(va, 16) - BASE, 4))[0]
    b, nb = rep['list_bindings'], rep['bindings']
    for k, api in (('_LD2_IsWindowUnicode', 'IsWindowUnicode'), ('_LD2_GetWindowLongW', 'GetWindowLongW'),
                   ('_LD2_GetClassLongW', 'GetClassLongW'), ('_LD2_SetWindowLongW', 'SetWindowLongW'),
                   ('_LD2_SendDlgItemMessageW', 'SendDlgItemMessageW'), ('_LD2_GetDlgItem', 'GetDlgItem')):
        assert mp.iat_name(view, int(b[k], 16) - BASE) == ('USER32.dll', api), k
    assert mp.iat_name(view, int(b['_LD2_MultiByteToWideChar'], 16) - BASE) == ('KERNEL32.dll', 'MultiByteToWideChar')
    assert mp.iat_name(view, int(nb['_LD2_TextOutW'], 16) - BASE) == ('GDI32.dll', 'TextOutW')
    for k in ('_LD2_Catalog', '_LD2_CatalogBytes', '___security_cookie', '@__security_check_cookie@4'):
        assert b[k] == nb[k], k   # ONE shared catalog blob/size word
    dlg = rd(b['_LD2_OriginalDlgItem'])
    assert dlg == mp.WRAPPER_VA != 0, 'OriginalDlgItem must be non-zero'
    assert rd(b['_LD2_ListMode']) == rep['list_mode']
    assert rd(nb['_LD2_ExpectedTextOutA']) == mp.TEXTOUTA_HELPER_VA
    nbytes = rd(b['_LD2_CatalogBytes'])
    blob = view.read(int(b['_LD2_Catalog'], 16) - BASE, nbytes)
    assert sha(blob) == rep['blob_sha256'] and nbytes == rep['capacity']['blob_bytes']
    return dict(original_dlgitem_value=hex(dlg), list_mode=rd(b['_LD2_ListMode']), catalog_bytes=nbytes,
                blob_sha256=sha(blob), shared_catalog=True)


def indirect_calls(img, rep):
    """Linear scan of the relocated list helper: every indirect call must load from a function
    binding slot (directly, via a register loaded from it, or via an EBP stack slot spilled from
    such a register). Data-only bindings must never be call targets."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    view = ib.View(img)
    out = {}
    for label, start, nbytes, bind in (('list', rep['list_code_va'], rep['list_details']['code_bytes'], rep['list_bindings']),
                                       ('name', rep['name_code_va'], rep['name_details']['code_bytes'], rep['bindings'])):
        start = int(start, 16)
        fn = {int(v, 16) for k, v in bind.items() if k not in DATA_ONLY}
        data = {int(bind[k], 16) for k in DATA_ONLY if k in bind}
        reg, slot, seen, other = {}, {}, set(), []
        for i in md.disasm(view.read(start - BASE, nbytes), start):
            op, mn = i.op_str, i.mnemonic
            dst = op.split(',')[0].strip()
            if mn == 'mov' and ', dword ptr [0x' in op:
                reg[dst] = int(op.split('[')[1][:-1], 16)
                continue
            if mn == 'mov' and dst.startswith('dword ptr [ebp - 0x'):
                src = op.split(',')[1].strip()
                slot[dst] = reg.get(src)
                continue
            if mn == 'lea' and '[ebp - 0x' in op:
                slot.pop('dword ptr [' + op.split('[')[1], None)
            if mn == 'call':
                if op.startswith('dword ptr [0x'):
                    t = int(op[len('dword ptr ['):-1], 16)
                elif op in reg:
                    t = reg[op]
                elif op in slot:
                    t = slot[op]
                elif op.startswith('0x'):
                    continue  # direct call (internal or __security_check_cookie)
                else:
                    other.append(f'{i.address:#x} call {op}')
                    continue
                assert t is not None and t not in data, f'{label}: data binding used as call target at {i.address:#x}'
                if t in fn:
                    seen.add(t)
                else:
                    other.append(f'{i.address:#x} call {op} <- {t:#x}')
            if dst in reg and mn not in ('cmp', 'test', 'push', 'call'):
                reg.pop(dst, None)
        out[label] = dict(binding_slots_called=sorted(map(hex, seen)), other_indirect=other)
    assert not out['list']['other_indirect'], out['list']['other_indirect']
    # NamePair: exactly one register call = LD2_OriginalOne's `call eax` into the original virtual method (object-audited)
    assert len(out['name']['other_indirect']) == 1 and out['name']['other_indirect'][0].endswith('call eax'), out['name']
    return out


def verify(o, inert, rep, en, erep, no, lo):
    r = bl.verify(o, inert, rep, en, erep)   # m061 hook stub / 8 sites / checksum / OriginalDlgItem & ExpectedTextOutA slots
    r['object_audits'] = object_audits(no, lo)
    r['fixups_name'] = fixup_audit(en, no, int(rep['name_code_va'], 16), {k: int(v, 16) for k, v in rep['bindings'].items()})
    r['fixups_list'] = fixup_audit(en, lo, int(rep['list_code_va'], 16), {k: int(v, 16) for k, v in rep['list_bindings'].items()})
    r['binding_targets'] = binding_targets(en, rep)
    r['indirect_calls'] = indirect_calls(en, rep)
    pe = pefile.PE(data=en)
    assert pe.verify_checksum()
    imps = {(d.dll.decode(), (i.name or b'').decode()) for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports}
    base_imps = {(d.dll.decode(), (i.name or b'').decode()) for d in pefile.PE(data=o).DIRECTORY_ENTRY_IMPORT for i in d.imports}
    new = sorted(f'{a}!{b}' for a, b in imps - base_imps)
    forbidden = [x for x in new if x.split('!')[1] in ('SetWindowLongA', 'CallWindowProcW', 'CallWindowProcA', 'SetWindowsHookExW',
                 'SetWindowsHookExA', 'VirtualProtect', 'LoadLibraryW', 'LoadLibraryA', 'GetProcAddress', 'SetClassLongW', 'SetClassLongA')]
    assert not forbidden, forbidden
    r['new_imports_vs_pristine'] = new
    # inert really is inert: no site/hook change relative to candidate
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default='reviewed', choices=sorted(mv.POLICIES))
    ap.add_argument('--modes', default='2,0')
    a = ap.parse_args()
    pre = inputs(a.catalog)
    out = dict(catalog=a.catalog, name_object_sha256=mv.NAME_V3_OBJECT_SHA256, list_object_sha256=mv.LIST_V3_OBJECT_SHA256,
               production_can_apply=False, release_approved=False, modes={})
    for mode in map(int, a.modes.split(',')):
        o, m, inert, rep, en, erep = build(mode, a.catalog, pre)
        v = verify(o, inert, rep, en, erep, pre[2], pre[3])
        out['blob_sha256'] = rep['blob_sha256']; out['capacity'] = rep['capacity']; out['catalog_build'] = rep['catalog_build']
        out['catalog_section'] = rep['catalog_section']
        out['modes'][str(mode)] = dict(inert_sha256=sha(inert), enabled_sha256=sha(en), size=len(en),
                                       entry_va=rep['entry_va'], list_entry_va=rep['list_entry_va'],
                                       list_mode_slot_va=rep['list_mode_slot_va'], original_dlgitem_slot_va=rep['original_dlgitem_slot_va'],
                                       hook_stub_sha256=erep['hook_stub_sha256'], changed_bytes_inert_to_enabled=erep['changed_bytes'],
                                       verify=v)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
