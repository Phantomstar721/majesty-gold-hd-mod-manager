#include "IntentTextRegistry.h"

#include <cstring>
#include <utility>

namespace MajestyIntentText {
namespace {

constexpr unsigned char kMagic[4] = {'M', 'M', 'T', 'X'};
constexpr std::size_t kHeaderBytes = 12;
constexpr std::size_t kRecordHeaderBytes = 8;

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

bool IsDefinedCp1252Byte(unsigned char value) {
    // Windows-1252 deliberately leaves these five C1 positions undefined.
    return value != 0x81 && value != 0x8D && value != 0x8F &&
        value != 0x90 && value != 0x9D;
}

}  // namespace

bool IsPrivateIntentId(std::uint32_t id) {
    return id >= kFirstPrivateIntentId && id <= kLastPrivateIntentId;
}

bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    std::vector<RegistryRecord>* records,
    std::string* error) {
    if (records == nullptr || bytes == nullptr) {
        SetError(error, "registry buffer or output is null");
        return false;
    }
    records->clear();
    if (error != nullptr) {
        error->clear();
    }
    if (size < kHeaderBytes || size > kMaximumRegistryBytes) {
        SetError(error, "registry size is outside the supported bounds");
        return false;
    }
    if (std::memcmp(bytes, kMagic, sizeof(kMagic)) != 0) {
        SetError(error, "registry magic is not MMTX");
        return false;
    }

    std::size_t cursor = sizeof(kMagic);
    std::uint32_t version = 0;
    std::uint32_t count = 0;
    if (!ReadU32(bytes, size, &cursor, &version) ||
        !ReadU32(bytes, size, &cursor, &count)) {
        SetError(error, "registry header is truncated");
        return false;
    }
    if (version != kRegistryVersion) {
        SetError(error, "registry schema version is unsupported");
        return false;
    }
    if (count > kMaximumRecordCount) {
        SetError(error, "registry record count is outside the supported bounds");
        return false;
    }
    if (count > (size - cursor) / kRecordHeaderBytes) {
        SetError(error, "registry cannot contain its declared record count");
        return false;
    }

    std::vector<RegistryRecord> parsed;
    parsed.reserve(count);
    std::uint32_t previousId = 0;
    for (std::uint32_t index = 0; index < count; ++index) {
        std::uint32_t id = 0;
        std::uint32_t length = 0;
        if (!ReadU32(bytes, size, &cursor, &id) ||
            !ReadU32(bytes, size, &cursor, &length)) {
            SetError(error, "registry record header is truncated");
            return false;
        }
        if (!IsPrivateIntentId(id)) {
            SetError(error, "registry record ID is outside the private range");
            return false;
        }
        if (index != 0 && id <= previousId) {
            SetError(error, "registry record IDs are not strictly increasing");
            return false;
        }
        if (length == 0 || length > kMaximumTextBytes ||
            cursor > size || static_cast<std::size_t>(length) > size - cursor) {
            SetError(error, "registry text length is invalid or truncated");
            return false;
        }
        for (std::uint32_t textIndex = 0; textIndex < length; ++textIndex) {
            const unsigned char value = bytes[cursor + textIndex];
            if (value == 0 || !IsDefinedCp1252Byte(value)) {
                SetError(error, "registry text is not valid non-NUL Windows-1252");
                return false;
            }
        }
        RegistryRecord record = {};
        record.id = id;
        record.text.assign(
            reinterpret_cast<const char*>(bytes + cursor),
            static_cast<std::size_t>(length));
        parsed.push_back(std::move(record));
        previousId = id;
        cursor += length;
    }
    if (cursor != size) {
        SetError(error, "registry contains trailing bytes");
        return false;
    }
    *records = std::move(parsed);
    return true;
}

}  // namespace MajestyIntentText
