#pragma once
#include "AttackObservationRuntime.h"
namespace MajestyCheckedPlacement {
bool PrepareRuntime(const wchar_t* capabilityManifest,MajestyBuildId);
bool RebindPreparedWorld();
void TracePlacementStage(std::uint32_t actor,unsigned reason,const char* message);
// Internal installer contract, never populated from package data or GPL.
bool RegisterBuildingAttributeReplacement(MajestyBuildId, std::uint32_t slot,
    std::uint32_t original, std::uint32_t replacement);
// If this feature was not prepared, registration remains untouched.
bool InstallPreparedRuntime(MajestyAttackObservation::RegisterProcedure);
}
