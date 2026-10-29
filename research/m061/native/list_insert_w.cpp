// m061: dialog list Unicode shim (MSVC x86). Compile-only on Windows via
// HANDOFF-COMPILE/WINDOWS-COMPILE.ps1; never linked into the game by that script.
// Replaces, per pinned call site only, `call CWnd::SendDlgItemMessage` (thiscall,
// ret 0x10) for LB_ADDSTRING / LB_INSERTSTRING / CB_INSERTSTRING. Any guard
// failure delegates the untouched arguments to the original wrapper.
// Compile: cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs list_insert_w.cpp
static int __stdcall ld2_decode932(const unsigned char* src, int bytes, unsigned short* dst, int capacity);
#define LD2_LIST_DECODE(s, n, d, c) ld2_decode932((s), (n), (d), (c))
#include "list_bindings.h"

static int __stdcall ld2_decode932(const unsigned char* src, int bytes, unsigned short* dst, int capacity) {
    // 932 = Shift-JIS (CP932); 8 = MB_ERR_INVALID_CHARS: invalid input -> 0 -> original path.
    return LD2_MultiByteToWideChar(932, 8, reinterpret_cast<const char*>(src), bytes, dst, capacity);
}

extern "C" __declspec(noinline) LD2Word __fastcall LD2_ListInsert(LD2Wnd* wnd, void* edx, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    const volatile LD2Word* w = reinterpret_cast<const volatile LD2Word*>(wnd);
    if (!wnd || w[0x4c / 4] != 0 || !LD2_SendDlgItemMessageW || !LD2_MultiByteToWideChar || !LD2_OriginalDlgItem)
        return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    LD2LWide owned[257];
    const int units = LD2_ListPrepare(msg, reinterpret_cast<const unsigned char*>(lp), LD2_Entries,
                                      LD2_EntryCount, 0, owned);
    if (units <= 0) return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    // The list box copies the string synchronously; `owned` lives on this helper's stack only.
    const LD2Word result = LD2_SendDlgItemMessageW(reinterpret_cast<void*>(w[0x20 / 4]), id, msg, wp,
                                                   reinterpret_cast<LD2Word>(owned));
    for (int i = 0; i <= units; ++i) reinterpret_cast<volatile LD2LWide*>(owned)[i] = 0;
    return result;
}
