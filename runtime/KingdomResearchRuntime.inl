// Included inside the runtime's private namespace after the common stock UI
// and GPL-evaluator helpers. No scheduler or saved pointer owns this feature.
using KingdomResearchRecord = MajestyRuntimeFeatures::KingdomResearchRecord;
void RefreshKingdomResearch(std::uint32_t controller, bool child);

bool KingdomResearchVisualsSelected() {
    return std::any_of(g_runtimeFeatureRegistry.kingdomResearch.begin(),
        g_runtimeFeatureRegistry.kingdomResearch.end(),
        [](const KingdomResearchRecord& r) { return !r.activeEffector.empty(); });
}

bool ValidateKingdomResearchProfile() {
    if (g_buildProfile != &kBeta2BuildProfile) return false;
    // Entire audited executor/completion bodies, including payment, callback
    // reasons and cleanup. Validate before installing the shared name adapter.
    const auto hash = [](std::uintptr_t rva, std::size_t size) {
        std::uint32_t value = 2166136261u;
        auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+rva);
        for (std::size_t i = 0; i < size; ++i) value = (value ^ bytes[i]) * 16777619u;
        return value;
    };
    const auto& p = QuestBoardProfile();
    const unsigned char addInteger[] = {0x83,0xC1,0x08,0xE9};
    // A one-time state-2 -> play boundary, not the state-3 update loop. Readiness
    // and owner setters are wrapped after stock, and only on BuildingRec.
    if (KingdomResearchVisualsSelected() &&
        !(hash(0x49950u, 0x259) == 0x79A54DEEu &&
          hash(0x1CF320u, 0x25) == 0xBA1A13F1u &&
          hash(0x2AC32u, 0xB6) == 0x723478B1u &&
          hash(0x1B9030u, 0x68) == 0xA33A9A12u &&
          OccupantCallMatches(0x26234u, 0x2AAB0u) &&
          *reinterpret_cast<const std::uintptr_t*>(g_imageBase+0x262C8u) == g_imageBase+0x26232u &&
          *reinterpret_cast<const std::uintptr_t*>(g_imageBase+0x3531E8u) == g_imageBase+0x49950u &&
          *reinterpret_cast<const std::uintptr_t*>(g_imageBase+0x3530E4u) == g_imageBase+0x1CF320u)) return false;
    return hash(0x0E02F0u, 0x131) == 0x1ED81331u &&
        hash(0x0E0430u, 0x24C) == 0x21D00DDFu &&
        hash(0x1DF010u, 0x1B) == 0x43D252E8u &&
        hash(0x1DE410u, 8) == 0x7F4FC095u &&
        OccupantCallMatches(p.evaluatorHelper+0x2D, OccupantProfile().stringConstructor) &&
        OccupantCallMatches(p.evaluatorHelper+0x43, p.evaluatorConstructor) &&
        OccupantCallMatches(p.evaluatorHelper+0x51, p.stringDestructor) &&
        OccupantCallMatches(p.evaluatorHelper+0x5F, p.addAgent) &&
        OccupantCallMatches(p.evaluatorHelper+0x68, p.execute) &&
        OccupantCallMatches(p.evaluatorHelper+0x71, p.scalarResult) &&
        OccupantCallMatches(p.scalarResult+5, p.resultAt) &&
        OccupantCallMatches(p.evaluatorHelper+0x84, p.evaluatorDestructor) &&
        MatchesProfileBytes(p.addInteger, addInteger, sizeof(addInteger), "research GPL integer argument");
}

const KingdomResearchRecord* FindKingdomResearch(std::uint32_t command) {
    for (const auto& record : g_runtimeFeatureRegistry.kingdomResearch)
        if (record.actionControlId == command) return &record;
    return nullptr;
}
bool KingdomResearchMatches(void* unit, const KingdomResearchRecord& record) {
    return unit && ((*reinterpret_cast<const std::uint32_t*>(
        static_cast<const unsigned char*>(unit)+0x7C) & 0xFFFFFFu) == record.buildingFamily);
}
int KingdomResearchEligible(void* unit, std::uint32_t command) {
    const auto* record = FindKingdomResearch(command);
    return record && KingdomResearchMatches(unit, *record) &&
        SelectedBuildingLevel(unit) >= static_cast<int>(record->requiredLevel) &&
        ReadPackedAttributeValue(unit, 0x01425041u) == 1 &&
        ReadPackedAttributeValue(unit, 0x02425041u) == 1 ? 1 : 0;
}

