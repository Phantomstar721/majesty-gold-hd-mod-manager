// A scoped construction source, never a persistent native pointer. The GPL
// agent-reference attribute is installed after initialization, before birth.
namespace SpellOrigin {
const MajestySpellOrigin::Profile* profile = nullptr;
std::uintptr_t resume = 0;
thread_local void* source = nullptr;
struct Scope {
    void* previous;
    explicit Scope(void* value) : previous(source) { source = value; }
    ~Scope() { source = previous; }
};

bool Record(void* spell, void* caster) {
    const auto& p = QuestBoardProfile();
    std::uint32_t text[3]{};
    __declspec(align(4)) unsigned char evaluator[0x40]{};
    using String = void* (__thiscall*)(void*, const char*);
    using Construct = void* (__thiscall*)(void*, const void*);
    using Destroy = void (__thiscall*)(void*);
    using Agent = void (__thiscall*)(void*, void*);
    using At = void** (__thiscall*)(void*, unsigned);
    using Scalar = std::uint32_t (__thiscall*)(void*);
    reinterpret_cast<String>(g_imageBase+OccupantProfile().stringConstructor)(text,"MM_SO_Record");
    reinterpret_cast<Construct>(g_imageBase+p.evaluatorConstructor)(evaluator,text);
    reinterpret_cast<Destroy>(g_imageBase+p.stringDestructor)(text);
    bool valid = *reinterpret_cast<std::uint32_t*>(evaluator+4) != 0;
    if (valid) {
        reinterpret_cast<Agent>(g_imageBase+p.addAgent)(evaluator,spell);
        reinterpret_cast<Agent>(g_imageBase+p.addAgent)(evaluator,caster);
        reinterpret_cast<Destroy>(g_imageBase+p.execute)(evaluator);
        void** entry = reinterpret_cast<At>(g_imageBase+p.resultAt)(evaluator+0x24,0);
        valid = entry && *entry &&
            *reinterpret_cast<std::uint32_t*>(static_cast<unsigned char*>(*entry)+4) == kGplIntegerResultType &&
            reinterpret_cast<Scalar>(g_imageBase+p.scalarResult)(evaluator) == 1;
    }
    reinterpret_cast<Destroy>(g_imageBase+p.evaluatorDestructor)(evaluator);
    return valid;
}
using Recorder = bool (*)(void*, void*);
Recorder record = &Record;

// Replay the complete displaced prologue; stock owns its locals and epilogue.
__declspec(naked) void __cdecl Original(void*) {
    __asm {
        sub esp, 2Ch
        push ebx
        push ebp
        jmp dword ptr [resume]
    }
}

void __cdecl Create(void* arguments) {
    using Argument = void** (__thiscall*)(void*, unsigned);
    using Agent = void* (__thiscall*)(void*);
    void** parameter = reinterpret_cast<Argument>(g_imageBase+profile->argument)(arguments,1);
    void* value = parameter ? *parameter : nullptr;
    void* unit = nullptr;
    if (value) {
        auto** vtable = *reinterpret_cast<void***>(value);
        void* agent = reinterpret_cast<Agent>(vtable[0x5C/4])(value);
        unit = reinterpret_cast<Agent>(g_imageBase+profile->unit)(agent);
    }
    Scope scope(unit);
    Original(arguments);
}

void __fastcall Birth(void* callback, void*, void* spell, void* target) {
    // This call site belongs only to CreateSpellUnit. Sovereign command births
    // use a different call site and must not inherit even a nested source.
    if (!record(spell,source))
        StopUnsafeManagerRuntimeLaunch("Spell origin could not save the original caster before birth.");
    using Stock = void (__thiscall*)(void*, void*, void*);
    reinterpret_cast<Stock>(g_imageBase+profile->birth)(callback,spell,target);
}

bool Install() {
    profile = g_buildProfile ? MajestySpellOrigin::For(g_buildProfile->buildId) : nullptr;
    if (!profile) return false;
    const auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+profile->create);
    std::uint32_t hash = 2166136261u;
    for (unsigned i=0;i<0x175;++i) hash = (hash ^ bytes[i])*16777619u;
    const auto& p = QuestBoardProfile();
    const unsigned char prologue[]{0x83,0xEC,0x2C,0x53,0x55};
    if (hash != profile->hash ||
        !MatchesProfileBytes(profile->create,prologue,sizeof(prologue),"spell origin CreateSpellUnit") ||
        !OccupantCallMatches(profile->create+0xF,profile->argument) ||
        !OccupantCallMatches(profile->create+0x35,profile->unit) ||
        !OccupantCallMatches(profile->create+0x168,profile->birth) ||
        !OccupantCallMatches(p.evaluatorHelper+0x2D,OccupantProfile().stringConstructor) ||
        !OccupantCallMatches(p.evaluatorHelper+0x43,p.evaluatorConstructor) ||
        !OccupantCallMatches(p.evaluatorHelper+0x51,p.stringDestructor) ||
        !OccupantCallMatches(p.evaluatorHelper+0x5F,p.addAgent) ||
        !OccupantCallMatches(p.evaluatorHelper+0x68,p.execute) ||
        !OccupantCallMatches(p.evaluatorHelper+0x71,p.scalarResult) ||
        !OccupantCallMatches(p.scalarResult+5,p.resultAt) ||
        !OccupantCallMatches(p.evaluatorHelper+0x84,p.evaluatorDestructor)) return false;
    resume = g_imageBase+profile->create+5;
    return WriteOccupantBranch(g_imageBase+profile->create+0x168,reinterpret_cast<void*>(&Birth),0xE8) &&
           WriteOccupantBranch(g_imageBase+profile->create,reinterpret_cast<void*>(&Create),0xE9);
}
}
