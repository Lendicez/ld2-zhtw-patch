"""Native Windows primitives for NEW synthetic fixtures, never an installer.

No production TransactionFS implementation is exported. In particular no safe
compare-and-replace for an existing filename is claimed. All writable handles
belong to a freshly created flat directory; callers can only use declared leaf
names. Existing parent directories are pinned against rename while in use.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import ntpath
import os
from pathlib import Path
import re
import tempfile

READ=0x80000000; WRITE=0x40000000; DELETE=0x10000; ATTR=0x80
SHARE_READ=1; SHARE_WRITE=2; SHARE_DELETE=4
CREATE_NEW=1; OPEN_EXISTING=3
DIRECTORY=0x10; REPARSE=0x400
OPEN_REPARSE=0x00200000; BACKUP_SEMANTICS=0x02000000
MAX_BYTES=65536


class FixtureRefusal(ValueError):
    pass


class NativeFailure(OSError):
    def __init__(self, operation, code):
        self.operation=operation; self.code=code
        super().__init__(code, f'{operation}: WinError {code}')


class ReplacementGate(FixtureRefusal):
    pass


class _Info(C.Structure):
    _fields_=[('attributes',W.DWORD),('created',W.FILETIME),
              ('accessed',W.FILETIME),('written',W.FILETIME),
              ('volume',W.DWORD),('size_high',W.DWORD),('size_low',W.DWORD),
              ('links',W.DWORD),('index_high',W.DWORD),('index_low',W.DWORD)]


class _FileId(C.Structure):
    _fields_=[('volume',C.c_ulonglong),('id',C.c_ubyte*16)]


class _Rename(C.Structure):
    # SDK 26100 FILE_RENAME_INFO union is DWORD-sized. No packed alignment.
    _fields_=[('flags',W.DWORD),('root',W.HANDLE),
              ('length',W.DWORD),('name',W.WCHAR*1)]


@dataclass(frozen=True)
class Identity:
    volume: int
    file_id: str
    size: int
    written: int
    attributes: int
    links: int
    final_path: str


def validate_attributes(attributes, links, directory=False):
    if attributes & REPARSE:
        raise FixtureRefusal('reparse point')
    if bool(attributes & DIRECTORY) != directory:
        raise FixtureRefusal('wrong file kind')
    if not directory and links != 1:
        raise FixtureRefusal('hardlink alias')


def validate_leaf(name):
    if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}\.(?:bin|json)',name):
        raise FixtureRefusal('not a synthetic leaf name')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))}:
        raise FixtureRefusal('reserved name')
    return name


def validate_parent(parent):
    text=os.fspath(parent)
    drive,tail=ntpath.splitdrive(text)
    if not re.fullmatch(r'[A-Za-z]:',drive) or not tail.startswith('\\'):
        raise FixtureRefusal('local absolute drive path required')
    parts=tail.split('\\')[1:]
    if not parts or any(not p or p in ('.','..') or p[-1:] in (' ','.') or ':' in p or '/' in p for p in parts):
        raise FixtureRefusal('ambiguous parent path')
    if len(text)>170:
        raise FixtureRefusal('fixture parent too long')
    return Path(text)


class NativeAPI:
    def __init__(self):
        if os.name!='nt':
            raise FixtureRefusal('Windows only')
        self.k=C.WinDLL('kernel32',use_last_error=True)
        def bind(name,args,result):
            fn=getattr(self.k,name); fn.argtypes=args; fn.restype=result; return fn
        self.open=bind('CreateFileW',[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE)
        self.close=bind('CloseHandle',[W.HANDLE],W.BOOL)
        self.info=bind('GetFileInformationByHandle',[W.HANDLE,C.POINTER(_Info)],W.BOOL)
        self.info_ex=bind('GetFileInformationByHandleEx',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL)
        self.final=bind('GetFinalPathNameByHandleW',[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD],W.DWORD)
        self.read=bind('ReadFile',[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL)
        self.write=bind('WriteFile',[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL)
        self.seek=bind('SetFilePointerEx',[W.HANDLE,C.c_longlong,C.POINTER(C.c_longlong),W.DWORD],W.BOOL)
        self.flush=bind('FlushFileBuffers',[W.HANDLE],W.BOOL)
        self.set_info=bind('SetFileInformationByHandle',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL)
        self.volume=bind('GetVolumeInformationByHandleW',[W.HANDLE,W.LPWSTR,W.DWORD,C.POINTER(W.DWORD),C.POINTER(W.DWORD),C.POINTER(W.DWORD),W.LPWSTR,W.DWORD],W.BOOL)
        self.drive_type=bind('GetDriveTypeW',[W.LPCWSTR],W.UINT)
        self.symlink=bind('CreateSymbolicLinkW',[W.LPCWSTR,W.LPCWSTR,W.DWORD],C.c_ubyte)
        self.hardlink=bind('CreateHardLinkW',[W.LPCWSTR,W.LPCWSTR,C.c_void_p],W.BOOL)
        self.is_admin=C.WinDLL('shell32',use_last_error=True).IsUserAnAdmin
        self.is_admin.argtypes=[]; self.is_admin.restype=W.BOOL

    @staticmethod
    def check(result,operation):
        if not result:
            raise NativeFailure(operation,C.get_last_error())
        return result

    def open_handle(self,path,access=READ,share=0,creation=OPEN_EXISTING,directory=False):
        h=self.open(str(path),access,share,None,creation,OPEN_REPARSE|BACKUP_SEMANTICS,None)
        if h==C.c_void_p(-1).value:
            raise NativeFailure('CreateFileW',C.get_last_error())
        result=Handle(self,h)
        try:
            info=result.identity()
            validate_attributes(info.attributes,info.links,directory)
            if ntpath.normcase(info.final_path)!=ntpath.normcase(str(path)):
                raise FixtureRefusal('final path differs from declared path')
        except BaseException:
            result.close(); raise
        return result


class Handle:
    def __init__(self,api,value):
        self.api=api; self.value=value
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def close(self):
        if self.value is not None:
            value=self.value; self.value=None
            self.api.check(self.api.close(value),'CloseHandle')
    def identity(self):
        info=_Info(); file_id=_FileId()
        self.api.check(self.api.info(self.value,C.byref(info)),'GetFileInformationByHandle')
        self.api.check(self.api.info_ex(self.value,18,C.byref(file_id),C.sizeof(file_id)),'GetFileInformationByHandleEx(FileIdInfo)')
        buf=C.create_unicode_buffer(512)
        n=self.api.final(self.value,buf,len(buf),0)
        self.api.check(n,'GetFinalPathNameByHandleW')
        if n>=len(buf) or not buf.value.startswith('\\\\?\\'):
            raise FixtureRefusal('unsupported final path')
        return Identity(file_id.volume,bytes(file_id.id).hex(),(info.size_high<<32)|info.size_low,
                        (info.written.dwHighDateTime<<32)|info.written.dwLowDateTime,
                        info.attributes,info.links,buf.value[4:])
    def read(self):
        before=self.identity()
        if before.size>MAX_BYTES: raise FixtureRefusal('fixture file too large')
        self.api.check(self.api.seek(self.value,0,None,0),'SetFilePointerEx')
        buf=C.create_string_buffer(MAX_BYTES+1); count=W.DWORD()
        self.api.check(self.api.read(self.value,buf,len(buf),C.byref(count),None),'ReadFile')
        if count.value!=before.size or self.identity()!=before:
            raise FixtureRefusal('file changed while reading')
        return buf.raw[:count.value]
    def write_new(self,data):
        if not isinstance(data,bytes) or len(data)>MAX_BYTES or self.identity().size:
            raise FixtureRefusal('bounded empty synthetic file required')
        count=W.DWORD(); buf=C.create_string_buffer(data)
        self.api.check(self.api.write(self.value,buf,len(data),C.byref(count),None),'WriteFile')
        if count.value!=len(data): raise FixtureRefusal('short write; retain incomplete stage')
        self.api.check(self.api.flush(self.value),'FlushFileBuffers')
        if self.read()!=data: raise FixtureRefusal('readback differs')
    def rename(self,destination,replace=False):
        # Private primitive: NativeFixture supplies only its fixed leaf paths.
        encoded=str(destination).encode('utf-16-le')
        # Include an explicit UTF-16 NUL beyond FileNameLength. This also bounds
        # Win32 full-path normalization, even though the length excludes NUL.
        size=max(C.sizeof(_Rename),_Rename.name.offset+len(encoded)+2)
        buf=C.create_string_buffer(size); info=_Rename.from_buffer(buf)
        info.flags=int(replace); info.root=None; info.length=len(encoded)
        C.memmove(C.addressof(buf)+_Rename.name.offset,encoded,len(encoded))
        self.api.check(self.api.set_info(self.value,3,buf,size),'SetFileInformationByHandle(FileRenameInfo)')
        if ntpath.normcase(self.identity().final_path)!=ntpath.normcase(str(destination)):
            raise FixtureRefusal('rename returned an unexpected final path; retain evidence')


class NativeFixture:
    """Fresh flat subtree; no attach-existing mode and no production apply API."""
    can_apply=False
    def __init__(self,parent,names):
        self.parent=validate_parent(parent)
        self.names=frozenset(validate_leaf(x) for x in names)
        self.api=NativeAPI(); self.stack=ExitStack(); self.root=None
        if self.api.is_admin(): raise FixtureRefusal('fixture requires a non-administrator process')
        try:
            # Top-down pinned directory handles, no FILE_SHARE_DELETE.
            for p in reversed([self.parent,*self.parent.parents]):
                self.stack.enter_context(self.api.open_handle(p,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            if self.api.drive_type(self.parent.anchor)!=3:
                raise FixtureRefusal('fixed local drive required')
            last=self.stack.enter_context(self.api.open_handle(self.parent,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            fs=C.create_unicode_buffer(32)
            self.api.check(self.api.volume(last.value,None,0,None,None,None,fs,len(fs)),'GetVolumeInformationByHandleW')
            if fs.value!='NTFS': raise FixtureRefusal('NTFS fixture required')
            self.filesystem=fs.value
            self.root=Path(tempfile.mkdtemp(prefix='ld2-native-',dir=self.parent))
            self.root_handle=self.stack.enter_context(self.api.open_handle(self.root,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
        except BaseException:
            self.stack.close(); raise
    def __enter__(self): return self
    def __exit__(self,*args): self.stack.close()
    def path(self,name):
        validate_leaf(name)
        if name not in self.names or self.root is None:
            raise FixtureRefusal('undeclared fixture file')
        return self.root/name
    def open(self,name,*,access=READ,share=0):
        return self.api.open_handle(self.path(name),access,share)
    def create(self,name,data):
        with self.api.open_handle(self.path(name),READ|WRITE|DELETE,0,CREATE_NEW) as h:
            h.write_new(data); return h.identity()
    def read(self,name):
        with self.open(name) as h: return h.read()
    def verify(self,name,expected_identity,expected_hash):
        with self.open(name) as h:
            now=h.identity()
            if (now.volume,now.file_id)!=(expected_identity.volume,expected_identity.file_id):
                raise FixtureRefusal('file identity changed')
            if hashlib.sha256(h.read()).hexdigest()!=expected_hash:
                raise FixtureRefusal('file content changed')
            return now
    def promote_new(self,stage,destination,expected_hash):
        with self.open(stage,access=READ|WRITE|DELETE) as h:
            before=h.identity()
            if hashlib.sha256(h.read()).hexdigest()!=expected_hash:
                raise FixtureRefusal('stage hash mismatch')
            if before.volume!=self.root_handle.identity().volume:
                raise FixtureRefusal('different volume')
            h.rename(self.path(destination))  # replace=False: cannot overwrite.
            after=h.identity()
            if (before.volume,before.file_id)!=(after.volume,after.file_id):
                raise FixtureRefusal('rename identity changed')
            self.api.check(self.api.flush(h.value),'FlushFileBuffers')
            return after
    def probe_protected_replace(self,target,stage):
        """One diagnostic attempt; intentionally retain protection on failure."""
        with self.open(target) as protected, self.open(stage,access=READ|WRITE|DELETE) as staged:
            before=protected.identity(); data=protected.read()
            try:
                staged.rename(self.path(target),replace=True)
            except NativeFailure as error:
                if error.code not in (5,32): raise
                if protected.identity()!=before or protected.read()!=data:
                    raise FixtureRefusal('target changed during refused replace')
                return {'operation':error.operation,'winerror':error.code,'target_unchanged':True,
                        'protective_handle_retained':True,'retry':False}
            raise FixtureRefusal('unexpected replacement under protected target; stop investigation')
    def apply(self,*args,**kwargs):
        raise ReplacementGate('existing-target compare-and-replace contract is unresolved')
    uninstall=apply
    recover=apply
