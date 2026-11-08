// m062: mock harness for LD2_ListInsertV3 (x86) = m061b's 22 cases over a runtime v3 blob,
// plus v3-only cases (female full_any row, male prefix+suffix join, ambiguous join, corrupt blob). Does NOT open the game, GDI, or USER32:
// every binding is a fake that records its call. Expected last line:
//   cases=N assertions=M failed=0 game_or_user32_called=false
// Windows: HANDOFF-COMPILE-M062/WINDOWS-COMPILE-M062.ps1 Stage B (MSVC /MT).
// Linux rehearsal (logic + i386 stdcall/fastcall ABI only, NOT the MSVC object):
//   zig c++ -target x86-linux-musl -fms-extensions -D_M_IX86=600 list_insert_v3.cpp list_mock_test_v3.cpp
#if !defined(_M_IX86)
#error x86 only
#endif
#ifdef _MSC_VER
#pragma warning(disable : 4505)  // unused static helpers from list_core_v3.h
#endif
#include "list_bindings_v3.h"
#include "v3_mock_blob.h"
#include <cstdio>
#include <cstring>

enum Kind { K_ORIG = 0, K_SENDW, K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SETWL };
struct Capture {
    int kind;
    LD2Wnd* wnd;
    void* edx;
    int id, index;
    unsigned msg;
    LD2Word wp, lp;
    void* hwnd;
    long value;
    int wide_units;
    LD2LWide wide[257];
};
struct Ctx {
    Capture calls[16];
    int total, quiet;
    LD2Word original_return, w_return;
    LD2LWide mb_out[8];
    int mb_out_units, mb_fail_next;
    // fake list box window state
    void* child;          // GetDlgItem result (0 = no such control)
    int unicode;          // IsWindowUnicode
    long proc;            // GetWindowLongW(GWL_WNDPROC)
    unsigned long cproc;  // GetClassLongW(GCL_WNDPROC)
    int set_effective;    // SetWindowLongW(GWL_WNDPROC, same) makes window Unicode
};
static Ctx* active;
static int checks, failed, cases;
#define CHECK(x) do { ++checks; if (!(x)) { ++failed; std::printf("FAIL %d: %s\n", __LINE__, #x); } } while (0)

static Capture sink;
static Capture& Push(int kind) {
    Ctx& c = *active;
    if (c.quiet) { sink.kind = kind; return sink; }
    CHECK(c.total < 16);
    Capture& v = c.calls[c.total < 16 ? c.total++ : 15];
    std::memset(&v, 0, sizeof v);
    v.kind = kind;
    return v;
}
static LD2Word __fastcall FakeOriginal(LD2Wnd* wnd, void* edx, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    Capture& v = Push(K_ORIG);
    v.wnd = wnd; v.edx = edx; v.id = id; v.msg = msg; v.wp = wp; v.lp = lp;
    return active->original_return;
}
static LD2Word __stdcall FakeSendW(void* hwnd, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    Capture& v = Push(K_SENDW);
    v.hwnd = hwnd; v.id = id; v.msg = msg; v.wp = wp; v.lp = lp;
    const LD2LWide* s = reinterpret_cast<const LD2LWide*>(lp);
    int n = 0;
    while (s && n < 256 && s[n]) { v.wide[n] = s[n]; ++n; }
    v.wide_units = n;
    return active->w_return;
}
static int __stdcall FakeMB(unsigned cp, unsigned long flags, const char*, int, LD2LWide* dst, int cap) {
    Capture& v = Push(K_MB);
    if (active->mb_fail_next) { active->mb_fail_next = 0; return 0; }
    if (cp != 932 || (flags & 8) == 0 || !dst || cap < active->mb_out_units) return 0;
    for (int i = 0; i < active->mb_out_units; ++i) dst[i] = active->mb_out[i];
    v.value = active->mb_out_units;
    return active->mb_out_units;
}
static void* __stdcall FakeGetDlgItem(void* dlg, int id) {
    Capture& v = Push(K_GETDLGITEM);
    v.hwnd = dlg; v.id = id;
    return active->child;
}
static int __stdcall FakeIsWindowUnicode(void* h) {
    Capture& v = Push(K_ISUNI);
    v.hwnd = h;
    return active->unicode;
}
static long __stdcall FakeGetWindowLongW(void* h, int index) {
    Capture& v = Push(K_GETWL);
    v.hwnd = h; v.index = index;
    return index == LD2_GWL_WNDPROC ? active->proc : 0x5a5a;
}
static unsigned long __stdcall FakeGetClassLongW(void* h, int index) {
    Capture& v = Push(K_GETCL);
    v.hwnd = h; v.index = index;
    return index == LD2_GCL_WNDPROC ? active->cproc : 0xa5a5;
}
static long __stdcall FakeSetWindowLongW(void* h, int index, long value) {
    Capture& v = Push(K_SETWL);
    v.hwnd = h; v.index = index; v.value = value;
    const long prev = active->proc;
    if (index == LD2_GWL_WNDPROC && active->set_effective) active->unicode = 1;
    return prev;
}

