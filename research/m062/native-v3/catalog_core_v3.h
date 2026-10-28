/* m062: portable lookup core for the expandable v3 catalog (research only).
 * Pure C: no Windows headers, CRT, heap or globals. Semantics must match
 * research/m062/catalog_v3.py:Lookup (the Python tests cross-check them).
 * Layout (little-endian):
 *   header 32 B: magic 'LD2C', u16 version=3, u16 header=32, u32 count,
 *                u32 row_size=16, u32 rows_off=32, u32 pool_off, u32 pool_bytes, u32 flags=1(sorted)
 *   row 16 B:    u16 ansi_len, u16 wide_units, i16 id(-1 = any), u8 kind, u8 0, u32 ansi_off, u32 wide_off
 *   rows sorted by (kind, ansi_len, ansi bytes, id); pool holds NUL/0000-terminated strings.
 * Kinds: 1 full_id (item, keyed by stored_id), 2 full_any (female names),
 *        3 prefix / 4 suffix (male first/second, matched only as a two-part join).
 * Any doubt returns 0 = "caller keeps the original ANSI path". */
#ifndef LD2_CATALOG_CORE_V3_H
#define LD2_CATALOG_CORE_V3_H
typedef unsigned int LD2C3Word;
typedef unsigned short LD2C3Wide;
enum { LD2C3_MAGIC = 0x43324C44u, LD2C3_VERSION = 3, LD2C3_HEADER = 32, LD2C3_ROW = 16,
       LD2C3_MAX_ROWS = 8192, LD2C3_MAX_POOL = 1u << 20, LD2C3_MAX_ANSI = 64, LD2C3_MAX_UNITS = 256,
       LD2C3_FULL_ID = 1, LD2C3_FULL_ANY = 2, LD2C3_PREFIX = 3, LD2C3_SUFFIX = 4, LD2C3_ANY_ID = -1 };
typedef struct LD2C3View { const unsigned char* rows; const unsigned char* pool; LD2C3Word count, pool_bytes; } LD2C3View;

static LD2C3Word ld2c3_u32(const unsigned char* p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((LD2C3Word)p[3] << 24); }
static unsigned ld2c3_u16(const unsigned char* p) { return p[0] | (p[1] << 8); }

