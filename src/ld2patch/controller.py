"""Headless Traditional Chinese preview controller. Install capability is absent."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib

from .discovery import Discovery, EvidenceError, Issue, child, manual_candidate, path_key, read_stable
from .planner import ProcessEvidence, _versions
from .windows_readonly import detect


@dataclass(frozen=True)
class Preview:
    install_dir: str
    origin: str
    source_sha256: str
    file_version: str | None
    source_bytes: int
    known_original: bool
    already_patched: bool
    can_generate: bool
    can_install: bool = False


class Controller:
    def __init__(self, config, fs, read_registry, processes, generate):
        self.config = deepcopy(config)
        self.fs, self.registry, self.processes, self.writer = fs, read_registry, processes, generate
        self.discovery = Discovery(config.get('steam_app_id'))
        self.preview = None
        self.issue = ''
        self.stopped = False

    def _require_open(self):
        if self.stopped:
            raise EvidenceError('session_stopped_after_access_denial')

    def _error(self, exc):
        self.preview = None
        self.issue = getattr(exc, 'code', type(exc).__name__)
        if isinstance(exc, PermissionError) or 'denied' in self.issue:
            self.stopped = True

    def discover(self):
        self._require_open()
        self.preview = None
        self.discovery = detect(self.config.get('steam_app_id'), self.fs, self.registry)
        self.issue = ', '.join(x.code for x in self.discovery.issues)
        if any('denied' in x.code for x in self.discovery.issues):
            self.stopped = True
        return self.view()

    def manual(self, folder):
        self._require_open()
        self.preview = None
        self.discovery = Discovery(self.config.get('steam_app_id'))
        try:
            candidate = manual_candidate(folder, self.config.get('steam_app_id'), self.fs)
            self.discovery = Discovery(candidate.app_id, [candidate], complete=True)
            self.issue = ''
        except (OSError, EvidenceError) as exc:
            self._error(exc)
        return self.view()

    def inspect(self, folder):
        self._require_open()
        self.preview = None
        try:
            if not self.discovery.complete:
                raise EvidenceError('discovery_incomplete')
            candidates = [c for c in self.discovery.candidates if path_key(c.install_dir) == path_key(folder)]
            if len(candidates) != 1:
                raise EvidenceError('selection_required')
            candidate = candidates[0]
            evidence = self.processes()
            if getattr(evidence, 'issue', '') == 'process_access_denied':
                raise EvidenceError('process_access_denied')
            if (not isinstance(evidence, ProcessEvidence) or evidence.complete is not True
                    or evidence.unresolved_game_processes is not False or not isinstance(evidence.running_game_paths, tuple)):
                raise EvidenceError('process_state_unknown')
            if evidence.running_game_paths:
                raise EvidenceError('game_running')
            data, meta = read_stable(self.fs, child(candidate.install_dir, 'Ld95.exe'), 32 * 1024 * 1024)
            digest = hashlib.sha256(data).hexdigest()
            versions = _versions(self.config)
            original = any(digest == v['source_sha256'] and len(data) == v['source_size'] and meta.file_version == v['file_version'] for v in versions)
            patched = any(digest == v['historical_m020_sha256'] and len(data) == v['historical_m020_size'] and meta.file_version == v['file_version'] for v in versions)
            self.preview = Preview(candidate.install_dir, candidate.origin, digest, meta.file_version,
                                   len(data), original, patched, original)
            self.issue = '' if original else 'already_patched' if patched else 'unsupported_hash_or_version'
        except (OSError, EvidenceError) as exc:
            self._error(exc)
        return self.view()

    def generate(self, output, metadata, *, confirmed=False):
        self._require_open()
        if confirmed is not True or self.preview is None or not self.preview.can_generate:
            raise EvidenceError('explicit_generation_confirmation_required')
        previous = self.preview
        self.inspect(previous.install_dir)
        if self.preview != previous or not self.preview.can_generate:
            raise EvidenceError('preview_changed')
        try:
            return self.writer(child(previous.install_dir, 'Ld95.exe'), output, metadata)
        except (OSError, ValueError) as exc:
            self._error(exc)
            raise

    def view(self):
        return {'title': 'LD2 繁中離線產生器', 'app_id': self.config.get('steam_app_id'),
                'candidates': [asdict(c) for c in self.discovery.candidates],
                'discovery_complete': self.discovery.complete, 'preview': asdict(self.preview) if self.preview else None,
                'issue': self.issue, 'stopped': self.stopped, 'install_enabled': False,
                'generate_enabled': bool(self.preview and self.preview.can_generate and not self.stopped),
                'notice': '只會產生新檔案。正式安裝尚未開放；原版、存檔與其他模組應保留。',
                'risk': '目前為有限範圍的資源翻譯；未簽章程式可能被 Windows 阻擋。Steam 更新可能還原修改。'}
