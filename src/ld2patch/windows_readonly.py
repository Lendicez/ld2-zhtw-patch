"""Lazy read-only Windows ports. Importing this module performs no host queries.

Injected ports are used in tests. These stat-based observations are preview
evidence, not the handle-pinning/exclusion contract of an installation backend.
"""
from dataclasses import dataclass
import ntpath
import os
from pathlib import Path
import stat

from .discovery import Discovery, EvidenceError, Issue, Metadata, checked_app_id, discover, windows_path
from .planner import ProcessEvidence

REGISTRY_LOCATIONS = (
    ('HKCU', r'Software\Valve\Steam', 'SteamPath', 0),
    ('HKLM', r'Software\Valve\Steam', 'InstallPath', 32),
    ('HKLM', r'Software\Valve\Steam', 'InstallPath', 64),
)
MAX_PROCESSES = 16384


def query_registry(location):
    """Only KEY_QUERY_VALUE, never create/write/expand environment variables."""
    import winreg
    hive, key, name, view = location
    if location not in REGISTRY_LOCATIONS:
        raise EvidenceError('unapproved_registry_location')
    access = winreg.KEY_QUERY_VALUE | {0: 0, 32: winreg.KEY_WOW64_32KEY, 64: winreg.KEY_WOW64_64KEY}[view]
    with winreg.OpenKey({'HKCU': winreg.HKEY_CURRENT_USER, 'HKLM': winreg.HKEY_LOCAL_MACHINE}[hive], key, 0, access) as handle:
        value, kind = winreg.QueryValueEx(handle, name)
    if kind != winreg.REG_SZ:
        raise EvidenceError('registry_value_type_unknown')
    return value


def registry_roots(query=query_registry):
    roots = []
    for location in REGISTRY_LOCATIONS:
        try:
            value = query(location)
        except FileNotFoundError:
            continue
        # PermissionError is deliberately not caught: stop before another hive.
        roots.append(windows_path(value))
    return roots


def detect(app_id, fs, query=query_registry):
    try:
        checked_app_id(app_id)
        return discover(registry_roots(query), app_id, fs)
    except PermissionError:
        return Discovery(app_id, issues=[Issue('registry_access_denied')])
    except OSError:
        return Discovery(app_id, issues=[Issue('registry_read_unavailable')])
    except EvidenceError as exc:
        return Discovery(app_id, issues=[Issue(exc.code, exc.path)])


@dataclass(frozen=True)
class ProcessRow:
    pid: int
    name: str


@dataclass(frozen=True)
class ProcessObservation(ProcessEvidence):
    issue: str = ''


def _kernel():
    if os.name != 'nt':
        raise OSError('Windows process API unavailable')
    import ctypes as c
    from ctypes import wintypes as w
    k = c.WinDLL('kernel32', use_last_error=True)
    k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
    return c, w, k


def snapshot_processes():
    c, w, k = _kernel()
    class Entry(c.Structure):
        _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ProcessID', w.DWORD),
                    ('th32DefaultHeapID', c.c_size_t), ('th32ModuleID', w.DWORD), ('cntThreads', w.DWORD),
                    ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', w.LONG), ('dwFlags', w.DWORD),
                    ('szExeFile', w.WCHAR * 260)]
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        f = getattr(k, name); f.argtypes = [w.HANDLE, c.POINTER(Entry)]; f.restype = w.BOOL
    handle = k.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    try:
        item = Entry(); item.dwSize = c.sizeof(item)
        if not k.Process32FirstW(handle, c.byref(item)):
            raise c.WinError(c.get_last_error())  # Empty snapshot is unknown.
        rows = []
        while True:
            rows.append(ProcessRow(int(item.th32ProcessID), item.szExeFile))
            if len(rows) > MAX_PROCESSES:
                raise EvidenceError('process_budget')
            if not k.Process32NextW(handle, c.byref(item)):
                error = c.get_last_error()
                if error != 18:  # ERROR_NO_MORE_FILES is the sole normal terminator.
                    raise c.WinError(error)
                return rows
    finally:
        k.CloseHandle(handle)


