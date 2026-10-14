#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <intrin.h>
#include <atomic>
#include <cstring>
#include <cstdio>
#include <exception>
#include <string>
#include <vector>
#include "NativeImpactRuntime.h"
#include "AttackObservation.h"
#include "AttackObservationWindows.h"
#include "AttackObservationProof.h"
#include "BcdDefinitionOwnership.h"
#include "AttackObservationBaseline.h"
#include "AttackObservationContext.h"
#include "WorldAttachmentProfiles.h"
#include "AttackObservationNativeProfiles.h"
#include "BooleanRuntime.h"
#include "NativeImpactProfiles.h"
#include "NativeImpactRegistry.h"
#include "NativeImpactCompletion.h"
#include "PairedOccupantLookupProfiles.h"

namespace {
using namespace MajestyAttackObservation;
using Word=std::uint32_t;
Lifecycle life;
Profile profile;
struct ProcessMemory final: Memory {
    bool Read(Address address,void* output,std::size_t bytes) const override {
        SIZE_T copied=0;
        return address && bytes<=UINT32_MAX-address && ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<const void*>(address),output,bytes,&copied) && copied==bytes;
    }
};
ProcessMemory memory;
PackageProof packageProof;
LoadProof loadProof;
bool prepared=false;
MajestyBuildId preparedBuild{}; // used only after successful preparation
unsigned char preparedProofDigest[32]{};
bool RegisterBindings(std::uintptr_t,RegisterProcedure);
DWORD ownerThread=0;
std::atomic<bool> fault{false};
bool installed=false;
const WorldAttachmentProfile* attachmentProfile=nullptr;
const ObservationNativeProfile* nativeProfile=nullptr;
void* original[kObservationHookCount]{};
MajestyBcdOwnership::BatchOwnership batchOwnership;
bool categoryFile=false;
void* batchReceiver=nullptr;

