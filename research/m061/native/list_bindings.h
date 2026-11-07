// m061: binding contract shared by list_insert_w.cpp and list_mock_test.cpp (MSVC x86).
// Every extern below is resolved by the hash-locked merge planner (game) or by the
// mock harness (Windows test only). The game values are documented next to each one.
#ifndef LD2_LIST_BINDINGS_H
#define LD2_LIST_BINDINGS_H
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
typedef int (__stdcall *LD2MultiByteToWideChar)(unsigned, unsigned long, const char*, int, LD2LWide*, int);  // 6 args, stdcall ret 24
extern "C" {
    extern LD2Word LD2_EntryCount;                         // shared .ld2c catalog word
    extern LD2ListRow LD2_Entries[];                       // shared .ld2c rows (592 bytes each)
    extern LD2OriginalDlgItemMessage LD2_OriginalDlgItem;  // .ld2c data word holding 0x4ea671
    extern LD2SendDlgItemMessageW LD2_SendDlgItemMessageW; // new USER32 IAT slot
    extern LD2MultiByteToWideChar LD2_MultiByteToWideChar; // existing KERNEL32 IAT slot 0x52537c
    LD2Word __fastcall LD2_ListInsert(LD2Wnd*, void*, int, unsigned, LD2Word, LD2Word);
}
#endif