def query_process_path(pid):
    c, w, k = _kernel()
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype = w.BOOL
    handle = k.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only.
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        buffer = c.create_unicode_buffer(32768); size = w.DWORD(len(buffer))
        if not k.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(size)):
            raise c.WinError(c.get_last_error())
        return windows_path(buffer.value)
    finally:
        k.CloseHandle(handle)


def process_state(enumerate_rows=snapshot_processes, query_path=query_process_path):
    """Empty/partial/denied evidence never means no game process exists."""
    paths = []
    try:
        rows = enumerate_rows()
        if not isinstance(rows, (list, tuple)) or not 0 < len(rows) <= MAX_PROCESSES:
            return ProcessEvidence(False, (), True)
        seen = set()
        for row in rows:
            if (not isinstance(row, ProcessRow) or type(row.pid) is not int or not 0 <= row.pid <= 0xffffffff
                    or row.pid in seen or type(row.name) is not str or not row.name or len(row.name) > 260):
                return ProcessEvidence(False, (), True)
            seen.add(row.pid)
            if ntpath.basename(row.name).casefold() == 'ld95.exe':
                path = windows_path(query_path(row.pid))
                if ntpath.basename(path).casefold() != 'ld95.exe':
                    return ProcessEvidence(False, tuple(paths), True)
                paths.append(path)
        return ProcessEvidence(True, tuple(paths), False)
    except PermissionError:
        return ProcessObservation(False, tuple(paths), True, 'process_access_denied')
    except (OSError, EvidenceError, TypeError):
        return ProcessEvidence(False, tuple(paths), True)


def _read(path, limit):
    with Path(path).open('rb') as file:
        return file.read(limit + 1)


def _version(path, read):
    from .patch_engine import file_versions
    from .pe_resources import PE
    try:
        data = read(path, 32 * 1024 * 1024)
        return file_versions(PE(data))[0]
    except ValueError:
        return None


class WindowsReadOnlyFS:
    """Bounded, explicit paths only; no directory scanning and no write methods."""
    def __init__(self, *, lstat=None, read=None, version=None):
        self._stat = lstat if lstat is not None else lambda p: Path(p).lstat()
        self._read = read if read is not None else _read
        self._version = version if version is not None else lambda p: _version(p, self._read)

    def metadata(self, path):
        path = windows_path(path)
        chain = [path]
        while ntpath.dirname(chain[-1]) != chain[-1]:
            chain.append(ntpath.dirname(chain[-1]))
        observed = None
        missing_parent = False
        for current in reversed(chain):
            try:
                item = self._stat(current)
            except FileNotFoundError:
                missing_parent = True
                continue
            if missing_parent:
                raise EvidenceError('ancestor_changed', current)
            if stat.S_ISLNK(item.st_mode) or getattr(item, 'st_file_attributes', 0) & 0x400:
                raise EvidenceError('reparse_or_unverified_ancestors', current)
            if current != path and not stat.S_ISDIR(item.st_mode):
                raise EvidenceError('ancestor_not_directory', current)
            if stat.S_ISREG(item.st_mode) and item.st_nlink != 1:
                raise EvidenceError('hardlink_refused', current)
            if not item.st_ino:
                raise EvidenceError('identity_unknown', current)
            if current == path:
                observed = item
        if observed is None:
            return Metadata('missing', path, True, False)
        is_file = stat.S_ISREG(observed.st_mode)
        if not is_file and not stat.S_ISDIR(observed.st_mode):
            raise EvidenceError('metadata_unknown', path)
        version = self._version(path) if is_file and ntpath.basename(path).casefold() == 'ld95.exe' and observed.st_size <= 32 * 1024 * 1024 else None
        return Metadata('file' if is_file else 'directory', path, True, False,
                        f'{observed.st_dev}:{observed.st_ino}',
                        f'{observed.st_size}:{observed.st_mtime_ns}' if is_file else None,
                        observed.st_size if is_file else None, version)

    def read_bytes(self, path, limit):
        if type(limit) is not int or not 0 <= limit <= 32 * 1024 * 1024:
            raise EvidenceError('read_budget')
        self.metadata(path)
        return self._read(windows_path(path), limit)
