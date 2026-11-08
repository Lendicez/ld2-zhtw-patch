// m063c: NamePair v4 (MSVC x86). Identical draw path to NamePair v3 (/EHs); only the core
// changes: LD2_FindCopy reads the v4 catalog (region-tagged fragments, version 4).
// Item draw sites pass stored_id (catalog_v4.SITE_FLAGS item_by_id = 0): only full_id rows,
// never full_any rows, never the male join, never NAME_ONLY (flags stay 0 as in v3).
// Compile (future m063b Win11 stage, needs user consent): cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs name_pair_v4.cpp
#include "name_pair_v4.h"

// No CRT strings, heap, C++ object cleanup, catches, HWND or process APIs.
extern "C" __declspec(noinline) LD2LegacyMethod __stdcall LD2_LoadMethod(LD2Cdc* cdc) {
    const LD2Word table=*reinterpret_cast<const volatile LD2Word*>(cdc);
    const LD2Word target=reinterpret_cast<const volatile LD2Word*>(table)[0x5c/4];
    return reinterpret_cast<LD2LegacyMethod>(target);
}
extern "C" __declspec(noinline) void __stdcall LD2_OriginalOne(LD2Cdc* cdc,int x,const char* ansi,int count) {
    LD2LegacyMethod method=LD2_LoadMethod(cdc);
    method(cdc,x,21,ansi,count); // ECX=cdc, four stack DWORDs, original ret 16.
}
extern "C" __declspec(noinline) void __stdcall LD2_OriginalPair(LD2Cdc* cdc,const char* ansi,int count) {
    LD2_OriginalOne(cdc,57,ansi,count);
    LD2_OriginalOne(cdc,56,ansi,count); // reloads vptr/slot; no cached method.
}
extern "C" __declspec(noinline) void __stdcall LD2_Wipe(volatile LD2Wide* text,int units) {
    for (int i=0;i<=units;++i) text[i]=0;
}
// Returns UTF-16 units copied to destination[0..units) with destination[units]==0, or 0.
// destination must hold 257 units. On any rejection the written prefix is wiped.
extern "C" __declspec(noinline) int __stdcall LD2_FindCopy(int id,const char* ansi,int count,volatile LD2Wide* destination) {
    if (!ansi || !destination || count<=0 || count>64) return 0;
    LD2C4View view;
    if (!ld2c4_open(LD2_Catalog,static_cast<LD2C4Word>(LD2_CatalogBytes),&view)) return 0;
    const LD2C4Word units=LD2C4_Lookup(&view,reinterpret_cast<const unsigned char*>(ansi),
                                       static_cast<LD2C4Word>(count),id,0u,destination,257u);
    if (units==0u || units>256u) return 0;
    for (LD2C4Word i=0;i<units;++i) {
        const LD2Wide v=destination[i];
        bool bad=v<32 || v==127;
        if (v>=0xd800 && v<=0xdbff) {
            if (++i>=units || destination[i]<0xdc00 || destination[i]>0xdfff) bad=true;
        } else if (v>=0xdc00 && v<=0xdfff) bad=true;
        if (bad) {
            LD2_Wipe(destination,static_cast<int>(units));
            return 0;
        }
    }
    return static_cast<int>(units);
}

extern "C" __declspec(noinline) void __stdcall LD2_NamePair(LD2Cdc* cdc,const char* ansi,int count,int id) {
    // Guard failure delegates opaque original arguments; it never suppresses
    // an original draw or catches an exception raised by a virtual method.
    if (!cdc || !ansi || count<=0 || count>64 || !LD2_ExpectedTextOutA || !LD2_TextOutW) {
        LD2_OriginalPair(cdc,ansi,count);
        return;
    }
    if (reinterpret_cast<LD2Word>(LD2_LoadMethod(cdc))!=LD2_ExpectedTextOutA) {
        LD2_OriginalPair(cdc,ansi,count);
        return;
    }
    LD2Wide owned[257]; // this helper's stack only, not the original MFC frame.
    const int units=LD2_FindCopy(id,ansi,count,owned);
    if (units==0) {
        LD2_OriginalPair(cdc,ansi,count);
        return;
    }
    void* hdc=reinterpret_cast<void*>(reinterpret_cast<const volatile LD2Word*>(cdc)[1]);
    LD2_TextOutW(hdc,57,21,owned,units);
    // A reentrant change must not silently bypass a changed second method.
    if (reinterpret_cast<LD2Word>(LD2_LoadMethod(cdc))==LD2_ExpectedTextOutA) {
        hdc=reinterpret_cast<void*>(reinterpret_cast<const volatile LD2Word*>(cdc)[1]);
        LD2_TextOutW(hdc,56,21,owned,units);
    } else {
        LD2_OriginalOne(cdc,56,ansi,count);
    }
    LD2_Wipe(owned,units);
}
