// Opt-in v2 command transport. Both identities travel in the stock serialized
// packet; no UI pointer or last-click state is consulted when it executes.
struct SovereignSourceTargetProfile {
    std::uintptr_t worldPointer, lookup, lookupCall, birthCall, birthInvoker;
};
SovereignSourceTargetProfile SourceTargetProfile() {
    switch (g_buildProfile->buildId) {
    case MajestyBuildId::SteamPublic:
        return {0x3C544C, 0x1A15F0, 0x0DA093, 0x0DAD8A, 0x1C5B20};
    case MajestyBuildId::SteamBeta2:
        return {0x3E3FD4, 0x1B65A0, 0x0DA6A3, 0x0DB39A, 0x1DAD00};
    case MajestyBuildId::Gog:
        return {0x3E426C, 0x1B58F0, 0x0DADE3, 0x0DBADA, 0x1DA050};
    default: return {};
    }
}

bool HasSourceTargetActions() {
    return std::any_of(g_stockControllerRegistry.sovereignTargetActions.begin(),
        g_stockControllerRegistry.sovereignTargetActions.end(),
        [](const MajestyStockControllers::SovereignTargetActionRecord& item) {
            return !item.sourceTargetCallback.empty();
        });
}

bool ValidateSourceTargetProfile() {
    if (!HasSourceTargetActions()) return true;
    const auto p = SourceTargetProfile();
    const unsigned char args[] = {0x57,0x56,0x8D,0x88,0x90,0,0,0};
    // The world lookup address and the complete argument-push boundary are
    // pinned against the existing sovereign executor, not discovered heuristically.
    const auto worldLoad = g_buildProfile->sovereignExecutorEntryRva + 0x34;
    const unsigned char load[] = {0xA1};
    const unsigned char manager[] = {0x8B,0x68,0x04};
    return p.worldPointer != 0 &&
        MatchesProfileBytes(worldLoad, load, sizeof(load), "sovereign world load") &&
        *reinterpret_cast<const std::uint32_t*>(g_imageBase + worldLoad + 1) == g_imageBase + p.worldPointer &&
        MatchesProfileBytes(worldLoad + 5, manager, sizeof(manager), "sovereign world manager") &&
        OccupantCallMatches(p.lookupCall, p.lookup) &&
        OccupantCallMatches(p.birthCall, p.birthInvoker) &&
        MatchesProfileBytes(p.birthCall - sizeof(args), args, sizeof(args), "sovereign birth arguments");
}

void* ResolveSovereignUnit(std::uint32_t handle) {
    if (!handle || handle == 0xFFFFFFFFu) return nullptr;
    const auto p = SourceTargetProfile();
    auto* world = *reinterpret_cast<unsigned char**>(g_imageBase + p.worldPointer);
    if (!world) return nullptr;
    void* manager = *reinterpret_cast<void**>(world + 4);
    if (!manager) return nullptr;
    using Lookup = void* (__thiscall*)(void*, std::uint32_t);
    return reinterpret_cast<Lookup>(g_imageBase + p.lookup)(manager, handle);
}
using SovereignUnitResolver = void* (*)(std::uint32_t);
SovereignUnitResolver g_sovereignUnitResolver = &ResolveSovereignUnit;

bool SourceMatchesAction(void* source, std::uint32_t player,
    const MajestyStockControllers::SovereignTargetActionRecord& action) {
    const auto* panel = g_stockControllerRegistry.FindPanelByKey(action.panelKey);
    if (!source || !panel) return false;
    const auto* data = static_cast<const unsigned char*>(source);
    const auto type = *reinterpret_cast<const std::uint32_t*>(data + 0x7C);
    std::uint32_t mask = 0xFFFFFFFFu;
    if ((panel->buildingFamilyId & 0xFF000000u) == 0) mask = 0x00FFFFFFu;
    if ((panel->buildingFamilyId & 0xFFFF0000u) == 0) mask = 0x0000FFFFu;
    if ((panel->buildingFamilyId & 0xFFFFFF00u) == 0) mask = 0x000000FFu;
    return *reinterpret_cast<const std::uint32_t*>(data + 0x80) == player &&
        (type & mask) == panel->buildingFamilyId &&
        SelectedBuildingLevel(source) >= static_cast<int>(action.requiredLevel);
}

