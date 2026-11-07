// m062 mocks only: build a sorted v3 catalog blob at runtime (same layout as
// catalog_v3.py:build_v3). Lets the mocks inject malformed rows the real builder refuses.
#ifndef LD2_V3_MOCK_BLOB_H
#define LD2_V3_MOCK_BLOB_H
#include <cstring>
struct MockRow {
    unsigned kind;
    int id;
    const char* ansi;
    const unsigned short* wide;
    unsigned units;      // stored wide_units (may lie: 0, 257 ...)
    unsigned stored;     // units actually written to the pool (normally == units)
    int bad_term;        // 1: terminator 0x4141 instead of 0x0000
};
static void MockPut16(unsigned char* p, unsigned v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }
static void MockPut32(unsigned char* p, unsigned v) { MockPut16(p, v & 0xffffu); MockPut16(p + 2, v >> 16); }
static int MockLess(const MockRow& a, const MockRow& b) {
    if (a.kind != b.kind) return a.kind < b.kind;
    const size_t an = std::strlen(a.ansi), bn = std::strlen(b.ansi);
    if (an != bn) return an < bn;
    const int c = std::memcmp(a.ansi, b.ansi, an);
    if (c) return c < 0;
    return (unsigned short)(short)a.id < (unsigned short)(short)b.id;
}
// Returns blob bytes, or 0 when cap is too small. n <= 64.
static unsigned BuildV3(const MockRow* in, int n, unsigned char* out, unsigned cap) {
    MockRow rows[64];
    if (n <= 0 || n > 64) return 0;
    for (int i = 0; i < n; ++i) rows[i] = in[i];
    for (int i = 1; i < n; ++i)
        for (int j = i; j > 0 && MockLess(rows[j], rows[j - 1]); --j) { MockRow t = rows[j]; rows[j] = rows[j - 1]; rows[j - 1] = t; }
    const unsigned poff = 32u + 16u * (unsigned)n;
    unsigned at = poff;
    if (cap < poff) return 0;
    std::memset(out, 0, cap);
    for (int i = 0; i < n; ++i) {
        const unsigned an = (unsigned)std::strlen(rows[i].ansi);
        unsigned char* r = out + 32u + 16u * (unsigned)i;
        if (at + an + 1u + 1u + rows[i].stored * 2u + 2u > cap) return 0;
        MockPut16(r, an); MockPut16(r + 2, rows[i].units); MockPut16(r + 4, (unsigned)(unsigned short)(short)rows[i].id);
        r[6] = (unsigned char)rows[i].kind; r[7] = 0;
        MockPut32(r + 8, at - poff);
        std::memcpy(out + at, rows[i].ansi, an); at += an; out[at++] = 0;
        if ((at - poff) & 1u) out[at++] = 0;
        MockPut32(r + 12, at - poff);
        for (unsigned k = 0; k < rows[i].stored; ++k) { MockPut16(out + at, rows[i].wide[k]); at += 2; }
        MockPut16(out + at, rows[i].bad_term ? 0x4141u : 0u); at += 2;
    }
    MockPut32(out, 0x43324C44u); MockPut16(out + 4, 3); MockPut16(out + 6, 32); MockPut32(out + 8, (unsigned)n);
    MockPut32(out + 12, 16); MockPut32(out + 16, 32); MockPut32(out + 20, poff); MockPut32(out + 24, at - poff); MockPut32(out + 28, 1);
    return at;
}
#endif
