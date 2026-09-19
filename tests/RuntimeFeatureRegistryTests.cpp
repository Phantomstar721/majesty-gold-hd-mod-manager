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
    badVersion[4] = 99;
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

    auto mapQuery = Header(2, 0, 0);
    AppendU32(&mapQuery, 1);
    if (!MajestyRuntimeFeatures::ParseRegistry(mapQuery.data(), mapQuery.size(), &registry, &error) ||
        !registry.mapFogQuery) return 22;
    mapQuery.back() = 2;
    if (!ExpectInvalid(mapQuery, "flags")) return 23;
    for (unsigned flags = 0; flags <= 3; ++flags) {
        auto queries = Header(2, 0, 0);
        AppendU32(&queries, flags);
        if (!MajestyRuntimeFeatures::ParseRegistry(queries.data(), queries.size(), &registry, &error) ||
            registry.mapFogQuery != ((flags & 1) != 0) ||
            registry.movementQuery != ((flags & 2) != 0)) return 24;
    }
    if (!MajestyRuntimeFeatures::ParseRegistry(empty.data(), empty.size(), &registry, &error) ||
        registry.mapFogQuery || registry.movementQuery) return 25;
    for (unsigned flags = 4; flags < 8; ++flags) {
        auto timing = Header(3,0,0);
        AppendU32(&timing,flags);
        AppendU32(&timing,1); AppendU32(&timing,FourCC("Za01"));
        AppendU32(&timing,1); AppendU32(&timing,FourCC("Ze01"));
        if (!MajestyRuntimeFeatures::ParseRegistry(timing.data(),timing.size(),&registry,&error) ||
            !registry.nativeTiming || registry.timingSpellIds != std::vector<std::uint32_t>{FourCC("Za01")} ||
            registry.timingEffectorIds != std::vector<std::uint32_t>{FourCC("Ze01")} ||
            registry.mapFogQuery != ((flags & 1) != 0) || registry.movementQuery != ((flags & 2) != 0)) return 26;
        for (std::size_t size = 0; size < timing.size(); ++size) {
            if (MajestyRuntimeFeatures::ParseRegistry(timing.data(),size,&registry,&error) ||
                registry.nativeTiming || !registry.timingSpellIds.empty() || !registry.timingEffectorIds.empty()) return 27;
        }
    }
    for (unsigned flags : {0u,1u,2u,3u,8u,0xffffffffu}) {
        auto timing = Header(3,0,0); AppendU32(&timing,flags);
        AppendU32(&timing,0); AppendU32(&timing,0);
        if (!ExpectInvalid(timing,"flags")) return 28;
    }
    for (unsigned flags = 8; flags < 16; ++flags) {
        auto equipment = Header(4, 0, 0);
        AppendU32(&equipment, flags);
        if (flags & 4) { AppendU32(&equipment, 0); AppendU32(&equipment, 0); }
        AppendU32(&equipment, 2);
        AppendU32(&equipment, 0x800001); AppendU32(&equipment, 0); AppendU32(&equipment, FourCC("ZN01"));
        AppendU32(&equipment, 0x900001); AppendU32(&equipment, 1); AppendU32(&equipment, FourCC("ZN02"));
        if (!MajestyRuntimeFeatures::ParseRegistry(equipment.data(), equipment.size(), &registry, &error) ||
            registry.equipment.size() != 2 || registry.equipment[1].slot != 1 ||
            registry.equipment[0].equipmentId != 0x800001) return 29;
        for (std::size_t size = 0; size < equipment.size(); ++size) {
            if (MajestyRuntimeFeatures::ParseRegistry(equipment.data(), size, &registry, &error) ||
                !registry.equipment.empty()) return 30;
        }
        equipment[equipment.size()-8] = 2; // illegal armor slot
        if (!ExpectInvalid(equipment, "equipment records")) return 31;
    }
    auto noEquipment = Header(4, 0, 0); AppendU32(&noEquipment, 8); AppendU32(&noEquipment, 0);
    if (!ExpectInvalid(noEquipment, "equipment record count")) return 32;
    auto research = Header(5, 0, 0);
    AppendU32(&research, 16); AppendU32(&research, 1);
    research.insert(research.end(), 16, 1);
    for (auto value : {0x00475845u, 0x7300u, 0x139Cu, 0xD1234567u, 3u,
            3000u, 15u, 15u, 0x7301u, 0x7302u, 4u}) AppendU32(&research, value);
    research.insert(research.end(), {'T','e','s','t'});
    if (!MajestyRuntimeFeatures::ParseRegistry(research.data(), research.size(), &registry, &error) ||
        registry.kingdomResearch.size() != 1 || registry.kingdomResearch[0].price != 3000 ||
        registry.kingdomResearch[0].CallbackSymbol() != "MM_KR_01010101010101010101010101010101") return 33;
    for (std::size_t size = 0; size < research.size(); ++size) {
        if (MajestyRuntimeFeatures::ParseRegistry(research.data(), size, &registry, &error) ||
            !registry.kingdomResearch.empty()) return 34;
    }
    for (auto offset : {42u, 43u, 47u, 48u, 55u, 56u, 62u, 64u, 68u, 75u, 79u, 80u, 84u}) {
        auto bad = research;
        bad[offset] = offset == 84u ? 0 : 0xFF;
        // Invalid family/template/attribute/level/price/percent/controls/text.
        if (MajestyRuntimeFeatures::ParseRegistry(bad.data(), bad.size(), &registry, &error)) {
            std::fprintf(stderr, "Accepted invalid kingdom record field at %u\n", offset); return 35;
        }
    }
    auto visual = research;
    visual[4] = 6;
    AppendU32(&visual, 14);
    const char visualName[] = "Example_Active";
    visual.insert(visual.end(), visualName, visualName+14);
    if (!MajestyRuntimeFeatures::ParseRegistry(visual.data(), visual.size(), &registry, &error) ||
        registry.kingdomResearch[0].activeEffector != visualName) return 36;
    for (std::size_t size = 0; size < visual.size(); ++size)
        if (MajestyRuntimeFeatures::ParseRegistry(visual.data(), size, &registry, &error)) return 37;
    for (unsigned invalid : {0u, 0xFFu, static_cast<unsigned>('1'), static_cast<unsigned>('"')}) {
        auto bad = visual;
        bad[bad.size()-14] = static_cast<unsigned char>(invalid);
        if (!ExpectInvalid(bad, "effector name")) return 38;
    }
    auto noVisual = research;
    noVisual[4] = 6;
    AppendU32(&noVisual, 0);
    if (!ExpectInvalid(noVisual, "requires an active effector")) return 39;
    auto info = Header(7, 0, 0);
    AppendU32(&info, 32); AppendU32(&info, 1);
    for (auto value : {3u, FourCC("ZH01"), 2u, FourCC("ZI01"), 1019u, 3u, 5u, 4u}) AppendU32(&info, value);
    const char infoText[] = "keyLabelHelp";
    info.insert(info.end(), infoText, infoText+12);
    if (!MajestyRuntimeFeatures::ParseRegistry(info.data(), info.size(), &registry, &error) ||
        registry.heroInfoRows.size() != 1 || !registry.FindHeroInfo(3, FourCC("ZH01")) ||
        registry.FindHeroInfo(2, FourCC("ZH01")) || registry.heroInfoRows[0].tooltipText != "Help") return 40;
    for (std::size_t size = 0; size < info.size(); ++size)
        if (MajestyRuntimeFeatures::ParseRegistry(info.data(), size, &registry, &error) || !registry.heroInfoRows.empty()) return 41;
    for (unsigned offset : {24u, 28u, 32u, 36u, 43u, 44u, 48u, 52u, 56u, 59u, 64u}) {
        auto bad = info; bad[offset] = 0;
        if (offset == 43u) bad[offset] = 1; // layered image set
        if (MajestyRuntimeFeatures::ParseRegistry(bad.data(), bad.size(), &registry, &error)) {
            std::fprintf(stderr, "Accepted bad hero row at %u\n", offset); return 42;
        }
    }
    // v7 also supports research without an effect; v6 deliberately doesn't.
    auto mixed = noVisual;
    mixed[4] = 7; mixed[16] = 48;
    mixed.insert(mixed.end(), info.begin()+20, info.end());
    if (!MajestyRuntimeFeatures::ParseRegistry(mixed.data(), mixed.size(), &registry, &error) ||
        registry.kingdomResearch.size() != 1 || registry.heroInfoRows.size() != 1) return 43;
    std::puts("Runtime feature registry parser tests passed.");
    return 0;
}
