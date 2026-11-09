#pragma once
#include <cstdint>

namespace MajestyResearchCompletion {
// Stock AP99's six Blacksmith descriptors. The names and FourCC registration
// are independently checked in test_research_descriptor_profiles.py.
inline std::uint32_t EquipmentAttribute(std::uint32_t command) {
    return command >= 0x1388 && command <= 0x138D
        ? 0x18425041u + ((command - 0x1388) << 24) : 0;
}
inline bool MatchesStockTemplate(std::uint32_t command, std::uint32_t attribute) {
    const auto expected = command == 5010 ? 0x1E425041u
        : command == 5020 ? 0x2A425041u
        : command == 5021 ? 0x2B425041u : EquipmentAttribute(command);
    return attribute != 0 && (!expected || attribute == expected);
}
}
