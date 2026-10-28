// m061: Windows mock harness for LD2_ListInsert (MSVC x86).
// Does NOT open the game, GDI, or USER32. Fake APIs capture every call.
// Expected: cases=N failed=0 game_or_user32_called=false.
// Compile+link: HANDOFF-COMPILE/WINDOWS-COMPILE.ps1 (Stage B).
#if !defined(_M_IX86)
#error x86 only
#endif
#include "list_bindings.h"
#include <cstdio>
#include <cstring>

struct Capture {
    int kind;  // 0 = OriginalDlgItem, 1 = SendDlgItemMessageW, 2 = MultiByteToWideChar
    LD2Wnd* wnd;
    void* edx;
    int id;
    unsigned msg;
    LD2Word wp, lp;
    void* hwnd;
    unsigned mb_cp;
    unsigned long mb_flags;
    int mb_src_len, mb_dst_cap, mb_result;
    char mb_src[64];
    LD2LWide wide[257];
    int wide_units;
};
struct Ctx {
    Capture calls[8];
    int total;
    int quiet;
    LD2Word original_return, w_return;
    int mb_result;               // units to write for MultiByteToWideChar, or 0 for failure
    LD2LWide mb_out[8];
    int mb_out_units;
    int mb_fail_next;            // if non-zero, next MultiByteToWideChar returns 0
    int site;                    // non-zero => m_pCtrlSite active => must fall back
};
static Ctx* active;
static int checks, failed, cases;

#define CHECK(x) do { ++checks; if (!(x)) { ++failed; std::printf("FAIL %d: %s\n", __LINE__, #x); } } while (0)

static Capture sink_capture;
static Capture& Push(int kind) {
    Ctx& c = *active;
    if (c.quiet) { sink_capture.kind = kind; return sink_capture; }
    CHECK(c.total < 8);
    Capture& v = c.calls[c.total++];
    std::memset(&v, 0, sizeof v);
    v.kind = kind;
    return v;
}

static LD2Word __fastcall FakeOriginal(LD2Wnd* wnd, void* edx, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    Capture& v = Push(0);
    v.wnd = wnd; v.edx = edx; v.id = id; v.msg = msg; v.wp = wp; v.lp = lp;
    return active->original_return;
}

static LD2Word __stdcall FakeSendW(void* hwnd, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    Capture& v = Push(1);
    v.hwnd = hwnd; v.id = id; v.msg = msg; v.wp = wp; v.lp = lp;
    const LD2LWide* s = reinterpret_cast<const LD2LWide*>(lp);
    if (s) {
        int n = 0;
        while (n < 257 && s[n]) { v.wide[n] = s[n]; ++n; }
        v.wide_units = n;
        v.wide[n] = 0;
    }
    return active->w_return;
}

static int __stdcall FakeMB(unsigned cp, unsigned long flags, const char* src, int src_len, LD2LWide* dst, int dst_cap) {
    Capture& v = Push(2);
    v.mb_cp = cp; v.mb_flags = flags; v.mb_src_len = src_len; v.mb_dst_cap = dst_cap;
    if (src && src_len > 0 && src_len < 64) std::memcpy(v.mb_src, src, static_cast<std::size_t>(src_len));
    if (active->mb_fail_next) { active->mb_fail_next = 0; v.mb_result = 0; return 0; }
    if (cp != 932 || (flags & 8) == 0 || !dst || dst_cap < active->mb_out_units) { v.mb_result = 0; return 0; }
    for (int i = 0; i < active->mb_out_units; ++i) dst[i] = active->mb_out[i];
    v.mb_result = active->mb_out_units;
    return active->mb_out_units;
}

// Bindings consumed by list_insert_w.cpp. The mock fills them before each call.
extern "C" {
    LD2Word LD2_EntryCount = 0;
    LD2ListRow LD2_Entries[4];
    LD2OriginalDlgItemMessage LD2_OriginalDlgItem = FakeOriginal;
    LD2SendDlgItemMessageW LD2_SendDlgItemMessageW = FakeSendW;
    LD2MultiByteToWideChar LD2_MultiByteToWideChar = FakeMB;
    // /GS symbols: local stubs so the mock links without CRT cookie objects.
    unsigned long ___security_cookie = 0xBB40E64EUL;
    void __fastcall __security_check_cookie(unsigned long cookie) {
        if (cookie != ___security_cookie) {
            std::printf("GS cookie mismatch\n");
            for (;;) {}
        }
    }
}

