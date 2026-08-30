#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>

#include <cstdint>
#include <cstring>
#include <cwchar>

#include "CrashDumpDiagnostic.h"

namespace {

constexpr std::uintptr_t kBeta2GplValueFaultRva = 0x0019AA36;

HMODULE g_runtimeModule = nullptr;
std::uintptr_t g_expectedFaultAddress = 0;
LONG g_dumpStarted = 0;

void BuildSiblingPath(
    const wchar_t* filename,
    wchar_t (&output)[MAX_PATH]) {
    output[0] = L'\0';
    GetModuleFileNameW(g_runtimeModule, output, MAX_PATH);
    wchar_t* separator = std::wcsrchr(output, L'\\');
    if (separator != nullptr) {
        separator[1] = L'\0';
    } else {
        output[0] = L'\0';
    }
    wcsncat_s(output, filename, _TRUNCATE);
}

void AppendDiagnosticLog(const wchar_t* message) {
    wchar_t path[MAX_PATH] = {};
    BuildSiblingPath(L"MajestyCrashDiagnostic.log", path);
    HANDLE file = CreateFileW(
        path,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD bytesWritten = 0;
    WriteFile(
        file,
        message,
        static_cast<DWORD>(std::wcslen(message) * sizeof(wchar_t)),
        &bytesWritten,
        nullptr);
    CloseHandle(file);
}

LONG CALLBACK CaptureDiagnosedGplFault(PEXCEPTION_POINTERS exceptionPointers) {
    if (exceptionPointers == nullptr ||
        exceptionPointers->ExceptionRecord == nullptr ||
        exceptionPointers->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION ||
        reinterpret_cast<std::uintptr_t>(
            exceptionPointers->ExceptionRecord->ExceptionAddress) !=
            g_expectedFaultAddress) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    if (InterlockedCompareExchange(&g_dumpStarted, 1, 0) != 0) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    SYSTEMTIME localTime = {};
    GetLocalTime(&localTime);
    wchar_t filename[96] = {};
    swprintf_s(
        filename,
        L"MajestyFullCrash-%04u%02u%02u-%02u%02u%02u.dmp",
        localTime.wYear,
        localTime.wMonth,
        localTime.wDay,
        localTime.wHour,
        localTime.wMinute,
        localTime.wSecond);
    wchar_t path[MAX_PATH] = {};
    BuildSiblingPath(filename, path);

    HANDLE dumpFile = CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ,
        nullptr,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (dumpFile == INVALID_HANDLE_VALUE) {
        AppendDiagnosticLog(L"Full-memory dump creation failed while opening the output file.\r\n");
        return EXCEPTION_CONTINUE_SEARCH;
    }

    MINIDUMP_EXCEPTION_INFORMATION exceptionInfo = {};
    exceptionInfo.ThreadId = GetCurrentThreadId();
    exceptionInfo.ExceptionPointers = exceptionPointers;
    exceptionInfo.ClientPointers = FALSE;
    const MINIDUMP_TYPE dumpType = static_cast<MINIDUMP_TYPE>(
        MiniDumpWithFullMemory |
        MiniDumpWithHandleData |
        MiniDumpWithUnloadedModules |
        MiniDumpWithFullMemoryInfo |
        MiniDumpWithThreadInfo);
    const BOOL wroteDump = MiniDumpWriteDump(
        GetCurrentProcess(),
        GetCurrentProcessId(),
        dumpFile,
        dumpType,
        &exceptionInfo,
        nullptr,
        nullptr);
    CloseHandle(dumpFile);

    if (wroteDump) {
        AppendDiagnosticLog(L"Captured the diagnosed GPL evaluator fault in a full-memory dump.\r\n");
    } else {
        DeleteFileW(path);
        AppendDiagnosticLog(L"MiniDumpWriteDump failed for the diagnosed GPL evaluator fault.\r\n");
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

}  // namespace

bool InstallCrashDumpDiagnostic(
    HMODULE runtimeModule,
    std::uintptr_t majestyImageBase,
    const char* buildProfileId) {
    if (runtimeModule == nullptr || majestyImageBase == 0 ||
        buildProfileId == nullptr ||
        std::strcmp(buildProfileId, "beta2-1.5.2.28") != 0) {
        return false;
    }
    g_runtimeModule = runtimeModule;
    g_expectedFaultAddress = majestyImageBase + kBeta2GplValueFaultRva;
    const PVOID observer = AddVectoredExceptionHandler(1, CaptureDiagnosedGplFault);
    if (observer == nullptr) {
        return false;
    }
    AppendDiagnosticLog(L"Installed full-memory capture for MajestyHD.exe+0x0019AA36.\r\n");
    return true;
}
