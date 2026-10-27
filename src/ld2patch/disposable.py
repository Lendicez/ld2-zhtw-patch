"""Offline disposable-copy acceptance only; no production installer API.

Fixed leaf names, version-bound contents, retained original, authenticated-by-
caller receipt. Two no-overwrite renames leave a documented missing-name gap.
"""
from contextlib import ExitStack
from dataclasses import dataclass
import ctypes as C
from ctypes import wintypes as W
import hashlib
import re
import struct
from pathlib import Path
from types import SimpleNamespace

from .windows_fixture import (NativeAPI, NativeFixture, Handle, FixtureRefusal,
    NativeFailure, READ, WRITE, DELETE, ATTR, SHARE_READ, SHARE_WRITE, CREATE_NEW,
    validate_parent)
from .windows_capture import CaptureExperiment, NAMES, encode, digest, token, parse_prepared
from .windows_crash_fixture import metadata, stable_metadata
from .patch_engine import strict_json, build_patch

MAX_COPY = 16 * 1024 * 1024
CHUNK = 1024 * 1024
READ_CONTROL = 0x20000
COPY_NAMES = NAMES | {'receipt.json'}
SOURCE_HASH = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
OUTPUT_HASH = 'a15bf7313636a7c19a065b388345f93b46bbce8eb6bf3c9b910a7dc192c3da81'


@dataclass(frozen=True)
class CopyRecipe:
    version: str
    source_hash: str
    source_size: int
    output_hash: str
    output_size: int

    def validate(self):
        if (not isinstance(self.version, str) or not re.fullmatch(r'[a-z0-9.-]{1,64}', self.version)
            or any(not isinstance(x, str) or not re.fullmatch('[0-9a-f]{64}', x)
                   for x in (self.source_hash, self.output_hash))
            or any(type(x) is not int or not 1 <= x <= MAX_COPY
                   for x in (self.source_size, self.output_size))
            or self.source_hash == self.output_hash):
            raise FixtureRefusal('invalid bounded copy recipe')

    def check(self, data, patched=False):
        self.validate()
        expected = (self.output_size, self.output_hash) if patched else (self.source_size, self.source_hash)
        if not isinstance(data, bytes) or (len(data), digest(data)) != expected:
            raise FixtureRefusal('copy content is outside version whitelist')


REVIEWED = CopyRecipe('ld95-1.0.3.16', SOURCE_HASH, 7090176, OUTPUT_HASH, 7102464)


def build_reviewed(source, catalog, versions, recipe):
    REVIEWED.check(source)
    built = build_patch(source, catalog, versions, recipe)
    REVIEWED.check(built.output, True)
    return built


class CopyHandle(Handle):
    def read(self):
        before = self.identity()
        if before.size > MAX_COPY:
            raise FixtureRefusal('copy exceeds 16 MiB budget')
        self.api.check(self.api.seek(self.value, 0, None, 0), 'SetFilePointerEx')
        data = bytearray()
        while len(data) < before.size:
            amount = min(CHUNK, before.size - len(data))
            buf = C.create_string_buffer(amount)
            count = W.DWORD()
            self.api.check(self.api.read(self.value, buf, amount, C.byref(count), None), 'ReadFile')
            if not count.value or count.value > amount:
                raise FixtureRefusal('short/invalid bounded read')
            data.extend(buf.raw[:count.value])
        if self.identity() != before:
            raise FixtureRefusal('copy changed while reading')
        return bytes(data)

    def write_new(self, data):
        if not isinstance(data, bytes) or len(data) > MAX_COPY or self.identity().size:
            raise FixtureRefusal('bounded empty copy required')
        for offset in range(0, len(data), CHUNK):
            part = data[offset:offset + CHUNK]
            buf = C.create_string_buffer(part)
            count = W.DWORD()
            self.api.check(self.api.write(self.value, buf, len(part), C.byref(count), None), 'WriteFile')
            if count.value != len(part):
                raise FixtureRefusal('short write; retain incomplete copy')
        self.api.check(self.api.flush(self.value), 'FlushFileBuffers')
        if self.read() != data:
            raise FixtureRefusal('copy readback mismatch')


class CopyAPI(NativeAPI):
    def __init__(self):
        super().__init__()
        self.security = C.WinDLL('advapi32', use_last_error=True)
        self.get_security = self.security.GetSecurityInfo
        self.get_security.argtypes = [W.HANDLE, C.c_int, W.DWORD] + [C.POINTER(C.c_void_p)] * 5
        self.get_security.restype = W.DWORD
        self.sd_length = self.security.GetSecurityDescriptorLength
        self.sd_length.argtypes = [C.c_void_p]
        self.sd_length.restype = W.DWORD
        self.free = self.k.LocalFree
        self.free.argtypes = [C.c_void_p]
        self.free.restype = C.c_void_p
        self.set_times = self.k.SetFileTime
        self.set_times.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 3
        self.set_times.restype = W.BOOL

    def open_handle(self, path, access=READ, share=0, creation=3, directory=False):
        h = super().open_handle(path, access if directory else access | READ_CONTROL,
                                share, creation, directory)
        result = CopyHandle(self, h.value)
        h.value = None
        return result


