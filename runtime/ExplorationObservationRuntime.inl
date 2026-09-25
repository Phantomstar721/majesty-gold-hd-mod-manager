// Opt-in beta2 source attribution. No XP policy, map scan or timer lives here.
// Included after the stock GPL evaluator and kingdom-research adapter.
namespace ExplorationObservation {
bool enabled = false;
bool pending = false; // Hint only: the authoritative queue is saved GPL state.
thread_local unsigned readDepth = 0;
thread_local void* stepWorld = nullptr;
struct Batch { std::uint32_t bit; int tiles; };
thread_local Batch* batch = nullptr;
volatile LONG activeBatches = 0;
std::uintptr_t tileResume = 0;
bool diagnostic = false;
bool diagnosticEvents = false;
LARGE_INTEGER diagnosticFrequency{};
LONGLONG recordTicks = 0;
unsigned recordBatches = 0;
unsigned long long recordTiles = 0;

LONGLONG Clock() {
    LARGE_INTEGER value{};
    QueryPerformanceCounter(&value);
    return value.QuadPart;
}
double Microseconds(LONGLONG ticks) {
    return diagnosticFrequency.QuadPart ?
        ticks * 1000000.0 / diagnosticFrequency.QuadPart : 0.0;
}

template<class T> T Field(const void* p, std::size_t offset) {
    T result{};
    std::memcpy(&result, static_cast<const unsigned char*>(p)+offset, sizeof(result));
    return result;
}
void* CurrentWorld() {
    const auto root = *reinterpret_cast<void**>(g_imageBase+0x3E3FD4u);
    return root ? Field<void*>(root,0x10) : nullptr;
}
bool LiveStep() {
    const auto game = *reinterpret_cast<void**>(g_imageBase+0x3DF574u);
    return enabled && !readDepth && stepWorld && stepWorld == CurrentWorld() &&
        game && Field<int>(game,0) == 3;
}
bool SourceReady(void* unit) {
    return unit && Field<void*>(unit,0x94) == CurrentWorld() &&
        Field<std::uint32_t>(unit,0x70) < 0x7FFFFFFFu &&
        !(Field<std::uint32_t>(unit,0x74) & 4u) &&
        ReadPackedAttributeValue(unit,0x4541u,0) != 0;
}

// Literal stock evaluator lifecycle, also used by the existing list adapter.
// Only Manager-owned record/invalidate/dispatch functions are called natively.
bool Evaluate(const char* symbol, void* source = nullptr, int owner = 0, int tiles = 0) {
    const auto& p = QuestBoardProfile();
    std::uint32_t text[3]{};
    __declspec(align(4)) unsigned char evaluator[0x40]{};
    using String = void* (__thiscall*)(void*, const char*);
    using Construct = void* (__thiscall*)(void*, const void*);
    using Destroy = void (__thiscall*)(void*);
    using Agent = void (__thiscall*)(void*, void*);
    using Integer = void (__thiscall*)(void*, int);
    using At = void** (__thiscall*)(void*, unsigned);
    using Scalar = std::uint32_t (__thiscall*)(void*);
    reinterpret_cast<String>(g_imageBase+OccupantProfile().stringConstructor)(text,symbol);
    reinterpret_cast<Construct>(g_imageBase+p.evaluatorConstructor)(evaluator,text);
    reinterpret_cast<Destroy>(g_imageBase+p.stringDestructor)(text);
    const auto token = Field<std::uint32_t>(evaluator,4);
    bool valid = token != 0;
    std::uint32_t resultType = 0xFFFFFFFFu;
    std::uint32_t resultValue = 0;
    if (valid) {
        if (source) reinterpret_cast<Agent>(g_imageBase+p.addAgent)(evaluator,source);
        if (tiles) {
            reinterpret_cast<Integer>(g_imageBase+p.addInteger)(evaluator,owner);
            reinterpret_cast<Integer>(g_imageBase+p.addInteger)(evaluator,tiles);
        }
        reinterpret_cast<Destroy>(g_imageBase+p.execute)(evaluator);
        void** entry = reinterpret_cast<At>(g_imageBase+p.resultAt)(evaluator+0x24,0);
        if (entry && *entry) resultType = Field<std::uint32_t>(*entry,4);
        if (resultType == kGplIntegerResultType)
            resultValue = reinterpret_cast<Scalar>(g_imageBase+p.scalarResult)(evaluator);
        valid = resultType == kGplIntegerResultType && resultValue == 1;
    }
    if (!valid) {
        char message[384]{};
        sprintf_s(message,
            "Exploration GPL failure: symbol=%s token=0x%08X type=0x%08X result=%d source=%p agent=%u unit=%u owner=%d tiles=%d",
            symbol,token,resultType,static_cast<int>(resultValue),source,
            source ? ReadPackedAttributeValue(source,0x4541u,0) : 0,
            source ? Field<std::uint32_t>(source,0x70) : 0,owner,tiles);
        WriteLog(message);
    }
    reinterpret_cast<Destroy>(g_imageBase+p.evaluatorDestructor)(evaluator);
    return valid;
}

void __cdecl TileChanged(std::uint32_t oldMask, std::uint32_t newMask) {
    if (batch && !(oldMask & batch->bit) && (newMask & batch->bit)) ++batch->tiles;
}
// Displaced instructions are replayed literally. Native CMP immediately after
// this trampoline overwrites flags. All registers and the native stack survive.
__declspec(naked) void TileWrite() {
    __asm {
        mov ecx, [edi]
        mov eax, ecx
        or eax, [esp+44h]
        cmp activeBatches, 0
        je unchanged
        pushad
        push eax
        push ecx
        call TileChanged
        add esp, 8
        popad
    unchanged:
        jmp dword ptr [tileResume]
    }
}
void __fastcall Reveal(void* map, void* unit, const void* point, int mask, int radius) {
    using Stock = void (__thiscall*)(void*, const void*, int, int);
    const bool observe = LiveStep() && SourceReady(unit);
    const int owner = observe ? Field<int>(unit,0x80) : -1;
    Batch local{owner >= 0 && owner < 8 ? (1u << owner) : 0u,0};
    {
        struct Context {
            Batch* previous;
            bool active;
            explicit Context(Batch& current) : previous(batch), active(current.bit != 0) {
                batch = active ? &current : nullptr;
                if (active) InterlockedIncrement(&activeBatches);
            }
            ~Context() {
                if (active) InterlockedDecrement(&activeBatches);
                batch = previous;
            }
        } context(local);
        reinterpret_cast<Stock>(g_imageBase+0x1D9ED0u)(map,point,mask,radius);
    }
    // No GPL executes inside the native fog loop. Manager code only enqueues;
    // consumers run after the complete stock simulation step and hero birth.
    if (local.tiles && LiveStep() && SourceReady(unit)) {
        // GPL's binary operators convert operands to signed 22.10 fixed point.
        // Reject before crossing that boundary; an int32 literal is NOT a safe
        // GPL expression bound (INT_MAX becomes -1 in its fixed-point form).
        if (local.tiles > 2097151)
            StopUnsafeManagerRuntimeLaunch("Exploration reveal exceeds GPL's exact expression range.");
        const auto start = diagnostic ? Clock() : 0;
        if (!Evaluate("MM_EO_Record",unit,owner,local.tiles))
            StopUnsafeManagerRuntimeLaunch("Exploration observation could not preserve its saved pending event.");
        pending = true;
        if (diagnostic) {
            recordTicks += Clock()-start;
            ++recordBatches;
            recordTiles += local.tiles;
            if (diagnosticEvents) {
                char message[192]{};
                sprintf_s(message,"Exploration record agent=%u unit=%u owner=%d tiles=%d",
                    ReadPackedAttributeValue(unit,0x4541u,0),
                    Field<std::uint32_t>(unit,0x70),owner,local.tiles);
                WriteLog(message);
            }
        }
    }
}
__declspec(naked) void RevealBridge() {
    __asm {
        mov edx, edi
        jmp Reveal
    }
}
int __fastcall ReadChunk(void* reader, void*) {
    struct Guard { Guard() { ++readDepth; } ~Guard() { --readDepth; } } guard;
    using Stock = int (__thiscall*)(void*);
    return reinterpret_cast<Stock>(g_imageBase+0x1EC5D0u)(reader);
}
int __fastcall WriteWorld(void* writer, void*, void* stream, void* world) {
    // Save serialization also converts references back to pointers; it must
    // not synthesize exploration or invalidate the restored ownership epoch.
    struct Guard { Guard() { ++readDepth; } ~Guard() { --readDepth; } } guard;
    using Stock = int (__thiscall*)(void*, void*, void*);
    return reinterpret_cast<Stock>(g_imageBase+0x1EBF70u)(writer,stream,world);
}
void Invalidate(void* unit) {
    // The dispatcher routes states 3/7/8 through the existing-world update
    // handler. Transfers must invalidate even outside our simulation frame;
    // otherwise an away-and-back transfer can revive a consumer's remainder.
    const auto game = *reinterpret_cast<void**>(g_imageBase+0x3DF574u);
    const int state = game ? Field<int>(game,0) : 0;
    if (enabled && !readDepth && (state == 3 || state == 7 || state == 8) && SourceReady(unit)) {
        if (!Evaluate("MM_EO_Invalidate",unit))
            StopUnsafeManagerRuntimeLaunch("Exploration observation could not invalidate transferred ownership.");
        if (diagnosticEvents) {
            char message[128]{};
            sprintf_s(message,"Exploration owner-invalidate agent=%u old-owner=%d",
                ReadPackedAttributeValue(unit,0x4541u,0),Field<int>(unit,0x80));
            WriteLog(message);
        }
    }
}
void __fastcall OwnerChanged(void* unit, void*, int owner) {
    const int previous = Field<int>(unit,0x80);
    // Cancel before stock notifications can reveal under the new owner.
    if (previous != owner) Invalidate(unit);
    using Stock = void (__thiscall*)(void*, int);
    reinterpret_cast<Stock>(g_imageBase+0x1CF320u)(unit,owner);
}

bool Install() {
    if (g_buildProfile != &kBeta2BuildProfile) return false;
    const auto hash = [](std::uintptr_t rva, unsigned size) {
        std::uint32_t value = 2166136261u;
        const auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+rva);
        for (unsigned i=0; i<size; ++i) value = (value ^ bytes[i])*16777619u;
        return value;
    };
    if (hash(0x470E0u,0xCD) != 0xC8A7EB00u ||
        hash(0x1D9ED0u,0x1AA) != 0x1AD223F1u ||
        hash(0x1EC5D0u,0x74) != 0x2D6F7DA8u ||
        hash(0x1EBF70u,0x62) != 0x0D5AB5C9u ||
        hash(0x1CF320u,0x25) != 0xBA1A13F1u ||
        hash(0x15D410u,0x124) != 0x1B6F2A2Bu) return false;
    const unsigned char tile[] = {0x8B,0x0F,0x8B,0xC1,0x0B,0x44,0x24,0x44,0x3B,0xC1,0x74,0x4C,0x89,0x07};
    const auto& p = QuestBoardProfile();
    if (!MatchesProfileBytes(0x1D9FFDu,tile,sizeof(tile),"exploration tile write") ||
        !OccupantCallMatches(0x471A0u,0x1D9ED0u) ||
        !OccupantCallMatches(0x1EC655u,0x1EC5D0u) ||
        !OccupantCallMatches(0x1C113Bu,0x1EC5D0u) ||
        !OccupantCallMatches(0x1C1285u,0x1EC5D0u) ||
        !OccupantCallMatches(p.evaluatorHelper+0x2D,OccupantProfile().stringConstructor) ||
        !OccupantCallMatches(p.evaluatorHelper+0x43,p.evaluatorConstructor) ||
        !OccupantCallMatches(p.evaluatorHelper+0x5F,p.addAgent) ||
        !OccupantCallMatches(p.evaluatorHelper+0x68,p.execute) ||
        !OccupantCallMatches(p.evaluatorHelper+0x71,p.scalarResult) ||
        !OccupantCallMatches(p.scalarResult+5,p.resultAt) ||
        !OccupantCallMatches(p.evaluatorHelper+0x84,p.evaluatorDestructor)) return false;
    // Cover native owner virtuals without replacing the building adapter.
    constexpr std::uintptr_t owners[] = {0x3530E4u,0x3533BCu,0x35361Cu,
        0x353A04u,0x353C5Cu,0x353F04u,0x35416Cu,0x361684u,0x362764u};
    for (auto rva : owners) {
        const auto target = *reinterpret_cast<std::uintptr_t*>(g_imageBase+rva);
        if (target != g_imageBase+0x1CF320u &&
            !(rva == 0x3530E4u && target == reinterpret_cast<std::uintptr_t>(&ResearchBuildingOwnerChanged))) return false;
    }
    for (auto rva : {0x354434u,0x362EFCu})
        if (*reinterpret_cast<std::uintptr_t*>(g_imageBase+rva) != g_imageBase+0x1EBF70u) return false;
    if (!InstallGameUpdateRefreshBridge() || !InstallSharedWorldReadyHook()) return false;
    tileResume = g_imageBase+0x1DA005u;
    if (!WriteOccupantBranch(g_imageBase+0x1D9FFDu,reinterpret_cast<void*>(&TileWrite),0xE9,8) ||
        !WriteOccupantBranch(g_imageBase+0x471A0u,reinterpret_cast<void*>(&RevealBridge),0xE8)) return false;
    for (auto rva : {0x1EC655u,0x1C113Bu,0x1C1285u})
        if (!WriteOccupantBranch(g_imageBase+rva,reinterpret_cast<void*>(&ReadChunk),0xE8)) return false;
    for (auto rva : owners) {
        auto* slot = reinterpret_cast<std::uintptr_t*>(g_imageBase+rva);
        if (*slot != g_imageBase+0x1CF320u) continue;
        DWORD old = 0, ignored = 0;
        if (!VirtualProtect(slot,4,PAGE_READWRITE,&old)) return false;
        *slot = reinterpret_cast<std::uintptr_t>(&OwnerChanged);
        if (!VirtualProtect(slot,4,old,&ignored)) return false;
    }
    for (auto rva : {0x354434u,0x362EFCu}) {
        auto* slot = reinterpret_cast<std::uintptr_t*>(g_imageBase+rva);
        DWORD old = 0, ignored = 0;
        if (!VirtualProtect(slot,4,PAGE_READWRITE,&old)) return false;
        *slot = reinterpret_cast<std::uintptr_t>(&WriteWorld);
        if (!VirtualProtect(slot,4,old,&ignored)) return false;
    }
    enabled = true;
    char option[16]{};
    if (GetEnvironmentVariableA("MAJESTY_EXPLORATION_TRACE",option,sizeof(option))) {
        diagnosticEvents = std::strcmp(option,"1") == 0;
        diagnostic = diagnosticEvents || std::strcmp(option,"timing") == 0;
    }
    if (diagnostic) {
        QueryPerformanceFrequency(&diagnosticFrequency);
        WriteLog(diagnosticEvents ? "Exploration trace enabled (events and delivery timing)" :
                                    "Exploration trace enabled (delivery timing only)");
    }
    return true;
}
} // namespace ExplorationObservation

