#include "PaidControllerFixture.h"
namespace PaidAcquisitionChecks { void Run(); }
namespace PaidChecks {
using namespace SovereignChecks;
unsigned char world[0x150]={};
PaidRecord submittedPaid{};
int gold=1000,debits=0,releases=0,stats=0;
bool hostile=true,lair=true,visible=true,makeSpell=true,retireSpell=false,nest=false,saveDuringCallback=false;
PaidCommand* currentCommand=nullptr;
void* World(){return world;}
void* ResolvePaid(std::uint32_t id){if(id==404 && !retireSpell)return spell;return Resolve(id);}
bool Lair(void*){return lair;}
bool Hostile(void*,std::uint32_t,void*){return hostile && visible;}
int __fastcall Attributes(void*,void*,std::uint32_t key,std::uint32_t){return key==0x0A555041 ? 0 : 100;}
std::uint32_t ContextPaid(std::uint32_t,std::uint32_t){return 9;}
void SubmitPaid(const PaidRecord& r){submittedPaid=r;}
void Release(PaidReference*){++releases;}
void Statistics(void*,std::uint32_t amount){assert(amount==500 || amount==0);++stats;}
bool existingBounty=false,failBounty=false;
int bountyCalls=0;
bool PrepareBounty(void*,void*,std::uint32_t price,std::uint32_t amount,std::uint32_t* remainder){
    ++bountyCalls;
    if(gold<static_cast<int>(price)||failBounty)return false;
    if(existingBounty){*remainder=price;return true;}
    gold-=amount;*remainder=price-amount;return true;
}
bool PaidCallback(const char* name,void* unit,void* source,void* target){
    assert(gold>=0 && debits==stats && g_sourceTargetExecution->dispatched);
    if(saveDuringCallback){
        PaidCommand restored{};MajestyPaidSourceTarget::Payload out{};
        restored.header={out.data(),32,MajestyPaidSourceTarget::CommandTag,1,0};restored.vtable=g_paidVtable+1;
        RestorePaidCommand(&restored,nullptr,SerializePaidCommand(currentCommand,nullptr));
        int before=debits;DispatchPaidCommand({&restored,nullptr});assert(debits==before);
    }
    return Callback(name,unit,source,target);
}
void __cdecl NativeExecute(std::uint32_t mode,std::uint32_t context,std::uint32_t player,
    std::uint32_t x,std::uint32_t y,std::uint32_t target,std::uint32_t cost){
    ++nativeCalls;
    if(mode==123){assert(g_sourceTargetExecution==nullptr && g_paidRecord==nullptr);return;}
    assert((cost==500 || cost==0) && target==303 && g_paidRecord==nullptr);
    if(gold<static_cast<int>(cost))return; // native affordability boundary stub
    if(nest){nest=false;ExecuteSourceTargetSovereignCommand(123,context,player,x,y,target,456);}
    if(makeSpell){assert(SourceTargetBirth(nullptr,nullptr,spell,victim));assert(!SourceTargetBirth(nullptr,nullptr,spell,victim));}
    gold-=cost;++debits; // only stock native executor owns this mutation
    PaidPostPayment(nullptr,nullptr,cost);
    PaidPostPayment(nullptr,nullptr,cost); // repeat delivery cannot repeat effect
    --stats; // second native statistics call above was only a hostile fixture
}
void __stdcall NativeDispatch(PaidReference ref){
    auto* c=ref.object;
    ExecuteSourceTargetSovereignCommand(c->mode,c->context,c->player,c->x,c->y,c->target,c->gold);
    Release(&ref);
}
void Dispatch(PaidRecord record){
    MajestyPaidSourceTarget::ToolbarPayload bytes{};
    PaidCommand command{};command.vtable=g_paidVtable+1;command.header={bytes.data(),32,MajestyPaidSourceTarget::CommandTag,1,0};
    SetPaidCommand(command,record);currentCommand=&command;
    DispatchPaidCommand({&command,nullptr});
    const int before=debits, callbacks=callbackCalls;
    DispatchPaidCommand({&command,nullptr});
    assert(debits==before && callbackCalls==callbacks && g_paidRecord==nullptr && g_sourceTargetExecution==nullptr);
}
int allocations=0,frees=0,owned=0,deleted=0;
bool failAllocation=false,failConstructor=false,failReference=false;
void* Allocate(std::size_t size){if(failAllocation)return nullptr;++allocations;return std::calloc(1,size);}
void Free(void* pointer){++frees;std::free(pointer);}
void* __fastcall DeleteCommand(PaidCommand* command,void*,unsigned release){
    ++deleted;LocalFree(command->header.bytes);if(release)Free(command);return command;
}
void Construct(void* storage,const PaidRecord& record){
    if(failConstructor)throw std::bad_alloc();
    auto* c=static_cast<PaidCommand*>(storage);SetPaidCommand(*c,record);
    c->header={LocalAlloc(LMEM_FIXED,28),28,0x3F1,1,0};
}
void Own(PaidReference* ref,void* command){
    if(failReference)throw std::bad_alloc();
    ref->object=static_cast<PaidCommand*>(command);ref->counter=reinterpret_cast<void*>(1);++owned;
}
PaidReference* __cdecl LegacyFactory(PaidReference* ref,std::uint32_t tag){assert(tag==0x3F1);ref->object=nullptr;return ref;}
void Ownership(){
    g_paidAllocate=&Allocate;g_paidFree=&Free;g_paidConstruct=&Construct;g_paidOwn=&Own;
    g_paidVtable[1]=reinterpret_cast<void*>(&DeleteCommand);g_paidFactory=&LegacyFactory;
    PaidReference ref{};
    assert(RestorePaidFactory(&ref,0x3F1)==&ref && allocations==0);
    RestorePaidFactory(&ref,MajestyPaidSourceTarget::CommandTag);
    assert(ref.object && ref.object->vtable==g_paidVtable+1 && ref.object->header.length==32);
    assert(ref.object->header.tag==MajestyPaidSourceTarget::CommandTag && ref.object->source==0 && owned==1);
    DeleteCommand(ref.object,nullptr,1);assert(allocations==frees && deleted==1);
    failAllocation=true;
    try{RestorePaidFactory(&ref,MajestyPaidSourceTarget::CommandTag);assert(false);}catch(const std::bad_alloc&){}
    failAllocation=false;failConstructor=true;
    try{RestorePaidFactory(&ref,MajestyPaidSourceTarget::CommandTag);assert(false);}catch(const std::bad_alloc&){}
    failConstructor=false;assert(allocations==frees && deleted==1);
    failReference=true;
    try{RestorePaidFactory(&ref,MajestyPaidSourceTarget::CommandTag);assert(false);}catch(const std::bad_alloc&){}
    failReference=false;assert(allocations==frees && deleted==2);
}
void Run(){
    Ownership();
    MajestyStockControllers::Registry parsed;
    std::string error;
    assert(MajestyStockControllers::ParseRegistry(kPaidControllerFixture,sizeof(kPaidControllerFixture),&parsed,&error));
    assert(parsed.sovereignTargetActions.size()==1 && parsed.sovereignTargetActions[0].sovereignGoldCost==500);
    assert(parsed.sovereignTargetActions[0].resourceKey.empty() && parsed.sovereignTargetActions[0].resourceCost==0);
    for(unsigned size=0;size<sizeof(kPaidControllerFixture);++size)
        assert(!MajestyStockControllers::ParseRegistry(kPaidControllerFixture,size,&parsed,&error));

    SovereignChecks::Run();
    auto& action=g_stockControllerRegistry.sovereignTargetActions[0];
    action.sourceTargetCallback="Private_Source_Target";action.requiredLevel=2;action.sovereignGoldCost=500;
    action.stockTargetMode=0x39327053;
    g_sourceTargetCallback=&PaidCallback;g_sourceTargetExecutor=&NativeExecute;
    g_sovereignUnitResolver=&ResolvePaid;g_paidWorld=&World;g_paidLair=&Lair;g_paidHostileVisible=&Hostile;
    g_paidSubmission=&SubmitPaid;g_paidContext=&ContextPaid;g_paidDispatcher=&NativeDispatch;
    g_paidReferenceRelease=&Release;g_paidStatistics=&Statistics;
    profile.readPackedAttributeRva=reinterpret_cast<std::uintptr_t>(&Attributes);
    for(auto* unit:{sourceA,sourceB,victim,spell}){
        *reinterpret_cast<std::uint32_t*>(unit+0x94)=reinterpret_cast<std::uintptr_t>(world);
    }
    *reinterpret_cast<std::uint32_t*>(sourceA+0x70)=101;
    *reinterpret_cast<std::uint32_t*>(sourceB+0x70)=102;
    *reinterpret_cast<std::uint32_t*>(victim+0x70)=303;
    *reinterpret_cast<std::uint32_t*>(spell+0x70)=404;
    g_pendingSovereignAction=&action;g_pendingSovereignBuilding=101;
    PaidAcquisitionChecks::Run();
    SubmitPrivateSovereignCommand(action.stockTargetMode,1,700,800,303,999);
    assert(submittedPaid.source==101 && submittedPaid.target==303 && submittedPaid.gold==500 && submittedPaid.context==9);
    // A ground-only click must not reuse the previous target, charge gold,
    // or reach native execution. Exact-unit acquisition is tested separately.
    const int callsBeforeGround=nativeCalls, goldBeforeGround=gold;
    submittedPaid={};
    SubmitPrivateSovereignCommand(action.stockTargetMode,1,700,800,0,999);
    assert(submittedPaid.source==0 && submittedPaid.target==0);
    assert(nativeCalls==callsBeforeGround && gold==goldBeforeGround);
    SubmitPrivateSovereignCommand(action.stockTargetMode,1,700,800,303,999);
    assert(submittedPaid.source==101 && submittedPaid.target==303);
    // Diagnostic reasons reuse the admission checks, without another query or
    // changing whether submission is allowed.
    assert(PaidActorsRejection(submittedPaid,action,sourceA,victim,world)==nullptr);
    lair=false;
    assert(std::strcmp(PaidActorsRejection(submittedPaid,action,sourceA,victim,world),"target-not-lair")==0);
    lair=true;hostile=false;
    assert(std::strcmp(PaidActorsRejection(submittedPaid,action,sourceA,victim,world),"target-team-or-visibility")==0);
    hostile=true;
    *reinterpret_cast<std::uint32_t*>(victim+0x84)=1;
    assert(std::strcmp(PaidActorsRejection(submittedPaid,action,sourceA,victim,world),"unit-contained")==0);
    *reinterpret_cast<std::uint32_t*>(victim+0x84)=0;
    // Actual serializer/restore maintains all eight independent words; malformed
    // length/tag clears a previously populated object, never retaining its source.
    PaidCommand original{},restored{};MajestyPaidSourceTarget::Payload buffer{};
    original.header={buffer.data(),32,MajestyPaidSourceTarget::CommandTag,1,0};SetPaidCommand(original,submittedPaid);
    auto* header=SerializePaidCommand(&original,nullptr);RestorePaidCommand(&restored,nullptr,header);
    assert(restored.source==101 && restored.target==303 && restored.gold==500);
    for(unsigned length=0;length<32;++length){header->length=length;RestorePaidCommand(&restored,nullptr,header);assert(!restored.source&&!restored.gold);}
    header->length=32;header->tag=0x3F1;RestorePaidCommand(&restored,nullptr,header);assert(!restored.source);
    g_pendingSovereignBuilding=102;g_pendingSovereignAction=nullptr; // selection/cancel does not retarget a queue entry
    int callbacks=callbackCalls;nest=true;saveDuringCallback=true;
    Dispatch(submittedPaid);assert(callbackCalls==callbacks+1 && callbackSource==sourceA && gold==500);
    saveDuringCallback=false;auto second=submittedPaid;second.source=102;
    Dispatch(second);assert(callbackCalls==callbacks+2 && callbackSource==sourceB && gold==0);
    Dispatch(second);assert(callbackCalls==callbacks+2 && debits==2); // queued affordability recheck
    gold=1000;const int before=nativeCalls;
    hostile=false;Dispatch(second);hostile=true;lair=false;Dispatch(second);lair=true;
    visible=false;Dispatch(second);visible=true;sourcePresent=false;Dispatch(second);sourcePresent=true;
    targetPresent=false;Dispatch(second);targetPresent=true;
    auto mismatch=second;mismatch.gold=1;Dispatch(mismatch);
    ExecuteSourceTargetSovereignCommand(second.mode,9,1,700,800,303,500); // no queued identity
    assert(nativeCalls==before && debits==2 && callbackCalls==callbacks+2);
    makeSpell=false;Dispatch(second);assert(debits==3 && callbackCalls==callbacks+2);
    makeSpell=true;retireSpell=true;Dispatch(second);retireSpell=false;
    assert(debits==4 && callbackCalls==callbacks+2); // stock debit retained; stale spell never delivered
    // Nested legacy dispatch cannot acquire an outer paid identity.
    PaidCommand legacy{};legacy.mode=123;const PaidRecord outer=second;
    g_paidRecord=&outer;DispatchPaidCommand({&legacy,nullptr});assert(g_paidRecord==&outer);g_paidRecord=nullptr;
    assert(releases>0 && !g_paidRecord && !g_sourceTargetExecution);
}
}
#include "PaidAcquisitionChecks.inl"
