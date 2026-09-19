#include "RuntimeCapabilityManifest.h"

#include <algorithm>
#include <cstring>
#include <utility>

namespace MajestyRuntimeCapabilities {
namespace {

constexpr unsigned char kMagic[4] = {'M', 'M', 'C', 'P'};
constexpr std::size_t kHeaderBytes = 12;
constexpr std::size_t kRecordHeaderBytes = 4;

constexpr const char* kSupportedCapabilities[] = {
    kExpandedBuildingSlots,
    kFreestyleCamRebind,
    kGenericEnchantmentRow,
    kGenericControllerRecipes,
    kGenericNameGenerator,
    kGenericVisitorLists,
    kPrivateActivityText,
    kMapFogQuery,
    kMovementQuery,
    kNativeTiming,
    kEquipment,
    kKingdomResearch,
    kHeroInfo,
};

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

bool IsCanonicalCapabilityName(const std::string& value) {
    if (value.empty()) {
        return false;
    }
    std::size_t segmentLength = 0;
    bool previousWasHyphen = false;
    std::size_t segments = 1;
    for (const unsigned char character : value) {
        const bool alphanumeric =
            (character >= 'a' && character <= 'z') ||
            (character >= '0' && character <= '9');
        if (character == '.') {
            if (segmentLength == 0 || previousWasHyphen) {
                return false;
            }
            ++segments;
            segmentLength = 0;
            previousWasHyphen = false;
            continue;
        }
        if (!alphanumeric && character != '-') {
            return false;
        }
        if (segmentLength == 0 && character == '-') {
            return false;
        }
        previousWasHyphen = character == '-';
        ++segmentLength;
    }
    return segments >= 2 && segmentLength != 0 && !previousWasHyphen;
}

}  // namespace

bool Manifest::Has(const char* capability) const {
    return capability != nullptr && std::binary_search(
        capabilities.begin(), capabilities.end(), std::string(capability));
}

bool IsSupportedCapability(const std::string& capability) {
    for (const char* supported : kSupportedCapabilities) {
        if (capability == supported) {
            return true;
        }
    }
    return false;
}

bool ParseManifest(
    const unsigned char* bytes,
    std::size_t size,
    Manifest* manifest,
    std::string* error) {
    if (manifest == nullptr || bytes == nullptr) {
        SetError(error, "capability manifest buffer or output is null");
        return false;
    }
    manifest->capabilities.clear();
    if (error != nullptr) {
        error->clear();
    }
    if (size < kHeaderBytes || size > kMaximumManifestBytes) {
        SetError(error, "capability manifest size is outside the supported bounds");
        return false;
    }
    if (std::memcmp(bytes, kMagic, sizeof(kMagic)) != 0) {
        SetError(error, "capability manifest magic is not MMCP");
        return false;
    }

    std::size_t cursor = sizeof(kMagic);
    std::uint32_t version = 0;
    std::uint32_t count = 0;
    if (!ReadU32(bytes, size, &cursor, &version) ||
        !ReadU32(bytes, size, &cursor, &count)) {
        SetError(error, "capability manifest header is truncated");
        return false;
    }
    if (version != kManifestVersion) {
        SetError(error, "capability manifest schema version is unsupported");
        return false;
    }
    if (count > kMaximumCapabilityCount) {
        SetError(error, "capability count is outside the supported bounds");
        return false;
    }
    if (count > (size - cursor) / kRecordHeaderBytes) {
        SetError(error, "capability manifest cannot contain its declared count");
        return false;
    }

    std::vector<std::string> parsed;
    parsed.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        std::uint32_t length = 0;
        if (!ReadU32(bytes, size, &cursor, &length)) {
            SetError(error, "capability record header is truncated");
            return false;
        }
        if (length == 0 || length > kMaximumCapabilityBytes ||
            cursor > size || static_cast<std::size_t>(length) > size - cursor) {
            SetError(error, "capability length is invalid or truncated");
            return false;
        }
        std::string capability(
            reinterpret_cast<const char*>(bytes + cursor),
            static_cast<std::size_t>(length));
        cursor += length;
        if (!IsCanonicalCapabilityName(capability)) {
            SetError(error, "capability name is not canonical lowercase ASCII");
            return false;
        }
        if (!IsSupportedCapability(capability)) {
            SetError(error, "capability is not supported by this runtime");
            return false;
        }
        if (!parsed.empty() && capability <= parsed.back()) {
            SetError(error, "capability names are not strictly increasing");
            return false;
        }
        parsed.push_back(std::move(capability));
    }
    if (cursor != size) {
        SetError(error, "capability manifest contains trailing bytes");
        return false;
    }
    manifest->capabilities = std::move(parsed);
    return true;
}

}  // namespace MajestyRuntimeCapabilities
