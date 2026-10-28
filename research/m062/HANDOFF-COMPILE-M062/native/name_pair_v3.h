// m062: NamePair v3 binding contract (MSVC x86). Same draw contract as m056/m058;
// only the catalog changes from 264 fixed 592-byte rows to the expandable v3 blob.
#pragma once
#if !defined(_M_IX86)
#error Compile this contract for x86 only.
#endif
#ifdef _MSC_VER
#pragma warning(disable : 4505)  // unused static helpers from catalog_core_v3.h
#endif
#include "catalog_core_v3.h"
typedef unsigned long LD2Word;
typedef unsigned short LD2Wide;
struct LD2Cdc;
typedef int (__thiscall *LD2LegacyMethod)(LD2Cdc*,int,int,const char*,int);
typedef int (__stdcall *LD2WideMethod)(void*,int,int,const LD2Wide*,int);
static_assert(sizeof(void*)==4 && sizeof(LD2Word)==4 && sizeof(LD2Wide)==2,"x86 widths");
extern "C" {
    // Real values come from the hash-locked merge planner (.ld2c, read-only).
    extern LD2Word LD2_CatalogBytes;          // total v3 blob bytes
    extern unsigned char LD2_Catalog[];       // v3 blob (header + rows + pool)
    extern const LD2Word LD2_ExpectedTextOutA;
    extern const LD2WideMethod LD2_TextOutW;  // one loader-populated TextOutW IAT word
    int __stdcall LD2_FindCopy(int,const char*,int,volatile LD2Wide*);
    void __stdcall LD2_NamePair(LD2Cdc*,const char*,int,int);
}
