#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <intrin.h>
#include <cstring>
#include <cstdio>
#include <limits>
#include <atomic>
#include <exception>
#include <set>
#include "CheckedCastWindows.h"
#include "CheckedPlacementRuntime.h"
#include "PendingCastProfiles.h"
#include "CheckedCastProfiles.h"
#include "CosmeticActionProfiles.h"
#include "AuditedBeta2.h"

namespace {
using namespace MajestyCheckedPlacement;
StockCasts casts;
CosmeticActionCleanup cosmeticCleanup;
const CosmeticActionProfile* cosmeticProfile{};
const CosmeticImageTypes* cosmeticTypes{};
CosmeticActionState cosmeticState;
CastBindings bindings;
const CastNativeProfile* nativeProfile{};
const PendingCastProfile* pendingProfile{};
Word nativeDoAction{},nativeCancel{};
DWORD owner{};
bool installed{};
std::atomic<bool> fault{false};
void* originals[18]{};
void* deadMethodOriginal{},*deadEventOriginal{},*deadOrderOriginal{},*deadFlagsOriginal{};
std::map<Word,std::pair<Word,std::uint64_t>> epochs;
std::uint64_t serial{};
struct Request { Identity actor,target;bool active{},submitted{}; } request;
Word processingUnit{},processingOrder{},releaseUnit{},releaseOrder{};
Word cancelActor{},cancelFrame{};
template<class T> bool Read(Word p,unsigned offset,T& out) {
    return bindings.memory&&p&&p<=UINT32_MAX-offset&&sizeof(T)<=UINT32_MAX-p-offset&&
        bindings.memory->Read(p+offset,&out,sizeof(out));
}
bool Owner() { if(!installed)return false; if(GetCurrentThreadId()!=owner){fault=true;return false;}return !fault; }
struct FailureGuard {
    int exceptions=std::uncaught_exceptions();
    ~FailureGuard(){if(std::uncaught_exceptions()>exceptions)fault=true;}
};
struct Operation {
    bool active=EnterCastOperation();
    int exceptions=std::uncaught_exceptions();
    ~Operation(){if(active)LeaveCastOperation(std::uncaught_exceptions()==exceptions);}
};
bool Capture(Word unit,Identity& identity) { return Owner()&&bindings.identity&&bindings.identity(unit,identity); }
struct Scope {
    Word& field;Word prior;
    Scope(Word& f,Word value):field(f),prior(f){field=value;}
    ~Scope(){field=prior;}
};
bool __fastcall Process(void* self,void*,Word unit,Word stack,Word event) {
    Operation operation;
    FailureGuard failure;
    const Word order=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    Scope u(processingUnit,Owner()?unit:0),o(processingOrder,Owner()?order:0);
    return reinterpret_cast<bool (__thiscall*)(void*,Word,Word,Word)>(originals[0])(self,unit,stack,event);
}
bool __fastcall TurnProcess(void* self,void*,Word unit,Word stack,Word event) {
    Operation operation;FailureGuard failure;
    const Word order=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    Word table{},callback{},qualifier{};
    const bool pending=Owner()&&pendingProfile&&(event==0||event==2)&&Read(order,0,table)&&table==pendingProfile->table&&
        Read(order,0x2C,callback)&&callback==0x1008&&Read(order,0x1C,qualifier)&&qualifier==1;
    // Submit inserts before synchronous Process. Capture this exact child
    // before it can immediately hand off again, not only after Submit returns.
    if(pending&&processingUnit==unit&&processingOrder) {
        Word ownerUnit{},id{},action{},target{};
        if(Read(stack,4,ownerUnit)&&ownerUnit==unit&&Read(unit,0x70,id)&&
            Read(order,0x50,action)&&Read(order,0x54,target))
            casts.Turning(id,processingOrder,order,action,target);
    }
    Scope u(processingUnit,pending?unit:0),o(processingOrder,pending?order:0);
    return reinterpret_cast<bool (__thiscall*)(void*,Word,Word,Word)>(originals[17])(self,unit,stack,event);
}
void __cdecl Schedule(void* arguments) {
    FailureGuard failure;
    Word value{},definition{},flags{};unsigned char executing{};
    Identity actor,target;
    bool observed=false;
    if(Owner()&&releaseUnit&&releaseOrder&&bindings.argument&&bindings.agent) {
        value=static_cast<Word>(reinterpret_cast<std::uintptr_t>(bindings.argument(arguments,1)));
        Word table{};
        observed=Read(value,0,table)&&nativeProfile&&table==nativeProfile->functionTable&&Read(value,8,definition)&&
            definition==bindings.movementCallback&&Read(value,0x4C,flags)&&!flags&&
            Read(value,0x54,executing)&&!executing&&Capture(bindings.agent(arguments,3),actor)&&
            actor.address==releaseUnit&&Capture(bindings.agent(arguments,4),target);
    }
    reinterpret_cast<void (__cdecl*)(void*)>(originals[2])(arguments);
    if(releaseUnit){char detail[200]{};std::snprintf(detail,sizeof(detail),
        "Schedule inputs value=%08X definition=%08X expected=%08X flags=%u executing=%u actor=%08X target=%08X",
        value,definition,bindings.movementCallback,flags,executing,actor.address,target.address);
        TracePlacementStage(releaseUnit,48,detail);}
    if(releaseUnit)TracePlacementStage(releaseUnit,observed?22:23,
        observed?"Schedule: callback arguments matched":"Schedule: callback arguments rejected");
    if(observed) {
        Word afterDefinition{},afterFlags{};Identity currentActor,currentTarget;
        if(Capture(actor.address,currentActor)&&Capture(target.address,currentTarget)&&
            Same(actor,currentActor)&&Same(target,currentTarget)&&
            Read(value,8,afterDefinition)&&afterDefinition==definition&&Read(value,0x4C,afterFlags)&&afterFlags==1)
            { const bool accepted=casts.Scheduled(actor.id,releaseOrder,value,definition,true);
              TracePlacementStage(actor.address,accepted?24:25,accepted?"Schedule: recorded":"Schedule: cast record rejected"); }
        else casts.Interrupted(actor.id);
    }
}
void __fastcall ResetFunction(void* self,void*) {
    if(Owner())casts.InvalidateFunction(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*)>(originals[3])(self);
}
void __fastcall DestroyFunction(void* self,void*) {
    if(Owner())casts.InvalidateFunction(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*)>(originals[4])(self);
}
void __fastcall Player(void* self,void*,Word player) {
    Operation operation;
    const Word unit=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));Word old{};
    if(Owner()&&(!Read(unit,0x80,old)||old!=player))ObserveCastRetire(unit);
    reinterpret_cast<void (__thiscall*)(void*,Word)>(originals[5])(self,player);
}
void __fastcall Team(void* self,void*,Word player,Word team) {
    Operation operation;
    if(Owner()){cosmeticCleanup.Reset();casts.Reset();}
    reinterpret_cast<void (__thiscall*)(void*,Word,Word)>(originals[6])(self,player,team);
}
void __fastcall Attribute(void* self,void*,Word attribute,int value) {
    Operation operation;
    if(Owner()&&attribute==0x00555041&&value<1)
        ObserveCastRetire(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*,Word,int)>(originals[7])(self,attribute,value);
}
void __fastcall RemovalRequested(void* self,void*) {
    Operation operation;
    if(Owner())ObserveCastRetire(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*)>(originals[9])(self);
}
void __fastcall Retarget(void* self,void*,Word target) {
    Operation operation;
    if(Owner())casts.RetargetedOrder(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),target);
    reinterpret_cast<void (__thiscall*)(void*,Word)>(originals[15])(self,target);
}
void __fastcall ChangeDescription(void* self,void*,Word id,bool notify) {
    Operation operation;
    if(Owner())ObserveCastRetire(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)));
    reinterpret_cast<void (__thiscall*)(void*,Word,bool)>(originals[10])(self,id,notify);
}
void __cdecl BeforeDead(Word unit) { if(Owner())ObserveCastRetire(unit); }
// Preserve the native ABI verbatim, including flags and all registers. Only
// event2 writes the dead flag at these two concrete stock callback entries.
__declspec(naked) void DeadMethod() {
    __asm {
        pushfd
        pushad
        push ecx
        call BeforeDead
        add esp,4
        popad
        popfd
        jmp dword ptr [deadMethodOriginal]
    }
}
__declspec(naked) void DeadEvent() {
    __asm {
        pushfd
        pushad
        cmp dword ptr [esp+56],2
        jne done
        push [esp+44]
        call BeforeDead
        add esp,4
    done:
        popad
        popfd
        jmp dword ptr [deadEventOriginal]
    }
}
__declspec(naked) void DeadOrder() {
    __asm {
        pushfd
        pushad
        cmp dword ptr [esp+56],2
        jne done
        push [esp+44]
        call BeforeDead
        add esp,4
    done:
        popad
        popfd
        jmp dword ptr [deadOrderOriginal]
    }
}
__declspec(naked) void DeadFlags() {
    __asm {
        pushfd
        pushad
        push [esp+40]
        call BeforeDead
        add esp,4
        popad
        popfd
        jmp dword ptr [deadFlagsOriginal]
    }
}
void __fastcall Clear(void* self,void*,Word channel) {
    Operation operation;
    const Word unit=static_cast<Word>(reinterpret_cast<std::uintptr_t>(self));
    const auto frame=reinterpret_cast<std::uintptr_t>(_AddressOfReturnAddress());
    Word id{};
    if(Owner()&&!(unit==cancelActor&&frame==cancelFrame)&&Read(unit,0x70,id))casts.Interrupted(id,"stock clear-orders");
    reinterpret_cast<void (__thiscall*)(void*,Word)>(originals[8])(self,channel);
}
void __fastcall CancelOrder(void* self,void*,Word order) {
    Operation operation;
    Word unit{};
    try {
        if(operation.active&&Read(static_cast<Word>(reinterpret_cast<std::uintptr_t>(self)),4,unit))
            cosmeticCleanup.Cancelling(unit,order);
    } catch(...) { fault=true;cosmeticCleanup.Reset(); }
    // A callback can refuse cancellation. Only actual unlink authorizes cleanup;
    // the order pointer is not dereferenced after native cancellation returns.
    reinterpret_cast<void (__thiscall*)(void*,Word)>(originals[16])(self,order);
}
void RefreshCosmeticOwner(Word unit) {
    TracePlacementStage(unit,49,"Arrival cleanup: stock state refresh");
    if(Owner()&&cosmeticProfile)
        reinterpret_cast<void (__cdecl*)(Word,int)>(cosmeticProfile->refresh)(unit,0);
}
bool CaptureCosmeticOwner(Word unit,Word order,CosmeticPose& pose) {
    const bool captured=Owner()&&cosmeticState.Capture(unit,order,pose);
    if(captured)TracePlacementStage(unit,50,"Arrival cleanup: pose captured");
    return captured;
}
bool CurrentCosmeticOwner(const CosmeticPose& pose) {
    const bool current=Owner()&&cosmeticState.Current(pose);
    TracePlacementStage(pose.actor.address,current?51:52,current?"Arrival cleanup: current":"Arrival cleanup: replaced/invalidated");
    return current;
}
// Called only by the actual stock timer dispatch site; nested callbacks receive
// a separate scope and cannot borrow the suspended caller's authorization.
Word __cdecl InvokeThread(Word value,void* definition,void* frame) {
    Operation operation;
    Identity a,t;bool entered=false;
    if(Owner()&&bindings.agent) {
        auto* arguments=static_cast<unsigned char*>(frame)+0x1C;
        Capture(bindings.agent(arguments,1),a);Capture(bindings.agent(arguments,2),t);
        const bool accepted=casts.EnterCallback(value,static_cast<Word>(reinterpret_cast<std::uintptr_t>(definition)),a,t);entered=true;
        if(static_cast<Word>(reinterpret_cast<std::uintptr_t>(definition))==bindings.movementCallback)
            TracePlacementStage(a.address,accepted?26:27,accepted?"Timer: callback authorized":"Timer: callback record rejected");
    }
    struct Exit { bool entered;~Exit(){if(entered)casts.LeaveCallback();} } exit{entered};
    return reinterpret_cast<Word (__thiscall*)(void*,void*)>(nativeProfile->invoke)(definition,frame);
}
__declspec(naked) void ThreadCall() {
    __asm {
        push [esp+4]
        push ecx
        push esi
        call InvokeThread
        add esp, 12
        ret 4
    }
}
// The stock emission callback keeps its animation in ESI immediately before
// its script call. Preserve all caller-visible registers except the ordinary
// thiscall volatile set, and expose that exact order only for this invocation.
Word __cdecl InvokeRelease(Word order,void* script,Word unit,Word target,Point point) {
    Scope scope(releaseOrder,Owner()?order:0);
    Identity a,t;Word action{},targetId{},flags{},kind{};
    const bool eligible=Owner()&&reinterpret_cast<std::uintptr_t>(script)==bindings.actionEngine+0x3C&&
        Capture(unit,a)&&Capture(target,t)&&Read(order,0x10,kind)&&kind==11&&
        Read(order,0x5C,action)&&action==bindings.action&&Read(order,0x60,targetId)&&targetId==t.id&&
        Read(order,0x6C,flags)&&(flags&1)&&casts.Release(a.id,order,action,targetId);
    Scope release(releaseUnit,eligible?unit:0);
    if(reinterpret_cast<std::uintptr_t>(script)==bindings.actionEngine+0x3C)
        {TracePlacementStage(unit,eligible?20:21,eligible?"Release: observed":"Release: cast record rejected");
        char detail[200]{};std::snprintf(detail,sizeof(detail),
            "Release inputs order=%08X kind=%u action=%08X expected=%08X target=%u capturedTarget=%u flags=%08X actor=%08X",
            order,kind,action,bindings.action,targetId,t.id,flags,a.address);
        TracePlacementStage(unit,53,detail);}
    return reinterpret_cast<Word (__thiscall*)(void*,Word,Word,Point)>(originals[1])(script,unit,target,point);
}
__declspec(naked) void ReleaseCall() {
    __asm {
        push [esp+16]
        push [esp+16]
        push [esp+16]
        push [esp+16]
        push ecx
        push esi
        call InvokeRelease
        add esp, 24
        ret 16
    }
}
__declspec(naked) void __cdecl Action(Word,Word,const char*) {
    __asm {
        push ebx
        mov ebx, [esp+8]
        mov eax, [esp+12]
        mov ecx, [esp+16]
        push 0
        push eax
        push ecx
        mov eax, dword ptr [nativeDoAction]
        call eax
        add esp, 12
        pop ebx
        ret
    }
}
__declspec(naked) void __cdecl Cancel(Word,Word*) {
    __asm {
        mov ecx, [esp+4]
        mov eax, [esp+8]
        lea edx, [esp-16]
        mov [eax], edx
        mov eax, dword ptr [nativeCancel]
        call eax
        ret
    }
}
}

