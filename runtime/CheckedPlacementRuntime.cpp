#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <string>
#include <vector>
#include <cstring>
#include "CheckedPlacementRuntime.h"
#include "CheckedPlacementNative.h"
#include "CheckedCastWindows.h"
#include "CheckedRelocation.h"
#include "AttackObservationShared.h"
#include "AuditedBeta2.h"
#include "CheckedPlacementProof.h"
#include "CheckedPlacementBindingProfiles.h"
#include "AttackObservationNativeProfiles.h"
#include "TravelCastAdmission.h"
#include "PlacementDiagnosticBudget.h"
#include <cstdio>
namespace {
using namespace MajestyCheckedPlacement;
using namespace MajestyAttackObservation;
PlacementProof config;
bool prepared{},installed{};
MajestyBuildId preparedBuild{}; // used only after successful PrepareRuntime
StateServices services;
Word buildingAttributeReplacement{};
const PlacementStateProfile* replacementProfile{};
const PlacementQueryProfile* queries{};
const PlacementBindingProfile* bindings{};
const ObservationNativeProfile* observation{};
const PlacementStateProfile* stateProfile{};
void DiagnosticActor(Word actor,unsigned reason,const char* message) {
#if defined(CAM_PLACEMENT_DIAGNOSTIC)
    static DiagnosticBudget budget;
    if(budget.emitted>=96)return;
    if(!budget.Take(actor,reason))return;
    char line[256]{};
    _snprintf_s(line,sizeof(line),_TRUNCATE,"placement-diagnostic actor=0x%08X reason=%u %s",actor,reason,message);
    SharedDiagnosticLine(line);
#else
    (void)actor;(void)reason;(void)message;
#endif
}
void Diagnostic(void* args,unsigned reason,const char* message) {
    DiagnosticActor(SharedAgent(args,1),reason,message);
}
template<class T> bool Read(Word p,unsigned offset,T& out) {
    return p&&p<=UINT32_MAX-offset&&sizeof(T)<=UINT32_MAX-p-offset&&SharedMemory().Read(p+offset,&out,sizeof(out));
}
Word Find(Word global,const std::string& name) {
    Word catalog{};if(!observation||!Read(global,0,catalog)||!catalog)return 0;
    return reinterpret_cast<Word (__thiscall*)(void*,const char*)>(observation->findName)(reinterpret_cast<void*>(catalog),name.c_str());
}
Word Function(const std::string& name) {
    if(!bindings)return 0;
    const Word root=reinterpret_cast<Word (__cdecl*)()>(bindings->root)();Word registry{};
    if(!Read(root,8,registry)||!registry)return 0;
    Word nativeString[3]{};
    reinterpret_cast<void (__thiscall*)(void*,const char*)>(bindings->stringCreate)(nativeString,name.c_str());
    struct Cleanup { Word* s;Word destroy;~Cleanup(){reinterpret_cast<void (__thiscall*)(void*)>(destroy)(s);} } cleanup{nativeString,bindings->stringDestroy};
    return reinterpret_cast<Word (__thiscall*)(void*,const void*)>(bindings->functionLookup)(reinterpret_cast<void*>(registry),nativeString);
}
int Hp(Word unit) {
    Word table{},dead{};
    if(!bindings||!Read(unit,0,table)||!Read(table,0x78,dead)||
        (dead!=bindings->unitDead&&dead!=bindings->buildingDead)||
        reinterpret_cast<bool (__thiscall*)(void*)>(dead)(reinterpret_cast<void*>(unit)))return 0;
    return reinterpret_cast<int (__thiscall*)(void*,Word,int)>(bindings->attributeValue)(reinterpret_cast<void*>(unit),0x00555041,0);
}
std::uint64_t Revision(){return NativeCasts().Authorizations().Invalidation();}
bool IdentityOf(Word unit,Identity& out){return ReadIdentity(services,unit,out);}
bool Effective() {
    if(!installed||!bindings||!observation||!stateProfile)return false;
    const Word actor=Find(observation->unitCatalog,config.actor),action=Find(observation->actionCatalog,config.action),callback=Function(config.callback);
    Word engine{},actionId{},projectile{},effect{},script{},flags{},cproc{};
    if(!actor||!action||!callback||!Read(action,4,actionId)||!actionId||!Read(action,0x14,engine)||
        !Read(engine,0x10,projectile)||projectile||!Read(engine,0x14,effect)||effect||
        !Read(engine,0x3C,script)||!Read(engine,0x40,flags)||flags||!Read(engine,0x44,cproc)||cproc)return false;
    std::vector<char> name(config.release.size()+1);
    if(!script||!SharedMemory().Read(script,name.data(),name.size())||name.back()||_stricmp(name.data(),config.release.c_str()))return false;
    services={&SharedMemory(),actor,&SharedCurrentIdentity,&Hp,&ObservedUnitEpoch,&Revision,
              stateProfile,replacementProfile==stateProfile?buildingAttributeReplacement:0};
    if(!ConfigureCastBindings({&SharedMemory(),&IdentityOf,&SharedFrameArgument,&SharedFrameAgent,actionId,engine,callback}))return false;
    if(config.arrival.empty())return true;
    const Word arrival=Find(observation->actionCatalog,config.arrival);Word arrivalEngine{},arrivalId{};
    if(!arrival||!Read(arrival,4,arrivalId)||!Read(arrival,0x14,arrivalEngine)) {
        ConfigureCosmeticCleanup({});return false;
    }
    return ConfigureCosmeticCleanup({&SharedMemory(),CosmeticImagesFor(preparedBuild),
        &IdentityOf,actor,arrival,arrivalEngine,arrivalId,0x42,8,config.imageId});
}
Word Proxy(void* args,unsigned index) {
    if(!bindings)return 0;
    void* value=SharedArgument(args,index);if(!value)return 0;
    using Ref=void* (__thiscall*)(void*);
    void* reference=reinterpret_cast<Ref>((*static_cast<void***>(value))[0x5C/4])(value);if(!reference)return 0;
    Word temporary[4]{};
    if(!Read(static_cast<Word>(reinterpret_cast<std::uintptr_t>(reference)),8,temporary[2]))return 0;
    return reinterpret_cast<Word (__thiscall*)(void*)>(bindings->proxy)(temporary);
}
bool Pair(void* args,Snapshot& s) {
    return Effective()&&ReadPlacement(services,SharedAgent(args,1),SharedAgent(args,2),s);
}
void __cdecl Ready(void* args) {
    int* output=SharedInteger(args,0);if(!output)return;*output=0;
    Identity actor;
    if(!Effective()){Diagnostic(args,0,"Ready: effective bindings rejected");return;}
    const char* failure="Ready: unspecified rejection";
    if(!ReadSupportedMover(services,SharedAgent(args,1),actor,&failure)){
        Diagnostic(args,1,failure);
        if(!std::strcmp(failure,"identity: shared current-identity rejected"))Diagnostic(args,17,SharedIdentityFailure());
        return;
    }
    if(!config.arrival.empty()&&!CosmeticAvailable(actor.address)){Diagnostic(args,2,"Ready: arrival presentation busy");return;}
    *output=1;Diagnostic(args,3,"Ready accepted; GPL eligibility is next");
}
void __cdecl Boundary(void* args) {
    int* output=SharedInteger(args,0);if(!output)return;
    const int* phase=SharedInteger(args,3);const int requested=phase?*phase:-1;*output=0;
    if(requested!=0&&requested!=1)return;
    Snapshot s;if(!Pair(args,s)){Diagnostic(args,4,"Boundary: pair identity/hostility/placement rejected");return;}
    if(requested==1){*output=NativeCasts().InCallback(s.actor,s.target);
        Diagnostic(args,*output?28:29,*output?"Callback: authorized":"Callback: authorization missing");return;}
    if(!SharedDecisionContext()){Diagnostic(args,5,"Boundary: decision context rejected");return;}
    if(NativeCasts().Pending(s.actor.id)){Diagnostic(args,6,"Boundary: cast already pending");return;}
    if(!TravelCastReady(SharedMemory(),s.actor.address,TravelCastFor(preparedBuild))){Diagnostic(args,7,"Boundary: order stack rejected");return;}
    *output=1;Diagnostic(args,8,"Boundary accepted");
}
void __cdecl Begin(void* args) {
    int* output=SharedInteger(args,0);if(!output)return;*output=0;
    Snapshot s;if(!Pair(args,s)){Diagnostic(args,9,"Begin: pair rejected");return;}
    if(!SharedDecisionContext()){Diagnostic(args,10,"Begin: decision context rejected");return;}
    if(NativeCasts().Pending(s.actor.id)){Diagnostic(args,11,"Begin: cast pending");return;}
    if(!TravelCastReady(SharedMemory(),s.actor.address,TravelCastFor(preparedBuild))){Diagnostic(args,12,"Begin: order stack rejected");return;}
    if(!config.arrival.empty()&&!CosmeticAvailable(s.actor.address)){Diagnostic(args,13,"Begin: arrival busy");return;}
    const Word actor=Proxy(args,1),target=Proxy(args,2);if(!actor||!target){Diagnostic(args,14,"Begin: proxy rejected");return;}
    *output=BeginObservedCast(s.actor,s.target,actor,target,config.action.c_str())?1:0;
    Diagnostic(args,*output?15:16,*output?"Begin: stock dispatch accepted":"Begin: stock dispatch rejected");
}
void __cdecl CommitMove(void* args) {
    int* output=SharedInteger(args,0);if(!output)return;*output=-1;
    if(!Effective()){Diagnostic(args,43,"Commit: effective bindings rejected");return;}*output=0;
    Snapshot s;if(!ReadPlacement(services,SharedAgent(args,1),SharedAgent(args,2),s)){Diagnostic(args,44,"Commit: placement state rejected");return;}
    if(!NativeCasts().InCallback(s.actor,s.target)){Diagnostic(args,45,"Commit: callback authorization missing");return;}
    StockPlacement native(services,*queries,s.actor.address,s.target.address);
    const char* detail="commit not entered";
    *output=Commit(NativeCasts().Authorizations(),native,config.range,&detail);
    Diagnostic(args,*output==1?30:31,detail);
    if(*output==1&&!config.arrival.empty()) {
        // Coordinate success remains success even if subsequent native work
        // retires the owner. Never replay movement or refund a completed move.
        const Word proxy=Proxy(args,1);
        const bool arrival=proxy&&BeginCosmeticAction(s.actor,proxy,config.arrival.c_str());
        Diagnostic(args,arrival?46:47,arrival?"Arrival: dispatched":"Arrival: proxy/presentation rejected");
    }
}

}
void MajestyCheckedPlacement::TracePlacementStage(Word actor,unsigned reason,const char* message) {
    DiagnosticActor(actor,reason,message);
}
bool MajestyCheckedPlacement::RegisterBuildingAttributeReplacement(MajestyBuildId build,
    Word slot,Word original,Word replacement) {
    const auto* profile=PlacementStateFor(build);Word actual{};
    if(!profile||slot!=profile->building+0x124||original!=profile->attribute||
        !replacement||replacement==original||!Read(slot,0,actual)||actual!=replacement||
        (buildingAttributeReplacement&&(replacementProfile!=profile||buildingAttributeReplacement!=replacement)))return false;
    replacementProfile=profile;buildingAttributeReplacement=replacement;return true;
}
bool MajestyCheckedPlacement::RebindPreparedWorld() {
    // Called only after the shared observer accepts the loaded/created world.
    // Restored animations need cleanup before their first GPL Ready query.
    return !prepared||Effective();
}
bool MajestyCheckedPlacement::PrepareRuntime(const wchar_t* manifest,MajestyBuildId build) {
    if(prepared||!manifest||!AuditedStartup(build))return false;
    const std::wstring path(manifest);const auto slash=path.find_last_of(L"\\/");if(slash==std::wstring::npos)return false;
    const auto proof=path.substr(0,slash+1)+L"majesty_mod_manager_checked_placement.bin";
    HANDLE file=CreateFileW(proof.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER size{};DWORD read{};
    bool ok=GetFileSizeEx(file,&size)&&size.QuadPart>=44&&size.QuadPart<=512;
    std::vector<unsigned char> bytes(ok?static_cast<std::size_t>(size.QuadPart):0);
    if(ok)ok=ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&read,nullptr)&&read==bytes.size();CloseHandle(file);
    PlacementProof next;
    if(!ok||!ParsePlacementProof(bytes.data(),bytes.size(),next)||!SharedProofMatches(next.observerDigest.data()))return false;
    config=std::move(next);preparedBuild=build;prepared=true;return true;
}
bool MajestyCheckedPlacement::InstallPreparedRuntime(RegisterProcedure registration) {
    if(!prepared)return true;
    if(!registration)return false;
    if(installed && (observation!=ObservationNativeFor(preparedBuild)||stateProfile!=PlacementStateFor(preparedBuild)))return false;
    // Re-register aliases for every stock table, but install process hooks once.
    if(!installed) {
    if(!AuditedStartup(preparedBuild))return false;
    // Startup certifies the shared observer/cast/action bodies; each remaining
    // helper below must independently match this same selected build.
    const auto* candidate=PlacementQueriesFor(preparedBuild);
    const auto* native=PlacementBindingsFor(preparedBuild);
    const auto* shared=ObservationNativeFor(preparedBuild);
    const auto* state=PlacementStateFor(preparedBuild);
    if(!native||!shared||!state||!PlacementBindingBytesMatch(*native))return false;
    if(!candidate||!PlacementQueryBytesMatch(*candidate,
        reinterpret_cast<const unsigned char*>(candidate->path),
        reinterpret_cast<const unsigned char*>(candidate->fit),
        reinterpret_cast<const unsigned char*>(candidate->seed)))return false;
    if(!InstallCastObservers(preparedBuild)||!InstallWriteBoundary(preparedBuild))return false;
    queries=candidate;
    bindings=native;observation=shared;stateProfile=state;
    installed=true;
    }
    const char* suffixes[]={"Ready","Boundary","Begin","Commit"};
    void (__cdecl* callbacks[])(void*)={&Ready,&Boundary,&Begin,&CommitMove};
    for(unsigned i=0;i<4;++i)registration((config.prefix+"_"+suffixes[i]).c_str(),callbacks[i]);
    return true;
}