void ExplorationStepBegin() {
    if (ExplorationObservation::enabled)
        ExplorationObservation::stepWorld = ExplorationObservation::CurrentWorld();
}
void ExplorationStepEnd() {
    using namespace ExplorationObservation;
    if (LiveStep() && pending) {
        pending = false;
        const auto start = diagnostic ? Clock() : 0;
        if (!Evaluate("MM_EO_Dispatch"))
            StopUnsafeManagerRuntimeLaunch("Exploration observation callback dispatch failed.");
        if (diagnostic) {
            char message[224]{};
            sprintf_s(message,
                "Exploration delivery records=%u tiles=%llu record-us=%.1f dispatch-us=%.1f pending-next=%d",
                recordBatches,recordTiles,Microseconds(recordTicks),
                Microseconds(Clock()-start),pending ? 1 : 0);
            WriteLog(message);
            recordTicks = 0;
            recordBatches = 0;
            recordTiles = 0;
        }
    }
    stepWorld = nullptr;
}
void ExplorationWorldReady() {
    if (ExplorationObservation::enabled) {
        ExplorationObservation::pending = true;
        if (ExplorationObservation::diagnostic)
            WriteLog("Exploration world-ready: saved queue check scheduled; reconstruction is not credited");
    }
}
void ExplorationOwnerChanging(void* unit) {
    if (ExplorationObservation::enabled) ExplorationObservation::Invalidate(unit);
}
