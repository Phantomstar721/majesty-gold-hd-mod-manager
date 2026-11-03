#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

namespace MajestyCheckedPlacement {
// Independently matched full stock bodies. This covers only relocation, not
// permission to install the dependent cast/identity observation service.
struct RelocationProfile {
    std::uintptr_t convert, write;
    std::uint32_t convertHash;
};
inline const RelocationProfile* RelocationFor(MajestyBuildId build) {
    static constexpr RelocationProfile publicBuild{0x5C2340,0x5C2280,0xC9DF12EC};
    static constexpr RelocationProfile betaBuild{0x5D7520,0x5D7460,0x393069FA};
    static constexpr RelocationProfile gogBuild{0x5D6870,0x5D67B0,0x64ACE6C4};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
inline std::uint32_t RelocationFingerprint(const unsigned char* bytes,unsigned size) {
    std::uint32_t value=2166136261u;
    for(unsigned i=0;i<size;++i)value=(value^bytes[i])*16777619u;
    return value;
}
inline bool RelocationBytesMatch(const RelocationProfile& profile,
                                const unsigned char* conversion,const unsigned char* write) {
    return RelocationFingerprint(conversion,0x59)==profile.convertHash &&
           RelocationFingerprint(write,0xB4)==0xDA557991;
}
}
