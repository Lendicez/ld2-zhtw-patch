r"""產生 cp950_variants.json：CP932 有、CP950（Big5）沒有的字 → Big5 可表示的對應字（顯示用）。

來源（建置時不需要；只在重新產生表時使用）：
- Unicode Unihan 資料庫 Unihan_Variants.txt（kZVariant／kCompatibilityVariant／kSemanticVariant／
  kSpecializedSemanticVariant／kTraditionalVariant；Unicode License v3）
- OpenCC（jp2t 日本新字體→舊字體、s2t、t2tw；Apache-2.0），以及 NFKC 相容分解
- MANUAL：日本國字等沒有對應的字，人工指定（見下）

用法：python gen_cp950_variants.py <Unihan.zip>（需 pip install opencc）。
"""
import json,re,collections,unicodedata,sys,zipfile
from pathlib import Path
import opencc
var=collections.defaultdict(dict)
with zipfile.ZipFile(sys.argv[1]) as z:
    for line in z.read('Unihan_Variants.txt').decode('utf-8').splitlines():
        if line.startswith('#') or not line.strip(): continue
        cp,field,val=line.split('\t')
        var[chr(int(cp[2:],16))][field]=[chr(int(m,16)) for m in re.findall(r'U\+([0-9A-F]+)',val)]
jp2t=opencc.OpenCC('jp2t'); s2t=opencc.OpenCC('s2t'); t2tw=opencc.OpenCC('t2tw')
def enc(x):
    try: x.encode('cp950'); return True
    except: return False
MANUAL={'宍':'肉','惣':'總','駄':'馱','込':'入','繋':'繫','働':'動','姫':'姬','頬':'頰','涜':'瀆','駈':'驅','峠':'嶺','喰':'食','嶋':'島','蝿':'蠅','産':'產','舎':'舍','聡':'聰','≪':'《','≫':'》','┣':'├','╋':'┼','┛':'┘','┥':'┤','┫':'┤','┳':'┬','┻':'┴','┏':'┌','┓':'┐','┗':'└','━':'─','┃':'│','ー':'－','・':'‧','〜':'～','鮎':'鮎','叶':'葉','笹':'筱','榊':'神','辻':'十','畑':'田','畠':'田','凪':'止','匁':'匁','枠':'框','栃':'櫪','樫':'橿','塀':'屏','雫':'滴','俣':'俁','麿':'麻','杢':'木','籾':'穀','鰯':'鰮','鴫':'鷸','凧':'箏','柾':'柾','椛':'樺','梶':'柁','硲':'硲','噺':'話','腺':'腺','匂':'匂','裃':'裃','躾':'躾','錺':'飾','鋲':'鉚','鞆':'鞆','颪':'颪'}
def cands(ch):
    v=var.get(ch,{})
    out=[]
    out+=v.get('kZVariant',[])+v.get('kCompatibilityVariant',[])
    out.append(unicodedata.normalize('NFKC',ch))
    out.append(jp2t.convert(ch))
    out+=v.get('kSemanticVariant',[])+v.get('kSpecializedSemanticVariant',[])
    tv=v.get('kTraditionalVariant',[])
    if ch not in tv: out+=tv
    out.append(s2t.convert(ch)); out.append(t2tw.convert(jp2t.convert(ch)))
    return out
def best(ch):
    if ch in MANUAL:
        m=MANUAL[ch]
        return m if (m!=ch and all(enc(c) for c in m)) else None
    seen=[]
    for c in cands(ch):
        if len(c)==1 and c!=ch and enc(c): return c
        if len(c)==1 and c!=ch: seen.append(c)
    for c in seen:   # 二次：變體的變體
        for c2 in cands(c):
            if len(c2)==1 and c2!=ch and enc(c2): return c2
    return None
table={}; left=[]
for hi in list(range(0x81,0xa0))+list(range(0xe0,0xfd)):
    for lo in list(range(0x40,0x7f))+list(range(0x80,0xfd)):
        try: ch=bytes([hi,lo]).decode('cp932')
        except: continue
        if len(ch)!=1 or enc(ch): continue
        m=best(ch)
        if m: table[ch]=m
        else: left.append(ch)
out=Path(__file__).with_name('cp950_variants.json')
out.write_text(json.dumps(dict(sorted(table.items())),ensure_ascii=False,indent=0)+'\n','utf-8')
print(len(table),'mapped',len(left),'left')
