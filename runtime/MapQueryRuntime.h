#pragma once
#include <cstdint>
// Installs one stock GPL-registration completion adapter. No hook at all is
// installed unless the composed MMFR/MMCP explicitly selects this feature.
bool InstallMapQueryRuntime(std::uintptr_t imageBase, bool publicBuild);
