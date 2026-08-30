#pragma once

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

// Installs the Freestyle CAM-generation repair for the already-selected
// Majesty executable profile. The function preflights every stock site before
// writing any hook and rolls back the complete group if a write fails.
bool InstallFreestyleCamRuntime(HMODULE runtimeModule, const char* profileId);
