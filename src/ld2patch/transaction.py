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
MAX_RESTORE_STAGES = 3
LEGACY_PHASES = {'prepared', 'backup_verified', 'staged', 'replace_pending', 'committed',
          'rollback_pending', 'rolled_back', 'aborted_unchanged', 'recovery_required'}
PHASES = LEGACY_PHASES | {'restore_preparing'}


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


def _paths(install, version, txid, restore_attempt=0):
    work = child(install, '.ld2-zhtw-stage', txid)
    return {'target': child(install, 'Ld95.exe'), 'work': work,
            'undo': child(work, 'before.bin'), 'stage': child(work, 'after.bin'),
            'restore': _restore_path(work, restore_attempt),
            'backup': child(install, '.ld2-zhtw-backups', version['id']+'-'+version['source_sha256'], 'Ld95.exe')}


def _retained(record):
    return [record[k] for k in ('backup', 'work')]


def _restore_path(work, attempt):
    if type(attempt) is not int or not 0 <= attempt < MAX_RESTORE_STAGES:
        raise EvidenceError('invalid_restore_attempt')
    return child(work, 'restore.bin' if attempt == 0 else f'restore-{attempt}.bin')


def _prepare_restore(fs, record, before):
    """Retain unowned orphan files; choose at most three exclusive stage slots."""
    while True:
        meta = checked_metadata(fs, record['restore'])
        if meta.kind == 'missing':
            if record['restore_meta'] is not None:
                raise EvidenceError('recorded_restore_stage_missing')
            # Persist the slot before creating it. A crash after creation but
            # before recording identity leaves a recognizable, untrusted orphan.
            _mark(fs, record, 'restore_preparing')
            fs.create_exclusive(record['restore'], before)
            _, meta = _verified(fs, record['restore'], record['before_hash'], record['before_size'])
            record['restore_meta'] = asdict(meta)
            return meta
        if meta.kind != 'file':
            raise EvidenceError('restore_stage_path_conflict')
        if record['restore_meta'] is not None:
            _, meta = _verified(fs, record['restore'], record['before_hash'], record['before_size'])
            if not _same(meta, record['restore_meta']):
                raise EvidenceError('restore_stage_ownership_unknown')
            return meta
        # Do not read, adopt, delete or overwrite an orphan, even if its bytes
        # might equal the preimage. Only verified undo/backup bytes are used.
        attempt = record['restore_attempt'] + 1
        if attempt >= MAX_RESTORE_STAGES:
            raise EvidenceError('restore_stage_retry_budget')
        record['restore_attempt'] = attempt
        record['restore'] = _restore_path(record['work'], attempt)


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
    restore_meta = _prepare_restore(fs, record, before)
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
                record = dict(schema=2, restore_attempt=0, transaction_id=txid, action=preview.action, install_dir=install,
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
    """Validate all JSON fields before any recovery mutation; normalize v1 in memory."""
    if not isinstance(config, dict):
        raise EvidenceError('unsupported_version_schema')
    if not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] not in (1, 2):
        raise EvidenceError('invalid_journal')
    fields = {'schema', 'transaction_id', 'action', 'install_dir', 'app_id', 'version_id', 'phase',
              'before_hash', 'after_hash', 'before_size', 'after_size', 'original_hash', 'original_size',
              'before_meta', 'stage_meta', 'restore_meta', 'target', 'work', 'undo', 'stage', 'restore', 'backup'}
    if record['schema'] == 2:
        fields.add('restore_attempt')
    if set(record) != fields:
        raise EvidenceError('invalid_journal_fields')
    phases = LEGACY_PHASES if record['schema'] == 1 else PHASES
    if type(record['phase']) is not str or record['phase'] not in phases:
        raise EvidenceError('invalid_journal_state')
    if type(record['action']) is not str or record['action'] not in ('install', 'uninstall'):
        raise EvidenceError('invalid_journal_state')
    for key in ('transaction_id', 'install_dir', 'app_id', 'version_id', 'target', 'work', 'undo', 'stage', 'restore', 'backup'):
        if type(record[key]) is not str or not record[key] or len(record[key]) > 240:
            raise EvidenceError('invalid_journal_field_type')
    for key in ('before_hash', 'after_hash', 'original_hash'):
        if type(record[key]) is not str or not re.fullmatch('[0-9a-f]{64}', record[key]):
            raise EvidenceError('invalid_journal_hash_type')
    for key in ('before_size', 'after_size', 'original_size'):
        if type(record[key]) is not int or not 0 < record[key] <= LIMIT:
            raise EvidenceError('invalid_journal_size')
    attempt = 0 if record['schema'] == 1 else record['restore_attempt']
    if type(attempt) is not int or not 0 <= attempt < MAX_RESTORE_STAGES:
        raise EvidenceError('invalid_restore_attempt')
    if record['transaction_id'] != txid or record['install_dir'] != install or record['app_id'] != checked_app_id(config.get('steam_app_id')):
        raise EvidenceError('journal_scope_mismatch')
    v = next((x for x in _versions(config) if x['id'] == record['version_id']), None)
    if v is None or not v['release_approved']:
        raise EvidenceError('invalid_journal_state')
    for key, value in _paths(install, v, txid, attempt).items():
        if record[key] != value:
            raise EvidenceError('journal_path_mismatch')
    original = (v['source_sha256'], v['source_size'])
    patched = (v['historical_m020_sha256'], v['historical_m020_size'])
    before, after = (original, patched) if record['action'] == 'install' else (patched, original)
    if ((record['before_hash'], record['before_size']) != before
            or (record['after_hash'], record['after_size']) != after
            or (record['original_hash'], record['original_size']) != original):
        raise EvidenceError('journal_hash_mismatch')
    metadata_fields = {'kind', 'canonical_path', 'ancestors_verified', 'reparse', 'identity', 'change_token', 'size', 'file_version'}
    for key, path, size in (('before_meta', record['target'], record['before_size']),
                            ('stage_meta', record['stage'], record['after_size']),
                            ('restore_meta', record['restore'], record['before_size'])):
        saved = record[key]
        if saved is None and key != 'before_meta':
            continue
        if not isinstance(saved, dict) or set(saved) != metadata_fields:
            raise EvidenceError('invalid_journal_metadata')
        if (saved['kind'] != 'file' or saved['canonical_path'] != path
                or saved['ancestors_verified'] is not True or saved['reparse'] is not False
                or type(saved['size']) is not int or saved['size'] != size):
            raise EvidenceError('invalid_journal_metadata')
        for name in ('identity', 'change_token'):
            if type(saved[name]) is not str or not 0 < len(saved[name]) <= 4096 or '\0' in saved[name]:
                raise EvidenceError('invalid_journal_metadata')
        if saved['file_version'] != v['file_version'] and not (key != 'before_meta' and saved['file_version'] is None):
            raise EvidenceError('invalid_journal_metadata')
    if record['phase'] in {'staged', 'replace_pending', 'committed', 'restore_preparing', 'rollback_pending', 'rolled_back'} and record['stage_meta'] is None:
        raise EvidenceError('incomplete_journal_metadata')
    if (record['phase'] in {'rollback_pending', 'rolled_back'} and record['restore_meta'] is None
            or record['restore_meta'] is not None and record['stage_meta'] is None):
        raise EvidenceError('incomplete_journal_metadata')
    return dict(deepcopy(record), schema=2, restore_attempt=attempt)


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
            record = _validate_record(record, transaction_id, install, config)
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
