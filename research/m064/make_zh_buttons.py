"""Translate the listed RES buttons in this lab; originals are read only."""
import json
import os
import struct
import ctypes
from ctypes import wintypes
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('LD2_PRISTINE_RES', 'pristine/RES'))  # 使用者的原版 RES 目錄（只讀）
DEST = HERE / "out_zh"
FONT = Path(r"C:\Windows\Fonts\mingliu.ttc")
TRANSLATIONS = {
    "決定": "確定", "取り消し": "取消", "次": "下一頁", "戻る": "返回",
    "能力": "能力", "家系": "家系", "持ち物1": "物品1",
    "持ち物2": "物品2", "戦闘力": "戰力",
}


def info(raw):
    if raw[:2] != b"BM":
        raise ValueError("Not a BMP")
    offset = struct.unpack_from("<I", raw, 10)[0]
    header_size = struct.unpack_from("<I", raw, 14)[0]
    width, height, planes, bpp, compression = struct.unpack_from("<iiHHI", raw, 18)
    if header_size < 40 or width <= 0 or height <= 0 or planes != 1 or bpp not in (4, 8) or compression != 0:
        raise ValueError("Expected bottom-up 4/8-bit BI_RGB BMP")
    palette = raw[14 + header_size:offset]
    stride = ((width * bpp + 31) // 32) * 4
    if len(raw) < offset + stride * height:
        raise ValueError("Truncated BMP")
    return dict(width=width, height=height, bpp=bpp, offset=offset,
                palette=palette, stride=stride, compression=compression)


def write_indices(original, meta, image):
    """Change only pixel index bytes, retaining headers, full palette and padding."""
    result = bytearray(original)
    w, h, bpp, offset, stride = (meta[k] for k in ("width", "height", "bpp", "offset", "stride"))
    for y in range(h):
        row = offset + (h - 1 - y) * stride
        for x in range(w):
            value = image.getpixel((x, y))
            if bpp == 8:
                result[row + x] = value
            elif x % 2 == 0:
                result[row + x // 2] = (result[row + x // 2] & 15) | (value << 4)
            else:
                result[row + x // 2] = (result[row + x // 2] & 240) | value
    return bytes(result)


def interior(im):
    # Exclude the raised/sunken frame and the four-pixel shadow on 48x24 buttons.
    return (2, 2, 46, 18) if im.width == 48 else (10, 9, 92, 33)


def inspect_text(im):
    box = interior(im)
    pixels = Counter(im.crop(box).tobytes())
    bg, _ = pixels.most_common(1)[0]
    other = [(count, index) for index, count in pixels.items() if index != bg]
    if not other:
        raise ValueError("No text pixels in interior")
    fg = max(other)[1]
    coords = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])
              if im.getpixel((x, y)) != bg]
    bounds = (min(x for x, _ in coords), min(y for _, y in coords),
              max(x for x, _ in coords) + 1, max(y for _, y in coords) + 1)
    return box, bg, fg, bounds


def text_mask(text, size, font_path=FONT, gap=None):
    font = ImageFont.truetype(str(font_path), size)
    # A generous canvas makes the measured ink bounding box independent of font bearings.
    mask = Image.new("1", (256, 96))
    draw = ImageDraw.Draw(mask)
    if gap is None:
        draw.text((16, 16), text, fill=1, font=font)
    else:
        # Match the seven blank columns between the two glyphs in the originals.
        if len(text) != 2:
            raise ValueError("Explicit spacing expects two characters")
        first_bbox = draw.textbbox((16, 16), text[0], font=font)
        second_bbox = draw.textbbox((0, 16), text[1], font=font)
        draw.text((16, 16), text[0], fill=1, font=font)
        draw.text((first_bbox[2] + gap - second_bbox[0], 16), text[1], fill=1, font=font)
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError("Font produced an empty glyph")
    return mask.crop(bounds)


