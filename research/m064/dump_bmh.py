"""Lab only: decode RES\*.BMH -> PNG + contact sheets grouped by name prefix."""
import sys, glob, io, struct, json, re
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent)); import bmh
RES = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
items = []
for f in sorted(RES.glob("*")):
    if f.suffix.lower() != ".bmh": continue
    d = bmh.decode(f.read_bytes())
    hsz = struct.unpack_from("<I", d, 0)[0]; bpp = struct.unpack_from("<H", d, 14)[0]; clr = struct.unpack_from("<I", d, 32)[0]
    ncol = clr or (1 << bpp if bpp <= 8 else 0)
    bfh = b"BM" + struct.pack("<IHHI", 14 + len(d), 0, 0, 14 + hsz + 4 * ncol)
    im = Image.open(io.BytesIO(bfh + d)).convert("RGB"); name = f.stem
    im.save(OUT / f"{name}.png"); items.append((name, im))
def sheet(group, tag):
    W = 1400; x = y = rowh = 0; pos = []
    for name, im in group:
        t = im.copy(); t.thumbnail((440, 440))
        if x + t.width > W: x, y, rowh = 0, y + rowh + 20, 0
        pos.append((name, t, x, y)); x += t.width + 10; rowh = max(rowh, t.height)
    S = Image.new("RGB", (W, y + rowh + 22), (50, 50, 50)); dr = ImageDraw.Draw(S)
    for name, t, x, y in pos: S.paste(t, (x, y)); dr.text((x, y + t.height + 2), name, fill=(255, 255, 0))
    S.save(OUT / f"sheet_{tag}.png")
groups = {}
for name, im in items:
    key = re.match(r"[A-Za-z_\-]+?(?=\d|$)", name); key = (key.group(0) if key else name).upper().rstrip("_")
    groups.setdefault(key, []).append((name, im))
idx = []
for k, g in groups.items():
    for j in range(0, len(g), 12):
        tag = f"{k}_{j//12}"; sheet(g[j:j+12], tag); idx.append(tag)
json.dump({"images": [n for n, _ in items], "sheets": idx}, open(OUT / "index.json", "w"), indent=1)
print(len(items), "images", len(idx), "sheets")