void SyncKingdomResearchVisual(void* unit, bool hadAgent = false) {
    if (!unit) return;
    const auto* bytes = static_cast<const unsigned char*>(unit);
    // Placement previews and retired units do not own a callable GPL agent.
    if (*reinterpret_cast<const std::uint32_t*>(bytes+0x70) >= 0x7FFFFFFFu ||
        (*reinterpret_cast<const std::uint32_t*>(bytes+0x74) & 4u)) return;
    for (const auto& record : g_runtimeFeatureRegistry.kingdomResearch) {
        if (record.activeEffector.empty() || !KingdomResearchMatches(unit, record)) continue;
        // Construction assigns an owner before creating the GPL agent. The
        // stock completion callback writes this flag only after that agent and
        // its upgraded attributes exist. Save loading writes raw maps instead.
        if (!hadAgent && ReadPackedAttributeValue(unit, 0x01425041u) != 1) return;
        const auto symbol = record.CallbackSymbol()+"_Visual";
        std::uint32_t result = 0;
        if (!g_questBoardScalarEvaluator(symbol.c_str(), unit, false, 0, &result, false) || result > 1)
            StopUnsafeManagerRuntimeLaunch("The prepared kingdom research active-effector callback is missing or invalid.");
        return; // registrations guarantee one feature per building family
    }
}
using ResearchBuildingSetFunction = void (__thiscall*)(void*, std::uint32_t, int);
using ResearchBuildingOwner = void (__thiscall*)(void*, int);
using ResearchWorldReady = void (__thiscall*)(void*);
ResearchBuildingSetFunction g_researchBuildingSet = nullptr;
ResearchBuildingOwner g_researchBuildingOwner = nullptr;
ResearchWorldReady g_researchWorldReady = nullptr;

void __fastcall ResearchBuildingSet(void* unit, void*, std::uint32_t attribute, int value) {
    const bool hadAgent = attribute == 0x01425041u && value != 1 &&
        ReadPackedAttributeValue(unit, 0x01425041u) == 1;
    g_researchBuildingSet(unit, attribute, value);
    if (attribute == 0x01425041u || attribute == 0x02425041u)
        SyncKingdomResearchVisual(unit, hadAgent);
}
void __fastcall ResearchBuildingOwnerChanged(void* unit, void*, int owner) {
    const auto previous = *reinterpret_cast<const int*>(static_cast<const unsigned char*>(unit)+0x80);
    g_researchBuildingOwner(unit, owner);
    if (previous != owner) SyncKingdomResearchVisual(unit);
}
void SyncKingdomResearchBuildingList(void* list) {
    if (!list) return;
    // Literal stock building-list traversal at 42A6BD..42A799. Effects are
    // created/deleted in the separate overlay collection, not this list.
    void* sentinel = *reinterpret_cast<void**>(static_cast<unsigned char*>(list)+0x20);
    for (void* node = *static_cast<void**>(sentinel); node != sentinel;) {
        void* unit = *reinterpret_cast<void**>(static_cast<unsigned char*>(node)+0x0C);
        node = *static_cast<void**>(node);
        SyncKingdomResearchVisual(unit);
    }
}
void __fastcall ResearchWorldReadyAfterStock(void* game, void*) {
    g_researchWorldReady(game);
    // Called once on initial entry/reload, after native objects, GPL state and
    // saved container links are available; never during serialization itself.
    void* root = *reinterpret_cast<void**>(g_imageBase+0x3E3FD4u);
    void* world = root ? *reinterpret_cast<void**>(static_cast<unsigned char*>(root)+4) : nullptr;
    if (!world) return;
    void* catalog = *reinterpret_cast<void**>(static_cast<unsigned char*>(world)+0x8C);
    using Collection = void* (__thiscall*)(void*, int, int);
    SyncKingdomResearchBuildingList(reinterpret_cast<Collection>(g_imageBase+0x1B9030u)(catalog, 0, 0));
}

