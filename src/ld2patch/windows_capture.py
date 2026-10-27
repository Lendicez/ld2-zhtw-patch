"""Fixture-only single-file capture/promote experiment, NOT atomic replacement.

The source's own DELETE-capable exclusive handle captures that exact file under a
new name. A second exclusive handle promotes staged bytes with replace=False.
The name can be temporarily absent. A competing name is never overwritten.
Only invented constant bytes and a fresh NativeFixture are accepted.
"""
from __future__ import annotations
from contextlib import ExitStack
import hashlib
import json
import re
from .windows_fixture import (NativeFixture,FixtureRefusal,NativeFailure,
    READ,WRITE,DELETE,CREATE_NEW)

ORIGINAL=b'LD2 SYNTHETIC ORIGINAL v1\n'
PATCHED=b'LD2 SYNTHETIC PATCH v1\n'
PHASES=('capture-intent','promote-intent','committed','rollback-intent','rolled-back')
NAMES=frozenset({'target.bin','backup.bin','stage.bin','captured.bin','revoked.bin',
    'save.bin','txn-owner.json','txn-prepared.json'}|
    {f'{phase}-{i}.json' for phase in PHASES for i in range(3)})


class InjectedFault(Exception): pass
class InjectedInterruption(BaseException): pass


def digest(data): return hashlib.sha256(data).hexdigest()
def token(info): return {'volume':info.volume,'file_id':info.file_id}
def encode(value): return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')


def _object_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise FixtureRefusal('duplicate journal key')
        result[key]=value
    return result


def parse_prepared(data,root_token,expected_token,source_hash=None,output_hash=None):
    try: value=json.loads(data,object_pairs_hook=_object_pairs)
    except (ValueError,UnicodeError) as e: raise FixtureRefusal('invalid prepared journal') from e
    if not isinstance(value,dict) or set(value)!={'schema','root','original','backup','stage','source_sha256','output_sha256'}:
        raise FixtureRefusal('prepared schema mismatch')
    if type(value['schema']) is not int or value['schema']!=1:
        raise FixtureRefusal('prepared schema version')
    for key in ('root','original','backup','stage'):
        item=value[key]
        if (not isinstance(item,dict) or set(item)!={'volume','file_id'} or
            type(item['volume']) is not int or not 0<=item['volume']<2**64 or
            not isinstance(item['file_id'],str) or not re.fullmatch('[0-9a-f]{32}',item['file_id'])):
            raise FixtureRefusal('invalid identity token')
    if value['root']!=root_token or value['original']!=expected_token:
        raise FixtureRefusal('journal root/original identity mismatch')
    if any(value[key]['volume']!=root_token['volume'] for key in ('original','backup','stage')):
        raise FixtureRefusal('journal volume mismatch')
    if value['source_sha256']!=(source_hash or digest(ORIGINAL)) or value['output_sha256']!=(output_hash or digest(PATCHED)):
        raise FixtureRefusal('journal recipe mismatch')
    if len({value[key]['file_id'] for key in ('original','backup','stage')})!=3:
        raise FixtureRefusal('journal aliases file identities')
    return value