def security_hash(h):
    """Read owner/group/DACL only, never SACL or any security-setting API."""
    ptr = C.c_void_p()
    code = h.api.get_security(h.value, 1, 7, None, None, None, None, C.byref(ptr))
    if code:
        raise NativeFailure('GetSecurityInfo(owner/group/DACL)', code)
    try:
        n = h.api.sd_length(ptr)
        if not 20 <= n <= 65536:
            raise FixtureRefusal('unsupported security descriptor size')
        return digest(C.string_at(ptr, n))
    finally:
        h.api.free(ptr)


def parse_streams(raw, expected_size):
    # The supported case is exactly one unnamed DATA stream; never strip ADS.
    if len(raw) < 24:
        raise FixtureRefusal('short stream information')
    next_offset, length, size, allocated = struct.unpack_from('<IIqq', raw)
    if (next_offset != 0 or length != 14 or size != expected_size or allocated < size
        or raw[24:38] != '::$DATA'.encode('utf-16-le')):
        raise FixtureRefusal('additional/unsupported data streams')


def basic(h):
    info = h.identity()
    if info.attributes != 0x20 or info.links != 1:
        raise FixtureRefusal('only ordinary single-link archive files supported')
    buf = C.create_string_buffer(65536)
    h.api.check(h.api.info_ex(h.value, 7, buf, len(buf)),
                'GetFileInformationByHandleEx(FileStreamInfo)')
    parse_streams(buf.raw, info.size)
    return {**stable_metadata(metadata(h)), 'security_sha256': security_hash(h)}


def copy_times(h, value):
    def ft(n):
        return W.FILETIME(n & 0xffffffff, n >> 32)
    created, written = ft(value['created']), ft(value['written'])
    h.api.check(h.api.set_times(h.value, C.byref(created), None, C.byref(written)), 'SetFileTime(copy)')
    h.api.check(h.api.flush(h.value), 'FlushFileBuffers(metadata)')


def _valid_identity(value):
    return (isinstance(value, dict) and set(value) == {'volume', 'file_id'}
            and type(value['volume']) is int and 0 <= value['volume'] < 2**64
            and isinstance(value['file_id'], str)
            and re.fullmatch('[0-9a-f]{32}', value['file_id']))


def validate_receipt(raw, expected_sha, recipe):
    recipe.validate()
    if not isinstance(expected_sha, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha):
        raise FixtureRefusal('independently retained receipt SHA-256 is required')
    if not isinstance(raw, bytes) or len(raw) > 16384 or digest(raw) != expected_sha:
        raise FixtureRefusal('receipt differs from independently retained digest')
    try:
        r = strict_json(raw, 16384)
    except ValueError as e:
        raise FixtureRefusal('invalid receipt JSON') from e
    keys = {'schema', 'version', 'leaf', 'prepared', 'metadata', 'source_size', 'output_size'}
    if (not isinstance(r, dict) or set(r) != keys or type(r['schema']) is not int or r['schema'] != 1
        or r['version'] != recipe.version or r['source_size'] != recipe.source_size
        or r['output_size'] != recipe.output_size or type(r['source_size']) is not int
        or type(r['output_size']) is not int or not isinstance(r['leaf'], str)
        or not re.fullmatch(r'case-[0-9]{2}', r['leaf'])):
        raise FixtureRefusal('receipt schema/version/leaf mismatch')
    e = r['prepared']
    if (not isinstance(e, dict) or not _valid_identity(e.get('root'))
        or not _valid_identity(e.get('original'))):
        raise FixtureRefusal('receipt identity schema')
    parse_prepared(encode(e), e['root'], e['original'], recipe.source_hash, recipe.output_hash)
    if e['root']['file_id'] in {e[x]['file_id'] for x in ('original', 'backup', 'stage')}:
        raise FixtureRefusal('root aliases a file')
    m = r['metadata']
    if (not isinstance(m, dict) or set(m) != {'attributes', 'created', 'written', 'security_sha256'}
        or type(m['attributes']) is not int or m['attributes'] != 0x20
        or any(type(m[k]) is not int or not 0 <= m[k] < 2**64 for k in ('created', 'written'))
        or not isinstance(m['security_sha256'], str)
        or not re.fullmatch('[0-9a-f]{64}', m['security_sha256'])):
        raise FixtureRefusal('receipt metadata schema')
    return r


