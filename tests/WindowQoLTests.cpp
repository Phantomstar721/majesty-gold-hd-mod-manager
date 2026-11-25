// Offline production-path fixture. All window/cursor APIs are recording fakes.
#include "../runtime/WindowQoL.cpp"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>
extern "C" unsigned char GogFixtureBytes[0x500000];
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"WindowQoL line %d: %s\n",__LINE__,#x); std::exit(1); } } while(0)
namespace {
using namespace WindowQoL;
HWND game = reinterpret_cast<HWND>(0x1234), foreground = game;
bool icon = false, visible = true, registerOk = true;
bool recreateOnDestroy = false;
RECT clipped = {}, clientRect = {0,0,800,600};
POINT origin = {-1200,100};
unsigned clipCalls = 0, registerCalls = 0, forwardCalls = 0, protectCalls = 0, failProtect = 0;
HWND WINAPI Foreground() { return foreground; }
DWORD WINAPI Process(HWND, DWORD* pid) { *pid = GetCurrentProcessId(); return 1; }
BOOL WINAPI Valid(HWND h) { return h == game; }
BOOL WINAPI Iconic(HWND) { return icon; }
BOOL WINAPI Visible(HWND) { return visible; }
BOOL WINAPI Client(HWND, RECT* r) { *r=clientRect; return TRUE; }
BOOL WINAPI Screen(HWND, POINT* p) { p->x+=origin.x; p->y+=origin.y; return TRUE; }
BOOL WINAPI Clip(const RECT* r) { ++clipCalls; clipped = r ? *r : RECT{0,0,0,0}; return TRUE; }
BOOL WINAPI GetClip(RECT* r) { *r=clipped; return TRUE; }
BOOL WINAPI Register(HWND h, int id, UINT modifiers, UINT key) {
    CHECK(h==game && id==0xC111 && modifiers==(MOD_CONTROL|MOD_SHIFT|MOD_NOREPEAT) && key==VK_F11);
    ++registerCalls; return registerOk;
}
BOOL WINAPI Unregister(HWND, int) { return TRUE; }
ATOM WINAPI AddAtom(LPCSTR) { return 0xC111; }
ATOM WINAPI DeleteAtom(ATOM) { return 0; }
BOOL WINAPI Protect(LPVOID p,SIZE_T s,DWORD protection,PDWORD previous) {
    if (++protectCalls==failProtect) return FALSE;
    return VirtualProtect(p,s,protection,previous);
}
LRESULT CALLBACK Original(HWND, UINT message, WPARAM, LPARAM) {
    ++forwardCalls;
    if (message == WM_NCDESTROY && recreateOnDestroy) {
        recreateOnDestroy = false;
        game = reinterpret_cast<HWND>(0x2345); foreground = game;
        *reinterpret_cast<HWND*>(image + profile->mainWindowRva) = game;
        Procedure(game, WM_SETFOCUS, 0, 0);
    }
    return 0x56789;
}
BOOL WINAPI WindowInfo(HWND, PWINDOWINFO info) {
    info->rcClient={origin.x,origin.y,origin.x+clientRect.right,origin.y+clientRect.bottom}; return TRUE;
}
void TestLog(const char*) {}
void Reset() {
    profile=nullptr; image=0; original=nullptr; requested=true; closing=owned=conflictLogged=false;
    focused=minimized=false; current=nullptr; hotkey=0; lastMode=-1;
    game=reinterpret_cast<HWND>(0x1234); foreground=game; icon=false; visible=true; registerOk=true; recreateOnDestroy=false;
    clipCalls=registerCalls=forwardCalls=protectCalls=failProtect=0;
    clipped={0,0,0,0}; clientRect={0,0,800,600}; origin={-1200,100};
    api={Foreground,Process,Valid,Iconic,Visible,Client,Screen,Clip,GetClip,Register,Unregister,AddAtom,DeleteAtom,Protect};
}
unsigned Load(const char* path) {
    std::ifstream stream(path,std::ios::binary); CHECK(stream.good());
    std::vector<char> bytes{std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
    const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(bytes.data()+reinterpret_cast<const IMAGE_DOS_HEADER*>(bytes.data())->e_lfanew);
    CHECK(nt->Signature==IMAGE_NT_SIGNATURE && nt->OptionalHeader.ImageBase==0x400000);
    std::memset(GogFixtureBytes,0,0x500000);
    std::memcpy(GogFixtureBytes,bytes.data(),nt->OptionalHeader.SizeOfHeaders);
    const auto* section=IMAGE_FIRST_SECTION(nt);
    for (unsigned i=0;i<nt->FileHeader.NumberOfSections;++i) {
        CHECK(section[i].VirtualAddress+section[i].SizeOfRawData<0x500000);
        std::memcpy(GogFixtureBytes+section[i].VirtualAddress,bytes.data()+section[i].PointerToRawData,section[i].SizeOfRawData);
    }
    DWORD old=0; CHECK(VirtualProtect(GogFixtureBytes,0x500000,PAGE_EXECUTE_READWRITE,&old));
    return nt->OptionalHeader.SizeOfImage;
}
void BindImport(const char* name, std::uintptr_t function) {
    auto* nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(GogFixtureBytes+reinterpret_cast<IMAGE_DOS_HEADER*>(GogFixtureBytes)->e_lfanew);
    auto* lib=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(GogFixtureBytes+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    unsigned count=0;
    for(;lib->Name;++lib) {
        auto* names=reinterpret_cast<IMAGE_THUNK_DATA32*>(GogFixtureBytes+lib->OriginalFirstThunk);
        auto* slots=reinterpret_cast<IMAGE_THUNK_DATA32*>(GogFixtureBytes+lib->FirstThunk);
        for(;names->u1.AddressOfData;++names,++slots) if(!IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) {
            auto* item=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(GogFixtureBytes+names->u1.AddressOfData);
            if(std::strcmp(reinterpret_cast<char*>(item->Name),name)==0) { slots->u1.Function=static_cast<DWORD>(function); ++count; }
        }
    }
    CHECK(count==1);
}
unsigned modeInput=0, modeOutput=0, styleOutput=0, xOutput=0, yOutput=0;
std::uintptr_t modeEntry=0;
__declspec(naked) void ModeStop() {
    __asm {
        mov eax,[esp+0b4h]
        mov modeOutput,eax
        mov styleOutput,esi
        mov eax,[esp+20h]
        mov xOutput,eax
        mov eax,[esp+1ch]
        mov yOutput,eax
        add esp,0c0h
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    }
}
__declspec(naked) void RunMode() {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        sub esp,0c0h
        xor ebp,ebp
        mov eax,modeInput
        mov [esp+0b4h],eax
        jmp modeEntry
    }
}
void Divert(unsigned char* at, std::uintptr_t destination) {
    at[0]=0xE9; const auto delta=static_cast<std::uint32_t>(destination-reinterpret_cast<std::uintptr_t>(at+5));
    std::memcpy(at+1,&delta,4);
}
void CheckMode(const WindowQoLProfiles::Profile& p) {
    auto* creation=GogFixtureBytes+p.creationRva;
    modeEntry=reinterpret_cast<std::uintptr_t>(creation+0x172);
    Divert(creation+0x257,reinterpret_cast<std::uintptr_t>(&ModeStop));
    for(unsigned m=0;m<3;++m) {
        modeInput=m; RunMode();
        CHECK(modeOutput==(m==0?2:m) && styleOutput==0x80000000 && xOutput==0 && yOutput==0);
        const auto address=*reinterpret_cast<DWORD*>(creation+0x1A5);
        CHECK(*reinterpret_cast<DWORD*>(address)==(m==1?1u:0u));
    }
}
void Lifecycle(const WindowQoLProfiles::Profile& p) {
    *reinterpret_cast<HWND*>(GogFixtureBytes+p.mainWindowRva)=game;
    *reinterpret_cast<int*>(GogFixtureBytes+p.gameFullscreenRva)=0;
    original=Original;
    if(p.gogClipRva) {
        *reinterpret_cast<int*>(GogFixtureBytes+p.gogModeRva)=1; // native saved preference untouched
        BindImport("GetWindowInfo",reinterpret_cast<std::uintptr_t>(&WindowInfo));
        BindImport("ClipCursor",reinterpret_cast<std::uintptr_t>(&Clip));
    }
    CHECK(Procedure(game,WM_SETFOCUS,0,0)==0x56789);
    CHECK(hotkey && clipped.left==-1200 && clipped.right==-400);
    CHECK(Procedure(reinterpret_cast<HWND>(0x8888),WM_HOTKEY,hotkey,0)==0x56789 && requested);
    const unsigned calls=clipCalls, registrations=registerCalls;
    for(unsigned i=0;i<10000;++i) CHECK(Procedure(game,WM_MOUSEMOVE,0,0)==0x56789);
    CHECK(clipCalls==calls && registerCalls==registrations);
    CHECK(Procedure(game,WM_HOTKEY,hotkey,0)==0 && !requested && clipped.right==0);
    if(p.gogClipRva) { ApplyCursor(); CHECK(clipped.right==0 && *reinterpret_cast<int*>(GogFixtureBytes+p.gogModeRva)==1); }
    CHECK(Procedure(game,WM_HOTKEY,hotkey,0)==0 && requested && clipped.right==-400);
    foreground=nullptr; Procedure(game,WM_KILLFOCUS,0,0); CHECK(!hotkey && clipped.right==0);
    foreground=game; Procedure(game,WM_SETFOCUS,0,0); CHECK(hotkey && clipped.right==-400);
    icon=true; Procedure(game,WM_SIZE,SIZE_MINIMIZED,0); CHECK(!hotkey && clipped.right==0);
    icon=false; Procedure(game,WM_SIZE,SIZE_RESTORED,0); CHECK(hotkey);
    origin={100,200}; clientRect.right=1000; Procedure(game,WM_DISPLAYCHANGE,0,0); CHECK(clipped.right==1100);
    visible=false; Procedure(game,WM_SHOWWINDOW,0,0); CHECK(!hotkey && clipped.right==0);
    visible=true; Procedure(game,WM_SHOWWINDOW,1,0); CHECK(hotkey);
    Procedure(game,WM_CLOSE,0,0); CHECK(hotkey); // canceled stock close is preserved
    Procedure(game,WM_ENDSESSION,0,0); CHECK(hotkey);
    *reinterpret_cast<int*>(GogFixtureBytes+p.gameFullscreenRva)=1;
    Procedure(game,WM_NULL,0,0); CHECK(!hotkey);
    if(p.gogClipRva) {
        CHECK(EffectiveGogMode()==1);
        ApplyCursor(); CHECK(clipped.right==1100); // stock fullscreen preference
    }
    *reinterpret_cast<int*>(GogFixtureBytes+p.gameFullscreenRva)=0;
    Procedure(game,WM_NULL,0,0); CHECK(hotkey);
    Procedure(game,WM_NCDESTROY,0,0); CHECK(!hotkey && !current && clipped.right==0);
    Procedure(game,WM_SETFOCUS,0,0); CHECK(hotkey && current==game);
    registerOk=false; foreground=nullptr; Procedure(game,WM_KILLFOCUS,0,0);
    foreground=game; Procedure(game,WM_SETFOCUS,0,0); CHECK(!hotkey && clipped.right==0);
    if(p.gogClipRva) { ApplyCursor(); CHECK(clipped.right==0); }
    if(!p.gogClipRva) {
        registerOk=true; Procedure(game,WM_WINDOWPOSCHANGED,0,0); CHECK(owned);
        clipped={10,10,20,20};
        const auto previous=clipCalls;
        foreground=nullptr; Procedure(game,WM_KILLFOCUS,0,0);
        CHECK(clipCalls==previous && clipped.right==20 && !owned);
    } else {
        // Exercise the unchanged native setter/getter against the patched
        // Apply entry, including focus reapplication and saved-mode roundtrip.
        auto setter=reinterpret_cast<void(__cdecl*)(int)>(image+p.gogClipRva+0x70);
        auto getter=reinterpret_cast<int(__cdecl*)()>(image+p.gogClipRva+0xB0);
        for(int mode=0;mode<3;++mode) {
            setter(mode); CHECK(getter()==mode && clipped.right==0);
        }
    }
    registerOk=true; foreground=game; Procedure(game,WM_SETFOCUS,0,0); CHECK(hotkey);
    const auto oldWindow=game; recreateOnDestroy=true;
    Procedure(oldWindow,WM_NCDESTROY,0,0);
    CHECK(current==game && game!=oldWindow && hotkey && requested);
}
}
int main(int argc,char** argv) {
    CHECK(argc==4 && reinterpret_cast<std::uintptr_t>(GogFixtureBytes)==0x400000);
    for(unsigned index=0;index<3;++index) {
        const auto& p=WindowQoLProfiles::profiles[index];
        const unsigned size=Load(argv[index+1]); Reset();
        std::vector<unsigned char> pristine(GogFixtureBytes,GogFixtureBytes+size);
        CHECK(Install(0x400000,p.build,false,false,TestLog)); CHECK(std::memcmp(pristine.data(),GogFixtureBytes,size)==0);
        CHECK(!Install(0x400000,static_cast<MajestyBuildId>(99),true,true,TestLog));
        CHECK(!Install(0x500000,p.build,true,true,TestLog));
        for(unsigned offset : {0u,540u,1079u}) {
            GogFixtureBytes[p.creationRva+offset]^=1;
            auto before=std::vector<unsigned char>(GogFixtureBytes,GogFixtureBytes+size);
            CHECK(!Install(0x400000,p.build,true,true,TestLog)); CHECK(std::memcmp(before.data(),GogFixtureBytes,size)==0);
            GogFixtureBytes[p.creationRva+offset]^=1;
        }
        for(unsigned range : {p.windowedPreferenceGuardRva,p.mainWindowGuardRva,p.gogClipRva}) if(range) {
            GogFixtureBytes[range]^=1; CHECK(!Install(0x400000,p.build,true,true,TestLog)); GogFixtureBytes[range]^=1;
        }
        for(unsigned failure=1;failure<=(p.gogClipRva?4u:3u);++failure) {
            failProtect=failure; protectCalls=0;
            CHECK(!Install(0x400000,p.build,true,true,TestLog)); CHECK(std::memcmp(pristine.data(),GogFixtureBytes,size)==0);
        }
        failProtect=0; CHECK(Install(0x400000,p.build,true,true,TestLog));
        CHECK(!Install(0x400000,p.build,true,true,TestLog));
        auto* creation=GogFixtureBytes+p.creationRva;
        for(unsigned operand : {140u,265u}) CHECK(*reinterpret_cast<DWORD*>(creation+operand)==reinterpret_cast<DWORD>(&Procedure));
        // No bytes outside the four precisely bounded hand-over sites changed.
        for(unsigned at=0;at<size;++at) {
            const auto in=[&](unsigned rva,unsigned n){return at>=rva && at<rva+n;};
            if(!in(p.creationRva+467,17) && !in(p.creationRva+140,4) && !in(p.creationRva+265,4) && !(p.gogClipRva && in(p.gogClipRva,5))) CHECK(GogFixtureBytes[at]==pristine[at]);
        }
        CheckMode(p); Lifecycle(p);
        for(unsigned flag=0;flag<2;++flag) {
            Load(argv[index+1]); Reset();
            CHECK(Install(0x400000,p.build,flag==0,flag==1,TestLog));
            CHECK((std::memcmp(GogFixtureBytes+p.creationRva+467,pristine.data()+p.creationRva+467,17)!=0)==(flag==0));
            CHECK((std::memcmp(GogFixtureBytes+p.creationRva+140,pristine.data()+p.creationRva+140,4)!=0)==(flag==1));
            CHECK(clipCalls==0 && registerCalls==0);
        }
    }
    return 0;
}
