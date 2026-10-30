/* m061b Linux host test of list_core_u.h decision logic (v2: catalog-miss count) (NOT an ABI/Windows test).
 * CP932 decoding is mocked with glibc iconv; no game data is used. */
#include <iconv.h>
#include <stdio.h>
#include <string.h>
#ifdef HOST_MACRO /* same direct-call decoder path as the MSVC entry */
static int decode(const unsigned char* s, int n, unsigned short* d, int cap);
#define LD2_LIST_DECODE(s, n, d, c) decode((s), (n), (d), (c))
#endif
#include "list_core_u.h"
static int decode(const unsigned char* s, int n, LD2LWide* d, int cap) {
    iconv_t cd = iconv_open("UTF-16LE", "CP932");
    if (cd == (iconv_t)-1) return 0;
    char* in = (char*)s; size_t il = (size_t)n; char* o = (char*)d; size_t ol = (size_t)cap * 2;
    size_t r = iconv(cd, &in, &il, &o, &ol); iconv_close(cd);
    if (r == (size_t)-1 || il) return 0;
    return (int)(((size_t)cap * 2 - ol) / 2);
}
static int fails = 0, total = 0;
#define CHECK(c) do { ++total; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static LD2ListRow rows[4];
static void row(int i, const char* a, const unsigned short* w, int units) {
    memset(&rows[i], 0, sizeof rows[i]); rows[i].ansi_bytes = strlen(a); memcpy(rows[i].ansi, a, strlen(a));
    rows[i].wide_units = units; memcpy(rows[i].wide, w, units * 2);
}
int main(void) {
    LD2LWide out[257];
    int m = -1;
    const unsigned short tr_item[] = {0x9053, 0x5177};        /* zh-TW 道具 (synthetic) */
    const unsigned short tr_a[] = {0x7532}, tr_b[] = {0x4e59};
    row(0, "\xb1\xb2\xc3\xd1", tr_item, 2);                   /* key: CP932 halfwidth katakana */
    row(1, "\x82\xa0", tr_a, 1); row(2, "\x82\xa0", tr_b, 1); /* ambiguous duplicate key */
    row(3, "\x82\xa2", tr_a, 1);
    CHECK(sizeof(LD2ListRow) == 592); /* same layout as m056 LD2NameEntry */
    /* message / pointer guards */
    CHECK(LD2_ListPrepare(0x184, (const unsigned char*)"\x93\xb9", rows, 4, decode, out, &m) == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)(unsigned long)0x1234, rows, 4, decode, out, &m) == 0);
#ifndef HOST_MACRO
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x93\xb9", rows, 4, 0, out, &m) == 0);
#endif
    /* ASCII stays on original path */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"Sword +1\t120", rows, 4, decode, out, &m) == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"", rows, 4, decode, out, &m) == 0);
    /* catalog hit (whole string) */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1", rows, 4, decode, out, &m) == 2 && out[0] == 0x9053 && out[1] == 0x5177 && out[2] == 0);
    /* plain CP932 decode: 道具 */
    CHECK(LD2_ListPrepare(0x180, (const unsigned char*)"\x93\xb9\x8b\xef", rows, 4, decode, out, &m) == 2 && out[0] == 0x9053 && out[1] == 0x5177);
    /* tab segments: catalog segment + decoded + ASCII number */
    int u = LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1\t\x82\xa2\t120", rows, 4, decode, out, &m);
    CHECK(u == 8 && out[0] == 0x9053 && out[2] == 9 && out[3] == 0x7532 && out[4] == 9 && out[5] == '1' && out[7] == '0');
    /* ambiguous duplicate -> decode (Japanese), not either translation */
    CHECK(LD2_ListPrepare(0x14a, (const unsigned char*)"\x82\xa0", rows, 4, decode, out, &m) == 1 && out[0] == 0x3042);
    /* halfwidth katakana without catalog decodes to U+FF71.. */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1", rows, 0, decode, out, &m) == 4 && out[0] == 0xff71 && out[3] == 0xff91);
    /* invalid CP932 (lone lead byte) -> original path */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x93", rows, 4, decode, out, &m) == 0);
    /* control characters -> original path */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x93\xb9\n", rows, 4, decode, out, &m) == 0);
    /* length bound: 256 bytes ok, 257 bytes refused */
    unsigned char big[300]; memset(big, 0, sizeof big);
    for (int i = 0; i < 256; i += 2) { big[i] = 0x93; big[i + 1] = 0xb9; }
    CHECK(LD2_ListPrepare(0x181, big, rows, 4, decode, out, &m) == 128 && out[128] == 0);
    big[256] = 'A';
    CHECK(LD2_ListPrepare(0x181, big, rows, 4, decode, out, &m) == 0);
    /* catalog guard: count over 264 disables lookup (decode still used) */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1", rows, 265, decode, out, &m) == 4);
    /* v2 miss accounting */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1", rows, 4, decode, out, &m) == 2 && m == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1\t120G", rows, 4, decode, out, &m) == 7 && m == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1\t\x82\xa2\t120", rows, 4, decode, out, &m) == 8 && m == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x93\xb9\x8b\xef\t120G", rows, 4, decode, out, &m) == 7 && m == 1);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x82\xa0\t\x93\xb9", rows, 4, decode, out, &m) == 3 && m == 2);
    /* padded requester name (%-12s): trailing spaces make the segment a miss */
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\xb1\xb2\xc3\xd1  ", rows, 4, decode, out, &m) == 6 && m == 1);
    /* refusal resets miss count to 0 */
    m = 7; CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x82\xa0\t\x93", rows, 4, decode, out, &m) == 0 && m == 0);
    m = 7; CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"ASCII", rows, 4, decode, out, &m) == 0 && m == 0);
    CHECK(LD2_ListPrepare(0x181, (const unsigned char*)"\x93\xb9", rows, 4, decode, out, 0) == 0);
    printf("%d checks, %d failed\n", total, fails);
    return fails != 0;
}
