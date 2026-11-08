// m063c: generic adventurer-name TextOut helper over the v4 catalog (MSVC x86).
// Research only; not compiled by MSVC yet (m063b needs user consent).
// production_can_apply/release_approved stay false.
// Same bindings, ABI and public symbol set as research/m062/native-m063/name_textout_v3.h;
// only the core (catalog_core_v4.h) and the lookup flags change. The merge planner tells the
// objects apart by sha256 pin, and a v4 helper refuses v3 blobs (and vice versa).
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
// catalog_v4.SITE_FLAGS['name']: never consult full_id rows (Kris / poleaxe join fixes).
#define LD2N4_FLAGS (LD2C4_ALLOW_ANY|LD2C4_ALLOW_JOIN|LD2C4_NAME_ONLY)
extern "C" {
    extern LD2Word LD2_CatalogBytes;
    extern unsigned char LD2_Catalog[];
    extern const LD2Word LD2_ExpectedTextOutA;   // CDC::TextOut 0x4e13d7 (vtable 0x574174 +0x5c)
    extern const LD2WideMethod LD2_TextOutW;
    int __stdcall LD2N_FindCopy(const char*,int,volatile LD2Wide*);
    void __stdcall LD2N_Wipe(volatile LD2Wide*,int);
    // Installed exactly as v3 (pair5 imm32 / tail8 rel32); callee pops 16.
    int __fastcall LD2_NameTextOut(LD2Cdc* cdc,int unused_edx,int x,int y,const char* ansi,int count);
}
