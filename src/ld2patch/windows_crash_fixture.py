"""Attach/recover ONLY registered invented fixtures across worker lifetimes."""
from contextlib import ExitStack
from types import SimpleNamespace
import ctypes as C
import json,re
from .windows_fixture import (NativeFixture,NativeAPI,FixtureRefusal,NativeFailure,
    validate_parent,ATTR,SHARE_READ,SHARE_WRITE,READ,_Info)
from .windows_capture import (CaptureExperiment,NAMES,ORIGINAL,PATCHED,digest,encode,token,_object_pairs)

RECIPE='invented-capture-v1'
REGISTERED_NAMES=NAMES|{'fixture-registration.json'}
INSTALL_PHASES=('original-held','backup-created','prepared','capture-intent','captured','promote-intent','promoted','committed')
RESTORE_PHASES=('restore-gap','restored','restore-committed')


def metadata(handle):
    info=_Info();handle.api.check(handle.api.info(handle.value,C.byref(info)),'GetFileInformationByHandle(metadata)')
    def time(value):return (value.dwHighDateTime<<32)|value.dwLowDateTime
    return {'attributes':info.attributes,'created':time(info.created),'written':time(info.written),
            'accessed':time(info.accessed)}


def stable_metadata(value):
    return {key:value[key] for key in ('attributes','created','written')}


def validate_registration(data):
    try:r=json.loads(data,object_pairs_hook=_object_pairs)
    except (ValueError,UnicodeError) as e:raise FixtureRefusal('invalid registration') from e
    keys={'schema','recipe','leaf','root','original','metadata','source_sha256','output_sha256','nonce'}
    if not isinstance(r,dict) or set(r)!=keys or type(r['schema']) is not int or r['schema']!=1:
        raise FixtureRefusal('registration schema')
    if r['recipe']!=RECIPE or r['source_sha256']!=digest(ORIGINAL) or r['output_sha256']!=digest(PATCHED):
        raise FixtureRefusal('registration version/hash')
    if not isinstance(r['leaf'],str) or not re.fullmatch(r'ld2-native-[a-z0-9_]{8}',r['leaf']):
        raise FixtureRefusal('registration leaf')
    if not isinstance(r['nonce'],str) or not re.fullmatch('[0-9a-f]{32}',r['nonce']):
        raise FixtureRefusal('registration nonce')
    for key in ('root','original'):
        item=r[key]
        if (not isinstance(item,dict) or set(item)!={'volume','file_id'} or
            type(item['volume']) is not int or not 0<=item['volume']<2**64 or
            not isinstance(item['file_id'],str) or not re.fullmatch('[0-9a-f]{32}',item['file_id'])):
            raise FixtureRefusal('registration identity')
    if r['root']['volume']!=r['original']['volume'] or r['root']['file_id']==r['original']['file_id']:
        raise FixtureRefusal('registration volume/alias')
    if not isinstance(r['metadata'],dict) or set(r['metadata'])!={'attributes','created','written','accessed'}:
        raise FixtureRefusal('registration metadata')
    if any(type(x) is not int or not 0<=x<2**64 for x in r['metadata'].values()):
        raise FixtureRefusal('registration metadata value')
    return r


def register_fixture(f,nonce):
    with f.open('target.bin') as h:
        if h.read()!=ORIGINAL:raise FixtureRefusal('not invented original')
        r={'schema':1,'recipe':RECIPE,'leaf':f.root.name,'root':token(f.root_handle.identity()),
           'original':token(h.identity()),'metadata':metadata(h),'source_sha256':digest(ORIGINAL),
           'output_sha256':digest(PATCHED),'nonce':nonce}
    validate_registration(encode(r));f.create('fixture-registration.json',encode(r));return r


class RegisteredFixture(NativeFixture):
    """No arbitrary existing-path attach: independent registration is required.

    The controller passes its retained registration through a private child pipe.
    Disk registration must match exactly; disk journal does not supply paths.
    """
    def __init__(self,parent,registration):
        self.registration=validate_registration(encode(registration))
        self.parent=validate_parent(parent);self.names=REGISTERED_NAMES
        self.api=NativeAPI();self.stack=ExitStack();self.root=None
        if self.api.is_admin():raise FixtureRefusal('non-admin worker required')
        try:
            for p in reversed([self.parent,*self.parent.parents]):
                self.stack.enter_context(self.api.open_handle(p,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            if self.api.drive_type(self.parent.anchor)!=3:raise FixtureRefusal('fixed drive required')
            self.root=self.parent/self.registration['leaf']
            self.root_handle=self.stack.enter_context(self.api.open_handle(self.root,ATTR,SHARE_READ|SHARE_WRITE,directory=True))
            if token(self.root_handle.identity())!=self.registration['root']:
                raise FixtureRefusal('registered root identity mismatch')
            fs=C.create_unicode_buffer(32)
            self.api.check(self.api.volume(self.root_handle.value,None,0,None,None,None,fs,len(fs)),'GetVolumeInformationByHandleW')
            if fs.value!='NTFS':raise FixtureRefusal('NTFS required')
            self.filesystem=fs.value
            if self.read('fixture-registration.json')!=encode(self.registration):
                raise FixtureRefusal('disk registration differs from independent controller evidence')
            if self.read('save.bin')!=b'SYNTHETIC SAVE UNCHANGED':raise FixtureRefusal('fixture sentinel mismatch')
        except BaseException:
            self.stack.close();raise


class PersistentCapture(CaptureExperiment):
    def __init__(self,fixture,process_guard,hook=None):
        self.registration=fixture.registration
        super().__init__(fixture,SimpleNamespace(**self.registration['original']),process_guard,hook)
    def verify(self,handle,identity,data):
        super().verify(handle,identity,data)
        if identity==self.expected and stable_metadata(metadata(handle))!=stable_metadata(self.registration['metadata']):
            raise FixtureRefusal('original basic metadata changed')
    def restore(self):
        self.guard()
        try:self.f.read('txn-prepared.json')
        except NativeFailure as e:
            if e.code!=2:raise
            # Pre-prepare crash: no rename is permitted yet. Only confirm the
            # independent original; retain every uncommitted artifact untouched.
            with self.f.open('target.bin') as h:self.verify(h,self.expected,ORIGINAL)
            if self.f.path('captured.bin').exists():raise FixtureRefusal('capture exists without prepared journal')
            return {'status':'original_intact_uncommitted_artifacts','can_apply':False}
        return super().restore()