def family_mask():
    """Render Windows MingLiU through GDI, using its non-antialiased strike."""
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    def api(name, result, *args):
        fn = getattr(gdi, name)
        fn.restype, fn.argtypes = result, args
        return fn
    handle = wintypes.HANDLE
    create_dc = api("CreateCompatibleDC", handle, handle)
    create_dib = api("CreateDIBSection", handle, handle, ctypes.c_void_p,
                     wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), handle, wintypes.DWORD)
    create_font = api("CreateFontW", handle, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                      ctypes.c_int, ctypes.c_int, wintypes.DWORD, wintypes.DWORD,
                      wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                      wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR)
    select = api("SelectObject", handle, handle, handle)
    delete = api("DeleteObject", wintypes.BOOL, handle)
    delete_dc = api("DeleteDC", wintypes.BOOL, handle)
    set_bk = api("SetBkMode", ctypes.c_int, handle, ctypes.c_int)
    set_color = api("SetTextColor", wintypes.DWORD, handle, wintypes.DWORD)
    text_out = api("TextOutW", wintypes.BOOL, handle, ctypes.c_int, ctypes.c_int,
                   wintypes.LPCWSTR, ctypes.c_int)
    face = api("GetTextFaceW", ctypes.c_int, handle, ctypes.c_int, wintypes.LPWSTR)
    # Top-down 32-bit DIB, initialized black. White ink becomes a 1-bit mask.
    bitmap_info = struct.pack("<IiiHHIIiiII", 40, 64, -32, 1, 32, 0, 0, 0, 0, 0, 0)
    info_buffer = ctypes.create_string_buffer(bitmap_info)
    bits = ctypes.c_void_p()
    dc = create_dc(None)
    bitmap = create_dib(dc, info_buffer, 0, ctypes.byref(bits), None, 0)
    font = create_font(-12, 0, 0, 0, 400, 0, 0, 0, 136, 0, 0, 3, 0, "細明體")
    if not dc or not bitmap or not font or not bits.value:
        raise ctypes.WinError(ctypes.get_last_error())
    old_bitmap = select(dc, bitmap)
    old_font = select(dc, font)
    try:
        actual_face = ctypes.create_unicode_buffer(128)
        if not face(dc, len(actual_face), actual_face) or actual_face.value not in ("細明體", "MingLiU"):
            raise ValueError(f"Unexpected GDI font substitution: {actual_face.value}")
        set_bk(dc, 1)  # TRANSPARENT
        set_color(dc, 0xFFFFFF)
        glyphs = []
        for char in "家系":
            ctypes.memset(bits, 0, 64 * 32 * 4)
            if not text_out(dc, 0, 0, char, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            raw = ctypes.string_at(bits, 64 * 32 * 4)
            image = Image.frombytes("RGB", (64, 32), raw, "raw", "BGRX")
            mask = image.convert("1", dither=Image.Dither.NONE)
            bounds = mask.getbbox()
            if not bounds:
                raise ValueError(f"GDI rendered an empty glyph: {char}")
            glyphs.append((mask, bounds))
        # Preserve the original baseline, with seven empty columns between ink.
        top = min(bounds[1] for _, bounds in glyphs)
        bottom = max(bounds[3] for _, bounds in glyphs)
        widths = [bounds[2] - bounds[0] for _, bounds in glyphs]
        result = Image.new("1", (sum(widths) + 7, bottom - top))
        x = 0
        for (glyph, bounds), width in zip(glyphs, widths):
            result.paste(glyph.crop(bounds), (x, bounds[1] - top))
            x += width + 7
        return result
    finally:
        select(dc, old_font)
        select(dc, old_bitmap)
        delete(font)
        delete(bitmap)
        delete_dc(dc)


def main():
    entries = json.loads((HERE / "out" / "text_images.json").read_text(encoding="utf-8"))
    entries = [entry for entry in entries if entry["name"].startswith("res_")]
    DEST.mkdir(exist_ok=True)
    reports, previews = [], []
    for entry in entries:
        name = entry["name"]
        filename = name[4:]
        original = (SOURCE / (filename + ".BMP")).read_bytes()
        old_meta = info(original)
        im = Image.open(SOURCE / (filename + ".BMP"))
        im.load()
        if im.mode != "P" or im.size != (old_meta["width"], old_meta["height"]):
            raise ValueError(f"Unexpected indexed image: {name}")
        box, bg, fg, old_bounds = inspect_text(im)
        text = TRANSLATIONS[entry["text_seen"]]
        # Keep every state the same size, including when the translated text is wider.
        size = 14 if text == "戰力" else (13 if im.width == 48 else 16)
        font_path = FONT
        gap = 7 if text in ("能力", "家系") else None
        mask = family_mask() if text == "家系" else text_mask(text, size, font_path, gap)
        while size > 10 and (mask.width > box[2] - box[0] or mask.height > box[3] - box[1]):
            size -= 1
            mask = text_mask(text, size, font_path, gap)
        if im.width == 104 and mask.width > box[2] - box[0] and text == "下一頁":
            text = "下頁"
            size = 16
            mask = text_mask(text, size, font_path, gap)
        # Center on the original ink, retaining that state's original pixel displacement.
        x = round((old_bounds[0] + old_bounds[2] - mask.width) / 2)
        y = round((old_bounds[1] + old_bounds[3] - mask.height) / 2)
        clipped = x < box[0] or y < box[1] or x + mask.width > box[2] or y + mask.height > box[3]
        if clipped:
            raise ValueError(f"Text does not fit: {name} {text}")
        im.paste(bg, box)
        im.paste(fg, (x, y), mask)
        updated = write_indices(original, old_meta, im)
        new_meta = info(updated)
        (DEST / (filename + ".BMP")).write_bytes(updated)
        with Image.open(DEST / (filename + ".BMP")) as result:
            result.load()
            if result.tobytes() != im.tobytes():
                raise ValueError(f"BMP pixel round-trip failed: {name}")
            result.convert("RGB").save(DEST / (filename + ".png"))
            preview = result.convert("RGB")
        with Image.open(SOURCE / (filename + ".BMP")) as source:
            previews.append((name, source.convert("RGB"), preview))
        reports.append({"name": name, "text": text,
                        "original": {k: old_meta[k] for k in ("width", "height", "bpp")},
                        "new": {k: new_meta[k] for k in ("width", "height", "bpp")},
                        "palette_identical": old_meta["palette"] == new_meta["palette"],
                        "compression": "BI_RGB", "bottom_up": True,
                        "font": "Windows GDI 細明體 (MingLiU), NONANTIALIASED_QUALITY" if text == "家系" else str(font_path),
                        "font_size_px": 12 if text == "家系" else size, "text_clipped": clipped})
    row_h = max(max(old.height, new.height) * 3 for _, old, new in previews) + 12
    width = max(old.width * 3 + new.width * 3 for _, old, new in previews) + 250
    sheet = Image.new("RGB", (width, row_h * len(previews)), (64, 64, 64))
    draw = ImageDraw.Draw(sheet)
    for i, (name, old, new) in enumerate(previews):
        y = i * row_h + 6
        old = old.resize((old.width * 3, old.height * 3), Image.Resampling.NEAREST)
        new = new.resize((new.width * 3, new.height * 3), Image.Resampling.NEAREST)
        sheet.paste(old, (0, y))
        sheet.paste(new, (old.width + 8, y))
        draw.text((old.width + new.width + 16, y + 4), name, fill="white")
    sheet.save(DEST / "compare.png")
    small_previews = [(name, old, new) for name, old, new in previews if name.startswith("res_WP_SB")]
    row_h = max(old.height for _, old, _ in small_previews) * 4 + 12
    width = max((old.width + new.width) * 4 for _, old, new in small_previews) + 250
    sheet = Image.new("RGB", (width, row_h * len(small_previews)), (64, 64, 64))
    draw = ImageDraw.Draw(sheet)
    for i, (name, old, new) in enumerate(small_previews):
        y = i * row_h + 6
        old = old.resize((old.width * 4, old.height * 4), Image.Resampling.NEAREST)
        new = new.resize((new.width * 4, new.height * 4), Image.Resampling.NEAREST)
        sheet.paste(old, (0, y))
        sheet.paste(new, (old.width + 8, y))
        draw.text((old.width + new.width + 16, y + 4), name, fill="white")
    sheet.save(DEST / "compare_x4.png")
    family_previews = [(name, old, new) for name, old, new in previews
                       if name in ("res_WP_SB10", "res_WP_SB11", "res_WP_SB12")]
    sheet = Image.new("RGB", (48 * 6, 24 * 6 * len(family_previews)), (64, 64, 64))
    for i, (_, _, new) in enumerate(family_previews):
        sheet.paste(new.resize((new.width * 6, new.height * 6), Image.Resampling.NEAREST), (0, i * 24 * 6))
    sheet.save(DEST / "sb1x_x6.png")
    (DEST / "report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(reports)} buttons; palette mismatches: {sum(not r['palette_identical'] for r in reports)}; clipped: {sum(r['text_clipped'] for r in reports)}")


if __name__ == "__main__":
    main()
