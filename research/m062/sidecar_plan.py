"""m062: item_sidecar batching + adventurer name sidecar validator (research only).

item_sidecar.build_item_sidecar (m051, lab tree) accepts 1..30 item rows and
categories weapon/armor/tool/consumable only. Rather than widen that reviewed
validator, larger drafts are split into deterministic <=30-row batches, each
validated unchanged, and adventurer rows get their own validator here.
No game writer; production_can_apply must stay false."""
import json, unicodedata

ITEM_BATCH_LIMIT = 30
ITEM_CATEGORIES = ('weapon', 'armor', 'tool', 'consumable')
ADVENTURER_TABLES = {'adventurer_male_first': (100, False), 'adventurer_male_second': (100, False),
                     'adventurer_female': (150, True)}
REGIONS = ('western', 'arabic', 'chinese', 'japanese')
NAME_STATUS = ('translated', 'identity_preserved')
MAX_NAME_UNITS = 12  # 8/13-byte source cells hold <=6 CP932 chars; leave headroom, layout unverified


def _meta(catalog):
    return {k: v for k, v in catalog.items() if k != 'items'}


def split_items(catalog, limit=ITEM_BATCH_LIMIT):
    """Return [catalog_dict,...] each with <=limit item rows, ordered by (table, slot).
    Adventurer rows are excluded (see validate_adventurers)."""
    if not 1 <= limit <= ITEM_BATCH_LIMIT:
        raise ValueError('Batch limit must stay within item_sidecar bound')
    if catalog.get('production_can_apply') is not False:
        raise ValueError('Research-only boundary')
    items = [i for i in catalog['items'] if i.get('category') in ITEM_CATEGORIES]
    keys = [(i.get('table'), i.get('slot')) for i in items]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate array slot across batches')
    items.sort(key=lambda i: (0 if i['table'] == 'primary' else 1, i['slot']))
    meta = _meta(catalog)
    return [dict(meta, items=items[k:k + limit], batch=dict(index=n, of=(len(items) + limit - 1) // limit))
            for n, k in enumerate(range(0, len(items), limit))]


def cp950_ok(text):
    try:
        text.encode('cp950', errors='strict')
        return True
    except UnicodeError:
        return False


def validate_adventurers(catalog):
    """Validate adventurer rows (schema only; source bytes are verified by
    catalog_v3.adventurer_row against the pinned EXE). Returns counts."""
    if catalog.get('production_can_apply') is not False or catalog.get('release_approved') is not False:
        raise ValueError('Research-only boundary')
    seen, counts = set(), {}
    by_source = {}
    for it in catalog['items']:
        if it.get('category') != 'adventurer':
            continue
        t, r, i = it.get('table'), it.get('region'), it.get('index')
        if t not in ADVENTURER_TABLES or r not in REGIONS:
            raise ValueError('Adventurer table/region')
        size, exact = ADVENTURER_TABLES[t]
        if type(i) is not int or not 0 <= i < size:
            raise ValueError('Adventurer index')
        if (t, r, i) in seen:
            raise ValueError('Duplicate adventurer slot')
        seen.add((t, r, i))
        if it.get('slot') is not None or it.get('stored_id') is not None or it.get('source_record_sha256') is not None:
            raise ValueError('Adventurer rows carry no item identity')
        if it.get('exact_match_usable') is not exact:
            raise ValueError('exact_match_usable must follow table (female exact, male join)')
        if it.get('name_status') not in NAME_STATUS:
            raise ValueError('Name review status')
        name = it.get('name_zh_tw')
        if type(name) is not str or not name or name != unicodedata.normalize('NFC', name):
            raise ValueError('Name text/NFC')
        if any(ord(c) < 32 or ord(c) == 127 for c in name) or len(name.encode('utf-16le')) // 2 > MAX_NAME_UNITS:
            raise ValueError('Name controls/length')
        if it.get('name_cp950_encodable') is not cp950_ok(name):
            raise ValueError('name_cp950_encodable flag mismatch')
        src = it.get('source_name_sha256')
        if type(src) is not str or len(src) != 64:
            raise ValueError('Source name hash')
        if by_source.setdefault(src, name) != name:
            raise ValueError('Same source bytes, different translation')
        counts[t] = counts.get(t, 0) + 1
    return counts


def public_copy(catalog):
    """Strip lab-only source text before any public commit (m051 policy)."""
    drop = ('source_name_ja', 'source_name_cp932_hex')
    return dict(_meta(catalog), items=[{k: v for k, v in i.items() if k not in drop} for i in catalog['items']])
