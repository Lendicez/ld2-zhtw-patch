/* m061b: portable decision core for the dialog list Unicode shim (v2: reports catalog misses).
 * Pure C, no Windows headers, no CRT strings, heap or globals. The Windows
 * entry (list_insert_w.cpp) and the Linux host test both include this file.
 * Catalog rows reuse the m056 LD2NameEntry layout (592 bytes) so one catalog
 * section serves both the TextOutW helper and this list shim. */
#ifndef LD2_LIST_CORE_U_H
#define LD2_LIST_CORE_U_H
typedef unsigned int LD2LWord;  /* 32-bit on MSVC x86 and on LP64 hosts */
typedef unsigned short LD2LWide;
typedef struct LD2ListRow {
    int stored_id;               /* ignored here: list strings carry no ID */
    LD2LWord ansi_bytes;
    unsigned char ansi[64];
    LD2LWord wide_units;
    LD2LWide wide[257];
} LD2ListRow;
/* Strict CP932 decoder: returns UTF-16 units written (no terminator) or 0.
 * Host builds pass a function pointer. The MSVC entry defines LD2_LIST_DECODE
 * so the decoder is a direct call (no indirect register call for the audit). */
typedef int (*LD2Decode932)(const unsigned char* src, int bytes, LD2LWide* dst, int capacity);
#ifdef LD2_LIST_DECODE
#define LD2_LIST_DECODE_CALL(s, n, d, c) LD2_LIST_DECODE(s, n, d, c)
#else
#define LD2_LIST_DECODE_CALL(s, n, d, c) decode(s, n, d, c)
#endif

enum { LD2_LB_ADDSTRING = 0x180, LD2_LB_INSERTSTRING = 0x181, LD2_CB_INSERTSTRING = 0x14a,
       LD2_LIST_MAX_BYTES = 256, LD2_LIST_MAX_UNITS = 256 };

static int ld2_list_valid_units(const LD2LWide* w, int n) {
    for (int i = 0; i < n; ++i) {
        LD2LWide v = w[i];
        if ((v < 32 && v != 9) || v == 127) return 0;
        if (v >= 0xd800 && v <= 0xdbff) {
            if (++i >= n || w[i] < 0xdc00 || w[i] > 0xdfff) return 0;
        } else if (v >= 0xdc00 && v <= 0xdfff) return 0;
    }
    return 1;
}

/* Unique exact-bytes match; 0 when absent or ambiguous (different translations). */
static const LD2ListRow* ld2_list_find(const unsigned char* s, int n, const LD2ListRow* rows, LD2LWord count) {
    const LD2ListRow* found = 0;
    if (!rows || n <= 0 || n > 64 || count > 264) return 0;
    for (LD2LWord i = 0; i < count; ++i) {
        const LD2ListRow* r = &rows[i];
        if (r->ansi_bytes != (LD2LWord)n) continue;
        int j = 0;
        while (j < n && r->ansi[j] == s[j]) ++j;
        if (j != n) continue;
        if (r->wide_units == 0 || r->wide_units > 256 || r->wide[r->wide_units] != 0) return 0;
        if (found) {
            if (found->wide_units != r->wide_units) return 0;
            for (LD2LWord k = 0; k < r->wide_units; ++k) if (found->wide[k] != r->wide[k]) return 0;
        }
        found = r;
    }
    return found;
}

/* Returns UTF-16 units placed in out[0..units) with out[units]==0, or 0 meaning
 * "use the original ANSI path unchanged". out must hold 257 units.
 * *misses = number of non-ASCII tab segments that were NOT a unique catalog hit
 * (decoded from CP932 instead). 0 means every non-ASCII segment is a translation. */
static int LD2_ListPrepare(unsigned msg, const unsigned char* ansi, const LD2ListRow* rows, LD2LWord count,
                           LD2Decode932 decode, LD2LWide* out, int* misses) {
    if (!misses) return 0;
    *misses = 0;
    if (msg != LD2_LB_ADDSTRING && msg != LD2_LB_INSERTSTRING && msg != LD2_CB_INSERTSTRING) return 0;
#ifdef LD2_LIST_DECODE
    (void)decode;
#else
    if (!decode) return 0;
#endif
    if (!out || (unsigned long)ansi < 0x10000UL) return 0;
    int n = 0, high = 0;
    while (n <= LD2_LIST_MAX_BYTES && ansi[n]) {
        if (ansi[n] >= 0x80) high = 1;
        else if ((ansi[n] < 32 && ansi[n] != 9) || ansi[n] == 127) return 0;
        ++n;
    }
    if (n == 0 || n > LD2_LIST_MAX_BYTES || !high) return 0;  /* ASCII stays on the original path */
    int units = 0, start = 0, miss = 0;
    for (int i = 0; i <= n; ++i) {
        if (i < n && ansi[i] != 9) continue;
        int len = i - start;
        if (len > 0) {
            const LD2ListRow* r = ld2_list_find(ansi + start, len, rows, count);
            if (r) {
                if (units + (int)r->wide_units > LD2_LIST_MAX_UNITS) return 0;
                for (LD2LWord k = 0; k < r->wide_units; ++k) out[units++] = r->wide[k];
            } else {
                int seg_high = 0;
                for (int k = start; k < i; ++k) if (ansi[k] >= 0x80) seg_high = 1;
                if (seg_high) ++miss;
                int got = LD2_LIST_DECODE_CALL(ansi + start, len, out + units, LD2_LIST_MAX_UNITS - units);
                if (got <= 0 || units + got > LD2_LIST_MAX_UNITS) return 0;
                units += got;
            }
        }
        if (i < n) {
            if (units + 1 > LD2_LIST_MAX_UNITS) return 0;
            out[units++] = 9;
        }
        start = i + 1;
    }
    if (units == 0 || !ld2_list_valid_units(out, units)) return 0;
    out[units] = 0;
    *misses = miss;
    return units;
}
#endif
