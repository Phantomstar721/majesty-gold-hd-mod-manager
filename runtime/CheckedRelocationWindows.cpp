#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstring>
#include <atomic>
#include "CheckedRelocation.h"
#include "CheckedRelocationProfiles.h"
#include "AuditedBeta2.h"

namespace {
using namespace MajestyCheckedPlacement;
WriteBoundary boundary;
DWORD owner{};
bool installed{};
std::atomic<bool> foreignWrite{false};
Word expectedFrame{};
FinalPlacementCheck finalCheck{},stillOwned{};
void* finalContext{};
Word site{},continuation{},notifications{},epilogue{},convertPoint{};
const unsigned char expected[]={0x8B,0x44,0x24,0x1C,0x8B,0x08};

int Refuse() noexcept {
    try { return stillOwned&&stillOwned(finalContext)?2:0; }catch(...){return 0;}
}
int __cdecl Permit(Word actor,Word frame) noexcept {
    if(GetCurrentThreadId()!=owner){foreignWrite=true;return 1;}
    if(!boundary.IsArmed())return 1;
    boundary.SetFrame(expectedFrame);
    if(!boundary.IsExpected(actor,frame)){boundary.OtherWrite();return 1;}
    if(!boundary.BeginCheck())return Refuse();
    bool valid=false;
    try { valid=finalCheck&&finalCheck(finalContext); } catch(...) { valid=false; }
    return boundary.FinishCheck(valid&&!foreignWrite)?1:Refuse();
}

// At this exact stock site ESI is the mover. Original ESP is restored before
// replaying the six displaced bytes or branching to the stock epilogue.
__declspec(naked) void BeforeCoordinateWrite() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        lea eax, [ebx+36]
        push eax
        push esi
        call Permit
        add esp, 8
        fxrstor [esp]
        mov esp, ebx
        test eax, eax
        jz retired
        cmp eax, 2
        je refused
        popad
        popfd
        mov eax, [esp+28]
        mov ecx, [eax]
        jmp dword ptr [continuation]
    refused:
        popad
        popfd
        lea ecx, [esp+12]
        push ecx
        mov ecx, esi
        jmp dword ptr [notifications]
    retired:
        popad
        popfd
        jmp dword ptr [epilogue]
    }
}

// Stack proof (all VAs refer to the pinned image): at this bridge's ESP=S,
// push argument/call enter 5D7520 at S-8. Its sub0C/pushESI/pushPoint/call
// enter 5D7460 at S-20h; sub14/pushESI put the guarded site at S-38h.
// Capturing the concrete frame prevents nested stock moves stealing this call.
__declspec(naked) void __cdecl InvokeStock(Word,const Point*,Word*) {
    __asm {
        mov eax, [esp+12]
        lea edx, [esp-56]
        mov [eax], edx
        mov ecx, [esp+4]
        mov eax, [esp+8]
        push eax
        mov eax, dword ptr [convertPoint]
        call eax
        ret
    }
}
}

bool MajestyCheckedPlacement::InstallWriteBoundary(MajestyBuildId build) {
    // Require shared startup admission before the independently guarded write.
    if(installed||!AuditedStartup(build))return false;
    const auto* profile=RelocationFor(build);
    if(!profile||!RelocationBytesMatch(*profile,
        reinterpret_cast<const unsigned char*>(profile->convert),
        reinterpret_cast<const unsigned char*>(profile->write)))return false;
    site=static_cast<Word>(profile->write+0x2F);
    continuation=static_cast<Word>(profile->write+0x35);
    notifications=static_cast<Word>(profile->write+0x4B);
    epilogue=static_cast<Word>(profile->write+0xAD);
    convertPoint=static_cast<Word>(profile->convert);
    if(
        std::memcmp(reinterpret_cast<void*>(site),expected,sizeof(expected)))return false;
    DWORD previous{};
    if(!VirtualProtect(reinterpret_cast<void*>(site),sizeof(expected),PAGE_EXECUTE_READWRITE,&previous))return false;
    unsigned char patch[sizeof(expected)]={0xE9,0,0,0,0,0x90};
    const auto displacement=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(&BeforeCoordinateWrite)-site-5);
    std::memcpy(patch+1,&displacement,4);
    std::memcpy(reinterpret_cast<void*>(site),patch,sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(site),sizeof(patch));
    DWORD ignored{};
    if(!VirtualProtect(reinterpret_cast<void*>(site),sizeof(expected),previous,&ignored)) {
        // The initial protection change succeeded; undo the code write while
        // that page is still writable. Keep this provider unavailable.
        std::memcpy(reinterpret_cast<void*>(site),expected,sizeof(expected));
        FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(site),sizeof(expected));
        VirtualProtect(reinterpret_cast<void*>(site),sizeof(expected),previous,&ignored);
        foreignWrite=true;return false;
    }
    owner=GetCurrentThreadId();installed=true;return true;
}
bool MajestyCheckedPlacement::RelocateChecked(Word actor,Point pixels,FinalPlacementCheck check,FinalPlacementCheck owned,void* context) {
    if(!installed||foreignWrite||GetCurrentThreadId()!=owner||!check||!owned||!boundary.Arm(actor))return false;
    struct Reset { ~Reset(){boundary.Clear();finalCheck=nullptr;stillOwned=nullptr;finalContext=nullptr;expectedFrame=0;} } reset;
    finalCheck=check;stillOwned=owned;finalContext=context;
    InvokeStock(actor,&pixels,&expectedFrame);
    return boundary.Committed();
}
