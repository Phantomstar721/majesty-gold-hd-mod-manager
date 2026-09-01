#include "../runtime/RuntimeFeatureRegistry.h"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

std::uint32_t FourCC(const char value[5]) {
    return static_cast<std::uint32_t>(value[0]) |
        (static_cast<std::uint32_t>(value[1]) << 8) |
        (static_cast<std::uint32_t>(value[2]) << 16) |
        (static_cast<std::uint32_t>(value[3]) << 24);
}

void AppendU32(std::vector<unsigned char>* bytes, std::uint32_t value) {
    bytes->push_back(static_cast<unsigned char>(value & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 8) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 16) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 24) & 0xFF));
}

std::vector<unsigned char> Header(
    std::uint32_t version,
    std::uint32_t nameCount,
    std::uint32_t rowCount) {
    std::vector<unsigned char> bytes = {'M', 'M', 'F', 'R'};
    AppendU32(&bytes, version);
    AppendU32(&bytes, nameCount);
    AppendU32(&bytes, rowCount);
    return bytes;
}

void AppendName(
    std::vector<unsigned char>* bytes,
    const char generator[5],
    const char first[5],
    const char second[5],
    const char third[5],
    const char fourth[5]) {
    AppendU32(bytes, FourCC(generator));
    AppendU32(bytes, FourCC(first));
    AppendU32(bytes, FourCC(second));
    AppendU32(bytes, FourCC(third));
    AppendU32(bytes, FourCC(fourth));
}

void AppendRow(
    std::vector<unsigned char>* bytes,
    const char overlay[5],
    const std::vector<unsigned char>& text) {
    AppendU32(bytes, FourCC(overlay));
    AppendU32(bytes, static_cast<std::uint32_t>(text.size()));
    bytes->insert(bytes->end(), text.begin(), text.end());
}

bool ExpectInvalid(
    const std::vector<unsigned char>& bytes,
    const char* expectedErrorPart) {
    MajestyRuntimeFeatures::Registry registry;
    std::string error;
    if (MajestyRuntimeFeatures::ParseRegistry(
            bytes.data(), bytes.size(), &registry, &error)) {
        std::fprintf(stderr, "Expected MMFR rejection.\n");
        return false;
    }
    if (error.find(expectedErrorPart) == std::string::npos) {
        std::fprintf(
            stderr,
            "Wrong MMFR rejection: expected '%s', got '%s'.\n",
            expectedErrorPart,
            error.c_str());
        return false;
    }
    return registry.nameGenerators.empty() && registry.enchantmentRows.empty();
}

}  // namespace

