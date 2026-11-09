#pragma once
#include <cstdint>
#include "MajestyBuildId.h"
namespace MajestyAttackObservation {
using RegisterProcedure = void (*)(const char*,void (__cdecl*)(void*));
// Read the Manager-generated sibling proof; never accept package offsets/code.
bool PrepareRuntime(const wchar_t* capabilityManifest,MajestyBuildId,bool interception=false);
// Called exclusively by MapQueryRuntime's existing post-stock registration edge.
bool InstallRuntime(std::uintptr_t imageBase, RegisterProcedure, void (*log)(const char*));
}
