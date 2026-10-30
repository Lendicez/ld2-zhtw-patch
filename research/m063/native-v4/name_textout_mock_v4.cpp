#define _CRT_SECURE_NO_WARNINGS
// m063c mock harness for LD2_NameTextOut v4 (logic + i386 ABI only, NOT the MSVC object).
// Port of research/m062/native-m063/name_textout_mock_v3.cpp over a runtime v4 blob, plus v4
// cases: NAME_ONLY (item full_id rows never shown at a name site: Kris / 戟斧 shapes),
// same-region joins only (cross-region false split fixed), version / region-tag fail-closed.
// Synthetic ASCII rows only; never opens the game or GDI.
// Linux: python -m ziglang c++ -target x86-linux-musl -fms-extensions -fasm-blocks -D_M_IX86=600 \
//          name_textout_v4.cpp name_textout_mock_v4.cpp -o mock
// Expected last line: JSON with "failed":0 and "game_or_gdi_called":false.
#include "name_textout_v4.h"
#include "v4_mock_blob.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>

struct Capture {int kind,x,y,count;const void* pointer;LD2Wide wide[257];};
enum Mode {Plain,ReturnFalse,ThrowLegacy,ThrowWide};
struct Context {Capture calls[4];int total;Mode mode;void* hdc;};
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
    __declspec(noinline) virtual int __thiscall Text(int,int,const char*,int);  // slot 23 = +0x5c
    __declspec(noinline) int __thiscall Alternate(int,int,const char*,int);
};
static int Record(MockCdc* r,int kind,int x,int y,const void* p,int n,const LD2Wide* w) {
    Context& c=*active;CHECK(r==nullptr || r->hdc==c.hdc);CHECK(c.total<4);
    const int i=c.total++;if(i>=4)return 0;
    Capture& v=c.calls[i];v.kind=kind;v.x=x;v.y=y;v.count=n;v.pointer=p;
    if(w && n>0 && n<=256){std::memcpy(v.wide,w,static_cast<std::size_t>(n)*2);CHECK(w[n]==0);}
    if((c.mode==ThrowLegacy && kind!=3)||(c.mode==ThrowWide && kind==3))throw 900+kind;
    return c.mode==ReturnFalse?0:(kind==3?77:55);
}
int __thiscall MockCdc::Text(int x,int y,const char* s,int n){return Record(this,1,x,y,s,n,nullptr);}
int __thiscall MockCdc::Alternate(int x,int y,const char* s,int n){return Record(this,2,x,y,s,n,nullptr);}
static __declspec(noinline) int __stdcall FakeWide(void* hdc,int x,int y,const LD2Wide* t,int u) {
    CHECK(hdc==active->hdc);CHECK(0<u && u<=256);
    const std::uintptr_t p=reinterpret_cast<std::uintptr_t>(t),b=reinterpret_cast<std::uintptr_t>(LD2_Catalog);
    CHECK(p<b || p>=b+LD2_CatalogBytes);
    return Record(nullptr,3,x,y,t,u,t);
}
static LD2Word ExpectedTarget(){MockCdc o;return (*reinterpret_cast<const LD2Word* const*>(&o))[23];}
static LD2Word AlternateTarget(){int (__thiscall MockCdc::*m)(int,int,const char*,int)=&MockCdc::Alternate;LD2Word v=0;std::memcpy(&v,&m,4);return v;}
extern "C" {
    const LD2Word LD2_ExpectedTextOutA=ExpectedTarget();
    const LD2WideMethod LD2_TextOutW=&FakeWide;
    LD2Word LD2_CatalogBytes=0;
    unsigned char LD2_Catalog[16384];
}
static const LD2Wide W_ANY[]={0x611b,0x8389},W_P[]={0x963f},W_S[]={0x70c8,0x723e},W_P2[]={0x5c0f},W_S2[]={0x660e},
    W_ITEM[]={0x9304,0x6a94},W_D1[]={0x7532},W_D2[]={0x4e59},W_HIGH[]={0xd800},W_CTL[]={0x41,0x1f};
