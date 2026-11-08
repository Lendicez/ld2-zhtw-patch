// m061b: binding contract shared by list_insert_u.cpp and list_mock_test_u.cpp (MSVC x86).
// v1 bindings plus four USER32 *W window-class APIs, the existing GetDlgItem IAT slot
// and one .ld2c policy word. Every extern is resolved by the hash-locked merge planner.
#ifndef LD2_LIST_BINDINGS_U_H
#define LD2_LIST_BINDINGS_U_H
#if !defined(_M_IX86)
#error x86 only
#endif
#include "list_core_u.h"
typedef unsigned long LD2Word;
struct LD2Wnd;  // MFC CWnd: +0x20 m_hWnd, +0x4c m_pCtrlSite (as read by the original wrapper 0x4ea671)
typedef LD2Word (__fastcall *LD2OriginalDlgItemMessage)(LD2Wnd*, void*, int, unsigned, LD2Word, LD2Word);
typedef LD2Word (__stdcall *LD2SendDlgItemMessageW)(void*, int, unsigned, LD2Word, LD2Word);    // ret 20
typedef int (__stdcall *LD2MultiByteToWideChar)(unsigned, unsigned long, const char*, int, LD2LWide*, int);  // ret 24
typedef void* (__stdcall *LD2GetDlgItem)(void*, int);                 // ret 8  (existing USER32 IAT 0x525498)
typedef int (__stdcall *LD2IsWindowUnicode)(void*);                   // ret 4  (new USER32 import)
typedef long (__stdcall *LD2GetWindowLongW)(void*, int);              // ret 8  (new USER32 import)
typedef unsigned long (__stdcall *LD2GetClassLongW)(void*, int);      // ret 8  (new USER32 import)
typedef long (__stdcall *LD2SetWindowLongW)(void*, int, long);        // ret 12 (new USER32 import)
enum { LD2_GWL_WNDPROC = -4, LD2_GCL_WNDPROC = -24 };
// .ld2c policy word (planner-written, read-only section):
//   0 = W path only when every non-ASCII segment is a catalog hit (lowest risk; misses keep m045 ANSI path)
//   1 = m061 run1 behaviour (W path for any decodable string; ANSI list boxes lose kana to '?')
//   2 = like 1, but on a catalog miss in a LIST BOX first make that one control a Unicode window
//       (same system proc re-set through SetWindowLongW) when it is provably not subclassed
//   >2 = disabled: always original path
enum { LD2_MODE_HITS_ONLY = 0, LD2_MODE_W_ALWAYS = 1, LD2_MODE_FLIP = 2 };
extern "C" {
    extern LD2Word LD2_EntryCount;
    extern LD2ListRow LD2_Entries[];
    extern LD2Word LD2_ListMode;
    extern LD2OriginalDlgItemMessage LD2_OriginalDlgItem;
    extern LD2SendDlgItemMessageW LD2_SendDlgItemMessageW;
    extern LD2MultiByteToWideChar LD2_MultiByteToWideChar;
    extern LD2GetDlgItem LD2_GetDlgItem;
    extern LD2IsWindowUnicode LD2_IsWindowUnicode;
    extern LD2GetWindowLongW LD2_GetWindowLongW;
    extern LD2GetClassLongW LD2_GetClassLongW;
    extern LD2SetWindowLongW LD2_SetWindowLongW;
    LD2Word __fastcall LD2_ListInsertU(LD2Wnd*, void*, int, unsigned, LD2Word, LD2Word);
}
#endif
