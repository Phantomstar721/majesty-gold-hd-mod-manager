#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

constexpr wchar_t kCapabilityManifestEnvironment[] =
    L"MAJESTY_MOD_MANAGER_CAPABILITIES";
constexpr wchar_t kRuntimeReadyEventEnvironment[] =
    L"MAJESTY_BUILDING_RUNTIME_READY_EVENT";
constexpr wchar_t kProfileLockHandleEnvironment[] =
    L"MAJESTY_MOD_MANAGER_PROFILE_LOCK_HANDLE";

std::wstring ParentDirectory(const std::wstring& path) {
    const std::size_t separator = path.find_last_of(L"\\/");
    return separator == std::wstring::npos ? L"." : path.substr(0, separator);
}

bool FileExists(const std::wstring& path) {
    const DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

bool EnvironmentVariableExists(const wchar_t* name) {
    SetLastError(ERROR_SUCCESS);
    const DWORD length = GetEnvironmentVariableW(name, nullptr, 0);
    return length != 0 || GetLastError() != ERROR_ENVVAR_NOT_FOUND;
}

bool ReadInheritedProfileLock(HANDLE* lockHandle) {
    if (lockHandle == nullptr) {
        return false;
    }
    *lockHandle = nullptr;
    wchar_t value[32] = {};
    SetLastError(ERROR_SUCCESS);
    const DWORD length = GetEnvironmentVariableW(
        kProfileLockHandleEnvironment,
        value,
        static_cast<DWORD>(sizeof(value) / sizeof(value[0])));
    if (length == 0 || length >= sizeof(value) / sizeof(value[0])) {
        return false;
    }
    for (DWORD index = 0; index < length; ++index) {
        if (value[index] < L'0' || value[index] > L'9') {
            return false;
        }
    }
    errno = 0;
    wchar_t* end = nullptr;
    const unsigned long long encoded = _wcstoui64(value, &end, 10);
    if (errno == ERANGE || end != value + length || encoded == 0 ||
        encoded > static_cast<unsigned long long>(~static_cast<ULONG_PTR>(0))) {
        return false;
    }
    const HANDLE candidate = reinterpret_cast<HANDLE>(
        static_cast<ULONG_PTR>(encoded));
    DWORD flags = 0;
    SetLastError(ERROR_SUCCESS);
    if (!GetHandleInformation(candidate, &flags) ||
        GetFileType(candidate) != FILE_TYPE_DISK) {
        return false;
    }
    *lockHandle = candidate;
    return true;
}

void CloseProfileLock(HANDLE* lockHandle) {
    if (lockHandle != nullptr && *lockHandle != nullptr) {
        CloseHandle(*lockHandle);
        *lockHandle = nullptr;
    }
}

std::wstring QuoteCommandLineArgument(const std::wstring& argument) {
    if (argument.empty()) {
        return L"\"\"";
    }
    if (argument.find_first_of(L" \t\n\v\"") == std::wstring::npos) {
        return argument;
    }

    std::wstring quoted = L"\"";
    std::size_t backslashes = 0;
    for (const wchar_t character : argument) {
        if (character == L'\\') {
            ++backslashes;
            continue;
        }
        if (character == L'\"') {
            quoted.append(backslashes * 2 + 1, L'\\');
            quoted.push_back(character);
            backslashes = 0;
            continue;
        }
        quoted.append(backslashes, L'\\');
        backslashes = 0;
        quoted.push_back(character);
    }
    quoted.append(backslashes * 2, L'\\');
    quoted.push_back(L'\"');
    return quoted;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc < 3) {
        std::fwprintf(
            stderr,
            L"Usage: MajestyBuildingRuntimeLauncher.exe <MajestyHD.exe> <runtime.dll> [game arguments...]\n");
        return 2;
    }
    const std::wstring executable = argv[1];
    const std::wstring runtime = argv[2];
    if (!FileExists(executable) || !FileExists(runtime)) {
        std::fwprintf(stderr, L"Majesty executable or runtime DLL was not found.\n");
        return 3;
    }

    std::wstring commandLine = QuoteCommandLineArgument(executable);
    for (int index = 3; index < argc; ++index) {
        commandLine += L" ";
        commandLine += QuoteCommandLineArgument(argv[index]);
    }
    std::vector<wchar_t> mutableCommand(commandLine.begin(), commandLine.end());
    mutableCommand.push_back(L'\0');

    STARTUPINFOW startup = {};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {};
    const std::wstring workingDirectory = ParentDirectory(executable);
    // MMCP presence is the authoritative Mod Manager launch marker. The
    // launcher therefore holds Majesty suspended until the DLL has validated
    // the complete manifest and installed only its declared hook groups.
    const bool managerLaunch =
        EnvironmentVariableExists(kCapabilityManifestEnvironment);
    const bool profileLockDeclared =
        EnvironmentVariableExists(kProfileLockHandleEnvironment);
    HANDLE profileLock = nullptr;
    if (profileLockDeclared &&
        (!managerLaunch || !ReadInheritedProfileLock(&profileLock))) {
        std::fwprintf(
            stderr,
            L"The Mod Manager generated-profile lock handle is absent or invalid.\n");
        return 4;
    }
    HANDLE runtimeReadyEvent = nullptr;
    std::wstring previousReadyEvent;
    bool hadPreviousReadyEvent = false;
    if (managerLaunch) {
        wchar_t eventName[128] = {};
        swprintf_s(
            eventName,
            L"Local\\MajestyBuildingRuntimeReady-%08lX-%08lX",
            GetCurrentProcessId(),
            GetTickCount());
        runtimeReadyEvent = CreateEventW(
            nullptr, TRUE, FALSE, eventName);
        if (runtimeReadyEvent == nullptr) {
            std::fwprintf(
                stderr,
                L"Could not create the Mod Manager runtime barrier (error %lu).\n",
                GetLastError());
            CloseProfileLock(&profileLock);
            return 4;
        }
        wchar_t previous[32768] = {};
        SetLastError(ERROR_SUCCESS);
        const DWORD previousLength = GetEnvironmentVariableW(
            kRuntimeReadyEventEnvironment,
            previous,
            static_cast<DWORD>(sizeof(previous) / sizeof(previous[0])));
        hadPreviousReadyEvent = previousLength != 0 ||
            GetLastError() != ERROR_ENVVAR_NOT_FOUND;
        if (previousLength >= sizeof(previous) / sizeof(previous[0]) ||
            (hadPreviousReadyEvent && previousLength == 0)) {
            CloseHandle(runtimeReadyEvent);
            std::fwprintf(
                stderr,
                L"The existing Mod Manager runtime barrier value is invalid.\n");
            CloseProfileLock(&profileLock);
            return 4;
        }
        if (hadPreviousReadyEvent) {
            previousReadyEvent.assign(previous, previousLength);
        }
        if (!SetEnvironmentVariableW(
                kRuntimeReadyEventEnvironment, eventName)) {
            CloseHandle(runtimeReadyEvent);
            std::fwprintf(
                stderr,
                L"Could not publish the Mod Manager runtime barrier (error %lu).\n",
                GetLastError());
            CloseProfileLock(&profileLock);
            return 4;
        }
    }
    if (!CreateProcessW(
            executable.c_str(), mutableCommand.data(), nullptr, nullptr, FALSE,
            CREATE_SUSPENDED, nullptr, workingDirectory.c_str(), &startup, &process)) {
        if (managerLaunch) {
            SetEnvironmentVariableW(
                kRuntimeReadyEventEnvironment,
                hadPreviousReadyEvent ? previousReadyEvent.c_str() : nullptr);
            CloseHandle(runtimeReadyEvent);
        }
        CloseProfileLock(&profileLock);
        std::fwprintf(stderr, L"Could not start MajestyHD.exe (error %lu).\n", GetLastError());
        return 4;
    }
    if (managerLaunch) {
        SetEnvironmentVariableW(
            kRuntimeReadyEventEnvironment,
            hadPreviousReadyEvent ? previousReadyEvent.c_str() : nullptr);
    }

    const SIZE_T bytes = (runtime.size() + 1) * sizeof(wchar_t);
    void* remotePath = VirtualAllocEx(
        process.hProcess, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remotePath == nullptr ||
        !WriteProcessMemory(process.hProcess, remotePath, runtime.c_str(), bytes, nullptr)) {
        std::fwprintf(stderr, L"Could not stage the runtime DLL path (error %lu).\n", GetLastError());
        TerminateProcess(process.hProcess, 5);
        if (runtimeReadyEvent != nullptr) {
            CloseHandle(runtimeReadyEvent);
        }
        CloseProfileLock(&profileLock);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        return 5;
    }

    const HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    const auto loadLibrary = reinterpret_cast<LPTHREAD_START_ROUTINE>(
        GetProcAddress(kernel32, "LoadLibraryW"));
    const HANDLE injection = CreateRemoteThread(
        process.hProcess, nullptr, 0, loadLibrary, remotePath, 0, nullptr);
    if (injection == nullptr) {
        std::fwprintf(stderr, L"Could not inject the runtime DLL (error %lu).\n", GetLastError());
        TerminateProcess(process.hProcess, 6);
        if (runtimeReadyEvent != nullptr) {
            CloseHandle(runtimeReadyEvent);
        }
        CloseProfileLock(&profileLock);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        return 6;
    }
    WaitForSingleObject(injection, INFINITE);
    DWORD loadResult = 0;
    GetExitCodeThread(injection, &loadResult);
    CloseHandle(injection);
    VirtualFreeEx(process.hProcess, remotePath, 0, MEM_RELEASE);
    if (loadResult == 0) {
        std::fwprintf(stderr, L"Majesty rejected the runtime DLL.\n");
        TerminateProcess(process.hProcess, 7);
        if (runtimeReadyEvent != nullptr) {
            CloseHandle(runtimeReadyEvent);
        }
        CloseProfileLock(&profileLock);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        return 7;
    }

    if (managerLaunch) {
        const HANDLE waitHandles[2] = {runtimeReadyEvent, process.hProcess};
        const DWORD waitResult = WaitForMultipleObjects(
            2, waitHandles, FALSE, 30000);
        if (waitResult != WAIT_OBJECT_0) {
            if (waitResult != WAIT_OBJECT_0 + 1) {
                TerminateProcess(process.hProcess, 8);
            }
            std::fwprintf(
                stderr,
                L"Majesty Mod Manager runtime initialization did not complete safely.\n");
            CloseHandle(runtimeReadyEvent);
            CloseProfileLock(&profileLock);
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            return 8;
        }
        CloseHandle(runtimeReadyEvent);
    }
    if (ResumeThread(process.hThread) == static_cast<DWORD>(-1)) {
        std::fwprintf(stderr, L"Could not resume MajestyHD.exe (error %lu).\n", GetLastError());
        TerminateProcess(process.hProcess, 9);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseProfileLock(&profileLock);
        return 9;
    }
    CloseHandle(process.hThread);
    if (profileLock != nullptr) {
        const DWORD waitResult = WaitForSingleObject(process.hProcess, INFINITE);
        if (waitResult != WAIT_OBJECT_0) {
            std::fwprintf(
                stderr,
                L"Could not wait for MajestyHD.exe while holding the generated-profile lock (error %lu).\n",
                GetLastError());
            CloseHandle(process.hProcess);
            CloseProfileLock(&profileLock);
            return 10;
        }
    }
    CloseHandle(process.hProcess);
    CloseProfileLock(&profileLock);
    return 0;
}
