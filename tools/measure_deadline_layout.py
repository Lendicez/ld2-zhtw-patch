"""Offscreen MingLiU metrics for the fixed m040 layout; no HWND/window/DPI changes."""
import ctypes as C,json,struct,sys
from ctypes import wintypes as W
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ld2patch.deadline_text import format_deadline
class MemoryFont:
 def __init__(self,point,dpi):
  self.g=C.WinDLL('gdi32',use_last_error=True);g=self.g
  g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
  g.CreateFontW.argtypes=[C.c_int]*5+[W.DWORD]*8+[W.LPCWSTR];g.CreateFontW.restype=W.HFONT
  g.SelectObject.argtypes=[W.HDC,W.HANDLE];g.SelectObject.restype=W.HANDLE
  g.GetTextExtentPoint32W.argtypes=[W.HDC,W.LPCWSTR,C.c_int,C.c_void_p];g.GetTextExtentPoint32W.restype=W.BOOL
  g.GetTextFaceW.argtypes=[W.HDC,C.c_int,W.LPWSTR];g.GetTextFaceW.restype=C.c_int
  g.GetGlyphIndicesW.argtypes=[W.HDC,W.LPCWSTR,C.c_int,C.POINTER(W.WORD),W.DWORD];g.GetGlyphIndicesW.restype=W.DWORD
  g.DeleteObject.argtypes=[W.HANDLE];g.DeleteDC.argtypes=[W.HDC]
  self.dc=g.CreateCompatibleDC(None)
  if not self.dc:raise C.WinError()
  self.font=g.CreateFontW(-round(point*dpi/72),0,0,0,400,0,0,0,136,0,0,0,0,'MingLiU')
  if not self.font:g.DeleteDC(self.dc);raise C.WinError()
  self.prior=g.SelectObject(self.dc,self.font)
  if not self.prior or self.prior==C.c_void_p(-1).value:self.close();raise C.WinError()
  name=C.create_unicode_buffer(128)
  if not g.GetTextFaceW(self.dc,len(name),name):self.close();raise C.WinError()
  self.face=name.value
  g.GetFontData.argtypes=[W.HDC,W.DWORD,W.DWORD,C.c_void_p,W.DWORD];g.GetFontData.restype=W.DWORD
  tag=int.from_bytes(b'name','little');size=g.GetFontData(self.dc,tag,0,None,0)
  if size==0xffffffff or size<6 or size>1048576:self.close();raise ValueError('Font name table unavailable')
  raw=C.create_string_buffer(size)
  if g.GetFontData(self.dc,tag,0,raw,size)!=size:self.close();raise ValueError('Font name table read failed')
  data=raw.raw;fmt,count,offset=struct.unpack_from('>HHH',data);self.internal_names=[]
  if 6+12*count>len(data):self.close();raise ValueError('Malformed font name records')
  for i in range(count):
   plat,enc,lang,nid,length,pos=struct.unpack_from('>HHHHHH',data,6+12*i)
   if nid not in [1,4,6] or plat not in [0,3]:continue
   if offset+pos+length>len(data):self.close();raise ValueError('Malformed font name string')
   value=data[offset+pos:offset+pos+length].decode('utf-16be')
   self.internal_names.append({'name_id':nid,'language':lang,'value':value})
  if not any(x['value']=='MingLiU' for x in self.internal_names):self.close();raise ValueError('Selected font identity not MingLiU: '+self.face)
 def extent(self,s):
  v=(C.c_long*2)();n=len(s.encode('utf-16le'))//2
  if not self.g.GetTextExtentPoint32W(self.dc,s,n,v):raise C.WinError()
  return list(v)
 def missing(self,s):
  n=len(s.encode('utf-16le'))//2;buf=(W.WORD*n)();rc=self.g.GetGlyphIndicesW(self.dc,s,n,buf,1)
  if rc==0xffffffff or rc!=n:raise ValueError('Glyph query failed')
  return [s[i] for i,k in enumerate(buf) if k==0xffff]
 def close(self):
  if getattr(self,'prior',None):self.g.SelectObject(self.dc,self.prior)
  if getattr(self,'font',None):self.g.DeleteObject(self.font)
  if getattr(self,'dc',None):self.g.DeleteDC(self.dc)

def measure():
 if sys.platform!='win32':raise RuntimeError('Windows GDI required; not a runtime game test')
 u=C.WinDLL('user32',use_last_error=True)
 u.DrawTextW.argtypes=[W.HDC,W.LPCWSTR,C.c_int,C.POINTER(W.RECT),W.UINT];u.DrawTextW.restype=C.c_int
 rows=[]
 for dpi in (96,120,144,192):
  f=MemoryFont(14,dpi)
  try:
   sx,sy=f.extent('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz');bx=(sx//26+1)//2
   for n in (-2147483648,-2147483647,-365,-1,0,1,30,365,999,1000,2147483647):
    text=format_deadline(n);tw,th=f.extent(text);w=int(115*bx/4);h=sy
    r=W.RECT(0,0,w,h)
    if not u.DrawTextW(f.dc,text,len(text),C.byref(r),0x410):raise C.WinError()
    missing=f.missing(text)
    rows.append(dict(dpi=dpi,days=n,text=text,text_px=[tw,th],control_px=[w,h],
       calcrect_px=[r.right,r.bottom],font=f.face,missing_glyphs=missing,
       fits=not missing and tw+2*dpi/96<=w and th<=h and r.right<=w and r.bottom<=h))
  finally:f.close()
 return dict(scope='Offscreen metrics only; actual game font/DPI and window layout unobserved',
             runtime_tested=False,production_can_apply=False,measurements=rows,
             all_fit=all(r['fits'] for r in rows))

if __name__=='__main__':
 result=measure();print(json.dumps(result,ensure_ascii=True,indent=2));sys.exit(not result['all_fit'])
