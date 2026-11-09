#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

namespace MajestyAttackObservation {
// Native dependency addresses, separate from admission and loaded-content
// proof. A profile entry alone never enables this development provider.
struct ObservationNativeProfile {
    std::uint32_t findName, callbacks, actionCatalog, unitCatalog;
    std::uint32_t releaseCallback, impactCallback, pendingCallback;
    std::uint32_t missileTable, animationTable, retirement;
    std::uint32_t worldCatalog, argumentAt, resolveAgent;
    std::uint32_t runtimeGlobal, allUnitsTable, impactGlobal, impactFunction, findUnit;
};
inline const ObservationNativeProfile* ObservationNativeFor(MajestyBuildId build) {
    static const ObservationNativeProfile publicBuild{
        0x5AE060,0x5F3090,0x7C545C,0x7C5304,
        0x5F6D40,0x5F9180,0x5FB9B0,0x740514,0x7495B0,0x4474F0,
        0x5A15D0,0x42DDF0,0x558B20,0x7C544C,0x748D4C,0x7B967C,0x4DC940,0x5A15F0};
    static const ObservationNativeProfile betaBuild{
        0x5C3000,0x6083D0,0x7E3FE4,0x7E3E8C,
        0x60C080,0x60E4C0,0x610CF0,0x759214,0x763680,0x448400,
        0x5B6580,0x42ED50,0x56EC60,0x7E3FD4,0x762E1C,0x7D812C,0x4DCF50,0x5B65A0};
    static const ObservationNativeProfile gogBuild{
        0x5C2350,0x607720,0x7E427C,0x7E4124,
        0x60B3D0,0x60D810,0x610040,0x7583CC,0x762540,0x448320,
        0x5B58D0,0x42EC20,0x56DF60,0x7E426C,0x761CDC,0x7D83CC,0x4DD690,0x5B58F0};
    switch (build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
}
