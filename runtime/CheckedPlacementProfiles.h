#pragma once
#include "CheckedRelocationProfiles.h"

namespace MajestyCheckedPlacement {
struct PlacementStateProfile {
    std::uint32_t unit, vehicle, building, linearMovement;
    std::uint32_t retirement, footprint, attribute;
    bool Supports(std::uint32_t table) const {
        return table==unit || table==vehicle || table==building;
    }
};
inline const PlacementStateProfile* PlacementStateFor(MajestyBuildId build) {
    // Concrete RTTI-backed tables and their +30/+C0/+124 method slots.
    static constexpr PlacementStateProfile publicBuild{0x73A924,0x73B08C,0x73A004,0x74A240,0x4474F0,0x441FE0,0x448A40};
    static constexpr PlacementStateProfile betaBuild{0x7539E4,0x75414C,0x7530C4,0x764310,0x448400,0x442EF0,0x449950};
    static constexpr PlacementStateProfile gogBuild{0x752A2C,0x753194,0x75210C,0x7631D0,0x448320,0x442E10,0x449870};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
// Query-only profile. These entries do not establish cast/identity readiness.
struct PlacementQueryProfile {
    std::uintptr_t path, fit, seed;
    std::uint32_t pathHash, fitHash, seedHash;
};
inline const PlacementQueryProfile* PlacementQueriesFor(MajestyBuildId build) {
    static constexpr PlacementQueryProfile publicBuild{0x5C5350,0x5CCA50,0x5C53A0,0x3DBBA409,0x938887BE,0x1D4D3806};
    static constexpr PlacementQueryProfile betaBuild{0x5DA530,0x5E1C30,0x5DA580,0x99754926,0x1509B5DD,0x5DEBEB32};
    static constexpr PlacementQueryProfile gogBuild{0x5D9880,0x5E0F80,0x5D98D0,0x016DA326,0x02FE9421,0x0EE8ED32};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
inline bool PlacementQueryBytesMatch(const PlacementQueryProfile& p,
                                     const unsigned char* path,
                                     const unsigned char* fit,
                                     const unsigned char* seed) {
    return RelocationFingerprint(path,0x45)==p.pathHash &&
           RelocationFingerprint(fit,0x9F)==p.fitHash &&
           RelocationFingerprint(seed,0xBC)==p.seedHash;
}
}
