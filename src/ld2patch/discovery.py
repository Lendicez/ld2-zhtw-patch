"""Read-only Steam discovery through injected ports. No registry/OS adapter."""
from dataclasses import asdict, dataclass, field
import ntpath
import re
from typing import Callable, Iterable, Protocol

from .steam_vdf import app_manifest, libraries, parse

MAX_VDF_BYTES = 2 * 1024 * 1024
MAX_ROOTS = 8
MAX_LIBRARIES = 64
_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3])(?:\.|$)', re.I)


class EvidenceError(ValueError):
    def __init__(self, code: str, path: str = ''):
        self.code, self.path = code, path
        super().__init__(code)


def windows_path(value: str) -> str:
    """Conservative drive-absolute Win32 paths, independent of executor OS."""
    if not isinstance(value, str) or not value or len(value) > 240:
        raise EvidenceError('unsafe_path')
    value = value.replace('/', '\\')
    drive, tail = ntpath.splitdrive(value)
    if not re.fullmatch(r'[A-Za-z]:', drive) or not tail.startswith('\\'):
        raise EvidenceError('unsafe_path', value)
    if any(ord(c) < 32 or c in '<>"|?*' for c in value):
        raise EvidenceError('unsafe_path', value)
    parts = tail.split('\\')[1:]
    if parts and parts[-1] == '':
        parts.pop()
    for part in parts:
        if not part or part in ('.', '..') or part[-1] in ' .' or ':' in part or _RESERVED.match(part):
            raise EvidenceError('unsafe_path', value)
    return drive.upper() + '\\' + '\\'.join(parts)


def path_key(path: str) -> str:
    # This comparison is conservative, not a replacement for Windows file IDs.
    return windows_path(path).casefold()


def child(parent: str, *parts: str) -> str:
    root = windows_path(parent)
    result = windows_path(ntpath.join(root, *parts))
    if not path_key(result).startswith(path_key(root).rstrip('\\') + '\\'):
        raise EvidenceError('path_escape', result)
    return result


def checked_app_id(value: str | None) -> str:
    if value is None or value == '':
        raise EvidenceError('appid_required')
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) > 0xffffffff:
        raise EvidenceError('invalid_appid')
    return value


@dataclass(frozen=True)
class Metadata:
    kind: str  # file, directory, missing; anything else is unknown
    canonical_path: str
    ancestors_verified: bool
    reparse: bool
    identity: str | None = None
    change_token: str | None = None
    size: int | None = None
    file_version: str | None = None


class ReadOnlyFS(Protocol):
    def metadata(self, path: str) -> Metadata: ...
    def read_bytes(self, path: str, limit: int) -> bytes: ...


def checked_metadata(fs: ReadOnlyFS, path: str) -> Metadata:
    path = windows_path(path)
    try:
        meta = fs.metadata(path)
    except PermissionError as exc:
        raise EvidenceError('access_denied', path) from exc
    except OSError as exc:
        raise EvidenceError('metadata_unavailable', path) from exc
    if not isinstance(meta, Metadata) or meta.kind not in ('file', 'directory', 'missing'):
        raise EvidenceError('metadata_unknown', path)
    if meta.ancestors_verified is not True or meta.reparse is not False:
        raise EvidenceError('reparse_or_unverified_ancestors', path)
    if path_key(meta.canonical_path) != path_key(path):
        raise EvidenceError('canonical_path_mismatch', path)
    if meta.kind != 'missing' and not meta.identity:
        raise EvidenceError('identity_unknown', path)
    return meta


def read_stable(fs: ReadOnlyFS, path: str, limit: int) -> tuple[bytes, Metadata]:
    before = checked_metadata(fs, path)
    if before.kind != 'file':
        raise EvidenceError('file_missing' if before.kind == 'missing' else 'not_a_file', path)
    if type(before.size) is not int or not 0 <= before.size <= limit or not before.change_token:
        raise EvidenceError('file_size_or_change_token_unknown', path)
    try:
        data = fs.read_bytes(path, limit)
    except PermissionError as exc:
        raise EvidenceError('access_denied', path) from exc
    except OSError as exc:
        raise EvidenceError('read_unavailable', path) from exc
    if not isinstance(data, bytes) or len(data) != before.size or len(data) > limit:
        raise EvidenceError('file_changed_or_oversized', path)
    if checked_metadata(fs, path) != before:
        raise EvidenceError('file_changed', path)
    return data, before


