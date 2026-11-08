// m063c: NamePair v4 binding contract (MSVC x86). Same draw contract, bindings and public
// symbol set as research/m062/native-v3/name_pair_v3.h; only the core changes to catalog v4.
#pragma once
#if !defined(_M_IX86)
#error Compile this contract for x86 only.
#endif
#ifdef _MSC_VER
#pragma warning(disable : 4505)  // unused static helpers from catalog_core_v4.h
#endif
#include "catalog_core_v4.h"
typedef unsigned long LD2Word;
typedef unsigned short LD2Wide;
struct LD2Cdc;
typedef int (__thiscall *LD2LegacyMethod)(LD2Cdc*,int,int,const char*,int);
typedef int (__stdcall *LD2WideMethod)(void*,int,int,const LD2Wide*,int);
static_assert(sizeof(void*)==4 && sizeof(LD2Word)==4 && sizeof(LD2Wide)==2,"x86 widths");
extern "C" {
    // Real values come from the hash-locked merge planner (.ld2c, read-only).
    extern LD2Word LD2_CatalogBytes;          // total v4 blob bytes
    extern unsigned char LD2_Catalog[];       // v4 blob (header version 4 + rows + pool)
    extern const LD2Word LD2_ExpectedTextOutA;
    extern const LD2WideMethod LD2_TextOutW;  // one loader-populated TextOutW IAT word
    int __stdcall LD2_FindCopy(int,const char*,int,volatile LD2Wide*);
    void __stdcall LD2_NamePair(LD2Cdc*,const char*,int,int);
}