StockCasts& MajestyCheckedPlacement::NativeCasts(){return casts;}
std::uint64_t MajestyCheckedPlacement::ObservedUnitEpoch(Word unit,Word id) {
    if(!Owner()||!unit||!id)return 0;
    auto i=epochs.find(id);
    if(i!=epochs.end()&&i->second.first==unit)return i->second.second;
    if(epochs.size()>=65536||serial==std::numeric_limits<std::uint64_t>::max()){fault=true;casts.Reset();return 0;}
    const auto epoch=++serial;epochs[id]={unit,epoch};return epoch;
}
bool MajestyCheckedPlacement::ConfigureCastBindings(const CastBindings& b) {
    if(!installed||!Owner()||!b.memory||!b.identity||!b.argument||!b.agent||!b.action||!b.actionEngine||!b.movementCallback)return false;
    if(bindings.memory==b.memory&&bindings.identity==b.identity&&bindings.argument==b.argument&&
        bindings.agent==b.agent&&bindings.action==b.action&&bindings.actionEngine==b.actionEngine&&
        bindings.movementCallback==b.movementCallback)return true;
    cosmeticCleanup.Configure({});casts.Reset();epochs.clear();bindings=b;return true;
}
void MajestyCheckedPlacement::ResetCastBindings(){if(installed&&Owner()){cosmeticCleanup.Configure({});casts.Reset();epochs.clear();bindings={};}}
void MajestyCheckedPlacement::CastBindingEpochChanged(){ResetCastBindings();}
void MajestyCheckedPlacement::ObserveCastRetire(Word unit) {
    if(Owner())cosmeticCleanup.Invalidate(unit);
    Word id{};if(Owner()&&Read(unit,0x70,id)){casts.InvalidateUnit(id);epochs.erase(id);}
}
void MajestyCheckedPlacement::ObserveCastUnlink(Word unit,Word order) {
#if defined(CAM_PLACEMENT_DIAGNOSTIC)
    if(Owner()) {
        CosmeticPose pose;
        if(cosmeticState.Capture(unit,order,pose))TracePlacementStage(unit,61,"Arrival: selected private animation unlinked");
    }
#endif
    if(Owner())cosmeticCleanup.Unlinked(unit,order);
    Word id{};if(Owner()&&Read(unit,0x70,id))casts.Unlinked(id,order);
}
std::uint64_t MajestyCheckedPlacement::ObserveCastSubmissionStarting(Word unit,Word order) {
    if(!Owner())return 0;
    cosmeticCleanup.Invalidate(unit);
    Word id{},kind{};
    if(Owner()&&Read(unit,0x70,id)&&Read(order,0x10,kind)) {
        // Only a child of the currently processed action may retain its cast.
        // New or unrelated stock submissions invalidate before their callbacks.
        Word table{},callback{},qualifier{};
        const bool turn=kind==1&&pendingProfile&&Read(order,0,table)&&table==pendingProfile->table&&
            Read(order,0x2C,callback)&&callback==0x1008&&Read(order,0x1C,qualifier)&&qualifier==1;
        if(!((kind==11||turn)&&processingUnit==unit&&processingOrder))casts.Interrupted(id,"new unrelated order submission");
    }
    return casts.Authorizations().Invalidation();
}
bool MajestyCheckedPlacement::EnterCastOperation() {
    if(!Owner())return false;
    cosmeticCleanup.Enter();return true;
}
void MajestyCheckedPlacement::LeaveCastOperation(bool normal) {
    // Unwind the matching scope even if a nested callback set fault.
    try { cosmeticCleanup.Leave(normal&&!fault); }
    catch(...) { fault=true;cosmeticCleanup.Reset(); }
}
bool MajestyCheckedPlacement::ConfigureCosmeticCleanup(const CosmeticActionState& state) {
    if(!Owner())return false;
    if(!cosmeticProfile||state.types!=cosmeticTypes||state.memory!=bindings.memory||
        state.identity!=bindings.identity||!state.identity||!state.approvedImage||!state.Action()) {
        cosmeticCleanup.Configure({});cosmeticState={};return false;
    }
    if(cosmeticState.actorDescriptor!=state.actorDescriptor||cosmeticState.actionDescriptor!=state.actionDescriptor||
        cosmeticState.actionEngine!=state.actionEngine||cosmeticState.actionId!=state.actionId||
        cosmeticState.requestedSet!=state.requestedSet||cosmeticState.completionSet!=state.completionSet||
        cosmeticState.approvedImage!=state.approvedImage)
        cosmeticCleanup.Reset();
    cosmeticState=state;
    cosmeticCleanup.Configure({&CaptureCosmeticOwner,&CurrentCosmeticOwner,&RefreshCosmeticOwner});return true;
}
bool MajestyCheckedPlacement::CosmeticAvailable(Word unit) {
    return Owner()&&cosmeticState.CanStart(unit,false);
}
namespace {
bool ContainsOrder(Word unit,Word channel,Word wanted) {
    Word stack{},ownerUnit{},head{},link{};
    if(channel>=3||!Read(unit,0x98+channel*4,stack)||!Read(stack,4,ownerUnit)||ownerUnit!=unit||
        !Read(stack,0x1C,head)||!head||!Read(head,0,link))return false;
    std::set<Word> seen;
    while(link!=head) {
        Word order{};
        if(seen.size()>=65536||!seen.insert(link).second||!Read(link,8,order))return false;
        if(order==wanted)return true;
        if(!Read(link,0,link))return false;
    }
    return false;
}
}
void MajestyCheckedPlacement::ObserveCastSubmit(Word unit,Word channel,Word order,Word result,std::uint64_t revision) {
#if defined(CAM_PLACEMENT_DIAGNOSTIC)
    if(Owner()&&order&&result==order&&cosmeticState.actionId) {
        Word kind{},action{};
        if(Read(order,0x10,kind)&&((kind==11&&Read(order,0x5C,action))||(kind==10&&Read(order,0x34,action)))&&action==cosmeticState.actionId) {
            CosmeticPose pose;const bool matched=kind==11&&cosmeticState.Capture(unit,order,pose);
            Word partIndex{},collection{},parts{},partSet{},partImage{},frame{};
            if(kind==11&&Read(order,0x38,partIndex)&&Read(unit,0x28,collection)&&Read(collection,0x1C,parts)&&partIndex<16) {
                Read(parts+partIndex*0x40,4,partImage);Read(parts+partIndex*0x40,8,partSet);Read(parts+partIndex*0x40,0x20,frame);
            }
            char detail[220]{};std::snprintf(detail,sizeof(detail),"Arrival installed kind=%u channel=%u order=%08X matched=%u part=%u image=%08X set=%08X frameword=%08X",kind,channel,order,matched,partIndex,partImage,partSet,frame);
            TracePlacementStage(unit,kind==10?59:60,detail);
        }
    }
#endif
    if(!Owner()||!bindings.action||result!=order||!order||revision!=casts.Authorizations().Invalidation())return;
    Identity actor,target;Word kind{},action{},targetId{};
    if(!Capture(unit,actor)||!ContainsOrder(unit,channel,order)||!Read(order,0x10,kind))return;
    if(kind==10&&Read(order,0x34,action)&&Read(order,0x3C,targetId)&&request.active&&
        Same(request.actor,actor)&&request.target.id==targetId&&action==bindings.action&&channel==1) {
        request.submitted=true;
        TracePlacementStage(unit,18,"Submission: action order observed");
        const bool recorded=Capture(request.target.address,target)&&Same(request.target,target)&&casts.Submitted(actor,target,action,order);
        TracePlacementStage(unit,recorded?54:55,recorded?"Submission: authorization recorded":"Submission: authorization rejected");
    } else if(kind==1&&pendingProfile&&processingUnit==unit&&processingOrder) {
        Word table{},callback{},qualifier{};
        if(Read(order,0,table)&&table==pendingProfile->table&&Read(order,0x2C,callback)&&callback==0x1008&&
            Read(order,0x1C,qualifier)&&qualifier==1&&Read(order,0x50,action)&&Read(order,0x54,targetId)&&
            casts.Turning(actor.id,processingOrder,order,action,targetId))
            TracePlacementStage(unit,58,"Submission: stock pending-turn transfer observed");
        else casts.Interrupted(actor.id,"unmatched turn submission");
    } else if(kind==11&&Read(order,0x5C,action)&&Read(order,0x60,targetId)&&processingUnit==unit&&processingOrder&&
        casts.Animation(actor.id,processingOrder,order,action,targetId)) {
        // Literal child of the currently executing stock action order.
        TracePlacementStage(unit,19,"Submission: animation transfer observed");
    } else casts.Interrupted(actor.id);
}
bool MajestyCheckedPlacement::BeginObservedCast(const Identity& actor,const Identity& target,Word actorProxy,Word targetProxy,const char* actionName) {
#if defined(CAM_PLACEMENT_DIAGNOSTIC)
    casts.diagnostic=&TracePlacementStage;
#endif
    if(!installed||!Owner()||request.active||!actorProxy||!targetProxy||!actionName||casts.Pending(actor.id))return false;
    Identity currentActor,currentTarget;
    if(!Capture(actor.address,currentActor)||!Capture(target.address,currentTarget)||
        !Same(actor,currentActor)||!Same(target,currentTarget))return false;
    FailureGuard failure;
    request={actor,target,true,false};
    struct Exit { ~Exit(){request={};} } exit;
    Action(actorProxy,targetProxy,actionName);
    // Dispatch may synchronously cancel itself. Once the stock action was
    // invoked this is a started attempt, never a side-effect-free refusal.
    return true;
}
void MajestyCheckedPlacement::CancelObservedCast(Word actor) {
    if(!installed||!Owner()||cancelActor){fault=true;casts.Reset();return;}
    Scope scope(cancelActor,actor);cancelFrame=0;Cancel(actor,&cancelFrame);cancelFrame=0;
}
bool MajestyCheckedPlacement::BeginCosmeticAction(const Identity& expected,Word proxy,const char* name) {
    if(!Owner()||!proxy||!name||!cosmeticState.Action())return false;
    Identity current;
    if(!Capture(expected.address,current)||!Same(expected,current)||
        current.description!=cosmeticState.actorDescriptor||!cosmeticState.CanStart(current.address))return false;
    Operation operation;FailureGuard failure;
    // Same stock DoAction bridge, targeting this actor. No queued Manager work,
    // timer, saved token or replay on world attachment is created.
    Action(proxy,proxy,name);return true;
}

