"""Lab-only (m062): m045 -> v3 enabled image deltas (schema m062-v3-enabled-delta/1).
Writes ONLY into research/m062/lab-deltas/ (never committed: contains game-derived catalog bytes).
No EXE is written. Delta runs are verified to reproduce the in-memory image exactly.
  ~/venv-ld2/bin/python -I -B make_v3_delta.py [--catalog reviewed|lab_preview] [--modes 2,0]"""
import argparse, hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_v3_lab as b3  # noqa: E402
import enable_plan as ep  # noqa: E402

D = HERE / 'lab-deltas'


def sha(x): return hashlib.sha256(x).hexdigest()


def runs_for(m, x, erep):
    hdr = []
    for i in (i for i in range(0x1000) if m[i] != x[i]):
        if hdr and i - hdr[-1][1] <= 8: hdr[-1][1] = i + 1
        else: hdr.append([i, i + 1])
    code = [[ep.HOOK_SPAN[0], ep.HOOK_SPAN[1]]] + sorted([int(s['va'], 16) - 0x400000 + 1, int(s['va'], 16) - 0x400000 + 5] for s in erep['sites'])
    covered = set()
    for a, b in hdr + code: covered |= set(range(a, b))
    diff = {i for i in range(len(m)) if m[i] != x[i]}
    assert diff <= covered, sorted(diff - covered)[:10]
    return [dict(offset=a, length=b - a, kind=k) for k, rs in (('header', hdr), ('code', code), ('append', [[len(m), len(x)]])) for a, b in rs]


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default='reviewed', choices=sorted(b3.mv.POLICIES))
    ap.add_argument('--modes', default='2,0')
    a = ap.parse_args()
    D.mkdir(exist_ok=True)
    pre = b3.inputs(a.catalog)
    summary = {}
    for mode in map(int, a.modes.split(',')):
        o, m, inert, rep, x, erep = b3.build(mode, a.catalog, pre)
        b3.verify(o, inert, rep, x, erep, pre[2], pre[3])
        runs = runs_for(m, x, erep)
        blob = b''.join(x[r['offset']:r['offset'] + r['length']] for r in runs)
        for r in runs: r['sha256'] = sha(x[r['offset']:r['offset'] + r['length']])
        assert apply(m, runs, blob) == x
        stem = f'm062-v3-{a.catalog}-mode{mode}'
        man = {"schema": "m062-v3-enabled-delta/1", "base": "m045", "base_sha256": sha(m), "base_size": len(m),
               "catalog_policy": a.catalog, "release_eligible_catalog": rep['catalog_build']['review']['release_eligible'],
               "catalog_rows": rep['capacity']['rows'], "blob_sha256": rep['blob_sha256'], "blob_bytes": rep['capacity']['blob_bytes'],
               "list_profile": "v3", "list_mode": mode, "list_mode_slot_va": rep['list_mode_slot_va'],
               "original_dlgitem_slot_va": rep['original_dlgitem_slot_va'], "original_dlgitem_value": rep['original_dlgitem_va'],
               "name_object_sha256": b3.mv.NAME_V3_OBJECT_SHA256, "list_object_sha256": b3.mv.LIST_V3_OBJECT_SHA256,
               "inert_sha256": sha(inert), "out_sha256": sha(x), "out_size": len(x),
               "delta_file": stem + '.delta.bin', "delta_sha256": sha(blob), "delta_size": len(blob), "runs": runs,
               "hook_span": list(ep.HOOK_SPAN), "hook_stub_sha256": erep['hook_stub_sha256'],
               "name_pair_va": erep['name_pair_va'], "list_entry_va": erep['list_entry_va'], "sites": [s['va'] for s in erep['sites']],
               "list_sites_patched": True, "textoutw_hook_enabled": True, "production_can_apply": False, "release_approved": False}
        (D / man['delta_file']).write_bytes(blob)
        (D / (stem + '.delta.json')).write_text(json.dumps(man, indent=2) + '\n')
        summary[stem] = dict(out_sha256=man['out_sha256'], inert_sha256=man['inert_sha256'], delta_sha256=man['delta_sha256'],
                             delta_size=len(blob), manifest_sha256=sha((D / (stem + '.delta.json')).read_bytes()))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
