#pragma once
#include <cstdint>
#include "MajestyBuildId.h"
#include "ObserverBodyProfiles.h"
namespace MajestyBooleanRuntime {
enum class Decision { Unavailable, Allow, Absorb, InvalidResult };
// Startup only. String helpers come from the existing guarded occupant profile.
bool Prepare(MajestyBuildId, std::uintptr_t stringConstructor, std::uintptr_t stringDestructor);
bool GuardBodies(const MajestyAttackObservation::ObserverBody*, unsigned count);
bool BindOwnerThread(); // existing stock registration edge, not loader thread
// Internal to the attested impact service: caller owns declaration/content and
// source/target lifetime admission. InvalidResult is never a false decision.
Decision Invoke(const char* symbol, void* source, void* target);
}
