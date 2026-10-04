// Execute the production installer against private copies of all three PEs.
// Never execute game code, attach to Majesty, or alter an installed file.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <vector>
#include "../runtime/MapQueryRuntime.h"
#include "../runtime/RuntimeFeatureRegistry.h"
extern "C" unsigned char GogFixtureBytes[0x500000];

static int Research(void*, std::uint32_t) { return 0; }
static int Distance(void*, int value) { return value; }

static bool VerifyProductionBoundaries(unsigned char* image, MajestyBuildId id) {
    g_imageBase = reinterpret_cast<std::uintptr_t>(image);
    g_buildProfile = id == MajestyBuildId::SteamPublic ? &kPublicBuildProfile :
        id == MajestyBuildId::SteamBeta2 ? &kBeta2BuildProfile : &kGogBuildProfile;
    g_runtimeFeatureRegistry = {};
    g_stockControllerRegistry.Clear();
    MajestyRuntimeFeatures::KingdomResearchRecord research{};
    research.activeEffector = "FixtureEffector";
    g_runtimeFeatureRegistry.kingdomResearch.push_back(research);
    MajestyStockControllers::SovereignTargetActionRecord action{};
    action.sourceTargetCallback = "FixtureCallback";
    g_stockControllerRegistry.sovereignTargetActions.push_back(action);
    const struct { const char* name; bool (*check)(); } checks[] = {
        {"activity text", &ValidatePrivateIntentTextProfile},
        {"guild controller", &ValidateCustomGuildFactoryFallback},
        {"research completion", &ValidateResearchCompletionDispatchSlot},
        {"controller recipes", &ValidateStockControllerRecipeProfile},
        {"enchantment rows", &ValidatePrivateEnchantmentRowsProfile},
        {"reward flags", &ValidatePrivateRewardFlagProfile},
        {"name generators", &ValidatePrivateNameGeneratorProfile},
        {"research route", &ValidateStockResearchRoute},
        {"occupant panels", &ValidateOccupantPanelProfile},
        {"quest board", &ValidateQuestBoardProfile},
        {"hero information", &ValidateHeroInfoProfile},
        {"movement scale", &ValidateMovementScaleProfile},
        {"kingdom research with visuals", &ValidateKingdomResearchProfile},
        {"source-target actions", &ValidateSourceTargetProfile},
    };
    for (const auto& check : checks) {
        if (!check.check()) {
            std::fprintf(stderr, "Profile %u rejected %s\n", static_cast<unsigned>(id), check.name);
            return false;
        }
    }
    return MajestyFeatureParity::Validate(g_imageBase, id, MajestyFeatureParity::Feature::Equipment) &&
           MajestyPrivateRecruitment::Validate(g_imageBase, id);
}

static bool Verify(const char* path, MajestyBuildId id, DWORD stamp, DWORD registration) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) return false;
    const auto length = file.tellg();
    if (length < 4096 || length > 64 * 1024 * 1024) return false;
    std::vector<char> bytes(static_cast<std::size_t>(length));
    file.seekg(0); file.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!file) return false;
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(bytes.data());
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 ||
        static_cast<std::size_t>(dos->e_lfanew) + sizeof(IMAGE_NT_HEADERS32) > bytes.size()) return false;
    const auto* pe = reinterpret_cast<const IMAGE_NT_HEADERS32*>(bytes.data() + dos->e_lfanew);
    if (pe->Signature != IMAGE_NT_SIGNATURE || pe->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        pe->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        pe->FileHeader.TimeDateStamp != stamp || pe->OptionalHeader.ImageBase != 0x400000 ||
        pe->OptionalHeader.SizeOfImage > 0x500000) return false;
    const auto* sections = IMAGE_FIRST_SECTION(pe);
    if (reinterpret_cast<const char*>(sections + pe->FileHeader.NumberOfSections) > bytes.data() + bytes.size()) return false;
    const auto size = pe->OptionalHeader.SizeOfImage;
    if (size < 4096 || pe->OptionalHeader.SizeOfHeaders > size || pe->OptionalHeader.SizeOfHeaders > bytes.size()) return false;
    auto* image = GogFixtureBytes;
    if (image != reinterpret_cast<void*>(0x400000)) {
        std::fprintf(stderr, "Private fixture section is not at the required base\n"); return false;
    }
    bool ok = true;
    for (unsigned mask = 0; mask != 32 && ok; ++mask) {
        std::memset(image, 0, size);
        std::memcpy(image, bytes.data(), pe->OptionalHeader.SizeOfHeaders);
        for (unsigned i = 0; i != pe->FileHeader.NumberOfSections; ++i) {
            const auto& section = sections[i];
            if (static_cast<std::uint64_t>(section.PointerToRawData) + section.SizeOfRawData > bytes.size() ||
                static_cast<std::uint64_t>(section.VirtualAddress) + section.SizeOfRawData > size) { ok = false; break; }
            std::memcpy(image + section.VirtualAddress, bytes.data() + section.PointerToRawData, section.SizeOfRawData);
        }
        if (!ok) break;
        if (mask == 0 && !VerifyProductionBoundaries(image, id)) { ok = false; break; }
        MajestyRuntimeFeatures::Registry timing;
        timing.nativeTiming = true;
        const bool map = (mask & 1) != 0, movement = (mask & 2) != 0;
        const bool timed = (mask & 4) != 0, research = (mask & 8) != 0, distance = (mask & 16) != 0;
        const auto base = reinterpret_cast<std::uintptr_t>(image);
        // Invalid paired callbacks must still fail before touching code.
        if (InstallMapQueryRuntime(base, id, map, movement, timed ? &timing : nullptr,
                                  &Research, nullptr, distance ? &Distance : nullptr)) { ok = false; break; }
        if (!InstallMapQueryRuntime(base, id, map, movement, timed ? &timing : nullptr,
                                    research ? &Research : nullptr, research ? &Research : nullptr,
                                    distance ? &Distance : nullptr)) {
            std::fprintf(stderr, "Shared runtime installation rejected profile %u feature mask %u\n",
                         static_cast<unsigned>(id), mask);
            ok = false;
        }
        // For an active bridge, corrupting the actual registration call must fail.
        if (ok && (map || movement || timed || research)) {
            image[registration] = 0xCC;
            if (InstallMapQueryRuntime(base, id, true, true, &timing, &Research, &Research, &Distance)) ok = false;
        }
    }
    return ok;
}

int main(int argc, char** argv) {
    if (argc != 4) { std::fprintf(stderr, "Required: public beta2 GOG executable fixtures\n"); return 2; }
    return Verify(argv[1], MajestyBuildId::SteamPublic, 0x5897B72F, 0x198EE7) &&
           Verify(argv[2], MajestyBuildId::SteamBeta2, 0x5A8A11D5, 0x1ADE97) &&
           Verify(argv[3], MajestyBuildId::Gog, 0x5BBB8DB8, 0x1AD1E7) ? 0 : 1;
}
