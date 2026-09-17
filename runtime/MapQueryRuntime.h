#pragma once
#include <cstdint>
// Installs one stock GPL-registration completion adapter. No hook at all is
// installed unless MMFR/MMCP selects map or movement queries. Movement-only
// use does not install the optional PathCost guard or access map tiles.
bool InstallMapQueryRuntime(std::uintptr_t imageBase, bool publicBuild,
                           bool mapQuery = true, bool movementQuery = false);
