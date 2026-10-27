"""Portable translation contracts; native Windows conversion is optional."""
import re, unicodedata, hashlib, sys
PRINTF = re.compile(r'%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:I64|I32|hh|ll|[hlLjztw])?[diuoxXfFeEgGaAcCsSpn%]')
INDEXED = re.compile(r'%[1-9][0-9]*(?:![^!\r\n]+!)?')
def scalar(text):
    if not isinstance(text,str): raise ValueError('Unicode string required')
    text.encode('utf-8','strict')
    if '\0' in text or '\ufffd' in text: raise ValueError('NUL/replacement character')
    return text
def contract(text):
    scalar(text)
    printf=PRINTF.findall(text)
    if any(t.endswith('n') for t in printf): raise ValueError('%n forbidden')
    rest=PRINTF.sub('',text)
    indexed=INDEXED.findall(rest)
    rest=INDEXED.sub('',rest)
    return dict(printf=printf,indexed=indexed,other_percent=rest.count('%'),
                controls=[f'U+{ord(c):04X}' for c in text if unicodedata.category(c) in ('Cc','Cf')],
                mnemonics=re.findall(r'(?<!&)&([^&])',text.replace('&&','')),
                literal_ampersands=text.count('&&'),shortcuts=text.split('\t')[1:])
def validate(text, expected, *, allow_empty=False, max_utf16_units=65535):
    scalar(text)
    if not text and not allow_empty: raise ValueError('Empty translation')
    if len(text.encode('utf-16le'))//2>max_utf16_units: raise ValueError('UTF-16 capacity')
    if contract(text)!=expected: raise ValueError('Format/control/accelerator mismatch')
    encoded=text.encode('cp950','strict')
    if encoded.decode('cp950')!=text: raise ValueError('Nonreversible CP950')
    return len(encoded)
def verify_source(text, expected_sha256):
    if hashlib.sha256(text.encode('utf-16le')).hexdigest()!=expected_sha256:
        raise ValueError('Source text mismatch')
def native_cp950(text):
    if sys.platform!='win32': raise RuntimeError('Windows native check unavailable')
    import ctypes as c
    from ctypes import wintypes as w
    f=c.WinDLL('kernel32',use_last_error=True).WideCharToMultiByte
    f.argtypes=[w.UINT,w.DWORD,w.LPCWSTR,c.c_int,c.c_void_p,c.c_int,c.c_void_p,c.POINTER(w.BOOL)]
    f.restype=c.c_int
    used=w.BOOL();n=f(950,0x400,text,-1,None,0,None,c.byref(used))
    if n<=0 or used.value: raise ValueError('Windows CP950 loss')
    buf=c.create_string_buffer(n);used=w.BOOL()
    if f(950,0x400,text,-1,buf,n,None,c.byref(used))!=n or used.value: raise ValueError('Windows CP950 loss')
    if buf.raw[:-1].decode('cp950')!=text: raise ValueError('Windows CP950 roundtrip')
    return n-1
