#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace MajestyRuntimeCapabilities {

constexpr std::uint32_t kManifestVersion = 1;
constexpr std::uint32_t kMaximumCapabilityCount = 64;
constexpr std::uint32_t kMaximumCapabilityBytes = 128;
constexpr std::size_t kMaximumManifestBytes = 64u * 1024u;

constexpr char kExpandedBuildingSlots[] =
    "expanded-building-slots.cg-prefix";
constexpr char kFreestyleCamRebind[] = "freestyle-cam-rebind.v1";
constexpr char kPrivateActivityText[] =
    "private-activity-text-registry.v1";
constexpr char kGenericVisitorLists[] = "generic-visitor-lists.v1";
constexpr char kAlchemistSecondaryController[] =
    "alchemist.cgbrewing-secondary-controller";
constexpr char kAlchemistPrivateOilRows[] =
    "alchemist.ap78-private-oil-rows";
constexpr char kAlchemistNameGenerator[] =
    "alchemist.nm18-name-generator";
constexpr char kPhantomNameGenerator[] =
    "phantom.nm19-name-generator";

struct Manifest {
    std::vector<std::string> capabilities;

    bool Has(const char* capability) const;
};

// Parses the manager-owned, deterministic MMCP v1 wire format. Keeping the
// parser independent of Win32 file I/O lets malformed input be tested without
// loading the injected runtime.
bool ParseManifest(
    const unsigned char* bytes,
    std::size_t size,
    Manifest* manifest,
    std::string* error);

bool IsSupportedCapability(const std::string& capability);

}  // namespace MajestyRuntimeCapabilities
