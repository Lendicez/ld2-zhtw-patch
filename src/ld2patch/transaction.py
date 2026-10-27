"""Single-file transaction algorithm, deliberately gated to synthetic backends.

No OS adapter or installer entry point. Production Plan.can_apply stays false.
Filesystem atomicity, durability and locks are obligations of a future adapter.
"""
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import re
from typing import Callable, Protocol
import uuid

from .discovery import Discovery, EvidenceError, Issue, Metadata, ReadOnlyFS, checked_app_id, checked_metadata, child, path_key, read_stable, windows_path
from .planner import Plan, ProcessEvidence, _versions, plan_install

LIMIT = 32 * 1024 * 1024
PHASES = {'prepared', 'backup_verified', 'staged', 'replace_pending', 'committed',
          'rollback_pending', 'rolled_back', 'aborted_unchanged', 'recovery_required'}


class TransactionFS(ReadOnlyFS, Protocol):
    synthetic_scope: bool
    def lock(self, install_dir: str) -> AbstractContextManager: ...
    def ensure_directory(self, path: str) -> None: ...
    def create_exclusive(self, path: str, content: bytes) -> None: ...
    def replace_if_unchanged(self, stage: str, target: str, stage_meta: Metadata, target_meta: Metadata) -> None: ...
    def create_journal(self, record: dict) -> None: ...
    def save_journal(self, record: dict) -> None: ...
    def load_journal(self, transaction_id: str) -> dict: ...


@dataclass
class Outcome:
    status: str = 'blocked'
    transaction_id: str | None = None
    phase: str | None = None
    issues: list[str] = field(default_factory=list)
    retained_paths: list[str] = field(default_factory=list)
    production_apply_enabled: bool = False


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _quiet(provider: Callable[[], ProcessEvidence]):
    try:
        e = provider()
    except OSError as exc:
        raise EvidenceError('process_state_unknown') from exc
    if (not isinstance(e, ProcessEvidence) or e.complete is not True
            or e.unresolved_game_processes is not False or not isinstance(e.running_game_paths, tuple)):
        raise EvidenceError('process_state_unknown')
    if e.running_game_paths:
        raise EvidenceError('game_running')
    return e


def _backup(fs, install, version):
    root = child(install, '.ld2-zhtw-backups')
    directory = child(root, version['id'] + '-' + version['source_sha256'])
    for path in (root, directory):
        if checked_metadata(fs, path).kind not in ('missing', 'directory'):
            raise EvidenceError('backup_directory_conflict', path)
    return root, directory, child(directory, 'Ld95.exe')


def _verified(fs, path, expected_hash, expected_size):
    content, meta = read_stable(fs, path, LIMIT)
    if len(content) != expected_size or digest(content) != expected_hash:
        raise EvidenceError('content_hash_or_size_mismatch', path)
    return content, meta


def plan_uninstall(discovery: Discovery, config: dict, fs: ReadOnlyFS, processes: ProcessEvidence,
                   *, selected_install_dir=None) -> Plan:
    plan = plan_install(discovery, config, fs, processes, selected_install_dir=selected_install_dir)
    plan.action = 'uninstall'
    if plan.status == 'blocked':
        return plan
    if plan.status == 'ready_for_review':
        plan.status = 'already_original'
        plan.proposed_changes = []
        plan.expected_output_sha256 = plan.source_sha256
        return plan
    try:
        v = next(x.copy() for x in _versions(config) if x['id'] == plan.version_id)
        if not v['release_approved']:
            raise EvidenceError('release_not_approved')
        _, _, plan.backup = _backup(fs, plan.install_dir, v)
        _verified(fs, plan.backup, v['source_sha256'], v['source_size'])
        _, target_meta = _verified(fs, plan.target, v['historical_m020_sha256'], v['historical_m020_size'])
        plan.backup_action = 'retain_verified_backup'
        plan.expected_output_sha256 = v['source_sha256']
        plan.proposed_changes = [{
            'path': plan.target, 'operation': 'restore_after_verified_backup',
            'before_sha256': v['historical_m020_sha256'], 'after_sha256': v['source_sha256'],
            'before_bytes': v['historical_m020_size'], 'after_bytes': v['source_size'],
            'observed_identity': target_meta.identity, 'observed_change_token': target_meta.change_token,
        }]
        plan.status = 'ready_for_review'
    except EvidenceError as exc:
        plan.status = 'blocked'; plan.issues.append(Issue(exc.code, exc.path))
    return plan


