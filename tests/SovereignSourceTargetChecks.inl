namespace SovereignChecks {
unsigned char sourceA[0xA0] = {}, sourceB[0xA0] = {}, victim[0xA0] = {}, spell[0xA0] = {};
std::uint32_t submitted[6] = {}, executed[7] = {};
int nativeCalls = 0, callbackCalls = 0;
void* callbackSource = nullptr;
bool targetPresent = true, sourcePresent = true;
int __fastcall ReadResource(void*, void*, std::uint32_t attribute, std::uint32_t) {
    assert(attribute == 1);
    return packedValue;
}
void* Resolve(std::uint32_t id) {
    if (id == 101 && sourcePresent) return sourceA;
    if (id == 102 && sourcePresent) return sourceB;
    return id == 303 && targetPresent ? victim : nullptr;
}
void __cdecl Submit(std::uint32_t a, std::uint32_t b, std::uint32_t c,
    std::uint32_t d, std::uint32_t e, std::uint32_t f) {
    const std::uint32_t values[] = {a,b,c,d,e,f};
    std::memcpy(submitted, values, sizeof(values));
}
bool Callback(const char* name, void* unit, void* source, void* target) {
    assert(std::strcmp(name, "Private_Source_Target") == 0);
    assert(unit == spell && target == victim);
    callbackSource = source;
    ++callbackCalls;
    return true;
}
void __cdecl Execute(std::uint32_t a, std::uint32_t b, std::uint32_t c,
    std::uint32_t d, std::uint32_t e, std::uint32_t f, std::uint32_t g) {
    const std::uint32_t values[] = {a,b,c,d,e,f,g};
    std::memcpy(executed, values, sizeof(values));
    ++nativeCalls;
    if (g_sourceTargetExecution) {
        assert(g == 0 && f == 303);
        assert(SourceTargetBirth(nullptr, nullptr, spell, victim));
        assert(!SourceTargetBirth(nullptr, nullptr, spell, victim)); // no double callback
    }
}
void Run() {
    Reset();
    g_imageBase = 0;
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&ReadResource);
    profile.getPanelContextRva = reinterpret_cast<std::uintptr_t>(&Context);
    profile.sovereignSubmitCommandRva = reinterpret_cast<std::uintptr_t>(&Submit);
    g_buildProfile = &profile;
    g_stockControllerRegistry.Clear();
    g_stockControllerRegistry.panels.push_back({"private", 0x31425041, 0x32425041, 0x00424C41, 99});
    g_stockControllerRegistry.meters.push_back({"private", "resource", 1, 2, 3, 4});
    MajestyStockControllers::SovereignTargetActionRecord record = {};
    record.panelKey = "private"; record.resourceKey = "resource";
    record.sourceTargetCallback = "Private_Source_Target";
    record.privateMode = 0x31724150; record.privateUnitId = 0x31544150;
    record.stockTargetMode = 0x33327053; record.stockExecutorMode = 0x34317053;
    record.resourceCost = 10; record.requiredLevel = 3;
    g_stockControllerRegistry.sovereignTargetActions.push_back(record);
    auto* action = &g_stockControllerRegistry.sovereignTargetActions[0];
    for (auto* source : {sourceA, sourceB}) {
        *reinterpret_cast<std::uint32_t*>(source + 0x7C) = 0x33424C41;
        *reinterpret_cast<std::uint32_t*>(source + 0x80) = 1;
    }
    *reinterpret_cast<std::uint32_t*>(spell + 0x7C) = record.privateUnitId;
    g_sovereignUnitResolver = &Resolve;
    g_sourceTargetExecutor = &Execute;
    g_sourceTargetCallback = &Callback;
    g_pendingSovereignAction = action; g_pendingSovereignBuilding = 101;
    packedValue = 10;
    SubmitPrivateSovereignCommand(record.stockTargetMode, 1, 700, 800, 303, 1000);
    assert(submitted[0] == record.privateMode && submitted[4] == 303 && submitted[5] == 101);
    // Select another building and cancel the cursor before the queued action runs.
    g_pendingSovereignBuilding = 102; g_pendingSovereignAction = nullptr;
    ExecuteSourceTargetSovereignCommand(submitted[0], 9, submitted[1], submitted[2],
        submitted[3], submitted[4], submitted[5]);
    assert(callbackCalls == 1 && callbackSource == sourceA && executed[6] == 0);
    assert(g_sourceTargetExecution == nullptr);
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 1, 700, 800, 303, 102);
    assert(callbackCalls == 2 && callbackSource == sourceB);
    const int previous = nativeCalls;
    targetPresent = false;
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 1, 700, 800, 303, 101);
    targetPresent = true; sourcePresent = false;
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 1, 700, 800, 303, 101);
    sourcePresent = true;
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 2, 700, 800, 303, 101);
    assert(nativeCalls == previous && callbackCalls == 2);
    packedValue = 9;
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 1, 700, 800, 303, 101);
    assert(executed[0] == record.stockTargetMode && executed[6] == kStockUnaffordableGoldCost);
    assert(callbackCalls == 2);
    g_pendingSovereignAction = action; g_pendingSovereignBuilding = 101;
    SubmitPrivateSovereignCommand(record.stockTargetMode, 1, 700, 800, 303, 1000);
    assert(submitted[0] == record.stockTargetMode && submitted[4] == 303 && submitted[5] == kStockUnaffordableGoldCost);
    // Non-private commands preserve all seven stock fields.
    ExecuteSourceTargetSovereignCommand(123, 9, 1, 700, 800, 303, 456);
    assert(executed[0] == 123 && executed[5] == 303 && executed[6] == 456);
    // Legacy private actions retain the former building-as-target contract.
    action->sourceTargetCallback.clear(); packedValue = 10;
    g_activePanelRecord = &g_stockControllerRegistry.panels[0];
    g_parentController = reinterpret_cast<LONG>(&parent);
    SubmitPrivateSovereignCommand(record.stockTargetMode, 1, 700, 800, 303, 1000);
    assert(submitted[4] == 101 && submitted[5] == 0);
    ExecuteSourceTargetSovereignCommand(record.privateMode, 9, 1, 700, 800, 101, 0);
    assert(executed[0] == record.stockExecutorMode && executed[5] == 101 && executed[6] == 0);
    assert(g_sourceTargetExecution == nullptr);
}
}