namespace {
struct Window { Word address;unsigned count;unsigned char bytes[10];void* hook;int original; };
Window windows[]={
    {0,0,{},reinterpret_cast<void*>(&Process),0},
    {0,0,{},reinterpret_cast<void*>(&Schedule),2},
    {0,0,{},reinterpret_cast<void*>(&ResetFunction),3},
    {0,0,{},reinterpret_cast<void*>(&DestroyFunction),4},
    {0,0,{},reinterpret_cast<void*>(&Player),5},
    {0,0,{},reinterpret_cast<void*>(&Team),6},
    {0,0,{},reinterpret_cast<void*>(&Attribute),7},
    {0,0,{},reinterpret_cast<void*>(&Clear),8},
    {0,0,{},reinterpret_cast<void*>(&RemovalRequested),9},
    {0,0,{},reinterpret_cast<void*>(&ChangeDescription),10},
    {0,0,{},reinterpret_cast<void*>(&DeadMethod),11},
    {0,0,{},reinterpret_cast<void*>(&DeadEvent),12},
    {0,0,{},reinterpret_cast<void*>(&DeadOrder),13},
    {0,0,{},reinterpret_cast<void*>(&DeadFlags),14},
    {0,0,{},reinterpret_cast<void*>(&Retarget),15},
    {0,0,{},reinterpret_cast<void*>(&ReleaseCall),-1},
    {0,0,{},reinterpret_cast<void*>(&ThreadCall),-1},
    {0,6,{0x56,0x8B,0x74,0x24,0x08,0x57},reinterpret_cast<void*>(&CancelOrder),16},
    {0,6,{0x51,0x53,0x8B,0x5C,0x24,0x14},reinterpret_cast<void*>(&TurnProcess),17},
};
bool Patch(const Window& w,bool restore) {
    DWORD previous{};
    auto* address=reinterpret_cast<unsigned char*>(w.address);
    if(!VirtualProtect(address,w.count,PAGE_EXECUTE_READWRITE,&previous))return false;
    if(restore)std::memcpy(address,w.bytes,w.count);
    else {
        address[0]=w.original<0?0xE8:0xE9;
        const auto delta=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(w.hook)-w.address-5);
        std::memcpy(address+1,&delta,4);std::memset(address+5,0x90,w.count-5);
    }
    FlushInstructionCache(GetCurrentProcess(),address,w.count);
    DWORD ignored{};return VirtualProtect(address,w.count,previous,&ignored)!=0;
}
}
bool MajestyCheckedPlacement::InstallCastObservers(MajestyBuildId build) {
    if(installed||fault||!AuditedStartup(build))return false;
    // Full cast bodies are certified at startup; guard every write window too.
    nativeProfile=CastProfileFor(build);
    pendingProfile=PendingCastFor(build);
    cosmeticProfile=CosmeticActionsFor(build);
    cosmeticTypes=CosmeticImagesFor(build);
    if(!nativeProfile||!cosmeticProfile||!CosmeticActionBytesMatch(*cosmeticProfile)||!pendingProfile||
        *reinterpret_cast<const Word*>(pendingProfile->table+0x18)!=pendingProfile->process||
        RelocationFingerprint(reinterpret_cast<const unsigned char*>(pendingProfile->process),380)!=pendingProfile->hash)return false;
    static_assert(sizeof(windows)/sizeof(windows[0])==19,"cast hook profile shape");
    windows[17].address=cosmeticProfile->cancelOrder;
    windows[18].address=pendingProfile->process;
    for(unsigned i=0;i<17;++i) {
        const auto& source=nativeProfile->windows[i];
        windows[i].address=source.address;windows[i].count=source.count;
        std::memcpy(windows[i].bytes,source.bytes,sizeof(source.bytes));
    }
    nativeDoAction=nativeProfile->doAction;nativeCancel=nativeProfile->cancel;
    for(const auto& w:windows)if(std::memcmp(reinterpret_cast<void*>(w.address),w.bytes,w.count))return false;
    auto* trampolines=static_cast<unsigned char*>(VirtualAlloc(nullptr,18*32,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    if(!trampolines)return false;
    originals[1]=reinterpret_cast<void*>(nativeProfile->release);
    for(const auto& w:windows)if(w.original>=0) {
        auto* t=trampolines+32*w.original;std::memcpy(t,w.bytes,w.count);t[w.count]=0xE9;
        const auto delta=static_cast<std::int32_t>(w.address+w.count-reinterpret_cast<std::uintptr_t>(t+w.count)-5);
        std::memcpy(t+w.count+1,&delta,4);originals[w.original]=t;
    }
    DWORD previous{};
    if(!VirtualProtect(trampolines,18*32,PAGE_EXECUTE_READ,&previous)){VirtualFree(trampolines,0,MEM_RELEASE);return false;}
    FlushInstructionCache(GetCurrentProcess(),trampolines,18*32);owner=GetCurrentThreadId();
    deadMethodOriginal=originals[11];deadEventOriginal=originals[12];
    deadOrderOriginal=originals[13];deadFlagsOriginal=originals[14];
    const unsigned count=sizeof(windows)/sizeof(windows[0]);unsigned changed=0;
    for(;changed<count;++changed)if(!Patch(windows[changed],false))break;
    if(changed!=count){bool restored=true;
        for(unsigned i=0;i<=changed&&i<count;++i)restored=Patch(windows[i],true)&&restored;
        if(restored)VirtualFree(trampolines,0,MEM_RELEASE);fault=true;return false;}
    installed=true;return true;
}
