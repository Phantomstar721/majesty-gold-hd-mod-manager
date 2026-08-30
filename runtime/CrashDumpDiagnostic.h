#pragma once

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>

// Installs a logging-only vectored exception observer for the diagnosed GPL
// evaluator fault. The observer writes a full-memory minidump, then returns
// EXCEPTION_CONTINUE_SEARCH so Majesty's ordinary crash lifecycle is unchanged.
bool InstallCrashDumpDiagnostic(
    HMODULE runtimeModule,
    std::uintptr_t majestyImageBase,
    const char* buildProfileId);
