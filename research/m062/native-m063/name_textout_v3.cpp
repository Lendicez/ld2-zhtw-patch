// m063 draft: LD2_NameTextOut (MSVC x86, /EHs). Whole-string adventurer-name lookup:
// id = -1 with LD2C3_ALLOW_ANY|LD2C3_ALLOW_JOIN (female full_any rows, male prefix+suffix
// join, and full_id rows only when the translation is unique across ids) - the same flags as
// ListInsertV3. Any doubt calls the original virtual TextOut with the untouched arguments.
// Compile (future Win11 stage): cl /nologo /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs name_textout_v3.cpp
#include "name_textout_v3.h"

static __declspec(noinline) LD2LegacyMethod LD2N_Method(LD2Cdc* cdc) {
    const LD2Word table=*reinterpret_cast<const volatile LD2Word*>(cdc);
    return reinterpret_cast<LD2LegacyMethod>(reinterpret_cast<const volatile LD2Word*>(table)[0x5c/4]);
}
extern "C" __declspec(noinline) void __stdcall LD2N_Wipe(volatile LD2Wide* text,int units) {
    for (int i=0;i<=units;++i) text[i]=0;
}
extern "C" __declspec(noinline) int __stdcall LD2N_FindCopy(const char* ansi,int count,volatile LD2Wide* destination) {
    if (!ansi || !destination || count<=0 || count>64) return 0;
    LD2C3View view;
    if (!ld2c3_open(LD2_Catalog,static_cast<LD2C3Word>(LD2_CatalogBytes),&view)) return 0;
    const LD2C3Word units=LD2C3_Lookup(&view,reinterpret_cast<const unsigned char*>(ansi),
                                       static_cast<LD2C3Word>(count),LD2C3_ANY_ID,
                                       LD2C3_ALLOW_ANY|LD2C3_ALLOW_JOIN,destination,257u);
    if (units==0u || units>256u) return 0;
    for (LD2C3Word i=0;i<units;++i) {
        const LD2Wide v=destination[i];
        bool bad=v<32 || v==127;
        if (v>=0xd800 && v<=0xdbff) {
            if (++i>=units || destination[i]<0xdc00 || destination[i]>0xdfff) bad=true;
        } else if (v>=0xdc00 && v<=0xdfff) bad=true;
        if (bad) { LD2N_Wipe(destination,static_cast<int>(units)); return 0; }
    }
    return static_cast<int>(units);
}
extern "C" int __fastcall LD2_NameTextOut(LD2Cdc* cdc,int,int x,int y,const char* ansi,int count) {
    // The original receiver/method is reloaded from the live vtable; never cached.
    if (!cdc) return LD2N_Method(cdc)(cdc,x,y,ansi,count);  // same fault as the original call
    if (!ansi || count<=0 || count>64 || !LD2_ExpectedTextOutA || !LD2_TextOutW ||
        reinterpret_cast<LD2Word>(LD2N_Method(cdc))!=LD2_ExpectedTextOutA)
        return LD2N_Method(cdc)(cdc,x,y,ansi,count);
    LD2Wide owned[257];
    const int units=LD2N_FindCopy(ansi,count,owned);
    if (units==0) return LD2N_Method(cdc)(cdc,x,y,ansi,count);
    void* hdc=reinterpret_cast<void*>(reinterpret_cast<const volatile LD2Word*>(cdc)[1]);
    const int result=LD2_TextOutW(hdc,x,y,owned,units);
    LD2N_Wipe(owned,units);
    return result;
}
