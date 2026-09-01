#include "../runtime/RuntimeCapabilityManifest.h"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

void AppendU32(std::vector<unsigned char>* bytes, std::uint32_t value) {
    bytes->push_back(static_cast<unsigned char>(value));
    bytes->push_back(static_cast<unsigned char>(value >> 8));
    bytes->push_back(static_cast<unsigned char>(value >> 16));
    bytes->push_back(static_cast<unsigned char>(value >> 24));
}

std::vector<unsigned char> Encode(
    const std::vector<std::string>& capabilities,
    std::uint32_t version = 1) {
    std::vector<unsigned char> bytes = {'M', 'M', 'C', 'P'};
    AppendU32(&bytes, version);
    AppendU32(&bytes, static_cast<std::uint32_t>(capabilities.size()));
    for (const auto& capability : capabilities) {
        AppendU32(&bytes, static_cast<std::uint32_t>(capability.size()));
        bytes.insert(bytes.end(), capability.begin(), capability.end());
    }
    return bytes;
}

bool ExpectValid(
    const std::vector<std::string>& capabilities,
    const char* expected = nullptr) {
    const auto bytes = Encode(capabilities);
    MajestyRuntimeCapabilities::Manifest manifest;
    std::string error;
    if (!MajestyRuntimeCapabilities::ParseManifest(
            bytes.data(), bytes.size(), &manifest, &error)) {
        std::fprintf(stderr, "Expected valid MMCP: %s\n", error.c_str());
        return false;
    }
    if (manifest.capabilities != capabilities) {
        std::fprintf(stderr, "Parsed MMCP capabilities differ.\n");
        return false;
    }
    if (expected != nullptr && !manifest.Has(expected)) {
        std::fprintf(stderr, "Expected capability is absent.\n");
        return false;
    }
    return true;
}

bool ExpectInvalid(
    std::vector<unsigned char> bytes,
    const char* expectedError) {
    MajestyRuntimeCapabilities::Manifest manifest;
    std::string error;
    if (MajestyRuntimeCapabilities::ParseManifest(
            bytes.data(), bytes.size(), &manifest, &error)) {
        std::fprintf(stderr, "Expected MMCP rejection.\n");
        return false;
    }
    if (error != expectedError) {
        std::fprintf(
            stderr,
            "Wrong MMCP rejection: expected '%s', got '%s'.\n",
            expectedError,
            error.c_str());
        return false;
    }
    return true;
}

bool ExpectCapabilityProfiles() {
    using namespace MajestyRuntimeCapabilities;
    const auto standardBytes = Encode({});
    Manifest standard;
    std::string error;
    if (!ParseManifest(
            standardBytes.data(), standardBytes.size(), &standard, &error) ||
        !standard.capabilities.empty() ||
        standard.Has(kExpandedBuildingSlots) ||
        standard.Has(kFreestyleCamRebind) ||
        standard.Has(kPrivateActivityText) ||
        standard.Has(kGenericControllerRecipes) ||
        standard.Has(kGenericEnchantmentRow) ||
        standard.Has(kGenericNameGenerator)) {
        std::fprintf(
            stderr,
            "Standard-only empty MMCP did not remain capability-free: %s\n",
            error.c_str());
        return false;
    }

    const std::vector<std::string> hauntOnly = {
        kExpandedBuildingSlots,
        kFreestyleCamRebind,
        kGenericVisitorLists,
        kPrivateActivityText,
        kGenericNameGenerator,
    };
    const auto hauntBytes = Encode(hauntOnly);
    Manifest haunt;
    if (!ParseManifest(
            hauntBytes.data(), hauntBytes.size(), &haunt, &error)) {
        std::fprintf(stderr, "Haunt-only MMCP was rejected: %s\n", error.c_str());
        return false;
    }
    if (!haunt.Has(kExpandedBuildingSlots) ||
        !haunt.Has(kFreestyleCamRebind) ||
        !haunt.Has(kGenericNameGenerator) ||
        !haunt.Has(kPrivateActivityText) ||
        haunt.Has(kGenericControllerRecipes) ||
        haunt.Has(kGenericEnchantmentRow)) {
        std::fprintf(stderr, "Haunt-only MMCP enabled an incorrect hook group.\n");
        return false;
    }

    const std::vector<std::string> combined = {
        kExpandedBuildingSlots,
        kFreestyleCamRebind,
        kGenericVisitorLists,
        kPrivateActivityText,
        kGenericEnchantmentRow,
        kGenericControllerRecipes,
        kGenericNameGenerator,
    };
    const auto combinedBytes = Encode(combined);
    Manifest all;
    if (!ParseManifest(
            combinedBytes.data(), combinedBytes.size(), &all, &error)) {
        std::fprintf(stderr, "Combined MMCP was rejected: %s\n", error.c_str());
        return false;
    }
    if (!all.Has(kGenericEnchantmentRow) ||
        !all.Has(kGenericNameGenerator) ||
        !all.Has(kGenericControllerRecipes)) {
        std::fprintf(stderr, "Combined MMCP omitted a private hook group.\n");
        return false;
    }
    return true;
}

}  // namespace

int main() {
    using namespace MajestyRuntimeCapabilities;
    if (!ExpectValid({}) ||
        !ExpectValid(
            {kExpandedBuildingSlots, kGenericControllerRecipes},
            kGenericControllerRecipes) ||
        !ExpectCapabilityProfiles()) {
        return 1;
    }
    if (!ExpectInvalid(Encode({kExpandedBuildingSlots}, 2),
            "capability manifest schema version is unsupported") ||
        !ExpectInvalid(Encode({"Example.MixedCase"}),
            "capability name is not canonical lowercase ASCII") ||
        !ExpectInvalid(Encode({"example.future-hook.v1"}),
            "capability is not supported by this runtime") ||
        !ExpectInvalid(
            Encode({kGenericControllerRecipes, kExpandedBuildingSlots}),
            "capability names are not strictly increasing") ||
        !ExpectInvalid(
            Encode({kExpandedBuildingSlots, kExpandedBuildingSlots}),
            "capability names are not strictly increasing")) {
        return 1;
    }
    auto trailing = Encode({});
    trailing.push_back(0);
    if (!ExpectInvalid(
            trailing, "capability manifest contains trailing bytes")) {
        return 1;
    }
    auto truncated = Encode({kExpandedBuildingSlots});
    truncated.pop_back();
    if (!ExpectInvalid(
            truncated, "capability length is invalid or truncated")) {
        return 1;
    }
    std::puts("Runtime capability manifest parser tests passed.");
    return 0;
}