using SovereignExecutor = void (__cdecl*)(std::uint32_t, std::uint32_t,
    std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
SovereignExecutor g_sourceTargetExecutor = nullptr;
struct SourceTargetExecution {
    const MajestyStockControllers::SovereignTargetActionRecord* action;
    void* source;
    void* target;
    bool dispatched;
};
thread_local SourceTargetExecution* g_sourceTargetExecution = nullptr;
struct SourceTargetScope {
    SourceTargetExecution* previous;
    LONG previousUnit;
    explicit SourceTargetScope(SourceTargetExecution* current)
        : previous(g_sourceTargetExecution), previousUnit(g_executingSovereignUnit) {
        g_sourceTargetExecution = current;
    }
    ~SourceTargetScope() {
        g_sourceTargetExecution = previous;
        g_executingSovereignUnit = previousUnit;
    }
};
bool EvaluateSourceTargetCallback(const char*, void*, void*, void*);
using SourceTargetCallback = bool (*)(const char*, void*, void*, void*);
SourceTargetCallback g_sourceTargetCallback = &EvaluateSourceTargetCallback;

void __cdecl ExecuteSourceTargetSovereignCommand(std::uint32_t mode,
    std::uint32_t commandContext, std::uint32_t player, std::uint32_t x,
    std::uint32_t y, std::uint32_t target, std::uint32_t cost) {
    const auto* action = g_stockControllerRegistry.FindSovereignByPrivateMode(mode);
    const bool paired = action && !action->sourceTargetCallback.empty();
    SourceTargetExecution execution = {action, nullptr, nullptr, false};
    SourceTargetScope scope(paired ? &execution : nullptr);
    if (paired) {
        // V2 reserves the otherwise-zero private gold-cost word for source ID.
        // Decode before entering stock code, so it can never become a gold debit.
        execution.source = g_sovereignUnitResolver(cost);
        execution.target = g_sovereignUnitResolver(target);
        if (!SourceMatchesAction(execution.source, player, *action) || !execution.target) return;
        cost = 0;
        const auto* meter = g_stockControllerRegistry.FindMeter(action->panelKey, action->resourceKey);
        if (!meter || ReadPackedAttributeValue(execution.source, meter->attributeId, 0) <
                static_cast<int>(action->resourceCost)) {
            // Recheck at execution too: a prior queued cast may have spent it.
            g_sourceTargetExecution = nullptr;
            g_sourceTargetExecutor(action->stockTargetMode, commandContext, player,
                x, y, target, kStockUnaffordableGoldCost);
            return;
        }
    }
    if (action) {
        g_executingSovereignUnit = static_cast<LONG>(action->privateUnitId);
        mode = action->stockExecutorMode;
    } else g_executingSovereignUnit = 0;
    g_sourceTargetExecutor(mode, commandContext, player, x, y, target, cost);
}

bool __fastcall SourceTargetBirth(void* nativeCallback, void*, void* spell, void* target) {
    auto* frame = g_sourceTargetExecution;
    if (frame && !frame->dispatched && frame->target == target && spell &&
        *reinterpret_cast<const std::uint32_t*>(static_cast<unsigned char*>(spell) + 0x7C) ==
            frame->action->privateUnitId) {
        frame->dispatched = true;
        return g_sourceTargetCallback(frame->action->sourceTargetCallback.c_str(),
            spell, frame->source, target);
    }
    // Do not invoke a v1 birthscript on a broken v2 invocation.
    if (frame) return false;
    using Invoke = bool (__thiscall*)(void*, void*, void*);
    return reinterpret_cast<Invoke>(g_imageBase + SourceTargetProfile().birthInvoker)(nativeCallback, spell, target);
}

bool InstallSourceTargetBirthHook() {
    const auto p = SourceTargetProfile();
    auto* call = reinterpret_cast<unsigned char*>(g_imageBase + p.birthCall);
    DWORD old = 0;
    if (!VirtualProtect(call, 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&SourceTargetBirth) - reinterpret_cast<std::uintptr_t>(call + 5));
    call[0] = 0xE8;
    std::memcpy(call + 1, &relative, 4);
    FlushInstructionCache(GetCurrentProcess(), call, 5);
    DWORD ignored = 0;
    VirtualProtect(call, 5, old, &ignored);
    return true;
}