int acceptedStatus=-1;
Word acceptedWorld=0;
void (*logger)(const char*)=nullptr;
unsigned effectiveReason=1;
void Trace(const char*,unsigned=0,unsigned=0,unsigned=0) {}
void Fault(const char*,unsigned=0,unsigned=0) { fault=true; }
template<class T> bool Read(Word p,unsigned offset,T& out) { return p && p<=UINT32_MAX-offset && memory.Read(p+offset,&out,sizeof(out)); }
template<class T> T Value(const void* p,unsigned offset) { T out{}; if (!Read(static_cast<Word>(reinterpret_cast<std::uintptr_t>(p)),offset,out)) Fault("first-fault/read",static_cast<Word>(reinterpret_cast<std::uintptr_t>(p)),offset); return out; }
bool Owner() { if (GetCurrentThreadId()!=ownerThread) { Fault("first-fault/thread",ownerThread,GetCurrentThreadId()); return false; } return true; }
struct Guard {
    bool active=Owner();
    int exceptions=std::uncaught_exceptions();
    Guard() { if (active) { life.EnterOperation(); } }
    ~Guard() { if (active) {
        const bool normal=std::uncaught_exceptions()==exceptions;
        if (!normal) { Fault("first-fault/unwind"); life.IdentityIncoherent(); }
        life.LeaveOperation();
    } }
};
bool Digest(HANDLE file,unsigned char (&digest)[32]) {
    BCRYPT_ALG_HANDLE algorithm=nullptr; BCRYPT_HASH_HANDLE hash=nullptr;
    bool ok=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0;
    if (ok) ok=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0;
    unsigned char buffer[65536]; DWORD count=0;
    while (ok) { if (!ReadFile(file,buffer,sizeof(buffer),&count,nullptr)) { ok=false; break; } if (!count) break; ok=BCryptHashData(hash,buffer,count,0)>=0; }
    if (ok) ok=BCryptFinishHash(hash,digest,32,0)>=0;
    if (hash) BCryptDestroyHash(hash); if (algorithm) BCryptCloseAlgorithmProvider(algorithm,0);
    return ok;
}
HANDLE LockNativePath(const void* nativeString) {
    const auto data=Value<Word>(nativeString,0),flags=Value<Word>(nativeString,4),length=Value<Word>(nativeString,8);
    if (!data || !length || length>32767) return INVALID_HANDLE_VALUE;
    // The stock constructor tests native-string byte+7 mask1 (bit0) and calls
    // narrow/wide open imports with that exact data pointer, not an archive VFS.
    if (flags&0x01000000) {
        std::vector<wchar_t> path(length+1);
        if (!memory.Read(data,path.data(),(length+1)*sizeof(wchar_t)) || path.back()!=0) return INVALID_HANDLE_VALUE;
        return CreateFileW(path.data(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    }
    std::vector<char> path(length+1);
    if (!memory.Read(data,path.data(),length+1) || path.back()!=0) return INVALID_HANDLE_VALUE;
    return CreateFileA(path.data(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
}
bool __stdcall Bcd(const void* filename) {
    Guard guard;
    HANDLE file=LockNativePath(filename);
    unsigned char digest[32]{};
    int index=file!=INVALID_HANDLE_VALUE && Digest(file,digest) ? packageProof.Find(digest) : -1;
    MajestyBcdOwnership::Definitions definitions;
    bool parsed=false;
    if(file!=INVALID_HANDLE_VALUE && !packageProof.protectedNames.empty()) {
        LARGE_INTEGER size{},zero{};DWORD count=0;
        if(GetFileSizeEx(file,&size)&&size.QuadPart>=4&&size.QuadPart<=64*1024*1024&&
           SetFilePointerEx(file,zero,nullptr,FILE_BEGIN)) {
            std::vector<unsigned char> bytes(static_cast<std::size_t>(size.QuadPart));
            parsed=ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&count,nullptr)&&
               count==bytes.size()&&MajestyBcdOwnership::ReadDefinitions(bytes.data(),bytes.size(),definitions);
        }
        const bool generated=index>=6&&index<(packageProof.scoped?9:7);
        const bool baseline=index>=0&&index<6;
        bool admitted=parsed;
        if(parsed && categoryFile)
            admitted=batchOwnership.Admit(definitions,packageProof.protectedNames,generated,baseline);
        else if(parsed && !baseline) {
            // Outside the reviewed batch route no earlier declaration proves
            // shadowing. Only genuinely non-overlapping optional files qualify.
            admitted=!generated;
            for(const auto& key:definitions)
                if(packageProof.protectedNames.count(MajestyBcdOwnership::Lower(key.second)))admitted=false;
        }
        if(!admitted)index=-1;
        else {
            // Trailing stock entries in this same reverse list do not replace
            // the generated winners; unchanged callbacks retain audited stock
            // owners. Classify them as admitted baseline continuations,
            // not a new baseline reload. Postload discards this evidence.
            index=batchOwnership.ContinuationIndex(index,categoryFile,loadProof.Ready(),
                                                    definitions,packageProof.protectedNames);
            if(index<0)index=-2;
        }
    }
    if (guard.active) {
        // Invalidate before native registration, not after it has changed tables.
        life.IdentityIncoherent();profile.effectivePackage=false;
        if (!loadProof.Begin(index)) Fault("first-fault/bcd-begin",static_cast<unsigned>(index));
    }
    bool result=false;
    try { result=reinterpret_cast<bool (__stdcall*)(const void*)>(original[10])(filename); }
    catch (...) { if (file!=INVALID_HANDLE_VALUE) CloseHandle(file); Fault("first-fault/bcd-exception",static_cast<unsigned>(index)); throw; }
    if (file!=INVALID_HANDLE_VALUE) CloseHandle(file);
    if (guard.active && !loadProof.Complete(index,result)) Fault("first-fault/bcd-complete",static_cast<unsigned>(index),result);
    if(guard.active && result && parsed && categoryFile && index!=-1)
        batchOwnership.Complete(definitions,packageProof.protectedNames,index>=6&&index<(packageProof.scoped?9:7));
    return result;
}
bool __fastcall BcdFilename(void* self,void*,const void* filename) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    Guard guard;
    const bool previous=categoryFile;
    categoryFile=guard.active && caller==Category1FileReturnFor(preparedBuild);
    if(categoryFile) {
        if(previous || (batchReceiver && batchReceiver!=self))Fault("first-fault/bcd-batch-reentry");
        batchReceiver=self;
    }
    struct RestoreRoute { bool previous; ~RestoreRoute(){ categoryFile=previous; } } restore{previous};
    return reinterpret_cast<bool (__thiscall*)(void*,const void*)>(original[12])(self,filename);
}
void __stdcall BeforeBcdPostload() {
    if(!Owner())return;
    // The full reverse list has now ended. Do not borrow publication evidence
    // across linking/catalog release or an unrecognized postload caller.
    batchOwnership.Reset();batchReceiver=nullptr;
    if(categoryFile)Fault("first-fault/postload-during-file");
}
__declspec(naked) void BcdPostload() {
    __asm {
        pushfd
        pushad
        call BeforeBcdPostload
        popad
        popfd
        jmp dword ptr [original + 52]
    }
}
Word Find(Word global,const char* name) {
    Word catalog=0;
    if (!Read(global,0,catalog) || !catalog) return 0;
    using FindName=void* (__thiscall*)(void*,const char*);
    return static_cast<Word>(reinterpret_cast<std::uintptr_t>(reinterpret_cast<FindName>(nativeProfile->findName)(reinterpret_cast<void*>(catalog),name)));
}
bool Callback(unsigned id,Word expected) {
    using Registry=void* (__cdecl*)(); using FindCallback=void* (__thiscall*)(void*,unsigned);
    void* registry=reinterpret_cast<Registry>(nativeProfile->callbacks)();
    if (!registry) return false;
    Word table=Value<Word>(registry,0),lookup=0;
    if (!Read(table,4,lookup) || !lookup) return false;
    return reinterpret_cast<std::uintptr_t>(reinterpret_cast<FindCallback>(lookup)(registry,id))==expected;
}
#include "NativeImpactRuntime.inl"
bool Effective() {
    effectiveReason=1;
    if (!Owner() || fault || !loadProof.Ready() || !ImpactGate()) return false;
    effectiveReason=0;
    return packageProof.actor.empty() && impactPrepared && Callback(0x100A,nativeProfile->impactCallback);
}
bool Gate() {
    profile.effectivePackage=Effective();
    static unsigned previous=~0u;
    if (previous!=effectiveReason) { Trace("effective(reason,loaded,fault)",effectiveReason,loadProof.Ready()?1u:0u,fault?1u:0u); previous=effectiveReason; }
    return profile.effectivePackage;
}
Word __fastcall Dispatch(void* self,void*,Word a,Word b,Word c) {
    Guard guard;
    struct RestoreImpact {
        TerminalMissileContext previous;
        ~RestoreImpact(){nativeImpactContext=previous;}
    } restore{nativeImpactContext};
    nativeImpactContext=guard.active&&impactPrepared?CaptureTerminalMissile(
        [](Word p,unsigned offset,Word& out){return Read(p,offset,out);},
        static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),a,c,nativeProfile->missileTable,life.Generation()):TerminalMissileContext{};
    return reinterpret_cast<Word (__thiscall*)(void*,Word,Word,Word)>(original[0])(self,a,b,c);
}
void __fastcall Unlink(void* self,void*,Word order) {
    Guard guard;
    reinterpret_cast<void (__thiscall*)(void*,Word)>(original[1])(self,order);
}
void __fastcall UnitRetire(void* self,void*) {
    Guard guard;
    const bool owner=guard.active; const Word pointer=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    Word id=0; const bool published=owner && Read(pointer,0x70,id) && id;
    RetirementToken token{};
    if (published) token=life.BeginRetirement(pointer,id); else if (owner) life.EnterOperation();
    reinterpret_cast<void (__thiscall*)(void*)>(original[2])(self);
    if (published) life.EndRetirement(token,true); else if (owner) life.LeaveOperation();
}
void __fastcall StackDestroy(void* self,void*,Word channel) {
    Guard guard;
    reinterpret_cast<void (__thiscall*)(void*,Word)>(original[3])(self,channel);
}
Word __cdecl Emit(Word world,Word unit,Word stack,Word order,Word event) {
    Guard guard;
    return reinterpret_cast<Word (__cdecl*)(Word,Word,Word,Word,Word)>(original[4])(world,unit,stack,order,event);
}
Word __fastcall Submit(void* self,void*,Word channel,Word order) {
    Guard guard;
    const Word result=reinterpret_cast<Word (__thiscall*)(void*,Word,Word)>(original[5])(self,channel,order);
    return result;
}
void __fastcall WorldDestroy(void* self,void*) {
    Guard guard;
    const bool owner=guard.active; if (owner) life.BeginWorldTeardown();
    if (owner) Trace("world-teardown");
    reinterpret_cast<void (__thiscall*)(void*)>(original[6])(self);
    if (owner) life.LeaveOperation();
}
void __fastcall Attach(void* self,void*,Word world,Word mode) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    if (Owner()) {
        life.IdentityIncoherent();
    }
    { Guard guard; reinterpret_cast<void (__thiscall*)(void*,Word,Word)>(original[7])(self,world,mode); }
    const auto route=attachmentProfile ? attachmentProfile->Classify(caller,mode,world,acceptedStatus,acceptedWorld) : AttachmentRoute::None;
    if (Owner() && route!=AttachmentRoute::None && Gate()) {
        using Catalog=void* (__thiscall*)(void*,unsigned);
        const Word catalog=static_cast<Word>(reinterpret_cast<std::uintptr_t>(reinterpret_cast<Catalog>(nativeProfile->worldCatalog)(reinterpret_cast<void*>(world),3)));
        const bool attached=route==AttachmentRoute::Saved ?
            life.Attach(memory,profile,acceptedStatus,static_cast<int>(mode),world,catalog) :
            life.AttachCreated(memory,profile,static_cast<int>(mode),world,catalog);
        Trace("attach(mode,accepted,generation)",mode,attached?1u:0u,static_cast<unsigned>(life.Generation()));
    } else life.IdentityIncoherent();
    acceptedStatus=-1; acceptedWorld=0;
}
int __fastcall Load(void* self,void*,Word filename,Word output) {
    if (Owner()) { life.IdentityIncoherent(); acceptedStatus=-1; acceptedWorld=0; }
    Guard guard;
    const int status=reinterpret_cast<int (__thiscall*)(void*,Word,Word)>(original[8])(self,filename,output);
    if (guard.active) { acceptedStatus=status; if (!Read(output,0,acceptedWorld)) acceptedWorld=0; Trace("load(status,nonnull)",static_cast<unsigned>(status),acceptedWorld?1u:0u); }
    return status;
}
Word __fastcall Spawn(void* self,void*,Word a,Word b,Word c,Word d,Word x,Word y,Word z,Word h,Word flags) {
    Guard guard;
    const auto result=reinterpret_cast<Word (__thiscall*)(void*,Word,Word,Word,Word,Word,Word,Word,Word,Word)>(original[9])(self,a,b,c,d,x,y,z,h,flags);
    // Constructor/failure-cleanup certification is explicitly paused. Do not
    // infer readiness from a failed spawn or attempt replacement cleanup.
    if (!result && guard.active) { life.IdentityIncoherent(); Trace("spawn-failed-readiness-invalidated"); }
    return result;
}
Word __fastcall Restore(void* self,void*,Word stream) {
    Guard guard;
    return reinterpret_cast<Word (__thiscall*)(void*,Word)>(original[11])(self,stream);
}
void* targets[]={reinterpret_cast<void*>(&Dispatch),reinterpret_cast<void*>(&Unlink),reinterpret_cast<void*>(&UnitRetire),reinterpret_cast<void*>(&StackDestroy),reinterpret_cast<void*>(&Emit),reinterpret_cast<void*>(&Submit),reinterpret_cast<void*>(&WorldDestroy),reinterpret_cast<void*>(&Attach),reinterpret_cast<void*>(&Load),reinterpret_cast<void*>(&Spawn),reinterpret_cast<void*>(&Bcd),reinterpret_cast<void*>(&Restore),reinterpret_cast<void*>(&BcdFilename),reinterpret_cast<void*>(&BcdPostload)};
bool Patch(const HookWindow& window,const void* target,bool restore) {
    auto* site=reinterpret_cast<unsigned char*>(window.address); DWORD previous=0;
    if (!VirtualProtect(site,window.count,PAGE_EXECUTE_READWRITE,&previous)) return false;
    if (restore) std::memcpy(site,window.bytes,window.count);
    else {
        site[0]=0xE9; const auto delta=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(target)-window.address-5);
        std::memcpy(site+1,&delta,4); std::memset(site+5,0x90,window.count-5);
    }
    FlushInstructionCache(GetCurrentProcess(),site,window.count);
    DWORD ignored=0; return VirtualProtect(site,window.count,previous,&ignored)!=0;
}
bool RegisterBindings(std::uintptr_t base,RegisterProcedure) {
    return base==0x400000 && nativeProfile && packageProof.actor.empty() && impactPrepared;
}

