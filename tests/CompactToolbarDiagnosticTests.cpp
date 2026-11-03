#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include "../runtime/MajestyBuildId.h"
#include "../runtime/ControllerLifecycleRegistry.h"
// Same production registry, in this TU solely to replace its retained native
// destructor with a fixture stub. No instructions from the game are executed.
#include "../runtime/ControllerLifecycleRegistry.cpp"
#define CAM_COMPACT_TOOLBAR_DIAGNOSTIC 1
using ControllerSetup=void (__thiscall*)(void*);
using ControllerEvent=void (__thiscall*)(void*,unsigned,unsigned,unsigned,unsigned);
struct Profile { MajestyBuildId buildId;const char* id; };
Profile profile{MajestyBuildId::SteamPublic,"fixture"};
Profile* g_buildProfile=&profile;
std::uintptr_t g_imageBase=0;
std::vector<std::string> logs;
void WriteLog(const char* s){logs.emplace_back(s);}
ULONGLONG tick=1000;
ULONGLONG FixtureTick(){return tick;}
#define GetTickCount64 FixtureTick
#include "../runtime/CompactToolbarDiagnostic.inl"
#undef GetTickCount64
unsigned setups=0,events=0,last[4]{};
unsigned destructors=0,lastFlags=0;
void* __fastcall Destroy(void* object,void*,unsigned flags){++destructors;lastFlags=flags;return object;}
void __fastcall Setup(void*,void*){++setups;}
void __fastcall Event(void*,void*,unsigned a,unsigned b,unsigned c,unsigned d){
    ++events;last[0]=a;last[1]=b;last[2]=c;last[3]=d;
}
int main(int argc,char** argv){
    assert(argc==3);unsigned index=static_cast<unsigned>(std::stoi(argv[2]));assert(index<3);
    profile.buildId=static_cast<MajestyBuildId>(index);
    std::ifstream file(argv[1],std::ios::binary);
    std::vector<unsigned char> data((std::istreambuf_iterator<char>(file)),{});
    assert(data.size()>64);
    auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(data.data()+reinterpret_cast<const IMAGE_DOS_HEADER*>(data.data())->e_lfanew);
    std::vector<unsigned char> image(nt->OptionalHeader.SizeOfImage);
    g_imageBase=reinterpret_cast<std::uintptr_t>(image.data());
    const auto* sections=IMAGE_FIRST_SECTION(nt);
    for(unsigned i=0;i<nt->FileHeader.NumberOfSections;++i){
        assert(sections[i].PointerToRawData+sections[i].SizeOfRawData<=data.size());
        std::memcpy(image.data()+sections[i].VirtualAddress,data.data()+sections[i].PointerToRawData,sections[i].SizeOfRawData);
    }
    const auto& p=MajestyCompactDiagnostic::profiles[index];
    auto** stock=reinterpret_cast<void**>(g_imageBase+p.table);
    for(unsigned i=0;i<9;++i){
        assert(reinterpret_cast<std::uintptr_t>(stock[i])==0x400000+p.slots[i]);
        stock[i]=reinterpret_cast<void*>(g_imageBase+p.slots[i]);
    }
    void** object=stock;
    const auto address=static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&object));
    image[p.slots[8]]^=1;CaptureCompactDiagnostic(address);
    assert(object==stock&&g_compactController==0&&logs.back().find("code-guard")!=std::string::npos);
    CaptureCompactDiagnostic(address);assert(logs.size()==1); // failure is also bounded
    image[p.slots[8]]^=1;logs.clear();g_compactRejected=false;CaptureCompactDiagnostic(address);
    assert(object==g_compactTable&&g_compactController==static_cast<LONG>(address));
    // Never execute fixture-native instructions. Substitute only captured stock
    // callbacks, then exercise the real diagnostic wrappers and budget.
    g_compactStockSetup=reinterpret_cast<ControllerSetup>(&Setup);
    g_compactStockEvent=reinterpret_cast<ControllerEvent>(&Event);
    CompactDiagnosticSetup(&object,nullptr);CompactDiagnosticSetup(&object,nullptr);
    assert(setups==2&&logs.size()==1&&logs[0].find("ARMED")!=std::string::npos);
    for(unsigned i=0;i<1000;++i)CompactDiagnosticEvent(&object,nullptr,1,0,MajestyCompactDiagnostic::kClock,99);
    assert(events==1000&&logs.size()==1);
    MajestyControllerLifecycle::g_registrations->stockDestructor=
        reinterpret_cast<MajestyControllerLifecycle::StockControllerDestructor>(&Destroy);
    using Delete=void* (__thiscall*)(void*,unsigned);
    auto destructor=reinterpret_cast<Delete>(g_compactTable[0]);
    tick+=62;assert(destructor(&object,1)==&object);
    assert(destructors==1&&lastFlags==1&&g_compactController==0&&!g_compactBudget.stopped);
    assert(logs.back().find("DETACHED")!=std::string::npos);
    void** replacement=stock;
    tick+=2;CaptureCompactDiagnostic(static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(&replacement)));
    assert(replacement==g_compactTable&&g_compactTable[0]==reinterpret_cast<void*>(destructor));
    CompactDiagnosticSetup(&replacement,nullptr);
    assert(g_compactBudget.start==1000&&logs.back().find("ATTACHED")!=std::string::npos);
    auto beforeStale=logs.size();destructor(&object,7);
    assert(destructors==2&&lastFlags==7&&logs.size()==beforeStale&&g_compactSetupReady);
    tick=21000;CompactDiagnosticEvent(&replacement,nullptr,77,1,0x02435358,22);
    assert(events==1001&&last[0]==77&&last[3]==22&&logs.back().find("stock_refresh=1")!=std::string::npos);
    tick=121000;CompactDiagnosticEvent(&replacement,nullptr,1,0,MajestyCompactDiagnostic::kClock,0);
    assert(g_compactBudget.stopped&&logs.back().find("time-limit")!=std::string::npos);
    auto count=logs.size();destructor(&replacement,2);CompactDiagnosticSetup(&object,nullptr);
    assert(logs.size()==count);
    void** late=stock;CaptureCompactDiagnostic(static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(&late)));
    assert(late==stock&&logs.size()==count);
    MajestyCompactDiagnostic::Budget budget;assert(budget.Arm(0));
    for(unsigned i=0;i<254;++i)assert(budget.Event(1,7));
    assert(!budget.Event(1,7)&&budget.Stop()&&budget.records==256&&!budget.Stop()&&!budget.Arm(2));
    CompactDiagnosticEvent(reinterpret_cast<void*>(1),nullptr,1,2,3,4);
    assert(logs.size()==count);
}
