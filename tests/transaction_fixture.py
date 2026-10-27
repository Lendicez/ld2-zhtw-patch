"""Synthetic transaction adapter. Every byte lives in a TemporaryDirectory.

Virtual Windows paths are mapped below that owned root, never used as OS paths.
This adapter is a test double, not a production Windows filesystem adapter.
"""
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

from ld2patch.discovery import EvidenceError, Metadata, path_key, windows_path
from fake_steam import VERSION, example


class SimulatedCrash(BaseException):
    pass


class TempFS:
    synthetic_scope = True

    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ld2-synthetic-')
        self.root = Path(self.temp.name).resolve()
        self.data = self.root/'files'; self.data.mkdir()
        self.journals = self.root/'journals'; self.journals.mkdir()
        self.mutex = threading.Lock()
        self.calls = []
        self.hooks = {}
        self.unsafe = set()
        self.last_transaction_id = None

    def close(self):
        self.temp.cleanup()

    def hook(self, event):
        self.calls.append(event)
        callback = self.hooks.pop(event, None)
        if callback:
            callback()

    def actual(self, path):
        p = windows_path(path)
        components = [p[0].upper()] + p[3:].split('\\')
        components = [x for x in components if x]
        target = self.data.joinpath(*components)
        # Case aliases are not emulated; all core tests use canonical spelling.
        current = self.data
        for component in components:
            current = current/component
            if current.exists() or current.is_symlink():
                info = current.lstat()
                attrs = getattr(info, 'st_file_attributes', 0)
                if stat.S_ISLNK(info.st_mode) or attrs & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
                    raise EvidenceError('fixture_link_rejected', path)
                if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                    raise EvidenceError('fixture_hardlink_rejected', path)
        if target.resolve().is_relative_to(self.data) is not True:
            raise EvidenceError('fixture_scope_escape', path)
        if any(path_key(path).startswith(key) for key in self.unsafe):
            raise EvidenceError('fixture_reparse_rejected', path)
        return target

    def seed(self, virtual, data=None):
        p=self.actual(virtual)
        if data is None:
            p.mkdir(parents=True,exist_ok=True)
        else:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

    def metadata(self, path):
        p=self.actual(path)
        if not p.exists():
            return Metadata('missing',windows_path(path),True,False)
        s=p.stat()
        kind='directory' if p.is_dir() else 'file'
        return Metadata(kind,windows_path(path),True,False,identity=f'{s.st_dev}:{s.st_ino}',
                        change_token=f'{s.st_size}:{s.st_mtime_ns}' if kind=='file' else None,
                        size=s.st_size if kind=='file' else None,
                        file_version=VERSION if kind=='file' else None)

    def read_bytes(self, path, limit):
        with self.actual(path).open('rb') as f:
            return f.read(limit+1)

    @contextmanager
    def lock(self, install):
        self.actual(install)
        if not self.mutex.acquire(blocking=False):
            raise EvidenceError('fixture_transaction_locked')
        try:
            yield
        finally:
            self.mutex.release()

    def ensure_directory(self, path):
        p=self.actual(path);p.mkdir(exist_ok=True)

    def create_exclusive(self, path, content):
        p=self.actual(path)
        label='backup' if '.ld2-zhtw-backups' in path else p.name
        self.hook('create:'+label)
        with p.open('xb') as f:
            middle=max(1,len(content)//2)
            f.write(content[:middle]);f.flush()
            self.hook('partial:'+label)
            f.write(content[middle:]);f.flush();os.fsync(f.fileno())
        self.hook('created:'+label)

    def replace_if_unchanged(self, stage, target, stage_meta, target_meta):
        label='restore' if stage.rsplit('\\', 1)[-1] in {'restore.bin', 'restore-1.bin', 'restore-2.bin'} else 'apply'
        self.hook('before_replace:'+label)
        if self.metadata(stage)!=stage_meta or self.metadata(target)!=target_meta:
            raise EvidenceError('compare_and_replace_conflict')
        source,dest=self.actual(stage),self.actual(target)
        if source.stat().st_dev!=dest.stat().st_dev:
            raise EvidenceError('fixture_cross_volume')
        # This real rename tests only this temporary volume, not production NTFS
        # guarantees, external writer exclusion, directory fsync or crash safety.
        os.replace(source,dest)
        self.hook('after_replace:'+label)

    def journal_path(self, transaction_id):
        if not re.fullmatch('[0-9a-f]{32}',transaction_id):
            raise EvidenceError('invalid_transaction_id')
        info=self.journals.lstat()
        if self.journals.is_symlink() or getattr(info,'st_file_attributes',0)&0x400 or self.journals.resolve()!=self.root/'journals':
            raise EvidenceError('fixture_journal_directory_rejected')
        p=self.journals/(transaction_id+'.json')
        if p.is_symlink() or (p.exists() and p.stat().st_nlink!=1):
            raise EvidenceError('fixture_journal_link_rejected')
        return p

    def create_journal(self, record):
        self.hook('journal:prepared')
        p=self.journal_path(record['transaction_id'])
        with p.open('x',encoding='utf-8',newline='\n') as f:
            json.dump(record,f,ensure_ascii=True,sort_keys=True)
            f.flush();os.fsync(f.fileno())
        self.last_transaction_id=record['transaction_id']
        self.hook('journal_saved:prepared')

    def save_journal(self, record):
        self.hook('journal:'+record['phase'])
        p=self.journal_path(record['transaction_id'])
        tmp=p.with_suffix('.new')
        with tmp.open('x',encoding='utf-8',newline='\n') as f:
            json.dump(record,f,ensure_ascii=True,sort_keys=True)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
        self.last_transaction_id=record['transaction_id']
        self.hook('journal_saved:'+record['phase'])

    def load_journal(self, transaction_id):
        with self.journal_path(transaction_id).open(encoding='utf-8') as f:
            text=f.read(65537)
        if len(text)>65536:
            raise EvidenceError('fixture_journal_too_large')
        try:
            return json.loads(text)
        except ValueError as exc:
            raise EvidenceError('invalid_journal') from exc


def temporary_example():
    memory,root,install,config=example()
    fs=TempFS()
    for metadata,body in memory.entries.values():
        fs.seed(metadata.canonical_path,body)
    return fs,root,install,config
