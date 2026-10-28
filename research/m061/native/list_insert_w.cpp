// m061: dialog list Unicode shim (MSVC x86 source; NOT compiled or linked yet).
// Replaces, per pinned call site only, `call CWnd::SendDlgItemMessage` (thiscall,
// ret 0x10) for LB_ADDSTRING / LB_INSERTSTRING / CB_INSERTSTRING. Any guard
// failure delegates the untouched arguments to the original wrapper.
// Expected compile (Windows, later milestone): cl /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs list_insert_w.cpp
#if !defined(_M_IX86)
#error x86 only
#endif
#include "list_core.h"
typedef unsigned long LD2Word;
struct LD2Wnd;  // MFC CWnd: +0x20 m_hWnd, +0x4c m_pCtrlSite (as read by the original wrapper 0x4ea671)
// __fastcall with an unused EDX parameter has the same ABI as the thiscall wrapper:
// ECX=this, four stack DWORDs, callee pops 16 bytes.
typedef LD2Word (__fastcall *LD2OriginalDlgItemMessage)(LD2Wnd*, void*, int, unsigned, LD2Word, LD2Word);
typedef LD2Word (__stdcall *LD2SendDlgItemMessageW)(void*, int, unsigned, LD2Word, LD2Word);
typedef int (__stdcall *LD2MultiByteToWideChar)(unsigned, unsigned long, const char*, int, LD2LWide*, int);
extern "C" {
    // Bound by a hash-locked builder; never guessed.
    extern const LD2Word LD2_EntryCount;                       // shared .ld2c catalog
    extern const LD2ListRow LD2_Entries[];
    extern const LD2OriginalDlgItemMessage LD2_OriginalDlgItem;  // data word = 0x4ea671
    extern const LD2SendDlgItemMessageW LD2_SendDlgItemMessageW; // new USER32 IAT word (address of)
    extern const LD2MultiByteToWideChar LD2_MultiByteToWideChar; // existing KERNEL32 IAT word 0x52537c
    LD2Word __fastcall LD2_ListInsert(LD2Wnd*, void*, int, unsigned, LD2Word, LD2Word);
}
static int __stdcall ld2_decode932(const unsigned char* src, int bytes, LD2LWide* dst, int capacity) {
    // 932 = Shift-JIS (CP932); 8 = MB_ERR_INVALID_CHARS: invalid input -> 0 -> original path.
    return LD2_MultiByteToWideChar(932, 8, reinterpret_cast<const char*>(src), bytes, dst, capacity);
}
static int ld2_decode_adapter(const unsigned char* s, int n, LD2LWide* d, int c) { return ld2_decode932(s, n, d, c); }

extern "C" __declspec(noinline) LD2Word __fastcall LD2_ListInsert(LD2Wnd* wnd, void* edx, int id, unsigned msg, LD2Word wp, LD2Word lp) {
    const volatile LD2Word* w = reinterpret_cast<const volatile LD2Word*>(wnd);
    if (!wnd || w[0x4c / 4] != 0 || !LD2_SendDlgItemMessageW || !LD2_MultiByteToWideChar || !LD2_OriginalDlgItem)
        return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    LD2LWide owned[257];
    const int units = LD2_ListPrepare(msg, reinterpret_cast<const unsigned char*>(lp), LD2_Entries,
                                      LD2_EntryCount, ld2_decode_adapter, owned);
    if (units <= 0) return LD2_OriginalDlgItem(wnd, edx, id, msg, wp, lp);
    // The list box copies the string synchronously; `owned` lives on this helper's stack only.
    const LD2Word result = LD2_SendDlgItemMessageW(reinterpret_cast<void*>(w[0x20 / 4]), id, msg, wp,
                                                   reinterpret_cast<LD2Word>(owned));
    for (int i = 0; i <= units; ++i) reinterpret_cast<volatile LD2LWide*>(owned)[i] = 0;
    return result;
}
