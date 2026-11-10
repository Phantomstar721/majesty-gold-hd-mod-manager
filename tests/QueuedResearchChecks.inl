// Actual beta2 research executor body. Six relative calls and two absolute
// globals are relocated to explicit fixture services; virtual calls use fixtures.
#include <type_traits>

namespace QueuedResearchChecks {
using StockCompletionCallback = std::uint32_t (__cdecl*)(
    std::uint32_t, void*, std::uint32_t, std::uint32_t, std::uint32_t);
static_assert(std::is_same<decltype(&ResearchCompletionBridge), StockCompletionCallback>::value,
    "The stock event dispatcher consumes the research completion return value");
unsigned char building[0xA0]={}, other[0xA0]={}, player[0x168]={};
void* buildingTable[100]={};void* playerMethods[10]={};void* ownerMethods[8]={};void* processorMethods[36]={};
struct Object{void** table;} owner={ownerMethods},processor={processorMethods};
int current=77,started=20,duration=40,gold=500,debits=0,schedules=0,notices=0;
unsigned clock=100;void* ui=reinterpret_cast<void*>(1);
bool existing=false;
int completions=0;
unsigned completionReturn=0;
std::map<unsigned, void*> completionRegistry;
std::vector<void*> completionAllocations;
unsigned completionTemplate[5]={15000,1,200,0,0x18425041};
bool templateAvailable=true;
int queuedEffects=0, queuedCancels=0;
bool queuedPending=false;
int paidStarts=0, paidSchedules=0, paidReagents=5;
bool paidPublished=true, paidCommit=true;
bool PaidOrderPresent(void*) { return existing; }
bool PaidStatus(const char*,void*,bool hasOperation,int operation,unsigned* result,bool) {
    assert(hasOperation);
    *result=0;
    if(operation==0) { *result=queuedPending || gold<5000 || paidReagents<5 ? 3u : 0u; }
    if(operation==1) {
        if(!paidCommit || queuedPending || gold<5000 || paidReagents<5) { *result=3; return true; }
        queuedPending=true;gold-=5000;paidReagents-=5;++paidStarts;
    }
    if(operation==3) queuedPending=false;
    if(operation==2) {
        assert(current==0 && duration==0);
        if(queuedPending) {queuedPending=false;++queuedEffects;}
    }
    return true;
}
bool __fastcall PaidExecute(void*,void*,void*,unsigned command) {
    assert(queuedPending && gold==0 && paidReagents==0); // payment precedes stock charge
    ++paidSchedules;current=command;duration=30000;existing=paidPublished;return true;
}
bool QueuedStatus(const char*,void* unit,bool hasCommand,int operation,unsigned* result,bool) {
    assert(unit==building && hasCommand);
    if(operation==2 || operation==3) assert(current==0 && duration==0);
    if(operation==2 && queuedPending) { queuedPending=false; ++queuedEffects; }
    if(operation==3) { queuedPending=false; ++queuedCancels; }
    *result=0; return true;
}
const unsigned* __cdecl SavedCompletionDescriptor(unsigned command) {
    if(command==5000) return templateAvailable ? completionTemplate : nullptr;
    return static_cast<const unsigned*>(completionRegistry[command]);
}
void** __fastcall InsertCompletionDescriptor(void* registry,void*,const unsigned* command) {
    assert(registry==&completionRegistry);
    return &completionRegistry[*command];
}
void* __cdecl AllocateCompletionDescriptor(std::size_t size) {
    assert(size==20);
    auto* allocation=std::malloc(size);
    completionAllocations.push_back(allocation);
    return allocation;
}
const unsigned* __cdecl CompletionDescriptor(unsigned command){assert(command==0x6000);return researchDescriptor;}
unsigned __cdecl Complete(unsigned,void* unit,unsigned,unsigned,unsigned reason){
    assert(unit==building);
    ++completions;
    if(reason==2){assert(current==0x6000);researchComplete=1;current=0;duration=0;}
    return completionReturn;
}
unsigned descriptor[5]={15000,1,200,0,0x18425041};
const unsigned char executorBody[]={0x51,0x53,0x56,0x8B,0x74,0x24,0x10,0x8B,0x06,0x8B,0x90,0x80,0x01,0x00,0x00,0x68,0x05,0x40,0x00,0x00,0x89,0x4C,0x24,0x0C,0x6A,0x01,0x8B,0xCE,0x32,0xDB,0xFF,0xD2,0x85,0xC0,0x0F,0x85,0x01,0x01,0x00,0x00,0x8B,0x44,0x24,0x14,0x55,0x57,0x50,0xE8,0xAC,0x8C,0xFC,0xFF,0x8B,0xD8,0x8B,0x4B,0x08,0x56,0x51,0xE8,0x60,0x6B,0xFC,0xFF,0x8B,0x8E,0x94,0x00,0x00,0x00,0x8B,0x11,0x8B,0xE8,0x8B,0x86,0x80,0x00,0x00,0x00,0x83,0xC4,0x0C,0x50,0x8B,0x42,0x18,0xFF,0xD0,0x8B,0xF8,0x8B,0x17,0x8B,0x42,0x20,0x68,0x41,0x50,0x50,0x00,0x8B,0xCF,0xFF,0xD0,0x3B,0xC5,0x7C,0x78,0x8B,0x17,0x8B,0x42,0x18,0x55,0x68,0x41,0x50,0x50,0x00,0x8B,0xCF,0xFF,0xD0,0x8B,0x44,0x24,0x1C,0x01,0xAF,0x64,0x01,0x00,0x00,0x8B,0x16,0x8B,0x92,0x24,0x01,0x00,0x00,0x50,0x68,0x41,0x50,0x42,0x2C,0x8B,0xCE,0xFF,0xD2,0x8B,0x0D,0xDC,0x3F,0x7E,0x00,0x8B,0x06,0x8B,0x90,0x24,0x01,0x00,0x00,0x8B,0x3B,0x51,0x68,0x41,0x50,0x42,0x38,0x8B,0xCE,0xFF,0xD2,0x8B,0x06,0x8B,0x90,0x24,0x01,0x00,0x00,0x57,0x68,0x41,0x50,0x42,0x0D,0x8B,0xCE,0xFF,0xD2,0x8B,0x4C,0x24,0x10,0x8B,0x01,0x8B,0x50,0x78,0x6A,0x01,0x68,0x05,0x40,0x00,0x00,0x68,0x09,0x20,0x00,0x00,0x57,0x56,0xFF,0xD2,0x5F,0x5D,0x5E,0x5B,0x59,0xC2,0x08,0x00,0x8B,0x0D,0x4C,0xFE,0x7D,0x00,0x68,0xFF,0x00,0x00,0x00,0x68,0x00,0xFF,0x00,0x80,0x6A,0x01,0xE8,0x84,0xBA,0xF8,0xFF,0x8B,0xB6,0x80,0x00,0x00,0x00,0x68,0x06,0x01,0x00,0x00,0xE8,0xD4,0x68,0xF4,0xFF,0x8B,0xC8,0xE8,0xED,0x4B,0xF4,0xFF,0x6A,0x01,0x56,0x50,0xE8,0x84,0xBA,0xF8,0xFF,0x83,0xC4,0x0C,0x5F,0x5D,0x5E,0x32,0xC0,0x5B,0x59,0xC2,0x08,0x00,0x5E,0x8A,0xC3,0x5B,0x59,0xC2,0x08,0x00};
const unsigned* __cdecl Descriptor(unsigned command){assert(command==0x6000 || command==0x6001);return descriptor;}
int __cdecl Price(unsigned amount,void*){assert(amount==200);return amount;}
void __fastcall NoticeColor(void*,void*,unsigned,unsigned,unsigned){++notices;}
void* __cdecl Strings(){return reinterpret_cast<void*>(1);}
void* __fastcall Text(void*,void*,unsigned id){assert(id==0x106);return reinterpret_cast<void*>(2);}
void __cdecl Notice(void*,unsigned,unsigned){}
void* __fastcall Player(void*,void*,unsigned id){assert(id==7);return player;}
int __fastcall Gold(void*,void*,unsigned attr){assert(attr==0x00505041);return gold;}
void __fastcall Debit(void*,void*,unsigned attr,unsigned value){assert(attr==0x00505041);gold-=value;++debits;}
void* __fastcall Order(void*,void*,unsigned flag,unsigned id){assert(flag==1 && id==0x4005);return existing ? building : nullptr;}
void __fastcall Write(void*,void*,unsigned attr,int value){
    if(attr==kCurrentResearchAttributeId)current=value;
    else if(attr==kResearchStartedAtAttributeId)started=value;
    else {assert(attr==kResearchDurationAttributeId);duration=value;}
}
int __fastcall Read(void*,void*,unsigned attr,unsigned){
    if(attr==0x18425041)return researchComplete;
    if(attr==kCurrentResearchAttributeId)return current;
    if(attr==kResearchStartedAtAttributeId)return started;
    assert(attr==kResearchDurationAttributeId);return duration;
}
bool EmploymentDenied(const char* symbol, void*, bool hasCommand, int command, unsigned* result, bool) {
    assert(std::strcmp(symbol,"MM_TestEmployment_Admit")==0 && hasCommand && command==8009);
    *result=0;return true;
}
bool __fastcall Schedule(void*,void*,void* unit,unsigned time,unsigned event,unsigned order,unsigned flag){
    assert(unit==building && time==15000 && event==0x2009 && order==0x4005 && flag==1);++schedules;return true;
}
void Run(){
    auto* code=static_cast<unsigned char*>(VirtualAlloc(nullptr,sizeof(executorBody),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));assert(code);
    std::memcpy(code,executorBody,sizeof(executorBody));
    const auto call=[code](unsigned offset,const void* target){assert(code[offset]==0xE8);*reinterpret_cast<int*>(code+offset+1)=static_cast<int>(reinterpret_cast<std::uintptr_t>(target)-reinterpret_cast<std::uintptr_t>(code+offset+5));};
    call(0x2F,reinterpret_cast<void*>(&Descriptor));call(0x3B,reinterpret_cast<void*>(&Price));
    call(0xF7,reinterpret_cast<void*>(&NoticeColor));call(0x107,reinterpret_cast<void*>(&Strings));
    call(0x10E,reinterpret_cast<void*>(&Text));call(0x117,reinterpret_cast<void*>(&Notice));
    *reinterpret_cast<unsigned*>(code+0x9A)=reinterpret_cast<unsigned>(&clock);
    *reinterpret_cast<unsigned*>(code+0xE7)=reinterpret_cast<unsigned>(&ui);
    DWORD protection=0;assert(VirtualProtect(code,sizeof(executorBody),PAGE_EXECUTE_READ,&protection));FlushInstructionCache(GetCurrentProcess(),code,sizeof(executorBody));
    auto execute=reinterpret_cast<StockResearchExecution>(code);
    buildingTable[0x180/4]=reinterpret_cast<void*>(&Order);buildingTable[0x124/4]=reinterpret_cast<void*>(&Write);
    ownerMethods[0x18/4]=reinterpret_cast<void*>(&Player);playerMethods[0x20/4]=reinterpret_cast<void*>(&Gold);playerMethods[0x18/4]=reinterpret_cast<void*>(&Debit);
    processorMethods[0x78/4]=reinterpret_cast<void*>(&Schedule);
    *reinterpret_cast<void***>(building)=buildingTable;*reinterpret_cast<void***>(player)=playerMethods;
    *reinterpret_cast<unsigned*>(building+0x70)=123;*reinterpret_cast<unsigned*>(building+0x80)=7;*reinterpret_cast<void**>(building+0x94)=&owner;
    std::memcpy(other,building,sizeof(building));
    const auto originalRead=profile.readPackedAttributeRva;profile.readPackedAttributeRva=reinterpret_cast<std::uintptr_t>(&Read);
    const auto begin=[](){ResearchPair();parent.context=child.context=building;*reinterpret_cast<unsigned*>(building+0x7C)=g_stockControllerRegistry.panels[0].buildingFamilyId;current=0;started=20;duration=0;gold=500;debits=schedules=notices=0;existing=false;SecondaryPanelControllerControl(&child,nullptr,0x6000);assert(g_researchOwner.pending && submitCount==1);};
    begin();gold=10;
    // Before-fix witness: the actual native insufficient-funds branch leaves
    // no tuple; ordinary capture cannot release the private pending owner.
    assert(!execute(&processor,building,0x6000));
    assert(notices==1 && debits==0 && schedules==0 && current==0 && duration==0);
    assert(!CaptureSubmittedResearch() && g_researchOwner.pending);
    SecondaryPanelControllerControl(&child,nullptr,0x6000);assert(submitCount==1);
    // The shared outcome adapter consumes only this exact rejected request.
    begin();gold=10;const int refreshed=refreshCount;
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6000));
    assert(!PrivateResearchIsActive() && !g_researchOwner.context && debits==0 && schedules==0 && gold==10);
    assert(current==0 && started==20 && duration==0 && refreshCount>refreshed);
    gold=500;SecondaryPanelControllerControl(&child,nullptr,0x6000);assert(submitCount==2 && g_researchOwner.pending);
    assert(ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6000));
    assert(g_researchOwner.pending && debits==1 && schedules==1 && gold==300);
    assert(CaptureSubmittedResearch() && !g_researchOwner.pending);
    assert(current==0x6000 && started==100 && duration==15000);
    // Losing all DLL state (save/reload) must not lose accepted research.
    g_researchOwner={};
    assert(PrivateResearchMatches(building,&g_stockControllerRegistry.researchRows[0]));
    SecondaryPanelControllerControl(&child,nullptr,0x6000);assert(submitCount==2);
    begin();gold=10;
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,other,0x6000));assert(g_researchOwner.pending && g_researchOwner.context==building);
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6001));assert(g_researchOwner.pending);
    existing=true;
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6000));assert(!PrivateResearchIsActive() && !debits);
    begin();duration=7000;current=0; // recruitment won the queued race
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6000));
    assert(!g_researchOwner.pending && debits==0 && schedules==0 && duration==7000);
    begin();
    const auto oldLists=g_stockControllerRegistry.liveAgentLists;
    const auto oldScalar=g_questBoardScalarEvaluator;
    const auto oldOpener=g_stockControllerRegistry.panels[0].openCommandId;
    g_stockControllerRegistry.panels[0].openCommandId=8009;
    QuestBoard employment={};employment.parentDialogId=g_stockControllerRegistry.panels[0].parentDialogId;
    employment.actionUsesPair=true;employment.openCommandId=31300;
    employment.admissionCallbackSymbol="MM_TestEmployment_Admit";employment.gatedControlIds={8009};
    g_stockControllerRegistry.liveAgentLists={employment};g_questBoardScalarEvaluator=&EmploymentDenied;
    assert(EmploymentCommandAllowed(building,employment.parentDialogId,0x1F47)); // upgrades unaffected
    assert(!ExecutePrivateResearchWithOutcome(execute,&processor,building,0x6000));
    assert(!g_researchOwner.pending && debits==0 && schedules==0 && gold==500 && duration==0);
    // Restored stock fields, no process-local owner: completion and cancellation
    // still consume the same research and leave the building available.
    const auto oldCompletion=g_stockResearchCompletion;
    const auto oldResolver=g_resolveResearchDescriptorTrampoline;
    const auto registeredDescriptors=g_privateResearchDescriptors;
    g_stockResearchCompletion=&Complete;
    g_resolveResearchDescriptorTrampoline=reinterpret_cast<std::uintptr_t>(&CompletionDescriptor);
    for(unsigned reason : {2u,1u}) {
        g_researchOwner={};current=0x6000;duration=15000;researchComplete=0;
        // World exit destroys descriptor registration before cancelling orders.
        // Cancellation must not enter the resolver or require borrowed data.
        if(reason==1) {
            g_privateResearchDescriptors.clear();
            g_resolveResearchDescriptorTrampoline=0;
        }
        ResearchCompletionBridge(0,building,0,0,reason);
        assert(current==0 && duration==0);
        assert(researchComplete==(reason==2 ? 1 : 0));
    }
    assert(completions==2);
    // Cold-process save load: stock activity exists, but no AP69 setup has
    // occurred and no private descriptors have ever been registered.
    const auto oldMap=g_researchDescriptorRegistryMap;
    const auto oldInsert=g_researchDescriptorRegistryFindOrInsert;
    const auto oldNew=profile.stockOperatorNewRva;
    const bool oldObserved=g_privateResearchDescriptorsRegistered;
    auto& row=g_stockControllerRegistry.researchRows[0];
    const auto oldRow=row;
    row.descriptorTemplateControlId=row.completionTemplateControlId=5000;
    row.requiredLevel=2;row.price=350;
    g_privateResearchDescriptors={{&row,nullptr}};
    g_privateResearchDescriptorsRegistered=false;
    g_resolveResearchDescriptorTrampoline=reinterpret_cast<std::uintptr_t>(&SavedCompletionDescriptor);
    g_researchDescriptorRegistryMap=reinterpret_cast<std::uintptr_t>(&completionRegistry);
    g_researchDescriptorRegistryFindOrInsert=reinterpret_cast<std::uintptr_t>(&InsertCompletionDescriptor);
    profile.stockOperatorNewRva=reinterpret_cast<std::uintptr_t>(&AllocateCompletionDescriptor);
    completionRegistry.clear();completionAllocations.clear();templateAvailable=true;
    g_parentController=g_childController=0;
    g_parentPanelRecord=g_activePanelRecord=nullptr;
    g_secondaryPanelActive=0;
    for(int quest=0;quest<2;++quest) {
        // Second iteration models stock registry teardown/rebuild while the
        // DLL retains its previous borrowed descriptor identity.
        completionRegistry.clear();
        g_researchOwner={};current=0x6000;duration=15000;researchComplete=0;
        const int paid=debits,queued=schedules;
        assert(SavedCompletionDescriptor(0x6000)==nullptr); // old guard failed here
        ResearchCompletionBridge(0,building,0,0,2);
        assert(current==0 && duration==0 && researchComplete==1);
        assert(debits==paid && schedules==queued);
        const auto* registered=SavedCompletionDescriptor(0x6000);
        assert(registered==g_privateResearchDescriptors[0].descriptor);
        assert(registered[1]==2 && registered[2]==350 && registered[4]==0x18425041);
        const auto allocations=completionAllocations.size();
        assert(EnsurePrivateResearchCompletionDescriptor(&row));
        assert(completionAllocations.size()==allocations); // warm path never reallocates
    }
    assert(completions==4);
    // The stock dispatcher completes once, then sends removal only when the
    // callback returns zero. Exercise that consuming boundary, not just the
    // activity writes: a void bridge previously leaked a nonzero EAX here.
    {
        const auto earlier=completions;
        current=0x6000;duration=15000;researchComplete=0;
        unsigned liveOrders=1,completionEvents=0,removalEvents=0;
        while(liveOrders && completionEvents<2) {
            ++completionEvents;
            const auto result=ResearchCompletionBridge(0,building,0,0,2);
            if(result==0) {
                ++removalEvents;
                assert(ResearchCompletionBridge(0,building,0,0,1)==0);
                --liveOrders;
            }
        }
        assert(!liveOrders && completionEvents==1 && removalEvents==1);
        assert(current==0 && duration==0 && researchComplete==1);
        // Preserve the actual callee's full return word, even through private
        // logging/cleanup, rather than merely hardcoding success everywhere.
        completionReturn=0x71A20F03u;
        current=0x6000;duration=15000;researchComplete=0;
        assert(ResearchCompletionBridge(0,building,0,0,2)==completionReturn);
        assert(ResearchCompletionBridge(0,building,0,0,1)==completionReturn);
        completionReturn=0;
        completions=earlier;
    }
    // Occupied identities and unavailable stock templates still fail closed.
    completionRegistry[0x6000]=completionTemplate;
    assert(!EnsurePrivateResearchCompletionDescriptor(&row));
    completionRegistry.clear();templateAvailable=false;
    assert(!EnsurePrivateResearchCompletionDescriptor(&row));
    // Cancellation during teardown never needs a live registry or resolver.
    g_resolveResearchDescriptorTrampoline=0;g_privateResearchDescriptors.clear();
    current=0x6000;duration=15000;researchComplete=0;
    ResearchCompletionBridge(0,building,0,0,1);
    assert(current==0 && duration==0 && researchComplete==0 && completions==5);
    // Repeatable charge completion works without a panel, descriptor registry,
    // or process-local owner. It retires activity BEFORE the saved GPL callback.
    row.chargeMs=30000;row.price=0;row.savedActionSymbol="MM_QA_Fixture";
    g_questBoardScalarEvaluator=&QueuedStatus;
    queuedEffects=queuedCancels=0;
    for(unsigned reason : {2u,1u}) {
        g_researchOwner={};current=0x6000;duration=30000;
        queuedPending=true;researchComplete=0;
        assert(ResearchCompletionBridge(0,building,0,0,reason)==0);
        assert(current==0 && duration==0 && !queuedPending && researchComplete==0);
    }
    assert(queuedEffects==1 && queuedCancels==1 && completions==5);
    // Stock retired actors must not be passed back into GPL during teardown.
    *reinterpret_cast<unsigned*>(building+0x74)=4;
    current=0x6000;duration=30000;
    ResearchCompletionBridge(0,building,0,0,1);
    assert(current==0 && duration==0 && queuedCancels==1);
    *reinterpret_cast<unsigned*>(building+0x74)=0;
    // Optional upfront transaction: shared-slot and stock-order rejection happen
    // before debit; completion and restored completion never requote affordability.
    const auto oldOrderPresent=g_researchOrderPresent;
    g_researchOrderPresent=&PaidOrderPresent;
    g_questBoardScalarEvaluator=&PaidStatus;
    g_stockControllerRegistry.liveAgentLists.clear();
    row.startCallbackSymbol="Pay";row.quoteCallbackSymbol="CanPay";
    g_privateResearchDescriptors={{&row,researchDescriptor}};
    const auto paidExecute=reinterpret_cast<StockResearchExecution>(&PaidExecute);
    for(int failure=0;failure<4;++failure) {
        current=duration=0;existing=false;queuedPending=false;
        gold=5000;paidReagents=5;paidStarts=paidSchedules=0;paidPublished=true;paidCommit=true;
        if(failure==0) existing=true;
        if(failure==1) duration=15000;
        if(failure==2) gold=4999;
        if(failure==3) paidCommit=false;
        assert(!ExecutePrivateResearchWithOutcome(paidExecute,&processor,building,0x6000));
        assert(paidStarts==0 && paidSchedules==0 && paidReagents==5);
    }
    for(bool publish : {true,false}) {
        current=duration=0;existing=false;queuedPending=false;g_researchOwner={};
        gold=5000;paidReagents=5;paidStarts=paidSchedules=0;paidCommit=true;paidPublished=publish;
        assert(ExecutePrivateResearchWithOutcome(paidExecute,&processor,building,0x6000)==publish);
        assert(paidStarts==1 && paidSchedules==1 && gold==0 && paidReagents==0);
        if(publish) {
            assert(!ExecutePrivateResearchWithOutcome(paidExecute,&processor,building,0x6000));
            const auto effects=queuedEffects;
            g_researchOwner={}; // lost DLL UI state does not cause another debit
            ResearchCompletionBridge(0,building,0,0,2);
            assert(queuedEffects==effects+1 && paidStarts==1 && gold==0 && paidReagents==0);
        } else assert(!queuedPending && current==0 && duration==0); // stock nonrefund policy
    }
    g_researchOrderPresent=oldOrderPresent;
    row=oldRow;
    completionRegistry.clear();
    for(auto* allocation:completionAllocations) std::free(allocation);
    completionAllocations.clear();
    g_researchDescriptorRegistryMap=oldMap;
    g_researchDescriptorRegistryFindOrInsert=oldInsert;
    profile.stockOperatorNewRva=oldNew;
    g_privateResearchDescriptorsRegistered=oldObserved;
    // Completion above ran with the employment gate closed: admitted stock
    // research still finishes/cancels normally, without another unlock check.
    g_stockControllerRegistry.liveAgentLists=oldLists;g_questBoardScalarEvaluator=oldScalar;
    g_stockControllerRegistry.panels[0].openCommandId=oldOpener;
    g_privateResearchDescriptors=registeredDescriptors;
    g_stockResearchCompletion=oldCompletion;
    g_resolveResearchDescriptorTrampoline=oldResolver;
    profile.readPackedAttributeRva=originalRead;ResearchPair();VirtualFree(code,0,MEM_RELEASE);
}
}
