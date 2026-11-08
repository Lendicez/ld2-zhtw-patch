/* m062: portable lookup core for the expandable v3 catalog (research only).
 * Pure C/C++ subset: no Windows headers, CRT, heap or globals. Semantics must match
 * research/m062/catalog_v3.py:Lookup (the Python tests cross-check them).
 * Layout (little-endian):
 *   header 32 B: magic 'LD2C', u16 version=3, u16 header=32, u32 count,
 *                u32 row_size=16, u32 rows_off=32, u32 pool_off, u32 pool_bytes, u32 flags=1(sorted)
 *   row 16 B:    u16 ansi_len, u16 wide_units, i16 id(-1 = any), u8 kind, u8 0, u32 ansi_off, u32 wide_off
 *   rows sorted by (kind, ansi_len, ansi bytes, id); pool holds NUL/0000-terminated strings.
 * Kinds: 1 full_id (item, keyed by stored_id), 2 full_any (female names),
 *        3 prefix / 4 suffix (male first/second, matched only as a two-part join).
 * Lookup flags: LD2C3_ALLOW_ANY (consult full_any rows), LD2C3_ALLOW_JOIN (two-part join).
 *   NamePair (item draw, has stored_id) passes 0; the list shim passes both.
 * Any doubt returns 0 = "caller keeps the original ANSI path".
 * Copy loops write through volatile so MSVC /O2 /Oi cannot turn them into memcpy. */
#ifndef LD2_CATALOG_CORE_V3_H
#define LD2_CATALOG_CORE_V3_H
typedef unsigned int LD2C3Word;
typedef unsigned short LD2C3Wide;
#define LD2C3_MAGIC 0x43324C44u
#define LD2C3_VERSION 3u
#define LD2C3_HEADER 32u
#define LD2C3_ROW 16u
#define LD2C3_MAX_ROWS 8192u
#define LD2C3_MAX_POOL 0x100000u
#define LD2C3_MAX_ANSI 64u
#define LD2C3_MAX_UNITS 256u
#define LD2C3_FULL_ID 1u
#define LD2C3_FULL_ANY 2u
#define LD2C3_PREFIX 3u
#define LD2C3_SUFFIX 4u
#define LD2C3_ANY_ID (-1)
#define LD2C3_ALLOW_ANY 1u
#define LD2C3_ALLOW_JOIN 2u
typedef struct LD2C3View { const unsigned char* rows; const unsigned char* pool; LD2C3Word count, pool_bytes; } LD2C3View;

static LD2C3Word ld2c3_u32(const unsigned char* p) {
    return (LD2C3Word)p[0] | ((LD2C3Word)p[1] << 8) | ((LD2C3Word)p[2] << 16) | ((LD2C3Word)p[3] << 24);
}
static LD2C3Word ld2c3_u16(const unsigned char* p) { return (LD2C3Word)p[0] | ((LD2C3Word)p[1] << 8); }

/* Validates header extents; per-row extents are checked on use. */
static int ld2c3_open(const unsigned char* blob, LD2C3Word size, LD2C3View* v) {
    if (!blob || !v || size < LD2C3_HEADER || size > LD2C3_HEADER + LD2C3_MAX_ROWS * LD2C3_ROW + LD2C3_MAX_POOL) return 0;
    const LD2C3Word count = ld2c3_u32(blob + 8), poff = ld2c3_u32(blob + 20), plen = ld2c3_u32(blob + 24);
    if (ld2c3_u32(blob) != LD2C3_MAGIC || ld2c3_u16(blob + 4) != LD2C3_VERSION || ld2c3_u16(blob + 6) != LD2C3_HEADER) return 0;
    if (ld2c3_u32(blob + 12) != LD2C3_ROW || ld2c3_u32(blob + 16) != LD2C3_HEADER || ld2c3_u32(blob + 28) != 1u) return 0;
    if (count == 0u || count > LD2C3_MAX_ROWS || plen > LD2C3_MAX_POOL) return 0;
    if (poff != LD2C3_HEADER + count * LD2C3_ROW || poff + plen != size) return 0;
    v->rows = blob + LD2C3_HEADER; v->pool = blob + poff; v->count = count; v->pool_bytes = plen;
    return 1;
}
/* Compare row key (kind, len, bytes) against probe: -1/0/1, or 2 when the row is corrupt. */
static int ld2c3_cmp(const LD2C3View* v, LD2C3Word i, LD2C3Word kind, const unsigned char* s, LD2C3Word n) {
    const unsigned char* r = v->rows + i * LD2C3_ROW;
    const LD2C3Word rk = r[6], rn = ld2c3_u16(r);
    if (rk != kind) return rk < kind ? -1 : 1;
    if (rn != n) return rn < n ? -1 : 1;
    const LD2C3Word a = ld2c3_u32(r + 8);
    if (a >= v->pool_bytes || rn >= v->pool_bytes - a) return 2;
    for (LD2C3Word j = 0; j < n; ++j) if (v->pool[a + j] != s[j]) return v->pool[a + j] < s[j] ? -1 : 1;
    return 0;
}
/* Row text: returns units (1..256) with *w set, or 0 if malformed. */
static LD2C3Word ld2c3_text(const LD2C3View* v, LD2C3Word i, const unsigned char** w) {
    const unsigned char* r = v->rows + i * LD2C3_ROW;
    const LD2C3Word units = ld2c3_u16(r + 2), off = ld2c3_u32(r + 12);
    if (units == 0u || units > LD2C3_MAX_UNITS || (off & 1u) || off >= v->pool_bytes || units * 2u + 2u > v->pool_bytes - off) return 0;
    if (v->pool[off + units * 2u] || v->pool[off + units * 2u + 1u]) return 0;
    *w = v->pool + off;
    return units;
}
static int ld2c3_same(const unsigned char* a, LD2C3Word an, const unsigned char* b, LD2C3Word bn) {
    if (an != bn) return 0;
    for (LD2C3Word k = 0; k < an * 2u; ++k) if (a[k] != b[k]) return 0;
    return 1;
}
/* Unique translation for (kind, bytes[, id]). Returns 1 hit, 0 absent, -1 ambiguous/corrupt.
 * *any_key is set to 1 when the key exists for any id. */
