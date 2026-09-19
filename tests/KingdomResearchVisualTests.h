// Included in the x86 runtime harness. Executes the actual native adapters
// against stock-shaped unit/list memory, without attaching to the game.
namespace {
unsigned visualCalls = 0, visualStockWrites = 0;
bool visualExpectStock = false;
bool visualWorldReady = false;
void* visualWorldList = nullptr;
void __fastcall VisualWorldReady(void*, void*) { visualWorldReady = true; }
void* __fastcall VisualCollection(void* catalog, void*, int kind, int filter) {
    assert(visualWorldReady && catalog == visualWorldList && kind == 0 && filter == 0);
    return visualWorldList;
}
int __fastcall VisualRead(void* unit, void*, std::uint32_t attribute, std::uint32_t fallback) {
    auto* words = static_cast<std::uint32_t*>(unit);
    if (attribute == 0x01425041u) return words[0x100/4];
    if (attribute == 0x02425041u) return words[0x104/4];
    return fallback;
}
void __fastcall VisualSet(void* unit, void*, std::uint32_t attribute, int value) {
    ++visualStockWrites;
    auto* words = static_cast<std::uint32_t*>(unit);
    if (attribute == 0x01425041u) words[0x100/4] = value;
    if (attribute == 0x02425041u) words[0x104/4] = value;
}
void __fastcall VisualOwner(void* unit, void*, int value) {
    ++visualStockWrites;
    static_cast<int*>(unit)[0x80/4] = value;
}
bool VisualEvaluate(const char* symbol, void* unit, bool hasInteger, int,
                    std::uint32_t* result, bool trace) {
    if (visualExpectStock) assert(visualStockWrites != 0);
    assert(!hasInteger && !trace && unit != nullptr);
    assert(std::strcmp(symbol, "MM_KR_01010101010101010101010101010101_Visual") == 0);
    ++visualCalls;
    *result = 1;
    return true;
}
void RunKingdomResearchVisualTests() {
    const auto savedBase = g_imageBase;
    const auto* savedProfile = g_buildProfile;
    const auto savedEvaluator = g_questBoardScalarEvaluator;
    const auto savedSet = g_researchBuildingSet;
    const auto savedOwner = g_researchBuildingOwner;
    const auto savedReady = g_researchWorldReady;
    auto savedRegistry = g_runtimeFeatureRegistry;
    MajestyBuildProfile profile = kBeta2BuildProfile;
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&VisualRead);
    g_imageBase = 0;
    g_buildProfile = &profile;
    g_questBoardScalarEvaluator = &VisualEvaluate;
    g_researchBuildingSet = reinterpret_cast<ResearchBuildingSetFunction>(&VisualSet);
    g_researchBuildingOwner = reinterpret_cast<ResearchBuildingOwner>(&VisualOwner);
    g_runtimeFeatureRegistry.kingdomResearch.clear();
    KingdomResearchRecord record{};
    record.identity = "01010101010101010101010101010101";
    record.buildingFamily = 0x00475845;
    g_runtimeFeatureRegistry.kingdomResearch.push_back(record);
    assert(!KingdomResearchVisualsSelected());
    auto& installed = g_runtimeFeatureRegistry.kingdomResearch[0];
    installed.activeEffector = "Example_Active";
    assert(KingdomResearchVisualsSelected());
    std::uint32_t unit[0x168/4] = {};
    unit[0x70/4] = 42;
    unit[0x7C/4] = 0x33475845; // EXG3
    visualCalls = visualStockWrites = 0;
    visualExpectStock = true;
    // Construction owner/readiness writes before a GPL agent exists do not
    // call scripts. Completion runs AFTER stock writes, including both flags.
    ResearchBuildingOwnerChanged(unit, nullptr, 1);
    ResearchBuildingSet(unit, nullptr, 0x02425041u, 1);
    assert(visualCalls == 0);
    ResearchBuildingSet(unit, nullptr, 0x01425041u, 1);
    assert(visualCalls == 1 && unit[0x100/4] == 1);
    ResearchBuildingSet(unit, nullptr, 0x02425041u, 0); // upgrade suspends
    assert(visualCalls == 2 && unit[0x104/4] == 0);
    ResearchBuildingSet(unit, nullptr, 0x02425041u, 1); // completion resumes
    assert(visualCalls == 3);
    ResearchBuildingOwnerChanged(unit, nullptr, 2);
    assert(visualCalls == 4 && unit[0x80/4] == 2);
    ResearchBuildingOwnerChanged(unit, nullptr, 2); // no change
    ResearchBuildingSet(unit, nullptr, 0x00425041u, 6); // capacity unrelated
    assert(visualCalls == 4);
    ResearchBuildingSet(unit, nullptr, 0x01425041u, 0); // remove if readiness lost
    assert(visualCalls == 5);
    unit[0x100/4] = 1;
    visualExpectStock = false;
    for (auto state : {4u, 0u}) {
        unit[0x74/4] = state;
        unit[0x70/4] = state ? 42 : 0xFFFFFFFFu;
        SyncKingdomResearchVisual(unit);
    }
    assert(visualCalls == 5); // dead and placement preview
    unit[0x70/4] = 42;
    unit[0x7C/4] = 0x3358595A; // unrelated family
    SyncKingdomResearchVisual(unit);
    assert(visualCalls == 5);
    unit[0x7C/4] = 0x33475845;
    // Stock saved-world category-zero list: one sentinel and one building.
    void* head[4] = {}, *node[4] = {}, *list[9] = {};
    list[8] = head; head[0] = node; node[0] = head; node[3] = unit;
    SyncKingdomResearchBuildingList(list);
    assert(visualCalls == 6);
    head[0] = head;
    SyncKingdomResearchBuildingList(list);
    assert(visualCalls == 6);
    // Execute the real post-initialization adapter too. This private synthetic
    // image contains only two JMP stubs and the stock-shaped root/collection;
    // it never maps or runs the game executable or touches a live process.
    auto* image = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x3E4000,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    assert(image != nullptr);
    const auto jump = [image](unsigned rva, const void* target) {
        image[rva] = 0xE9;
        const auto relative = static_cast<std::int32_t>(
            reinterpret_cast<std::uintptr_t>(target) - reinterpret_cast<std::uintptr_t>(image+rva+5));
        std::memcpy(image+rva+1, &relative, 4);
    };
    jump(0x100, reinterpret_cast<const void*>(&VisualRead));
    jump(0x1B9030, reinterpret_cast<const void*>(&VisualCollection));
    void* world[0x90/4] = {}, *root[2] = {};
    world[0x8C/4] = list; root[1] = world;
    *reinterpret_cast<void**>(image+0x3E3FD4) = root;
    head[0] = node;
    visualWorldList = list;
    visualWorldReady = false;
    g_researchWorldReady = reinterpret_cast<ResearchWorldReady>(&VisualWorldReady);
    g_imageBase = reinterpret_cast<std::uintptr_t>(image);
    profile.readPackedAttributeRva = 0x100;
    FlushInstructionCache(GetCurrentProcess(), image, 0x3E4000);
    ResearchWorldReadyAfterStock(nullptr, nullptr);
    assert(visualWorldReady && visualCalls == 7);
    g_imageBase = 0;
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&VisualRead);
    VirtualFree(image, 0, MEM_RELEASE);
    installed.activeEffector.clear();
    SyncKingdomResearchVisual(unit);
    assert(visualCalls == 7); // old v5 research remains effect-free
    g_runtimeFeatureRegistry = std::move(savedRegistry);
    g_researchBuildingSet = savedSet;
    g_researchBuildingOwner = savedOwner;
    g_researchWorldReady = savedReady;
    g_questBoardScalarEvaluator = savedEvaluator;
    g_buildProfile = savedProfile;
    g_imageBase = savedBase;
}
}
