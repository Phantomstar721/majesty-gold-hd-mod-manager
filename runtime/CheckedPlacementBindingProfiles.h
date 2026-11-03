#pragma once
#include "CheckedPlacementProfiles.h"

namespace MajestyCheckedPlacement {
// Complete bounded helper bodies, not permission to enable an unfinished chain.
struct PlacementBindingProfile {
    std::uint32_t root, stringCreate, stringDestroy, functionLookup;
    std::uint32_t unitDead, buildingDead, attributeValue, proxy;
    std::uint32_t hashes[8];
};
inline const PlacementBindingProfile* PlacementBindingsFor(MajestyBuildId build) {
    static constexpr PlacementBindingProfile publicBuild{
        0x55EEF0,0x627A80,0x627C30,0x56BC00,0x43A940,0x43C100,0x5B9FD0,0x5586F0,
        {0x84C3CC3D,0xB54450FF,0x8BCE86A9,0x8F0AF352,0x485B1A75,0x51B63A4D,0x6C32FBAD,0x2ED63628}};
    static constexpr PlacementBindingProfile betaBuild{
        0x575030,0x63A220,0x63A3D0,0x581C10,0x43B850,0x43D010,0x5CEF70,0x56E830,
        {0xA5E6C345,0x5A295AC3,0x333BAFA2,0x730D5630,0x485B1A75,0x502B243E,0x95C4D700,0x2ED63628}};
    static constexpr PlacementBindingProfile gogBuild{
        0x574330,0x63C370,0x63C520,0x580F10,0x43B770,0x43CF30,0x5CE2C0,0x56DB30,
        {0xA5E6C345,0x22529BDF,0x788DA9A2,0xF30284AC,0x485B1A75,0x36F0746D,0x0CDE635B,0x2ED63628}};
    switch(build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
inline bool PlacementBindingBytesMatch(const PlacementBindingProfile& p) {
    const std::uint32_t addresses[]={p.root,p.stringCreate,p.stringDestroy,p.functionLookup,
        p.unitDead,p.buildingDead,p.attributeValue,p.proxy};
    const unsigned sizes[]={9,0x45,0x21,0x66,10,0x24,0x21,0x24};
    for(unsigned i=0;i<8;++i)
        if(RelocationFingerprint(reinterpret_cast<const unsigned char*>(addresses[i]),sizes[i])!=p.hashes[i])return false;
    return true;
}
}
