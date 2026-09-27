#pragma once
#include "MajestyBuildId.h"
#include <cstdint>

namespace MajestySpellOrigin {
struct Profile {
    std::uintptr_t create, argument, unit, birth;
    std::uint32_t hash;
};
constexpr Profile kPublic{0x30A20,0x2DDF0,0x158B20,0x1C5B20,0xF7B85B33};
constexpr Profile kBeta2{0x31980,0x2ED50,0x16EC60,0x1DAD00,0xFF20764A};
constexpr Profile kGog{0x31850,0x2EC20,0x16DF60,0x1DA050,0x724455C9};
inline const Profile* For(MajestyBuildId build) {
    switch(build) {
    case MajestyBuildId::SteamPublic: return &kPublic;
    case MajestyBuildId::SteamBeta2: return &kBeta2;
    case MajestyBuildId::Gog: return &kGog;
    default: return nullptr;
    }
}
}