// This is only a reentrant call-stack guard, never purchase persistence. Stock
// debit/attribute notifications may refresh a panel before its order is added,
// and completion notifications run before the saved ledger can be committed.
void* g_kingdomResearchInFlight = nullptr;
std::uint32_t g_kingdomResearchInFlightCommand = 0;
struct KingdomResearchFlight {
    void* previousUnit = g_kingdomResearchInFlight;
    std::uint32_t previousCommand = g_kingdomResearchInFlightCommand;
    KingdomResearchFlight(void* unit, std::uint32_t command) {
        g_kingdomResearchInFlight = unit;
        g_kingdomResearchInFlightCommand = command;
    }
    ~KingdomResearchFlight() {
        g_kingdomResearchInFlight = previousUnit;
        g_kingdomResearchInFlightCommand = previousCommand;
    }
};
bool KingdomResearchHasStockOrder(void* unit, std::uint32_t command) {
    if (!unit || ReadPackedAttributeValue(unit, kCurrentResearchAttributeId) != static_cast<int>(command)) return false;
    auto** table = *static_cast<void***>(unit);
    if (reinterpret_cast<std::uintptr_t>(table[0x180/4]) != g_imageBase+0x1DF010u)
        StopUnsafeManagerRuntimeLaunch("Kingdom research encountered an unknown stock order accessor.");
    using Order = void* (__thiscall*)(void*, int, int);
    return reinterpret_cast<Order>(table[0x180/4])(unit, 1, 0x4005) != nullptr;
}
int KingdomResearchOrder(void* unit, std::uint32_t command) {
    const auto* record = FindKingdomResearch(command);
    if (!record || !KingdomResearchMatches(unit, *record)) return 0;
    if (unit == g_kingdomResearchInFlight && command == g_kingdomResearchInFlightCommand) return 1;
    return KingdomResearchHasStockOrder(unit, command) ? 1 : 0;
}
std::uint32_t KingdomResearchStatus(const KingdomResearchRecord& record, void* unit, int operation) {
    std::uint32_t result = 3;
    if (!EvaluateQuestBoardScalar(record.CallbackSymbol().c_str(), unit, true, operation, &result, false) || result > 3)
        StopUnsafeManagerRuntimeLaunch("The prepared kingdom research saved-state callback is missing or invalid.");
    return result;
}

bool __fastcall ExecuteKingdomResearch(void* processor, void*, void* unit, std::uint32_t command) {
    using Execute = bool (__thiscall*)(void*, void*, std::uint32_t);
    const auto original = reinterpret_cast<Execute>(g_imageBase+0x0E02F0u);
    const auto* record = FindKingdomResearch(command);
    if (!record) return original(processor, unit, command);
    if (!KingdomResearchMatches(unit, *record) ||
        ReadPackedAttributeValue(unit, kResearchDurationAttributeId) != 0 ||
        SelectedBuildingLevel(unit) < static_cast<int>(record->requiredLevel) ||
        ReadPackedAttributeValue(unit, 0x01425041u) != 1 ||
        ReadPackedAttributeValue(unit, 0x02425041u) != 1) return false;
    if (!RegisterPrivateResearchDescriptors())
        StopUnsafeManagerRuntimeLaunch("Could not register the kingdom research stock descriptor.");
    KingdomResearchFlight flight(unit, command);
    if (KingdomResearchStatus(*record, unit, 1) != 0) return false;
    // Stock alone checks the treasury, pays, notifies and creates its saved
    // 0x4005 order. If it refused, remove only the reservation; never refund.
    const bool result = original(processor, unit, command);
    if (!KingdomResearchHasStockOrder(unit, command)) KingdomResearchStatus(*record, unit, 3);
    return result;
}

