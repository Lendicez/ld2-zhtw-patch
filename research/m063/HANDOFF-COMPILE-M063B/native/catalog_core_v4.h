/* m063c: portable lookup core for catalog v4 (research only; production_can_apply=false).
 * v4 = v3 (research/m062/native-v3/catalog_core_v3.h) plus:
 *   - header version 4 (v3 helpers refuse it; this core refuses version 3);
 *   - row byte 7 = region tag: 0 for full_id/full_any, 1..4 for prefix/suffix
 *     (western, arabic, chinese, japanese); a male join needs both halves from one region;
 *   - lookup flag LD2C4_NAME_ONLY: never consult full_id rows (adventurer-name call sites).
 * Semantics must match research/m063/catalog_v4.py:Lookup (test_catalog_v4.py cross-checks).
 * Pure C/C++ subset: no Windows headers, CRT, heap or globals. Any doubt returns 0 =
 * "caller keeps the original ANSI path". Copy loops write through volatile (MSVC /O2 /Oi). */
#ifndef LD2_CATALOG_CORE_V4_H
#define LD2_CATALOG_CORE_V4_H
typedef unsigned int LD2C4Word;
typedef unsigned short LD2C4Wide;
#define LD2C4_MAGIC 0x43324C44u
#define LD2C4_VERSION 4u
#define LD2C4_HEADER 32u
#define LD2C4_ROW 16u
#define LD2C4_MAX_ROWS 8192u
#define LD2C4_MAX_POOL 0x100000u
#define LD2C4_MAX_ANSI 64u
#define LD2C4_MAX_UNITS 256u
#define LD2C4_FULL_ID 1u
#define LD2C4_FULL_ANY 2u
#define LD2C4_PREFIX 3u
#define LD2C4_SUFFIX 4u
#define LD2C4_REGIONS 4u
#define LD2C4_ANY_ID (-1)
#define LD2C4_ALLOW_ANY 1u
#define LD2C4_ALLOW_JOIN 2u
#define LD2C4_NAME_ONLY 4u
#define LD2C4_FLAG_MASK 7u
typedef struct LD2C4View { const unsigned char* rows; const unsigned char* pool; LD2C4Word count, pool_bytes; } LD2C4View;

static LD2C4Word ld2c4_u32(const unsigned char* p) {
    return (LD2C4Word)p[0] | ((LD2C4Word)p[1] << 8) | ((LD2C4Word)p[2] << 16) | ((LD2C4Word)p[3] << 24);
}
static LD2C4Word ld2c4_u16(const unsigned char* p) { return (LD2C4Word)p[0] | ((LD2C4Word)p[1] << 8); }

static int ld2c4_open(const unsigned char* blob, LD2C4Word size, LD2C4View* v) {
    if (!blob || !v || size < LD2C4_HEADER || size > LD2C4_HEADER + LD2C4_MAX_ROWS * LD2C4_ROW + LD2C4_MAX_POOL) return 0;
    const LD2C4Word count = ld2c4_u32(blob + 8), poff = ld2c4_u32(blob + 20), plen = ld2c4_u32(blob + 24);
    if (ld2c4_u32(blob) != LD2C4_MAGIC || ld2c4_u16(blob + 4) != LD2C4_VERSION || ld2c4_u16(blob + 6) != LD2C4_HEADER) return 0;
    if (ld2c4_u32(blob + 12) != LD2C4_ROW || ld2c4_u32(blob + 16) != LD2C4_HEADER || ld2c4_u32(blob + 28) != 1u) return 0;
    if (count == 0u || count > LD2C4_MAX_ROWS || plen > LD2C4_MAX_POOL) return 0;
    if (poff != LD2C4_HEADER + count * LD2C4_ROW || poff + plen != size) return 0;
    v->rows = blob + LD2C4_HEADER; v->pool = blob + poff; v->count = count; v->pool_bytes = plen;
    return 1;
}
/* Compare row key (kind, len, bytes) with the probe: -1/0/1, or 2 when the row is corrupt. */
static int ld2c4_cmp(const LD2C4View* v, LD2C4Word i, LD2C4Word kind, const unsigned char* s, LD2C4Word n) {
    const unsigned char* r = v->rows + i * LD2C4_ROW;
    const LD2C4Word rk = r[6], rn = ld2c4_u16(r);
    if (rk != kind) return rk < kind ? -1 : 1;
    if (rn != n) return rn < n ? -1 : 1;
    const LD2C4Word a = ld2c4_u32(r + 8);
    if (a >= v->pool_bytes || rn >= v->pool_bytes - a) return 2;
    for (LD2C4Word j = 0; j < n; ++j) if (v->pool[a + j] != s[j]) return v->pool[a + j] < s[j] ? -1 : 1;
    return 0;
}
static LD2C4Word ld2c4_text(const LD2C4View* v, LD2C4Word i, const unsigned char** w) {
    const unsigned char* r = v->rows + i * LD2C4_ROW;
    const LD2C4Word units = ld2c4_u16(r + 2), off = ld2c4_u32(r + 12);
    if (units == 0u || units > LD2C4_MAX_UNITS || (off & 1u) || off >= v->pool_bytes || units * 2u + 2u > v->pool_bytes - off) return 0;
    if (v->pool[off + units * 2u] || v->pool[off + units * 2u + 1u]) return 0;
    *w = v->pool + off;
    return units;
}
static int ld2c4_same(const unsigned char* a, LD2C4Word an, const unsigned char* b, LD2C4Word bn) {
    if (an != bn) return 0;
    for (LD2C4Word k = 0; k < an * 2u; ++k) if (a[k] != b[k]) return 0;
    return 1;
}
/* Unique translation for (kind, bytes[, id][, region]); region 0 = full kinds.
 * Returns 1 hit, 0 absent, -1 ambiguous/corrupt. *any_key = key exists for any id/region.
 * A row whose region tag does not fit its kind is corrupt (-1) wherever it is met. */
