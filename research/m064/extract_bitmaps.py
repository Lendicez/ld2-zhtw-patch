"""Lab only: dump EXE RT_BITMAP + RES\*.BMP to PNG and build labeled contact sheets. Never writes into game dirs."""
import struct, sys, io, glob, os, json
from pathlib import Path
from PIL import Image, ImageDraw
GAME = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
exe = (GAME / "Ld95.exe").read_bytes()
pe = struct.unpack_from("<I", exe, 0x3c)[0]; opt = pe + 24
rva, _ = struct.unpack_from("<II", exe, opt + 96 + 16)
n = struct.unpack_from("<H", exe, pe + 6)[0]; so = struct.unpack_from("<H", exe, pe + 20)[0]; sec = opt + so
for i in range(n):
    nm, vsz, va, rsz, raw = struct.unpack_from("<8sIIII", exe, sec + 40 * i)
    if va == rva: braw, bva = raw, va
r2o = lambda r: r - bva + braw
def walk(off, path):
    _, _, _, _, nn, ni = struct.unpack_from("<IIHHHH", exe, off); out = []
    for k in range(nn + ni):
        name, od = struct.unpack_from("<II", exe, off + 16 + 8 * k)
        key = name & 0x7fffffff if not name & 0x80000000 else "N"
        if od & 0x80000000: out += walk(r2o(rva) + (od & 0x7fffffff), path + [key])
        else:
            drva, dsz = struct.unpack_from("<II", exe, r2o(rva) + od); out.append((path + [key], r2o(drva), dsz))
    return out
items = []
for p, o, s in walk(r2o(rva), []):
    if p[0] != 2: continue
    dib = exe[o:o + s]
    hsz, bpp, clr = struct.unpack_from("<I", dib, 0)[0], struct.unpack_from("<H", dib, 14)[0], struct.unpack_from("<I", dib, 32)[0]
    ncol = clr or (1 << bpp if bpp <= 8 else 0)
    bfh = b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + hsz + 4 * ncol)
    im = Image.open(io.BytesIO(bfh + dib)).convert("RGB"); name = f"rsrc_{p[1]}"
    im.save(OUT / f"{name}.png"); items.append((name, im))
for f in sorted(glob.glob(str(GAME / "RES" / "*.[bB][mM][pP]"))):
    im = Image.open(f).convert("RGB"); name = "res_" + Path(f).stem
    im.save(OUT / f"{name}.png"); items.append((name, im))
# contact sheets: each tile scaled x2 (small ones), label under
def sheet(group, idx):
    tiles = []
    for name, im in group:
        sc = 3 if im.width <= 160 else (2 if im.width <= 300 else 1)
        t = im.resize((im.width * sc, im.height * sc), Image.NEAREST); tiles.append((name, t))
    W = 1000; x = y = 0; rowh = 0; pos = []
    for name, t in tiles:
        if x + t.width > W: x, y, rowh = 0, y + rowh + 22, 0
        pos.append((name, t, x, y)); x += t.width + 12; rowh = max(rowh, t.height)
    S = Image.new("RGB", (W, y + rowh + 24), (60, 60, 60)); d = ImageDraw.Draw(S)
    for name, t, x, y in pos: S.paste(t, (x, y)); d.text((x, y + t.height + 3), name, fill=(255, 255, 0))
    S.save(OUT / f"sheet_{idx:02d}.png")
group, idx, area = [], 0, 0
for it in items:
    group.append(it); area += it[1].width * it[1].height * 9
    if area > 260000: sheet(group, idx); group, area, idx = [], 0, idx + 1
if group: sheet(group, idx)
json.dump([{"name": n, "w": im.width, "h": im.height} for n, im in items], open(OUT / "index.json", "w"), indent=1)
print(len(items), "images;", idx + 1, "sheets")