class CaptureExperiment:
    can_apply=False
    source_bytes=ORIGINAL
    patch_bytes=PATCHED
    def __init__(self,fixture,expected_original,process_guard,hook=None):
        if not isinstance(fixture,NativeFixture) or not NAMES<=fixture.names:
            raise FixtureRefusal('fresh synthetic fixture required')
        self.f=fixture; self.expected=token(expected_original)
        self.process_guard=process_guard; self.hook=hook or (lambda phase:None)
    def guard(self):
        if self.process_guard()!='clear':
            raise FixtureRefusal('process state is not confirmed clear')
    def verify(self,handle,identity,data):
        info=handle.identity()
        if token(info)!=identity or info.links!=1 or info.attributes&0x400:
            raise FixtureRefusal('identity, link or reparse mismatch')
        if info.volume!=self.f.root_handle.identity().volume or handle.read()!=data:
            raise FixtureRefusal('volume/content mismatch')
    def event(self,phase):
        # Bounded exclusive slots; unknown existing artifacts are retained unread.
        for i in range(3):
            name=f'{phase}-{i}.json'
            try: self.f.path(name).lstat()
            except FileNotFoundError:
                self.f.create(name,encode({'phase':phase,'original':self.expected})); return
        raise FixtureRefusal('event slots exhausted; retain diagnostics')
    def create_held(self,stack,name,data):
        h=stack.enter_context(self.f.api.open_handle(self.f.path(name),READ|WRITE|DELETE,0,CREATE_NEW))
        h.write_new(data);return h
    def rollback_held(self,original,patched,backup,evidence):
        self.guard();self.verify(original,evidence['original'],self.source_bytes)
        self.verify(backup,evidence['backup'],self.source_bytes)
        if patched is not None: self.verify(patched,evidence['stage'],self.patch_bytes)
        self.event('rollback-intent')
        if patched is not None:
            # Preserve the known patched inode, never delete/overwrite another file.
            patched.rename(self.f.path('revoked.bin'))
            self.hook('restore-gap')
        self.guard();self.verify(original,evidence['original'],self.source_bytes)
        original.rename(self.f.path('target.bin'))
        self.hook('restored')
        self.event('rolled-back')
        self.hook('restore-committed')
        return {'status':'rolled_back','source_identity':token(original.identity())}
    def install(self):
        self.guard(); captured=False; promoted=False
        with ExitStack() as stack:
            original=stack.enter_context(self.f.open('target.bin',access=READ|DELETE))
            self.verify(original,self.expected,self.source_bytes)
            self.hook('original-held')
            owner=self.create_held(stack,'txn-owner.json',encode({'schema':1,'original':self.expected}))
            backup=self.create_held(stack,'backup.bin',self.source_bytes)
            self.hook('backup-created')
            staged=self.create_held(stack,'stage.bin',self.patch_bytes)
            evidence={'schema':1,'root':token(self.f.root_handle.identity()),'original':self.expected,
                'backup':token(backup.identity()),'stage':token(staged.identity()),
                'source_sha256':digest(self.source_bytes),'output_sha256':digest(self.patch_bytes)}
            self.f.create('txn-prepared.json',encode(evidence))
            try:
                self.hook('prepared')
                self.guard();self.verify(original,evidence['original'],self.source_bytes)
                self.verify(backup,evidence['backup'],self.source_bytes);self.verify(staged,evidence['stage'],self.patch_bytes)
                self.event('capture-intent')
                self.hook('capture-intent')
                original.rename(self.f.path('captured.bin'));captured=True
                self.hook('captured')
                self.guard();self.verify(original,evidence['original'],self.source_bytes)
                self.verify(staged,evidence['stage'],self.patch_bytes)
                self.event('promote-intent')
                self.hook('promote-intent')
                staged.rename(self.f.path('target.bin'));promoted=True
                self.hook('promoted')
                self.verify(staged,evidence['stage'],self.patch_bytes)
                self.verify(backup,evidence['backup'],self.source_bytes)
                self.event('committed')
                self.hook('committed')
                return {'status':'committed_fixture','atomic_visibility':False,'can_apply':False,
                        'original':evidence['original'],'patched':evidence['stage']}
            except InjectedFault:
                if not captured: return {'status':'aborted_unchanged'}
                return self.rollback_held(original,staged if promoted else None,backup,evidence)
            # Native errors, access refusals and unknown process state propagate.
            # No automatic API/permission retry. All stages/backup/intent survive.

    def _optional(self,stack,name):
        try: h=self.f.open(name,access=READ|DELETE)
        except NativeFailure as e:
            if e.code==2: return None
            raise
        return stack.enter_context(h)

    def restore(self):
        """Explicit fixture rollback using persisted evidence; never finish install.

        The independently retained expected original ID is mandatory. This is not
        a production restart loader or trust in arbitrary on-disk instructions.
        """
        self.guard()
        evidence=parse_prepared(self.f.read('txn-prepared.json'),token(self.f.root_handle.identity()),self.expected,digest(self.source_bytes),digest(self.patch_bytes))
        with ExitStack() as stack:
            backup=stack.enter_context(self.f.open('backup.bin'))
            self.verify(backup,evidence['backup'],self.source_bytes)
            target=self._optional(stack,'target.bin')
            captured=self._optional(stack,'captured.bin')
            if target is not None and token(target.identity())==evidence['original']:
                self.verify(target,evidence['original'],self.source_bytes)
                if captured is not None: raise FixtureRefusal('unexpected captured original')
                return {'status':'already_original'}
            if captured is None: raise FixtureRefusal('captured original missing')
            self.verify(captured,evidence['original'],self.source_bytes)
            if target is not None:
                self.verify(target,evidence['stage'],self.patch_bytes)
            return self.rollback_held(captured,target,backup,evidence)