def read_vdf(fs: ReadOnlyFS, path: str) -> dict:
    data, _ = read_stable(fs, path, MAX_VDF_BYTES)
    try:
        return parse(data.decode('utf-8-sig'))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError('invalid_vdf', path) from exc


@dataclass(frozen=True)
class Issue:
    code: str
    path: str = ''


@dataclass(frozen=True)
class Candidate:
    install_dir: str
    app_id: str
    library: str | None
    manifest_path: str | None
    origin: str = 'steam_manifest'


@dataclass
class Discovery:
    app_id: str | None
    candidates: list[Candidate] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    examined_libraries: list[str] = field(default_factory=list)
    complete: bool = False

    def to_dict(self):
        return asdict(self)


def discover(steam_roots: Iterable[str], app_id: str | None, fs: ReadOnlyFS) -> Discovery:
    """Root values are supplied by a caller, never read from host registry here."""
    result = Discovery(app_id)
    try:
        result.app_id = checked_app_id(app_id)
    except EvidenceError as exc:
        result.issues.append(Issue(exc.code))
        return result
    roots = []
    try:
        for index, raw in enumerate(steam_roots):
            if index >= MAX_ROOTS:
                raise EvidenceError('root_budget')
            root = windows_path(raw)
            if path_key(root) not in {path_key(x) for x in roots}:
                roots.append(root)
    except (EvidenceError, TypeError) as exc:
        result.issues.append(Issue(getattr(exc, 'code', 'invalid_roots'), getattr(exc, 'path', '')))
        return result
    if not roots:
        result.issues.append(Issue('steam_roots_missing'))
        return result
    all_libraries = list(roots)  # Steam's own library is included even for legacy VDF.
    for root in roots:
        path = root
        try:
            path = child(root, 'steamapps', 'libraryfolders.vdf')
            document = read_vdf(fs, path)
            for value in libraries(document):
                library = windows_path(value)
                if path_key(library) not in {path_key(x) for x in all_libraries}:
                    if len(all_libraries) >= MAX_LIBRARIES:
                        raise EvidenceError('library_budget', path)
                    all_libraries.append(library)
        except (EvidenceError, ValueError) as exc:
            result.issues.append(Issue(getattr(exc, 'code', 'invalid_libraryfolders'), getattr(exc, 'path', path)))
            # Unknown library enumeration must not silently select a partial result.
            return result
    result.complete = True
    seen = set()
    for library in all_libraries:
        result.examined_libraries.append(library)
        manifest_path = library
        try:
            manifest_path = child(library, 'steamapps', f'appmanifest_{result.app_id}.acf')
            state = app_manifest(read_vdf(fs, manifest_path))
            if state['appid'] != result.app_id:
                raise EvidenceError('manifest_appid_mismatch', manifest_path)
            install = child(library, 'steamapps', 'common', state['installdir'])
            meta = checked_metadata(fs, install)
            if meta.kind != 'directory':
                raise EvidenceError('install_directory_missing', install)
            if path_key(install) not in seen:
                result.candidates.append(Candidate(install, result.app_id, library, manifest_path))
                seen.add(path_key(install))
        except (EvidenceError, ValueError) as exc:
            code = getattr(exc, 'code', 'invalid_manifest')
            result.issues.append(Issue(code, getattr(exc, 'path', manifest_path)))
            if code not in ('file_missing', 'install_directory_missing'):
                result.complete = False
            if getattr(exc, 'code', '') == 'access_denied':
                break
    return result


def discover_from_registry_values(read_roots: Callable[[], Iterable[str]], app_id: str | None, fs: ReadOnlyFS) -> Discovery:
    """Injected provider; permission failure is reported without a fallback read."""
    try:
        checked_app_id(app_id)
    except EvidenceError as exc:
        return Discovery(app_id, issues=[Issue(exc.code)])
    try:
        roots = read_roots()
        return discover(roots, app_id, fs)
    except PermissionError:
        return Discovery(app_id, issues=[Issue('registry_access_denied')])
    except OSError:
        return Discovery(app_id, issues=[Issue('registry_read_unavailable')])


def manual_candidate(install_dir: str, app_id: str | None, fs: ReadOnlyFS) -> Candidate:
    """Manual selection still requires explicit AppID and the same path checks."""
    app_id = checked_app_id(app_id)
    install_dir = windows_path(install_dir)
    if checked_metadata(fs, install_dir).kind != 'directory':
        raise EvidenceError('install_directory_missing', install_dir)
    return Candidate(install_dir, app_id, None, None, 'manual')
