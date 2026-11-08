// m063 draft: generic adventurer-name TextOut helper over the v3 catalog (MSVC x86).
// Research only; not compiled by MSVC yet. production_can_apply/release_approved stay false.
#pragma once
#if !defined(_M_IX86)
#error Compile this contract for x86 only.
#endif
#ifdef _MSC_VER
#pragma warning(disable : 4505)  // unused static helpers from catalog_core_v3.h
#endif
#include "../native-v3/catalog_core_v3.h"
typedef unsigned long LD2Word;
typedef unsigned short LD2Wide;
struct LD2Cdc;
typedef int (__thiscall *LD2LegacyMethod)(LD2Cdc*,int,int,const char*,int);
typedef int (__stdcall *LD2WideMethod)(void*,int,int,const LD2Wide*,int);
static_assert(sizeof(void*)==4 && sizeof(LD2Word)==4 && sizeof(LD2Wide)==2,"x86 widths");
extern "C" {
    // Same three bindings as NamePair v3 (shared, read-only; filled by the merge planner/loader).
    extern LD2Word LD2_CatalogBytes;
    extern unsigned char LD2_Catalog[];
    extern const LD2Word LD2_ExpectedTextOutA;   // CDC::TextOut 0x4e13d7 (vtable 0x574174 +0x5c)
    extern const LD2WideMethod LD2_TextOutW;
    // Distinct names from NamePair v3 so both objects can be merged side by side.
    int __stdcall LD2N_FindCopy(const char*,int,volatile LD2Wide*);
    void __stdcall LD2N_Wipe(volatile LD2Wide*,int);
    // Installed at each site by replacing the 5-byte pair `mov R1,[cdc]; mov R2,[R1+0x5c]` with
    // `mov R2,imm32(helper)`; the original `mov ecx,cdc; call R2` then enters here with the
    // thiscall stack (x,y,s,n). EDX carries the helper address (ignored). Callee pops 16.
    int __fastcall LD2_NameTextOut(LD2Cdc* cdc,int unused_edx,int x,int y,const char* ansi,int count);
}
