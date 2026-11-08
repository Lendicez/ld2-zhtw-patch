"""Localize individually inspected map labels, in the lab only.

Rectangles exclude directional arrows. By default only MC12–15 are rebuilt;
other maps require an explicit --only selection. The shared report is merged
by map name.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
import struct
from pathlib import Path
from PIL import Image
import bmh
from make_zh_panels import gdi_mask, load_dib

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('LD2_PRISTINE_RES', 'pristine/RES'))  # 使用者的原版 RES 目錄（只讀）
GLOSSARY = Path(__file__).resolve().parent / 'PLACE-NAMES.zh-TW.json'
OUT = HERE / 'out_zh_maps'

# Exclusive source rectangles, checked against enlarged original images. The
# final flag distinguishes the two original one-pixel shadow colors.
SPECS = {
 'WP_MC00': [('白夜の村',(172,20,238,38),'town'),('水鏡都市',(57,69,124,85),'town'),('雪嵐の道',(145,93,205,109),'route'),('崖岸道',(11,156,57,173),'route'),('峭壁の狭路',(119,177,195,194),'route'),('岩塊の町',(57,221,124,239),'town'),('月明の村',(177,230,243,248),'town')],
 'WP_MC01': [('砂海都市',(153,24,221,42),'town'),('白昼の航路',(175,59,248,76),'route'),('白夜の村',(83,75,149,93),'town'),('水鏡都市',(4,125,71,143),'town'),('雪嵐の道',(61,155,122,173),'route'),('氷解の道',(160,148,221,166),'route'),('流砂の町',(158,192,225,210),'town')],
 'WP_MC02': [('水鏡都市',(141,5,208,24),'town'),('崖岸道',(134,58,181,76),'route'),('岩塊の町',(90,103,157,122),'town'),('陰火の船路',(9,180,84,198),'route'),('丘墟の道',(135,182,195,200),'route'),('漁火の町',(7,231,76,250),'town'),('三角州の村',(111,228,195,247),'town')],
 'WP_MC03': [('岩塊の町',(29,5,96,24),'town'),('黄埃の路',(97,53,160,71),'route'),('月明の村',(177,53,244,72),'town'),('丘墟の道',(27,69,88,87),'route'),('三角州の村',(25,123,109,142),'town'),('深林の山路',(93,160,168,179),'route'),('漁火の町',(115,230,182,250),'town')],
 'WP_MC04': [('月明の村',(61,5,128,24),'town'),('天鐘の町',(174,69,242,88),'town'),('月空の道',(74,87,135,105),'route'),('百鐘の海路',(130,123,204,142),'route'),('千年都市',(16,140,85,161),'town'),('越河の道',(77,183,139,201),'route'),('漁火の町',(55,231,125,251),'town')],
 'WP_MC05': [('水鏡都市',(43,3,112,23),'town'),('流砂の町',(135,3,204,23),'town'),('峭壁の狭路',(51,31,128,50),'route'),('山峡の険道',(122,51,199,70),'route'),('星屑の町',(159,84,228,104),'town'),('月明の村',(79,110,149,130),'town'),('星芒の路',(192,115,254,134),'route'),('黄埃の路',(11,126,74,145),'route'),('三角州の村',(9,173,95,194),'town'),('月空の道',(167,169,229,189),'route'),('千年都市',(111,221,181,242),'town')],
 'WP_MC06': [('三角州の村',(44,11,129,31),'town'),('千年都市',(164,64,234,83),'town'),('深林の山路',(23,95,97,114),'route'),('越河の道',(180,132,242,151),'route'),('岩塊の町',(21,159,88,179),'town'),('陰火の船路',(30,204,105,222),'route'),('漁火の町',(111,204,180,224),'town'),('跨越海道',(192,188,253,207),'route'),('細流の村',(164,233,231,253),'town')],
 'WP_MC07': [('星屑の町',(133,3,201,23),'town'),('天鐘の町',(59,79,128,99),'town'),('山脚道',(151,75,197,94),'route'),('百鐘の海路',(41,137,116,155),'route'),('千年都市',(5,169,74,189),'town'),('風岸の道',(168,153,231,172),'route'),('細流の村',(157,194,226,214),'town')],
 'WP_MC08': [('白夜の村',(22,32,88,49),'town'),('砂海都市',(106,64,172,82),'town'),('白昼の航路',(6,84,79,101),'route'),('海岳の道',(181,85,242,102),'route'),('砂塵の路',(5,132,63,149),'route'),('流砂の町',(25,170,92,188),'town'),('茫洋の港町',(149,170,232,188),'town'),('荒蕪の路',(48,203,107,220),'route'),('星屑の町',(72,234,140,252),'town')],
 'WP_MC09': [('白夜の村',(32,8,98,26),'town'),('氷解の道',(32,51,91,69),'route'),('流砂の町',(90,67,158,85),'town'),('砂塵の路',(138,95,198,113),'route'),('砂海都市',(160,129,227,147),'town'),('熱砂の道',(159,170,220,188),'route'),('山峡の険道',(45,194,117,212),'route'),('星屑の町',(189,203,254,221),'town'),('月明の村',(32,231,99,249),'town')],
 'WP_MC10': [('流砂の町',(31,6,98,25),'town'),('砂海都市',(159,2,227,22),'town'),('熱砂の道',(30,69,90,86),'route'),('荒蕪の路',(109,55,170,73),'route'),('星芒の路',(7,100,65,118),'route'),('蒼高の峠道',(159,87,232,105),'route'),('星屑の町',(89,109,157,128),'town'),('月明の村',(6,142,74,161),'town'),('鈴音の町',(165,135,234,154),'town'),('山脚道',(89,159,133,178),'route'),('天鐘の町',(23,224,92,243),'town')],
 'WP_MC11': [('砂海都市',(29,2,97,22),'town'),('海岳の道',(111,11,171,29),'route'),('茫洋の港町',(60,87,146,106),'town'),('森羅の道',(182,128,242,146),'route'),('港湾海路',(92,139,151,158),'route'),('鈴音の町',(49,219,117,238),'town'),('東方都市',(159,222,228,242),'town')],
 'WP_MC12': [('鈴音の町',(43,18,110,37),'town'),('茫洋の港町',(160,5,245,25),'town'),('森羅の道',(160,53,222,71),'route'),('島繋回廊',(50,88,111,106),'route'),('東方都市',(152,122,222,141),'town'),('緑波の道',(82,182,145,200),'route'),('深森の町',(67,231,136,250),'town')],
 'WP_MC13': [('茫洋の港町',(168,11,254,31),'town'),('港湾海路',(97,63,158,81),'route'),('星屑の町',(20,111,88,130),'town'),('鈴音の町',(131,119,201,139),'town'),('蒼高の峠道',(33,149,110,168),'route'),('草露の道',(60,199,122,218),'route'),('島繋回廊',(129,211,189,230),'route'),('東方都市',(181,190,252,210),'town'),('細流の村',(20,234,89,254),'town')],
 'WP_MC14': [('東方都市',(146,5,216,24),'town'),('緑波の道',(173,74,235,94),'route'),('細流の村',(19,92,88,112),'town'),('深森の町',(148,153,218,173),'town'),('渡船の海道',(54,169,130,189),'route')],
 'WP_MC16': [('ロシュフォーン',(136,143,250,161),'town')],
 'WP_MC15': [('天鐘の町',(22,6,91,26),'town'),('鈴音の町',(179,2,251,22),'town'),('風岸の道',(22,61,83,81),'route'),('草露の道',(133,53,196,73),'route'),('跨越海道',(19,95,83,115),'route'),('細流の村',(59,116,129,136),'town'),('深森の町',(181,82,252,102),'town'),('渡船の海道',(155,143,232,163),'route'),('漁火の町',(28,162,97,183),'town')],
}
ARROWS = {
 'WP_MC00': [(154,229,173,248)],
 'WP_MC01': [(220,25,239,43),(227,192,247,211)],
 'WP_MC02': [(76,230,95,251),(195,228,216,249)],
 'WP_MC03': [(10,5,29,25),(190,229,210,251)],
 'WP_MC04': [],
 'WP_MC05': [(22,3,43,24),(204,3,225,24),(229,84,251,105)],
 'WP_MC06': [(3,158,21,180),(231,232,251,254)],
 'WP_MC07': [(226,194,248,215)],
 'WP_MC08': [(3,32,22,50),(6,170,25,189),(53,234,72,253)],
 'WP_MC09': [(12,8,32,27),(227,129,247,148),(12,231,32,250)],
 'WP_MC10': [(11,6,31,26),(140,2,159,23),(2,125,21,142),(234,135,254,155),(3,224,23,244)],
 'WP_MC11': [(228,222,248,243)],
 'WP_MC12': [(140,5,159,25)],
 'WP_MC13': [(2,111,20,131),(90,234,110,254)],
 'WP_MC14': [],
 'WP_MC16': [],
 'WP_MC15': [(2,6,22,27),(159,2,178,23),(9,162,28,183)],
}

# The glossary corrected the Japanese reading as well as the translation.
GLOSSARY_KEYS = {'蒼高の峠道': '登高の峠道'}
ROAD_CLEARANCE = {
    ('WP_MC02', '丘墟の道'), ('WP_MC02', '陰火の船路'),
    ('WP_MC03', '丘墟の道'), ('WP_MC03', '黄埃の路'),
    ('WP_MC05', '黄埃の路'),
    ('WP_MC08', '流砂の町'), ('WP_MC13', '島繋回廊'),
}

# On these labels, the older inward fill could copy adjacent road dots into
# the erased Japanese strokes. Sample only terrain when repairing the mask.
R4_TERRAIN_FILL = {
    ('WP_MC01', '雪嵐の道'), ('WP_MC02', '陰火の船路'),
    ('WP_MC02', '漁火の町'), ('WP_MC03', '黄埃の路'),
    ('WP_MC03', '月明の村'), ('WP_MC05', '黄埃の路'),
    ('WP_MC05', '峭壁の狭路'), ('WP_MC08', '流砂の町'),
    ('WP_MC13', '島繋回廊'),
}

# Source boxes include the full original glyphs and their one-pixel shadows.
# Insets on the neighbouring roads and arrows remain protected independently.
BOX_FIXES = {
 ('WP_MC03', '漁火の町'): (115,230,187,251),
 ('WP_MC04', '漁火の町'): (55,230,130,252),
 ('WP_MC05', '峭壁の狭路'): (48,31,130,50),
 ('WP_MC06', '越河の道'): (177,132,243,151),
 ('WP_MC08', '星屑の町'): (72,234,145,253),
 ('WP_MC10', '星芒の路'): (7,100,68,119),
}

def town_mask(text):
    """GDI binary bold town labels with a 15-pixel actual ink height."""
    g = ctypes.WinDLL('gdi32', use_last_error=True)
    def api(name, result, *args):
        f = getattr(g,name); f.restype=result; f.argtypes=args; return f
    H=wintypes.HANDLE
    dcnew=api('CreateCompatibleDC',H,H)
    create=api('CreateDIBSection',H,H,ctypes.c_void_p,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p),H,wintypes.DWORD)
    fontnew=api('CreateFontW',H,*([ctypes.c_int]*5),*([wintypes.DWORD]*8),wintypes.LPCWSTR)
    select=api('SelectObject',H,H,H); delete=api('DeleteObject',wintypes.BOOL,H); deletedc=api('DeleteDC',wintypes.BOOL,H)
    bk=api('SetBkMode',ctypes.c_int,H,ctypes.c_int); color=api('SetTextColor',wintypes.DWORD,H,wintypes.DWORD)
    out=api('TextOutW',wintypes.BOOL,H,ctypes.c_int,ctypes.c_int,wintypes.LPCWSTR,ctypes.c_int)
    face=api('GetTextFaceW',ctypes.c_int,H,ctypes.c_int,wintypes.LPWSTR)
    w,h=512,48
    info=ctypes.create_string_buffer(struct.pack('<IiiHHIIiiII',40,w,-h,1,32,0,0,0,0,0,0))
    bits=ctypes.c_void_p(); dc=dcnew(None)
    bitmap=create(dc,info,0,ctypes.byref(bits),None,0)
    font=fontnew(-17,0,0,0,700,0,0,0,136,0,0,3,0,'微軟正黑體')
    if not dc or not bitmap or not font or not bits.value: raise ctypes.WinError(ctypes.get_last_error())
    ob=select(dc,bitmap); of=select(dc,font)
    try:
        actual=ctypes.create_unicode_buffer(128); face(dc,128,actual)
        if actual.value not in ('微軟正黑體','Microsoft JhengHei'): raise ValueError('Unexpected font: '+actual.value)
        ctypes.memset(bits,0,w*h*4); bk(dc,1); color(dc,0xffffff)
        if not out(dc,0,0,text,len(text)): raise ctypes.WinError(ctypes.get_last_error())
        raw=Image.frombytes('RGB',(w,h),ctypes.string_at(bits,w*h*4),'raw','BGRX')
        if not set(raw.getdata()) <= {(0,0,0),(255,255,255)}: raise ValueError('Non-binary GDI output')
        mask=raw.convert('1',dither=Image.Dither.NONE)
        if not mask.getbbox(): raise ValueError('Empty text: '+text)
        return mask.crop(mask.getbbox())
    finally:
        select(dc,of); select(dc,ob); delete(font); delete(bitmap); deletedc(dc)

def palette_index(im, rgb):
    p = im.getpalette()
    return next(i for i in range(256) if tuple(p[3*i:3*i+3]) == rgb)

def fill_inward(im, pixels):
    pending = set(pixels)
    while pending:
        updates = []
        for x, y in sorted(pending, key=lambda p: (p[1], p[0])):
            near = [(x+dx,y+dy) for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))
                    if 0 <= x+dx < im.width and 0 <= y+dy < im.height
                    and (x+dx,y+dy) not in pending]
            if near:
                values = [im.getpixel(p) for p in near]
                updates.append(((x,y), max(set(values), key=lambda v:(values.count(v),-v))))
        if not updates:
            raise ValueError('Cannot reconstruct text mask')
        for point,value in updates:
            im.putpixel(point,value)
            pending.remove(point)

def fill_road_gap(im, pixels, protected):
    """Fill the small clearance using terrain, never a neighbouring road dot."""
    pending = set(pixels)
    while pending:
        updates = []
        for x, y in sorted(pending, key=lambda p: (p[1], p[0])):
            near = [(x+dx, y+dy) for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))
                    if 0 <= x+dx < im.width and 0 <= y+dy < im.height
                    and (x+dx,y+dy) not in pending
                    and ((x+dx,y+dy) not in protected or (x+dx,y+dy) in pixels)]
            if near:
                values = [im.getpixel(p) for p in near]
                updates.append(((x,y), max(set(values), key=lambda v:(values.count(v),-v))))
        if not updates:
            raise ValueError('Cannot reconstruct road clearance from terrain')
        for point,value in updates:
            im.putpixel(point,value)
            pending.remove(point)

def fill_textured(im, original, pixels, forbidden):
    """Match nearby intact terrain patches when reconstructing map artwork."""
    palette = original.getpalette()
    rgb = [tuple(palette[i:i+3]) for i in range(0, 768, 3)]
    source = original.load()
    w, h = original.size
    offsets = [(dx,dy) for dy in range(-24,25,3) for dx in range(-24,25,3)
               if abs(dx)+abs(dy) >= 6]
    fallback = im.copy()
    fill_inward(fallback, pixels)
    updates = []
    for x,y in sorted(pixels, key=lambda p:(p[1],p[0])):
        known = [(a,b) for b in range(-3,4) for a in range(-3,4)
                 if 0 <= x+a < w and 0 <= y+b < h
                 and (x+a,y+b) not in pixels and (x+a,y+b) not in forbidden]
        best = None
        for dx,dy in offsets:
            sx,sy=x+dx,y+dy
            if not (0 <= sx < w and 0 <= sy < h) or (sx,sy) in pixels or (sx,sy) in forbidden:
                continue
            score=0; count=0
            for a,b in known:
                tx,ty=sx+a,sy+b
                if not (0 <= tx < w and 0 <= ty < h) or (tx,ty) in pixels or (tx,ty) in forbidden:
                    continue
                c1=rgb[source[x+a,y+b]]; c2=rgb[source[tx,ty]]
                score += sum((c1[k]-c2[k])**2 for k in range(3)); count += 1
            if count < 8:
                continue
            candidate=(score/count + 2*(abs(dx)+abs(dy)), abs(dx)+abs(dy),dy,dx)
            if best is None or candidate < best:
                best=candidate
        if best is None:
            updates.append(((x,y),fallback.getpixel((x,y))))
        else:
            updates.append(((x,y),source[x+best[3],y+best[2]]))
    for point,value in updates:
        im.putpixel(point,value)

def run(name):
    glossary = {r['ja']:r['zh_tw'] for r in json.loads(GLOSSARY.read_text(encoding='utf-8-sig'))['rows']}
    packed_source = (SOURCE / (name+'.BMH')).read_bytes()
    source = bmh.decode(packed_source)
    im,offset,stride = load_dib(source)
    original = im.copy()
    black = palette_index(im,(1,1,1))
    road_colors = {palette_index(im,rgb) for rgb in ((240,50,60),(25,30,176))}
    road = {(x,y) for y in range(im.height) for x in range(im.width)
            if original.getpixel((x,y)) in road_colors}
    # The road dots' black drop shadow is displaced one pixel down and right.
    road_edge = {(x+dx,y+dy) for x,y in road for dx,dy in ((1,1),)
                 if 0 <= x+dx < im.width and 0 <= y+dy < im.height
                 and original.getpixel((x+dx,y+dy)) == black}
    arrow = {(x,y) for x0,y0,x1,y1 in ARROWS[name]
             for y in range(y0,y1) for x in range(x0,x1)}
    protected = road | road_edge | arrow
    road_cleared = set()
    revised = True
    allowed = set()
    labels = []
    for ja,box,kind in SPECS[name]:
        box = BOX_FIXES.get((name,ja),box)
        glossary_ja = GLOSSARY_KEYS.get(ja, ja)
        zh = glossary[glossary_ja]
        shadow = palette_index(im, (230,235,255) if kind == 'town' else (140,150,250))
        x0,y0,x1,y1 = box
        if ja == zh:
            labels.append({'ja':ja,'zh':zh,'source_box':box,'render_box':box,
                           'color_index':black,'shadow_color_index':shadow,'shadow_offset':[1,0],
                           'font_height':None,'fill':'none; identical original glyphs preserved',
                           'fits':True,'review':'Original text already matches glossary; retained to preserve road crossings.'})
            continue
        ink = {(x,y) for y in range(y0,y1) for x in range(x0,x1)
               if original.getpixel((x,y)) == black and (x,y) not in protected}
        if not ink:
            raise ValueError(f'{name} {ja}: no ink')
        # Some ink pixels coincide with a road shadow. Their text shadow still
        # belongs to the label and must be removed to avoid blue/white ghosts.
        shadow_pixels = {(x,y) for y in range(y0,y1) for x in range(x0+1,x1)
                         if original.getpixel((x,y)) == shadow
                         and original.getpixel((x-1,y)) == black and (x,y) not in protected}
        erase = ink | shadow_pixels
        bounds = (min(x for x,y in erase), min(y for x,y in erase),
                  max(x for x,y in erase)+1, max(y for x,y in erase)+1)
        textured = name == 'WP_MC11' and ja in ('茫洋の港町', '鈴音の町')
        if textured:
            fill_textured(im, original, erase, protected)
        elif (name, ja) in R4_TERRAIN_FILL:
            fill_road_gap(im, erase, protected)
        else:
            fill_inward(im,erase)
        mask = town_mask(zh) if kind == 'town' else gdi_mask(zh,-12)
        cx = (bounds[0]+bounds[2]-mask.width)//2
        cy = (bounds[1]+bounds[3]-mask.height)//2
        glyph = {(x,y) for y in range(mask.height) for x in range(mask.width) if mask.getpixel((x,y))}
        footprint = glyph | {(x+1,y) for x,y in glyph}
        clearance = (name, ja) in ROAD_CLEARANCE
        radius = 2 if (name, ja) in {('WP_MC02', '陰火の船路'),
                                     ('WP_MC03', '黄埃の路'),
                                     ('WP_MC13', '島繋回廊')} else 1
        halo = {(u+du,v+dv) for u,v in footprint
                for du in range(-radius,radius+1) for dv in range(-radius,radius+1)} if clearance else footprint
        candidates=[]
        # Keep new town labels clear of adjacent labels and road dots. Source
        # text can obscure a road, but visible original road pixels are sacred.
        other_boxes = [b for other,b,k in SPECS[name] if other != ja]
        special_shift = ((name == 'WP_MC05' and ja == '三角州の村') or
                                     (name == 'WP_MC08' and ja == '流砂の町'))
        horizontal_range = 40 if special_shift else 22
        for dy in range(-22,23):
            for dx in range(-horizontal_range,horizontal_range+1):
                x,y=cx+dx,cy+dy
                if clearance and (name, ja) != ('WP_MC13', '島繋回廊') and (x-1 < x0 or y-1 < y0 or
                                  x+mask.width+2 > x1 or y+mask.height+1 > y1):
                    continue
                right_margin = 35 if special_shift else 18
                if x<max(1,x0-18) or y<max(1,y0-18) or x+mask.width+1>min(im.width-1,x1+right_margin) or y+mask.height>min(im.height-1,y1+18):
                    continue
                if name == 'WP_MC05' and ja == '三角州の村' and x < 50:
                    continue  # Clear both the blue node and its diagonal dotted road.
                if name == 'WP_MC08' and ja == '流砂の町' and x != 26:
                    continue  # Restore the original label's position next to its arrow.
                if name == 'WP_MC13' and ja == '島繋回廊' and (x, y) != (137, 223):
                    continue  # Keep the established r3 label position.
                collisions=sum((x+u,y+v) in (arrow if clearance else protected) for u,v in footprint)
                other_collisions = sum(any(a<=x+u<c and b<=y+v<d for a,b,c,d in other_boxes) for u,v in footprint) if revised else 0
                if name == 'WP_MC13' and ja == '草露の道':
                    near_road = sum(any((x+u+vx,y+v+vy) in road for vx in range(-2,3) for vy in range(-2,3)) for u,v in footprint)
                elif clearance:
                    near_road = sum((x+u,y+v) in (road | road_edge) for u,v in halo)
                else:
                    near_road = sum(any((x+u+vx,y+v+vy) in road for vx,vy in ((-1,0),(1,0),(0,-1),(0,1))) for u,v in footprint) if kind == 'town' else 0
                candidates.append((collisions,other_collisions,abs(dx)+abs(dy)+3*near_road,abs(dx)+abs(dy),abs(dy),dy,dx,x,y))
        if not candidates:
            raise ValueError(f'{name} {ja}: translation does not fit')
        collisions,other_collisions,_,_,_,_,_,x,y=min(candidates)
        if collisions:
            raise ValueError(f'{name} {ja}: cannot avoid {collisions} road pixels')
        if other_collisions:
            raise ValueError(f'{name} {ja}: cannot avoid adjacent label')
        if clearance:
            # Remove only visible road pixels immediately next to the text;
            # reconstruct those tiny gaps from adjacent terrain before drawing.
            halo_points = {(x+u,y+v) for u,v in halo}
            affected = halo_points & (road | road_edge)
            # Erasing original text may itself have propagated a nearby dot.
            affected |= {p for p in halo_points if im.getpixel(p) in road_colors}
            if affected & arrow:
                raise ValueError(f'{name} {ja}: road clearance touches an arrow')
            current_road = {(u,v) for v in range(im.height) for u in range(im.width)
                            if im.getpixel((u,v)) in road_colors}
            fill_road_gap(im, affected, protected | current_road)
            road_cleared.update(affected & protected)
        allowed.update((u,v) for v in range(y0,y1) for u in range(x0,x1))
        allowed.update((u,v) for v in range(y,y+mask.height) for u in range(x,x+mask.width+1))
        im.paste(shadow,(x+1,y),mask)
        im.paste(black,(x,y),mask)
        if clearance:
            leaks = [(x+u,y+v) for u,v in halo if im.getpixel((x+u,y+v)) in road_colors]
            assert not leaks, f'{name} {ja}: road in text margin {leaks[:10]}'
        labels.append({'ja':glossary_ja,'zh':zh,'source_box':bounds,'inspection_box':box,
                       'render_box':[x,y,x+mask.width+1,y+mask.height],
                       'color_index':black,'shadow_color_index':shadow,'shadow_offset':[1,0],
                       'font_height':-17 if kind == 'town' else -12,
                       'font_face':'Microsoft JhengHei bold, binary' if kind == 'town' else 'MingLiU, binary',
                       'ink_size':[mask.width,mask.height],
                       'fill':('nearby terrain patch matching' if textured else
                               'inward terrain propagation excluding road and arrows' if (name, ja) in R4_TERRAIN_FILL else
                               'inward nearest-neighbour propagation of ink and shadow only'),
                       'fits':x>=x0 and y>=y0 and x+mask.width+1<=x1 and y+mask.height<=y1,
                       'within_allowed_area':True,
                       'protected_road_pixels_in_source_box':sum(x0<=u<x1 and y0<=v<y1 for u,v in road | road_edge),
                       'road_pixels_cleared_for_text_margin':len(affected) if clearance else 0,
                       'road_clearance_radius_pixels':radius if clearance else 0,
                       'review':'Underlying terrain and obscured road segments cannot be recovered exactly from the flattened source.'})
    assert all(im.getpixel(p)==original.getpixel(p) for p in protected - road_cleared), 'Road or arrow pixel changed'
    if revised:
        changed={(x,y) for y in range(im.height) for x in range(im.width) if im.getpixel((x,y)) != original.getpixel((x,y))}
        assert changed <= allowed, f'{name}: changed pixels outside label boxes'
    result=bytearray(source)
    for row in range(im.height):
        pos=offset+(im.height-1-row)*stride
        result[pos:pos+im.width]=im.crop((0,row,im.width,row+1)).tobytes()
    result=bytes(result)
    assert result[:offset]==source[:offset] and len(result)==len(source)
    packed=bmh.encode_huffman(result,packed_source)
    assert bmh.decode(packed)==result
    decoded,_,_=load_dib(result)
    assert decoded.tobytes()==im.tobytes()
    OUT.mkdir(exist_ok=True)
    (OUT/(name+'.dib')).write_bytes(result)
    (OUT/(name+'.BMH')).write_bytes(packed)
    assert bmh.decode((OUT/(name+'.BMH')).read_bytes()) == (OUT/(name+'.dib')).read_bytes()
    im.convert('RGB').save(OUT/(name+'.png'))
    compare=Image.new('RGB',(im.width*2,im.height*4))
    compare.paste(original.convert('RGB').resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(0,0))
    compare.paste(im.convert('RGB').resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(0,im.height*2))
    compare.save(OUT/('compare_'+name+'.png'))
    report_path=OUT/'report.json'
    report=json.loads(report_path.read_text(encoding='utf-8-sig')) if report_path.exists() else {'maps':[]}
    record={'name':name,'header_palette_identical':True,'huffman_roundtrip':True,
            'original_visible_road_pixels_and_down_right_shadows_preserved':not bool(road_cleared),
            'road_pixels_cleared_for_label_margin':len(road_cleared),
            'arrow_rectangles_identical':True,'arrow_rectangles':ARROWS[name],'labels':labels}
    if revised:
        record['difference_within_label_boxes'] = True
        record['changed_pixels'] = len(changed)
    report['maps']=[r for r in report['maps'] if r['name']!=name]+[record]
    report['maps'].sort(key=lambda r:r['name'])
    done={r['name'] for r in report['maps']}
    report['complete']=all(f'WP_MC{i:02}' in done for i in range(17))
    report['scope']='all WP_MC00–WP_MC16' if report['complete'] else 'partial; completed maps listed below'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{name}: {len(labels)} labels; header/palette, arrows and BMH round-trip verified; {len(road_cleared)} protected road pixels cleared')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--only',choices=sorted(SPECS),help='Build just one map in this batch')
    args=parser.parse_args()
    for name in ([args.only] if args.only else [f'WP_MC{i:02}' for i in range(9,17)]):
        run(name)
