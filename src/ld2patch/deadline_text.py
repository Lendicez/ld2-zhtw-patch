"""Pure, headless deadline text research. No HWND, native calls, or installation."""
from dataclasses import dataclass

INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1
DEADLINE_FORMAT = '%d 天'
DEADLINE_CAPACITY_UNITS = 14  # Includes NUL for the longest signed int32 rendering.
MAX_RESEARCH_UNITS = 4096


def _integer(value, minimum, maximum):
    if type(value) is not int:
        raise TypeError('An explicit integer is required')
    if not minimum <= value <= maximum:
        raise ValueError('Integer outside the accepted range')
    return value


def signed_days_from_word(word):
    """Explicitly interpret an unsigned x86 word as a signed int32; no clamping."""
    word = _integer(word, 0, (1 << 32) - 1)
    return word if word <= INT32_MAX else word - (1 << 32)


def format_deadline(days):
    """Preserve signed decimal semantics, including negative values and zero.

    This mechanically translates the numeric unit. It does not infer sentinel
    meanings, calculate dates, or apply to the separate preformatted-text branch.
    """
    days = _integer(days, INT32_MIN, INT32_MAX)
    return f'{days} 天'


def utf16z_single_line(text, capacity_units):
    """Return independently owned UTF-16LE bytes, with NUL, or reject.

    Capacity is measured in UTF-16 code units including the terminator. Never
    truncates, replaces invalid characters, reuses a game buffer, or exposes a
    pointer. The allocation limit is a research-tool limit, not a game capacity.
    """
    if type(text) is not str:
        raise TypeError('Plain Unicode text required')
    capacity_units = _integer(capacity_units, 1, MAX_RESEARCH_UNITS)
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('NUL and line/control characters are not accepted')
    if len(text) + 1 > capacity_units:
        raise ValueError('UTF-16 capacity exceeded')
    encoded = text.encode('utf-16le', errors='strict')
    if len(encoded) // 2 + 1 > capacity_units:
        raise ValueError('UTF-16 capacity exceeded')
    return encoded + b'\0\0'


@dataclass(frozen=True)
class BoundaryObservation:
    """Injected synthetic facts only; this type never queries or validates a HWND."""
    dialog_resource: int
    control_id: int
    class_name: str
    branch: str
    is_unicode: bool | None = None
    is_alive: bool | None = None
    same_ui_thread: bool | None = None
    plain_win32_control: bool | None = None
    buffer_lifetime_proven: bool | None = None
    layout_fit_proven: bool | None = None


def boundary_blockers(observation):
    """Evaluate a proposed single-control boundary without granting execution."""
    if observation is None:
        return ('live_target_not_observed', 'runtime_integration_not_implemented')
    if type(observation) is not BoundaryObservation:
        raise TypeError('BoundaryObservation required')
    reasons = []
    if type(observation.dialog_resource) is not int or observation.dialog_resource != 292:
        reasons.append('wrong_dialog_resource')
    if type(observation.control_id) is not int or observation.control_id != 1050:
        reasons.append('wrong_control_id')
    if observation.class_name != 'STATIC':
        reasons.append('wrong_control_class')
    if observation.branch != 'numeric_deadline':
        reasons.append('non_numeric_branch')
    for field, code in (
        ('is_unicode', 'unicode_window'),
        ('is_alive', 'target_liveness'),
        ('same_ui_thread', 'same_ui_thread'),
        ('plain_win32_control', 'plain_win32_control'),
        ('buffer_lifetime_proven', 'buffer_lifetime'),
        ('layout_fit_proven', 'layout_fit'),
    ):
        value = getattr(observation, field)
        if value is not None and type(value) is not bool:
            raise TypeError('Observation facts must be bool or None')
        if value is not True:
            reasons.append(code + ('_unknown' if value is None else '_not_proven'))
    reasons.append('runtime_integration_not_implemented')
    return tuple(reasons)


@dataclass(frozen=True)
class DeadlinePreview:
    text: str
    utf16le_z: bytes
    required_units: int
    blockers: tuple[str, ...]

    @property
    def can_apply(self):
        return False


def preview_deadline(days, observation=None, *, capacity_units=DEADLINE_CAPACITY_UNITS):
    """Create data for headless review only; never installs or sends a message."""
    text = format_deadline(days)
    payload = utf16z_single_line(text, capacity_units)
    return DeadlinePreview(text, payload, len(payload) // 2, boundary_blockers(observation))

