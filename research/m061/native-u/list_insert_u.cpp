// m061b: dialog list Unicode shim v2 (MSVC x86). Compile-only on Windows; never linked
// into the game by the compile handoff. Replaces, per pinned call site only,
// `call CWnd::SendDlgItemMessage` (thiscall, ret 0x10) for LB_ADDSTRING / LB_INSERTSTRING /
// CB_INSERTSTRING. Any guard failure delegates the untouched arguments to the original wrapper.
// v2 adds a policy word (LD2_ListMode) and, in mode 2, turns the target list box into a
// Unicode window so kana survive (m061 run1: ANSI list boxes converted UTF-16 -> CP950 -> '?').
// Compile: cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs list_insert_u.cpp
static int __stdcall ld2_decode932(const unsigned char* src, int bytes, unsigned short* dst, int capacity);
#define LD2_LIST_DECODE(s, n, d, c) ld2_decode932((s), (n), (d), (c))
#include "list_bindings_u.h"

static int __stdcall ld2_decode932(const unsigned char* src, int bytes, unsigned short* dst, int capacity) {
    // 932 = Shift-JIS (CP932); 8 = MB_ERR_INVALID_CHARS: invalid input -> 0 -> original path.
    return LD2_MultiByteToWideChar(932, 8, reinterpret_cast<const char*>(src), bytes, dst, capacity);
}

// Make one dialog list box a Unicode window, only when its window procedure is still the
// class (system) procedure, i.e. nobody (MFC SubclassDlgItem/DDX_Control, comctl32, IME,
// accessibility tools) has subclassed it. Re-setting the SAME procedure through the W API
// is the documented way to switch a window's A/W message translation; no new code runs
// inside the list box. If the window is already Unicode, or the check fails, nothing changes.
static void ld2_make_unicode(void* dlg, int id) {
    void* const h = LD2_GetDlgItem(dlg, id);
    if (!h || LD2_IsWindowUnicode(h)) return;
    const long proc = LD2_GetWindowLongW(h, LD2_GWL_WNDPROC);
    if (!proc || static_cast<unsigned long>(proc) != LD2_GetClassLongW(h, LD2_GCL_WNDPROC)) return;
    LD2_SetWindowLongW(h, LD2_GWL_WNDPROC, proc);
}

extern "C" __declspec(noinline) LD2Word __fastcall LD2_ListInsertU(LD2Wnd* wnd, void* edx, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    const volatile LD2Word* w = reinterpret_cast<const volatile LD2Word*>(wnd);
    const LD2Word mode = LD2_ListMode;
    if (!wnd || w[0x4c / 4] != 0 || mode > static_cast<LD2Word>(LD2_MODE_FLIP) || !LD2_SendDlgItemMessageW || !LD2_MultiByteToWideChar ||
        !LD2_OriginalDlgItem || !LD2_GetDlgItem || !LD2_IsWindowUnicode || !LD2_GetWindowLongW ||
        !LD2_GetClassLongW || !LD2_SetWindowLongW)
        return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    LD2LWide owned[257];
    int misses = 0;
    const int units = LD2_ListPrepare(msg, reinterpret_cast<const unsigned char*>(lp), LD2_Entries,
                                      LD2_EntryCount, 0, owned, &misses);
    if (units <= 0) return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    void* const dlg = reinterpret_cast<void*>(w[0x20 / 4]);
    if (misses) {
        if (mode == static_cast<LD2Word>(LD2_MODE_HITS_ONLY)) return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
        if (mode == static_cast<LD2Word>(LD2_MODE_FLIP) && msg != static_cast<unsigned>(LD2_CB_INSERTSTRING)) ld2_make_unicode(dlg, id);
    }
    // The list box copies the string synchronously; `owned` lives on this helper's stack only.
    const LD2Word result = LD2_SendDlgItemMessageW(dlg, id, msg, wp, reinterpret_cast<LD2Word>(owned));
    for (int i = 0; i <= units; ++i) reinterpret_cast<volatile LD2LWide*>(owned)[i] = 0;
    return result;
}
