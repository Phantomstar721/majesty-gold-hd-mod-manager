#pragma once
#include <cstdint>
#include "RuntimeFeatureRegistry.h"
#include "MajestyBuildId.h"

// No hooks or state are installed for an empty registry. Verify the selected
// executable's native boundaries before replacing either stock call.
bool InstallEquipmentRuntime(std::uintptr_t imageBase, MajestyBuildId build,
    const MajestyRuntimeFeatures::Registry& registry,
    void (*fatal)(const char*));