def _gate(fs):
    if getattr(fs, 'synthetic_scope', None) is not True:
        raise EvidenceError('production_transactions_disabled')


def _mark(fs, record, phase):
    # The backend persists a copy before this function reports a phase durable.
    updated = dict(record, phase=phase)
    fs.save_journal(updated)
    record.update(updated)


def _same(meta, saved):
    # A rename changes the path but must preserve the observed file identity and
    # content/change evidence. read_stable separately checks the current path.
    return (isinstance(saved, dict) and set(saved) == set(asdict(meta))
            and all(value == saved[key] for key, value in asdict(meta).items() if key != 'canonical_path'))


def _paths(install, version, txid):
    work = child(install, '.ld2-zhtw-stage', txid)
    return {'target': child(install, 'Ld95.exe'), 'work': work,
            'undo': child(work, 'before.bin'), 'stage': child(work, 'after.bin'),
            'restore': child(work, 'restore.bin'),
            'backup': child(install, '.ld2-zhtw-backups', version['id']+'-'+version['source_sha256'], 'Ld95.exe')}


def _retained(record):
    return [record[k] for k in ('backup', 'work')]


def _restore(fs, record, provider):
    """Rollback only exact observed files owned by this transaction; never guess."""
    _quiet(provider)
    current, meta = read_stable(fs, record['target'], LIMIT)
    before_hash, after_hash = record['before_hash'], record['after_hash']
    if digest(current) == before_hash and len(current) == record['before_size']:
        if _same(meta, record['before_meta']) or _same(meta, record['restore_meta']):
            phase = 'rolled_back' if record['restore_meta'] else 'aborted_unchanged'
            _mark(fs, record, phase)
            return phase
        raise EvidenceError('target_ownership_unknown')
    if (digest(current) != after_hash or len(current) != record['after_size']
            or not _same(meta, record['stage_meta'])):
        raise EvidenceError('target_changed_outside_transaction')
    before, _ = _verified(fs, record['undo'], before_hash, record['before_size'])
    # The immutable original backup must remain valid even for uninstall rollback.
    _verified(fs, record['backup'], record['original_hash'], record['original_size'])
    restore_meta = checked_metadata(fs, record['restore'])
    if restore_meta.kind == 'missing':
        fs.create_exclusive(record['restore'], before)
        _, restore_meta = _verified(fs, record['restore'], before_hash, record['before_size'])
        record['restore_meta'] = asdict(restore_meta)
    else:
        _, restore_meta = _verified(fs, record['restore'], before_hash, record['before_size'])
        if not _same(restore_meta, record['restore_meta']):
            raise EvidenceError('restore_stage_ownership_unknown')
    _mark(fs, record, 'rollback_pending')
    _quiet(provider)
    fs.replace_if_unchanged(record['restore'], record['target'], restore_meta, meta)
    _, restored = _verified(fs, record['target'], before_hash, record['before_size'])
    if not _same(restored, record['restore_meta']):
        raise EvidenceError('restore_identity_mismatch')
    _mark(fs, record, 'rolled_back')
    return 'rolled_back'


