#include "MajestyBuildId.h"
#pragma once
#include <cstdint>
namespace MajestyRuntimeFeatures { struct Registry; }
// Installs one stock GPL-registration completion adapter. No hook at all is
// installed unless MMFR/MMCP selects map, movement, or native timing services.
// Movement/timing-only use does not patch PathCost or access map tiles.
bool InstallMapQueryRuntime(std::uintptr_t imageBase, MajestyBuildId buildId,
                           bool mapQuery = true, bool movementQuery = false,
                           const MajestyRuntimeFeatures::Registry* timing = nullptr);
