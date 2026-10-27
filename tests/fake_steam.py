"""Entirely invented in-memory files. No filesystem or registry operations."""
from dataclasses import replace
import hashlib
import json

from ld2patch.discovery import Metadata, child, path_key, windows_path

APP_ID = '1234567890'  # Synthetic only; not an assertion about the real game.
ORIGINAL = b'SYNTHETIC ORIGINAL CONTENT FOR DRY RUN TESTS'
PATCHED = b'SYNTHETIC PATCHED CONTENT FOR DRY RUN TESTS'
VERSION = '1.2.3.4'


class MemoryFS:
    def __init__(self):
        self.entries = {}
        self.reads = []
        self.probes = []
        self.denied = set()
        self.change_after_read = set()

    def add(self, path, data=None, **overrides):
        path = windows_path(path)
        meta = Metadata('directory' if data is None else 'file', path, True, False,
                        identity='synthetic:' + path_key(path), change_token='v1',
                        size=None if data is None else len(data), file_version=VERSION if data else None)
        self.entries[path_key(path)] = (replace(meta, **overrides), data)
        return path

    def metadata(self, path):
        path = windows_path(path); self.probes.append(path)
        if path_key(path) in self.denied:
            raise PermissionError('synthetic denied')
        return self.entries.get(path_key(path), (Metadata('missing', path, True, False), None))[0]

    def read_bytes(self, path, limit):
        path = windows_path(path); self.reads.append(path)
        if path_key(path) in self.denied:
            raise PermissionError('synthetic denied')
        meta, data = self.entries[path_key(path)]
        if path_key(path) in self.change_after_read:
            self.entries[path_key(path)] = (replace(meta, change_token='v2'), data)
        if data is None:
            raise OSError('synthetic directory')
        return data[:limit + 1]

    def snapshot(self):
        return dict(self.entries)


def vdf_string(value):
    return json.dumps(value, ensure_ascii=False)


def add_library(fs, library, folder='合成 遊戲', *, app_id=APP_ID, body=ORIGINAL):
    manifest = child(library, 'steamapps', f'appmanifest_{APP_ID}.acf')
    text = f'"AppState" {{ "appid" "{app_id}" "installdir" {vdf_string(folder)} }}'
    fs.add(manifest, text.encode('utf-8'))
    install = child(library, 'steamapps', 'common', folder)
    fs.add(install); fs.add(child(install, 'Ld95.exe'), body)
    return install


def example(two=False):
    fs = MemoryFS();root = r'C:\Synthetic Steam';lib = r'D:\合成 程式庫'
    library_doc = '"libraryfolders" { "0" { "path" ' + vdf_string(root) + ' } "1" { "path" ' + vdf_string(lib) + ' } }'
    fs.add(child(root, 'steamapps', 'libraryfolders.vdf'), library_doc.encode('utf-8'))
    install = add_library(fs, lib)
    if two:
        add_library(fs, root, 'Another Synthetic Game')
    config = {'schema_version': 1, 'steam_app_id': APP_ID, 'versions': [{
        'id': 'synthetic-v1', 'filename': 'Ld95.exe', 'file_version': VERSION,
        'source_sha256': hashlib.sha256(ORIGINAL).hexdigest(), 'source_size': len(ORIGINAL),
        'historical_m020_sha256': hashlib.sha256(PATCHED).hexdigest(), 'historical_m020_size': len(PATCHED),
        'release_approved': True,
    }]}
    return fs, root, install, config
