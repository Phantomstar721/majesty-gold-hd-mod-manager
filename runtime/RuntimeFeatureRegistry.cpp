#include "RuntimeFeatureRegistry.h"

#include <algorithm>
#include <cstring>
#include <utility>

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
    if (version != kRegistryVersion && version != 2) {
        SetError(error, "runtime feature registry schema version is unsupported");
        return false;
    }
    std::uint32_t flags = 0;
    if (version == 2 && (!ReadU32(bytes, size, &cursor, &flags) || (flags & ~3u) != 0)) {
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
    if (cursor != size) {
        SetError(error, "runtime feature registry contains trailing bytes");
        return false;
    }
    registry->nameGenerators = std::move(names);
    registry->enchantmentRows = std::move(rows);
    registry->mapFogQuery = (flags & 1u) != 0;
    registry->movementQuery = (flags & 2u) != 0;
    return true;
}

}  // namespace MajestyRuntimeFeatures