bool AuditedStartup(MajestyBuildId build) {
    const auto* p=ObservationNativeFor(build);
    if(!p || reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr))!=0x400000)return false;
    static bool certified=false; static MajestyBuildId certifiedBuild{};
    if(certified && certifiedBuild!=build)return false;
    if(!certified) {
        if(!MajestyBooleanRuntime::GuardBodies(ObserverBodiesFor(build),ObserverBodyCount))return false;
        certified=true; certifiedBuild=build;
    }
    Word runtime{},attached{},current{};
    return Read(p->runtimeGlobal,0,runtime) && (!runtime ||
        (Read(runtime,4,attached) && Read(runtime,0x10,current) && !attached && !current));
}
}
bool MajestyAttackObservation::PrepareRuntime(const wchar_t* manifest,MajestyBuildId build,bool interception) {
    if (prepared || !manifest || !AuditedStartup(build)) return false;
    const std::wstring path(manifest);
    const auto slash=path.find_last_of(L"\\/");
    if (slash==std::wstring::npos) return false;
    const auto proofPath=path.substr(0,slash+1)+L"majesty_mod_manager_attack_observation.bin";
    HANDLE file=CreateFileW(proofPath.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file==INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};DWORD read=0;
    bool ok=GetFileSizeEx(file,&size) && size.QuadPart>=12 && size.QuadPart<=1048576;
    std::vector<unsigned char> bytes(ok?static_cast<std::size_t>(size.QuadPart):0);
    if (ok) ok=ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&read,nullptr) && read==bytes.size();
    if(ok)ok=SetFilePointer(file,0,nullptr,FILE_BEGIN)!=INVALID_SET_FILE_POINTER&&Digest(file,preparedProofDigest);
    CloseHandle(file);
    if (!ok || !ParsePackageProof(bytes.data(),bytes.size(),packageProof)) return false;
    const unsigned char* baseline[6]{};
    for(unsigned i=0;i<6;++i)baseline[i]=packageProof.digests[i].data();
    if(!KnownBaselineBundle(baseline))return false;
    if(interception&&!PrepareImpactPolicy(manifest,build))return false;
    if(!packageProof.actor.empty() || !packageProof.apiPrefix.empty() || !impactPrepared)return false;
    loadProof=LoadProof(packageProof.scoped);
    preparedBuild=build;prepared=true;return true;
}

