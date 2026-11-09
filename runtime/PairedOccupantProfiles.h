#pragma once
#include <cstdint>
#include "MajestyBuildId.h"
namespace MajestyPairedOccupantAction {
struct Profile { std::uintptr_t appendCall, executeCall, append, execute; };
struct Window { std::uintptr_t rva; unsigned size; std::uint32_t hash; };
constexpr Profile Profiles[] = {
    {0xC5625u, 0xC562Eu, 0x162C40u, 0x1637C0u}, // Public
    {0xC6065u, 0xC606Eu, 0x178D70u, 0x1798F0u}, // Beta2
    {0xC6665u, 0xC666Eu, 0x178070u, 0x178BF0u}, // Gog
};
constexpr Window Windows[][8] = {
    {
        {0xC56BCu, 92u, 0xA1F8CFBEu},
        {0xC4DA0u, 77u, 0xE7FBAA8Du},
        {0xC5583u, 181u, 0x481DF7F5u},
        {0xC4FB7u, 42u, 0xEDC7BF23u},
        {0xC56A5u, 22u, 0xCD00A2B7u},
        {0x1A15F0u, 64u, 0x438A4466u},
        {0xDA054u, 8u, 0xF79C904Du},
        {0xDA093u, 5u, 0x67D914D4u},
    }, // Public
    {
        {0xC60FCu, 92u, 0x365388EBu},
        {0xC57E0u, 77u, 0x5FA1CF2Au},
        {0xC5FC3u, 181u, 0x5FD750AAu},
        {0xC59F7u, 42u, 0x8605FE3Au},
        {0xC60E5u, 22u, 0xCD00A2B7u},
        {0x1B65A0u, 64u, 0x438A4466u},
        {0xDA664u, 8u, 0xD576BF7Cu},
        {0xDA6A3u, 5u, 0x100A2894u},
    }, // Beta2
    {
        {0xC66FCu, 92u, 0x951914D9u},
        {0xC5DE0u, 77u, 0x44ED5EE7u},
        {0xC65C3u, 181u, 0x404A9985u},
        {0xC5FF7u, 42u, 0x01F9C2D1u},
        {0xC66E5u, 22u, 0xCD00A2B7u},
        {0x1B58F0u, 64u, 0x438A4466u},
        {0xDADA4u, 8u, 0x7A3EE1F5u},
        {0xDADE3u, 5u, 0x26218BF7u},
    }, // Gog
};
inline unsigned ProfileIndex(MajestyBuildId build) {
    switch(build) {
    case MajestyBuildId::SteamPublic: return 0;
    case MajestyBuildId::SteamBeta2: return 1;
    case MajestyBuildId::Gog: return 2;
    default: return 3;
    }
}
template<class ReadWindow>
bool ValidateProfile(MajestyBuildId build, std::uintptr_t imageBase, ReadWindow read) {
    const auto index = ProfileIndex(build);
    // Pinned windows contain absolute addresses. Reject relocation rather than
    // treating fixed-image evidence as an ASLR-adjusted proof.
    if (index >= 3 || imageBase != 0x400000u) return false;
    for (const auto& window : Windows[index]) {
        const unsigned char* bytes = read(window.rva, window.size);
        if (!bytes) return false;
        std::uint32_t hash = 2166136261u;
        for (unsigned i = 0; i < window.size; ++i)
            hash = (hash ^ bytes[i]) * 16777619u;
        if (hash != window.hash) return false;
    }
    return true;
}
} // namespace MajestyPairedOccupantAction