def simulate_transaction(preview: Plan, discovery: Discovery, config: dict, fs: TransactionFS,
                         process_provider: Callable[[], ProcessEvidence], *, patch_bytes: bytes | None = None) -> Outcome:
    """Exercise install/uninstall with a synthetic backend; never enable real apply."""
    out = Outcome(); record = None; journal_ready = False
    try:
        _gate(fs)
        preview, discovery, config = deepcopy((preview, discovery, config))
        if not isinstance(preview, Plan) or preview.action not in ('install', 'uninstall'):
            raise EvidenceError('invalid_plan')
        install = windows_path(preview.install_dir)
        with fs.lock(install):
            try:
                processes = _quiet(process_provider)
                make_plan = plan_install if preview.action == 'install' else plan_uninstall
                fresh = make_plan(discovery, config, fs, processes, selected_install_dir=install)
                if preview.to_dict() != fresh.to_dict():
                    raise EvidenceError('plan_changed_or_tampered')
                v = next((x.copy() for x in _versions(config) if x['id'] == fresh.version_id), None)
                if fresh.status == 'blocked' or v is None or not v['release_approved']:
                    raise EvidenceError('plan_not_ready')
                backup_root, backup_dir, backup = _backup(fs, install, v)
                if fresh.status in ('already_patched', 'already_original'):
                    if fresh.status == 'already_patched':
                        _verified(fs, backup, v['source_sha256'], v['source_size'])
                    out.status = fresh.status
                    return out
                if fresh.status != 'ready_for_review' or len(fresh.proposed_changes) != 1:
                    raise EvidenceError('single_file_plan_required')
                change = fresh.proposed_changes[0]
                if change['path'] != child(install, 'Ld95.exe') or fresh.can_apply is not False:
                    raise EvidenceError('invalid_target_set')
                before, before_meta = _verified(fs, fresh.target, change['before_sha256'], change['before_bytes'])
                if preview.action == 'install':
                    after = patch_bytes
                else:
                    after, _ = _verified(fs, backup, v['source_sha256'], v['source_size'])
                if not isinstance(after, bytes) or len(after) != change['after_bytes'] or digest(after) != change['after_sha256']:
                    raise EvidenceError('patch_payload_mismatch')
                txid = uuid.uuid4().hex
                record = dict(schema=1, transaction_id=txid, action=preview.action, install_dir=install,
                              app_id=fresh.app_id, version_id=v['id'], phase='prepared',
                              before_hash=digest(before), after_hash=digest(after), before_size=len(before), after_size=len(after),
                              original_hash=v['source_sha256'], original_size=v['source_size'],
                              before_meta=asdict(before_meta), stage_meta=None, restore_meta=None,
                              **_paths(install, v, txid))
                out.transaction_id = txid; out.retained_paths = _retained(record)
                fs.create_journal(record)
                journal_ready = True
                for directory in (backup_root, backup_dir, child(install, '.ld2-zhtw-stage'), record['work']):
                    fs.ensure_directory(directory)
                if checked_metadata(fs, backup).kind == 'missing':
                    if preview.action != 'install':
                        raise EvidenceError('original_backup_missing')
                    fs.create_exclusive(backup, before)
                _verified(fs, backup, v['source_sha256'], v['source_size'])
                _mark(fs, record, 'backup_verified')
                fs.create_exclusive(record['undo'], before)
                _verified(fs, record['undo'], digest(before), len(before))
                fs.create_exclusive(record['stage'], after)
                _, stage_meta = _verified(fs, record['stage'], digest(after), len(after))
                record['stage_meta'] = asdict(stage_meta)
                _mark(fs, record, 'staged')
                current, current_meta = _verified(fs, fresh.target, digest(before), len(before))
                if current_meta != before_meta:
                    raise EvidenceError('target_changed_before_replace')
                _quiet(process_provider)
                _verified(fs, backup, v['source_sha256'], v['source_size'])
                _mark(fs, record, 'replace_pending')
                fs.replace_if_unchanged(record['stage'], record['target'], stage_meta, current_meta)
                _, applied = _verified(fs, fresh.target, digest(after), len(after))
                if not _same(applied, record['stage_meta']):
                    raise EvidenceError('replacement_identity_mismatch')
                _mark(fs, record, 'committed')
                out.status = 'simulated_committed'; out.phase = record['phase']
                return out
            except (EvidenceError, OSError) as exc:
                out.issues.append(getattr(exc, 'code', type(exc).__name__))
                if record is not None and not journal_ready:
                    # No target/backup/stage writes have begun. Do not overwrite
                    # a conflicting or partially persisted initial journal.
                    out.status = 'recovery_required'
                    out.issues.append('initial_journal_not_confirmed')
                elif record is not None:
                    try:
                        out.status = _restore(fs, record, process_provider)
                    except (EvidenceError, OSError) as restore_exc:
                        out.status = 'recovery_required'
                        out.issues.append(getattr(restore_exc, 'code', type(restore_exc).__name__))
                        try:
                            _mark(fs, record, 'recovery_required')
                        except OSError:
                            out.issues.append('journal_update_failed')
                    out.phase = record['phase']
                return out
    except (EvidenceError, OSError) as exc:
        out.issues.append(getattr(exc, 'code', type(exc).__name__))
        return out


