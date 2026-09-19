// Map fixture bytes as data only. No game code, process, window, or package runs.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cstdio>
#include <fstream>
#include <iterator>
#include "GogStandardModTests.h"
#include "GogQuestTests.h"

extern "C" unsigned char GogFixtureBytes[0x500000];

static bool Check(bool value, const char* name) {
    if (!value) std::fprintf(stderr, "GOG profile check failed: %s\n", name);
    return value;
}

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    StandardModTests::Run();
    QuestTests::Run();
    std::string registryRoot;
    std::vector<const char*> executables;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--registries") == 0 && i + 1 < argc)
            registryRoot = argv[++i];
        else executables.push_back(argv[i]);
    }
    auto* mapped = GogFixtureBytes;
    if (!Check(mapped == reinterpret_cast<void*>(0x400000), "fixture mapping")) return 4;
    for (const auto* executable : executables) {
        std::ifstream input(executable, std::ios::binary);
        std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(input)), {});
        if (bytes.size() < 0x400) return 3;
        auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(bytes.data());
        auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(bytes.data() + dos->e_lfanew);
        if (nt->OptionalHeader.SizeOfImage > 0x500000) return 3;
        std::memset(mapped, 0, 0x500000);
        std::memcpy(mapped, bytes.data(), nt->OptionalHeader.SizeOfHeaders);
        const auto* sections = IMAGE_FIRST_SECTION(nt);
        for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i)
            std::memcpy(mapped + sections[i].VirtualAddress,
                bytes.data() + sections[i].PointerToRawData, sections[i].SizeOfRawData);
        g_imageBase = reinterpret_cast<std::uintptr_t>(mapped);
        g_buildProfile = &kGogBuildProfile;
        // Inspect the generated utility payload, including code after its
        // alignment padding. Each path must return to the GOG stock lifecycle.
        for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
            if (std::strncmp(reinterpret_cast<const char*>(sections[i].Name), ".muqk", 8) != 0) continue;
            const auto* code = mapped + sections[i].VirtualAddress;
            if (code[0] == 0) continue; // a deliberately inert section
            for (const auto offset : {42, 92}) {
                if (!Check(RelativeCallTarget(code + offset) == g_imageBase + 0x78BB0,
                        "unlock click/reset calls stock GOG map rebuild")) return 7;
            }
            for (const auto& target : {std::make_pair(19, 0x11DA47), std::make_pair(51, 0x79569),
                    std::make_pair(62, 0x7980F), std::make_pair(110, 0x7999D)}) {
                std::int32_t relative = 0;
                std::memcpy(&relative, code + target.first + 1, 4);
                if (!Check(code[target.first] == 0xE9 &&
                        reinterpret_cast<std::uintptr_t>(code + target.first + 5) + relative == g_imageBase + target.second,
                        "unlock stock GOG continuation")) return 7;
            }
        }
        g_stockControllerRegistry.Clear();
        g_runtimeFeatureRegistry = {};
        g_runtimeCapabilities.capabilities = {
            MajestyRuntimeCapabilities::kGenericControllerRecipes,
            MajestyRuntimeCapabilities::kExpandedBuildingSlots,
            MajestyRuntimeCapabilities::kFreestyleCamRebind,
            MajestyRuntimeCapabilities::kGenericVisitorLists,
            MajestyRuntimeCapabilities::kGenericNameGenerator,
            MajestyRuntimeCapabilities::kGenericEnchantmentRow,
            MajestyRuntimeCapabilities::kPrivateActivityText,
            MajestyRuntimeCapabilities::kMapFogQuery,
            MajestyRuntimeCapabilities::kMovementQuery,
            MajestyRuntimeCapabilities::kNativeTiming,
        };
        bool valid = Check(ValidateStockControllerRecipeProfile(), "recipe sites") &&
            Check(ValidatePrivateRewardFlagProfile(), "reward sites") &&
            Check(ValidateQuestBoardProfile(), "list and occupant sites") &&
            Check(ValidateStockResearchRoute(), "research route") &&
            Check(MajestyPrivateRecruitment::Validate(g_imageBase, MajestyBuildId::Gog), "recruitment clones") &&
            Check(MajestyGogAudit::Validate(g_imageBase, MajestyGogAudit::kRecipes,
                sizeof(MajestyGogAudit::kRecipes) / sizeof(MajestyGogAudit::kRecipes[0])), "complete recipe bodies");
        valid = Check(ValidateMajestyBuildProfile(), "selected controller capability") && valid;
        valid = Check(ValidateGogStandardModProfile(), "Standard manifest stock lifecycle") && valid;
        valid = Check(ValidateGogQuestProfile(), "Quest manifest stock lifecycle") && valid;
        for (const auto& range : MajestyGogAudit::kWorkshopQuests) {
            mapped[range.rva] ^= 1;
            valid = Check(!ValidateGogQuestProfile(), "Quest lifecycle mutation rejection") && valid;
            mapped[range.rva] ^= 1;
        }
        for (const auto& range : MajestyGogAudit::kStandardMods) {
            mapped[range.rva] ^= 1;
            valid = Check(!ValidateGogStandardModProfile(), "Standard lifecycle mutation rejection") && valid;
            mapped[range.rva] ^= 1;
        }
        g_buildProfile = &kBeta2BuildProfile;
        valid = Check(!ValidateGogQuestProfile(), "Quest bridge excludes Steam") && valid;
        valid = Check(!ValidateGogStandardModProfile(), "Standard bridge excludes Steam") && valid;
        g_buildProfile = &kGogBuildProfile;
        // Exercise every handoff policy: an empty registry skips these exact
        // branch guards, even when the controller capability is selected.
        for (unsigned policy = 0; policy < 8; ++policy) {
            QuestBoard board{};
            board.parentControllerBase = kAp10DialogId;
            board.stayOnPanelAfterAction = (policy & 1) != 0;
            board.focusSelectedRowOnClick = (policy & 2) == 0;
            board.actionUsesParent = (policy & 4) != 0;
            g_stockControllerRegistry.liveAgentLists = {board};
            valid = Check(ValidateMajestyBuildProfile(), "selected list handoff policy") && valid;
        }
        // Wrong message slots and altered jump-table targets must still fail.
        const auto& occupant = OccupantProfile();
        mapped[occupant.selectionFocusBranch + 7] = 0x68;
        valid = Check(!ValidateOccupantPanelProfile(), "focus slot mutation rejection") && valid;
        mapped[occupant.selectionFocusBranch + 7] = 0x74;
        mapped[occupant.selectionFocusJumpTableEntry] ^= 1;
        valid = Check(!ValidateOccupantPanelProfile(), "focus target mutation rejection") && valid;
        mapped[occupant.selectionFocusJumpTableEntry] ^= 1;
        g_stockControllerRegistry.Clear();
        for (std::size_t i = 0; i < 24 && valid; ++i)
            valid = Check(MajestyGogAudit::ValidateController(g_imageBase, i), "parent lifecycle");
        // A renderer mutation outside the helper's exact sites must fail.
        mapped[0x98F40] ^= 1;
        valid = Check(!MajestyGogAudit::Validate(g_imageBase, MajestyGogAudit::kRecipes,
            sizeof(MajestyGogAudit::kRecipes) / sizeof(MajestyGogAudit::kRecipes[0])), "renderer mutation rejection") && valid;
        mapped[0x98F40] ^= 1;
        for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
            if (std::memcmp(sections[i].Name, ".mgvl\0\0", 8) != 0) continue;
            mapped[sections[i].VirtualAddress + 0x10] ^= 1;
            valid = Check(!MajestyGogAudit::ValidateVisitorOverlay(g_imageBase), "helper mutation rejection") && valid;
            mapped[sections[i].VirtualAddress + 0x10] ^= 1;
        }
        if (!registryRoot.empty()) {
            const auto read = [&](const char* name) {
                std::ifstream file(registryRoot + "/" + name, std::ios::binary);
                return std::vector<unsigned char>((std::istreambuf_iterator<char>(file)), {});
            };
            const auto capabilities = read("majesty_mod_manager_capabilities.bin");
            const auto controllers = read("majesty_mod_manager_controllers.bin");
            const auto features = read("majesty_mod_manager_features.bin");
            std::string error;
            if (!Check(MajestyRuntimeCapabilities::ParseManifest(capabilities.data(), capabilities.size(),
                    &g_runtimeCapabilities, &error), "selected capability manifest") ||
                !Check(MajestyStockControllers::ParseRegistry(controllers.data(), controllers.size(),
                    &g_stockControllerRegistry, &error), "selected controller registry") ||
                !Check(MajestyRuntimeFeatures::ParseRegistry(features.data(), features.size(),
                    &g_runtimeFeatureRegistry, &error), "selected feature registry")) return 6;
            valid = Check(ValidateMajestyBuildProfile(), "complete selected launch profile") && valid;
        }
        if (!valid) return 5;
    }
    return 0;
}
