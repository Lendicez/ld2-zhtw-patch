"""m063d lab-only: m045 -> v4 ENABLED image deltas for the Win11 enable/acceptance handoff
(schema m063d-v4-enabled-delta/1). The INERT image is derived from the enabled one on Win11 by putting the
m045 bytes back into every enable window and writing the inert PE CheckSum (both pinned in the manifest),
so one delta serves the inert-first launch and the enabled launch.
Writes ONLY into --out (default HERE/lab-deltas; must not be inside a git checkout: the .bin carries
game-derived catalog bytes and helper code). No EXE is written. Every delta is re-applied in Python and
must reproduce both images bit-for-bit.

  ~/venv-ld2/bin/python -I -B make_v4_delta.py [--catalog lab_preview|reviewed] [--modes 2,0] [--out DIR]
"""
import argparse, hashlib, json, struct, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_v4_lab as bv  # noqa: E402

SCHEMA = 'm063d-v4-enabled-delta/1'


def sha(b): return hashlib.sha256(b).hexdigest()


def runs_for(m, x, wins):
    hdr = []
    for i in (i for i in range(0x1000) if m[i] != x[i]):
        if hdr and i - hdr[-1][1] <= 8: hdr[-1][1] = i + 1
        else: hdr.append([i, i + 1])
    code = [[a, b] for a, b, _ in wins]
    covered = set()
    for a, b in hdr + code: covered |= set(range(a, b))
    diff = {i for i in range(len(m)) if m[i] != x[i]}
    assert diff <= covered, sorted(diff - covered)[:10]
    kinds = {(a, b): k for a, b, k in wins}
    return [dict(offset=a, length=b - a, kind='header') for a, b in hdr] + \
           [dict(offset=a, length=b - a, kind='code', site=kinds[(a, b)]) for a, b in code] + \
           [dict(offset=len(m), length=len(x) - len(m), kind='append')]


def apply(m, runs, blob):
    out, p = bytearray(m), 0
    for r in runs:
        chunk = blob[p:p + r['length']]; p += r['length']
        if r['kind'] == 'append':
            assert r['offset'] == len(out); out += chunk
        else:
            out[r['offset']:r['offset'] + r['length']] = chunk
    assert p == len(blob)
    return bytes(out)


def derive_inert(m, x, runs, co, ck):
    out = bytearray(x)
    for r in runs:
        if r['kind'] == 'code':
            out[r['offset']:r['offset'] + r['length']] = m[r['offset']:r['offset'] + r['length']]
    struct.pack_into('<I', out, co, ck)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default='lab_preview', choices=('lab_preview', 'reviewed'))
    ap.add_argument('--modes', default='2,0')
    ap.add_argument('--out', type=Path, default=HERE / 'lab-deltas')
    a = ap.parse_args()
    out = a.out.resolve()
    inside_git = subprocess.run(['git', '-C', str(out.parent if not out.exists() else out), 'rev-parse'], capture_output=True).returncode == 0
    assert not inside_git, f'{out} is inside a git checkout; deltas must stay lab-local'
    out.mkdir(parents=True, exist_ok=True)
    modes = [int(x) for x in a.modes.split(',')]
    summary, pre, built = bv.run(a.catalog, modes)
    m = pre[1]
    res = {}
    for mode in modes:
        inert, rep, x, erep = built[mode]
        wins = bv.windows(erep)
        v = summary['modes'][str(mode)]['verify']
        runs = runs_for(m, x, wins)
        blob = b''.join(x[r['offset']:r['offset'] + r['length']] for r in runs)
        for r in runs: r['sha256'] = sha(x[r['offset']:r['offset'] + r['length']])
        assert apply(m, runs, blob) == x
        co, ck = v['checksum_offset'], int(v['checksum_inert'], 16)
        assert derive_inert(m, x, runs, co, ck) == inert
        stem = f'm063d-v4-{a.catalog}-mode{mode}'
        man = dict(schema=SCHEMA, base='m045', base_sha256=sha(m), base_size=len(m),
                   catalog_policy=a.catalog, release_eligible_catalog=summary['release_eligible_catalog'],
                   catalog_version=4, catalog_rows=rep['capacity']['rows'], blob_sha256=rep['blob_sha256'],
                   blob_bytes=rep['capacity']['blob_bytes'], list_mode=mode, list_mode_slot_va=rep['list_mode_slot_va'],
                   original_dlgitem_slot_va=rep['original_dlgitem_slot_va'], original_dlgitem_value='0x4ea671',
                   name_object_sha256=rep['name_object_sha256'], list_object_sha256=rep['list_object_sha256'],
                   textout_object_sha256=rep['textout_object_sha256'],
                   entry_va=rep['entry_va'], list_item_entry_va=rep['list_item_entry_va'],
                   list_name_entry_va=rep['list_name_entry_va'], textout_entry_va=rep['textout_entry_va'],
                   code_range=rep['code_range'], code_sha256=rep['code_sha256'],
                   hook_stub_sha256=erep['hook_stub_sha256'], counts=erep['counts'],
                   inert_sha256=sha(inert), inert_checksum_offset=co, inert_checksum=hex(ck),
                   out_sha256=sha(x), out_size=len(x), size_of_image=v['size_of_image'],
                   delta_file=f'{stem}.delta.bin', delta_sha256=sha(blob), delta_size=len(blob),
                   runs=runs, hook_enabled=True, list_sites_retargeted=True, textout_sites_patched=True,
                   handoff_eligible=rep['handoff_eligible'], production_can_apply=False, release_approved=False)
        (out / f'{stem}.delta.bin').write_bytes(blob)
        raw = (json.dumps(man, indent=2, ensure_ascii=False) + '\n').encode()
        (out / f'{stem}.delta.json').write_bytes(raw)
        res[stem] = dict(inert_sha256=man['inert_sha256'], enabled_sha256=man['out_sha256'], out_size=len(x),
                         delta_sha256=man['delta_sha256'], delta_size=len(blob), delta_json_sha256=sha(raw),
                         runs=len(runs), code_runs=sum(r['kind'] == 'code' for r in runs),
                         header_runs=sum(r['kind'] == 'header' for r in runs))
    print(json.dumps(dict(schema=SCHEMA, catalog=a.catalog, out_dir_is_lab_local=True, deltas=res,
                          production_can_apply=False, release_approved=False), indent=1))


if __name__ == '__main__':
    main()
