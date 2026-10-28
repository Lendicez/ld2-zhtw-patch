/* m062: dialog list Unicode shim decision core over the v3 catalog.
 * Same contract as m061b list_core_u.h (LD2_ListPrepare) except each tab segment is
 * looked up with LD2C3_Lookup(id=-1, ALLOW_ANY|ALLOW_JOIN): item names (any id, unique
 * translation), female names, then male first+second joins. Pure C, no CRT/heap/globals. */
#ifndef LD2_LIST_CORE_V3_H
#define LD2_LIST_CORE_V3_H
#include "catalog_core_v3.h"
typedef unsigned short LD2LWide;
typedef int (*LD2Decode932)(const unsigned char* src, int bytes, LD2LWide* dst, int capacity);
#ifdef LD2_LIST_DECODE
#define LD2_LIST_DECODE_CALL(s, n, d, c) LD2_LIST_DECODE(s, n, d, c)
#else
#define LD2_LIST_DECODE_CALL(s, n, d, c) decode(s, n, d, c)
#endif
#define LD2_LB_ADDSTRING 0x180u
#define LD2_LB_INSERTSTRING 0x181u
#define LD2_CB_INSERTSTRING 0x14au
#define LD2_LIST_MAX_BYTES 256
#define LD2_LIST_MAX_UNITS 256

static int ld2_list_valid_units(const LD2LWide* w, int n) {
    for (int i = 0; i < n; ++i) {
        const LD2LWide v = w[i];
        if ((v < 32 && v != 9) || v == 127) return 0;
        if (v >= 0xd800 && v <= 0xdbff) {
            if (++i >= n || w[i] < 0xdc00 || w[i] > 0xdfff) return 0;
        } else if (v >= 0xdc00 && v <= 0xdfff) return 0;
    }
    return 1;
}
/* Returns UTF-16 units in out[0..units) with out[units]==0, or 0 = original ANSI path.
 * out must hold 257 units. *misses = non-ASCII segments that were not a catalog hit. */
static int LD2_ListPrepareV3(unsigned msg, const unsigned char* ansi, const LD2C3View* view,
                             LD2Decode932 decode, LD2LWide* out, int* misses) {
    if (!misses) return 0;
    *misses = 0;
    if (msg != LD2_LB_ADDSTRING && msg != LD2_LB_INSERTSTRING && msg != LD2_CB_INSERTSTRING) return 0;
#ifdef LD2_LIST_DECODE
    (void)decode;
#else
    if (!decode) return 0;
#endif
    if (!out || !view || (unsigned long)ansi < 0x10000UL) return 0;
    int n = 0, high = 0;
    while (n <= LD2_LIST_MAX_BYTES && ansi[n]) {
        if (ansi[n] >= 0x80) high = 1;
        else if ((ansi[n] < 32 && ansi[n] != 9) || ansi[n] == 127) return 0;
        ++n;
    }
    if (n == 0 || n > LD2_LIST_MAX_BYTES || !high) return 0;
    int units = 0, start = 0, miss = 0;
    for (int i = 0; i <= n; ++i) {
        if (i < n && ansi[i] != 9) continue;
        const int len = i - start;
        if (len > 0) {
            const LD2C3Word got = LD2C3_Lookup(view, ansi + start, (LD2C3Word)len, LD2C3_ANY_ID,
                                               LD2C3_ALLOW_ANY | LD2C3_ALLOW_JOIN,
                                               (volatile LD2C3Wide*)(out + units), (LD2C3Word)(LD2_LIST_MAX_UNITS + 1 - units));
            if (got) {
                units += (int)got;
            } else {
                int seg_high = 0;
                for (int k = start; k < i; ++k) if (ansi[k] >= 0x80) seg_high = 1;
                if (seg_high) ++miss;
                const int dec = LD2_LIST_DECODE_CALL(ansi + start, len, out + units, LD2_LIST_MAX_UNITS - units);
                if (dec <= 0 || units + dec > LD2_LIST_MAX_UNITS) return 0;
                units += dec;
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