bool MajestyAttackObservation::InstallRuntime(std::uintptr_t base,RegisterProcedure registration,void (*writer)(const char*)) {
    logger=writer;
    if (!prepared || !registration || base!=0x400000 || !AuditedStartup(preparedBuild)) {
        Trace("registration-admission-rejected"); return false;
    }
    // Stock rebuilds its GPL registration table more than once. Hooks belong
    // to this process, callbacks to each table. Do not hash our own patched
    // entries as stock or allocate/install a second set of trampolines.
    if (installed) {
        if (fault || GetCurrentThreadId()!=ownerThread) {
            Trace("registration-state-rejected"); return false;
        }
        const bool ok=RegisterBindings(base,registration);
        if(ok)Trace("bindings-reregistered");
        return ok;
    }
    // Require the complete stock creator and its nonnull caller before
    // admitting the new-world route.
    attachmentProfile=WorldAttachmentFor(preparedBuild);
    nativeProfile=ObservationNativeFor(preparedBuild);
    const auto* hookWindows=ObservationHooksFor(preparedBuild);
    const auto guardedBody=[](Word address,unsigned size,Word expected) {
        std::vector<unsigned char> bytes(size);
        if (!memory.Read(address,bytes.data(),bytes.size())) return false;
        Word hash=2166136261u;
        for (auto byte:bytes) hash=(hash^byte)*16777619u;
        return hash==expected;
    };
    if (!attachmentProfile || !nativeProfile || !hookWindows ||
        hookWindows[7].address!=attachmentProfile->attach ||
        !guardedBody(attachmentProfile->attach,0x108,attachmentProfile->attachHash) ||
        !guardedBody(attachmentProfile->creationReturn2-0x22,0x22,attachmentProfile->creationHash2) ||
        !guardedBody(attachmentProfile->creationReturn3-0x21,0x21,attachmentProfile->creationHash3) ||
        !guardedBody(attachmentProfile->builder,0x575,attachmentProfile->builderHash) ||
        !guardedBody(attachmentProfile->createdReturn-0x3F,0x4D,attachmentProfile->callerHash)) return false;
    // Reuse the independently verified stock service binding. GS_Level uses
    // AllUnitsList as well as GE_AllUnitsList; their primary receivers share
    // both lookup and enumeration methods (no receiver adjustment).
    const unsigned serviceIndex=static_cast<unsigned>(preparedBuild);
    if(serviceIndex>=3 || nativeProfile->allUnitsTable!=
        base+MajestyPairedOccupantAction::LookupProfiles[serviceIndex].serviceVtable)return false;
    const Word stockAllUnits=static_cast<Word>(base+MajestyPairedOccupantAction::AllUnitsTables[serviceIndex]);
    for(unsigned slot:{0x28u,0x30u}) {
        Word engineMethod=0,stockMethod=0;
        if(!Read(nativeProfile->allUnitsTable,slot,engineMethod)||!engineMethod||
           !Read(stockAllUnits,slot,stockMethod)||stockMethod!=engineMethod)return false;
    }
    unsigned char categoryCall[5]{};
    const Word categoryReturn=Category1FileReturnFor(preparedBuild);
    std::int32_t relative=0;
    if(!categoryReturn||!memory.Read(categoryReturn-5,categoryCall,sizeof(categoryCall))||categoryCall[0]!=0xE8)return false;
    std::memcpy(&relative,categoryCall+1,4);
    if(categoryReturn+relative!=hookWindows[12].address)return false;
    // Any installation failure is fatal at the owning registration boundary.
    // No readiness before every hook and loaded-output guard has succeeded.
    if (!RegisterBindings(base,registration)) return false;
    ownerThread=GetCurrentThreadId();
    if(impactPrepared&&!MajestyBooleanRuntime::BindOwnerThread())return false;
    Word runtime=0,attached=0,current=0;
    if (!Read(nativeProfile->runtimeGlobal,0,runtime) || (runtime &&
        (!Read(runtime,4,attached) || !Read(runtime,0x10,current) || attached || current))) {
        Trace("late-install-refused"); return false;
    }
    // All windows checked before ANY write. Only whole nonrelative entry
    // instructions are copied. No stopped-thread patching or midgame attach.
    for (unsigned i=0;i<kObservationHookCount;++i) {
        const auto& window=hookWindows[i];
        if (std::memcmp(reinterpret_cast<const void*>(window.address),window.bytes,window.count)) { Trace("hook-window-rejected",window.address); return false; }
    }
    auto* trampolines=static_cast<unsigned char*>(VirtualAlloc(nullptr,kObservationHookCount*32,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    if (!trampolines) return false;
    for (unsigned i=0;i<kObservationHookCount;++i) {
        const auto& w=hookWindows[i]; auto* code=trampolines+i*32;
        std::memcpy(code,w.bytes,w.count); code[w.count]=0xE9;
        const auto delta=static_cast<std::int32_t>(w.address+w.count-reinterpret_cast<std::uintptr_t>(code+w.count)-5);
        std::memcpy(code+w.count+1,&delta,4); original[i]=code;
    }
    DWORD previous=0;
    if (!VirtualProtect(trampolines,kObservationHookCount*32,PAGE_EXECUTE_READ,&previous)) { VirtualFree(trampolines,0,MEM_RELEASE); return false; }
    FlushInstructionCache(GetCurrentProcess(),trampolines,kObservationHookCount*32);
    unsigned changed=0;
    for (;changed<kObservationHookCount;++changed) if (!Patch(hookWindows[changed],targets[changed],false)) break;
    if (changed!=kObservationHookCount) {
        // Include the failed site: it might already have been written before
        // restoring its protection failed. Keep executable storage alive if
        // rollback fails; readiness remains disabled either way.
        bool restored=true;
        for (unsigned i=0;i<=changed && i<kObservationHookCount;++i) restored=Patch(hookWindows[i],nullptr,true)&&restored;
        if (restored) VirtualFree(trampolines,0,MEM_RELEASE);
        Fault("first-fault/install-rollback"); return false;
    }
    profile.imageBase=0x400000; profile.runtimeGlobal=nativeProfile->runtimeGlobal; profile.allUnitsVtable=nativeProfile->allUnitsTable;
    profile.stockAllUnitsVtable=stockAllUnits;
    profile.impactGlobal=nativeProfile->impactGlobal; profile.impactFunction=nativeProfile->impactFunction;
    profile.exactExecutable=profile.lifecycleBound=true;
    installed=true;
    Trace("hooks-installed",kObservationHookCount);
    return true;
}
