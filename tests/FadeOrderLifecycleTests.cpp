// Executes bounded, hash-pinned stock fade/order bodies in a private process.
// Unit draw methods, notifications and stack removal are supplied test doubles.
// No game attachment, actor factory, native scheduler or save file is involved.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <vector>
#include <cstdio>
#include "../runtime/CosmeticActionCleanup.h"

using Word = std::uint32_t;
void Require(bool value, const char* message) { if(!value) throw std::runtime_error(message); }
struct Unit { void** table; Word draw; unsigned writes{}, notices{}, clears{}; };
struct Stack { void** table; unsigned removes{}; };
void __fastcall Get(Unit* unit, void*, Word* out) { *out=unit->draw; }
void __fastcall Set(Unit* unit, void*, const Word* value) { unit->draw=*value; ++unit->writes; }
void __fastcall Clear(Unit* unit, void*) { unit->draw=0; ++unit->clears; }
void __fastcall Notify(Unit* unit, void*) { ++unit->notices; }
void __fastcall Remove(Stack* stack, void*, void*) { ++stack->removes; }
struct Allocation {
    void* address{};
    ~Allocation(){if(address)VirtualFree(address,0,MEM_RELEASE);}
};
std::vector<unsigned char> Window(const char* path, Word va, std::size_t length=0xE5) {
    std::ifstream file(path,std::ios::binary);
    Require(bool(file),"missing executable fixture");
    std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(file)),{});
    Require(bytes.size()>=sizeof(IMAGE_DOS_HEADER),"truncated DOS header");
    IMAGE_DOS_HEADER dos{};std::memcpy(&dos,bytes.data(),sizeof(dos));
    Require(dos.e_lfanew>=0 && static_cast<std::size_t>(dos.e_lfanew)+sizeof(IMAGE_NT_HEADERS32)<=bytes.size(),"truncated PE header");
    IMAGE_NT_HEADERS32 pe{};std::memcpy(&pe,bytes.data()+dos.e_lfanew,sizeof(pe));
    Require(pe.Signature==IMAGE_NT_SIGNATURE && pe.OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC && pe.OptionalHeader.ImageBase==0x400000,"wrong executable format/base");
    const auto table=static_cast<std::size_t>(dos.e_lfanew)+24+pe.FileHeader.SizeOfOptionalHeader;
    for(unsigned index=0;index<pe.FileHeader.NumberOfSections;++index){
        const auto offset=table+index*sizeof(IMAGE_SECTION_HEADER);
        Require(offset+sizeof(IMAGE_SECTION_HEADER)<=bytes.size(),"truncated sections");
        IMAGE_SECTION_HEADER section{};std::memcpy(&section,bytes.data()+offset,sizeof(section));
        const Word rva=va-pe.OptionalHeader.ImageBase;
        if(rva<section.VirtualAddress)continue;
        const auto delta=static_cast<std::size_t>(rva-section.VirtualAddress);
        if(delta+length>section.SizeOfRawData || delta+length>section.Misc.VirtualSize)continue;
        const auto raw=section.PointerToRawData+delta;
        Require(raw+length<=bytes.size(),"truncated code");
        return {bytes.begin()+raw,bytes.begin()+raw+length};
    }
    throw std::runtime_error("missing fade handler");
}
void LoadCode(Allocation& code,const char* path,Word entry,std::size_t length,Word expectedHash,
              std::size_t clockOffset=0,Word expectedClock=0,Word* privateClock=nullptr) {
    auto bytes=Window(path,entry,length);Word hash=2166136261u;
    for(auto byte:bytes)hash=(hash^byte)*16777619u;
    Require(hash==expectedHash,"unreviewed stack lifecycle bytes");
    if(privateClock){
        Require(clockOffset+4<=bytes.size(),"clock operand outside code");
        Word oldClock{};std::memcpy(&oldClock,bytes.data()+clockOffset,4);
        Require(oldClock==expectedClock,"unexpected scheduler clock operand");
        const auto address=static_cast<Word>(reinterpret_cast<std::uintptr_t>(privateClock));
        std::memcpy(bytes.data()+clockOffset,&address,4);
    }
    code.address=VirtualAlloc(nullptr,length,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    Require(code.address!=nullptr,"stack fixture allocation failed");
    std::memcpy(code.address,bytes.data(),length);DWORD old{};
    Require(VirtualProtect(code.address,length,PAGE_EXECUTE_READ,&old)!=0,"stack fixture protection failed");
    FlushInstructionCache(GetCurrentProcess(),code.address,length);
}
struct EventStack {
    void** table; Unit* unit; void* cancel;
    unsigned count{}, processed{}, unlinked{}; Word events[4]{}; bool intercept{};
};
MajestyCheckedPlacement::CosmeticActionCleanup cosmeticCleanup;
bool cosmeticTest{},privatePose{};
unsigned cosmeticRefreshes{};
bool CaptureCosmetic(Word unit,Word order,MajestyCheckedPlacement::CosmeticPose& out) {
    out={{unit,1,7,0,9,11},order,17,18,19,0x90,20,21};return privatePose;
}
bool CurrentCosmetic(const MajestyCheckedPlacement::CosmeticPose&) {return privatePose;}
void RefreshCosmetic(Word) {++cosmeticRefreshes;privatePose=false;}
struct SubmitUnit {
    void** table; Word order[0x3C/4]{};
    unsigned created{},submitted{}; bool reject{};
};
Word* __fastcall CreateFade(SubmitUnit* unit,void*,Word kind) {
    Require(kind==14,"wrong native fade order type");
    ++unit->created;return unit->reject?nullptr:unit->order;
}
Word __fastcall SubmitFade(SubmitUnit* unit,void*,Word channel,Word* order) {
    Require(channel==1 && order==unit->order,"fade queued to wrong owner/channel");
    ++unit->submitted;
    // Deliberately return zero: the stock manager ignores the submission result.
    return 0;
}
void CheckSubmit(const char* path,Word entry,Word expectedHash) {
    Allocation code;LoadCode(code,path,entry,0x5E,expectedHash);
    void* table[0x18C/4+1]{};
    table[0x188/4]=reinterpret_cast<void*>(&CreateFade);
    table[0x18C/4]=reinterpret_cast<void*>(&SubmitFade);
    using Submit=bool (__thiscall*)(void*,SubmitUnit*,Word,Word,Word,Word);
    const auto submit=reinterpret_cast<Submit>(code.address);
    Require(!submit(nullptr,nullptr,10,500,0,0),"null fade owner accepted");
    for(Word target:{0u,10u}) {
        SubmitUnit unit{table};
        Require(submit(nullptr,&unit,target,500,0,0),"valid fade rejected");
        Require(unit.created==1 && unit.submitted==1,"fade not created/submitted once");
        Require(unit.order[0x10/4]==14 && unit.order[0x14/4]==500 &&
                unit.order[0x2C/4]==0 && unit.order[0x34/4]==target &&
                unit.order[0x38/4]==0,"fade fields/argument ordering changed");
        SubmitUnit rejected{table};rejected.reject=true;
        Require(!submit(nullptr,&rejected,target,500,0,0),"failed allocation accepted");
        Require(rejected.created==1 && !rejected.submitted,"failed allocation queued");
    }
}
int __fastcall EventDispatch(EventStack* stack,void*,void*,void*,Word event) {
    Require(stack->count<4,"too many event callbacks");
    stack->events[stack->count++]=event;
    // Standup's event2 callback normally selects its completion image. Supplied
    // here as a callback double; this fixture executes the real stack bodies.
    if(cosmeticTest&&event==2&&!stack->intercept)privatePose=false;
    return stack->intercept?1:0;
}
bool __fastcall EventProcess(void*,void*,Unit*,EventStack* stack,Word event) {
    Require(event<=1,"unexpected processor event");++stack->processed;return true;
}
void __fastcall EventUnlink(EventStack* stack,void*,void* order) {
    ++stack->unlinked;
    if(cosmeticTest){
        cosmeticCleanup.Unlinked(static_cast<Word>(reinterpret_cast<std::uintptr_t>(stack->unit)),
                                static_cast<Word>(reinterpret_cast<std::uintptr_t>(order)));
        std::memset(order,0xDD,0x3C); // retired order storage must not be reread
    }
}
void __fastcall EventCancel(EventStack* stack,void*,void* order) {
    if(cosmeticTest){
        cosmeticCleanup.Enter();
        cosmeticCleanup.Cancelling(static_cast<Word>(reinterpret_cast<std::uintptr_t>(stack->unit)),
                                  static_cast<Word>(reinterpret_cast<std::uintptr_t>(order)));
    }
    reinterpret_cast<void (__thiscall*)(void*,void*)>(stack->cancel)(stack,order);
    if(cosmeticTest)cosmeticCleanup.Leave();
}
void CheckStack(const char* path,Word cancel,Word complete,Word scheduler,Word clock,Word schedulerHash) {
    Allocation cancelCode,completeCode,schedulerCode;
    Word privateClock{};
    LoadCode(cancelCode,path,cancel,0x44,0x0A8F3E5A);
    LoadCode(completeCode,path,complete,0x2F,0xB4CF1939);
    LoadCode(schedulerCode,path,scheduler,0x31,schedulerHash,0xC,clock,&privateClock);
    void* table[0x58/4+1]{};void* orderTable[0x18/4+1]{};
    table[0x44/4]=reinterpret_cast<void*>(&EventDispatch);
    table[0x48/4]=reinterpret_cast<void*>(&EventCancel);
    table[0x58/4]=reinterpret_cast<void*>(&EventUnlink);
    orderTable[0x18/4]=reinterpret_cast<void*>(&EventProcess);
    Word order[0x3C/4]{};order[0]=static_cast<Word>(reinterpret_cast<std::uintptr_t>(orderTable));
    order[0x10/4]=14;Unit unit{};
    using Operation=void (__thiscall*)(void*,void*);
    for(bool intercept : {false,true}) {
        EventStack stack{table,&unit,cancelCode.address};stack.intercept=intercept;
        reinterpret_cast<Operation>(completeCode.address)(&stack,order);
        Require(stack.events[0]==2,"completion notification missing");
        Require(stack.count==(intercept?1u:2u),"completion/cancellation notification order changed");
        if(!intercept)Require(stack.events[1]==1,"cleanup notification missing");
        Require(stack.processed==(intercept?0u:1u) && stack.unlinked==(intercept?0u:1u),"cleanup/unlink sequence differs");
    }
    EventStack timer{table,&unit,cancelCode.address};
    order[8/4]=100;order[12/4]=50;privateClock=149;
    reinterpret_cast<Operation>(schedulerCode.address)(&timer,order);
    Require(timer.processed==0,"timer executed before interval elapsed");
    privateClock=150;
    reinterpret_cast<Operation>(schedulerCode.address)(&timer,order);
    Require(timer.processed==1,"timer missed due event");
    order[0x18/4]=1;
    reinterpret_cast<Operation>(schedulerCode.address)(&timer,order);
    Require(timer.processed==1,"disabled order executed");
    cosmeticTest=true;
    for(bool normalFinish:{false,true})for(bool intercepted:{false,true}) {
        cosmeticCleanup.Configure({CaptureCosmetic,CurrentCosmetic,RefreshCosmetic});
        cosmeticRefreshes=0;privatePose=true;
        std::memset(order,0,sizeof(order));
        order[0]=static_cast<Word>(reinterpret_cast<std::uintptr_t>(orderTable));order[0x10/4]=11;
        EventStack stack{table,&unit,cancelCode.address};stack.intercept=intercepted;
        cosmeticCleanup.Enter(); // outer native dispatch/clear operation
        if(normalFinish)reinterpret_cast<Operation>(completeCode.address)(&stack,order);
        else EventCancel(&stack,nullptr,order);
        Require(!cosmeticRefreshes,"refreshed inside native cancellation");
        cosmeticCleanup.Leave();
        Require(cosmeticRefreshes==(!normalFinish&&!intercepted?1u:0u),
                "cosmetic cleanup confused cancellation, completion or callback refusal");
    }
    cosmeticTest=false;
}
void CheckConcreteDraw(const char* path,Word unitTable,Word vehicleTable,Word buildingTable,
                       Word get,Word set,Word clear) {
    for (Word table:{unitTable,vehicleTable,buildingTable}) {
        const auto slots=Window(path,table+0x50,12);
        Word actual[3]{};std::memcpy(actual,slots.data(),12);
        Require(actual[0]==get && actual[1]==set && actual[2]==clear,"concrete unit draw slots changed");
    }
    Allocation getter,setter,clearer;
    LoadCode(getter,path,get,14,0xC22E5F4D);
    LoadCode(setter,path,set,12,0x8D3437F9);
    LoadCode(clearer,path,clear,12,0xFEEAB29D);
    using GetDraw=bool (__thiscall*)(void*,Word*);
    using SetDraw=void (__thiscall*)(void*,const Word*);
    using ClearDraw=void (__thiscall*)(void*);
    for (Word request:{0u,0x505u,0xA05u,0x01000505u,0x02000905u,0xFFFFFFFFu}) {
        Word unit[12];for (auto& value:unit)value=0xA5A5A5A5;
        reinterpret_cast<SetDraw>(setter.address)(unit,&request);
        Require(unit[0x24/4]==request,"draw setter did not copy complete word");
        Word result{};
        Require(reinterpret_cast<GetDraw>(getter.address)(unit,&result) && result==request,"draw getter differs");
        reinterpret_cast<ClearDraw>(clearer.address)(unit);
        // Native clear changes the mode byte and color byte only. It is neither
        // a zero assignment nor restoration of whatever appearance came before.
        Require(unit[0x24/4]==((request|0xFFu)&0x00FFFFFFu),"native clear word differs");
        for (unsigned i=0;i<12;++i)if(i!=0x24/4)
            Require(unit[i]==0xA5A5A5A5,"draw method changed unrelated state");
    }
}
void Check(const char* path,Word entry,Word clock,Word expectedHash) {
    auto bytes=Window(path,entry);Word hash=2166136261u;
    for(auto byte:bytes)hash=(hash^byte)*16777619u;
    Require(hash==expectedHash,"unreviewed fade handler bytes");
    Word operand{};std::memcpy(&operand,bytes.data()+0x7A,4);
    Require(operand==clock,"unexpected clock operand");
    Word privateClock=1234;
    // Rebase only the independently guarded absolute clock operand. All control
    // flow and instructions remain stock; no installed game memory is touched.
    const auto privateAddress=static_cast<Word>(reinterpret_cast<std::uintptr_t>(&privateClock));
    std::memcpy(bytes.data()+0x7A,&privateAddress,4);
    Allocation code{VirtualAlloc(nullptr,bytes.size(),MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)};
    Require(code.address!=nullptr,"fixture allocation failed");
    std::memcpy(code.address,bytes.data(),bytes.size());DWORD old{};
    Require(VirtualProtect(code.address,bytes.size(),PAGE_EXECUTE_READ,&old)!=0,"fixture executable protection failed");
    FlushInstructionCache(GetCurrentProcess(),code.address,bytes.size());
    using Process=bool (__thiscall*)(void*,Unit*,Stack*,Word);
    const auto process=reinterpret_cast<Process>(code.address);
    void* unitTable[0xB8/4+1]{};void* stackTable[0x4C/4+1]{};
    unitTable[0x50/4]=reinterpret_cast<void*>(&Get);
    unitTable[0x54/4]=reinterpret_cast<void*>(&Set);
    unitTable[0x58/4]=reinterpret_cast<void*>(&Clear);
    unitTable[0xB8/4]=reinterpret_cast<void*>(&Notify);
    stackTable[0x4C/4]=reinterpret_cast<void*>(&Remove);
    for(Word target : {0u,10u})for(Word current : {0u,5u,10u}){
        Word order[0x3C/4]{};order[0x34/4]=target;order[0x14/4]=500;
        Unit unit{unitTable,(current<<8)|5};Stack stack{stackTable};
        Require(process(order,&unit,&stack,0),"stock fade rejected supplied event");
        if(current==target){
            Require(stack.removes==1 && !unit.writes,"completed fade did not unlink");
        }else{
            const Word next=current<target?current+1:current-1;
            Require(unit.draw==((next<<8)|5) && unit.writes==1 && unit.notices==1,"fade step differs");
            Require(order[8/4]==1234 && order[12/4]==500,"fade timer fields differ");
        }
        Unit cancelled{unitTable,(5u<<8)|5};Stack cancelledStack{stackTable};
        Require(process(order,&cancelled,&cancelledStack,1),"cleanup event failed");
        Require(cancelled.clears==(target==0?1u:0u),"cleanup direction changed");
        Require(!cancelled.writes && !cancelled.notices,"unexpected cleanup draw update");
        Unit unrelated{unitTable,(5u<<8)|5};
        Require(process(order,&unrelated,&cancelledStack,2),"other event failed");
        Require(!unrelated.writes && !unrelated.clears,"unrelated event changed presentation");
    }
}
struct DelayedStack { void** table; unsigned starts{}, completions{}; };
int __fastcall DelayedNotify(DelayedStack* stack,void*,void*,void*,Word event) {
    Require(event==0,"unexpected delayed progress event"); ++stack->starts; return 0;
}
void __fastcall DelayedComplete(DelayedStack* stack,void*,void*) { ++stack->completions; }
void CheckDelayedResearch(const char* path,Word address,Word clock,Word hash) {
    Allocation code; Word now=1234;
    LoadCode(code,path,address,0x5E,hash,0x38,clock,&now);
    void* table[0x50/4]{};
    table[0x44/4]=reinterpret_cast<void*>(&DelayedNotify);
    table[0x4C/4]=reinterpret_cast<void*>(&DelayedComplete);
    DelayedStack stack{table}; Word order[0x38/4]{};
    order[0x10/4]=0x4005; order[0x14/4]=30000;
    using Process=bool (__thiscall*)(void*,void*,DelayedStack*,Word);
    auto process=reinterpret_cast<Process>(code.address);
    Require(process(order,nullptr,&stack,0),"delayed research failed to start");
    Require(order[0x34/4]==1 && order[8/4]==1234 && order[12/4]==30000,
            "delayed research clock/counter differs");
    Require(stack.starts==1 && !stack.completions,"charge completed at start");
    Word restored[0x38/4]{};std::memcpy(restored,order,sizeof(order));
    now=31234;
    Require(process(restored,nullptr,&stack,0),"restored delayed order refused due step");
    Require(stack.completions==1 && restored[8/4]==1234 && restored[12/4]==30000,
            "restored charge restarted instead of completing");
    const auto before=stack.starts;
    Require(process(restored,nullptr,&stack,1),"delayed cancellation failed");
    Require(stack.starts==before && stack.completions==1,"cancellation activated charge");
    // The actual serializer field checks are separate Python exact-image tests;
    // this copy tests the restored-field processor, not loading a game save.
}
int main(int argc,char** argv) {
    try {
        Require(argc==4,"requires beta2, public and GOG executable fixtures");
        CheckDelayedResearch(argv[1],0x4DD3A0,0x7E3FDC,0x0E747EFE);
        CheckDelayedResearch(argv[2],0x4DCD90,0x7C5454,0xE0BCBA41);
        CheckDelayedResearch(argv[3],0x4DDAE0,0x7E4274,0xB24FA0B5);
        CheckConcreteDraw(argv[1],0x7539E4,0x75414C,0x7530C4,0x5DB410,0x5DB420,0x5DB4E0);
        CheckConcreteDraw(argv[2],0x73A924,0x73B08C,0x73A004,0x5C6230,0x5C6240,0x5C6300);
        CheckConcreteDraw(argv[3],0x752A2C,0x753194,0x75210C,0x5DA760,0x5DA770,0x5DA830);
        CheckSubmit(argv[1],0x60D140,0x22301758);
        CheckSubmit(argv[2],0x5F7E00,0x22301758);
        CheckSubmit(argv[3],0x60C490,0x22301758);
        Check(argv[1],0x60D050,0x7E3FDC,0x69B08C8B);
        Check(argv[2],0x5F7D10,0x7C5454,0xBB056322);
        Check(argv[3],0x60C3A0,0x7E4274,0xAD870BFA);
        CheckStack(argv[1],0x612180,0x6121D0,0x612200,0x7E3FDC,0x9263B0BD);
        CheckStack(argv[2],0x5FCE40,0x5FCE90,0x5FCEC0,0x7C5454,0x9956EA24);
        CheckStack(argv[3],0x6114D0,0x611520,0x611550,0x7E4274,0x3C4A7B38);
        return 0;
    }catch(const std::exception& e){std::fprintf(stderr,"Fade lifecycle fixture: %s\n",e.what());return 1;}
}
