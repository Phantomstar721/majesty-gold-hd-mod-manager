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

struct KingdomResearchRecord {
    std::string identity;
    std::uint32_t buildingFamily, actionControlId, descriptorTemplateControlId;
    std::uint32_t completionAttribute, requiredLevel, price;
    std::uint32_t goldBonusPercent, experienceBonusPercent;
    std::uint32_t progressControlId, activeDisplayControlId;
    std::string completionText;
    std::string activeEffector;
    std::string CallbackSymbol() const { return "MM_KR_" + identity; }
};

struct HeroInfoRecord {
    std::uint32_t kind, subjectId, unlockLevel, imageId, imageSet;
    std::string featureKey, displayText, tooltipText;
};

struct Registry {
    struct EquipmentRecord {
        std::uint32_t equipmentId;
        std::uint32_t slot;
        std::uint32_t nameTable;
    };
    std::vector<EquipmentRecord> equipment;
    std::vector<KingdomResearchRecord> kingdomResearch;
    std::vector<HeroInfoRecord> heroInfoRows;
    std::vector<NameGeneratorRecord> nameGenerators;
    std::vector<EnchantmentRowRecord> enchantmentRows;
    bool mapFogQuery = false;
    bool movementQuery = false;
    bool nativeTiming = false;
    std::vector<std::uint32_t> timingSpellIds;
    std::vector<std::uint32_t> timingEffectorIds;

    const EnchantmentRowRecord* FindEnchantmentRow(
        std::uint32_t overlayId) const;
    // Sorted range; a subject can have several passive rows, but only one
    // spell/effect row. Returns the first matching record, or null.
    const HeroInfoRecord* FindHeroInfo(std::uint32_t kind, std::uint32_t subjectId) const;
};

// Parses the manager-owned, deterministic MMFR v1-v7 data formats. The parser is
// independent of Win32 and executable patching so every malformed boundary can
// be tested before the injected runtime consumes it.
bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    Registry* registry,
    std::string* error);

}  // namespace MajestyRuntimeFeatures
