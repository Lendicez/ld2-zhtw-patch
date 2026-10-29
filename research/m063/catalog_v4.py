"""m063c: catalog v4 = v3 + region-tagged male fragments + NAME_ONLY lookup (research only).

production_can_apply=false. Linux model only: no file writer, PE patch, EXE output or
execution. Licensed inputs are only read; nothing derived from them is stored here.

Why (research/m062/draft3/REVIEW.zh-TW.md, "draft4 後剩下的阻礙" 2 and 3):
  * Kris: an item name (extended 28) has the same CP932 bytes as a female adventurer name.
    v3 with id=-1 consults full_id rows first, so a name site would show the item text.
    -> LD2C4_NAME_ONLY: name-only call sites never consult full_id rows.
  * 2 male joins (arabic 69+31, 69+95) equal an item name and are taken by that full_id
    row -> fixed by the same NAME_ONLY flag.
  * 5 male joins have a second split whose prefix and suffix come from different regions,
    so v3 sees two different joins and falls back to the original text.
    -> prefix/suffix rows carry region+1 in the former reserved byte; a join needs both
       halves from the same region (the game builds a name from one region's tables).

Format change (fail closed against pinned v3 helpers):
  header version 4 (v3 helpers refuse it; v4 helpers refuse version 3);
  row byte 7 = region tag: 0 for full_id/full_any, 1..4 for prefix/suffix.
  rows sorted by (kind, ansi_len, ansi bytes, region, id).
"""
import hashlib, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm062'))
import catalog_v3 as c3  # noqa: E402

Refuse, need, sha = c3.Refuse, c3.need, c3.sha
FULL_ID, FULL_ANY, PREFIX, SUFFIX, ANY_ID = c3.FULL_ID, c3.FULL_ANY, c3.PREFIX, c3.SUFFIX, c3.ANY_ID
V4_MAGIC, V4_VERSION, V4_HEADER, V4_ROW = c3.V3_MAGIC, 4, 32, 16
V4_MAX_ROWS, V4_MAX_POOL = c3.V3_MAX_ROWS, c3.V3_MAX_POOL
REGION_TAGS = {name: idx + 1 for name, idx in c3.REGIONS.items()}  # western 1 .. japanese 4
ALLOW_ANY, ALLOW_JOIN, NAME_ONLY = 1, 2, 4
FLAG_MASK = ALLOW_ANY | ALLOW_JOIN | NAME_ONLY
# Call-site classes (enable plan input; see DESIGN-M063C). Values are the lookup flags.
SITE_FLAGS = {
    'item_by_id': 0,                                  # NamePair: stored_id known
    'item_list': ALLOW_ANY | ALLOW_JOIN,              # shop lists: v3 behaviour unchanged
    'unclassified_list': ALLOW_ANY | ALLOW_JOIN,      # commission lists: keep v3 behaviour
    'name': ALLOW_ANY | ALLOW_JOIN | NAME_ONLY,       # tavern, 10 m063 list sites, NameTextOut
}


def make_row(kind, ident, ansi, text, region=0):
    kind, ident, ansi, text = c3.make_row(kind, ident, ansi, text)
    if kind in (PREFIX, SUFFIX):
        need(type(region) is int and 1 <= region <= 4, 'Fragment region tag')
    else:
        need(region == 0, 'Full rows carry no region tag')
    return (kind, ident, ansi, text, region)


def adventurer_row(original, item):
    kind, ident, ansi, text = c3.adventurer_row(original, item)
    return make_row(kind, ident, ansi, text, REGION_TAGS[item['region']] if kind in (PREFIX, SUFFIX) else 0)


def verified_rows(original, catalogs, categories=('weapon', 'armor', 'tool', 'consumable', 'adventurer')):
    """Same inputs and checks as catalog_v3.verified_rows; fragments keep their region."""
    import json
    need(type(original) is bytes and sha(original) == c3.SOURCE, 'Unsupported source hash')
    suffix_list = c3.suffixes(original)
    rows, stats = [], {}
    for raw, pinned in catalogs:
        need(type(raw) is bytes and type(pinned) is str and sha(raw) == pinned, 'Catalog hash pin')
        cat = json.loads(raw)
        need(cat.get('source_sha256') == c3.SOURCE and cat.get('production_can_apply') is False, 'Catalog boundary')
        items = cat.get('items')
        need(isinstance(items, list) and items, 'Catalog items')
        for item in items:
            c = item.get('category')
            if c not in categories:
                continue
            if c == 'adventurer':
                got = [adventurer_row(original, item)]
            else:
                got = [make_row(*r) for r in c3.item_rows(original, item, suffix_list)]
            rows.extend(got)
            stats[c] = stats.get(c, 0) + len(got)
    return dedupe(rows), stats


def dedupe(rows):
    out, seen = [], {}
    for r in rows:
        key = (r[0], r[1], r[2], r[4])
        if key in seen:
            need(seen[key] == r[3], 'Duplicate/ambiguous key')
            continue
        seen[key] = r[3]
        out.append(r)
    return out


def sort_key(row):
    kind, ident, ansi, text, region = row
    return (kind, len(ansi), ansi, region, ident)