def _validate_record(record, txid, install, config):
    if not isinstance(config, dict):
        raise EvidenceError('unsupported_version_schema')
    if not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] != 1:
        raise EvidenceError('invalid_journal')
    if record.get('transaction_id') != txid or record.get('install_dir') != install or record.get('app_id') != checked_app_id(config.get('steam_app_id')):
        raise EvidenceError('journal_scope_mismatch')
    v = next((x for x in _versions(config) if x['id'] == record.get('version_id')), None)
    if v is None or not v['release_approved'] or record.get('action') not in ('install', 'uninstall') or record.get('phase') not in PHASES:
        raise EvidenceError('invalid_journal_state')
    for key, value in _paths(install, v, txid).items():
        if record.get(key) != value:
            raise EvidenceError('journal_path_mismatch')
    original = (v['source_sha256'], v['source_size'])
    patched = (v['historical_m020_sha256'], v['historical_m020_size'])
    before, after = (original, patched) if record['action'] == 'install' else (patched, original)
    if ((record.get('before_hash'), record.get('before_size')) != before
            or (record.get('after_hash'), record.get('after_size')) != after
            or (record.get('original_hash'), record.get('original_size')) != original):
        raise EvidenceError('journal_hash_mismatch')
    for key in ('before_meta', 'stage_meta', 'restore_meta'):
        if key not in record or (record[key] is not None and not isinstance(record[key], dict)):
            raise EvidenceError('invalid_journal_metadata')


def recover_simulation(transaction_id: str, install_dir: str, config: dict, fs: TransactionFS,
                       process_provider: Callable[[], ProcessEvidence]) -> Outcome:
    """Inspect an interrupted fixture transaction and restore its exact preimage.

    A committed or already reverted journal is observed, not undone again.
    Unknown ownership or conflicting bytes are retained for diagnosis.
    """
    out = Outcome(transaction_id=transaction_id)
    try:
        _gate(fs)
        if not isinstance(transaction_id, str) or not re.fullmatch('[0-9a-f]{32}', transaction_id):
            raise EvidenceError('invalid_transaction_id')
        install = windows_path(install_dir)
        with fs.lock(install):
            record = fs.load_journal(transaction_id)
            _validate_record(record, transaction_id, install, config)
            out.retained_paths = _retained(record)
            _quiet(process_provider)
            if record['phase'] == 'committed':
                _, meta = _verified(fs, record['target'], record['after_hash'], record['after_size'])
                if not _same(meta, record['stage_meta']):
                    raise EvidenceError('target_ownership_unknown')
                _verified(fs, record['backup'], record['original_hash'], record['original_size'])
                out.status = 'already_committed'
            else:
                out.status = _restore(fs, record, process_provider)
            out.phase = record['phase']
    except (EvidenceError, OSError) as exc:
        out.status = 'recovery_required'
        out.issues.append(getattr(exc, 'code', type(exc).__name__))
    return out
