#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

namespace WindowQoL {
// Pre-window installation only. Does not change the executable on disk or prefs.
bool Install(std::uintptr_t base, MajestyBuildId build, bool borderless,
             bool confinement, void (*log)(const char*));
}