def encode_v4(rows):
    need(type(rows) in (list, tuple) and 1 <= len(rows) <= V4_MAX_ROWS, 'v4 catalog count')
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
    for kind, ident, ansi, text, region in rows:
        wide = text.encode('utf-16le')
        a = put(ansi + b'\0', ansi_at, 1)
        w = put(wide + b'\0\0', wide_at, 2)
        table.extend(struct.pack('<HHhBBII', len(ansi), len(wide) // 2, ident, kind, region, a, w))
    pool.extend(b'\0' * (-len(pool) % 4))
    need(len(pool) <= V4_MAX_POOL, 'v4 pool limit')
    header = struct.pack('<IHHIIIIII', V4_MAGIC, V4_VERSION, V4_HEADER, len(rows), V4_ROW, V4_HEADER,
                         V4_HEADER + len(table), len(pool), 1)
    return header + bytes(table) + bytes(pool)


def decode_v4(blob):
    need(type(blob) is bytes and len(blob) >= V4_HEADER, 'v4 size')
    magic, ver, hsize, count, rsize, roff, poff, plen, flags = struct.unpack_from('<IHHIIIIII', blob)
    need(magic == V4_MAGIC and ver == V4_VERSION and hsize == V4_HEADER and rsize == V4_ROW and roff == V4_HEADER, 'v4 header')
    need(1 <= count <= V4_MAX_ROWS and poff == roff + count * rsize and poff + plen == len(blob)
         and plen <= V4_MAX_POOL and flags == 1, 'v4 extents')
    pool, rows = blob[poff:], []
    for i in range(count):
        alen, units, ident, kind, region, a, w = struct.unpack_from('<HHhBBII', blob, roff + i * rsize)
        need(a + alen < plen and pool[a + alen] == 0 and w % 2 == 0 and w + units * 2 + 2 <= plen, 'v4 row extents')
        need(pool[w + units * 2:w + units * 2 + 2] == b'\0\0', 'v4 wide terminator')
        rows.append(make_row(kind, ident, pool[a:a + alen], pool[w:w + units * 2].decode('utf-16le'), region))
    need(rows == sorted(rows, key=sort_key), 'v4 sort order')
    return rows


class Lookup:
    """Python model of native-v4/catalog_core_v4.h (the host test cross-checks them).
    Returns the translation or None (= caller keeps the original ANSI path)."""

    def __init__(self, rows):
        self.by = {}
        for kind, ident, ansi, text, region in rows:
            self.by.setdefault((kind, ansi), []).append((ident, text, region))

    @staticmethod
    def _unique(hits):
        texts = {h[1] for h in hits}
        return texts.pop() if len(texts) == 1 else None

    def find(self, ansi, ident=ANY_ID, flags=ALLOW_ANY | ALLOW_JOIN):
        if type(ansi) is not bytes or not 0 < len(ansi) <= c3.MAX_ANSI or flags & ~FLAG_MASK:
            return None
        if flags & NAME_ONLY and ident != ANY_ID:
            return None                                    # name sites never carry an item id
        if not flags & NAME_ONLY:
            every = self.by.get((FULL_ID, ansi), [])
            hits = [h for h in every if ident == ANY_ID or h[0] == ident]
            if hits:
                return self._unique(hits)
            if every:
                return None                                # item key under another stored_id
        if flags & ALLOW_ANY:
            hits = self.by.get((FULL_ANY, ansi), [])
            if hits:
                return self._unique(hits)                  # ambiguous exact key never joins
        return self.join(ansi) if flags & ALLOW_JOIN else None

    def join(self, ansi):
        try:
            cuts = sorted(c3.cp932_boundaries(ansi) - {0, len(ansi)})
        except Refuse:
            return None
        found = set()
        for k in cuts:
            ps, qs = self.by.get((PREFIX, ansi[:k]), []), self.by.get((SUFFIX, ansi[k:]), [])
            for _, pt, pr in ps:
                for _, qt, qr in qs:
                    if pr == qr:
                        found.add(pt + qt)
        return found.pop() if len(found) == 1 else None


def lookup_v3_equivalent(rows):
    """v3 semantics over v4 rows (region dropped), for regression comparison."""
    return c3.Lookup([(k, i, a, t) for k, i, a, t, _ in rows])


# Site classes for the m063b helper build (call VA -> SITE_FLAGS key). Must cover exactly
# enable_plan_m063's 25 pair5 + 1 tail8 TextOut sites and 18 list sites (test locks it).
# Roles from research/m061/list_sites.json; 'unclassified_list' keeps v3 flags until a
# Win11 observation shows what those lists contain.
LIST_SITE_CLASS = {
    0x4aaf19: 'item_list', 0x4ab0fe: 'item_list',         # shop-buy
    0x4b46e4: 'item_list', 0x4b4df1: 'item_list',         # shop-strengthen, shop-sell
    0x492431: 'unclassified_list',                        # commission-list
    0x4b1153: 'unclassified_list',                        # commission-info
    0x4b3477: 'unclassified_list',                        # inn-commission
    0x4b2d1f: 'name',                                     # tavern
    **{va: 'name' for va in (0x4735f6, 0x474ead, 0x47502c, 0x475bbe, 0x47c242,
                             0x481d42, 0x497a20, 0x4cb4b2, 0x46e73a, 0x47db6a)},  # m063 whole-name
}
TEXTOUT_SITE_CLASS = 'name'   # every LD2_NameTextOut site (pair5 x25, tail8 x1)
NAMEPAIR_SITE_CLASS = 'item_by_id'