struct Layout {
    LD2Word pad[0x20 / 4];
    LD2Word hwnd;      // +0x20
    LD2Word mid[(0x4c - 0x24) / 4];
    LD2Word site;      // +0x4c
};
static_assert(sizeof(Layout) >= 0x50, "layout");

static void FillRow(int i, const char* ansi, const LD2LWide* wide, int units) {
    LD2ListRow& r = LD2_Entries[i];
    std::memset(&r, 0, sizeof r);
    r.stored_id = i + 1;
    r.ansi_bytes = static_cast<LD2LWord>(std::strlen(ansi));
    std::memcpy(r.ansi, ansi, r.ansi_bytes);
    r.wide_units = static_cast<LD2LWord>(units);
    for (int k = 0; k < units; ++k) r.wide[k] = wide[k];
    r.wide[units] = 0;
}

static void ResetCtx() {
    active->total = 0;
    active->original_return = 0x11111111UL;
    active->w_return = 0x22222222UL;
    active->mb_result = 0;
    active->mb_out_units = 0;
    active->mb_fail_next = 0;
    active->site = 0;
    active->quiet = 0;
    std::memset(active->calls, 0, sizeof active->calls);
    std::memset(active->mb_out, 0, sizeof active->mb_out);
}

static void Case(const char* name) {
    ++cases;
    std::printf("CASE %d %s\n", cases, name);
}

