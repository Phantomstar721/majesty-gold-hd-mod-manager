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
#include "AttackObservationRuntime.h"
#include "GplCallArguments.h"
#include "AttackObservation.h"
#include "AttackObservationWindows.h"
#include "AttackObservationProof.h"
#include "BcdDefinitionOwnership.h"
#include "AttackObservationBaseline.h"
#include "AttackObservationContext.h"
#include "CheckedCastWindows.h"
#include "CheckedPlacementRuntime.h"
#include "AttackObservationShared.h"
#include "WorldAttachmentProfiles.h"
#include "AttackObservationNativeProfiles.h"
#include "AuditedBeta2.h"
#include "BooleanRuntime.h"
#include "NativeImpactProfiles.h"
#include "NativeImpactRegistry.h"
#include "NativeImpactCompletion.h"
#include "PairedOccupantLookupProfiles.h"
#include "RegistrationDiagnostic.h"

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
Word lastAttachCaller=0,lastAttachMode=0,lastAttachWorld=0;
int lastAttachLoadStatus=-1;
FailureReportBudget settlementFailureBudget;
void SettlementFailure(const char* stage,Word actor=0,const Capture* capture=nullptr) {
    if(!logger || !settlementFailureBudget.Take(Result::Unknown))return;
    char line[512]{};
    _snprintf_s(line,sizeof(line),_TRUNCATE,
        "attack-settlement first failure: stage=%s actor=%u effective=%u loaded=%u fault=%u units=%u orders=%u pending=%u missiles=%u lifecycle=%s attachCaller=%08X attachMode=%u attachWorld=%08X loadStatus=%d",
        stage,actor,effectiveReason,loadProof.Ready()?1u:0u,fault?1u:0u,
        capture?static_cast<unsigned>(capture->units):0u,
        capture?static_cast<unsigned>(capture->orders):0u,
        capture?static_cast<unsigned>(capture->actorPending):0u,
        capture?static_cast<unsigned>(capture->missiles):0u,life.Failure(),
        lastAttachCaller,lastAttachMode,lastAttachWorld,lastAttachLoadStatus);
    logger(line);
}
CombatContext releaseContext,impactContext;
void Trace(const char*,unsigned,unsigned,unsigned);
Word CombatIdentity(bool release,Word actor,Word target) {
    const auto& context=release?releaseContext:impactContext;
    const Word id=ContextId(context,actor,target);
    const Word accepted=id && life.ContextAllowed(memory,profile,context.world,context.generation,actor,id) ? id : 0;
    Trace(release?"release-ticket(actor,target,id)":"impact-ticket(actor,target,id)",actor,target,accepted);
    return accepted;
}
void CapacityTrace(Word actor,Word target,Word shot) { Trace("payload-capacity-exhausted",actor,target,shot); }
void Trace(const char* event,unsigned first=0,unsigned second=0,unsigned third=0) {
#if defined(CAM_ATTACK_DIAGNOSTIC)
    if (!logger) return;
    char line[192]{};
    _snprintf_s(line,sizeof(line),_TRUNCATE,"attack-observation %s: %u %u %u",event,first,second,third);
    logger(line);
#else
    (void)event;(void)first;(void)second;(void)third;
#endif
}
void ObservationTrace(std::uint32_t id,const Capture& capture) {
    static std::uint32_t lastId=0; static Result last=Result::Unknown;
    static std::size_t pending=~std::size_t(0),missiles=~std::size_t(0);
    if (id!=lastId || capture.result!=last || capture.actorPending!=pending || capture.missiles!=missiles) {
        Trace("observation(actor,result+1,owners-packed)",id,static_cast<unsigned>(static_cast<int>(capture.result)+1),static_cast<unsigned>((capture.actorPending<<16)|capture.missiles));
        lastId=id;last=capture.result;pending=capture.actorPending;missiles=capture.missiles;
    }
}
#if 1 // bounded first-fault evidence is part of normal support
static thread_local const char* diagnosticBoundary="outside-hook";
struct DiagnosticBoundary {
    const char* previous=diagnosticBoundary;
    explicit DiagnosticBoundary(const char* name) { diagnosticBoundary=name; }
    ~DiagnosticBoundary() { diagnosticBoundary=previous; }
};
struct DiagnosticHistory {
    char rows[16][768]{};
    unsigned count=0;
    void Add(const char* row) { std::snprintf(rows[count++%16],768,"%s",row); }
    void Dump(void (*writer)(const char*)) const {
        const unsigned begin=count>16?count-16:0;
        for(unsigned i=begin;i<count;++i)writer(rows[i%16]);
    }
};
static thread_local DiagnosticHistory diagnosticHistory;
struct BcdDiagnostic {
    static thread_local BcdDiagnostic* current;
    BcdDiagnostic* previous=current;
    char path[512]{};
    unsigned char digest[32]{};
    int rawIndex=-99,finalIndex=-99;
    unsigned openError=0,parsed=0,category=0,ready=0,openAttempted=0,hashed=0;
    const char* phase="entry";
    char conflict[160]{};
    int nativeResult=-1;
    LoadProof::State before{};
    BcdDiagnostic() { current=this; }
    ~BcdDiagnostic() {
        if(!fault) {
            char row[768]{};
            std::snprintf(row,sizeof(row),"FirstFault/v3 history raw=%d classified=%d result=%d phase=%s category=%u path=%s",rawIndex,finalIndex,nativeResult,phase,category,path);
            diagnosticHistory.Add(row);
        }
        current=previous;
    }
};
thread_local BcdDiagnostic* BcdDiagnostic::current=nullptr;
void DiagnosticPath(const char* path) {
    if(!BcdDiagnostic::current)return;
    auto& out=BcdDiagnostic::current->path;
    std::snprintf(out,sizeof(out),"%.511s",path);
    for(auto& c:out)if(c && static_cast<unsigned char>(c)<32)c='?';
}
#endif
void Fault(const char* reason,unsigned a=0,unsigned b=0,const char* boundary=nullptr) {
#if 1 // bounded first-fault evidence is part of normal support
    if(fault.exchange(true))return;
    if(!logger)return;
    char line[768]{};
    std::snprintf(line,sizeof(line),"FirstFault/v3 reason=%s boundary=%s a=%08x b=%08x thread=%08x owner=%08x build=%u",reason,boundary?boundary:diagnosticBoundary,a,b,GetCurrentThreadId(),ownerThread,static_cast<unsigned>(preparedBuild));
    logger(line);
    if(GetCurrentThreadId()==ownerThread) {
        const auto s=loadProof.DiagnosticState();
        std::snprintf(line,sizeof(line),"FirstFault/v3 proof started=%08x completed=%u finished=%08x depth=%u top=%d fault=%u scoped=%u category=%u receiver=%p",s.started,s.completed,s.finished,s.depth,s.top,s.fault,s.scoped,categoryFile,batchReceiver);
        logger(line);
        // Expected hashes identify the exact generated output as well as stock inputs.
        for(unsigned i=0;i<packageProof.digests.size() && i<9;++i) {
            char hex[65]{};for(unsigned j=0;j<32;++j)std::snprintf(hex+2*j,3,"%02x",packageProof.digests[i][j]);
            std::snprintf(line,sizeof(line),"FirstFault/v3 expected index=%u sha256=%s",i,hex);logger(line);
        }
    }
    diagnosticHistory.Dump(logger);
    if(const auto* context=BcdDiagnostic::current) {
        std::snprintf(line,sizeof(line),"FirstFault/v3 bcd raw=%d classified=%d parsed=%u category=%u readyBefore=%u openAttempted=%u openError=%u hashed=%u result=%d phase=%s conflict=%s",context->rawIndex,context->finalIndex,context->parsed,context->category,context->ready,context->openAttempted,context->openError,context->hashed,context->nativeResult,context->phase,context->conflict);
        logger(line);
        const auto& s=context->before;
        std::snprintf(line,sizeof(line),"FirstFault/v3 proofBefore started=%08x completed=%u finished=%08x depth=%u top=%d fault=%u scoped=%u",s.started,s.completed,s.finished,s.depth,s.top,s.fault,s.scoped);logger(line);
        char hex[65]{};
        for(unsigned i=0;i<32;++i)std::snprintf(hex+2*i,3,"%02x",context->digest[i]);
        std::snprintf(line,sizeof(line),"FirstFault/v3 bcd sha256=%s path=%s",hex,context->path);
        logger(line);
    }
#else
    (void)reason;(void)a;(void)b;(void)boundary;
    fault=true;
#endif
}
template<class T> bool Read(Word p,unsigned offset,T& out) { return p && p<=UINT32_MAX-offset && memory.Read(p+offset,&out,sizeof(out)); }
template<class T> T Value(const void* p,unsigned offset) { T out{}; if (!Read(static_cast<Word>(reinterpret_cast<std::uintptr_t>(p)),offset,out)) Fault("first-fault/read",static_cast<Word>(reinterpret_cast<std::uintptr_t>(p)),offset); return out; }
bool Owner(const char* boundary=nullptr) { if (GetCurrentThreadId()!=ownerThread) { Fault("first-fault/thread",ownerThread,GetCurrentThreadId(),boundary); return false; } return true; }
struct Guard {
    DiagnosticBoundary scope;
    bool active;
    bool castActive=false;
    int exceptions=std::uncaught_exceptions();
    explicit Guard(const char* name="observer") : scope(name),active(Owner(name)) { if (active) { life.EnterOperation();castActive=MajestyCheckedPlacement::EnterCastOperation(); } }
    ~Guard() { if (active) {
        const bool normal=std::uncaught_exceptions()==exceptions;
        if (!normal) { Fault("first-fault/unwind"); life.IdentityIncoherent("native-unwind"); }
        life.LeaveOperation();
        if(castActive)MajestyCheckedPlacement::LeaveCastOperation(normal&&!fault);
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
#if 1 // bounded first-fault evidence is part of normal support
        char bounded[512]{};
        if(WideCharToMultiByte(CP_UTF8,0,path.data(),-1,bounded,sizeof(bounded),nullptr,nullptr))DiagnosticPath(bounded);
        else DiagnosticPath("[path exceeds diagnostic limit or conversion failed]");
        if(BcdDiagnostic::current)BcdDiagnostic::current->openAttempted=1;
#endif
        return CreateFileW(path.data(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    }
    std::vector<char> path(length+1);
    if (!memory.Read(data,path.data(),length+1) || path.back()!=0) return INVALID_HANDLE_VALUE;
#if 1 // bounded first-fault evidence is part of normal support
    DiagnosticPath(path.data());
    if(BcdDiagnostic::current)BcdDiagnostic::current->openAttempted=1;
#endif
    return CreateFileA(path.data(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
}
bool __stdcall Bcd(const void* filename) {
#if 1 // bounded first-fault evidence is part of normal support
    BcdDiagnostic diagnostic;
    diagnostic.category=categoryFile?1u:0u;
#endif
    Guard guard("Bcd");
#if 1 // bounded first-fault evidence is part of normal support
    if(guard.active){diagnostic.ready=loadProof.Ready()?1u:0u;diagnostic.before=loadProof.DiagnosticState();}
    diagnostic.phase="open";
#endif
    HANDLE file=LockNativePath(filename);
#if 1 // bounded first-fault evidence is part of normal support
    diagnostic.openError=file==INVALID_HANDLE_VALUE && diagnostic.openAttempted?GetLastError():0;
#endif
    unsigned char digest[32]{};
    const bool digested=file!=INVALID_HANDLE_VALUE && Digest(file,digest);
    int index=digested ? packageProof.Find(digest) : -1;
#if 1 // bounded first-fault evidence is part of normal support
    diagnostic.rawIndex=index;std::memcpy(diagnostic.digest,digest,32);
    diagnostic.hashed=digested?1u:0u;
    diagnostic.phase=file==INVALID_HANDLE_VALUE?"open-failed":digested?"hashed":"digest-failed";
#endif
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
        if(parsed && categoryFile) {
#if 1 // bounded first-fault evidence is part of normal support
            const MajestyBcdOwnership::Key* rejected=nullptr;const char* reason="batch-admitted";
            admitted=batchOwnership.Admit(definitions,packageProof.protectedNames,generated,baseline,&rejected,&reason);
            diagnostic.phase=reason;
            if(rejected)std::snprintf(diagnostic.conflict,sizeof(diagnostic.conflict),"%u:%s",rejected->first,rejected->second.c_str());
#else
            admitted=batchOwnership.Admit(definitions,packageProof.protectedNames,generated,baseline);
#endif
        }
        else if(parsed && !baseline) {
            // Outside the reviewed batch route no earlier declaration proves
            // shadowing. Only genuinely non-overlapping optional files qualify.
            admitted=!generated;
            for(const auto& key:definitions)
                if(packageProof.protectedNames.count(MajestyBcdOwnership::Lower(key.second))) {
                    admitted=false;
#if 1 // bounded first-fault evidence is part of normal support
                    diagnostic.phase="protected-definition-outside-batch";
                    if(!diagnostic.conflict[0])std::snprintf(diagnostic.conflict,sizeof(diagnostic.conflict),"%u:%s",key.first,key.second.c_str());
#endif
                }
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
    #if 1 // bounded first-fault evidence is part of normal support
    diagnostic.finalIndex=index;diagnostic.parsed=parsed?1u:0u;
    if(file!=INVALID_HANDLE_VALUE && !parsed && !packageProof.protectedNames.empty())diagnostic.phase="definitions-unreadable";
    #endif
    if (guard.active) {
        // Invalidate before native registration, not after it has changed tables.
        MajestyCheckedPlacement::CastBindingEpochChanged();
        life.IdentityIncoherent("bcd-registration");profile.effectivePackage=false;
        if (!loadProof.Begin(index)) Fault("first-fault/bcd-begin",static_cast<unsigned>(index));
    }
    bool result=false;
    try { result=reinterpret_cast<bool (__stdcall*)(const void*)>(original[10])(filename); }
    catch (...) { if (file!=INVALID_HANDLE_VALUE) CloseHandle(file); Fault("first-fault/bcd-exception",static_cast<unsigned>(index)); throw; }
    if (file!=INVALID_HANDLE_VALUE) CloseHandle(file);
#if 1 // bounded first-fault evidence is part of normal support
    diagnostic.nativeResult=result?1:0;
#endif
    if (guard.active && !loadProof.Complete(index,result)) Fault("first-fault/bcd-complete",static_cast<unsigned>(index),result);
    if(guard.active && result && parsed && categoryFile && index!=-1)
        batchOwnership.Complete(definitions,packageProof.protectedNames,index>=6&&index<(packageProof.scoped?9:7));
    return result;
}
bool __fastcall BcdFilename(void* self,void*,const void* filename) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    Guard guard("BcdFilename");
    const bool previous=categoryFile;
    categoryFile=guard.active && caller==Category1FileReturnFor(preparedBuild);
    if(categoryFile) {
        if(previous || (batchReceiver && batchReceiver!=self))Fault("first-fault/bcd-batch-reentry",static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(self)),previous?1u:0u);
        batchReceiver=self;
    }
    struct RestoreRoute { bool previous; ~RestoreRoute(){ categoryFile=previous; } } restore{previous};
    return reinterpret_cast<bool (__thiscall*)(void*,const void*)>(original[12])(self,filename);
}
void __stdcall BeforeBcdPostload() {
    if(!Owner("BeforeBcdPostload"))return;
    const auto previousReceiver=static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(batchReceiver));
    // The full reverse list has now ended. Do not borrow publication evidence
    // across linking/catalog release or an unrecognized postload caller.
    batchOwnership.Reset();batchReceiver=nullptr;
    if(categoryFile)Fault("first-fault/postload-during-file",previousReceiver,0,"BeforeBcdPostload");
#if 1 // bounded first-fault evidence is part of normal support
    if(!fault)diagnosticHistory.Add("FirstFault/v3 history postload-reset");
#endif
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
    if(packageProof.actor.empty()) {
        effectiveReason=0;
        return impactPrepared && Callback(0x100A,nativeProfile->impactCallback);
    }
    effectiveReason=2;
    const Word action=Find(nativeProfile->actionCatalog,packageProof.action.c_str()),projectile=Find(nativeProfile->unitCatalog,packageProof.projectile.c_str()),hero=Find(nativeProfile->unitCatalog,packageProof.actor.c_str());
    Word actionEngine=0,projectileEngine=0,projectileId=0,emittedId=0,effect=0,script=0,scriptFlags=0,callbackId=0,text=0;
    if (!action || !projectile || !hero || !Read(action,0x14,actionEngine) || !Read(projectile,0x14,projectileEngine) || !Read(projectile,4,projectileId) || !Read(actionEngine,0x10,emittedId) || emittedId!=projectileId || !Read(actionEngine,0x14,effect) || effect || !Read(actionEngine,0x3C,script) || !Read(actionEngine,0x40,scriptFlags) || scriptFlags || !Read(actionEngine,0x44,callbackId) || callbackId) return false;
    std::vector<char> releaseName(packageProof.releaseCallback.size()+1);
    if (!script || !memory.Read(script,releaseName.data(),releaseName.size()) || releaseName.back() || _stricmp(releaseName.data(),packageProof.releaseCallback.c_str())) return false;
    effectiveReason=3;
    if (!Read(projectileEngine,0x90,text) || !Read(projectileEngine,0x94,scriptFlags) || scriptFlags) return false;
    char name[12]{}; if (!memory.Read(text,name,12) || name[11] || _stricmp(name,"make_attack")) return false;
    effectiveReason=4;
    if (!Callback(0x1000,nativeProfile->releaseCallback) || !Callback(0x100A,nativeProfile->impactCallback) || !Callback(0x1008,nativeProfile->pendingCallback)) return false;
    profile.projectileId=projectileId; profile.projectileEngine=projectileEngine; profile.scriptFlags=0;
    profile.actorDescriptor=hero; profile.movementEngine=0; profile.requireStockMovementFlags=true;
    profile.missileVtable=nativeProfile->missileTable; profile.animationVtable=nativeProfile->animationTable;
    profile.retirementMethod=nativeProfile->retirement;
    effectiveReason=0; return true;
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
    CombatContext context{};
    if (guard.active && profile.projectileEngine) {
        const auto current=CaptureTerminalMissile(
            [](Word p,unsigned offset,Word& out) { return Read(p,offset,out); },
            static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),a,c,
            profile.missileVtable,life.Generation());
        if (current.engine==profile.projectileEngine) context=current.identity;
    }
    CombatScope scope(impactContext,context);
    return reinterpret_cast<Word (__thiscall*)(void*,Word,Word,Word)>(original[0])(self,a,b,c);
}
void __fastcall Unlink(void* self,void*,Word order) {
    Guard guard;Word unit{};
    if(guard.active&&Read(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),4,unit))
        MajestyCheckedPlacement::ObserveCastUnlink(unit,order);
    reinterpret_cast<void (__thiscall*)(void*,Word)>(original[1])(self,order);
}
void __fastcall UnitRetire(void* self,void*) {
    Guard guard;
    const bool owner=guard.active; const Word pointer=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    if(owner)MajestyCheckedPlacement::ObserveCastRetire(pointer);
    Word id=0; const bool published=owner && Read(pointer,0x70,id) && id;
    RetirementToken token{};
    if (published) token=life.BeginRetirement(pointer,id); else if (owner) life.EnterOperation();
    reinterpret_cast<void (__thiscall*)(void*)>(original[2])(self);
    if (published) life.EndRetirement(token,true); else if (owner) life.LeaveOperation();
}
void __fastcall StackDestroy(void* self,void*,Word channel) {
    Guard guard;
    if(guard.active)MajestyCheckedPlacement::ObserveCastRetire(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*,Word)>(original[3])(self,channel);
}
Word __cdecl Emit(Word world,Word unit,Word stack,Word order,Word event) {
    Guard guard; CombatContext context{};
    Word description=0;
    if (guard.active && event==3 && profile.actorDescriptor && Read(unit,0x90,description) &&
        description==profile.actorDescriptor && Read(unit,0x70,context.actor) && Read(unit,0x94,context.world) &&
        Read(order,0x60,context.target)) context.generation=life.Generation();
    else context={};
    CombatScope scope(releaseContext,context);
    return reinterpret_cast<Word (__cdecl*)(Word,Word,Word,Word,Word)>(original[4])(world,unit,stack,order,event);
}
Word __fastcall Submit(void* self,void*,Word channel,Word order) {
    Guard guard;
    // Submit may synchronously process and destroy both the order and its
    // owner. Capture the emitted identity while the native caller owns them;
    // the returned pointer is not proof of either object's continued lifetime.
    Word kind=0,terminal=0,shooter=0,target=0,description=0,engine=0,id=0,vtable=0,world=0;
    const Word unit=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    if (guard.active && releaseContext.actor && profile.projectileEngine &&
        Read(order,0x10,kind) && kind==3 && Read(order,0x2C,terminal) && terminal==0x100A &&
        Read(order,0,vtable) && vtable==profile.missileVtable &&
        Read(order,0x5C,shooter) && shooter==releaseContext.actor && Read(order,0x38,target) && target==releaseContext.target &&
        Read(unit,0x90,description) && Read(description,0x14,engine) && engine==profile.projectileEngine &&
        Read(unit,0x70,id) && Read(unit,0x94,world) && world==releaseContext.world &&
        life.ContextAllowed(memory,profile,world,releaseContext.generation,shooter,id))
        releaseContext.projectile=id;
    const auto castRevision=guard.active?MajestyCheckedPlacement::ObserveCastSubmissionStarting(
        static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),order):0;
    const Word result=reinterpret_cast<Word (__thiscall*)(void*,Word,Word)>(original[5])(self,channel,order);
    if(guard.active)MajestyCheckedPlacement::ObserveCastSubmit(
        static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),channel,order,result,castRevision);
    return result;
}
void __fastcall WorldDestroy(void* self,void*) {
    Guard guard;
    const bool owner=guard.active; if (owner) life.BeginWorldTeardown();
    if(owner)MajestyCheckedPlacement::CastBindingEpochChanged();
    if (owner) Trace("world-teardown");
    reinterpret_cast<void (__thiscall*)(void*)>(original[6])(self);
    if (owner) life.LeaveOperation();
}
void __fastcall Attach(void* self,void*,Word world,Word mode) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    if (Owner()) {
        lastAttachCaller=static_cast<Word>(caller);lastAttachMode=mode;
        lastAttachWorld=world;lastAttachLoadStatus=acceptedStatus;
        MajestyCheckedPlacement::CastBindingEpochChanged();
        life.IdentityIncoherent("world-attach-enter");
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
        if(attached&&!MajestyCheckedPlacement::RebindPreparedWorld()) {
            life.IdentityIncoherent("placement-world-binding-rejected");Trace("placement-world-binding-rejected");
        }
    } else life.IdentityIncoherent(route==AttachmentRoute::None ? "world-attach-unrecognized-route" : "world-attach-gate-rejected");
    acceptedStatus=-1; acceptedWorld=0;
}
int __fastcall Load(void* self,void*,Word filename,Word output) {
    if(Owner())MajestyCheckedPlacement::CastBindingEpochChanged();
    if (Owner()) { life.IdentityIncoherent("world-load-enter"); acceptedStatus=-1; acceptedWorld=0; }
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
    if (!result && guard.active) { life.IdentityIncoherent("spawn-failed-readiness-invalidated"); Trace("spawn-failed-readiness-invalidated"); }
    return result;
}
Word __fastcall Restore(void* self,void*,Word stream) {
    Guard guard;if(guard.active)MajestyCheckedPlacement::CastBindingEpochChanged();
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
Lifecycle* bindingLifecycle=nullptr;
Profile* bindingProfile=nullptr;
bool (*bindingGate)()=nullptr;
void (*bindingTrace)(std::uint32_t,const Capture&)=nullptr;
std::uint32_t (*bindingContext)(bool,std::uint32_t,std::uint32_t)=nullptr;
void (*bindingCapacity)(std::uint32_t,std::uint32_t,std::uint32_t)=nullptr;
ShotSnapshot bindingSnapshot;
template<class T> T Direct(const void* p,unsigned offset) { T v{}; std::memcpy(&v,static_cast<const unsigned char*>(p)+offset,sizeof(v)); return v; }
void* FrameArgument(void* arguments,unsigned index) {
    if (!arguments) return nullptr;
    const auto first=Direct<std::uintptr_t>(arguments,0x0C),last=Direct<std::uintptr_t>(arguments,0x10);
    if (!first || last<first || last-first>16*sizeof(void*) || (last-first)%sizeof(void*) || index>=(last-first)/sizeof(void*)) return nullptr;
    using At=void** (__thiscall*)(void*,unsigned);
    if (!nativeProfile) return nullptr;
    auto entry=reinterpret_cast<At>(nativeProfile->argumentAt)(arguments,index); return entry?*entry:nullptr;
}
void* Argument(void* arguments,unsigned index) {
    if (!arguments) return nullptr;
    const auto first=Direct<std::uintptr_t>(arguments,0x0C),last=Direct<std::uintptr_t>(arguments,0x10);
    if (!first || last<first || last-first>16*sizeof(void*) || (last-first)%sizeof(void*)) return nullptr;
    unsigned slot{};
    return MajestyGplCall::ExplicitSlot(index,(last-first)/sizeof(void*),slot) ? FrameArgument(arguments,slot) : nullptr;
}
void __cdecl Settled(void* arguments) {
    using Ref=void* (__thiscall*)(void*);
    void* result=Argument(arguments,0);
    if (!result) { SettlementFailure("output-argument");return; }
    auto output=static_cast<int*>(reinterpret_cast<Ref>((*static_cast<void***>(result))[0x28/4])(result));
    if (!output) { SettlementFailure("output-reference");return; }
    *output=static_cast<int>(Result::Unknown);
    if (!bindingLifecycle || !bindingProfile || !bindingProfile->lifecycleBound) { SettlementFailure("binding");return; }
    if (bindingGate && !bindingGate()) { SettlementFailure("effective-package");return; }
    void* agent=Argument(arguments,1); if (!agent) { SettlementFailure("agent-argument");return; }
    void* reference=reinterpret_cast<Ref>((*static_cast<void***>(agent))[0x5C/4])(agent); if (!reference) { SettlementFailure("agent-reference");return; }
    std::uint32_t temporary[4]{}; temporary[2]=Direct<std::uint32_t>(reference,8);
    void* unit=reinterpret_cast<Ref>(nativeProfile->resolveAgent)(temporary); if (!unit) { SettlementFailure("agent-resolution");return; }
    std::uint32_t id=0;
    if (!Read(static_cast<Address>(reinterpret_cast<std::uintptr_t>(unit)),0x70,id)) { SettlementFailure("actor-id");return; }
    const auto capture=bindingLifecycle->Query(memory,*bindingProfile,static_cast<Address>(reinterpret_cast<std::uintptr_t>(unit)),id);
    *output=static_cast<int>(capture.result);
    if(capture.result==Result::Unknown)SettlementFailure(capture.failure,id,&capture);
    if (bindingTrace) bindingTrace(id,capture);
}
Address AgentValueAddress(void* agent) {
    using Ref=void* (__thiscall*)(void*);
    if (!agent) return 0;
    void* reference=reinterpret_cast<Ref>((*static_cast<void***>(agent))[0x5C/4])(agent); if (!reference) return 0;
    std::uint32_t temporary[4]{}; temporary[2]=Direct<std::uint32_t>(reference,8);
    void* unit=reinterpret_cast<Ref>(nativeProfile->resolveAgent)(temporary); if (!unit) return 0;
    return static_cast<Address>(reinterpret_cast<std::uintptr_t>(unit));
}
Address AgentAddress(void* arguments,unsigned index) {
    return AgentValueAddress(Argument(arguments,index));
}
std::uint32_t AgentId(void* arguments,unsigned index) {
    std::uint32_t id=0;
    const Address actor=AgentAddress(arguments,index);
    if (actor) Read(actor,0x70,id);
    return id;
}
int* IntegerArgument(void* args,unsigned index) {
    using Ref=void* (__thiscall*)(void*);
    void* value=Argument(args,index);if (!value) return nullptr;
    return static_cast<int*>(reinterpret_cast<Ref>((*static_cast<void***>(value))[0x28/4])(value));
}
bool SnapshotGate() { return bindingLifecycle && bindingProfile && bindingGate && bindingGate(); }
void __cdecl BeginShotSnapshot(void* args) {
    auto output=IntegerArgument(args,0);if (!output) return;*output=0;
    if (!SnapshotGate()) return;
    const Address actor=AgentAddress(args,1);std::uint32_t id=0;
    if (!actor || !Read(actor,0x70,id)) return;
    *output=bindingSnapshot.Begin(memory,*bindingProfile,*bindingLifecycle,actor,id);
}
void __cdecl ShotPending(void* args) {
    auto output=IntegerArgument(args,0);if (!output) return;*output=-1;
    if (!SnapshotGate()) return;
    auto shot=IntegerArgument(args,2),token=IntegerArgument(args,3);if (!shot || !token || *shot<=0) return;
    const Address actor=AgentAddress(args,1);std::uint32_t id=0;
    if (!actor || !Read(actor,0x70,id)) return;
    *output=bindingSnapshot.Pending(memory,*bindingProfile,*bindingLifecycle,actor,id,*token,static_cast<std::uint32_t>(*shot));
}
void __cdecl EndShotSnapshot(void* args) {
    auto token=IntegerArgument(args,0);if (token) bindingSnapshot.End(*token);
}
void __cdecl PayloadFull(void* args) {
    if (!SnapshotGate() || !bindingContext || !bindingCapacity) return;
    auto shot=IntegerArgument(args,2);if (!shot || *shot<=0) return;
    const auto actor=AgentId(args,0),target=AgentId(args,1);
    if (bindingContext(true,actor,target)==static_cast<std::uint32_t>(*shot)) bindingCapacity(actor,target,*shot);
}
void __cdecl ShotRetired(void* args) {
    auto output=IntegerArgument(args,0);if (!output) return;*output=-1;
    if (!SnapshotGate() || !bindingContext) return;
    auto current=IntegerArgument(args,3),old=IntegerArgument(args,4);
    if (!current || !old || !Representable(static_cast<Word>(*current)) ||
        !Representable(static_cast<Word>(*old))) return;
    // Only an already recorded concrete retirement is usable during release.
    // No native-list walk or relaxation of the settled/snapshot guard.
    if (bindingContext(true,AgentId(args,1),AgentId(args,2))!=static_cast<std::uint32_t>(*current)) return;
    *output=bindingLifecycle->RecordedRetirement(static_cast<std::uint32_t>(*old))?1:0;
}
void ContextOutput(void* arguments,bool release) {
    using Ref=void* (__thiscall*)(void*);
    void* value=Argument(arguments,0); if (!value) return;
    auto output=static_cast<int*>(reinterpret_cast<Ref>((*static_cast<void***>(value))[0x28/4])(value));
    if (!output) return;
    *output=0;
    if (!bindingContext || !bindingProfile || !bindingProfile->lifecycleBound || !bindingGate || !bindingGate()) return;
    *output=static_cast<int>(bindingContext(release,AgentId(arguments,1),AgentId(arguments,2)));
}
void __cdecl ReleaseId(void* args) { ContextOutput(args,true); }
void __cdecl ImpactId(void* args) { ContextOutput(args,false); }
bool RegisterBindings(std::uintptr_t base,RegisterProcedure registration) {
    if (base!=0x400000 || !nativeProfile) return false;
    if(packageProof.apiPrefix.empty())return impactPrepared;
    bindingLifecycle=&life;bindingProfile=&profile;
    bindingGate=&Gate;bindingTrace=&ObservationTrace;bindingContext=&CombatIdentity;bindingCapacity=&CapacityTrace;
    const char* suffixes[]={"AttackSettled","ReleaseId","ImpactId","BeginShotSnapshot","ShotPending","EndShotSnapshot","PayloadFull","ShotRetired"};
    void (__cdecl* callbacks[])(void*)={&Settled,&ReleaseId,&ImpactId,&BeginShotSnapshot,&ShotPending,&EndShotSnapshot,&PayloadFull,&ShotRetired};
    for (unsigned i=0;i<8;++i) registration((packageProof.apiPrefix+"_"+suffixes[i]).c_str(),callbacks[i]);
    return true;
}
}
bool MajestyAttackObservation::PrepareRuntime(const wchar_t* manifest,MajestyBuildId build,bool interception) {
    if (prepared || !manifest || !MajestyCheckedPlacement::AuditedStartup(build)) return false;
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
    if(packageProof.actor.empty()&&!impactPrepared)return false;
    loadProof=LoadProof(packageProof.scoped);
    preparedBuild=build;prepared=true;return true;
}