static const LD2Wide W_KRIS_F[]={0x514b,0x8389,0x7d72},W_KRIS_I[]={0x6ce2,0x5203,0x77ed,0x528d},
    W_HALB_I[]={0x621f,0x65a7},W_HA[]={0x54c8},W_LB[]={0x723e,0x5e03},W_XA[]={0x514b},W_XB[]={0x6069},W_XC[]={0x514b,0x6069},
    W_XD[]={0x591a};
// Region tags: 1 western, 2 arabic, 3 chinese, 4 japanese (catalog_v4.REGION_TAGS).
static const MockRow4 ROWS[]={
    {LD2C4_FULL_ANY,-1,"ANNA",W_ANY,2,2,0,0},       // female: whole string
    {LD2C4_PREFIX,-1,"JO",W_P,1,1,0,1},              // male: JO+HN joins (western)
    {LD2C4_SUFFIX,-1,"HN",W_S,2,2,0,1},
    {LD2C4_PREFIX,-1,"K",W_P2,1,1,0,1},              // second split of KEN would disagree (same region)
    {LD2C4_SUFFIX,-1,"EN",W_S2,1,1,0,1},
    {LD2C4_PREFIX,-1,"KE",W_P,1,1,0,1},
    {LD2C4_SUFFIX,-1,"N",W_S,2,2,0,1},
    {LD2C4_FULL_ID,136,"SWORD",W_ITEM,2,2,0,0},      // item only: a NAME_ONLY site never shows it
    {LD2C4_FULL_ID,14,"DUP",W_D1,1,1,0,0},
    {LD2C4_FULL_ID,15,"DUP",W_D2,1,1,0,0},
    {LD2C4_FULL_ANY,-1,"HIGH",W_HIGH,1,1,0,0},       // lone surrogate: reject
    {LD2C4_FULL_ANY,-1,"CTL",W_CTL,2,2,0,0},         // control unit: reject
    // Kris shape: item (extended 28 analogue) and female name share bytes -> name site = female.
    {LD2C4_FULL_ID,28,"KRIS",W_KRIS_I,4,4,0,0},
    {LD2C4_FULL_ANY,-1,"KRIS",W_KRIS_F,3,3,0,0},
    // 戟斧 shape: arabic join HA+LB equals an item name -> name site = the join.
    {LD2C4_FULL_ID,69,"HALB",W_HALB_I,2,2,0,0},
    {LD2C4_PREFIX,-1,"HA",W_HA,1,1,0,2},
    {LD2C4_SUFFIX,-1,"LB",W_LB,2,2,0,2},
    // false split shape: XQZ = X+QZ (chinese) is real; XQ+Z mixes japanese prefix + chinese suffix.
    {LD2C4_PREFIX,-1,"X",W_XA,1,1,0,3},
    {LD2C4_SUFFIX,-1,"QZ",W_XB,1,1,0,3},
    {LD2C4_PREFIX,-1,"XQ",W_XC,2,2,0,4},
    {LD2C4_SUFFIX,-1,"Z",W_XD,1,1,0,3},
    // cross-region only: prefix western + suffix arabic never joins.
    {LD2C4_PREFIX,-1,"MO",W_P,1,1,0,1},
    {LD2C4_SUFFIX,-1,"RE",W_S,2,2,0,2},
};
static const int ROW_COUNT=static_cast<int>(sizeof ROWS/sizeof ROWS[0]);
struct Snapshot {LD2Word before,after,ebx,esi,edi,ebp,eax;};
// Emulates the patched site: ECX=cdc, EDX=helper address, four DWORDs pushed (n,s,y,x), call.
extern "C" __declspec(naked) void __cdecl ProbeSite(LD2Cdc*,int,int,const char*,int,Snapshot*) {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        mov eax,[esp+40]
        mov [eax],esp
        push dword ptr [esp+36]
        push dword ptr [esp+36]
        push dword ptr [esp+36]
        push dword ptr [esp+36]
        mov ecx,[esp+36]
        mov ebx,11223344h
        mov esi,55667788h
        mov edi,99aabbcch
        mov ebp,0ddeeff00h
        mov edx,offset LD2_NameTextOut
        call edx
        mov edx,[esp+40]
        mov [edx+4],esp
        mov [edx+8],ebx
        mov [edx+12],esi
        mov [edx+16],edi
        mov [edx+20],ebp
        mov [edx+24],eax
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    }
}
struct Fixture {
    Context context;MockCdc cdc;LD2Word table[24];char text[80],before[80];
    Fixture(const char* s):context{},cdc(reinterpret_cast<void*>(0x76543210)){
        active=&context;context.hdc=cdc.hdc;
        std::memcpy(table,*reinterpret_cast<const LD2Word* const*>(&cdc),sizeof(table));CHECK(table[23]==LD2_ExpectedTextOutA);
        *reinterpret_cast<LD2Word**>(&cdc)=table;
        std::memset(text,0x5a,sizeof text);const std::size_t n=std::strlen(s);CHECK(n+1u<=sizeof text);std::memcpy(text,s,n+1u);std::memcpy(before,text,sizeof text);
    }
    int probe(int x,int y,int n,const char* p=nullptr,bool null=false){
        Snapshot s={};ProbeSite(reinterpret_cast<LD2Cdc*>(&cdc),x,y,null?nullptr:(p?p:text),n,&s);
        CHECK(s.before==s.after);CHECK(s.ebx==0x11223344 && s.esi==0x55667788 && s.edi==0x99aabbcc && s.ebp==0xddeeff00);
        CHECK(std::memcmp(text,before,sizeof text)==0);CHECK(cdc.hdc==context.hdc);
        return static_cast<int>(s.eax);
    }
};
static void Hit(const char* s,const LD2Wide* w,int units,int x,int y) {
    ++cases;Fixture f(s);int r=f.probe(x,y,static_cast<int>(std::strlen(s)));
    CHECK(r==77);CHECK(f.context.total==1);CHECK(f.context.calls[0].kind==3);
    CHECK(f.context.calls[0].x==x && f.context.calls[0].y==y && f.context.calls[0].count==units);
    CHECK(std::memcmp(f.context.calls[0].wide,w,static_cast<std::size_t>(units)*2)==0);
}
static void Miss(const char* s,int n,int x,int y) {
    ++cases;Fixture f(s);int r=f.probe(x,y,n);
    CHECK(r==55);CHECK(f.context.total==1);CHECK(f.context.calls[0].kind==1);
    CHECK(f.context.calls[0].x==x && f.context.calls[0].y==y && f.context.calls[0].count==n && f.context.calls[0].pointer==f.text);
}
int main() {
    std::setvbuf(stdout,nullptr,_IONBF,0);
    LD2_CatalogBytes=BuildV4(ROWS,ROW_COUNT,LD2_Catalog,sizeof LD2_Catalog);CHECK(LD2_CatalogBytes>0);
    // Coordinates of the static plan sites (0x438910 party panel, 0x4b92d0, 0x4d77a0 footer).
    Hit("ANNA",W_ANY,2,12,233);Hit("ANNA",W_ANY,2,11,232);Miss("SWORD",5,13,9);   // v3 showed the unique item text; v4 NAME_ONLY never does
    {static const LD2Wide J[]={0x963f,0x70c8,0x723e};Hit("JOHN",J,3,284,233);}
    Miss("KEN",3,12,263);          // splits K+EN and KE+N disagree
    Miss("DUP",3,10,232);   // item rows are not consulted at all
Miss("HIGH",4,13,235);Miss("CTL",3,13,235);
    Miss("ANNA",3,12,233);Miss("ANNA",5,12,233);  // count is honoured, never strlen
    Miss("CUSTOM",6,12,233);Miss("ANNA",0,12,233);Miss("ANNA",-1,12,233);Miss("ANNA",65,12,233);
    {++cases;Fixture f("ANNA");int r=f.probe(1,2,4,nullptr,true);CHECK(r==55 && f.context.calls[0].kind==1 && f.context.calls[0].pointer==nullptr);}
    {++cases;Fixture f("ANNA");f.table[23]=AlternateTarget();int r=f.probe(1,2,4);CHECK(r==55 && f.context.total==1 && f.context.calls[0].kind==2);}
    {++cases;Fixture f("ANNA");f.context.mode=ReturnFalse;CHECK(f.probe(1,2,4)==0);CHECK(f.context.calls[0].kind==3);}
    {++cases;Fixture f("CUSTOM");f.context.mode=ReturnFalse;CHECK(f.probe(1,2,6)==0);CHECK(f.context.calls[0].kind==1);}
    {++cases;const LD2Word keep=LD2_CatalogBytes;LD2_Catalog[4]^=1;Miss("ANNA",4,1,2);LD2_Catalog[4]^=1;
        LD2_CatalogBytes=0;Miss("ANNA",4,1,2);LD2_CatalogBytes=keep;Hit("ANNA",W_ANY,2,1,2);}
    for(Mode m:{ThrowLegacy,ThrowWide}){++cases;Fixture f(m==ThrowLegacy?"CUSTOM":"ANNA");f.context.mode=m;bool caught=false;
        try{LD2_NameTextOut(reinterpret_cast<LD2Cdc*>(&f.cdc),0,3,4,f.text,m==ThrowLegacy?6:4);CHECK(false);}
        catch(int v){caught=true;CHECK(v==(m==ThrowLegacy?901:903));}
        CHECK(caught && f.context.total==1);}
    {++cases;LD2Wide box[259];for(auto& v:box)v=0x7777;
        CHECK(LD2N_FindCopy("ANNA",4,box+1)==2);CHECK(box[0]==0x7777 && box[3]==0 && box[258]==0x7777);
        LD2N_Wipe(box+1,2);CHECK(box[1]==0 && box[2]==0 && box[3]==0);
        CHECK(LD2N_FindCopy(nullptr,4,box)==0);CHECK(LD2N_FindCopy("ANNA",4,nullptr)==0);}
    // ---- m063c v4-only cases
    {static const LD2Wide J[]={0x514b,0x8389,0x7d72};Hit("KRIS",J,3,12,233);}              // female, not the item
    {static const LD2Wide J[]={0x54c8,0x723e,0x5e03};Hit("HALB",J,3,12,233);}              // join, not the item
    {static const LD2Wide J[]={0x514b,0x6069};Hit("XQZ",J,2,12,233);}                      // only the same-region split counts
    Miss("MORE",4,12,233);                                                                 // cross-region halves never join
    {++cases;unsigned char keep[16384];const LD2Word kb=LD2_CatalogBytes;std::memcpy(keep,LD2_Catalog,kb);
        LD2_CatalogBytes=BuildV4(ROWS,ROW_COUNT,LD2_Catalog,sizeof LD2_Catalog,3);CHECK(LD2_CatalogBytes>0);
        Miss("ANNA",4,1,2);Miss("JOHN",4,1,2);                                             // v3 header refused
        static const MockRow4 BADREG[]={{LD2C4_FULL_ANY,-1,"ANNA",W_ANY,2,2,0,1},{LD2C4_PREFIX,-1,"JO",W_P,1,1,0,0},
                                        {LD2C4_SUFFIX,-1,"HN",W_S,2,2,0,1}};
        LD2_CatalogBytes=BuildV4(BADREG,3,LD2_Catalog,sizeof LD2_Catalog);CHECK(LD2_CatalogBytes>0);
        Miss("ANNA",4,1,2);Miss("JOHN",4,1,2);                                             // region tag corrupt
        static const MockRow4 BADREG5[]={{LD2C4_PREFIX,-1,"JO",W_P,1,1,0,5},{LD2C4_SUFFIX,-1,"HN",W_S,2,2,0,5}};
        LD2_CatalogBytes=BuildV4(BADREG5,2,LD2_Catalog,sizeof LD2_Catalog);CHECK(LD2_CatalogBytes>0);
        Miss("JOHN",4,1,2);
        std::memcpy(LD2_Catalog,keep,kb);LD2_CatalogBytes=kb;Hit("ANNA",W_ANY,2,1,2);}
    for(int i=0;i<1000;++i){++iterations;Fixture f("JOHN");CHECK(f.probe(i,i+1,4)==77);}
    std::printf("{\"cases\":%d,\"assertions\":%d,\"failed\":%d,\"normal_abi_iterations\":%d,\"entry\":\"@LD2_NameTextOut@24\",\"flags\":\"ALLOW_ANY|ALLOW_JOIN|NAME_ONLY\",\"catalog_version\":4,\"game_or_gdi_called\":false}\n",
        cases,checks,failed,iterations);
    return failed?1:0;
}