class DisposableCase(NativeFixture):
    """Only new/registered case-NN roots, never arbitrary game-directory install."""
    def __init__(self, parent, leaf, *, create=False, receipt_sha=None, recipe=REVIEWED):
        self.parent = validate_parent(parent)
        if not isinstance(leaf, str) or not re.fullmatch(r'case-[0-9]{2}', leaf):
            raise FixtureRefusal('case leaf required')
        self.names = COPY_NAMES
        self.api = CopyAPI()
        self.stack = ExitStack()
        self.root = None
        self.recipe = recipe
        recipe.validate()
        if self.api.is_admin():
            raise FixtureRefusal('disposable acceptance must be non-admin')
        try:
            for p in reversed([self.parent, *self.parent.parents]):
                self.stack.enter_context(self.api.open_handle(p, ATTR, SHARE_READ | SHARE_WRITE, directory=True))
            if self.api.drive_type(self.parent.anchor) != 3:
                raise FixtureRefusal('fixed local drive required')
            self.root = self.parent / leaf
            if create:
                self.root.mkdir()  # exclusive new directory; never adopt a populated one
            self.root_handle = self.stack.enter_context(
                self.api.open_handle(self.root, ATTR, SHARE_READ | SHARE_WRITE, directory=True))
            fs = C.create_unicode_buffer(32)
            self.api.check(self.api.volume(self.root_handle.value, None, 0, None, None, None, fs, len(fs)),
                           'GetVolumeInformationByHandleW')
            if fs.value != 'NTFS':
                raise FixtureRefusal('NTFS required')
            if not create:
                self.receipt = validate_receipt(self.read('receipt.json'), receipt_sha, recipe)
                if self.receipt['leaf'] != leaf or self.receipt['prepared']['root'] != token(self.root_handle.identity()):
                    raise FixtureRefusal('receipt root/leaf differs')
                if self.read('txn-prepared.json') != encode(self.receipt['prepared']):
                    raise FixtureRefusal('prepared journal differs from receipt')
                self.receipt_sha = receipt_sha
        except BaseException:
            self.stack.close()
            raise

    def path(self, name):
        # No path comes from a journal. The internal target alias maps only here.
        logical = super().path(name)
        return self.root / 'Ld95.exe' if name == 'target.bin' else logical

    def create_with_metadata(self, name, data, original_metadata):
        with self.api.open_handle(self.path(name), READ | WRITE | DELETE, 0, CREATE_NEW) as h:
            h.write_new(data)
            copy_times(h, original_metadata)
        with self.open(name) as h:
            if h.read() != data:
                raise FixtureRefusal('reopened output changed')
            m = basic(h)
            if m != original_metadata:
                raise FixtureRefusal('metadata/security not inherited identically; no ACL repair')
            return token(h.identity())

    def prepare(self, source, output):
        self.recipe.check(source)
        self.recipe.check(output, True)
        original = self.create('target.bin', source)
        with self.open('target.bin') as h:
            original_metadata = basic(h)
        backup = self.create_with_metadata('backup.bin', source, original_metadata)
        stage = self.create_with_metadata('stage.bin', output, original_metadata)
        e = {'schema': 1, 'root': token(self.root_handle.identity()), 'original': token(original),
             'backup': backup, 'stage': stage, 'source_sha256': self.recipe.source_hash,
             'output_sha256': self.recipe.output_hash}
        self.create('txn-prepared.json', encode(e))
        r = {'schema': 1, 'version': self.recipe.version, 'leaf': self.root.name, 'prepared': e,
             'metadata': original_metadata, 'source_size': len(source), 'output_size': len(output)}
        raw = encode(r)
        self.receipt_sha = digest(raw)
        self.receipt = validate_receipt(raw, self.receipt_sha, self.recipe)
        self.create('receipt.json', raw)
        return self.receipt_sha


