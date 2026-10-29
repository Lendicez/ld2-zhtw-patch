// m063c: mock harness for NamePair v4 = the NamePair v3 mock (ABI probe, exceptions through the
// helper, vtable swaps) over a runtime-built v4 blob, plus v4 cases: flags stay 0 (item_by_id),
// so a Kris-shaped female row with the same bytes is ignored and the item text is drawn;
// v3 header / bad region tags fail closed. Does NOT open the game or GDI.
// Expected last line: JSON with "failed":0 and "game_or_gdi_called":false.
// Linux rehearsal (logic + i386 ABI only, NOT the MSVC object):
//   zig c++ -target x86-linux-musl -fms-extensions -fasm-blocks -D_M_IX86=600 name_pair_v4.cpp name_pair_mock_v4.cpp
#include "name_pair_v4.h"
#include "v4_mock_blob.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>

struct Capture {
    int kind,x,y,count;
    const void* pointer;
    char ansi[128];
    LD2Wide wide[257];
};
enum Mode {Plain,FalseFirst,FalseSecond,SwapLegacy,SwapWide,ThrowLegacy,ThrowWide,LateThrow};
struct Context {
    Capture calls[4];int total;Mode mode;int throw_at;int cleanup;
    LD2Word* table;LD2Word alternate;void* hdc;
};
static Context* active;
static int checks,failed,cases,iterations;
#define CHECK(x) do { ++checks; if (!(x)) { ++failed; std::printf("FAIL %d: %s\n",__LINE__,#x); } } while (0)
struct MockCdc {
    void* hdc;
    explicit MockCdc(void* h=0):hdc(h) {}
#define UNUSED_SLOT(n) virtual int Slot##n() { return n; }
    UNUSED_SLOT(0) UNUSED_SLOT(1) UNUSED_SLOT(2) UNUSED_SLOT(3)
    UNUSED_SLOT(4) UNUSED_SLOT(5) UNUSED_SLOT(6) UNUSED_SLOT(7)
    UNUSED_SLOT(8) UNUSED_SLOT(9) UNUSED_SLOT(10) UNUSED_SLOT(11)
    UNUSED_SLOT(12) UNUSED_SLOT(13) UNUSED_SLOT(14) UNUSED_SLOT(15)
    UNUSED_SLOT(16) UNUSED_SLOT(17) UNUSED_SLOT(18) UNUSED_SLOT(19)
    UNUSED_SLOT(20) UNUSED_SLOT(21) UNUSED_SLOT(22)
    __declspec(noinline) virtual int __thiscall Text(int,int,const char*,int);
    __declspec(noinline) int __thiscall Alternate(int,int,const char*,int);
};
static void RecordAnsi(MockCdc* receiver,int kind,int x,int y,const char* text,int count) {
    Context& c=*active;CHECK(receiver->hdc==c.hdc);CHECK(c.total<4);
    const int index=c.total++;
    if(index>=4)return;
    Capture& v=c.calls[index];v.kind=kind;v.x=x;v.y=y;v.count=count;v.pointer=text;
    if(text && count>=0 && count<128)std::memcpy(v.ansi,text,static_cast<std::size_t>(count));
    if(c.mode==SwapLegacy && index==0)c.table[23]=c.alternate;
    if((c.mode==ThrowLegacy && index+1==c.throw_at) || (c.mode==LateThrow && kind==2))throw 700+index+1;
}
int __thiscall MockCdc::Text(int x,int y,const char* s,int n) {RecordAnsi(this,1,x,y,s,n);return 1;}
int __thiscall MockCdc::Alternate(int x,int y,const char* s,int n) {RecordAnsi(this,2,x,y,s,n);return 1;}
static __declspec(noinline) int __stdcall FakeWide(void* hdc,int x,int y,const LD2Wide* text,int units) {
    Context& c=*active;CHECK(hdc==c.hdc);CHECK(c.total<4);CHECK(0<units && units<=256);
    const int index=c.total++;
    if(index>=4)return 0;
    Capture& v=c.calls[index];v.kind=3;v.x=x;v.y=y;v.count=units;v.pointer=text;
    if(units>0 && units<=256)std::memcpy(v.wide,text,static_cast<std::size_t>(units)*2);
    CHECK(text[units]==0);
    const std::uintptr_t ptr=reinterpret_cast<std::uintptr_t>(text);
    const std::uintptr_t table=reinterpret_cast<std::uintptr_t>(LD2_Catalog);
    CHECK(ptr<table || ptr>=table+LD2_CatalogBytes); // copied stack owner, not catalog storage.
    if((c.mode==SwapWide || c.mode==LateThrow) && index==0)c.table[23]=c.alternate;
    if(c.mode==ThrowWide && index+1==c.throw_at)throw 700+index+1;
    return !((c.mode==FalseFirst && index==0)||(c.mode==FalseSecond && index==1));
}
static LD2Word ExpectedTarget() {
    MockCdc object;
    return (*reinterpret_cast<const LD2Word* const*>(&object))[23];
}
static LD2Word AlternateTarget() {
    int (__thiscall MockCdc::*method)(int,int,const char*,int)=&MockCdc::Alternate;
#ifdef _MSC_VER
    static_assert(sizeof(method)==sizeof(LD2Word),"single-inheritance member pointer");
#endif  // Itanium (Linux rehearsal): first word of the 8-byte member pointer is the code address.
    LD2Word value=0;std::memcpy(&value,&method,4);return value;
}
#define X16 120,120,120,120,120,120,120,120,120,120,120,120,120,120,120,120
extern "C" {
    const LD2Word LD2_ExpectedTextOutA=ExpectedTarget();
    const LD2WideMethod LD2_TextOutW=&FakeWide;
    LD2Word LD2_CatalogBytes=0;
    unsigned char LD2_Catalog[16384];
    void __stdcall LD2_Wipe(volatile LD2Wide*,int);
}
static const LD2Wide W_CANON[]={0x9304,0x6a94,0x6e2c,0x8a66,0x528d,32,43,49,48},W_VAR[]={0x9304,0x6a94,0x6e2c,0x8a66,0x621f},
    W_PAIR[]={0x528d,0xd83d,0xde42},W_BADNUL[]={0x9304,0},W_HIGH[]={0xd800},W_LOW[]={0xdc00},W_D1[]={0x7532},W_D2[]={0x4e59},
    W_J1[]={0x963f},W_J2[]={0x70c8,0x723e},W_ANY[]={0x611b,0x8389},
    W_KRIS_I[]={0x514b,0x529b,0x58eb,0x528d},W_KRIS_F[]={0x514b,0x8389,0x7d72};
