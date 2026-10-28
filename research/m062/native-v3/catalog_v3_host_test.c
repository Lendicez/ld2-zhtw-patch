/* m062 host test: reads a v3 catalog blob and a case file, checks LD2C3_Lookup.
 * Case line: <ansi hex> <id> <join 0|1> <expected utf16le hex or -> ; prints PASS/FAIL counts.
 * Linux/gcc only; links nothing but libc for file IO in this harness. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "catalog_core_v3.h"
static unsigned hex(const char* h, unsigned char* out, unsigned cap) {
    unsigned n = 0;
    while (h[0] && h[1] && n < cap) { unsigned v; sscanf(h, "%2x", &v); out[n++] = (unsigned char)v; h += 2; }
    return n;
}
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    FILE* f = fopen(argv[1], "rb"); if (!f) return 2;
    static unsigned char blob[(1 << 20) + 8192 * 16 + 64];
    size_t size = fread(blob, 1, sizeof blob, f); fclose(f);
    LD2C3View v;
    int opened = ld2c3_open(blob, (LD2C3Word)size, &v);
    FILE* c = fopen(argv[2], "r"); if (!c) return 2;
    char a[512], e[1200]; int id, join, pass = 0, fail = 0;
    if (fscanf(c, "open %d\n", &id) == 1 && id != opened) { printf("FAIL open=%d\n", opened); return 1; }
    if (!opened) { printf("PASS 0 FAIL 0 (refused as expected)\n"); return 0; }
    while (fscanf(c, "%511s %d %d %1199s", a, &id, &join, e) == 4) {
        unsigned char s[256]; unsigned n = strcmp(a, "-") ? hex(a, s, sizeof s) : 0;
        LD2C3Wide out[LD2C3_MAX_UNITS + 1]; memset(out, 0xCC, sizeof out);
        unsigned u = LD2C3_Lookup(&v, s, n, id, join, out);
        unsigned char want[600]; unsigned wn = strcmp(e, "-") ? hex(e, want, sizeof want) : 0;
        int ok = (u * 2 == wn) && (!u || out[u] == 0);
        for (unsigned k = 0; ok && k < u; ++k) ok = out[k] == (LD2C3Wide)(want[2 * k] | (want[2 * k + 1] << 8));
        if (ok) ++pass; else { ++fail; if (fail < 10) printf("FAIL %s id=%d join=%d got=%u\n", a, id, join, u); }
    }
    fclose(c);
    printf("PASS %d FAIL %d\n", pass, fail);
    return fail ? 1 : 0;
}