int main() {
    std::vector<unsigned char> valid = Header(1, 2, 2);
    AppendName(&valid, "NM18", "HN69", "HN70", "HN71", "HN72");
    AppendName(&valid, "NM19", "HN73", "HN74", "HN75", "HN76");
    AppendRow(
        &valid,
        "ALo1",
        std::vector<unsigned char>{'P','a','r','a','l','y','t','i','c'});
    AppendRow(
        &valid,
        "ALo2",
        std::vector<unsigned char>{'c','a','f',0xE9});
    MajestyRuntimeFeatures::Registry registry;
    std::string error;
    if (!MajestyRuntimeFeatures::ParseRegistry(
            valid.data(), valid.size(), &registry, &error)) {
        std::fprintf(stderr, "Valid MMFR rejected: %s\n", error.c_str());
        return 1;
    }
    if (registry.nameGenerators.size() != 2 ||
        registry.enchantmentRows.size() != 2 ||
        registry.nameGenerators[1].generatorId != FourCC("NM19") ||
        registry.nameGenerators[1].namePartIds[3] != FourCC("HN76")) {
        std::fprintf(stderr, "Valid MMFR records changed during parsing.\n");
        return 2;
    }
    const auto* row = registry.FindEnchantmentRow(FourCC("ALo2"));
    if (row == nullptr || row->displayText.size() != 4 ||
        static_cast<unsigned char>(row->displayText[3]) != 0xE9 ||
        registry.FindEnchantmentRow(FourCC("NOPE")) != nullptr) {
        std::fprintf(stderr, "MMFR row lookup did not preserve exact CP1252.\n");
        return 3;
    }

    std::vector<unsigned char> empty = Header(1, 0, 0);
    if (!MajestyRuntimeFeatures::ParseRegistry(
            empty.data(), empty.size(), &registry, &error) ||
        !registry.nameGenerators.empty() || !registry.enchantmentRows.empty()) {
        std::fprintf(stderr, "Empty MMFR was not accepted.\n");
        return 4;
    }

    for (std::size_t size = 0; size < valid.size(); ++size) {
        MajestyRuntimeFeatures::Registry truncatedRegistry;
        std::string truncatedError;
        if (MajestyRuntimeFeatures::ParseRegistry(
                valid.data(), size, &truncatedRegistry, &truncatedError) ||
            !truncatedRegistry.nameGenerators.empty() ||
            !truncatedRegistry.enchantmentRows.empty()) {
            std::fprintf(stderr, "MMFR truncation at %u bytes was accepted.\n",
                static_cast<unsigned int>(size));
            return 5;
        }
    }

    std::vector<unsigned char> trailing = valid;
    trailing.push_back(0);
    if (!ExpectInvalid(trailing, "trailing")) {
        return 6;
    }
    std::vector<unsigned char> badVersion = valid;
    badVersion[4] = 2;
    if (!ExpectInvalid(badVersion, "version")) {
        return 7;
    }
    std::vector<unsigned char> tooManyNames = Header(1, 257, 0);
    if (!ExpectInvalid(tooManyNames, "count")) {
        return 8;
    }
    std::vector<unsigned char> tooManyRows = Header(1, 0, 1025);
    if (!ExpectInvalid(tooManyRows, "count")) {
        return 9;
    }
    std::vector<unsigned char> oversized(
        MajestyRuntimeFeatures::kMaximumRegistryBytes + 1u, 0);
    if (!ExpectInvalid(oversized, "size")) {
        return 19;
    }

    std::vector<unsigned char> duplicateName = Header(1, 2, 0);
    AppendName(&duplicateName, "NM18", "HN69", "HN70", "HN71", "HN72");
    AppendName(&duplicateName, "NM18", "HN73", "HN74", "HN75", "HN76");
    if (!ExpectInvalid(duplicateName, "strictly increasing")) {
        return 10;
    }
    std::vector<unsigned char> reverseName = Header(1, 2, 0);
    AppendName(&reverseName, "NM19", "HN73", "HN74", "HN75", "HN76");
    AppendName(&reverseName, "NM18", "HN69", "HN70", "HN71", "HN72");
    if (!ExpectInvalid(reverseName, "strictly increasing")) {
        return 11;
    }
    std::vector<unsigned char> wrongNamePrefix = Header(1, 1, 0);
    AppendName(&wrongNamePrefix, "AB18", "HN69", "HN70", "HN71", "HN72");
    if (!ExpectInvalid(wrongNamePrefix, "NM FourCC")) {
        return 12;
    }
    std::vector<unsigned char> wrongPartPrefix = Header(1, 1, 0);
    AppendName(&wrongPartPrefix, "NM18", "XX69", "HN70", "HN71", "HN72");
    if (!ExpectInvalid(wrongPartPrefix, "HN FourCC")) {
        return 13;
    }
    std::vector<unsigned char> duplicateParts = Header(1, 1, 0);
    AppendName(&duplicateParts, "NM18", "HN69", "HN70", "HN69", "HN72");
    if (!ExpectInvalid(duplicateParts, "distinct")) {
        return 20;
    }
    std::vector<unsigned char> stockName = Header(1, 1, 0);
    AppendName(&stockName, "NM17", "HN69", "HN70", "HN71", "HN72");
    if (!ExpectInvalid(stockName, "collides with stock")) {
        return 18;
    }
    std::vector<unsigned char> stockNamePart = Header(1, 1, 0);
    AppendName(&stockNamePart, "NM18", "HN68", "HN69", "HN70", "HN71");
    if (!ExpectInvalid(stockNamePart, "collides with stock")) {
        return 21;
    }

    std::vector<unsigned char> duplicateRow = Header(1, 0, 2);
    AppendRow(&duplicateRow, "ALo1", std::vector<unsigned char>{'a'});
    AppendRow(&duplicateRow, "ALo1", std::vector<unsigned char>{'b'});
    if (!ExpectInvalid(duplicateRow, "strictly increasing")) {
        return 14;
    }
    std::vector<unsigned char> reverseRow = Header(1, 0, 2);
    AppendRow(&reverseRow, "ALo2", std::vector<unsigned char>{'a'});
    AppendRow(&reverseRow, "ALo1", std::vector<unsigned char>{'b'});
    if (!ExpectInvalid(reverseRow, "strictly increasing")) {
        return 15;
    }
    std::vector<unsigned char> invalidCp1252 = Header(1, 0, 1);
    AppendRow(&invalidCp1252, "ALo1", std::vector<unsigned char>{0x81});
    if (!ExpectInvalid(invalidCp1252, "Windows-1252")) {
        return 16;
    }
    std::vector<unsigned char> tooLongText = Header(1, 0, 1);
    AppendRow(&tooLongText, "ALo1", std::vector<unsigned char>(513, 'x'));
    if (!ExpectInvalid(tooLongText, "invalid or truncated")) {
        return 17;
    }

    std::puts("Runtime feature registry parser tests passed.");
    return 0;
}
