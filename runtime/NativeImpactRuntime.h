#pragma once
#include <cstdint>
#include "MajestyBuildId.h"
namespace MajestyAttackObservation {
using RegisterProcedure = void (*)(const char*,void (__cdecl*)(void*));
// Release-only shared projectile service: no hero observation GPL exports.
bool PrepareRuntime(const wchar_t*,MajestyBuildId,bool interception=true);
bool InstallRuntime(std::uintptr_t,RegisterProcedure,void (*log)(const char*));
}