class DisposableTransaction(CaptureExperiment):
    def __init__(self, case, source, output, process_guard, hook=None):
        case.recipe.check(source)
        case.recipe.check(output, True)
        self.source_bytes, self.patch_bytes = source, output
        self.receipt = case.receipt
        super().__init__(case, SimpleNamespace(**self.receipt['prepared']['original']), process_guard, hook)

    def verify(self, handle, identity, data):
        # Even if the journal changes between its comparison and the base read,
        # it cannot introduce an identity absent from the anchored receipt.
        e = self.receipt['prepared']
        if identity not in (e['original'], e['backup'], e['stage']):
            raise FixtureRefusal('identity absent from independently anchored receipt')
        expected_hash = (self.f.recipe.output_hash if identity == e['stage']
                         else self.f.recipe.source_hash)
        if digest(data) != expected_hash:
            raise FixtureRefusal('identity/content role differs from receipt')
        super().verify(handle, identity, data)
        if basic(handle) != self.receipt['metadata']:
            raise FixtureRefusal('copy metadata or owner/group/DACL changed')

    def install(self):
        self.guard()
        e = self.receipt['prepared']
        if self.f.read('txn-prepared.json') != encode(e):
            raise FixtureRefusal('prepared journal changed')
        with ExitStack() as stack:
            original = stack.enter_context(self.f.open('target.bin', access=READ | DELETE))
            self.verify(original, e['original'], self.source_bytes)
            backup = stack.enter_context(self.f.open('backup.bin'))
            staged = stack.enter_context(self.f.open('stage.bin', access=READ | DELETE))
            self.verify(original, e['original'], self.source_bytes)
            self.verify(backup, e['backup'], self.source_bytes)
            self.verify(staged, e['stage'], self.patch_bytes)
            self.guard()
            self.event('capture-intent')
            original.rename(self.f.path('captured.bin'))
            self.hook('captured')
            self.guard()
            self.verify(original, e['original'], self.source_bytes)
            self.verify(staged, e['stage'], self.patch_bytes)
            self.event('promote-intent')
            staged.rename(self.f.path('target.bin'))
            self.hook('promoted')
            self.verify(staged, e['stage'], self.patch_bytes)
            self.verify(backup, e['backup'], self.source_bytes)
            self.event('committed')
            self.hook('committed')
            return {'status': 'committed_disposable', 'can_apply': False, 'atomic_visibility': False}

    def restore(self):
        # Compare authenticated evidence again before base recovery reads it.
        if self.f.read('txn-prepared.json') != encode(self.receipt['prepared']):
            raise FixtureRefusal('prepared journal changed')
        return super().restore()

    def snapshot(self):
        results = {}
        with ExitStack() as stack:
            for name in ('target.bin', 'captured.bin', 'backup.bin', 'stage.bin', 'revoked.bin'):
                h = self._optional(stack, name)
                if h is not None:
                    results[name] = {'sha256': digest(h.read()), 'bytes': h.identity().size,
                                     'identity': token(h.identity()), 'metadata': basic(h)}
        return results


def load_payloads(case):
    """Use only receipt-bound file identities and known bytes after a restart."""
    e = case.receipt['prepared']
    with case.open('backup.bin') as h:
        if token(h.identity()) != e['backup'] or basic(h) != case.receipt['metadata']:
            raise FixtureRefusal('backup evidence changed')
        source = h.read()
        case.recipe.check(source)
    output = None
    for name in ('stage.bin', 'target.bin', 'revoked.bin'):
        try:
            with case.open(name) as h:
                if token(h.identity()) != e['stage']:
                    if name == 'target.bin' and token(h.identity()) == e['original']:
                        continue
                    raise FixtureRefusal('unknown output file identity')
                if basic(h) != case.receipt['metadata']:
                    raise FixtureRefusal('output metadata changed')
                if output is not None:
                    raise FixtureRefusal('duplicate stage identity')
                output = h.read()
                case.recipe.check(output, True)
        except NativeFailure as error:
            if error.code != 2:
                raise
    if output is None:
        raise FixtureRefusal('known staged output missing')
    return source, output


def observed_guard(target, observation):
    import ntpath
    if not observation.complete or observation.unresolved_game_processes:
        return 'unknown'
    return ('running' if ntpath.normcase(str(target)) in
            {ntpath.normcase(p) for p in observation.running_game_paths} else 'clear')


def read_source_only(path):
    """Read the exact selected input through pinned parents and a read-only handle."""
    path = Path(path)
    parent = validate_parent(path.parent)
    if path.name != 'Ld95.exe':
        raise FixtureRefusal('only explicit Ld95.exe input supported')
    api = CopyAPI()
    if api.is_admin():
        raise FixtureRefusal('non-admin input read required')
    with ExitStack() as stack:
        for p in reversed([parent, *parent.parents]):
            stack.enter_context(api.open_handle(p, ATTR, SHARE_READ | SHARE_WRITE, directory=True))
        with api.open_handle(path, READ, SHARE_READ) as h:
            before = token(h.identity())
            m = basic(h)
            data = h.read()
            REVIEWED.check(data)
            if token(h.identity()) != before or basic(h) != m:
                raise FixtureRefusal('source changed during read')
            return data, {'sha256': digest(data), 'bytes': len(data), 'identity': before, 'metadata': m}

