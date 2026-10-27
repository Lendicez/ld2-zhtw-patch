"""Current-user protected recovery anchor, outside the mutable EXE case."""
from contextlib import ExitStack
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import re
import uuid
from .disposable import CopyAPI, basic
from .windows_fixture import ATTR, READ, WRITE, DELETE, SHARE_READ, SHARE_WRITE, CREATE_NEW, validate_parent, FixtureRefusal, NativeFailure
from .windows_capture import token, encode, digest
from .patch_engine import strict_json
from .profiles import profile_for_version

MAX_CARD=65536
PURPOSE='ld2-disposable-candidate-v1'


class Blob(C.Structure):
    _fields_=[('size',W.DWORD),('data',C.c_void_p)]


class CurrentUserProtector:
    """DPAPI, UI_FORBIDDEN only; no machine scope, credentials, prompts or ACLs."""
    def __init__(self):
        self.c=C.WinDLL('crypt32',use_last_error=True)
        self.k=C.WinDLL('kernel32',use_last_error=True)
        for name in ('CryptProtectData','CryptUnprotectData'):
            f=getattr(self.c,name)
            f.argtypes=[C.POINTER(Blob),C.c_void_p,C.POINTER(Blob),C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
            f.restype=W.BOOL
        self.k.LocalFree.argtypes=[C.c_void_p];self.k.LocalFree.restype=C.c_void_p

    def _call(self,name,data):
        if not isinstance(data,bytes) or not 1<=len(data)<=MAX_CARD:
            raise FixtureRefusal('protected recovery data budget')
        buf=C.create_string_buffer(data);source=Blob(len(data),C.addressof(buf));out=Blob()
        if not getattr(self.c,name)(C.byref(source),None,None,None,None,1,C.byref(out)):
            raise NativeFailure(name,C.get_last_error())
        try:
            if not 1<=out.size<=MAX_CARD:raise FixtureRefusal('protected output budget')
            return C.string_at(out.data,out.size)
        finally:self.k.LocalFree(out.data)

    def seal(self,body):
        return self._call('CryptProtectData',encode({'body':body,'sha256':digest(encode(body))}))

    def open(self,blob):
        raw=self._call('CryptUnprotectData',blob)
        value=strict_json(raw,MAX_CARD)
        if (not isinstance(value,dict) or set(value)!={'body','sha256'}
            or digest(encode(value['body']))!=value['sha256']):
            raise FixtureRefusal('protected recovery integrity mismatch')
        return value['body']


def identity(value):
    return (isinstance(value,dict) and set(value)=={'volume','file_id'}
        and type(value['volume']) is int and 0<=value['volume']<2**64
        and isinstance(value['file_id'],str) and re.fullmatch('[0-9a-f]{32}',value['file_id']))


def validate_policy(value):
    if (not isinstance(value,dict) or set(value)!={'schema','purpose','parent','identity'}
        or type(value['schema']) is not int or value['schema']!=1 or value['purpose']!=PURPOSE
        or not identity(value['identity']) or not isinstance(value['parent'],str)):
        raise FixtureRefusal('bundled disposable policy required')
    validate_parent(value['parent'])
    return value


def policy_for_new_parent(parent):
    """Build-time helper. Caller already created the authorized empty parent."""
    api=CopyAPI()
    if api.is_admin():raise FixtureRefusal('non-admin required')
    parent=validate_parent(parent)
    with ExitStack() as stack:
        for p in reversed([parent,*parent.parents]):
            h=stack.enter_context(api.open_handle(p,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
        return {'schema':1,'purpose':PURPOSE,'parent':str(parent),'identity':token(h.identity())}


class TrialSpace:
    def __init__(self,policy,leaf,*,create=False,protector=None):
        self.policy=validate_policy(policy)
        if not isinstance(leaf,str) or not re.fullmatch('ld2-trial-[0-9a-f]{32}',leaf):
            raise FixtureRefusal('owned trial workspace required')
        self.parent=Path(policy['parent']);self.root=self.parent/leaf;self.vault=self.root/'recovery-store'
        self.api=CopyAPI();self.stack=ExitStack()
        if self.api.is_admin():raise FixtureRefusal('candidate refuses elevation')
        self.protector=protector or CurrentUserProtector()
        try:
            for p in reversed([self.parent,*self.parent.parents]):
                h=self.stack.enter_context(self.api.open_handle(p,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            if token(h.identity())!=policy['identity']:
                raise FixtureRefusal('bound test parent identity changed')
            if create:self.root.mkdir()
            self.root_handle=self.stack.enter_context(
                self.api.open_handle(self.root,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            if create:self.vault.mkdir()
            self.vault_handle=self.stack.enter_context(
                self.api.open_handle(self.vault,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
        except BaseException:
            self.stack.close();raise
    def __enter__(self):return self
    def __exit__(self,*args):self.stack.close()

    def _body(self,receipt,case_id,version):
        return {'schema':1,'purpose':PURPOSE,'workspace':token(self.root_handle.identity()),
                'vault':token(self.vault_handle.identity()),'leaf':self.root.name,
                'receipt_sha256':receipt,'case_root':case_id,'version':version}

    def save(self,receipt,case_id,version='ld95-1.0.3.16'):
        profile_for_version(version)
        body=self._body(receipt,case_id,version);blob=self.protector.seal(body)
        # This independent store is created and verified BEFORE any EXE rename.
        with self.api.open_handle(self.vault/'anchor.bin',READ|WRITE|DELETE,0,CREATE_NEW) as h:
            h.write_new(blob)
        if self.load()!=body:raise FixtureRefusal('protected anchor readback mismatch')
        return body

    def load(self):
        with self.api.open_handle(self.vault/'anchor.bin') as h:
            if h.identity().size>MAX_CARD:raise FixtureRefusal('recovery card budget')
            basic(h);body=self.protector.open(h.read())
        fields={'schema','purpose','workspace','vault','leaf','receipt_sha256','case_root','version'}
        if (not isinstance(body,dict) or set(body)!=fields or type(body['schema']) is not int
            or body['schema']!=1 or body['purpose']!=PURPOSE or not isinstance(body['version'],str)
            or body['leaf']!=self.root.name or not identity(body['case_root'])
            or not isinstance(body['receipt_sha256'],str)
            or not re.fullmatch('[0-9a-f]{64}',body['receipt_sha256'])
            or body['workspace']!=token(self.root_handle.identity())
            or body['vault']!=token(self.vault_handle.identity())):
            raise FixtureRefusal('protected recovery binding mismatch')
        profile_for_version(body['version'])
        return body


def new_leaf():
    return 'ld2-trial-'+uuid.uuid4().hex

