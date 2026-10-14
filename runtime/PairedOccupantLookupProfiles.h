#pragma once
#include "PairedOccupantProfiles.h"
namespace MajestyPairedOccupantAction {
struct LookupProfile { std::uintptr_t categoryGetter, serviceVtable; };
constexpr LookupProfile LookupProfiles[] = {
    {0x1A15D0u, 0x348D4Cu},
    {0x1B6580u, 0x362E1Cu},
    {0x1B58D0u, 0x361CDCu},
};
// Exact-image stock AllUnitsList primary tables share the already guarded
// GE_AllUnitsList virtual28 thunk, without a receiver adjustment.
constexpr std::uintptr_t AllUnitsTables[] = {0x33A4FCu, 0x3535BCu, 0x352604u};
inline bool AdmittedService(unsigned index, std::uintptr_t table, std::uintptr_t base) {
    return index < 3 && (table == base + LookupProfiles[index].serviceVtable ||
                         table == base + AllUnitsTables[index]);
}
constexpr Window LookupWindows[][11] = {
    {
        {0x1A15D0u, 30u, 0xF97BC27Eu},
        {0x1A4080u, 106u, 0x64943074u},
        {0x1A3FD0u, 176u, 0x60C3FBCDu},
        {0x1A15F0u, 64u, 0x438A4466u},
        {0x1CE3E0u, 5u, 0xFC840986u},
        {0x1A3FB0u, 32u, 0x4E447FB4u},
        {0x1A3B70u, 109u, 0x36ED83D9u},
        {0x1A3790u, 139u, 0xBD8A528Eu},
        {0x3B9284u, 22u, 0x05A48908u},
        {0x35D368u, 20u, 0x1C1AEFD0u},
        {0x348D74u, 4u, 0x7AAE2848u},
    },
    {
        {0x1B6580u, 30u, 0xF97BC27Eu},
        {0x1B9030u, 106u, 0xF0AD98AAu},
        {0x1B8F80u, 176u, 0xC9C10B19u},
        {0x1B65A0u, 64u, 0x438A4466u},
        {0x1E35C0u, 5u, 0xED256744u},
        {0x1B8F60u, 32u, 0x4E447FB4u},
        {0x1B8B20u, 109u, 0x9C79A4EBu},
        {0x1B8740u, 139u, 0x41CFD074u},
        {0x3D7D34u, 22u, 0x05A48908u},
        {0x378350u, 20u, 0xFB202B41u},
        {0x362E44u, 4u, 0xE9676A00u},
    },
    {
        {0x1B58D0u, 30u, 0xF97BC27Eu},
        {0x1B8380u, 106u, 0xFF18E74Eu},
        {0x1B82D0u, 176u, 0xF4326431u},
        {0x1B58F0u, 64u, 0x438A4466u},
        {0x1E2910u, 5u, 0xED256744u},
        {0x1B82B0u, 32u, 0x4E447FB4u},
        {0x1B7E70u, 109u, 0xD9B38027u},
        {0x1B7A90u, 139u, 0x2BED4858u},
        {0x3D7FD8u, 22u, 0x05A48908u},
        {0x377504u, 20u, 0x8E3B2809u},
        {0x361D04u, 4u, 0x91A3BDACu},
    },
};
} // namespace MajestyPairedOccupantAction
