#pragma once
#include "CheckedRelocationProfiles.h"
namespace MajestyCheckedPlacement {
struct PendingCastProfile { std::uint32_t process,table,hash; };
inline const PendingCastProfile* PendingCastFor(MajestyBuildId build) {
    // Complete 380-byte OrderTurn Process, independently matched in
    // research pending-action-handoff-20261010.json. No beta offset reuse.
    static constexpr PendingCastProfile pub{0x5FB440,0x749A0C,0x5EC569A0};
    static constexpr PendingCastProfile beta{0x610780,0x763ADC,0xA262FF7D};
    static constexpr PendingCastProfile gog{0x60FAD0,0x76299C,0x654266E4};
    switch(build){case MajestyBuildId::SteamPublic:return &pub;
    case MajestyBuildId::SteamBeta2:return &beta;case MajestyBuildId::Gog:return &gog;}
    return nullptr;
}
}
