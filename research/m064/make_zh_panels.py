"""Lab-only BMH status panel translation. Reads pristine resources; writes here only."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path
import io, json, struct
from PIL import Image
import bmh

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('LD2_PRISTINE_RES', 'pristine/RES'))  # 使用者的原版 RES 目錄（只讀）
OUT = HERE / 'out_zh_bmh'
# Each box is an exclusive rectangle in source image coordinates. Limits reserve
# room for longer translations and avoid neighboring labels, icons, and frames.
SPECS = {
'WI_STA00': [
 ('性別','性別',(90,41,121,57)),('年齢','年齡',(151,41,182,57)),('特徴','特徵',(90,73,121,89)),('状態','狀態',(90,93,121,109)),
 ('秩','秩',(225,40,242,53)),('善','善',(193,71,209,85)),('悪','惡',(257,71,273,85)),('混','混',(225,101,242,115)),
 ('体力','體力',(12,127,44,143)),('魔力','魔力',(12,151,44,167)),('筋力','筋力',(12,179,44,195)),('知性','知性',(12,203,44,219)),('敏捷','敏捷',(12,227,44,243)),('魅力','魅力',(12,251,44,267)),
 ('武','武',(47,295,63,311)),('盾','盾',(99,295,115,311)),('兜','盔',(151,295,167,311)),('鎧','鎧',(203,295,219,311)),('他','他',(255,295,272,311)),('所持金','持有金錢',(125,317,173,333),(125,316,190,334))],
'WI_STA01': [
 ('性別','性別',(90,41,121,57)),('年齢','年齡',(151,41,182,57)),('特徴','特徵',(90,73,121,89)),('状態','狀態',(90,93,121,109)),
 ('秩','秩',(225,40,242,53)),('善','善',(193,71,209,85)),('悪','惡',(257,71,273,85)),('混','混',(225,101,242,115)),
 ('通常戦闘力','一般戰力',(13,141,87,157),(13,140,98,158)),('攻撃','攻擊',(98,141,130,157)),('防御','防禦',(156,141,188,157)),('回避','迴避',(214,141,246,157)),
 ('魔法攻撃力','魔法攻擊力',(13,183,87,199),(13,182,96,200)),('魔法防御力','魔法防禦力',(137,183,211,199),(137,182,220,200)),
 ('秩','秩',(97,191,113,205)),('善','善',(65,221,81,235)),('悪','惡',(129,221,145,235)),('混','混',(97,251,113,265)),
 ('秩','秩',(221,191,237,205)),('善','善',(189,221,205,235)),('悪','惡',(253,221,269,235)),('混','混',(221,251,237,265)),('特殊技能','特殊技能',(9,278,70,294))],
'WI_STA02': [('誕生日','生日',(84,41,131,57)),('月','月',(156,41,172,57)),('日','日',(188,41,204,57)),('年齢','年齡',(211,41,244,57)),('出身国','出身國',(84,59,131,75)),('出身地','出身地',(84,77,131,93)),('家','家',(98,95,115,111)),('父親','父親',(8,125,40,141)),('母親','母親',(8,171,40,187)),('配偶者','配偶',(8,217,55,233)),('子供','子女',(8,263,40,279))],
'WI_INFC': [('秩','秩',(30,32,45,46)),('善','善',(0,61,14,75)),('悪','惡',(61,61,76,75)),('混','混',(30,92,45,103)),('年','年',(119,43,135,59)),('月','月',(156,43,172,59)),('日','日',(188,43,204,59)),('人口','人口',(88,61,120,77)),('人','人',(171,61,187,77)),('知名度','知名度',(88,79,135,95))],
'WI_INFD': [('年','年',(119,43,135,59)),('月','月',(156,43,172,59)),('日','日',(188,43,204,59)),('明り','照明',(98,79,130,96))],
'WI_STAB': [('種類','種類',(12,58,44,74)),('箇所','部位',(175,58,207,74)),('攻撃','攻擊',(16,80,48,96)),('防御','防禦',(80,80,112,96)),('速度','速度',(144,80,176,96)),('命中','命中',(208,80,240,96)),('秩序','秩序',(16,104,48,120)),('混沌','混沌',(80,104,112,120)),('善','善',(152,104,168,120)),('悪','惡',(216,104,232,120))],
'WI_STAK': [('体力','體力',(84,40,111,54)),('魔力','魔力',(84,64,111,78)),('攻','攻',(84,92,99,106)),('防','防',(119,92,134,106)),('回','避',(154,92,169,106))],
'WI_CARAS': [('キャラクターシンボル：','角色圖示：',(15,18,210,37),(15,18,210,37))]
}

def gdi_mask(text, height=-12):
 g = ctypes.WinDLL('gdi32', use_last_error=True)
 def api(name, result, *args):
  f = getattr(g,name); f.restype=result; f.argtypes=args; return f
 H=wintypes.HANDLE
 dcnew=api('CreateCompatibleDC',H,H); create=api('CreateDIBSection',H,H,ctypes.c_void_p,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p),H,wintypes.DWORD)
 fontnew=api('CreateFontW',H,*([ctypes.c_int]*5),*([wintypes.DWORD]*8),wintypes.LPCWSTR)
 sel=api('SelectObject',H,H,H); delete=api('DeleteObject',wintypes.BOOL,H); deletedc=api('DeleteDC',wintypes.BOOL,H)
 bk=api('SetBkMode',ctypes.c_int,H,ctypes.c_int); color=api('SetTextColor',wintypes.DWORD,H,wintypes.DWORD)
 out=api('TextOutW',wintypes.BOOL,H,ctypes.c_int,ctypes.c_int,wintypes.LPCWSTR,ctypes.c_int)
 face=api('GetTextFaceW',ctypes.c_int,H,ctypes.c_int,wintypes.LPWSTR)
 w,h=512,48; info=ctypes.create_string_buffer(struct.pack('<IiiHHIIiiII',40,w,-h,1,32,0,0,0,0,0,0)); bits=ctypes.c_void_p()
 dc=dcnew(None); bitmap=create(dc,info,0,ctypes.byref(bits),None,0); font=fontnew(height,0,0,0,400,0,0,0,136,0,0,3,0,'細明體')
 if not dc or not bitmap or not font or not bits.value: raise ctypes.WinError(ctypes.get_last_error())
 ob=sel(dc,bitmap); of=sel(dc,font)
 try:
  actual=ctypes.create_unicode_buffer(128); face(dc,128,actual)
  if actual.value not in ('細明體','MingLiU'): raise ValueError('Unexpected font: '+actual.value)
  ctypes.memset(bits,0,w*h*4); bk(dc,1); color(dc,0xffffff)
  if not out(dc,0,0,text,len(text)): raise ctypes.WinError(ctypes.get_last_error())
  raw=Image.frombytes('RGB',(w,h),ctypes.string_at(bits,w*h*4),'raw','BGRX')
  if not set(raw.getdata()) <= {(0,0,0),(255,255,255)}:
   raise ValueError('GDI returned non-binary text pixels')
  im=raw.convert('1',dither=Image.Dither.NONE)
  if not im.getbbox(): raise ValueError('Empty text: '+text)
  return im.crop(im.getbbox())
 finally:
  sel(dc,of); sel(dc,ob); delete(font); delete(bitmap); deletedc(dc)

# Hand-edited from MingLiU -12; the advance and original placement stay intact.
# Each row is an ink bitmap, and the detached strokes remain binary pixels.
HAND_GLYPHS = {
 '鬥': ['####.#####','#.#....#.#','####.#####','#.#....#.#','####.#####',
        '#..#..#..#','#.....#..#','#...#.#..#','#.######.#','#.....#..#','#.....####'],
 '禦': ['.#..###.###','#.#.#.#.#.#','.#..#####.#','##..#.#.#.#','.#.#######.',
        '.#.#.#..#.#','.#.###..###','...........','###########','..#..#..#..','.#...#...#.'],
 '惡': ['###########','...#...#...','.###...###.','.#.#...#.#.','.###...###.',
        '...#...#...','###########','...........','..#..#...#.','.#..#.#...#','#...####..#'],
}

def patched_mask(text):
 mask=gdi_mask(text)
 for index,char in enumerate(text):
  if char not in HAND_GLYPHS: continue
  original=gdi_mask(char)
  # Match the untouched glyph in the full GDI rendering, preserving kerning and
  # baseline. A unique match is required so no adjacent character is changed.
  matches=[]
  for y in range(mask.height-original.height+1):
   for x in range(mask.width-original.width+1):
    if all(mask.getpixel((x+dx,y+dy))==original.getpixel((dx,dy))
           for dy in range(original.height) for dx in range(original.width)):
     matches.append((x,y))
  if len(matches)!=1: raise ValueError(f'Cannot uniquely locate {char} in {text}: {matches}')
  x,y=matches[0]; rows=HAND_GLYPHS[char]
  if len(rows)!=original.height or any(len(row)!=original.width for row in rows):
   raise ValueError(f'Wrong hand glyph dimensions: {char}')
  for dy,row in enumerate(rows):
   for dx,pixel in enumerate(row): mask.putpixel((x+dx,y+dy),255 if pixel=='#' else 0)
 return mask

def load_dib(d):
 hdr,w,h,planes,bpp,compression=struct.unpack_from('<IiiHHI',d)
 colors=struct.unpack_from('<I',d,32)[0] or 256
 if (hdr,planes,bpp,compression)!=(40,1,8,0) or h<=0: raise ValueError('Unexpected DIB format')
 offset=hdr+colors*4; stride=(w+3)&~3
 header=b'BM'+struct.pack('<IHHI',len(d)+14,0,0,offset+14)
 im=Image.open(io.BytesIO(header+d)); im.load()
 return im,offset,stride


def approved_glyphs():
 """Extract approved black ink from the saved r4 WI_STAB, using its report."""
 baseline=HERE/'panels_r4_baseline'
 report=json.loads((baseline/'report.json').read_text(encoding='utf-8-sig'))
 stab=next(panel for panel in report if panel['name']=='WI_STAB')
 image,_,_=load_dib((baseline/'WI_STAB.dib').read_bytes())
 palette=image.getpalette()
 black=next(i for i in range(256) if palette[i*3:i*3+3]==[1,1,1])
 result={}
 for char,word,height in [('惡','惡',-15),('禦','防禦',-14)]:
  entry=next(label for label in stab['labels'] if label['translated']==word)
  box=entry['render_box']
  pixels=image.crop(box).point(lambda value: 255 if value==black else 0).convert('1')
  expected=gdi_mask(char,height)
  matches=[]
  for y in range(pixels.height-expected.height+1):
   for x in range(pixels.width-expected.width+1):
    if pixels.crop((x,y,x+expected.width,y+expected.height)).tobytes()==expected.tobytes():
     matches.append((x,y))
  if len(matches)!=1: raise ValueError(f'Approved glyph {char}: {matches}')
  x,y=matches[0]
  glyph_box=(box[0]+x,box[1]+y,box[0]+x+expected.width,box[1]+y+expected.height)
  result[char]=(pixels.crop((x,y,x+expected.width,y+expected.height)),glyph_box)
 return result


def r6_evil_mask():
 """Recover the finalized STA00 glyph directly from the saved r6 DIB."""
 baseline=HERE/'panels_r6_baseline'
 report=json.loads((baseline/'report.json').read_text(encoding='utf-8-sig'))
 panel=next(p for p in report if p['name']=='WI_STA00')
 entry=next(e for e in panel['labels'] if e['translated']=='惡' and e['scan_box'][:2]==[257,71])
 image,_,_=load_dib((baseline/'WI_STA00.dib').read_bytes())
 x,y,_,_=entry['render_box']; w,h=entry['ink_size']
 return image.crop((x,y,x+w,y+h)).point(lambda v: 255 if v==16 else 0).convert('1'), [x,y,x+w,y+h]


def r5_mask(text, glyphs):
 """Use GDI -12 for the word and insert the unscaled approved r4 glyphs."""
 mask=gdi_mask(text,-12)
 replacements=[]
 for char in ('惡','禦'):
  if char not in text: continue
  original=gdi_mask(char,-12)
  matches=[]
  for y in range(mask.height-original.height+1):
   for x in range(mask.width-original.width+1):
    if mask.crop((x,y,x+original.width,y+original.height)).tobytes()==original.tobytes():
     matches.append((x,y))
  if len(matches)!=1: raise ValueError(f'Cannot locate {char} in {text}: {matches}')
  x,y=matches[0]
  replacements.append((x,y,original,glyphs[char][0],char))
 if not replacements: return mask,[]
 # Preserve the GDI spacing and increase the advance only by the extra width
 # required by an approved glyph, so it cannot overwrite the next character.
 width=mask.width+sum(g.width-o.width for _,_,o,g,_ in replacements)
 height=max(mask.height,*(g.height for _,_,_,g,_ in replacements))
 result=Image.new('1',(width,height)); shift=0; start=0; positions=[]
 for x,y,old,glyph,char in sorted(replacements):
  result.paste(mask.crop((start,0,x,mask.height)),(start+shift,(height-mask.height)//2))
  gx=x+shift; gy=(height-glyph.height)//2
  result.paste(glyph,(gx,gy)); positions.append((char,gx,gy,glyph.width,glyph.height))
  shift+=glyph.width-old.width; start=x+old.width
 result.paste(mask.crop((start,0,mask.width,mask.height)),(start+shift,(height-mask.height)//2))
 return result,positions

def main():
 OUT.mkdir(exist_ok=True); report=[]; glyphs=approved_glyphs(); evil_r6,evil_r6_box=r6_evil_mask()
 for name,labels in SPECS.items():
  source=(SOURCE/(name+'.BMH')).read_bytes(); dib=bmh.decode(source); im,offset,stride=load_dib(dib); original=im.copy(); palette=im.getpalette()
  black=next(i for i in range(256) if palette[i*3:i*3+3]==[1,1,1]); shadow=next((i for i in range(256) if palette[i*3:i*3+3]==[90,90,90]),None)
  records=[]
  for item in labels:
   old,new,box=item[:3]; limit=item[3] if len(item)>3 else box
   ink={(x,y) for y in range(box[1],box[3]) for x in range(box[0],box[2]) if original.getpixel((x,y))==black}
   # Most original labels have a rightward 90-gray shadow. WI_INFC's
   # alignment marker instead has a 200-gray shadow; some have none.
   shadow_index=next(i for i in range(256) if palette[i*3:i*3+3]==[200,200,200]) if name=='WI_INFC' and old=='悪' else shadow
   shadow_pts={(x+1,y) for x,y in ink if x+1<box[2] and original.getpixel((x+1,y))==shadow_index} if shadow_index is not None else set()
   if name=='WI_CARAS' or len(shadow_pts)<max(4,len(ink)*0.12): shadow_pts=set()
   pts=ink|shadow_pts
   if not pts: raise ValueError(f'{name} {old}: no ink found in {box}')
   bounds=(min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts)+1,max(y for x,y in pts)+1)
   record={'original':old,'translated':new,'source_box':list(bounds),'scan_box':list(box),'render_box':None,'font_height':None,'fits':True,'kept_original':old==new}
   if old!=new:
    # Fill only dark ink/shadow pixels from the closest non-ink background in
    # the original box. This retains nearby textured pixels and never paints frames.
    for x,y in pts:
     found=None
     for radius in range(1,20):
      candidates=[]
      for dy in range(-radius,radius+1):
       for dx in range(-radius,radius+1):
        if max(abs(dx),abs(dy))!=radius: continue
        xx,yy=x+dx,y+dy
        if box[0]<=xx<box[2] and box[1]<=yy<box[3] and (xx,yy) not in pts:
         candidates.append((dx*dx+dy*dy,abs(dy),yy,xx))
      if candidates:
       _,_,yy,xx=min(candidates); found=original.getpixel((xx,yy)); break
     if found is None: raise ValueError(f'Cannot reconstruct {name} {old}')
     im.putpixel((x,y),found)
    x=bounds[0]
    # The original title has 16 ink rows; MingLiU -17 renders exactly 16.
    extra=int(bool(shadow_pts))
    is_r5=name in ('WI_STA00','WI_STA01','WI_INFC')
    is_r4=not is_r5 and name!='WI_STA02' and any(c in new for c in '鬥禦惡齡')
    fallback=False
    glyph_positions=[]
    if new=='惡':
     # Match the measured black-ink height of the adjacent original 善:
     # STA00/STA01 11x11, INFC 9x10, STAB 13x13.
     font_height={'WI_STA00':-12,'WI_STA01':-12,'WI_INFC':-11,'WI_STAB':-14}[name]
     mask=gdi_mask(new,font_height)
     reference_box=max((spec[2] for spec in labels if spec[0]=='善' and
                        abs(spec[2][1]-box[1])<=1 and spec[2][0]<box[0]), key=lambda b:b[0])
     good=[(xx,yy) for yy in range(reference_box[1],reference_box[3])
           for xx in range(reference_box[0],reference_box[2]) if original.getpixel((xx,yy))==black]
     good_box=(min(xx for xx,yy in good),min(yy for xx,yy in good),
               max(xx for xx,yy in good)+1,max(yy for xx,yy in good)+1)
     if name=='WI_STAB':
      # Enlarge the exact approved bitmap using binary nearest-neighbor pixels.
      mask=evil_r6.resize((good_box[2]-good_box[0],good_box[3]-good_box[1]),Image.Resampling.NEAREST)
      font_height=-12
      shadow_pts=set(); extra=0
      record['reused_glyphs']=[{'character':'惡','source_panel':'WI_STA00',
        'source_box':evil_r6_box,'source_version':6,'scaling':'nearest'}]
      record['text_color_index']=black
     if mask.height!=good_box[3]-good_box[1]: raise ValueError(f'{name}: alignment glyph height mismatch')
     y=good_box[1]
     record['reference_good_ink_box']=list(good_box)
     record['reference_good_ink_size']=[good_box[2]-good_box[0],good_box[3]-good_box[1]]
     record['ink_size']=list(mask.size)
    elif is_r5:
     font_height=-12
     mask,glyph_positions=r5_mask(new,glyphs)
     y=(bounds[1]+bounds[3]-mask.height+1)//2 if glyph_positions else bounds[3]-mask.height
     if glyph_positions: y=max(limit[1],min(y,limit[3]-mask.height))
    elif is_r4:
     # Fit the entire unmodified GDI word, including its original shadow, in
     # the label's reserved rectangle. Center on the source ink row.
     for font_height in (-15,-14,-13):
      mask=gdi_mask(new,font_height)
      y=(bounds[1]+bounds[3]-mask.height+1)//2
      if (x>=limit[0] and y>=limit[1] and
          x+mask.width+extra<=limit[2] and y+mask.height<=limit[3]):
       break
     else:
      fallback=True
      font_height=-12
      mask=patched_mask(new)
      y=bounds[3]-mask.height
    else:
     font_height=-17 if name=='WI_CARAS' else -12
     mask=gdi_mask(new,font_height) if name=='WI_CARAS' else patched_mask(new)
     y=bounds[3]-mask.height
    if x<limit[0] or y<limit[1] or x+mask.width+extra>limit[2] or y+mask.height>limit[3]:
     raise ValueError(f'Text does not fit at -12: {name} {old} -> {new}, ink {x,y,mask.width,mask.height}, limit {limit}')
    if shadow_pts: im.paste(shadow_index,(x+1,y),mask)
    im.paste(black,(x,y),mask)
    record.update(render_box=[x,y,x+mask.width+extra,y+mask.height],font_height=font_height,shadow_color_index=shadow_index if shadow_pts else None,shadow_offset=[1,0] if shadow_pts else None)
    if new in ('年齡','一般戰力'):
     record['text_color_index']=black
    if glyph_positions:
     record['reused_glyphs']=[{'character':char,'source_panel':'WI_STAB',
       'source_box':list(glyphs[char][1]),'render_box':[x+gx,y+gy,x+gx+w,y+gy+h]}
       for char,gx,gy,w,h in glyph_positions]
    if is_r4:
     record.update(r4_fit=not fallback, r4_kept_previous=fallback,
                   available_box=list(limit))
     if fallback:
      record['r4_note']='-15、-14、-13 均超出可用範圍，保留第 3 版'
   records.append(record)
  result=bytearray(dib)
  for y in range(im.height):
   row=offset+(im.height-1-y)*stride
   result[row:row+im.width]=bytes(im.crop((0,y,im.width,y+1)).getdata())
  result=bytes(result)
  assert result[:offset]==dib[:offset] and len(result)==len(dib)
  packed=bmh.encode_huffman(result,source)
  assert bmh.decode(packed)==result
  check,_,_=load_dib(result); assert check.tobytes()==im.tobytes()
  (OUT/(name+'.dib')).write_bytes(result); (OUT/(name+'.BMH')).write_bytes(packed)
  im.convert('RGB').save(OUT/(name+'.png'))
  compare=Image.new('RGB',(im.width*2,im.height*4))
  compare.paste(original.convert('RGB').resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(0,0))
  compare.paste(im.convert('RGB').resize((im.width*2,im.height*2),Image.Resampling.NEAREST),(0,im.height*2))
  compare.save(OUT/('compare_'+name+'.png'))
  # Original Japanese and the new result side by side at 8x, including every
  # occurrence of the requested words, even a retained version-3 fallback.
  for record in records:
   if not (record['translated']=='一般戰力' or any(c in record['translated'] for c in '禦惡齡')): continue
   a,b=record['scan_box'],record['render_box']
   crop=(max(0,min(a[0],b[0])-2),max(0,min(a[1],b[1])-2),
         min(im.width,max(a[2],b[2])+2),min(im.height,max(a[3],b[3])+2))
   left=original.convert('RGB').crop(crop); right=im.convert('RGB').crop(crop)
   review=Image.new('RGB',(left.width*2+2,left.height),(255,0,255))
   review.paste(left,(0,0)); review.paste(right,(left.width+2,0))
   zoom=OUT/'zoom'; zoom.mkdir(exist_ok=True)
   filename=f"{name}_{record['translated']}_{a[0]}_{a[1]}.png"
   scaled=review.resize((review.width*8,review.height*8),Image.Resampling.NEAREST)
   scaled.save(zoom/filename)
   aliases={('WI_STA00','年齡'):'年齡',('WI_STA00','惡'):'惡',
            ('WI_STA01','一般戰力'):'一般戰力',('WI_STA01','防禦'):'防禦',
            ('WI_STA02','年齡'):'年齡'}
   alias=aliases.get((name,record['translated']))
   if alias: scaled.save(zoom/(name+'_'+alias+'.png'))
  # Source character and corresponding rendered character, at native pixel
  # coordinates; scale only after composing to retain the original palette.
  glyph_reviews={}
  for char,old_box,new_box in glyph_reviews.get(name,[]):
   left=original.convert('RGB').crop(old_box); right=im.convert('RGB').crop(new_box)
   review=Image.new('RGB',(left.width+right.width+2,max(left.height,right.height)),(255,0,255))
   review.paste(left,(0,0)); review.paste(right,(left.width+2,0))
   zoom=OUT/'zoom'; zoom.mkdir(exist_ok=True)
   review.resize((review.width*12,review.height*12),Image.Resampling.NEAREST).save(zoom/('glyph_'+char+'_12x.png'))
  report.append({'name':name,'size':list(im.size),'header_palette_identical':True,'huffman_roundtrip':True,'labels':records})
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'{len(report)} panels, {sum(len(r["labels"]) for r in report)} labels, Huffman round trips passed')
if __name__=='__main__': main()
