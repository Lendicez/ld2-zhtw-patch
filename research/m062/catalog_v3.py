"""m062: expandable catalog builder (research only; production_can_apply=false).

Two encoders share one verified row model:
  * encode_v1: the m056/m060 592-byte row table, hard cap 264 rows. It is
    byte-identical to m060.encode_entries and is the ONLY layout the pinned
    m058 NamePair and m061b ListInsertU objects accept (both refuse >264).
  * encode_v3: a compact, sorted, header-described table (no 264 cap) for a
    future recompiled helper (native-v3/catalog_core_v3.h). Adds two row kinds
    for male adventurer name fragments (runtime first+second join at 0x44e7xx).
No file writer, PE patch, EXE output or execution. Licensed inputs are only
read; nothing derived from them is stored by this module.
"""
import hashlib, json, struct

SOURCE = '6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2'
M051_CATALOG = 'afe520f3826804e49029177fcf4aabfc933d0152d495b55fa269436b21403147'
M051_V1_ENTRIES = '108b067c3f3499a6325b41f6932906b30f3cba1a126d420a379a016bc2c09612'  # 264 rows, 156288 B
V1_ROW, V1_MAX_ROWS, V1_MAX_ID = 592, 264, 446
V3_MAGIC, V3_VERSION, V3_HEADER, V3_ROW = 0x43324C44, 3, 32, 16
V3_MAX_ROWS, V3_MAX_POOL = 8192, 1 << 20
MAX_ANSI, MAX_UNITS = 64, 256
# Row kinds. FULL_ID: item names keyed by stored_id. FULL_ANY: exact string with
# no ID (female adventurer names). PREFIX/SUFFIX: male first/second fragments,
# only ever matched as a two-part join, never as a whole string.
FULL_ID, FULL_ANY, PREFIX, SUFFIX = 1, 2, 3, 4
KIND_NAMES = {FULL_ID: 'full_id', FULL_ANY: 'full_any', PREFIX: 'prefix', SUFFIX: 'suffix'}
ANY_ID = -1
REGIONS = {'western': 0, 'arabic': 1, 'chinese': 2, 'japanese': 3}
# VA layout read from 0x44e737..0x44e896 (pristine). file offset = VA-0x400000.
ADVENTURER_TABLES = {
    'adventurer_male_first':  (0x745EC8, 8, 200, 100, PREFIX),
    'adventurer_male_second': (0x7461E8, 8, 200, 100, SUFFIX),
    'adventurer_female':      (0x7477C8, 13, 150, 150, FULL_ANY),
}
ITEM_TABLES = {'primary': (0x3F0590, 302), 'extended': (0x400460, 144)}
ITEM_CATEGORIES = ('weapon', 'armor', 'tool', 'consumable')
SUFFIX_TABLE, SUFFIX_COUNT = 0x408924, 11