bool CompleteKingdomResearch(std::uint32_t owner, void* unit,
    std::uint32_t event, std::uint32_t argument, std::uint32_t reason) {
    if (!unit || g_runtimeFeatureRegistry.kingdomResearch.empty()) return false;
    const auto command = static_cast<std::uint32_t>(ReadPackedAttributeValue(unit, kCurrentResearchAttributeId));
    const auto* record = FindKingdomResearch(command);
    if (!record || !KingdomResearchMatches(unit, *record)) return false;
    if (!RegisterPrivateResearchDescriptors())
        StopUnsafeManagerRuntimeLaunch("Could not restore the saved kingdom research descriptor.");
    KingdomResearchFlight flight(unit, command);
    g_stockResearchCompletion(owner, unit, event, argument, reason);
    if (reason == 2) {
        if (ReadPackedAttributeValue(unit, kCurrentResearchAttributeId) == static_cast<int>(command) ||
            KingdomResearchStatus(*record, unit, 2) != 1)
            StopUnsafeManagerRuntimeLaunch("Stock kingdom research completion did not retire its saved reservation.");
    } else if (reason == 1) {
        // AP99 ignores reason 1. Retire the private tuple using the same native
        // setters/ordering as its completion, so surviving canceled owners do
        // not remain busy. The stock order manager still owns order destruction;
        // no refund or replacement order is introduced.
        KingdomResearchStatus(*record, unit, 3);
        WritePackedAttributeValue(unit, kCurrentResearchAttributeId, 0);
        WritePackedAttributeValue(unit, kResearchDurationAttributeId, 0);
    }
    const auto parent = static_cast<std::uint32_t>(g_parentController);
    if (parent && NativePanelContext(parent) == unit) RefreshKingdomResearch(parent, false);
    return true;
}

const KingdomResearchRecord* KingdomResearchActivity(void* unit) {
    if (!unit) return nullptr;
    const auto* record = FindKingdomResearch(static_cast<std::uint32_t>(
        ReadPackedAttributeValue(unit, kCurrentResearchAttributeId)));
    return record && KingdomResearchMatches(unit, *record) ? record : nullptr;
}
void RefreshKingdomResearch(std::uint32_t controller, bool child) {
    if (child || g_runtimeFeatureRegistry.kingdomResearch.empty()) return;
    void* unit = NativePanelContext(controller);
    if (!unit) return;
    for (const auto& record : g_runtimeFeatureRegistry.kingdomResearch) {
        if (!KingdomResearchMatches(unit, record)) continue;
        if (!RegisterPrivateResearchDescriptors())
            StopUnsafeManagerRuntimeLaunch("Kingdom research presentation lost its stock descriptors.");
        const auto status = KingdomResearchStatus(record, unit, 0);
        const unsigned stage = *reinterpret_cast<const std::uint32_t*>(static_cast<unsigned char*>(unit)+0x7C) >> 24;
        const bool offered = stage >= '1'+record.requiredLevel-1 && stage <= '3' &&
            ReadPackedAttributeValue(unit, 0x01425041u) == 1 &&
            ReadPackedAttributeValue(unit, 0x02425041u) == 1;
        const bool active = KingdomResearchActivity(unit) == &record &&
            ReadPackedAttributeValue(unit, kResearchDurationAttributeId) > 0;
        // A private AP99 completion bit is a presentation mirror, not ownership.
        // Use the ordinary raw map setter to avoid recursively notifying this
        // same row. The saved GPL owner ledger is authoritative at execution.
        using Set = void (__thiscall*)(void*, std::uint32_t, int);
        reinterpret_cast<Set>(g_imageBase+0x1DE410u)(unit, record.completionAttribute, status == 1 ? 1 : 0);
        using Refresh = void (__cdecl*)(void*, void*, std::uint32_t);
        reinterpret_cast<Refresh>(g_imageBase+g_buildProfile->refreshSingleResearchRowRva)(
            *reinterpret_cast<void**>(controller+0x24), unit, record.actionControlId);
        SetControllerControlVisible(controller, record.actionControlId, offered && !active);
        SetControllerControlVisible(controller, record.actionControlId+500, offered);
        SetControllerControlVisible(controller, record.actionControlId+1000, offered && !active && status != 1);
        SetControllerControlVisible(controller, record.progressControlId, active);
        SetControllerControlVisible(controller, record.activeDisplayControlId, active);
        if (status != 0 || ReadPackedAttributeValue(unit, kResearchDurationAttributeId) != 0)
            SendControllerMessage(controller, record.actionControlId, 0x0A, 1, 0);
        if (active) {
            const auto started = static_cast<DWORD>(ReadPackedAttributeValue(unit, kResearchStartedAtAttributeId));
            const auto duration = static_cast<DWORD>(ReadPackedAttributeValue(unit, kResearchDurationAttributeId));
            const auto now = SimulationClock();
            std::uint32_t progress[4] = {7, now > started ? now-started : 0, 0, duration};
            SendControllerMessage(controller, record.progressControlId, 0x29, 0,
                reinterpret_cast<std::uint32_t>(progress));
            SendControllerMessage(controller, record.progressControlId, 0x08, 0, 0);
        }
    }
}
bool HandleKingdomResearch(void* controller, std::uint32_t command) {
    const auto* record = FindKingdomResearch(command);
    if (!record) return false;
    auto* unit = NativePanelContext(reinterpret_cast<std::uint32_t>(controller));
    if (!KingdomResearchMatches(unit, *record) ||
        KingdomResearchStatus(*record, unit, 0) != 0 ||
        ReadPackedAttributeValue(unit, kResearchDurationAttributeId) != 0) return true;
    using Affordable = bool (__thiscall*)(void*, std::uint32_t);
    if (reinterpret_cast<Affordable>(g_imageBase+g_buildProfile->canSubmitResearchRva)(controller, command)) {
        // AP99's literal command submission shape, with the live building.
        using Submit = void (__cdecl*)(void*, void*, std::uint32_t);
        reinterpret_cast<Submit>(g_imageBase+g_buildProfile->submitResearchCommandRva)(
            *reinterpret_cast<void**>(unit+0x94), unit, command);
    }
    return true;
}