int main() {
    Ctx ctx; active = &ctx;
    Layout wnd; std::memset(&wnd, 0, sizeof wnd);
    wnd.hwnd = 0xDEADBEEFUL;
    LD2_EntryCount = 0;
    const LD2LWide tw[] = {0x9053, 0x5177};  // synthetic zh-TW 道具
    FillRow(0, "\xb1\xb2\xc3\xd1", tw, 2);    // CP932 halfwidth katakana bytes as catalog key
    LD2_EntryCount = 1;

    // 1. ASCII -> original path, no W call.
    {
        Case("ascii-fallback");
        ResetCtx();
        char ascii[] = "Sword +1";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x181,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(ascii));
        CHECK(r == 0x11111111UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 0);
        CHECK(ctx.calls[0].id == 1000 && ctx.calls[0].msg == 0x181);
        CHECK(ctx.calls[0].lp == reinterpret_cast<LD2Word>(ascii));
        CHECK(ctx.calls[0].wp == static_cast<LD2Word>(-1));
    }

    // 2. Catalog hit -> SendDlgItemMessageW with translated units; Original not called.
    {
        Case("catalog-hit");
        ResetCtx();
        char key[] = "\xb1\xb2\xc3\xd1";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x181,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x22222222UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 1);
        CHECK(ctx.calls[0].hwnd == reinterpret_cast<void*>(0xDEADBEEFUL));
        CHECK(ctx.calls[0].id == 1000 && ctx.calls[0].msg == 0x181);
        CHECK(ctx.calls[0].wide_units == 2);
        CHECK(ctx.calls[0].wide[0] == 0x9053 && ctx.calls[0].wide[1] == 0x5177);
    }

    // 3. Catalog miss + successful CP932 decode -> W path.
    {
        Case("cp932-decode");
        ResetCtx();
        ctx.mb_out[0] = 0x3042; ctx.mb_out_units = 1;  // あ
        char key[] = "\x82\xa0";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x180,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x22222222UL);
        CHECK(ctx.total == 2);
        CHECK(ctx.calls[0].kind == 2 && ctx.calls[0].mb_cp == 932 && (ctx.calls[0].mb_flags & 8));
        CHECK(ctx.calls[0].mb_src_len == 2);
        CHECK(ctx.calls[1].kind == 1 && ctx.calls[1].wide_units == 1 && ctx.calls[1].wide[0] == 0x3042);
    }

    // 4. Decode failure -> original path.
    {
        Case("decode-fail-fallback");
        ResetCtx();
        ctx.mb_fail_next = 1;
        char key[] = "\x93";  // truncated CP932 lead
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1073, 0x181,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x11111111UL);
        CHECK(ctx.total == 2);
        CHECK(ctx.calls[0].kind == 2 && ctx.calls[0].mb_result == 0);
        CHECK(ctx.calls[1].kind == 0 && ctx.calls[1].id == 1073);
        CHECK(ctx.calls[1].lp == reinterpret_cast<LD2Word>(key));
    }

    // 5. m_pCtrlSite != 0 -> original path, no W / no MultiByte.
    {
        Case("ctrl-site-fallback");
        ResetCtx();
        wnd.site = 1;
        char key[] = "\xb1\xb2\xc3\xd1";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x181,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x11111111UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 0);
        wnd.site = 0;
    }

    // 6. Wrong message -> original path.
    {
        Case("wrong-message");
        ResetCtx();
        char key[] = "\xb1\xb2\xc3\xd1";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x182,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x11111111UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 0 && ctx.calls[0].msg == 0x182);
    }

    // 7. Tab-segmented: catalog + decode.
    {
        Case("tab-segments");
        ResetCtx();
        ctx.mb_out[0] = 0x7532; ctx.mb_out_units = 1;  // 甲
        char key[] = "\xb1\xb2\xc3\xd1\t\x82\xa0";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x181,
                                   static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x22222222UL);
        CHECK(ctx.total == 2);  // MultiByte once for second segment; W once
        CHECK(ctx.calls[0].kind == 2);
        CHECK(ctx.calls[1].kind == 1);
        CHECK(ctx.calls[1].wide_units == 4);
        CHECK(ctx.calls[1].wide[0] == 0x9053 && ctx.calls[1].wide[1] == 0x5177);
        CHECK(ctx.calls[1].wide[2] == 9 && ctx.calls[1].wide[3] == 0x7532);
    }

    // 8. CB_INSERTSTRING catalog hit.
    {
        Case("combo-insert");
        ResetCtx();
        char key[] = "\xb1\xb2\xc3\xd1";
        LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x14a,
                                   0, reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x22222222UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 1 && ctx.calls[0].msg == 0x14a);
    }

    // 9. Null window -> original with null this (must not crash).
    {
        Case("null-wnd");
        ResetCtx();
        char key[] = "\xb1\xb2\xc3\xd1";
        LD2Word r = LD2_ListInsert(0, 0, 1000, 0x181, static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
        CHECK(r == 0x11111111UL);
        CHECK(ctx.total == 1 && ctx.calls[0].kind == 0 && ctx.calls[0].wnd == 0);
    }

    // 10. ABI stress: many fastcall/thiscall-shaped calls, no crash, returns stable.
    {
        Case("abi-loop");
        char key[] = "\xb1\xb2\xc3\xd1";
        ResetCtx();
        for (int i = 0; i < 8; ++i) {
            LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), 0, 1000, 0x181,
                                       static_cast<LD2Word>(-1), reinterpret_cast<LD2Word>(key));
            CHECK(r == 0x22222222UL);
        }
        CHECK(ctx.total == 8);
        for (int i = 0; i < 8; ++i) CHECK(ctx.calls[i].kind == 1 && ctx.calls[i].wide_units == 2);
        ctx.quiet = 1;
        for (int i = 0; i < 1000; ++i) {
            LD2Word r = LD2_ListInsert(reinterpret_cast<LD2Wnd*>(&wnd), reinterpret_cast<void*>(static_cast<LD2Word>(i)),
                                       1000 + (i & 7), 0x181, static_cast<LD2Word>(-1),
                                       reinterpret_cast<LD2Word>(key));
            CHECK(r == 0x22222222UL);
        }
        ctx.quiet = 0;
    }

    std::printf("cases=%d assertions=%d failed=%d game_or_user32_called=false\n", cases, checks, failed);
    return failed ? 1 : 0;
}
