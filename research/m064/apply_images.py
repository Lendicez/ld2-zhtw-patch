r"""Lab only: apply zh-TW bitmaps to a lab game copy.
- RES\<name>.BMP replaced by out_zh\<name>.BMP (must keep identical header+palette+size).
- EXE RT_BITMAP entries whose DIB == original RES BMP[14:] are overwritten in place with new DIB.
- RES\<name>.BMH replaced (raw block) when out_zh_bmh\<name>.dib exists.
Refuses to touch baseline/pristine. Writes manifest JSON.
usage: apply_images.py <pristine_game> <lab_game> <out_zh_dir> [<out_zh_bmh_dir>]
"""
import sys, struct, hashlib, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import bmh
P, LAB, ZH = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ZHBS = [Path(a) for a in sys.argv[4:]]
if "pristine" in str(LAB).lower() or "baseline" in str(LAB).lower(): sys.exit("refuse: lab path looks like baseline")
exe_p = LAB / "Ld95.exe"; exe = bytearray(exe_p.read_bytes()); man = {"bmp": [], "rsrc": [], "bmh": []}
pe = struct.unpack_from("<I", exe, 0x3c)[0]; opt = pe + 24; rva = struct.unpack_from("<I", exe, opt + 96 + 16)[0]
n = struct.unpack_from("<H", exe, pe + 6)[0]; so = struct.unpack_from("<H", exe, pe + 20)[0]
for i in range(n):
    _, _, va, _, raw = struct.unpack_from("<8sIIII", exe, opt + so + 40 * i)
    if va == rva: braw, bva = raw, va
r2o = lambda r: r - bva + braw
def walk(off, path):
    _, _, _, _, nn, ni = struct.unpack_from("<IIHHHH", exe, off); out = []
    for k in range(nn + ni):
        name, od = struct.unpack_from("<II", exe, off + 16 + 8 * k)
        if od & 0x80000000: out += walk(r2o(rva) + (od & 0x7fffffff), path + [name])
        else:
            drva, dsz = struct.unpack_from("<II", exe, r2o(rva) + od); out.append((path + [name], r2o(drva), dsz))
    return out
bitmaps = [(p, o, s) for p, o, s in walk(r2o(rva), []) if p[0] == 2]
for zf in sorted(ZH.glob("*.BMP")):
    orig = (P / "RES" / zf.name).read_bytes(); new = zf.read_bytes()
    oo, no = struct.unpack_from("<I", orig, 10)[0], struct.unpack_from("<I", new, 10)[0]
    assert len(orig) == len(new) and orig[14:oo] == new[14:no], f"format mismatch {zf.name}"
    (LAB / "RES" / zf.name).write_bytes(new)
    man["bmp"].append({"name": zf.name, "sha256": hashlib.sha256(new).hexdigest()})
    for p, o, s in bitmaps:
        if s == len(orig) - 14 and bytes(exe[o:o + s]) == orig[14:]:
            exe[o:o + s] = new[14:]; man["rsrc"].append({"id": p[1], "from": zf.name})
for ZHB in ZHBS:
    for df in sorted(ZHB.glob("*.dib")):
        name = df.stem; src = next((f for f in (P / "RES").iterdir() if f.stem.lower() == name.lower() and f.suffix.lower() == ".bmh"))
        orig = bmh.decode(src.read_bytes()); new = df.read_bytes()
        assert len(orig) == len(new) and orig[:0x28 + 0x400] == new[:0x28 + 0x400], f"format mismatch {name}"
        out = bmh.encode_raw(new, src.read_bytes()); assert bmh.decode(out) == new
        (LAB / "RES" / src.name).write_bytes(out); man["bmh"].append({"name": src.name, "sha256": hashlib.sha256(out).hexdigest()})
exe_p.write_bytes(exe); man["exe_sha256"] = hashlib.sha256(exe).hexdigest()
man.update(production_can_apply=False, release_approved=False, lab_only=True)
(LAB.parent / "image-manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in man.items()}, ensure_ascii=False))