extern "C" {
    LD2Word LD2_CatalogBytes = 0;
    unsigned char LD2_Catalog[4096];
    LD2Word LD2_ListMode = 2;
    LD2OriginalDlgItemMessage LD2_OriginalDlgItem = FakeOriginal;
    LD2SendDlgItemMessageW LD2_SendDlgItemMessageW = FakeSendW;
    LD2MultiByteToWideChar LD2_MultiByteToWideChar = FakeMB;
    LD2GetDlgItem LD2_GetDlgItem = FakeGetDlgItem;
    LD2IsWindowUnicode LD2_IsWindowUnicode = FakeIsWindowUnicode;
    LD2GetWindowLongW LD2_GetWindowLongW = FakeGetWindowLongW;
    LD2GetClassLongW LD2_GetClassLongW = FakeGetClassLongW;
    LD2SetWindowLongW LD2_SetWindowLongW = FakeSetWindowLongW;
}

struct Layout {
    LD2Word pad[0x20 / 4];
    LD2Word hwnd;  // +0x20
    LD2Word mid[(0x4c - 0x24) / 4];
    LD2Word site;  // +0x4c
};
static_assert(sizeof(Layout) >= 0x50, "layout");
static Layout wnd;
static void* const DLG = reinterpret_cast<void*>(0xDEADBEEFUL);
static void* const CHILD = reinterpret_cast<void*>(0x00C0FFEEUL);
static const long PROC = 0x77001234L;

static void Reset(LD2Word mode) {
    std::memset(active, 0, sizeof *active);
    active->original_return = 0x11111111UL;
    active->w_return = 0x22222222UL;
    active->mb_out[0] = 0x30b3; active->mb_out_units = 1;  // U+30B3 (kana: lost to '?' through CP950)
    active->child = CHILD; active->unicode = 0; active->proc = PROC;
    active->cproc = static_cast<unsigned long>(PROC); active->set_effective = 1;
    LD2_ListMode = mode;
    wnd.site = 0;
}
static void Case(const char* name) { ++cases; std::printf("CASE %d %s\n", cases, name); }
static LD2Word Call(const char* s, unsigned msg = 0x181, int id = 1000) {
    return LD2_ListInsertV3(reinterpret_cast<LD2Wnd*>(&wnd), 0, id, msg, static_cast<LD2Word>(-1),
                           reinterpret_cast<LD2Word>(s));
}
static bool Seq(const int* kinds, int n) {
    if (active->total != n) return false;
    for (int i = 0; i < n; ++i) if (active->calls[i].kind != kinds[i]) return false;
    return true;
}
#define SEQ(...) do { static const int k_[] = {__VA_ARGS__}; CHECK(Seq(k_, static_cast<int>(sizeof k_ / sizeof k_[0])));} while (0)