class Refuse(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refuse(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text_ok(text):
    return type(text) is str and text and all(ord(c) >= 32 and ord(c) != 127 for c in text)


def cp932_boundaries(data):
    """Set of byte offsets that start a CP932 character (plus len)."""
    out, i = {0}, 0
    while i < len(data):
        b = data[i]
        i += 2 if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) else 1
        out.add(i)
    need(i == len(data), 'Truncated CP932 lead byte')
    return out


def make_row(kind, ident, ansi, text):
    need(kind in KIND_NAMES, 'Row kind')
    need(type(ident) is int and (ident == ANY_ID if kind != FULL_ID else 0 <= ident < 0x8000), 'Row identifier')
    need(type(ansi) is bytes and 0 < len(ansi) <= MAX_ANSI and b'\0' not in ansi, 'ANSI bounds')
    try:
        decoded = ansi.decode('cp932', errors='strict')
    except UnicodeError:
        raise Refuse('ANSI not strict CP932') from None
    need(all(ord(c) >= 32 and ord(c) != 127 for c in decoded), 'ANSI controls')
    need(text_ok(text), 'Translation text')
    wide = text.encode('utf-16le', errors='strict')
    need(0 < len(wide) // 2 <= MAX_UNITS, 'Translation length')
    return (kind, ident, ansi, text)


def suffixes(original):
    s = [original[SUFFIX_TABLE + i * 5:SUFFIX_TABLE + (i + 1) * 5].split(b'\0', 1)[0] for i in range(SUFFIX_COUNT)]
    need(s == [b''] + [(' +' + str(i)).encode('ascii') for i in range(1, SUFFIX_COUNT)], 'Suffix contract')
    return s


def item_rows(original, item, suffix_list):
    table, slot = item.get('table'), item.get('slot')
    need(table in ITEM_TABLES and type(slot) is int and 0 <= slot < ITEM_TABLES[table][1], 'Catalog source slot')
    need(item.get('category') in ITEM_CATEGORIES, 'Item category')
    at = ITEM_TABLES[table][0] + 216 * slot
    record = original[at:at + 216]
    need(len(record) == 216 and sha(record) == item.get('source_record_sha256'), 'Record hash')
    window = record[4:40]
    need(b'\0' in window, 'Name terminator')
    name = window.split(b'\0', 1)[0]
    need(sha(name) == item.get('source_name_sha256') and struct.unpack_from('<i', record)[0] == item.get('stored_id'), 'Name/ID hash')
    return [make_row(FULL_ID, item['stored_id'], name + s, item['name_zh_tw'] + s.decode('ascii')) for s in suffix_list]


def adventurer_row(original, item):
    table = item.get('table')
    need(table in ADVENTURER_TABLES and item.get('category') == 'adventurer', 'Adventurer table')
    base, width, stride, count, kind = ADVENTURER_TABLES[table]
    region, index = item.get('region'), item.get('index')
    need(region in REGIONS and type(index) is int and 0 <= index < count, 'Adventurer region/index')
    offset = base + width * (REGIONS[region] * stride + index) - 0x400000
    need(item.get('file_offset') == offset, 'Adventurer file offset')
    cell = original[offset:offset + width]
    need(len(cell) == width and b'\0' in cell, 'Adventurer cell terminator')
    name = cell.split(b'\0', 1)[0]
    need(sha(name) == item.get('source_name_sha256'), 'Adventurer name hash')
    need(item.get('exact_match_usable') is (kind == FULL_ANY), 'exact_match_usable contract')
    return make_row(kind, ANY_ID, name, item['name_zh_tw'])


def verified_rows(original, catalogs, categories=('weapon', 'armor', 'tool', 'consumable', 'adventurer')):
    """catalogs: iterable of (catalog_json_bytes, pinned_sha256). Every catalog
    must be hash-pinned by the caller; no allow-unknown switch."""
    need(type(original) is bytes and sha(original) == SOURCE, 'Unsupported source hash')
    suffix_list = suffixes(original)
    rows, stats = [], {}
    for raw, pinned in catalogs:
        need(type(raw) is bytes and type(pinned) is str and sha(raw) == pinned, 'Catalog hash pin')
        cat = json.loads(raw)
        need(cat.get('source_sha256') == SOURCE and cat.get('production_can_apply') is False, 'Catalog boundary')
        items = cat.get('items')
        need(isinstance(items, list) and items, 'Catalog items')
        for item in items:
            c = item.get('category')
            if c not in categories:
                continue
            got = adventurer_row(original, item) if c == 'adventurer' else item_rows(original, item, suffix_list)
            got = got if isinstance(got, list) else [got]
            rows.extend(got)
            stats[c] = stats.get(c, 0) + len(got)
    return dedupe(rows), stats


def dedupe(rows):
    """Identical (kind,id,ansi) rows must carry identical text; drop exact repeats."""
    out, seen = [], {}
    for r in rows:
        key = r[:3]
        if key in seen:
            need(seen[key] == r[3], 'Duplicate/ambiguous key')
            continue
        seen[key] = r[3]
        out.append(r)
    return out


# ---------------------------------------------------------------- v1 (pinned)
def encode_v1(rows):
    """Byte-identical to m060.encode_entries for FULL_ID rows (cap 264)."""
    need(type(rows) in (list, tuple) and 1 <= len(rows) <= V1_MAX_ROWS, 'v1 catalog count (pinned helpers refuse >264)')
    out, seen = bytearray(), set()
    for kind, ident, ansi, text in rows:
        need(kind == FULL_ID and 0 <= ident < V1_MAX_ID, 'v1 accepts only item rows (id<446)')
        wide = text.encode('utf-16le')
        need(len(wide) <= 512, 'v1 text limit')
        need((ident, ansi) not in seen, 'Duplicate/ambiguous key')
        seen.add((ident, ansi))
        out.extend(struct.pack('<iI64sI514s2x', ident, len(ansi), ansi, len(wide) // 2, wide + b'\0\0'))
    need(len(out) == len(rows) * V1_ROW, 'v1 layout')
    return bytes(out)


# ---------------------------------------------------------------- v3 (expandable)
def sort_key(row):
    kind, ident, ansi, text = row
    return (kind, len(ansi), ansi, ident)


def encode_v3(rows):
    need(type(rows) in (list, tuple) and 1 <= len(rows) <= V3_MAX_ROWS, 'v3 catalog count')
    rows = sorted(dedupe([make_row(*r) for r in rows]), key=sort_key)
    pool, ansi_at, wide_at = bytearray(), {}, {}
    def put(blob, cache, align):
        if blob in cache:
            return cache[blob]
        pool.extend(b'\0' * (-len(pool) % align))
        cache[blob] = len(pool)
        pool.extend(blob)
        return cache[blob]
    table = bytearray()
    for kind, ident, ansi, text in rows:
        wide = text.encode('utf-16le')
        a = put(ansi + b'\0', ansi_at, 1)
        w = put(wide + b'\0\0', wide_at, 2)
        table.extend(struct.pack('<HHhBBII', len(ansi), len(wide) // 2, ident, kind, 0, a, w))
    pool.extend(b'\0' * (-len(pool) % 4))
    need(len(pool) <= V3_MAX_POOL, 'v3 pool limit')
    pool_off = V3_HEADER + len(table)
    header = struct.pack('<IHHIIIIII', V3_MAGIC, V3_VERSION, V3_HEADER, len(rows), V3_ROW, V3_HEADER, pool_off, len(pool), 1)
    need(len(header) == V3_HEADER, 'v3 header size')
    return header + bytes(table) + bytes(pool)


def decode_v3(blob):
    need(type(blob) is bytes and len(blob) >= V3_HEADER, 'v3 size')
    magic, ver, hsize, count, rsize, roff, poff, plen, flags = struct.unpack_from('<IHHIIIIII', blob)
    need(magic == V3_MAGIC and ver == V3_VERSION and hsize == V3_HEADER and rsize == V3_ROW and roff == V3_HEADER, 'v3 header')
    need(1 <= count <= V3_MAX_ROWS and poff == roff + count * rsize and poff + plen == len(blob) and plen <= V3_MAX_POOL and flags == 1, 'v3 extents')
    pool, rows = blob[poff:], []
    for i in range(count):
        alen, units, ident, kind, res, a, w = struct.unpack_from('<HHhBBII', blob, roff + i * rsize)
        need(res == 0 and a + alen < plen and pool[a + alen] == 0 and w % 2 == 0 and w + units * 2 + 2 <= plen, 'v3 row extents')
        need(pool[w + units * 2:w + units * 2 + 2] == b'\0\0', 'v3 wide terminator')
        rows.append(make_row(kind, ident, pool[a:a + alen], pool[w:w + units * 2].decode('utf-16le')))
    need(rows == sorted(rows, key=sort_key), 'v3 sort order')
    return rows


# ---------------------------------------------------------------- reference lookup
class Lookup:
    """Python model of native-v3 semantics (the C core must agree)."""
    def __init__(self, rows):
        self.by = {}
        for kind, ident, ansi, text in rows:
            self.by.setdefault((kind, ansi), []).append((ident, text))

    def _unique(self, hits):
        texts = {t for _, t in hits}
        return texts.pop() if len(texts) == 1 else None

    def exact(self, ansi, ident=ANY_ID, allow_any=True):
        every = self.by.get((FULL_ID, ansi), [])
        hits = [h for h in every if ident == ANY_ID or h[0] == ident]
        if hits:
            return self._unique(hits)
        if every or not allow_any:
            return None  # item key exists under another stored_id: keep original
        hits = self.by.get((FULL_ANY, ansi), [])
        return self._unique(hits) if hits else None

    def join(self, ansi):
        try:
            cuts = sorted(cp932_boundaries(ansi) - {0, len(ansi)})
        except Refuse:
            return None
        found = set()
        for k in cuts:
            p, q = self.by.get((PREFIX, ansi[:k])), self.by.get((SUFFIX, ansi[k:]))
            if p and q:
                found.add(p[0][1] + q[0][1])
        return found.pop() if len(found) == 1 else None

    def find(self, ansi, ident=ANY_ID, allow_join=True, allow_any=True):
        """allow_any/allow_join mirror LD2C3_ALLOW_ANY / LD2C3_ALLOW_JOIN."""
        hit = self.exact(ansi, ident, allow_any)
        if hit is not None:
            return hit
        if (FULL_ID, ansi) in self.by or (allow_any and (FULL_ANY, ansi) in self.by):
            return None  # exact key exists but ambiguous: never fall to a join
        return self.join(ansi) if allow_join else None