bool MajestyAttackObservation::InstallRuntime(std::uintptr_t base,RegisterProcedure registration,void (*writer)(const char*)) {
    logger=writer;
    RegistrationDiagnostic diagnostic(writer);
    diagnostic.Begin(static_cast<unsigned>(preparedBuild),(prepared?1u:0u)|(installed?2u:0u)|(fault?4u:0u),GetCurrentThreadId(),ownerThread);
    diagnostic.Stage("admission",static_cast<Word>(base),registration?1u:0u,prepared?1u:0u);
    if (!prepared || !registration || base!=0x400000) {
        Trace("registration-admission-rejected"); return false;
    }
    // Stock rebuilds its GPL registration table more than once. Hooks belong
    // to this process, callbacks to each table. Do not hash our own patched
    // entries as stock or allocate/install a second set of trampolines.
    if (installed) {
        diagnostic.Stage("reregistration-profile",static_cast<unsigned>(preparedBuild));
        if(nativeProfile!=ObservationNativeFor(preparedBuild))return false;
        diagnostic.Stage("reregistration-state",fault?1u:0u,GetCurrentThreadId(),ownerThread);
        if (fault || GetCurrentThreadId()!=ownerThread) {
            Trace("registration-state-rejected"); return false;
        }
        diagnostic.Stage("reregistration-bindings",nativeProfile?1u:0u,packageProof.actor.empty()?1u:0u,impactPrepared?1u:0u);
        const bool ok=RegisterBindings(base,registration);
        if(ok)Trace("bindings-reregistered");
        return ok?diagnostic.Accept("reregistered"):false;
    }
    // This check authorizes first-time hook installation only. A later stock
    // table rebuild does not install hooks and may occur with a world present.
    diagnostic.Stage("startup-certificate");
    if(!MajestyCheckedPlacement::AuditedStartup(preparedBuild))return false;
    // Require the complete stock creator and its nonnull caller before
    // admitting the new-world route.
    attachmentProfile=WorldAttachmentFor(preparedBuild);
    nativeProfile=ObservationNativeFor(preparedBuild);
    const auto* hookWindows=ObservationHooksFor(preparedBuild);
    const auto guardedBody=[&](Word address,unsigned size,Word expected) {
        diagnostic.Stage("body-read",address,size,expected);
        std::vector<unsigned char> bytes(size);
        if (!memory.Read(address,bytes.data(),bytes.size())) return false;
        Word hash=2166136261u;
        for (auto byte:bytes) hash=(hash^byte)*16777619u;
        diagnostic.Stage("body-hash",address,hash,expected);
        return hash==expected;
    };
    diagnostic.Stage("attachment-profiles",attachmentProfile?1u:0u,nativeProfile?1u:0u,hookWindows?1u:0u);
    if (!attachmentProfile || !nativeProfile || !hookWindows)return false;
    diagnostic.Stage("attachment-window",hookWindows[7].address,attachmentProfile->attach);
    if(hookWindows[7].address!=attachmentProfile->attach)return false;
    if (!guardedBody(attachmentProfile->attach,0x108,attachmentProfile->attachHash) ||
        !guardedBody(attachmentProfile->savedMenuReturn-19,19,attachmentProfile->savedMenuHash) ||
        !guardedBody(attachmentProfile->creationReturn2-0x22,0x22,attachmentProfile->creationHash2) ||
        !guardedBody(attachmentProfile->creationReturn3-0x21,0x21,attachmentProfile->creationHash3) ||
        !guardedBody(attachmentProfile->builder,0x575,attachmentProfile->builderHash) ||
        !guardedBody(attachmentProfile->createdReturn-0x3F,0x4D,attachmentProfile->callerHash)) return false;
    // Reuse the independently verified stock service binding. GS_Level uses
    // AllUnitsList as well as GE_AllUnitsList; their primary receivers share
    // both lookup and enumeration methods (no receiver adjustment).
    const unsigned serviceIndex=static_cast<unsigned>(preparedBuild);
    diagnostic.Stage("service-profile",serviceIndex,nativeProfile->allUnitsTable);
    if(serviceIndex>=3 || nativeProfile->allUnitsTable!=
        base+MajestyPairedOccupantAction::LookupProfiles[serviceIndex].serviceVtable)return false;
    const Word stockAllUnits=static_cast<Word>(base+MajestyPairedOccupantAction::AllUnitsTables[serviceIndex]);
    for(unsigned slot:{0x28u,0x30u}) {
        Word engineMethod=0,stockMethod=0;
        diagnostic.Stage("service-engine-read",slot,nativeProfile->allUnitsTable);
        if(!Read(nativeProfile->allUnitsTable,slot,engineMethod)||!engineMethod)return false;
        diagnostic.Stage("service-stock-read",slot,stockAllUnits);
        if(!Read(stockAllUnits,slot,stockMethod))return false;
        diagnostic.Stage("service-method-mismatch",slot,engineMethod,stockMethod);
        if(stockMethod!=engineMethod)return false;
    }
    unsigned char categoryCall[5]{};
    const Word categoryReturn=Category1FileReturnFor(preparedBuild);
    std::int32_t relative=0;
    diagnostic.Stage("category-call-read",categoryReturn);
    if(!categoryReturn||!memory.Read(categoryReturn-5,categoryCall,sizeof(categoryCall)))return false;
    diagnostic.Stage("category-call-opcode",categoryReturn,categoryCall[0]);
    if(categoryCall[0]!=0xE8)return false;
    std::memcpy(&relative,categoryCall+1,4);
    diagnostic.Stage("category-call-target",categoryReturn+relative,hookWindows[12].address);
    if(categoryReturn+relative!=hookWindows[12].address)return false;
    // Any installation failure is fatal at the owning registration boundary.
    // No readiness before every hook and loaded-output guard has succeeded.
    diagnostic.Stage("initial-bindings",nativeProfile?1u:0u,packageProof.actor.empty()?1u:0u,impactPrepared?1u:0u);
    if (!RegisterBindings(base,registration)) return false;
    ownerThread=GetCurrentThreadId();
    diagnostic.Stage("boolean-owner-thread",ownerThread);
    if(impactPrepared&&!MajestyBooleanRuntime::BindOwnerThread())return false;
    Word runtime=0,attached=0,current=0;
    diagnostic.Stage("late-runtime-read",nativeProfile->runtimeGlobal);
    if(!Read(nativeProfile->runtimeGlobal,0,runtime))return false;
    if(runtime) {
        diagnostic.Stage("late-attached-read",runtime);
        if(!Read(runtime,4,attached))return false;
        diagnostic.Stage("late-current-read",runtime,attached);
        if(!Read(runtime,0x10,current))return false;
        diagnostic.Stage("late-world-present",runtime,attached,current);
        if(attached || current)return false;
    }
    // All windows checked before ANY write. Only whole nonrelative entry
    // instructions are copied. No stopped-thread patching or midgame attach.
    for (unsigned i=0;i<kObservationHookCount;++i) {
        const auto& window=hookWindows[i];
        diagnostic.Stage("hook-window",i,window.address,window.count);
        if (std::memcmp(reinterpret_cast<const void*>(window.address),window.bytes,window.count)) { Trace("hook-window-rejected",window.address); return false; }
    }
    auto* trampolines=static_cast<unsigned char*>(VirtualAlloc(nullptr,kObservationHookCount*32,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    if (!trampolines) { diagnostic.Stage("trampoline-allocation",GetLastError()); return false; }
    for (unsigned i=0;i<kObservationHookCount;++i) {
        const auto& w=hookWindows[i]; auto* code=trampolines+i*32;
        std::memcpy(code,w.bytes,w.count); code[w.count]=0xE9;
        const auto delta=static_cast<std::int32_t>(w.address+w.count-reinterpret_cast<std::uintptr_t>(code+w.count)-5);
        std::memcpy(code+w.count+1,&delta,4); original[i]=code;
    }
    DWORD previous=0;
    if (!VirtualProtect(trampolines,kObservationHookCount*32,PAGE_EXECUTE_READ,&previous)) { diagnostic.Stage("trampoline-protection",GetLastError()); VirtualFree(trampolines,0,MEM_RELEASE); return false; }
    FlushInstructionCache(GetCurrentProcess(),trampolines,kObservationHookCount*32);
    unsigned changed=0;
    for (;changed<kObservationHookCount;++changed) if (!Patch(hookWindows[changed],targets[changed],false)) break;
    if (changed!=kObservationHookCount) {
        const DWORD patchError=GetLastError();
        // Include the failed site: it might already have been written before
        // restoring its protection failed. Keep executable storage alive if
        // rollback fails; readiness remains disabled either way.
        bool restored=true;
        for (unsigned i=0;i<=changed && i<kObservationHookCount;++i) restored=Patch(hookWindows[i],nullptr,true)&&restored;
        if (restored) VirtualFree(trampolines,0,MEM_RELEASE);
        diagnostic.Stage("hook-patch-rollback",changed,patchError,restored?1u:0u);
        Fault("first-fault/install-rollback"); return false;
    }
    profile.imageBase=0x400000; profile.runtimeGlobal=nativeProfile->runtimeGlobal; profile.allUnitsVtable=nativeProfile->allUnitsTable;
    profile.stockAllUnitsVtable=stockAllUnits;
    profile.impactGlobal=nativeProfile->impactGlobal; profile.impactFunction=nativeProfile->impactFunction;
    profile.exactExecutable=profile.lifecycleBound=true;
    installed=true;
    Trace("hooks-installed",kObservationHookCount);
    return diagnostic.Accept("installed");
}

const MajestyAttackObservation::Memory& MajestyAttackObservation::SharedMemory(){return memory;}
namespace { const char* sharedIdentityFailure="identity not queried"; }
const char* MajestyAttackObservation::SharedIdentityFailure(){return sharedIdentityFailure;}
bool MajestyAttackObservation::SharedCurrentIdentity(Address unit,Word id,Address world,Address description) {
    sharedIdentityFailure="shared: not installed";
    if(!installed)return false;
    sharedIdentityFailure="shared: effective observer gate rejected";
    if(!Gate())return false;
    sharedIdentityFailure="shared: world lifecycle context rejected";
    if(!life.ContextAllowed(memory,profile,world,life.Generation(),id,id))return false;
    using FindUnit=Word (__thiscall*)(void*,Word);
    sharedIdentityFailure="shared: world unit lookup mismatch";
    if(reinterpret_cast<FindUnit>(nativeProfile->findUnit)(reinterpret_cast<void*>(world),id)!=unit)return false;
    Word catalog{},resource{},unitResource{};
    sharedIdentityFailure="shared: resource ID mismatch";
    if(!Read(nativeProfile->unitCatalog,0,catalog)||!catalog||!Read(description,4,resource)||!Read(unit,0x7C,unitResource)||resource!=unitResource)return false;
    // 5C3000 traverses a tree through the native iterator, not next pointers.
    // Use its exact loaded-name lookup and require the identical descriptor.
    Word name{},data{},flags{},length{};
    sharedIdentityFailure="shared: descriptor name header rejected";
    if(!Read(description,0x0C,name)||!Read(name,0,data)||!Read(name,4,flags)||
        (flags&0x01000000)||!Read(name,8,length)||!length||length>255)return false;
    std::vector<char> text(length+1);
    sharedIdentityFailure="shared: descriptor name bytes rejected";
    if(!memory.Read(data,text.data(),text.size())||text.back()||
        std::strlen(text.data())!=length)return false;
    using FindName=Word (__thiscall*)(void*,const char*);
    sharedIdentityFailure="shared: loaded descriptor lookup mismatch";
    return reinterpret_cast<FindName>(nativeProfile->findName)(reinterpret_cast<void*>(catalog),text.data())==description;
}
bool MajestyAttackObservation::SharedIdle(Address unit,Word id,Address description) {
    if(!installed||!Gate())return false;
    auto local=profile;local.actorDescriptor=description;
    if(life.Query(memory,local,unit,id).result!=Result::Settled)return false;
    // Decision-phase admission requires no native order on any ordinary
    // channel. This excludes retreat and unsupported outstanding orders too.
    for(unsigned channel=0;channel<3;++channel) {
        Word stack{},ownerUnit{},head{},first{};
        if(!Read(unit,0x98+4*channel,stack))return false;
        if(!stack)continue;
        if(!Read(stack,4,ownerUnit)||ownerUnit!=unit||!Read(stack,0x1C,head)||!head||!Read(head,0,first)||first!=head)return false;
    }
    return true;
}
bool MajestyAttackObservation::SharedDecisionContext() {
    return installed&&Gate()&&life.SnapshotCurrent(memory,profile,life.Generation(),life.Revision());
}
void MajestyAttackObservation::SharedDiagnosticLine(const char* line) {
    if(logger&&line)logger(line);
}
void* MajestyAttackObservation::SharedArgument(void* arguments,unsigned index){return Argument(arguments,index);}
void* MajestyAttackObservation::SharedFrameArgument(void* arguments,unsigned index){return FrameArgument(arguments,index);}
MajestyAttackObservation::Address MajestyAttackObservation::SharedFrameAgent(void* arguments,unsigned index){return AgentValueAddress(FrameArgument(arguments,index));}
MajestyAttackObservation::Address MajestyAttackObservation::SharedAgent(void* arguments,unsigned index){return AgentAddress(arguments,index);}
int* MajestyAttackObservation::SharedInteger(void* arguments,unsigned index){return IntegerArgument(arguments,index);}

bool MajestyAttackObservation::SharedProofMatches(const unsigned char* digest){return prepared&&digest&&!std::memcmp(digest,preparedProofDigest,32);}