static const char HIT[] = "\xb1\xb2\xc3\xd1";     // catalog key (synthetic)
static const char MISS[] = "\x83\x52";           // CP932 U+30B3, not in catalog
static const char MIXED[] = "\xb1\xb2\xc3\xd1\t\x83\x52\t120G";
static const char FEMALE[] = "\x83\x41\x83\x43";        // synthetic full_any key
static const char MALE[] = "\x83\x4a\x83\x4c\x83\x4e";  // prefix "\x83\x4a" + suffix "\x83\x4c\x83\x4e"
static const char AMBIG[] = "\x83\x54\x83\x56\x83\x58"; // two splits with different text
static const char ROW_MIX[] = "\x83\x4a\x83\x4c\x83\x4e\t\x83\x41\x83\x43\t\xb1\xb2\xc3\xd1";
static unsigned good_bytes;
static unsigned char good_blob[4096];

int main() {
    Ctx ctx; active = &ctx;
    std::memset(&wnd, 0, sizeof wnd);
    wnd.hwnd = reinterpret_cast<LD2Word>(DLG);
    static const LD2LWide tw[] = {0x9053, 0x5177}, fw[] = {0x611b, 0x8389}, p1[] = {0x963f}, s1[] = {0x70c8, 0x723e},
        a1[] = {0x7532}, a2[] = {0x4e59, 0x4e19}, b1[] = {0x4e01, 0x620a}, b2[] = {0x5df1};
    static const MockRow rows[] = {
        {LD2C3_FULL_ID, 1, HIT, tw, 2, 2, 0},
        {LD2C3_FULL_ANY, -1, FEMALE, fw, 2, 2, 0},
        {LD2C3_PREFIX, -1, "\x83\x4a", p1, 1, 1, 0},
        {LD2C3_SUFFIX, -1, "\x83\x4c\x83\x4e", s1, 2, 2, 0},
        {LD2C3_PREFIX, -1, "\x83\x54", a1, 1, 1, 0},
        {LD2C3_SUFFIX, -1, "\x83\x56\x83\x58", a2, 2, 2, 0},
        {LD2C3_PREFIX, -1, "\x83\x54\x83\x56", b1, 2, 2, 0},
        {LD2C3_SUFFIX, -1, "\x83\x58", b2, 1, 1, 0},
    };
    good_bytes = BuildV3(rows, static_cast<int>(sizeof rows / sizeof rows[0]), good_blob, sizeof good_blob);
    CHECK(good_bytes > 0 && good_bytes <= sizeof LD2_Catalog);
    std::memcpy(LD2_Catalog, good_blob, good_bytes);
    LD2_CatalogBytes = good_bytes;

    { Case("ascii-original"); Reset(2); CHECK(Call("Torch\t120G") == 0x11111111UL); SEQ(K_ORIG); }
    { Case("mode2-hit-no-flip"); Reset(2); CHECK(Call(HIT) == 0x22222222UL); SEQ(K_SENDW);
      CHECK(ctx.calls[0].hwnd == DLG && ctx.calls[0].wide_units == 2 && ctx.calls[0].wide[0] == 0x9053); }
    { Case("mode2-miss-flip"); Reset(2); CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SETWL, K_SENDW);
      CHECK(ctx.calls[1].hwnd == DLG && ctx.calls[1].id == 1000);
      CHECK(ctx.calls[2].hwnd == CHILD && ctx.calls[3].hwnd == CHILD && ctx.calls[3].index == -4);
      CHECK(ctx.calls[4].index == -24 && ctx.calls[5].index == -4 && ctx.calls[5].value == PROC);
      CHECK(ctx.calls[6].hwnd == DLG && ctx.calls[6].wide_units == 1 && ctx.calls[6].wide[0] == 0x30b3);
      CHECK(ctx.unicode == 1); }
    { Case("mode2-already-unicode"); Reset(2); ctx.unicode = 1; CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_SENDW); }
    { Case("mode2-subclassed-no-flip"); Reset(2); ctx.proc = 0x00401000L; CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SENDW); }
    { Case("mode2-proc-zero-no-flip"); Reset(2); ctx.proc = 0; ctx.cproc = 0; CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_SENDW); }
    { Case("mode2-no-child"); Reset(2); ctx.child = 0; CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_SENDW); }
    { Case("mode2-flip-ineffective-still-run1-path"); Reset(2); ctx.set_effective = 0; CHECK(Call(MISS) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SETWL, K_SENDW); CHECK(ctx.unicode == 0); }
    { Case("mode2-combo-no-flip"); Reset(2); CHECK(Call(MISS, 0x14a) == 0x22222222UL); SEQ(K_MB, K_SENDW); }
    { Case("mode2-mixed-flip"); Reset(2); CHECK(Call(MIXED) == 0x22222222UL);
      SEQ(K_MB, K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SETWL, K_SENDW);
      CHECK(ctx.calls[7].wide_units == 6 && ctx.calls[7].wide[0] == 0x9053 && ctx.calls[7].wide[2] == 9 && ctx.calls[7].wide[3] == 0x30b3); }
    { Case("mode2-decode-fail-original"); Reset(2); ctx.mb_fail_next = 1; CHECK(Call(MISS) == 0x11111111UL); SEQ(K_MB, K_ORIG);
      CHECK(ctx.calls[1].lp == reinterpret_cast<LD2Word>(MISS) && ctx.calls[1].id == 1000); }
    { Case("mode0-hit-w"); Reset(0); CHECK(Call(HIT) == 0x22222222UL); SEQ(K_SENDW); }
    { Case("mode0-miss-original"); Reset(0); CHECK(Call(MISS) == 0x11111111UL); SEQ(K_MB, K_ORIG);
      CHECK(ctx.calls[1].msg == 0x181 && ctx.calls[1].wp == static_cast<LD2Word>(-1)); }
    { Case("mode0-mixed-original"); Reset(0); CHECK(Call(MIXED) == 0x11111111UL); SEQ(K_MB, K_MB, K_ORIG); }
    { Case("mode1-miss-w-no-flip"); Reset(1); CHECK(Call(MISS) == 0x22222222UL); SEQ(K_MB, K_SENDW); }
    { Case("mode3-disabled"); Reset(3); CHECK(Call(HIT) == 0x11111111UL); SEQ(K_ORIG); }
    { Case("mode-ffffffff-disabled"); Reset(0xffffffffUL); CHECK(Call(MISS) == 0x11111111UL); SEQ(K_ORIG); }
    { Case("null-binding-original"); Reset(2); LD2_SetWindowLongW = 0; CHECK(Call(MISS) == 0x11111111UL); SEQ(K_ORIG);
      LD2_SetWindowLongW = FakeSetWindowLongW; Reset(2); LD2_GetDlgItem = 0; CHECK(Call(HIT) == 0x11111111UL); SEQ(K_ORIG);
      LD2_GetDlgItem = FakeGetDlgItem; }
    { Case("ctrl-site-original"); Reset(2); wnd.site = 1; CHECK(Call(MISS) == 0x11111111UL); SEQ(K_ORIG); wnd.site = 0; }
    { Case("wrong-message-original"); Reset(2); CHECK(Call(MISS, 0x182) == 0x11111111UL); SEQ(K_ORIG); }
    { Case("null-wnd-original"); Reset(2);
      CHECK(LD2_ListInsertV3(0, 0, 1000, 0x181, 0, reinterpret_cast<LD2Word>(MISS)) == 0x11111111UL);
      SEQ(K_ORIG); CHECK(ctx.calls[0].wnd == 0); }
    { Case("v3-mode0-female-any-hit-w"); Reset(0); CHECK(Call(FEMALE) == 0x22222222UL); SEQ(K_SENDW);
      CHECK(ctx.calls[0].wide_units == 2 && ctx.calls[0].wide[0] == 0x611b && ctx.calls[0].wide[1] == 0x8389); }
    { Case("v3-mode0-male-join-hit-w"); Reset(0); CHECK(Call(MALE) == 0x22222222UL); SEQ(K_SENDW);
      CHECK(ctx.calls[0].wide_units == 3 && ctx.calls[0].wide[0] == 0x963f && ctx.calls[0].wide[1] == 0x70c8 && ctx.calls[0].wide[2] == 0x723e); }
    { Case("v3-mode0-ambiguous-join-original"); Reset(0); CHECK(Call(AMBIG) == 0x11111111UL); SEQ(K_MB, K_ORIG); }
    { Case("v3-mode2-ambiguous-join-decoded"); Reset(2); CHECK(Call(AMBIG) == 0x22222222UL);
      SEQ(K_MB, K_GETDLGITEM, K_ISUNI, K_GETWL, K_GETCL, K_SETWL, K_SENDW); CHECK(ctx.calls[6].wide[0] == 0x30b3); }
    { Case("v3-mode0-tab-row-all-hits-w"); Reset(0); CHECK(Call(ROW_MIX) == 0x22222222UL); SEQ(K_SENDW);
      CHECK(ctx.calls[0].wide_units == 9 && ctx.calls[0].wide[3] == 9 && ctx.calls[0].wide[4] == 0x611b && ctx.calls[0].wide[6] == 9 && ctx.calls[0].wide[7] == 0x9053); }
    { Case("v3-corrupt-blob-original"); Reset(2);
      LD2_Catalog[0] ^= 1; CHECK(Call(HIT) == 0x11111111UL); SEQ(K_ORIG); LD2_Catalog[0] ^= 1;
      Reset(2); LD2_CatalogBytes = good_bytes - 1; CHECK(Call(MISS) == 0x11111111UL); SEQ(K_ORIG);
      Reset(2); LD2_CatalogBytes = 0; CHECK(Call(FEMALE) == 0x11111111UL); SEQ(K_ORIG);
      LD2_CatalogBytes = good_bytes; }
    { Case("v3-bad-row-text-original"); Reset(0);
      static const LD2LWide lone[] = {0xd800, 0x41};
      static const MockRow bad[] = {
          {LD2C3_FULL_ID, 1, HIT, lone, 2, 2, 0},          // lone high surrogate
          {LD2C3_FULL_ANY, -1, FEMALE, fw, 2, 2, 1},       // bad terminator
          {LD2C3_PREFIX, -1, "\x83\x4a", p1, 0, 1, 0},     // zero units
          {LD2C3_SUFFIX, -1, "\x83\x4c\x83\x4e", s1, 257, 2, 0}, // units > 256
      };
      unsigned char tmp[1024];
      const unsigned bytes = BuildV3(bad, 4, tmp, sizeof tmp);
      CHECK(bytes > 0);
      std::memcpy(LD2_Catalog, tmp, bytes); LD2_CatalogBytes = bytes;
      CHECK(Call(HIT) == 0x11111111UL); SEQ(K_ORIG);  // hit text fails final validation
      Reset(0); CHECK(Call(FEMALE) == 0x11111111UL); SEQ(K_MB, K_ORIG);
      Reset(0); CHECK(Call(MALE) == 0x11111111UL); SEQ(K_MB, K_ORIG);
      std::memcpy(LD2_Catalog, good_blob, good_bytes); LD2_CatalogBytes = good_bytes; }
    { Case("abi-loop"); Reset(2); ctx.quiet = 1;
      for (int i = 0; i < 1000; ++i) {
          ctx.unicode = i & 1; ctx.proc = (i & 2) ? PROC : 0x00401000L; LD2_ListMode = static_cast<LD2Word>(i % 3);
          const LD2Word r = LD2_ListInsertV3(reinterpret_cast<LD2Wnd*>(&wnd), reinterpret_cast<void*>(static_cast<LD2Word>(i)),
                                            1000 + (i & 7), 0x181, static_cast<LD2Word>(-1),
                                            reinterpret_cast<LD2Word>((i & 4) ? MISS : HIT));
          const bool orig = LD2_ListMode == 0 && (i & 4);
          CHECK(r == (orig ? 0x11111111UL : 0x22222222UL));
      }
      ctx.quiet = 0; }
    std::printf("cases=%d assertions=%d failed=%d game_or_user32_called=false\n", cases, checks, failed);
    return failed ? 1 : 0;
}
