// Offline x86 fixture: execute the production routing hook and the guarded
// stock picker/publication instructions, with opaque native services stubbed.
// No process, game image, UI, or merged package is modified.
namespace PaidAcquisitionChecks {
using namespace PaidChecks;
bool hit=true, accepted=true;
unsigned picks=0, predicates=0;
std::uint32_t mode=0x39327053, legacyFlags=0;
std::uintptr_t epilogue=0;
int __cdecl Picker(void* viewport,unsigned x,unsigned y,void** out,unsigned mask,unsigned type) {
    assert(viewport==reinterpret_cast<void*>(0x1234) && x==700 && y==800);
    assert(mask==0x80000030 && type==4);
    ++picks;
    *out=hit ? victim : nullptr;
    return hit;
}
bool __stdcall Predicate(unsigned original,void* picked) {
    assert(original==mode && picked==victim);
    ++predicates;return accepted;
}
__declspec(naked) void PredicateEntry() {
    __asm { push edi
            push eax
            call Predicate
            ret }
}
__declspec(naked) void LegacyGround() {
    __asm { pushfd
            pop dword ptr [legacyFlags]
            mov byte ptr [esp+0Fh], 1
            jmp dword ptr [epilogue] }
}
// Reproduce the already admitted helper frame. X and output are stack args;
// Y is inherited EBX. The real bounds/viewport services remain opaque.
__declspec(naked) bool __cdecl ClickFrame(unsigned x,void** out) {
    __asm { sub esp, 8
            mov byte ptr [esp+3], 0
            mov dword ptr [esp+4], 0
            push ebp
            push esi
            push edi
            mov esi, dword ptr [mode]
            mov eax, esi
            mov edi, 1234h
            jmp PaidUnitAcquisitionHook }
}
bool Click(void** out) {
    bool result;
    __asm { push ebx
            mov ebx, 800
            push out
            push 700
            call ClickFrame
            add esp, 8
            mov result, al
            pop ebx }
    return result;
}
void Run() {
    // These 84 bytes are identical across all three verified profiles. Only
    // the two relative calls are rebound to the opaque-service test doubles.
    const unsigned char stock[]={
        0x8b,0x44,0x24,0x18,0x6a,0x04,0x68,0x30,0x00,0x00,0x80,0x8d,0x54,0x24,0x18,0x52,0x53,0x50,0x57,
        0xe8,0xe2,0x6d,0xff,0xff,0x83,0xc4,0x18,0x85,0xc0,0x74,0x0f,0x8b,0x7c,0x24,0x10,0x8b,0xc6,
        0xe8,0xa0,0xf9,0xff,0xff,0x88,0x44,0x24,0x0f,0x5f,0x8b,0x44,0x24,0x18,0x5e,0x5d,0x85,0xc0,
        0x0f,0x84,0x86,0x01,0x00,0x00,0x8a,0x4c,0x24,0x03,0x0f,0xb6,0xd1,0xf7,0xda,0x1b,0xd2,0x23,0x54,
        0x24,0x04,0x89,0x10,0x8a,0xc1,0x83,0xc4,0x08,0xc3};
    auto* code=static_cast<unsigned char*>(VirtualAlloc(nullptr,sizeof(stock),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(code);std::memcpy(code,stock,sizeof(stock));
    const void* callees[]={reinterpret_cast<void*>(&Picker),reinterpret_cast<void*>(&PredicateEntry)};
    const unsigned offsets[]={19,37};
    for(unsigned i=0;i<2;++i) {
        const auto rel=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(callees[i])-reinterpret_cast<std::uintptr_t>(code+offsets[i]+5));
        std::memcpy(code+offsets[i]+1,&rel,4);
    }
    DWORD old=0;assert(VirtualProtect(code,sizeof(stock),PAGE_EXECUTE_READ,&old));
    FlushInstructionCache(GetCurrentProcess(),code,sizeof(stock));
    epilogue=reinterpret_cast<std::uintptr_t>(code+46);
    g_paidAcquisitionUnitBranch=reinterpret_cast<std::uintptr_t>(code);
    g_paidAcquisitionResume=reinterpret_cast<std::uintptr_t>(&LegacyGround);
    auto& action=g_stockControllerRegistry.sovereignTargetActions[0];
    g_pendingSovereignAction=&action;g_pendingSovereignBuilding=101;
    void* output=nullptr;
    assert(Click(&output) && output==victim && picks==1 && predicates==1);
    submittedPaid={};
    SubmitPrivateSovereignCommand(mode,1,700,800,*reinterpret_cast<unsigned*>(static_cast<unsigned char*>(output)+0x70),500);
    assert(submittedPaid.target==303 && submittedPaid.source==101);
    hit=false;output=victim;
    assert(!Click(&output) && output==nullptr && predicates==1);
    hit=true;accepted=false;output=victim;
    assert(!Click(&output) && output==nullptr && predicates==2);
    accepted=true;
    const auto count=picks;
    // Cancel/missing source, another mode, ordinary stock and unpaid private
    // routes keep the replaced CMP flags and stock ground-only result.
    g_pendingSovereignAction=nullptr;assert(Click(&output) && !output);
    g_pendingSovereignAction=&action;g_pendingSovereignBuilding=0;assert(Click(&output) && !output);
    g_pendingSovereignBuilding=101;mode=0x34327053;assert(Click(&output) && !output && (legacyFlags&0x40));
    mode=action.stockTargetMode;action.sovereignGoldCost=0;assert(Click(&output) && !output && !(legacyFlags&0x40));
    action.sovereignGoldCost=500;assert(picks==count);
    assert(Click(&output) && output==victim); // repeat acquires anew
    // Revalidate after acquisition: stale/non-lair clicks never get queued.
    targetPresent=false;submittedPaid={};SubmitPrivateSovereignCommand(mode,1,700,800,303,500);
    assert(!submittedPaid.source);targetPresent=true;
    lair=false;SubmitPrivateSovereignCommand(mode,1,700,800,303,500);assert(!submittedPaid.source);lair=true;
    VirtualFree(code,0,MEM_RELEASE);g_paidAcquisitionResume=g_paidAcquisitionUnitBranch=0;
}
}
