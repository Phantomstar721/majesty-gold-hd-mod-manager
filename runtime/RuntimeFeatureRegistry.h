#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace MajestyRuntimeFeatures {

constexpr std::uint32_t kRegistryVersion = 1;
constexpr std::uint32_t kMaximumNameGeneratorCount = 256;
constexpr std::uint32_t kMaximumEnchantmentRowCount = 1024;
constexpr std::uint32_t kMaximumDisplayTextBytes = 512;
constexpr std::size_t kMaximumRegistryBytes = 1024u * 1024u;

struct NameGeneratorRecord {
    std::uint32_t generatorId;
    std::uint32_t namePartIds[4];
};

struct EnchantmentRowRecord {
    std::uint32_t overlayId;
    std::string displayText;
};

struct Registry {
    std::vector<NameGeneratorRecord> nameGenerators;
    std::vector<EnchantmentRowRecord> enchantmentRows;
    bool mapFogQuery = false;
    bool movementQuery = false;
    bool nativeTiming = false;
    std::vector<std::uint32_t> timingSpellIds;
    std::vector<std::uint32_t> timingEffectorIds;

    const EnchantmentRowRecord* FindEnchantmentRow(
        std::uint32_t overlayId) const;
};

// Parses the manager-owned, deterministic MMFR v1-v3 data formats. The parser is
// independent of Win32 and executable patching so every malformed boundary can
// be tested before the injected runtime consumes it.
bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    Registry* registry,
    std::string* error);

}  // namespace MajestyRuntimeFeatures