static int ld2c4_find(const LD2C4View* v, LD2C4Word kind, const unsigned char* s, LD2C4Word n, int id, LD2C4Word region,
                      const unsigned char** w, LD2C4Word* units, int* any_key) {
    LD2C4Word lo = 0, hi = v->count;
    *any_key = 0;
    while (lo < hi) {
        const LD2C4Word mid = lo + (hi - lo) / 2u;
        const int c = ld2c4_cmp(v, mid, kind, s, n);
        if (c == 2) return -1;
        if (c < 0) lo = mid + 1u; else hi = mid;
    }
    int found = 0;
    for (LD2C4Word i = lo; i < v->count; ++i) {
        const int c = ld2c4_cmp(v, i, kind, s, n);
        if (c == 2) return -1;
        if (c != 0) break;
        const unsigned char* r = v->rows + i * LD2C4_ROW;
        const LD2C4Word rr = r[7];
        if (kind == LD2C4_PREFIX || kind == LD2C4_SUFFIX) {
            if (rr == 0u || rr > LD2C4_REGIONS) return -1;
        } else if (rr != 0u) return -1;
        *any_key = 1;
        if (rr != region) continue;
        const int rid = (int)(short)ld2c4_u16(r + 4);
        if (id != LD2C4_ANY_ID && rid != id) continue;
        const unsigned char* t = 0;
        const LD2C4Word u = ld2c4_text(v, i, &t);
        if (!u) return -1;
        if (found && !ld2c4_same(*w, *units, t, u)) return -1;
        *w = t; *units = u; found = 1;
    }
    return found;
}
static int ld2c4_lead(unsigned char b) { return (b >= 0x81 && b <= 0x9F) || (b >= 0xE0 && b <= 0xFC); }
static LD2C4Word ld2c4_put(volatile LD2C4Wide* out, LD2C4Word at, const unsigned char* w, LD2C4Word units) {
    for (LD2C4Word k = 0; k < units; ++k) out[at + k] = (LD2C4Wide)((LD2C4Word)w[2u * k] | ((LD2C4Word)w[2u * k + 1u] << 8));
    return at + units;
}
static int ld2c4_equal(const volatile LD2C4Wide* out, LD2C4Word at, const unsigned char* w, LD2C4Word units) {
    for (LD2C4Word k = 0; k < units; ++k)
        if (out[at + k] != (LD2C4Wide)((LD2C4Word)w[2u * k] | ((LD2C4Word)w[2u * k + 1u] << 8))) return 0;
    return 1;
}
/* Writes at most cap units (terminator included). Returns units with out[units]==0, or 0
 * (out[0..cap) may then hold scratch; the caller treats it as garbage). */
static LD2C4Word LD2C4_Lookup(const LD2C4View* v, const unsigned char* s, LD2C4Word n, int id, LD2C4Word flags,
                              volatile LD2C4Wide* out, LD2C4Word cap) {
    if (!v || !s || !out || n == 0u || n > LD2C4_MAX_ANSI || cap < 2u || (flags & ~LD2C4_FLAG_MASK)) return 0;
    if ((flags & LD2C4_NAME_ONLY) && id != LD2C4_ANY_ID) return 0;
    const unsigned char* w = 0;
    LD2C4Word units = 0;
    int key = 0, r = 0;
    if (!(flags & LD2C4_NAME_ONLY)) {
        r = ld2c4_find(v, LD2C4_FULL_ID, s, n, id, 0u, &w, &units, &key);
        if (r < 0) return 0;
        if (r == 0 && key) return 0;                   /* item key exists under another id */
    }
    if (r == 0 && (flags & LD2C4_ALLOW_ANY)) {
        r = ld2c4_find(v, LD2C4_FULL_ANY, s, n, LD2C4_ANY_ID, 0u, &w, &units, &key);
        if (r < 0) return 0;
        if (r == 0 && key) return 0;
    }
    if (r == 1) {
        if (units + 1u > cap) return 0;
        out[ld2c4_put(out, 0, w, units)] = 0;
        return units;
    }
    if (!(flags & LD2C4_ALLOW_JOIN)) return 0;
    LD2C4Word total = 0;
    int have = 0;
    for (LD2C4Word k = 0; k < n;) {
        k += ld2c4_lead(s[k]) ? 2u : 1u;
        if (k > n) return 0;                          /* truncated lead byte */
        if (k == n) break;
        for (LD2C4Word region = 1u; region <= LD2C4_REGIONS; ++region) {
            const unsigned char *pw = 0, *qw = 0;
            LD2C4Word pu = 0, qu = 0;
            int pk = 0, qk = 0;
            const int p = ld2c4_find(v, LD2C4_PREFIX, s, k, LD2C4_ANY_ID, region, &pw, &pu, &pk);
            if (p < 0) return 0;
            if (p == 0) continue;
            const int q = ld2c4_find(v, LD2C4_SUFFIX, s + k, n - k, LD2C4_ANY_ID, region, &qw, &qu, &qk);
            if (q < 0) return 0;
            if (q == 0) continue;
            if (pu + qu > LD2C4_MAX_UNITS || pu + qu + 1u > cap) return 0;
            if (!have) {
                ld2c4_put(out, ld2c4_put(out, 0, pw, pu), qw, qu);
                total = pu + qu; have = 1;
            } else if (pu + qu != total || !ld2c4_equal(out, 0, pw, pu) || !ld2c4_equal(out, pu, qw, qu)) {
                return 0;                             /* splits disagree */
            }
        }
    }
    if (!have) return 0;
    out[total] = 0;
    return total;
}
#endif
