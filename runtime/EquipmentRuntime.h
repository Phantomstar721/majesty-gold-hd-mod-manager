#pragma once
#include <cstdint>
#include "RuntimeFeatureRegistry.h"

// No hooks or state are installed for an empty registry. The only supported
// profile is beta2; verify all native boundaries before replacing either call.
bool InstallEquipmentRuntime(std::uintptr_t imageBase, bool beta2,
    const MajestyRuntimeFeatures::Registry& registry,
    void (*fatal)(const char*));
