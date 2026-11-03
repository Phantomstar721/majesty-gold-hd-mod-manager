// Selected only by matching MMFR/MMCP declarations. Install verifies the stock
// stream, controller and queued dismissal boundaries before installing hooks.
#include "MessageFlagHudLayout.h"
namespace MessageFlagControls {
using Word = std::uint32_t;
struct Profile {
    Word loader, getter, creation, worldGlobal, catalog, allTable, enumerate, resolve;
    Word commandConstructor, commandHandler, commandFactory, uiConstructor, table;
    Word tooltipCopy, slots[9], hashes[6];
};
constexpr Profile profiles[] = {
 {0x638A20,0x626AA0,0x449690,0x7C544C,0x5A15D0,0x748D4C,0x5CE900,0x5A15F0,
  0x4C45C0,0x4C4710,0x4C4790,0x46A780,0x73BD78,0x628350,
  {0x4695C0,0x4698E0,0x46A600,0x469C90,0x453830,0x453840,0x453810,0x4675A0,0x46A2B0},
  {0x246946A9,0x7310545C,0x178A9FF4,0x49307061,0x61389FC2,0x4AB00ADC}},
 {0x64DE70,0x646620,0x44A5A0,0x7E3FD4,0x5B6580,0x762E1C,0x5E3AE0,0x5B65A0,
  0x4C5000,0x4C5150,0x4C51D0,0x46B9C0,0x754E70,0x63AAF0,
  {0x46A800,0x46AB20,0x46B840,0x46AED0,0x4547B0,0x4547C0,0x454790,0x4687E0,0x46B4F0},
  {0x4725E728,0x98C75759,0x34F34A20,0x0A3B7BAA,0x94D3DE5E,0xFF75D414}},
 {0x64D360,0x63B390,0x44A4C0,0x7E426C,0x5B58D0,0x761CDC,0x5E2E30,0x5B58F0,
  0x4C5600,0x4C5750,0x4C57D0,0x46B8E0,0x753EC0,0x63CC40,
  {0x46A720,0x46AA40,0x46B760,0x46ADF0,0x4546D0,0x4546E0,0x4546B0,0x468700,0x46B410},
  {0xF1C23139,0x849824F8,0xE2719EE5,0x549AE516,0xF544F23E,0x601AFAC4}}
};
struct Construction { Word prepare, read; };
constexpr Construction constructions[] = {
    {0x646300,0x637EE0}, {0x65B760,0x64D330}, {0x65AC50,0x64C820}
};
const Construction* construction = nullptr;
const Profile* profile = nullptr;
bool installed = false;
Word stockAllUnitsTable = 0;
volatile LONG suppressed = 0;
volatile LONG controller = 0;
void* managed[9]{};
bool managedRegistered = false;
void* creationResume = nullptr;
using Load = void* (__thiscall*)(void*,void*,Word,Word,Word);
Load originalLoad = nullptr;
std::wstring preferencePath;

Word At(const void* object, std::size_t offset) {
    Word value;std::memcpy(&value,static_cast<const unsigned char*>(object)+offset,4);return value;
}
Word Hash(Word address,std::size_t length) {
    Word hash=2166136261u;
    const auto* bytes=reinterpret_cast<const unsigned char*>(address);
    for(std::size_t i=0;i<length;++i)hash=(hash^bytes[i])*16777619u;
    return hash;
}
bool Preference(bool write, bool value=false) {
    if(preferencePath.empty()) {
        wchar_t folder[32768]{};
        const auto size=GetEnvironmentVariableW(L"LOCALAPPDATA",folder,32768);
        if(!size||size>=32768)return false;
        std::wstring directory=std::wstring(folder)+L"\\MajestyHD";
        if(!CreateDirectoryW(directory.c_str(),nullptr)&&GetLastError()!=ERROR_ALREADY_EXISTS)return false;
        preferencePath=directory+L"\\MessageFlagControls.dat";
    }
    unsigned char bytes[8]={'M','M','M','F',1,0,0,static_cast<unsigned char>(value)};
    if(!write) {
        HANDLE file=CreateFileW(preferencePath.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
        if(file==INVALID_HANDLE_VALUE)return GetLastError()==ERROR_FILE_NOT_FOUND;
        DWORD read=0;LARGE_INTEGER size{};
        const bool ok=GetFileSizeEx(file,&size)&&size.QuadPart==8&&ReadFile(file,bytes,8,&read,nullptr)&&read==8;
        CloseHandle(file);
        if(!ok||std::memcmp(bytes,"MMMF\1\0\0",7)||bytes[7]>1)return false;
        suppressed=bytes[7];return true;
    }
    const auto temporary=preferencePath+L".tmp";
    HANDLE file=CreateFileW(temporary.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;
    const bool ok=WriteFile(file,bytes,8,&written,nullptr)&&written==8&&FlushFileBuffers(file);
    CloseHandle(file);
    if(!ok){DeleteFileW(temporary.c_str());return false;}
    if(!MoveFileExW(temporary.c_str(),preferencePath.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary.c_str());return false;
    }
    return true;
}

void* World() {
    auto* runtime=*reinterpret_cast<void**>(profile->worldGlobal);
    return runtime?reinterpret_cast<void*>(At(runtime,4)):nullptr;
}
struct Census { std::vector<Word> ids;std::size_t visited=0;bool failed=false; };
int __cdecl Collect(void* unit,void* context,void*) {
    auto& result=*static_cast<Census*>(context);
    if(++result.visited>1000000){result.failed=true;return 1;}
    if(!unit||At(unit,0x6C)!=0x4647534D||(At(unit,0x74)&4))return 0;
    try {result.ids.push_back(At(unit,0x70));}
    catch(...) {result.failed=true;return 1;}
    return 0;
}
bool ClearFailure(const char* stage, Word observed=0) {
    char message[192]{};
    std::snprintf(message,sizeof(message),"Message controls clear rejected: stage=%s observed=0x%08X.",stage,observed);
    WriteLog(message);return false;
}
bool Clear() {
    auto* world=World();if(!world)return ClearFailure("world-unavailable");
    using Catalog=void* (__thiscall*)(void*,Word);
    auto* catalog=reinterpret_cast<Catalog>(profile->catalog)(world,3);
    if(!catalog)return ClearFailure("category-3-unavailable");
    const auto table=At(catalog,0);
    if(table!=profile->allTable&&(!stockAllUnitsTable||table!=stockAllUnitsTable))
        return ClearFailure("catalog-class",table);
    Census census;
    using Enumerate=int (__thiscall*)(void*,int (__cdecl*)(void*,void*,void*),void*,void*);
    reinterpret_cast<Enumerate>(profile->enumerate)(catalog,&Collect,&census,nullptr);
    if(census.failed)return ClearFailure("census-limit-or-allocation");
    using Resolve=void* (__thiscall*)(void*,Word);
    using Submit=void (__cdecl*)(void*,void*,Word);
    // Finish the read-only census before submitting any stock deletion command.
    unsigned submitted=0;
    for(const auto id:census.ids) {
        if(World()!=world)return ClearFailure("world-changed");
        auto* unit=reinterpret_cast<Resolve>(profile->resolve)(world,id);
        if(!unit||At(unit,0x70)!=id||At(unit,0x6C)!=0x4647534D||(At(unit,0x74)&4))continue;
        reinterpret_cast<Submit>(profile->commandFactory)(world,unit,0);++submitted;
    }
    char message[192]{};
    std::snprintf(message,sizeof(message),"Message controls clear: class=0x%08X visited=%u flags=%u queued=%u.",
        table,static_cast<unsigned>(census.visited),static_cast<unsigned>(census.ids.size()),submitted);
    WriteLog(message);return true;
}

void Refresh(void* object) {
    const auto address=static_cast<Word>(reinterpret_cast<std::uintptr_t>(object));
    if(address!=static_cast<Word>(controller))return;
    SetControllerControlText(address,MajestyMessageFlagHud::ToggleControl,suppressed?"Flags OFF":"Flags ON");
    SetControllerControlText(address,MajestyMessageFlagHud::ClearControl,"Clear flags");
}
void __fastcall Setup(void* object,void*) {
    reinterpret_cast<void (__thiscall*)(void*)>(profile->slots[1])(object);
    Refresh(object);
    WriteLog("Message controls: applied captions to the captured HUD controller.");
}
int __fastcall Command(void* object,void*,Word control) {
    if(control!=MajestyMessageFlagHud::ToggleControl&&control!=MajestyMessageFlagHud::ClearControl)
        return reinterpret_cast<int (__thiscall*)(void*,Word)>(profile->slots[3])(object,control);
    if(reinterpret_cast<std::uintptr_t>(object)!=static_cast<Word>(controller))return 0;
    if(control==MajestyMessageFlagHud::ClearControl) {
        if(!Clear())WriteLog("Message-flag clear could not submit the stock commands.");
    } else {
        const bool next=suppressed==0;
        if(!Preference(true,next))WriteLog("Message-flag preference could not be saved; toggle unchanged.");
        else {
            InterlockedExchange(&suppressed,next?1:0);
            if(next&&!Clear())WriteLog("Message suppression enabled, but current flags could not be cleared.");
        }
    }
    Refresh(object);return 0;
}
bool __fastcall Hover(void* object,void*,Word control,Word arg,Word output) {
    const char* text=nullptr;
    if(control==MajestyMessageFlagHud::ToggleControl)
        text=suppressed?"Allow new message flags.":"Clear current message flags and suppress new messages.";
    else if(control==MajestyMessageFlagHud::ClearControl)
        text="Clear current message flags without changing message suppression.";
    if(!text)return reinterpret_cast<bool (__thiscall*)(void*,Word,Word,Word)>(profile->slots[2])(object,control,arg,output);
    if(reinterpret_cast<std::uintptr_t>(object)!=static_cast<Word>(controller))return false;
    if(!output)return false;
    Word string[3]{};OccupantString(string,text);
    reinterpret_cast<void* (__thiscall*)(void*,const void*)>(profile->tooltipCopy)(reinterpret_cast<void*>(output),string);
    reinterpret_cast<void (__thiscall*)(void*)>(g_imageBase+QuestBoardProfile().stringDestructor)(string);
    return true;
}
bool Capture(Word address) {
    if(!installed||!address)return true;
    auto*** object=reinterpret_cast<void***>(address);
    if(reinterpret_cast<std::uintptr_t>(*object)!=profile->table)return true;
    if(!managedRegistered) {
        std::memcpy(managed,*object,sizeof(managed));
        if(!MajestyControllerLifecycle::RegisterManagedVtable(managed,*object,9,&controller,nullptr,nullptr))return false;
        managed[1]=reinterpret_cast<void*>(&Setup);managed[2]=reinterpret_cast<void*>(&Hover);
        managed[3]=reinterpret_cast<void*>(&Command);managedRegistered=true;
    }
    controller=static_cast<LONG>(address);*object=managed;return true;
}

void* __fastcall ReadHud(void* factory,void*,void* context,Word key,Word mode,Word flags) {
    if(key!=0x4B4D5041)return originalLoad(factory,context,key,mode,flags);
    // This is the quest menu-construction loader, not the separate loader for
    // an already-constructed MenuObject. Preserve its preparation and result.
    reinterpret_cast<void (__cdecl*)(Word)>(construction->prepare)(0);
    auto* manager=reinterpret_cast<void* (__cdecl*)()>(profile->getter)();
    auto** table=*reinterpret_cast<void***>(manager);
    using Acquire=void* (__thiscall*)(void*,void*,Word,Word,Word,Word,void*,Word);
    auto* handle=reinterpret_cast<Acquire>(table[0x38/4])(manager,context,0x554E4D53,key,0,0,nullptr,0);
    if(!handle)return nullptr;
    auto* data=static_cast<unsigned char*>(GlobalLock(handle));
    void* menu=nullptr;
    std::vector<Word> extended;
    try {
        const auto size=GlobalSize(handle);
        if(data&&size&&MajestyMessageFlagHud::Extend(data,size,extended)) {
            Word* reader[]={extended.data(),extended.data()};
            using Construct=void* (__thiscall*)(void*,void*,void*,Word,Word,Word);
            menu=reinterpret_cast<Construct>(construction->read)(factory,reader,context,key,mode,flags);
            if(menu) *reinterpret_cast<Word*>(static_cast<unsigned char*>(menu)+0x2C)=key;
        }
    } catch(...) {menu=nullptr;}
    GlobalUnlock(handle);
    manager=reinterpret_cast<void* (__cdecl*)()>(profile->getter)();
    table=*reinterpret_cast<void***>(manager);
    using Release=void (__thiscall*)(void*,void*,Word);
    reinterpret_cast<Release>(table[0x40/4])(manager,handle,0);
    if(!menu)StopUnsafeManagerRuntimeLaunch("The active HUD layout could not add message controls safely.");
    else WriteLog("Message controls: constructed the quest HUD with both private controls.");
    return menu;
}

__declspec(naked) void CreationGate() {
    __asm {
        cmp dword ptr [suppressed], 0
        jne suppressed_return
        jmp dword ptr [creationResume]
    suppressed_return:
        ret
    }
}

bool Install() {
    if(installed)return true;
    const auto index=static_cast<unsigned>(g_buildProfile->buildId);
    if(index>=3||g_imageBase!=0x400000)return false;
    profile=&profiles[index];
    construction=&constructions[index];
    if(profile->allTable!=g_imageBase+MajestyPairedOccupantAction::LookupProfiles[index].serviceVtable)return false;
    stockAllUnitsTable=static_cast<Word>(g_imageBase+MajestyPairedOccupantAction::AllUnitsTables[index]);
    // Both verified primary stock classes share the same unadjusted receiver.
    for(unsigned slot:{0x28u,0x30u})
        if(At(reinterpret_cast<void*>(stockAllUnitsTable),slot)!=At(reinterpret_cast<void*>(profile->allTable),slot))return false;
    const Word addresses[]={profile->loader,profile->commandConstructor,profile->commandHandler,
                            profile->commandFactory,profile->uiConstructor,profile->enumerate};
    const unsigned lengths[]={166,0x97,0x71,0x78,0x15D,0x89};
    for(unsigned i=0;i<6;++i)if(Hash(addresses[i],lengths[i])!=profile->hashes[i])return false;
    if(std::memcmp(reinterpret_cast<void*>(profile->table),profile->slots,sizeof(profile->slots)))return false;
    if(At(reinterpret_cast<void*>(profile->allTable),0x30)!=profile->enumerate)return false;
    const unsigned char originalCreation[]={0x8B,0x4C,0x24,0x10,0x56,0x57};
    const unsigned char legacyCreation[]={0xC3,0x90,0x90,0x90,0x90,0x90};
    const unsigned char creationTail[]={0x8B,0x7C,0x24,0x0C,0x6A,0,0x6A,0xFF,0x83,0xEC};
    const auto* create=reinterpret_cast<unsigned char*>(profile->creation);
    if((std::memcmp(create,originalCreation,6)&&std::memcmp(create,legacyCreation,6))||
       std::memcmp(create+6,creationTail,sizeof(creationTail)))return false;
    if(!Preference(false))return false;
    auto* resume=static_cast<unsigned char*>(VirtualAlloc(nullptr,32,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    if(!resume)return false;
    std::memcpy(resume,originalCreation,6);
    resume[6]=0xE9;
    auto relative=static_cast<std::int32_t>(profile->creation+6-reinterpret_cast<std::uintptr_t>(resume+11));
    std::memcpy(resume+7,&relative,4);
    // The loader's first seven whole instructions bytes contain no relative
    // operand. Non-APMK requests retain the original loader unchanged.
    std::memcpy(resume+16,reinterpret_cast<void*>(profile->loader),7);
    resume[23]=0xE9;
    relative=static_cast<std::int32_t>(profile->loader+7-reinterpret_cast<std::uintptr_t>(resume+28));
    std::memcpy(resume+24,&relative,4);
    DWORD old=0;
    if(!VirtualProtect(resume,32,PAGE_EXECUTE_READ,&old)) {VirtualFree(resume,0,MEM_RELEASE);return false;}
    FlushInstructionCache(GetCurrentProcess(),resume,32);
    unsigned char creationPatch[6]={0xE9,0,0,0,0,0x90};
    unsigned char loaderPatch[7]={0xE9,0,0,0,0,0x90,0x90};
    relative=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(&CreationGate)-(profile->creation+5));
    std::memcpy(creationPatch+1,&relative,4);
    relative=static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(&ReadHud)-(profile->loader+5));
    std::memcpy(loaderPatch+1,&relative,4);
    DWORD creationProtection=0,loaderProtection=0;
    if(!VirtualProtect(reinterpret_cast<void*>(profile->creation),6,PAGE_EXECUTE_READWRITE,&creationProtection)) {
        VirtualFree(resume,0,MEM_RELEASE);return false;
    }
    if(!VirtualProtect(reinterpret_cast<void*>(profile->loader),7,PAGE_EXECUTE_READWRITE,&loaderProtection)) {
        VirtualProtect(reinterpret_cast<void*>(profile->creation),6,creationProtection,&old);
        VirtualFree(resume,0,MEM_RELEASE);return false;
    }
    creationResume=resume;originalLoad=reinterpret_cast<Load>(resume+16);
    std::memcpy(reinterpret_cast<void*>(profile->creation),creationPatch,6);
    std::memcpy(reinterpret_cast<void*>(profile->loader),loaderPatch,7);
    FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(profile->creation),6);
    FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(profile->loader),7);
    VirtualProtect(reinterpret_cast<void*>(profile->creation),6,creationProtection,&old);
    VirtualProtect(reinterpret_cast<void*>(profile->loader),7,loaderProtection,&old);
    installed=true;
    WriteLog("Message controls: installed the guarded quest-HUD loader and creation gate.");
    return true;
}
}
