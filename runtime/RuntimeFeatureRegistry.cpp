#include "RuntimeFeatureRegistry.h"

#include <algorithm>
#include <cstring>
#include <utility>
#include <set>
#include <tuple>

namespace MajestyRuntimeFeatures {
namespace {

constexpr unsigned char kMagic[4] = {'M', 'M', 'F', 'R'};
constexpr std::size_t kHeaderBytes = 16;
constexpr std::size_t kNameGeneratorBytes = 20;
constexpr std::size_t kEnchantmentHeaderBytes = 8;

void SetError(std::string* error, const char* message) {
    if (error != nullptr) {
        *error = message;
    }
}

bool ReadU32(
    const unsigned char* bytes,
    std::size_t size,
    std::size_t* cursor,
    std::uint32_t* value) {
    if (*cursor > size || size - *cursor < sizeof(std::uint32_t)) {
        return false;
    }
    const unsigned char* source = bytes + *cursor;
    *value =
        static_cast<std::uint32_t>(source[0]) |
        (static_cast<std::uint32_t>(source[1]) << 8) |
        (static_cast<std::uint32_t>(source[2]) << 16) |
        (static_cast<std::uint32_t>(source[3]) << 24);
    *cursor += sizeof(std::uint32_t);
    return true;
}

bool IsPrintableFourCC(std::uint32_t value) {
    for (unsigned int index = 0; index < 4; ++index) {
        const unsigned char character = static_cast<unsigned char>(
            (value >> (index * 8)) & 0xFFu);
        if (character < 0x21 || character > 0x7E) {
            return false;
        }
    }
    return true;
}

bool HasPrefix(
    std::uint32_t value,
    unsigned char first,
    unsigned char second) {
    return static_cast<unsigned char>(value & 0xFFu) == first &&
        static_cast<unsigned char>((value >> 8) & 0xFFu) == second;
}

bool IsStockNameGeneratorId(std::uint32_t value) {
    const unsigned char tens = static_cast<unsigned char>((value >> 16) & 0xFFu);
    const unsigned char ones = static_cast<unsigned char>((value >> 24) & 0xFFu);
    if (tens < '0' || tens > '9' || ones < '0' || ones > '9') {
        return false;
    }
    const unsigned int number =
        static_cast<unsigned int>(tens - '0') * 10u +
        static_cast<unsigned int>(ones - '0');
    return number >= 1u && number <= 17u;
}

bool IsStockNamePartId(std::uint32_t value) {
    const unsigned char tens = static_cast<unsigned char>((value >> 16) & 0xFFu);
    const unsigned char ones = static_cast<unsigned char>((value >> 24) & 0xFFu);
    if (tens < '0' || tens > '9' || ones < '0' || ones > '9') {
        return false;
    }
    const unsigned int number =
        static_cast<unsigned int>(tens - '0') * 10u +
        static_cast<unsigned int>(ones - '0');
    return number >= 1u && number <= 68u;
}

bool IsDefinedCp1252Byte(unsigned char value) {
    return value != 0x81 && value != 0x8D && value != 0x8F &&
        value != 0x90 && value != 0x9D;
}

}  // namespace

const EnchantmentRowRecord* Registry::FindEnchantmentRow(
    std::uint32_t overlayId) const {
    const auto found = std::lower_bound(
        enchantmentRows.begin(),
        enchantmentRows.end(),
        overlayId,
        [](const EnchantmentRowRecord& record, std::uint32_t requested) {
            return record.overlayId < requested;
        });
    return found != enchantmentRows.end() && found->overlayId == overlayId
        ? &*found
        : nullptr;
}

const HeroInfoRecord* Registry::FindHeroInfo(std::uint32_t kind, std::uint32_t subjectId) const {
    const auto found = std::lower_bound(heroInfoRows.begin(), heroInfoRows.end(),
        std::make_pair(kind, subjectId), [](const HeroInfoRecord& r, const std::pair<std::uint32_t, std::uint32_t>& key) {
            return std::make_pair(r.kind, r.subjectId) < key;
        });
    return found != heroInfoRows.end() && found->kind == kind && found->subjectId == subjectId ? &*found : nullptr;
}

bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    Registry* registry,
    std::string* error) {
    if (registry == nullptr || bytes == nullptr) {
        SetError(error, "runtime feature registry buffer or output is null");
        return false;
    }
    registry->nameGenerators.clear();
    registry->enchantmentRows.clear();
    registry->mapFogQuery = false;
    registry->movementQuery = false;
    registry->nativeTiming = false;
    registry->timingSpellIds.clear();
    registry->timingEffectorIds.clear();
    registry->equipment.clear();
    registry->kingdomResearch.clear();
    registry->heroInfoRows.clear();
    registry->movementScales.clear();
    if (error != nullptr) {
        error->clear();
    }
    if (size < kHeaderBytes || size > kMaximumRegistryBytes) {
        SetError(error, "runtime feature registry size is outside supported bounds");
        return false;
    }
    if (std::memcmp(bytes, kMagic, sizeof(kMagic)) != 0) {
        SetError(error, "runtime feature registry magic is not MMFR");
        return false;
    }

    std::size_t cursor = sizeof(kMagic);
    std::uint32_t version = 0;
    std::uint32_t nameCount = 0;
    std::uint32_t rowCount = 0;
    if (!ReadU32(bytes, size, &cursor, &version) ||
        !ReadU32(bytes, size, &cursor, &nameCount) ||
        !ReadU32(bytes, size, &cursor, &rowCount)) {
        SetError(error, "runtime feature registry header is truncated");
        return false;
    }
    if (version < kRegistryVersion || version > 8) {
        SetError(error, "runtime feature registry schema version is unsupported");
        return false;
    }
    std::uint32_t flags = 0;
    if (version >= 2 && (!ReadU32(bytes, size, &cursor, &flags) ||
        (flags & ~(version == 8 ? 127u : version == 7 ? 63u : version >= 5 ? 31u : version == 4 ? 15u : version == 3 ? 7u : 3u)) != 0 ||
        (version == 3 && !(flags & 4u)) || (version == 4 && !(flags & 8u)) ||
        ((version == 5 || version == 6) && !(flags & 16u)) || (version == 7 && !(flags & 32u)) ||
        (version == 8 && !(flags & 64u)))) {
        SetError(error, "runtime feature registry flags are invalid or truncated");
        return false;
    }
    if (nameCount > kMaximumNameGeneratorCount) {
        SetError(error, "runtime feature name-generator count is outside supported bounds");
        return false;
    }
    if (rowCount > kMaximumEnchantmentRowCount) {
        SetError(error, "runtime feature enchantment-row count is outside supported bounds");
        return false;
    }
    const std::size_t minimum =
        kHeaderBytes +
        static_cast<std::size_t>(nameCount) * kNameGeneratorBytes +
        static_cast<std::size_t>(rowCount) * kEnchantmentHeaderBytes;
    if (minimum > size) {
        SetError(error, "runtime feature registry cannot contain its declared records");
        return false;
    }

    std::vector<NameGeneratorRecord> names;
    names.reserve(nameCount);
    std::uint32_t previousGenerator = 0;
    for (std::uint32_t index = 0; index < nameCount; ++index) {
        NameGeneratorRecord record = {};
        if (!ReadU32(bytes, size, &cursor, &record.generatorId)) {
            SetError(error, "runtime feature name-generator record is truncated");
            return false;
        }
        for (std::size_t part = 0; part < 4; ++part) {
            if (!ReadU32(bytes, size, &cursor, &record.namePartIds[part])) {
                SetError(error, "runtime feature name-generator record is truncated");
                return false;
            }
        }
        if (!IsPrintableFourCC(record.generatorId) ||
            !HasPrefix(record.generatorId, 'N', 'M')) {
            SetError(error, "runtime feature generator ID is not an NM FourCC");
            return false;
        }
        if (IsStockNameGeneratorId(record.generatorId)) {
            SetError(error, "runtime feature generator ID collides with stock Majesty");
            return false;
        }
        if (index != 0 && record.generatorId <= previousGenerator) {
            SetError(error, "runtime feature generator IDs are not strictly increasing");
            return false;
        }
        for (const std::uint32_t part : record.namePartIds) {
            if (!IsPrintableFourCC(part) || !HasPrefix(part, 'H', 'N')) {
                SetError(error, "runtime feature name part is not an HN FourCC");
                return false;
            }
            if (IsStockNamePartId(part)) {
                SetError(error, "runtime feature name part collides with stock Majesty");
                return false;
            }
        }
        for (std::size_t left = 0; left < 4; ++left) {
            for (std::size_t right = left + 1; right < 4; ++right) {
                if (record.namePartIds[left] == record.namePartIds[right]) {
                    SetError(error, "runtime feature name parts must be distinct");
                    return false;
                }
            }
        }
        names.push_back(record);
        previousGenerator = record.generatorId;
    }

    std::vector<EnchantmentRowRecord> rows;
    rows.reserve(rowCount);
    std::uint32_t previousOverlay = 0;
    for (std::uint32_t index = 0; index < rowCount; ++index) {
        std::uint32_t overlayId = 0;
        std::uint32_t textLength = 0;
        if (!ReadU32(bytes, size, &cursor, &overlayId) ||
            !ReadU32(bytes, size, &cursor, &textLength)) {
            SetError(error, "runtime feature enchantment-row header is truncated");
            return false;
        }
        if (!IsPrintableFourCC(overlayId)) {
            SetError(error, "runtime feature overlay ID is not a printable FourCC");
            return false;
        }
        if (index != 0 && overlayId <= previousOverlay) {
            SetError(error, "runtime feature overlay IDs are not strictly increasing");
            return false;
        }
        if (textLength == 0 || textLength > kMaximumDisplayTextBytes ||
            cursor > size || static_cast<std::size_t>(textLength) > size - cursor) {
            SetError(error, "runtime feature display text is invalid or truncated");
            return false;
        }
        for (std::uint32_t textIndex = 0; textIndex < textLength; ++textIndex) {
            const unsigned char value = bytes[cursor + textIndex];
            if (value == 0 || !IsDefinedCp1252Byte(value)) {
                SetError(error, "runtime feature display text is not valid non-NUL Windows-1252");
                return false;
            }
        }
        EnchantmentRowRecord record = {};
        record.overlayId = overlayId;
        record.displayText.assign(
            reinterpret_cast<const char*>(bytes + cursor),
            static_cast<std::size_t>(textLength));
        rows.push_back(std::move(record));
        previousOverlay = overlayId;
        cursor += textLength;
    }
    std::vector<std::uint32_t> spells, effectors;
    if (flags & 4u) {
        for (auto* family : {&spells, &effectors}) {
            std::uint32_t count = 0, previous = 0;
            if (!ReadU32(bytes, size, &cursor, &count) || count > 1024 ||
                count > (size-cursor)/4) {
                SetError(error, "native timing resource count is invalid or truncated");
                return false;
            }
            family->reserve(count);
            for (std::uint32_t i = 0; i < count; ++i) {
                std::uint32_t id = 0;
                if (!ReadU32(bytes, size, &cursor, &id) || !IsPrintableFourCC(id) ||
                    (i != 0 && id <= previous)) {
                    SetError(error, "native timing IDs must be sorted, unique printable FourCCs");
                    return false;
                }
                family->push_back(id);
                previous = id;
            }
        }
    }
    std::vector<Registry::EquipmentRecord> equipment;
    if (flags & 8u) {
        std::uint32_t count = 0, previous = 0;
        if (!ReadU32(bytes, size, &cursor, &count) || count == 0 || count > 256 || count > (size-cursor)/12) {
            SetError(error, "equipment record count is invalid or truncated");
            return false;
        }
        equipment.reserve(count);
        for (std::uint32_t i = 0; i < count; ++i) {
            Registry::EquipmentRecord record{};
            if (!ReadU32(bytes, size, &cursor, &record.equipmentId) ||
                !ReadU32(bytes, size, &cursor, &record.slot) ||
                !ReadU32(bytes, size, &cursor, &record.nameTable) ||
                record.equipmentId < 0x800000 || record.equipmentId > 0xFFFFFF ||
                record.equipmentId <= previous || record.slot > 1 || !IsPrintableFourCC(record.nameTable)) {
                SetError(error, "equipment records must contain sorted unique private identities, a valid slot and name table");
                return false;
            }
            previous = record.equipmentId;
            equipment.push_back(record);
        }
    }
    std::vector<KingdomResearchRecord> research;
    if (flags & 16u) {
        std::uint32_t count = 0;
        if (!ReadU32(bytes, size, &cursor, &count) || count == 0 || count > 32) {
            SetError(error, "kingdom research count is invalid or truncated"); return false;
        }
        std::set<std::uint32_t> commands, attributes, families;
        std::string previous;
        constexpr char hex[] = "0123456789abcdef";
        for (std::uint32_t index = 0; index < count; ++index) {
            if (cursor > size || size-cursor < 60) {
                SetError(error, "kingdom research record is truncated"); return false;
            }
            KingdomResearchRecord record{};
            for (unsigned i = 0; i < 16; ++i) {
                const auto value = bytes[cursor++];
                record.identity.push_back(hex[value >> 4]);
                record.identity.push_back(hex[value & 15]);
            }
            std::uint32_t textSize = 0;
            for (auto* field : {&record.buildingFamily, &record.actionControlId,
                    &record.descriptorTemplateControlId, &record.completionAttribute,
                    &record.requiredLevel, &record.price, &record.goldBonusPercent,
                    &record.experienceBonusPercent, &record.progressControlId,
                    &record.activeDisplayControlId, &textSize}) {
                if (!ReadU32(bytes, size, &cursor, field)) return false;
            }
            const auto templ = record.descriptorTemplateControlId;
            const bool templateValid = (templ >= 0x1388 && templ <= 0x138D) || templ == 0x1392 ||
                templ == 0x139C || templ == 0x139D || (templ >= 0x13A6 && templ <= 0x13AB) ||
                (templ >= 0x13B0 && templ <= 0x13B3) || templ == 0x13BA ||
                (templ >= 0x13C5 && templ <= 0x13CA);
            bool familyValid = record.buildingFamily > 0 && record.buildingFamily <= 0xFFFFFF;
            auto family = record.buildingFamily;
            for (unsigned byte = 0; byte < 3; ++byte) {
                if ((family & 255) < 0x21 || (family & 255) > 0x7E) familyValid = false;
                family >>= 8;
            }
            const std::set<std::uint32_t> controls{record.actionControlId,
                record.actionControlId+500, record.actionControlId+1000,
                record.progressControlId, record.activeDisplayControlId};
            if (!templateValid || !familyValid || record.identity <= previous ||
                record.actionControlId < 0x22CF || record.actionControlId > 0x7FFFFC17 ||
                record.completionAttribute < 0xD0000000 || record.completionAttribute > 0xDFFFFFFF ||
                record.requiredLevel < 1 || record.requiredLevel > 3 ||
                record.price < 1 || record.price > 1000000 ||
                record.goldBonusPercent > 100 || record.experienceBonusPercent > 100 ||
                !(record.goldBonusPercent || record.experienceBonusPercent) || controls.size() != 5 ||
                record.progressControlId < 0x22CF || record.progressControlId > 0x7FFFFFFF ||
                record.activeDisplayControlId < 0x22CF || record.activeDisplayControlId > 0x7FFFFFFF ||
                !commands.insert(record.actionControlId).second ||
                !attributes.insert(record.completionAttribute).second ||
                !families.insert(record.buildingFamily).second ||
                textSize == 0 || textSize > 96 || size-cursor < textSize) {
                SetError(error, "kingdom research fields, identity or text are invalid"); return false;
            }
            for (std::uint32_t i = 0; i < textSize; ++i) {
                if (!bytes[cursor+i] || !IsDefinedCp1252Byte(bytes[cursor+i])) {
                    SetError(error, "kingdom research completion text is invalid"); return false;
                }
            }
            record.completionText.assign(reinterpret_cast<const char*>(bytes+cursor), textSize);
            cursor += textSize;
            if (version >= 6) {
                std::uint32_t length = 0;
                if (!ReadU32(bytes, size, &cursor, &length) || length > 64 || size-cursor < length) {
                    SetError(error, "kingdom research active effector is truncated or oversized"); return false;
                }
                for (unsigned i = 0; i < length; ++i) {
                    const unsigned char c = bytes[cursor+i];
                    if (!(c == '_' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                          (i && c >= '0' && c <= '9'))) {
                        SetError(error, "kingdom research active effector name is invalid"); return false;
                    }
                }
                record.activeEffector.assign(reinterpret_cast<const char*>(bytes+cursor), length);
                cursor += length;
            }
            previous = record.identity;
            research.push_back(std::move(record));
        }
        if (version == 6 && std::none_of(research.begin(), research.end(),
                [](const KingdomResearchRecord& r) { return !r.activeEffector.empty(); })) {
            SetError(error, "MMFR v6 requires an active effector"); return false;
        }
    }
    std::vector<HeroInfoRecord> info;
    if (flags & 32u) {
        std::uint32_t count = 0;
        if (!ReadU32(bytes, size, &cursor, &count) || !count || count > 1024) {
            SetError(error, "hero information row count is invalid"); return false;
        }
        for (std::uint32_t i = 0; i < count; ++i) {
            HeroInfoRecord r = {};
            std::uint32_t nk = 0, nl = 0, nt = 0;
            for (auto* field : {&r.kind, &r.subjectId, &r.unlockLevel, &r.imageId, &r.imageSet, &nk, &nl, &nt}) {
                if (!ReadU32(bytes, size, &cursor, field)) {
                    SetError(error, "hero information row is truncated"); return false;
                }
            }
            if (r.kind < 1 || r.kind > 3 || !IsPrintableFourCC(r.subjectId) ||
                !IsPrintableFourCC(r.imageId) || r.imageId == 0x6E544E49 || r.imageId == 0x33395849 ||
                r.imageSet > 0xFFFFFF || (r.kind == 3 ? r.unlockLevel < 1 || r.unlockLevel > 1000 : r.unlockLevel != 0) ||
                !nk || nk > 64 || !nl || nl > 512 || !nt || nt > 512 || size-cursor < nk+nl+nt) {
                SetError(error, "hero information row fields are invalid"); return false;
            }
            for (std::uint32_t j = 0; j < nk; ++j) {
                const auto c = bytes[cursor+j];
                if (!((c >= 'a' && c <= 'z') || (j && (c == '-' || (c >= '0' && c <= '9'))))) {
                    SetError(error, "hero information key is invalid"); return false;
                }
            }
            for (std::uint32_t j = nk; j < nk+nl+nt; ++j) {
                if (!bytes[cursor+j] || !IsDefinedCp1252Byte(bytes[cursor+j])) {
                    SetError(error, "hero information text is invalid"); return false;
                }
            }
            r.featureKey.assign(reinterpret_cast<const char*>(bytes+cursor), nk); cursor += nk;
            r.displayText.assign(reinterpret_cast<const char*>(bytes+cursor), nl); cursor += nl;
            r.tooltipText.assign(reinterpret_cast<const char*>(bytes+cursor), nt); cursor += nt;
            if (!info.empty()) {
                const auto& p = info.back();
                if (std::tie(r.kind, r.subjectId, r.featureKey) <= std::tie(p.kind, p.subjectId, p.featureKey) ||
                    (r.kind != 3 && r.kind == p.kind && r.subjectId == p.subjectId)) {
                    SetError(error, "hero information rows must be sorted and unique"); return false;
                }
            }
            if (r.kind == 2 && std::any_of(rows.begin(), rows.end(),
                    [&r](const EnchantmentRowRecord& old) { return old.overlayId == r.subjectId; })) {
                SetError(error, "hero information and legacy rows claim the same overlay"); return false;
            }
            info.push_back(std::move(r));
        }
    }
    std::vector<MovementScaleRecord> scales;
    if (flags & 64u) {
        std::uint32_t count = 0, previous = 0;
        if (!ReadU32(bytes, size, &cursor, &count) || !count || count > 256 || count > (size-cursor)/8) {
            SetError(error, "movement scale count is invalid or truncated"); return false;
        }
        for (std::uint32_t i = 0; i < count; ++i) {
            MovementScaleRecord record{};
            if (!ReadU32(bytes, size, &cursor, &record.overlayId) ||
                !ReadU32(bytes, size, &cursor, &record.percent) ||
                !IsPrintableFourCC(record.overlayId) || record.overlayId <= previous ||
                record.percent < 1 || record.percent > 1000) {
                SetError(error, "movement scales must contain sorted unique overlays and percentages 1..1000"); return false;
            }
            previous = record.overlayId;
            scales.push_back(record);
        }
    }
    if (cursor != size) {
        SetError(error, "runtime feature registry contains trailing bytes");
        return false;
    }
    registry->nameGenerators = std::move(names);
    registry->enchantmentRows = std::move(rows);
    registry->mapFogQuery = (flags & 1u) != 0;
    registry->movementQuery = (flags & 2u) != 0;
    registry->nativeTiming = (flags & 4u) != 0;
    registry->timingSpellIds = std::move(spells);
    registry->timingEffectorIds = std::move(effectors);
    registry->equipment = std::move(equipment);
    registry->kingdomResearch = std::move(research);
    registry->heroInfoRows = std::move(info);
    registry->movementScales = std::move(scales);
    return true;
}

}  // namespace MajestyRuntimeFeatures
