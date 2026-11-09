#pragma once
#include "CheckedPlacementProfiles.h"
#include "CheckedPlacement.h"

namespace MajestyCheckedPlacement {
// State-aware GS refresh plus its direct imagery helpers and stock event1
// cancellation. Full bodies are guarded; these entries do not enable a feature.
struct CosmeticActionProfile {
    Word refresh, selectNormal, animate, selectInjured, cancelOrder;
    Word hashes[5];
};
struct CosmeticImageTypes { Word collection,part,standardEngine,animation; };
inline const CosmeticImageTypes* CosmeticImagesFor(MajestyBuildId build) {
    static constexpr CosmeticImageTypes publicBuild{0x74A5C4,0x74A564,0x74754C,0x7495B0};
    static constexpr CosmeticImageTypes betaBuild{0x764694,0x764634,0x7614AC,0x763680};
    static constexpr CosmeticImageTypes gogBuild{0x763554,0x7634F4,0x76036C,0x762540};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
inline const CosmeticActionProfile* CosmeticActionsFor(MajestyBuildId build) {
    static constexpr CosmeticActionProfile publicBuild{
        0x447D80,0x447B50,0x5BC540,0x447CA0,0x5FCE40,
        {0xD7033B52,0x9134D759,0xBA8B77DA,0xE9524D59,0x0A8F3E5A}};
    static constexpr CosmeticActionProfile betaBuild{
        0x448C90,0x448A60,0x5D14F0,0x448BB0,0x612180,
        {0xEAC66B9A,0x44C282B3,0xBA8B77DA,0xB3278E34,0x0A8F3E5A}};
    static constexpr CosmeticActionProfile gogBuild{
        0x448BB0,0x448980,0x5D0840,0x448AD0,0x6114D0,
        {0x6D9330A1,0x050EC1EF,0xBA8B77DA,0xBAFF16F9,0x0A8F3E5A}};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
inline bool CosmeticActionBytesMatch(const CosmeticActionProfile& p) {
    const Word addresses[]={p.refresh,p.selectNormal,p.animate,p.selectInjured,p.cancelOrder};
    const unsigned sizes[]={0x1BF,0x4A,0x94,0xD1,0x44};
    for(unsigned i=0;i<5;++i)
        if(RelocationFingerprint(reinterpret_cast<const unsigned char*>(addresses[i]),sizes[i])!=p.hashes[i])return false;
    return true;
}
}