bool InstallKingdomResearchGate() {
    if (g_runtimeFeatureRegistry.kingdomResearch.empty()) return true;
    if (g_buildProfile != &kBeta2BuildProfile) return false;
    auto* slot = reinterpret_cast<std::uintptr_t*>(g_imageBase+0x358E1Cu);
    const unsigned char orderGetter[] = {0x8B,0x01,0x8B,0x54,0x24,0x04,0x8B,0x80,0x6C,0x01,0,0};
    // Complete stock/evaluator bodies were validated before any hook install.
    if (*slot != g_imageBase+0x0E02F0u ||
        !MatchesProfileBytes(0x1DE410u, reinterpret_cast<const unsigned char*>("\x83\xc1\x04\xe9"),4,"native saved attribute setter") ||
        !MatchesProfileBytes(0x1DF010u, orderGetter, sizeof(orderGetter), "native research order lookup")) return false;
    DWORD old = 0;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &old)) return false;
    *slot = reinterpret_cast<std::uintptr_t>(&ExecuteKingdomResearch);
    DWORD ignored = 0;
    if (!VirtualProtect(slot, sizeof(*slot), old, &ignored)) return false;
    if (!KingdomResearchVisualsSelected()) return true;
    const auto replace = [](std::uintptr_t rva, const void* function) {
        auto* entry = reinterpret_cast<std::uintptr_t*>(g_imageBase+rva);
        DWORD protection = 0, restored = 0;
        if (!VirtualProtect(entry, sizeof(*entry), PAGE_READWRITE, &protection)) return false;
        *entry = reinterpret_cast<std::uintptr_t>(function);
        return VirtualProtect(entry, sizeof(*entry), protection, &restored) != 0;
    };
    g_researchBuildingSet = reinterpret_cast<ResearchBuildingSetFunction>(g_imageBase+0x49950u);
    g_researchBuildingOwner = reinterpret_cast<ResearchBuildingOwner>(g_imageBase+0x1CF320u);
    g_researchWorldReady = reinterpret_cast<ResearchWorldReady>(g_imageBase+0x2AAB0u);
    return replace(0x3531E8u, reinterpret_cast<const void*>(&ResearchBuildingSet)) &&
        replace(0x3530E4u, reinterpret_cast<const void*>(&ResearchBuildingOwnerChanged)) &&
        WriteOccupantBranch(g_imageBase+0x26234u, reinterpret_cast<void*>(&ResearchWorldReadyAfterStock), 0xE8);
}