static LD2Wide W_X[257];
static const MockRow4 ROWS[]={
    {LD2C4_FULL_ID,136,"CANONICAL +10",W_CANON,9,9,0,0},
    {LD2C4_FULL_ID,136,"VARIANT",W_VAR,5,5,0,0},
    {LD2C4_FULL_ID,7,"PAIR",W_PAIR,3,3,0,0},
    {LD2C4_FULL_ID,8,"MAX",W_X,256,256,0,0},
    {LD2C4_FULL_ID,9,"EMPTY",W_D1,0,0,0,0},
    {LD2C4_FULL_ID,10,"BADNUL",W_BADNUL,2,2,0,0},
    {LD2C4_FULL_ID,11,"HIGH",W_HIGH,1,1,0,0},
    {LD2C4_FULL_ID,12,"LOW",W_LOW,1,1,0,0},
    {LD2C4_FULL_ID,13,"LONG",W_X,257,257,0,0},
    {LD2C4_FULL_ID,14,"DUP",W_D1,1,1,0,0},
    {LD2C4_FULL_ID,14,"DUP",W_D2,1,1,0,0},
    {LD2C4_FULL_ID,15,"BADTERM",W_D1,1,1,1,0},
    {LD2C4_FULL_ANY,-1,"ANYROW",W_ANY,2,2,0,0},   // female row: NamePair must ignore it
    {LD2C4_PREFIX,-1,"JO",W_J1,1,1,0,1},           // male join parts: NamePair must not join
    {LD2C4_SUFFIX,-1,"IN",W_J2,2,2,0,1},
    {LD2C4_FULL_ID,28,"KRIS",W_KRIS_I,4,4,0,0},  // m063c Kris shape: item row ...
    {LD2C4_FULL_ANY,-1,"KRIS",W_KRIS_F,3,3,0,0}, // ... and a female row with the same bytes
};
static const int ROW_COUNT=static_cast<int>(sizeof ROWS/sizeof ROWS[0]);
struct Snapshot {LD2Word before,after,ebx,esi,edi,ebp,flags;};
extern "C" __declspec(naked) void __cdecl ProbeFour(LD2Cdc*,const char*,int,int,Snapshot*) {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        sub esp,20
        mov eax,[esp+56]
        mov [esp],eax
        mov eax,[esp+40]
        mov [esp+4],eax
        mov eax,[esp+44]
        mov [esp+8],eax
        mov eax,[esp+48]
        mov [esp+12],eax
        mov eax,[esp+52]
        mov [esp+16],eax
        mov edx,[esp]
        mov [edx],esp
        mov ebx,11223344h
        mov esi,55667788h
        mov edi,99aabbcch
        mov ebp,0ddeeff00h
        mov ecx,0deadbeefh
        push dword ptr [esp+16]
        push dword ptr [esp+16]
        push dword ptr [esp+16]
        push dword ptr [esp+16]
        call LD2_NamePair
        mov edx,[esp]
        mov [edx+4],esp
        mov [edx+8],ebx
        mov [edx+12],esi
        mov [edx+16],edi
        mov [edx+20],ebp
        pushfd
        pop eax
        mov [edx+24],eax
        add esp,20
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    }
}
struct Guard {~Guard(){++active->cleanup;}};
struct Fixture {
    Context context;
    MockCdc cdc;
    LD2Word table[24];
    unsigned char record[216],before[216];
    Fixture(const char* name):context{},cdc(reinterpret_cast<void*>(0x76543210)) {
        active=&context;context.table=table;context.hdc=cdc.hdc;context.alternate=AlternateTarget();
        const LD2Word* original=*reinterpret_cast<const LD2Word* const*>(&cdc);
        std::memcpy(table,original,sizeof(table));CHECK(table[23]==LD2_ExpectedTextOutA);
        *reinterpret_cast<LD2Word**>(&cdc)=table;
        CHECK(reinterpret_cast<const unsigned char*>(&cdc.hdc)-reinterpret_cast<const unsigned char*>(&cdc)==4);
        std::memset(record,0xa5,sizeof(record));const std::size_t n=std::strlen(name);CHECK(n<64);
        std::memcpy(record+4,name,n+1);std::memcpy(before,record,sizeof(record));
    }
    const char* text()const{return reinterpret_cast<const char*>(record+4);}
    void probe(int n,int id,const char* supplied=nullptr,bool use_null=false) {
        Snapshot s={};ProbeFour(reinterpret_cast<LD2Cdc*>(&cdc),use_null?nullptr:(supplied?supplied:text()),n,id,&s);
        CHECK(s.before==s.after);CHECK(s.ebx==0x11223344 && s.esi==0x55667788 && s.edi==0x99aabbcc && s.ebp==0xddeeff00);
        CHECK((s.flags&0x400)==0);unchanged();
    }
    void unchanged()const {CHECK(cdc.hdc==context.hdc);CHECK(std::memcmp(record,before,sizeof(record))==0);}
    void pair(int first,int second)const {
        CHECK(context.total==2);CHECK(context.calls[0].kind==first && context.calls[1].kind==second);
        CHECK(context.calls[0].x==57 && context.calls[1].x==56 && context.calls[0].y==21 && context.calls[1].y==21);
        if(first==3 && second==3)CHECK(context.calls[0].pointer==context.calls[1].pointer);
    }
};
static void Known(const char* name,int id,int units) {
    ++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f(name);f.probe(static_cast<int>(std::strlen(name)),id);f.pair(3,3);
    CHECK(f.context.calls[0].count==units && f.context.calls[1].count==units);
    const MockRow4* expected=nullptr;
    for(int i=0;i<ROW_COUNT;++i)
        if(ROWS[i].kind==LD2C4_FULL_ID && ROWS[i].id==id && std::strcmp(ROWS[i].ansi,name)==0)expected=&ROWS[i];
    CHECK(expected!=nullptr);
    if(expected) {
        CHECK(std::memcmp(f.context.calls[0].wide,expected->wide,static_cast<std::size_t>(units)*2)==0);
        CHECK(std::memcmp(f.context.calls[1].wide,expected->wide,static_cast<std::size_t>(units)*2)==0);
    }
}
static void Fallback(const char* name,int n,int id) {
    ++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f(name);f.probe(n,id);f.pair(1,1);
    CHECK(f.context.calls[0].pointer==f.text() && f.context.calls[1].pointer==f.text());
    CHECK(f.context.calls[0].count==n && f.context.calls[1].count==n);
}
int main() {
    std::setvbuf(stdout,nullptr,_IONBF,0);
    std::setvbuf(stderr,nullptr,_IONBF,0);
    std::fputs("STAGE main-enter\n",stderr);
    static_assert(sizeof(void*)==4 && sizeof(LD2Wide)==2,"x86 UTF16");
    for(auto& x:W_X)x=120;
    LD2_CatalogBytes=BuildV4(ROWS,ROW_COUNT,LD2_Catalog,sizeof LD2_Catalog);
    CHECK(LD2_CatalogBytes>0);
    Known("CANONICAL +10",136,9);Known("VARIANT",136,5);Known("PAIR",7,3);Known("MAX",8,256);
    Fallback("CUSTOM",6,136);Fallback("CANONICAL +10",13,99);Fallback("CANONICAL +10",12,136);
    Fallback("CANONICAL +10",0,136);Fallback("CANONICAL +10",-1,136);Fallback("CANONICAL +10",65,136);
    Fallback("DUP",3,14);Fallback("EMPTY",5,9);Fallback("BADNUL",6,10);Fallback("HIGH",4,11);
    Fallback("LOW",3,12);Fallback("LONG",4,13);
    Fallback("BADTERM",7,15);Fallback("ANYROW",6,77);Fallback("ANYROW",6,-1);Fallback("JOIN",4,5);Fallback("JOIN",4,-1);
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);const LD2Word keep=LD2_CatalogBytes;
        LD2_Catalog[4]^=1;Fallback("CANONICAL +10",13,136);LD2_Catalog[4]^=1;
        LD2_CatalogBytes=keep+1;Fallback("CANONICAL +10",13,136);LD2_CatalogBytes=0;Fallback("VARIANT",7,136);
        LD2_CatalogBytes=keep;Known("VARIANT",136,5);}
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CUSTOM");f.probe(3,136,nullptr,true);f.pair(1,1);CHECK(f.context.calls[0].pointer==nullptr);}
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CANONICAL +10");f.table[23]=f.context.alternate;f.probe(13,136);f.pair(2,2);}
    for(Mode mode:{FalseFirst,FalseSecond}) {
        ++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CANONICAL +10");f.context.mode=mode;f.probe(13,136);f.pair(3,3);
    }
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CUSTOM");f.context.mode=SwapLegacy;f.probe(6,136);f.pair(1,2);}
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CANONICAL +10");f.context.mode=SwapWide;f.probe(13,136);f.pair(3,2);CHECK(f.context.calls[1].pointer==f.text());}
    for(Mode mode:{ThrowLegacy,ThrowWide}) for(int at=1;at<=2;++at) {
        ++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f(mode==ThrowLegacy?"CUSTOM":"CANONICAL +10");f.context.mode=mode;f.context.throw_at=at;bool caught=false;
        try {Guard guard;LD2_NamePair(reinterpret_cast<LD2Cdc*>(&f.cdc),f.text(),mode==ThrowLegacy?6:13,136);CHECK(false);}
        catch(int value){caught=true;CHECK(value==700+at);}
        CHECK(caught && f.context.cleanup==1 && f.context.total==at);f.unchanged();
        CHECK(f.context.calls[0].kind==(mode==ThrowLegacy?1:3));
    }
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);Fixture f("CANONICAL +10");f.context.mode=LateThrow;bool caught=false;
        try {Guard guard;LD2_NamePair(reinterpret_cast<LD2Cdc*>(&f.cdc),f.text(),13,136);CHECK(false);}
        catch(int value){caught=true;CHECK(value==702);}
        CHECK(caught && f.context.cleanup==1);f.pair(3,2);f.unchanged();}
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);struct Bounds {LD2Word left;LD2Wide text[257];LD2Word right;} box;
        for(int row=0;row<ROW_COUNT;++row) {
            box.left=0x11223344;box.right=0x55667788;for(auto& x:box.text)x=0x7777;
            const int len=static_cast<int>(std::strlen(ROWS[row].ansi));
            int n=LD2_FindCopy(ROWS[row].id,ROWS[row].ansi,len,box.text);
            // v4: both KRIS rows probe with their own id; id -1 (female row) still resolves to the unique
            // item row because flags 0 consult full_id only (NamePair never passes -1 in the game).
            const bool kris=std::strcmp(ROWS[row].ansi,"KRIS")==0;
            const MockRow4& want=kris?ROWS[ROW_COUNT-2]:ROWS[row];
            const bool valid=row<4 || kris;
            CHECK((n>0)==valid);CHECK(box.left==0x11223344 && box.right==0x55667788);
            if(n>0) {CHECK(n==static_cast<int>(want.units));CHECK(box.text[n]==0);
                CHECK(std::memcmp(box.text,want.wide,static_cast<std::size_t>(n)*2)==0);
                LD2_Wipe(box.text,n);for(int i=0;i<=n;++i)CHECK(box.text[i]==0);}
            else for(const auto x:box.text)CHECK(x==0x7777 || x==0);
            CHECK(box.left==0x11223344 && box.right==0x55667788);
        }
        CHECK(LD2_FindCopy(136,nullptr,13,box.text)==0);CHECK(LD2_FindCopy(136,"CANONICAL +10",13,nullptr)==0);
        CHECK(LD2_FindCopy(136,"CANONICAL +10",65,box.text)==0);CHECK(LD2_FindCopy(136,"CANONICAL +10",0,box.text)==0);}
    // ---- m063c v4-only cases (flags 0 = item_by_id)
    Known("KRIS",28,4);Fallback("KRIS",4,29);   // female row with same bytes never used (flags 0)
    {++cases;std::fprintf(stderr,"CASE %d line %d\n",cases,__LINE__);unsigned char keep[16384];const LD2Word kb=LD2_CatalogBytes;
        std::memcpy(keep,LD2_Catalog,kb);
        LD2_CatalogBytes=BuildV4(ROWS,ROW_COUNT,LD2_Catalog,sizeof LD2_Catalog,3);CHECK(LD2_CatalogBytes>0);
        Fallback("CANONICAL +10",13,136);Fallback("KRIS",4,28);                     // v3 header refused
        static const MockRow4 BADREG[]={{LD2C4_FULL_ID,136,"VARIANT",W_VAR,5,5,0,2}};
        LD2_CatalogBytes=BuildV4(BADREG,1,LD2_Catalog,sizeof LD2_Catalog);CHECK(LD2_CatalogBytes>0);
        Fallback("VARIANT",7,136);                                                  // full row with region tag = corrupt
        std::memcpy(LD2_Catalog,keep,kb);LD2_CatalogBytes=kb;Known("VARIANT",136,5);}
    std::fputs("STAGE normal-abi-loop\n",stderr);
    for(int i=0;i<1000;++i) {++iterations;Fixture f("CANONICAL +10");f.probe(13,136);f.pair(3,3);}
    std::printf("{\"cases\":%d,\"assertions\":%d,\"failed\":%d,\"normal_abi_iterations\":%d,\"pointer_bytes\":%u,\"wide_bytes\":%u,\"four_parameter_helper\":true,\"flags\":0,\"catalog_version\":4,\"game_or_gdi_called\":false}\n",
        cases,checks,failed,iterations,static_cast<unsigned>(sizeof(void*)),static_cast<unsigned>(sizeof(LD2Wide)));
    return failed?1:0;
}
