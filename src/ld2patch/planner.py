"""Pure dry-run planning. No writes, subprocesses, UAC or install entry point."""
from dataclasses import asdict, dataclass, field
import hashlib
import re

from .discovery import Discovery, EvidenceError, Issue, ReadOnlyFS, checked_app_id, checked_metadata, child, path_key, read_stable, windows_path


@dataclass(frozen=True)
class ProcessEvidence:
    complete: bool
    running_game_paths: tuple[str, ...] = ()
    unresolved_game_processes: bool = False


@dataclass
class Plan:
    status: str = 'blocked'
    mode: str = 'dry-run'
    can_apply: bool = False
    confirmation_required: bool = True
    install_dir: str | None = None
    app_id: str | None = None
    target: str | None = None
    version_id: str | None = None
    source_sha256: str | None = None
    expected_output_sha256: str | None = None
    backup: str | None = None
    backup_action: str | None = None
    proposed_changes: list[dict] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=lambda: [
        'Preview only; this is not permission or a capability to install.',
        'Steam updates or verification may restore the original executable.',
        'Unsigned releases may be warned about or blocked; do not bypass protection.',
        'Live Windows identity, process and reparse evidence must be rechecked by a future installer.',
    ])

    def to_dict(self):
        return asdict(self)


def _versions(config: dict) -> list[dict]:
    if config.get('schema_version') != 1:
        raise EvidenceError('unsupported_version_schema')
    versions = config.get('versions')
    if not isinstance(versions, list) or not versions:
        raise EvidenceError('version_allowlist_empty')
    ids, hashes = set(), set()
    for v in versions:
        if not isinstance(v, dict) or v.get('filename') != 'Ld95.exe':
            raise EvidenceError('unsafe_version_entry')
        ident = v.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', ident) or ident.endswith('.') or ident in ids:
            raise EvidenceError('unsafe_or_duplicate_version_id')
        ids.add(ident)
        for key in ('source_sha256', 'historical_m020_sha256'):
            value = v.get(key, '')
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value) or value in hashes:
                raise EvidenceError('invalid_or_ambiguous_version_hash')
            hashes.add(value)
        for key in ('source_size', 'historical_m020_size'):
            if type(v.get(key)) is not int or not 0 < v[key] <= 32 * 1024 * 1024:
                raise EvidenceError('invalid_version_size')
        if not isinstance(v.get('file_version'), str) or not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', v['file_version']):
            raise EvidenceError('invalid_file_version')
        if type(v.get('release_approved')) is not bool:
            raise EvidenceError('release_status_unknown')
    return versions


def plan_install(discovery: Discovery, config: dict, fs: ReadOnlyFS, processes: ProcessEvidence,
                 *, selected_install_dir: str | None = None) -> Plan:
    plan = Plan()
    try:
        if not isinstance(config, dict):
            raise EvidenceError('unsupported_version_schema')
        plan.app_id = checked_app_id(config.get('steam_app_id'))
        versions = _versions(config)
        if not isinstance(discovery, Discovery) or discovery.complete is not True:
            raise EvidenceError('discovery_incomplete')
        if discovery.app_id != plan.app_id:
            raise EvidenceError('discovery_appid_mismatch')
        candidates = discovery.candidates
        if not candidates:
            raise EvidenceError('no_candidates')
        unique = {}
        for candidate in candidates:
            if candidate.app_id != plan.app_id:
                raise EvidenceError('candidate_appid_mismatch')
            key = path_key(candidate.install_dir)
            if key in unique and candidate != unique[key]:
                raise EvidenceError('ambiguous_candidate_evidence')
            unique[key] = candidate
        if selected_install_dir is not None:
            key = path_key(selected_install_dir)
            if key not in unique:
                raise EvidenceError('selection_not_a_candidate')
            candidate = unique[key]
        else:
            if len(unique) != 1:
                raise EvidenceError('selection_required')
            candidate = next(iter(unique.values()))
        plan.install_dir = windows_path(candidate.install_dir)
        if checked_metadata(fs, plan.install_dir).kind != 'directory':
            raise EvidenceError('install_directory_missing', plan.install_dir)
        if (not isinstance(processes, ProcessEvidence) or processes.complete is not True
                or processes.unresolved_game_processes is not False or not isinstance(processes.running_game_paths, tuple)):
            raise EvidenceError('process_state_unknown')
        # Conservative: any reported LD95 instance blocks this preview's readiness.
        if processes.running_game_paths:
            for path in processes.running_game_paths:
                windows_path(path)
            raise EvidenceError('game_running')
        plan.target = child(plan.install_dir, 'Ld95.exe')
        data, metadata = read_stable(fs, plan.target, 32 * 1024 * 1024)
        digest = hashlib.sha256(data).hexdigest()
        plan.source_sha256 = digest
        matching = [v for v in versions if digest in (v['source_sha256'], v['historical_m020_sha256'])]
        if not matching:
            raise EvidenceError('unsupported_hash', plan.target)
        v = matching[0]
        original = digest == v['source_sha256']
        expected_size = v['source_size'] if original else v['historical_m020_size']
        if len(data) != expected_size:
            raise EvidenceError('version_size_mismatch', plan.target)
        if metadata.file_version != v['file_version']:
            raise EvidenceError('file_version_unknown_or_mismatch', plan.target)
        plan.version_id = v['id']
        plan.expected_output_sha256 = v['historical_m020_sha256']
        if not original:
            plan.status = 'already_patched'
            plan.warnings.append('No replacement proposed; upgrade/uninstall and backup recovery are not implemented.')
            return plan
        backup_root = child(plan.install_dir, '.ld2-zhtw-backups')
        backup_dir = child(backup_root, v['id'] + '-' + v['source_sha256'])
        for path in (backup_root, backup_dir):
            if checked_metadata(fs, path).kind not in ('missing', 'directory'):
                raise EvidenceError('backup_directory_conflict', path)
        plan.backup = child(backup_dir, 'Ld95.exe')
        backup_metadata = checked_metadata(fs, plan.backup)
        if backup_metadata.kind == 'missing':
            plan.backup_action = 'create_and_verify_before_any_replacement'
        elif backup_metadata.kind == 'file':
            backup_data, _ = read_stable(fs, plan.backup, 32 * 1024 * 1024)
            if len(backup_data) != v['source_size'] or hashlib.sha256(backup_data).hexdigest() != v['source_sha256']:
                raise EvidenceError('backup_content_conflict', plan.backup)
            plan.backup_action = 'reuse_verified_backup_without_overwrite'
        else:
            raise EvidenceError('backup_path_conflict', plan.backup)
        plan.proposed_changes = [{
            'path': plan.target, 'operation': 'replace_after_verified_backup',
            'before_sha256': digest, 'after_sha256': v['historical_m020_sha256'],
            'before_bytes': len(data), 'after_bytes': v['historical_m020_size'],
            'observed_identity': metadata.identity, 'observed_change_token': metadata.change_token,
        }]
        if not v['release_approved']:
            raise EvidenceError('release_not_approved')
        plan.status = 'ready_for_review'
    except EvidenceError as exc:
        plan.status = 'blocked'
        plan.issues.append(Issue(exc.code, exc.path))
    return plan
