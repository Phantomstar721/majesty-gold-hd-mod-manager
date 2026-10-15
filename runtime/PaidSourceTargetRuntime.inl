// Versioned queued command extension. Execution still uses stock family 03F1;
// the independently serialized header owns tag 7F31 and eight payload words.
using PaidRecord = MajestyPaidSourceTarget::Record;
struct PaidHeader { void* bytes; std::uint32_t length; std::uint16_t tag; unsigned char owns, pad; };
struct PaidCommand {
    void** vtable; std::uint32_t timestamp;
    std::uint32_t mode, context, player, x, y, target, gold;
    PaidHeader header;
    std::uint32_t source;
    std::uint32_t toolbarControl;
};
static_assert(sizeof(PaidCommand)==0x38 && offsetof(PaidCommand,header)==0x24,
    "Native command layout must remain x86 stock prefix plus source");
struct PaidReference { PaidCommand* object; void* counter; };
static_assert(sizeof(PaidReference)==8,"Stock smart reference ABI");
void* g_paidVtable[6] = {}; // RTTI locator, then five stock virtual slots
using PaidFactory = PaidReference* (__cdecl*)(PaidReference*, std::uint32_t);
using PaidDispatcher = void (__stdcall*)(PaidReference);
PaidFactory g_paidFactory = nullptr;
PaidDispatcher g_paidDispatcher = nullptr;
thread_local const PaidRecord* g_paidRecord = nullptr;
bool g_paidProfileVerified = false;
const MajestyPaidSourceTarget::NativeProfile& PaidProfile() {
    return MajestyPaidSourceTarget::Profiles[MajestyPaidSourceTarget::ProfileIndex(g_buildProfile->buildId)];
}
bool HasPaidActions() {
    return std::any_of(g_stockControllerRegistry.sovereignTargetActions.begin(),
        g_stockControllerRegistry.sovereignTargetActions.end(), [](const auto& a){return a.sovereignGoldCost!=0;});
}
bool ValidatePaidProfile() {
    g_paidProfileVerified=false;
    if(!HasPaidActions())return true;
    const unsigned index=MajestyPaidSourceTarget::ProfileIndex(g_buildProfile->buildId);
    if(index>=3 || g_imageBase!=0x400000)return false;
    const auto matches=[](const MajestyPaidSourceTarget::NativeWindow& w){
        const auto* bytes=reinterpret_cast<const unsigned char*>(g_imageBase+w.rva);
        std::uint32_t h=2166136261u;
        for(unsigned i=0;i<w.size;++i)h=(h^bytes[i])*16777619u;
        return h==w.hash;
    };
    for(const auto& w:MajestyPaidSourceTarget::Windows[index])if(!matches(w))return false;
    for(const auto& w:MajestyPaidSourceTarget::OwnershipWindows[index])if(!matches(w))return false;
    for(const auto& w:MajestyPaidSourceTarget::AcquisitionWindows[index])if(!matches(w))return false;
    const unsigned char choice[]={0x81,0xFE,0x53,0x70,0x32,0x34};
    if(std::memcmp(reinterpret_cast<void*>(g_imageBase+
        MajestyPaidSourceTarget::AcquisitionProfiles[index].choice),choice,sizeof(choice)))return false;
    g_paidProfileVerified=true;return true;
}
std::uintptr_t g_paidAcquisitionResume=0, g_paidAcquisitionUnitBranch=0;
bool __stdcall UsePaidUnitAcquisition(std::uint32_t mode) {
    const auto* action=g_pendingSovereignAction;
    return action && action->sovereignGoldCost && !action->sourceTargetCallback.empty() &&
        action->stockTargetMode==mode &&
        InterlockedCompareExchange(&g_pendingSovereignBuilding,0,0)!=0;
}
// Keep the complete inherited stock frame, coordinates, mode and flags.
// The bounds call already consumed its two arguments (RET 8); no extra POP.
// Ordinary ground routes replay the replaced CMP and resume its native branch.
__declspec(naked) void PaidUnitAcquisitionHook() {
    __asm {
        pushfd
        pushad
        push esi
        call UsePaidUnitAcquisition
        test al, al
        jz legacy
        popad
        popfd
        jmp dword ptr [g_paidAcquisitionUnitBranch]
    legacy:
        popad
        popfd
        cmp esi, 34327053h
        jmp dword ptr [g_paidAcquisitionResume]
    }
}
PaidRecord ReadPaidCommand(const PaidCommand& c) {
    return {c.mode,c.context,c.player,c.x,c.y,c.target,c.gold,c.source,c.toolbarControl};
}
void SetPaidCommand(PaidCommand& c,const PaidRecord& r) {
    c.mode=r.mode;c.context=r.context;c.player=r.player;c.x=r.x;c.y=r.y;
    c.target=r.target;c.gold=r.gold;c.source=r.source;
    c.toolbarControl=r.toolbarControl;
}
PaidHeader* __fastcall SerializePaidCommand(PaidCommand* command,void*) {
    if(command->toolbarControl) {
        MajestyPaidSourceTarget::ToolbarPayload bytes;
        MajestyPaidSourceTarget::EncodeToolbar(ReadPaidCommand(*command),bytes);
        std::memcpy(command->header.bytes,bytes.data(),bytes.size());
        command->header.length=static_cast<unsigned>(bytes.size());
        command->header.tag=MajestyPaidSourceTarget::ToolbarCommandTag;
    } else {
        MajestyPaidSourceTarget::Payload bytes;
        MajestyPaidSourceTarget::Encode(ReadPaidCommand(*command),bytes);
        std::memcpy(command->header.bytes,bytes.data(),bytes.size());
        command->header.length=static_cast<unsigned>(bytes.size());
        command->header.tag=MajestyPaidSourceTarget::CommandTag;
    }
    return &command->header;
}
void __fastcall RestorePaidCommand(PaidCommand* command,void*,const PaidHeader* header) {
    PaidRecord record;
    if(header)MajestyPaidSourceTarget::Decode(header->tag,header->bytes,header->length,record);
    SetPaidCommand(*command,record);
}
void* NativePaidAllocate(std::size_t size) {
    return reinterpret_cast<void* (__cdecl*)(std::size_t)>(g_imageBase+PaidProfile().allocate)(size);
}
void NativePaidFree(void* pointer) {
    reinterpret_cast<void (__cdecl*)(void*)>(g_imageBase+
        MajestyPaidSourceTarget::Deletion[MajestyPaidSourceTarget::ProfileIndex(g_buildProfile->buildId)].release)(pointer);
}
void NativePaidConstruct(void* storage,const PaidRecord& r) {
    using Ctor=void* (__thiscall*)(void*,std::uint32_t,std::uint32_t,std::uint32_t,
        std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t);
    reinterpret_cast<Ctor>(g_imageBase+PaidProfile().constructor)(storage,r.mode,r.context,r.player,r.x,r.y,r.target,r.gold);
}
void NativePaidOwn(PaidReference* reference,void* command) {
    reinterpret_cast<PaidReference* (__thiscall*)(PaidReference*,void*)>(g_imageBase+PaidProfile().ref_ctor)(reference,command);
}
using PaidAllocate=void* (*)(std::size_t);
using PaidFree=void (*)(void*);
using PaidConstruct=void (*)(void*,const PaidRecord&);
using PaidOwn=void (*)(PaidReference*,void*);
PaidAllocate g_paidAllocate=&NativePaidAllocate;
PaidFree g_paidFree=&NativePaidFree;
PaidConstruct g_paidConstruct=&NativePaidConstruct;
PaidOwn g_paidOwn=&NativePaidOwn;
PaidCommand* CreatePaidCommand(const PaidRecord& r) {
    // Allocate the extension payload first. Stock constructor/destructor retain
    // ownership of their original prefix, buffer and reference-count lifetime.
    void* payload=LocalAlloc(LMEM_FIXED,MajestyPaidSourceTarget::ToolbarPayloadSize);
    if(!payload)return nullptr;
    void* storage=nullptr;
    try {
        storage=g_paidAllocate(sizeof(PaidCommand));
        if(!storage){LocalFree(payload);return nullptr;}
        g_paidConstruct(storage,r);
    } catch(...) {
        if(storage)g_paidFree(storage);
        LocalFree(payload);throw;
    }
    auto* command=static_cast<PaidCommand*>(storage);
    if(command->header.bytes)LocalFree(command->header.bytes);
    command->header={payload,32,MajestyPaidSourceTarget::CommandTag,1,0};
    command->source=r.source;
    command->toolbarControl=r.toolbarControl;
    command->vtable=g_paidVtable+1;
    return command;
}
PaidReference* __cdecl RestorePaidFactory(PaidReference* result,std::uint32_t tag) {
    if(tag!=MajestyPaidSourceTarget::CommandTag&&tag!=MajestyPaidSourceTarget::ToolbarCommandTag)
        return g_paidFactory(result,tag);
    auto* command=CreatePaidCommand({});
    // Restore immediately invokes virtual+0C: never return an empty object on
    // allocation failure. No queue owner exists until this constructor succeeds.
    if(!command)throw std::bad_alloc();
    try {
        g_paidOwn(result,command);
        if(!result->counter)throw std::bad_alloc();
    } catch(...) {
        reinterpret_cast<void* (__thiscall*)(void*,unsigned)>(command->vtable[0])(command,1);
        throw;
    }
    return result;
}
void NativeReleasePaidReference(PaidReference* value) {
    reinterpret_cast<void (__thiscall*)(PaidReference*)>(g_imageBase+PaidProfile().ref_destroy)(value);
}
using PaidReferenceRelease=void (*)(PaidReference*);
PaidReferenceRelease g_paidReferenceRelease=&NativeReleasePaidReference;
void __stdcall DispatchPaidCommand(PaidReference reference) {
    struct Scope {
        const PaidRecord* previous;
        Scope():previous(g_paidRecord){g_paidRecord=nullptr;}
        ~Scope(){g_paidRecord=previous;}
    } scope;
    PaidRecord snapshot;
    if(reference.object && reference.object->vtable==g_paidVtable+1) {
        auto& command=*reference.object;
        const auto* payload=SerializePaidCommand(&command,nullptr);
        if(!MajestyPaidSourceTarget::Decode(payload->tag,payload->bytes,payload->length,snapshot)) {
            g_paidReferenceRelease(&reference);return;
        }
        // Consume before any callback, including save/reentry. A save of this
        // already executing queue entry restores inert, never a second payment.
        command.source=0;
        command.toolbarControl=0;
        g_paidRecord=&snapshot;
    }
    // Stock dispatcher consumes this by-value native reference exactly once.
    g_paidDispatcher(reference);
}
void SubmitPaidCommand(const PaidRecord& record) {
    auto* command=CreatePaidCommand(record);
    if(!command)return;
    const auto& p=PaidProfile();
    void* queue=reinterpret_cast<void* (__cdecl*)()>(g_imageBase+p.queue_get)();
    reinterpret_cast<void (__thiscall*)(void*,void*)>(g_imageBase+p.queue)(queue,command);
}
using PaidSubmission=void (*)(const PaidRecord&);
PaidSubmission g_paidSubmission=&SubmitPaidCommand;
std::uint32_t PaidCommandContext(std::uint32_t x,std::uint32_t y) {
    const auto source=SourceTargetProfile();
    auto* root=*reinterpret_cast<unsigned char**>(g_imageBase+source.worldPointer);
    void* world=root ? *reinterpret_cast<void**>(root+4) : nullptr;
    struct Point {std::uint32_t x,y;};
    return reinterpret_cast<std::uint32_t (__stdcall*)(void*,Point)>(
        g_imageBase+PaidProfile().context)(world,{x,y});
}
using PaidContext=std::uint32_t (*)(std::uint32_t,std::uint32_t);
PaidContext g_paidContext=&PaidCommandContext;
void __fastcall PaidPostPayment(void*,void*,std::uint32_t);
bool InstallPaidCommandHooks() {
    if(!HasPaidActions())return true;
    if(!g_paidProfileVerified)return false;
    const auto& p=PaidProfile();
    const unsigned index=MajestyPaidSourceTarget::ProfileIndex(g_buildProfile->buildId);
    const auto& acquisition=MajestyPaidSourceTarget::AcquisitionProfiles[index];
    struct Patch {std::uintptr_t rva;const void* hook;unsigned size;unsigned char old[7];DWORD protection;bool opened;};
    Patch patches[]={
        {p.factory,reinterpret_cast<const void*>(&RestorePaidFactory),7,{},0,false},
        {p.dispatcher,reinterpret_cast<const void*>(&DispatchPaidCommand),7,{},0,false},
        {p.post_payment,reinterpret_cast<const void*>(&PaidPostPayment),5,{},0,false},
        {acquisition.choice,reinterpret_cast<const void*>(&PaidUnitAcquisitionHook),6,{},0,false}};
    // Recheck owned entry bytes after the earlier complete profile preflight.
    for(const auto& patch:patches) {
        bool matched=false;
        if(patch.rva==acquisition.choice) {
            const unsigned char expected[]={0x81,0xFE,0x53,0x70,0x32,0x34};
            if(std::memcmp(reinterpret_cast<void*>(g_imageBase+patch.rva),expected,6))return false;
            continue;
        }
        for(const auto& w:MajestyPaidSourceTarget::Windows[index]) {
            if(w.rva!=patch.rva && w.rva!=patch.rva-0x21)continue;
            std::uint32_t h=2166136261u;
            auto* bytes=reinterpret_cast<const unsigned char*>(g_imageBase+w.rva);
            for(unsigned i=0;i<w.size;++i)h=(h^bytes[i])*16777619u;
            matched=h==w.hash;break;
        }
        if(!matched)return false;
    }
    auto* bridges=static_cast<unsigned char*>(VirtualAlloc(nullptr,24,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    if(!bridges)return false;
    for(unsigned i=0;i<2;++i) {
        auto* bridge=bridges+12*i;
        std::memcpy(bridge,reinterpret_cast<void*>(g_imageBase+patches[i].rva),7);
        bridge[7]=0xE9;
        const auto jump=static_cast<std::int32_t>(g_imageBase+patches[i].rva+7-reinterpret_cast<std::uintptr_t>(bridge+12));
        std::memcpy(bridge+8,&jump,4);
    }
    DWORD old=0;
    if(!VirtualProtect(bridges,24,PAGE_EXECUTE_READ,&old)){VirtualFree(bridges,0,MEM_RELEASE);return false;}
    FlushInstructionCache(GetCurrentProcess(),bridges,24);
    // Acquire every writable span before changing any native instruction.
    for(auto& patch:patches) {
        auto* address=reinterpret_cast<void*>(g_imageBase+patch.rva);
        std::memcpy(patch.old,address,patch.size);
        if(!VirtualProtect(address,patch.size,PAGE_EXECUTE_READWRITE,&patch.protection)) {
            for(int j=3;j>=0;--j)if(patches[j].opened){DWORD ignored;VirtualProtect(reinterpret_cast<void*>(g_imageBase+patches[j].rva),patches[j].size,patches[j].protection,&ignored);}
            VirtualFree(bridges,0,MEM_RELEASE);return false;
        }
        patch.opened=true;
    }
    std::memcpy(g_paidVtable,reinterpret_cast<void*>(g_imageBase+p.vtable-4),sizeof(g_paidVtable));
    g_paidVtable[2]=reinterpret_cast<void*>(&SerializePaidCommand);
    g_paidVtable[4]=reinterpret_cast<void*>(&RestorePaidCommand);
    g_paidFactory=reinterpret_cast<PaidFactory>(bridges);
    g_paidDispatcher=reinterpret_cast<PaidDispatcher>(bridges+12);
    g_paidAcquisitionResume=g_imageBase+acquisition.choice+6;
    g_paidAcquisitionUnitBranch=g_imageBase+acquisition.unitBranch;
    for(const auto& patch:patches) {
        auto* address=reinterpret_cast<unsigned char*>(g_imageBase+patch.rva);
        unsigned char bytes[7]={0xE9,0,0,0,0,0x90,0x90};
        if(patch.size==5)bytes[0]=0xE8;
        const auto jump=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(patch.hook)-reinterpret_cast<std::uintptr_t>(address+5));
        std::memcpy(bytes+1,&jump,4);std::memcpy(address,bytes,patch.size);
        FlushInstructionCache(GetCurrentProcess(),address,patch.size);
    }
    // Reverse order matters when two entry points share a memory page.
    for(int i=3;i>=0;--i){DWORD ignored;VirtualProtect(reinterpret_cast<void*>(g_imageBase+patches[i].rva),patches[i].size,patches[i].protection,&ignored);}
    return true;
}
