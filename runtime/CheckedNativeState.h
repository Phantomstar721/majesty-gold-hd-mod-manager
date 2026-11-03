#pragma once
#include "CheckedPlacement.h"
#include "AttackObservation.h"
#include "CheckedPlacementProfiles.h"
namespace MajestyCheckedPlacement {
// Internal effective-state reader. Its services are supplied only by the
// exact-image adapter, never by GPL arguments or a package's claimed address.
struct StateServices {
    const MajestyAttackObservation::Memory* memory{};
    Word actorDescriptor{};
    bool (*currentIdentity)(Word unit,Word id,Word world,Word description){};
    int (*hitPoints)(Word unit){};
    std::uint64_t (*epoch)(Word unit,Word id){};
    std::uint64_t (*revision)(){};
    const PlacementStateProfile* profile{};
    Word buildingAttributeReplacement{};
};
bool ReadIdentity(const StateServices&,Word unit,Identity&,const char** failure=nullptr);
bool ReadSupportedMover(const StateServices&,Word actor,Identity&,const char** failure=nullptr);
bool ReadPlacement(const StateServices&,Word actor,Word target,Snapshot&);
}