static int ld2c3_find(const LD2C3View* v, LD2C3Word kind, const unsigned char* s, LD2C3Word n, int id,
                      const unsigned char** w, LD2C3Word* units, int* any_key) {
    LD2C3Word lo = 0, hi = v->count;
    *any_key = 0;
    while (lo < hi) {
        const LD2C3Word mid = lo + (hi - lo) / 2u;
        const int c = ld2c3_cmp(v, mid, kind, s, n);
        if (c == 2) return -1;
        if (c < 0) lo = mid + 1u; else hi = mid;
    }
    int found = 0;
    for (LD2C3Word i = lo; i < v->count; ++i) {
        const int c = ld2c3_cmp(v, i, kind, s, n);
        if (c == 2) return -1;
        if (c != 0) break;
        *any_key = 1;
        const unsigned char* r = v->rows + i * LD2C3_ROW;
        const int rid = (int)(short)ld2c3_u16(r + 4);
        if (id != LD2C3_ANY_ID && rid != id) continue;
        const unsigned char* t = 0;
        const LD2C3Word u = ld2c3_text(v, i, &t);
        if (!u) return -1;
        if (found && !ld2c3_same(*w, *units, t, u)) return -1;
        *w = t; *units = u; found = 1;
    }
    return found;
}
static int ld2c3_lead(unsigned char b) { return (b >= 0x81 && b <= 0x9F) || (b >= 0xE0 && b <= 0xFC); }
static LD2C3Word ld2c3_put(volatile LD2C3Wide* out, LD2C3Word at, const unsigned char* w, LD2C3Word units) {
    for (LD2C3Word k = 0; k < units; ++k) out[at + k] = (LD2C3Wide)((LD2C3Word)w[2u * k] | ((LD2C3Word)w[2u * k + 1u] << 8));
    return at + units;
}
static int ld2c3_equal(const volatile LD2C3Wide* out, LD2C3Word at, const unsigned char* w, LD2C3Word units) {
    for (LD2C3Word k = 0; k < units; ++k)
        if (out[at + k] != (LD2C3Wide)((LD2C3Word)w[2u * k] | ((LD2C3Word)w[2u * k + 1u] << 8))) return 0;
    return 1;
}
/* Writes at most cap units (terminator included) to out. Returns units with out[units]==0,
 * or 0 (out[0..cap) may hold scratch and must be treated as garbage by the caller). */
static LD2C3Word LD2C3_Lookup(const LD2C3View* v, const unsigned char* s, LD2C3Word n, int id, LD2C3Word flags,
                              volatile LD2C3Wide* out, LD2C3Word cap) {
    if (!v || !s || !out || n == 0u || n > LD2C3_MAX_ANSI || cap < 2u) return 0;
    const unsigned char* w = 0;
    LD2C3Word units = 0;
    int key = 0, key2 = 0;
    int r = ld2c3_find(v, LD2C3_FULL_ID, s, n, id, &w, &units, &key);
    if (r < 0) return 0;
    if (r == 0 && key) return 0;                       /* item key exists under another id */
    if (r == 0 && (flags & LD2C3_ALLOW_ANY)) {
        r = ld2c3_find(v, LD2C3_FULL_ANY, s, n, LD2C3_ANY_ID, &w, &units, &key2);
        if (r < 0) return 0;
        if (r == 0 && key2) return 0;
    }
    if (r == 1) {
        if (units + 1u > cap) return 0;
        out[ld2c3_put(out, 0, w, units)] = 0;
        return units;
    }
    if (!(flags & LD2C3_ALLOW_JOIN)) return 0;
    LD2C3Word total = 0;
    int have = 0;
    for (LD2C3Word k = 0; k < n;) {
        k += ld2c3_lead(s[k]) ? 2u : 1u;
        if (k > n) return 0;                          /* truncated lead byte */
        if (k == n) break;
        const unsigned char *pw = 0, *qw = 0;
        LD2C3Word pu = 0, qu = 0;
        int pk = 0, qk = 0;
        const int p = ld2c3_find(v, LD2C3_PREFIX, s, k, LD2C3_ANY_ID, &pw, &pu, &pk);
        if (p < 0) return 0;
        if (p == 0) continue;
        const int q = ld2c3_find(v, LD2C3_SUFFIX, s + k, n - k, LD2C3_ANY_ID, &qw, &qu, &qk);
        if (q < 0) return 0;
        if (q == 0) continue;
        if (pu + qu > LD2C3_MAX_UNITS || pu + qu + 1u > cap) return 0;
        if (!have) {
            ld2c3_put(out, ld2c3_put(out, 0, pw, pu), qw, qu);
            total = pu + qu; have = 1;
        } else if (pu + qu != total || !ld2c3_equal(out, 0, pw, pu) || !ld2c3_equal(out, pu, qw, qu)) {
            return 0;                                 /* splits disagree */
        }
    }
    if (!have) return 0;
    out[total] = 0;
    return total;
}
#endif