/* Validates header extents only; per-row extents are checked on use. */
static int ld2c3_open(const unsigned char* blob, LD2C3Word size, LD2C3View* v) {
    if (!blob || !v || size < LD2C3_HEADER) return 0;
    LD2C3Word count = ld2c3_u32(blob + 8), poff = ld2c3_u32(blob + 20), plen = ld2c3_u32(blob + 24);
    if (ld2c3_u32(blob) != LD2C3_MAGIC || ld2c3_u16(blob + 4) != LD2C3_VERSION || ld2c3_u16(blob + 6) != LD2C3_HEADER) return 0;
    if (ld2c3_u32(blob + 12) != LD2C3_ROW || ld2c3_u32(blob + 16) != LD2C3_HEADER || ld2c3_u32(blob + 28) != 1) return 0;
    if (count == 0 || count > LD2C3_MAX_ROWS || plen > LD2C3_MAX_POOL) return 0;
    if (poff != LD2C3_HEADER + count * LD2C3_ROW || poff + plen != size) return 0;
    v->rows = blob + LD2C3_HEADER; v->pool = blob + poff; v->count = count; v->pool_bytes = plen;
    return 1;
}
/* Compare row key (kind, len, bytes) against probe; <0, 0, >0. */
static int ld2c3_cmp(const LD2C3View* v, LD2C3Word i, unsigned kind, const unsigned char* s, unsigned n) {
    const unsigned char* r = v->rows + i * LD2C3_ROW;
    unsigned rk = r[6], rn = ld2c3_u16(r);
    if (rk != kind) return rk < kind ? -1 : 1;
    if (rn != n) return rn < n ? -1 : 1;
    LD2C3Word a = ld2c3_u32(r + 8);
    if (a + rn >= v->pool_bytes) return 2; /* corrupt: caller refuses */
    for (unsigned j = 0; j < n; ++j) if (v->pool[a + j] != s[j]) return v->pool[a + j] < s[j] ? -1 : 1;
    return 0;
}
/* Row text: returns units (1..256) with *w set, or 0 if malformed. */
static unsigned ld2c3_text(const LD2C3View* v, LD2C3Word i, const unsigned char** w) {
    const unsigned char* r = v->rows + i * LD2C3_ROW;
    unsigned units = ld2c3_u16(r + 2); LD2C3Word off = ld2c3_u32(r + 12);
    if (units == 0 || units > LD2C3_MAX_UNITS || (off & 1) || off + units * 2 + 2 > v->pool_bytes) return 0;
    if (v->pool[off + units * 2] || v->pool[off + units * 2 + 1]) return 0;
    *w = v->pool + off; return units;
}
static int ld2c3_same(const unsigned char* a, unsigned an, const unsigned char* b, unsigned bn) {
    if (an != bn) return 0;
    for (unsigned k = 0; k < an * 2; ++k) if (a[k] != b[k]) return 0;
    return 1;
}
/* Unique translation for (kind, bytes[, id]). Returns 1 hit, 0 absent, -1 ambiguous/corrupt. */
static int ld2c3_find(const LD2C3View* v, unsigned kind, const unsigned char* s, unsigned n, int id,
                      const unsigned char** w, unsigned* units) {
    LD2C3Word lo = 0, hi = v->count;
    while (lo < hi) {  /* lower bound */
        LD2C3Word mid = lo + (hi - lo) / 2; int c = ld2c3_cmp(v, mid, kind, s, n);
        if (c == 2) return -1;
        if (c < 0) lo = mid + 1; else hi = mid;
    }
    int found = 0, seen_key = 0;
    for (LD2C3Word i = lo; i < v->count; ++i) {
        int c = ld2c3_cmp(v, i, kind, s, n);
        if (c == 2) return -1;
        if (c != 0) break;
        seen_key = 1;
        const unsigned char* r = v->rows + i * LD2C3_ROW;
        int rid = (short)ld2c3_u16(r + 4);
        if (id != LD2C3_ANY_ID && rid != id) continue;
        const unsigned char* t; unsigned u = ld2c3_text(v, i, &t);
        if (!u) return -1;
        if (found && !ld2c3_same(*w, *units, t, u)) return -1;
        *w = t; *units = u; found = 1;
    }
    (void)seen_key;
    return found;
}
static int ld2c3_lead(unsigned char b) { return (b >= 0x81 && b <= 0x9F) || (b >= 0xE0 && b <= 0xFC); }
static unsigned ld2c3_copy(LD2C3Wide* out, unsigned at, const unsigned char* w, unsigned units) {
    for (unsigned k = 0; k < units; ++k) out[at + k] = (LD2C3Wide)(w[2 * k] | (w[2 * k + 1] << 8));
    return at + units;
}
/* out must hold 257 units. Returns units written (out[units]==0) or 0. */
static unsigned LD2C3_Lookup(const LD2C3View* v, const unsigned char* s, unsigned n, int id, int allow_join, LD2C3Wide* out) {
    if (!v || !s || !out || n == 0 || n > LD2C3_MAX_ANSI) return 0;
    const unsigned char* w = 0; unsigned units = 0;
    int r = ld2c3_find(v, LD2C3_FULL_ID, s, n, id, &w, &units);
    if (r < 0) return 0;
    if (r == 0) {
        /* an id-filtered miss must not fall through if the key exists for another id */
        const unsigned char* w2 = 0; unsigned u2 = 0;
        if (id != LD2C3_ANY_ID && ld2c3_find(v, LD2C3_FULL_ID, s, n, LD2C3_ANY_ID, &w2, &u2) != 0) return 0;
        r = ld2c3_find(v, LD2C3_FULL_ANY, s, n, LD2C3_ANY_ID, &w, &units);
        if (r < 0) return 0;
    }
    if (r == 1) { out[ld2c3_copy(out, 0, w, units)] = 0; return units; }
    if (!allow_join) return 0;
    unsigned total = 0, have = 0;
    LD2C3Wide first[LD2C3_MAX_UNITS + 1];
    for (unsigned k = 0; k < n;) {
        k += ld2c3_lead(s[k]) ? 2 : 1;
        if (k > n) return 0;            /* truncated lead byte */
        if (k == n) break;
        const unsigned char *pw, *qw; unsigned pu, qu;
        int p = ld2c3_find(v, LD2C3_PREFIX, s, k, LD2C3_ANY_ID, &pw, &pu);
        if (p < 0) return 0;
        if (p == 0) continue;
        int q = ld2c3_find(v, LD2C3_SUFFIX, s + k, n - k, LD2C3_ANY_ID, &qw, &qu);
        if (q < 0) return 0;
        if (q == 0) continue;
        if (pu + qu > LD2C3_MAX_UNITS) return 0;
        LD2C3Wide cand[LD2C3_MAX_UNITS + 1];
        unsigned cu = ld2c3_copy(cand, ld2c3_copy(cand, 0, pw, pu), qw, qu);
        if (have) {
            if (cu != total) return 0;
            for (unsigned j = 0; j < cu; ++j) if (cand[j] != first[j]) return 0;
        } else {
            for (unsigned j = 0; j < cu; ++j) first[j] = cand[j];
            total = cu; have = 1;
        }
    }
    if (!have) return 0;
    for (unsigned j = 0; j < total; ++j) out[j] = first[j];
    out[total] = 0;
    return total;
}
#endif
