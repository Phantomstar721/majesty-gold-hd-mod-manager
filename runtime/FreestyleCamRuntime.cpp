#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "FreestyleCamRuntime.h"

// This implementation is derived from Iximi-Ixus/freestyle-cam-sidecar's
// MIT-licensed `reacquire-no-wrapuse` checkpoint. It keeps the proven stock
// IMAG acquire shape, adds explicit public/beta2 profiles, requires every hook
// site up front, and installs the hook group atomically. See the bundled
// third-party license and docs/freestyle-cam-runtime.md.

namespace {

struct FreestyleCamProfile {
    const char* id;
    std::uintptr_t handleUseRva;
    std::uintptr_t handleUse2Rva;
    std::uintptr_t handleFrameRva;
    std::uintptr_t handleGridRva;
    std::uintptr_t handlePrescanRva;
    std::uintptr_t cacheGetterRva;
    std::uintptr_t destructorSlot28Rva;
    std::uintptr_t wrapperAssignRva;
    std::uintptr_t namedWrapperCopyCallerRva;
    std::uintptr_t releasePointerRva;
    std::uintptr_t releaseVtable8Rvas[2];
    std::uintptr_t managerLoadRva;
    std::uintptr_t managerSingletonRva;
    unsigned char expectedManagerLoad[7];
};

constexpr FreestyleCamProfile kPublicFreestyleProfile = {
    "public-1.5.2.24",
    0x00271FD0,
    0x00272030,
    0x002728C0,
    0x00272450,
    0x0027258C,
    0x0025C810,
    0x0026F1E1,
    0x0026C740,
    0x002D23DA,
    0x00246950,
    {0x002BDF0A, 0x002BDF2A},
    0x00226AC1,
    0x003C8818,
    {0xA1, 0x18, 0x88, 0x7C, 0x00, 0x85, 0xC0},
};

constexpr FreestyleCamProfile kBeta2FreestyleProfile = {
    "beta2-1.5.2.28",
    0x00287430,
    0x00287490,
    0x00287D20,
    0x002878B0,
    0x002879EC,
    0x00271C70,
    0x00284641,
    0x00281BA0,
    0x002D23DA,
    0x0025BDB0,
    {0x002D349A, 0x002D34BA},
    0x00246641,
    0x003E7518,
    {0xA1, 0x18, 0x75, 0x7E, 0x00, 0x85, 0xC0},
};

constexpr FreestyleCamProfile kGogFreestyleProfile = {
    "gog-1.5.2.28",
    0x00286920, 0x00286980, 0x00287210, 0x00286DA0, 0x00286EDC,
    0x00271160, 0x00283B31, 0x00281090,
    0, // named-retention diagnostic is not audited for GOG
    0x0025B2A0, {0x002D298A, 0x002D29AA},
    0x0023B3B1, 0x003E7638,
    {0xA1, 0x38, 0x76, 0x7E, 0x00, 0x85, 0xC0},
};

constexpr unsigned char kExpectedHandleUse[] = {
    0x8B, 0xC1, 0x8B, 0x48, 0x2C, 0x85, 0xC9, 0x74, 0x44};
constexpr unsigned char kExpectedHandleUse2[] = {
    0x53, 0x56, 0x8B, 0x71, 0x2C, 0x32, 0xDB, 0x85, 0xF6, 0x74, 0x7B};
constexpr unsigned char kExpectedHandleFrame[] = {
    0x53, 0x56, 0x8B, 0xF1, 0xBB, 0x01, 0x00, 0x00, 0x00, 0x84, 0x5E, 0x68};
constexpr unsigned char kExpectedHandleGrid[] = {
    0x83, 0xEC, 0x4C, 0x53, 0x55, 0x56, 0x8B, 0x74, 0x24, 0x5C};
constexpr unsigned char kExpectedHandlePrescan[] = {
    0x8B, 0x7D, 0x2C, 0x8B, 0x4C, 0x24, 0x64, 0x51, 0x8B, 0xCF};
constexpr unsigned char kExpectedCacheGetter[] = {
    0x56, 0x8B, 0xF1, 0x8B, 0x86, 0x38, 0x01, 0x00, 0x00, 0x85, 0xC0, 0x75, 0x43};
constexpr unsigned char kExpectedDestructorSlot28[] = {
    0x8B, 0x4E, 0x28, 0xC7, 0x06, 0x00, 0x00, 0x00, 0x00,
    0xC7, 0x46, 0x04, 0x00, 0x00, 0x00, 0x00, 0x85, 0xC9, 0x74, 0x07};
constexpr unsigned char kExpectedWrapperAssign[] = {
    0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0x07, 0x8B, 0x10, 0x8B, 0xF1};
constexpr unsigned char kExpectedReleasePointer[] = {
    0x8B, 0x4C, 0x24, 0x04, 0x8B, 0x01, 0x8B, 0x50, 0x04, 0xFF, 0xE2};
constexpr unsigned char kExpectedReleaseVtable8[] = {
    0x8B, 0x01, 0x8B, 0x50, 0x08, 0xFF, 0xD2};

constexpr std::uint32_t kInterfaceImageTag = 0x61444E49u;  // INDa
constexpr std::uint32_t kImageResourceType = 0x47414D49u; // IMAG
constexpr std::uint32_t kAcquireFlagsBind = 0x80000000u;
constexpr std::uint32_t kAcquireFlagsAlternate = 0x80000001u;
constexpr std::uint32_t kAcquireFlagsFont = 0x80000003u;

constexpr int kRegistryCacheCapacity = 16;
constexpr int kEnsureDepthCapacity = 8;
constexpr int kPendingHandleCapacity = 16;
constexpr int kPatchCapacity = 16;
constexpr std::uintptr_t kMajestyComVtableSpan = 0x00400000;

#if defined(FREESTYLE_CAM_DIAGNOSTIC_NAMED_RETENTION)
bool g_diagnosticTracing = true;
bool g_namedRetentionOnly = true;
#elif defined(FREESTYLE_CAM_DIAGNOSTIC_PARITY)
bool g_diagnosticTracing = true;
bool g_namedRetentionOnly = false;
#else
bool g_diagnosticTracing = false;
bool g_namedRetentionOnly = false;
#endif

struct RegistryCacheEntry {
    std::uint32_t tag;
    std::uint32_t registry;
};

struct EnsureFrame {
    std::uint32_t tag;
    std::uint32_t pending[kPendingHandleCapacity];
    int count;
};

struct InstalledPatch {
    unsigned char* site;
    unsigned char original[9];
    std::size_t size;
};

const FreestyleCamProfile* g_profile = nullptr;
HMODULE g_runtimeModule = nullptr;
std::uintptr_t g_imageBase = 0;
std::uintptr_t g_imageLimit = 0;
std::uintptr_t g_codeStart = 0;
std::uintptr_t g_codeLimit = 0;
std::uint32_t* g_managerSlot = nullptr;

unsigned char* g_handleUseSite = nullptr;
unsigned char* g_handleUse2Site = nullptr;
unsigned char* g_handleFrameSite = nullptr;
unsigned char* g_handleGridSite = nullptr;
unsigned char* g_handlePrescanSite = nullptr;
unsigned char* g_cacheGetterSite = nullptr;
unsigned char* g_destructorSlot28Site = nullptr;
unsigned char* g_wrapperAssignSite = nullptr;
unsigned char* g_releasePointerSite = nullptr;
unsigned char* g_releaseVtable8Sites[2] = {};

unsigned char g_handleUseTrampoline[16] = {};
unsigned char g_handleUse2Trampoline[16] = {};
unsigned char g_handleFrameTrampoline[16] = {};
unsigned char g_handleGridTrampoline[16] = {};
unsigned char g_handlePrescanTrampoline[16] = {};
unsigned char g_destructorSlot28Trampoline[16] = {};
unsigned char g_cacheGetterCopy[0x60] = {};

RegistryCacheEntry g_registryCache[kRegistryCacheCapacity] = {};
int g_registryCacheCount = 0;
int g_registryCacheClock = 0;
EnsureFrame g_ensureFrames[kEnsureDepthCapacity] = {};
int g_ensureDepth = 0;

InstalledPatch g_installedPatches[kPatchCapacity] = {};
int g_installedPatchCount = 0;
int g_rebindLogCount = 0;
int g_skipLogCount = 0;
int g_acquireLogCount = 0;
int g_staleLogCount = 0;
int g_assignmentLogCount = 0;
int g_invalidationLogCount = 0;

void Log(const char* message) {
    if (g_runtimeModule == nullptr || message == nullptr) {
        return;
    }
    char modulePath[MAX_PATH] = {};
    if (!GetModuleFileNameA(g_runtimeModule, modulePath, MAX_PATH)) {
        return;
    }
    char* separator = std::strrchr(modulePath, '\\');
    if (separator != nullptr) {
        separator[1] = '\0';
    }
    strcat_s(modulePath, "MajestyBuildingRuntime.log");
    FILE* stream = nullptr;
    if (fopen_s(&stream, modulePath, "a") != 0 || stream == nullptr) {
        return;
    }
    SYSTEMTIME now = {};
    GetLocalTime(&now);
    std::fprintf(
        stream,
        "%04u-%02u-%02u %02u:%02u:%02u.%03u Freestyle CAM: %s\n",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    std::fclose(stream);
}

void LogFormat(const char* format, ...) {
    char message[512] = {};
    va_list arguments;
    va_start(arguments, format);
    vsprintf_s(message, format, arguments);
    va_end(arguments);
    Log(message);
}

bool Matches(
    std::uintptr_t rva,
    const unsigned char* expected,
    std::size_t size,
    const char* label) {
    const auto* actual = reinterpret_cast<const unsigned char*>(g_imageBase + rva);
    if (std::memcmp(actual, expected, size) == 0) {
        return true;
    }
    LogFormat("preflight refused %s at MajestyHD.exe+0x%08X", label,
              static_cast<unsigned int>(rva));
    return false;
}

bool IsFourcc(std::uint32_t tag) {
    if (tag == 0) {
        return false;
    }
    for (int index = 0; index < 4; ++index) {
        const unsigned char value = static_cast<unsigned char>(tag >> (index * 8));
        const bool alpha = (value >= 'A' && value <= 'Z') ||
            (value >= 'a' && value <= 'z');
        const bool digit = value >= '0' && value <= '9';
        if (!alpha && !digit) {
            return false;
        }
    }
    return true;
}

bool IsGameVtable(std::uint32_t pointer) {
    if (pointer < 0x10000) {
        return false;
    }
    std::uint32_t vtable = 0;
    __try {
        vtable = *reinterpret_cast<std::uint32_t*>(pointer);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return vtable >= g_imageBase && vtable < g_imageLimit;
}

bool IsGameCode(std::uint32_t pointer) {
    return pointer >= g_codeStart && pointer < g_codeLimit;
}

// Stock 0x65C0E0 consumes the wrapper installed by 0x681BA0 through this
// complete interface shape: AddRef (+0), Release (+4), then +18, +10, +14.
// A recycled named-node can accidentally begin with an address in Majesty's
// broad vtable span; requiring the methods stock actually dispatches prevents
// that data record from being retained as a render wrapper.
bool IsStockRenderWrapper(std::uint32_t pointer) {
    if (!IsGameVtable(pointer)) {
        return false;
    }
    std::uint32_t vtable = 0;
    std::uint32_t addRef = 0;
    std::uint32_t release = 0;
    std::uint32_t method10 = 0;
    std::uint32_t method14 = 0;
    std::uint32_t method18 = 0;
    __try {
        vtable = *reinterpret_cast<std::uint32_t*>(pointer);
        addRef = *reinterpret_cast<std::uint32_t*>(vtable);
        release = *reinterpret_cast<std::uint32_t*>(vtable + 0x04);
        method10 = *reinterpret_cast<std::uint32_t*>(vtable + 0x10);
        method14 = *reinterpret_cast<std::uint32_t*>(vtable + 0x14);
        method18 = *reinterpret_cast<std::uint32_t*>(vtable + 0x18);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return IsGameCode(addRef) && IsGameCode(release) &&
        IsGameCode(method10) && IsGameCode(method14) && IsGameCode(method18);
}

bool HasStockVtableMethod(std::uint32_t pointer, std::uintptr_t offset) {
    if (!IsGameVtable(pointer)) {
        return false;
    }
    std::uint32_t method = 0;
    __try {
        const std::uint32_t vtable =
            *reinterpret_cast<std::uint32_t*>(pointer);
        method = *reinterpret_cast<std::uint32_t*>(vtable + offset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return IsGameCode(method);
}

std::uint32_t VtableOf(std::uint32_t pointer) {
    if (pointer < 0x10000) {
        return 0;
    }
    __try {
        return *reinterpret_cast<std::uint32_t*>(pointer);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

bool RegistryLooksLive(std::uint32_t registry) {
    if (registry < 0x10000) {
        return false;
    }
    std::uint32_t count = 0;
    std::uint32_t array = 0;
    std::uint32_t first = 0;
    __try {
        count = *reinterpret_cast<std::uint32_t*>(registry + 0x0C);
        array = *reinterpret_cast<std::uint32_t*>(registry + 0x10);
        if (count < 1 || count > 64 || array < 0x10000 || array == count) {
            return false;
        }
        first = *reinterpret_cast<std::uint32_t*>(array);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return first != 0 && first < 0x10000;
}

bool IsInterfaceRegistry(std::uint32_t registry) {
    if (registry < 0x10000) {
        return false;
    }
    std::uint32_t count = 0;
    std::uint32_t array = 0;
    std::uint32_t first = 0;
    __try {
        count = *reinterpret_cast<std::uint32_t*>(registry + 0x0C);
        array = *reinterpret_cast<std::uint32_t*>(registry + 0x10);
        if (count != 9 || array < 0x10000 || array == count) {
            return false;
        }
        first = *reinterpret_cast<std::uint32_t*>(array);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return first == 0x3E8;
}

std::uint32_t FirstPayload(std::uint32_t registry) {
    if (registry < 0x10000) {
        return 0;
    }
    __try {
        const std::uint32_t array = *reinterpret_cast<std::uint32_t*>(registry + 0x10);
        return *reinterpret_cast<std::uint32_t*>(array + 0x20);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

struct RegistrySnapshot {
    std::uint32_t count;
    std::uint32_t array;
    std::uint32_t first;
    std::uint32_t payload;
};

RegistrySnapshot SnapshotRegistry(std::uint32_t registry) {
    RegistrySnapshot snapshot = {};
    if (registry < 0x10000) {
        return snapshot;
    }
    __try {
        snapshot.count = *reinterpret_cast<std::uint32_t*>(registry + 0x0C);
        snapshot.array = *reinterpret_cast<std::uint32_t*>(registry + 0x10);
        if (snapshot.array >= 0x10000) {
            snapshot.first = *reinterpret_cast<std::uint32_t*>(snapshot.array);
            snapshot.payload =
                *reinterpret_cast<std::uint32_t*>(snapshot.array + 0x20);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        snapshot = {};
    }
    return snapshot;
}

bool RegistryValidForTag(std::uint32_t tag, std::uint32_t registry) {
    if (tag == kInterfaceImageTag) {
        return IsInterfaceRegistry(registry) && FirstPayload(registry) >= 0x10000;
    }
    return RegistryLooksLive(registry);
}

bool RegistryCandidate(std::uint32_t pointer) {
    return RegistryLooksLive(pointer) || IsInterfaceRegistry(pointer);
}

std::uint32_t RegistryFromAcquired(std::uint32_t acquired) {
    if (RegistryCandidate(acquired)) {
        return acquired;
    }
    if (acquired < 0x10000) {
        return 0;
    }
    std::uint32_t candidate = 0;
    __try {
        candidate = *reinterpret_cast<std::uint32_t*>(acquired + 0x20);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    if (RegistryCandidate(candidate)) {
        return candidate;
    }
    __try {
        candidate = *reinterpret_cast<std::uint32_t*>(acquired + 0x2C);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return RegistryCandidate(candidate) ? candidate : 0;
}

std::uint32_t AcquireImage(std::uint32_t resourceId, std::uint32_t flags) {
    if (g_managerSlot == nullptr) {
        return 0;
    }
    std::uint32_t manager = 0;
    std::uint32_t vtable = 0;
    std::uint32_t function = 0;
    __try {
        manager = *g_managerSlot;
        if (manager < 0x10000) {
            return 0;
        }
        vtable = *reinterpret_cast<std::uint32_t*>(manager);
        function = *reinterpret_cast<std::uint32_t*>(vtable + 0x38);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    if (function < 0x10000) {
        return 0;
    }
    std::uint32_t result = 0;
    __try {
        __asm {
            push 0
            push 0
            push flags
            push 0
            push resourceId
            push 047414D49h
            push 0
            mov ecx, manager
            mov eax, function
            call eax
            mov result, eax
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = 0;
    }
    return result;
}

std::uint32_t PickRegistry(std::uint32_t tag) {
    constexpr std::uint32_t flags[] = {
        kAcquireFlagsBind, kAcquireFlagsFont, kAcquireFlagsAlternate};
    std::uint32_t fallback = 0;
    for (const std::uint32_t value : flags) {
        const std::uint32_t acquired = AcquireImage(tag, value);
        const std::uint32_t registry = RegistryFromAcquired(acquired);
        if (g_diagnosticTracing && g_acquireLogCount < 96) {
            const RegistrySnapshot snapshot = SnapshotRegistry(registry);
            LogFormat(
                "diag acquire tag=%08X flags=%08X acquired=%08X registry=%08X count=%u first=%08X payload=%08X live=%u interface=%u",
                tag,
                value,
                acquired,
                registry,
                snapshot.count,
                snapshot.first,
                snapshot.payload,
                RegistryLooksLive(registry) ? 1u : 0u,
                IsInterfaceRegistry(registry) ? 1u : 0u);
            ++g_acquireLogCount;
        }
        if (registry == 0) {
            continue;
        }
        if (IsInterfaceRegistry(registry) && FirstPayload(registry) >= 0x10000) {
            return registry;
        }
        if (RegistryLooksLive(registry) && fallback == 0) {
            fallback = registry;
        }
    }
    return fallback;
}

void ClearRegistryCache() {
    std::memset(g_registryCache, 0, sizeof(g_registryCache));
    g_registryCacheCount = 0;
    g_registryCacheClock = 0;
}

std::uint32_t FindCachedRegistry(std::uint32_t tag) {
    for (int index = 0; index < g_registryCacheCount; ++index) {
        if (g_registryCache[index].tag != tag) {
            continue;
        }
        const std::uint32_t registry = g_registryCache[index].registry;
        if (RegistryValidForTag(tag, registry) && FirstPayload(registry) >= 0x10000) {
            return registry;
        }
        g_registryCache[index].registry = 0;
        return 0;
    }
    return 0;
}

void CacheRegistry(std::uint32_t tag, std::uint32_t registry) {
    for (int index = 0; index < g_registryCacheCount; ++index) {
        if (g_registryCache[index].tag == tag) {
            g_registryCache[index].registry = registry;
            return;
        }
    }
    if (g_registryCacheCount < kRegistryCacheCapacity) {
        g_registryCache[g_registryCacheCount++] = {tag, registry};
        return;
    }
    g_registryCache[g_registryCacheClock] = {tag, registry};
    g_registryCacheClock = (g_registryCacheClock + 1) % kRegistryCacheCapacity;
}

EnsureFrame* FindEnsureFrame(std::uint32_t tag) {
    for (int index = 0; index < g_ensureDepth; ++index) {
        if (g_ensureFrames[index].tag == tag) {
            return &g_ensureFrames[index];
        }
    }
    return nullptr;
}

void AddPendingHandle(EnsureFrame* frame, std::uint32_t handle) {
    if (frame == nullptr) {
        return;
    }
    for (int index = 0; index < frame->count; ++index) {
        if (frame->pending[index] == handle) {
            return;
        }
    }
    if (frame->count < kPendingHandleCapacity) {
        frame->pending[frame->count++] = handle;
    }
}

void ZeroHandleRegistry(std::uint32_t handle) {
    __try {
        *reinterpret_cast<std::uint32_t*>(handle + 0x2C) = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

void InvalidateWrapperChain(std::uint32_t handle) {
    std::uint32_t owner = handle - 0xCC;
    if (owner < 0x10000) {
        return;
    }
    std::uint32_t stale = 0;
    __try {
        stale = *reinterpret_cast<std::uint32_t*>(owner + 0x138);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (stale == 0) {
        return;
    }
    for (int hop = 0; hop < 6 && owner >= 0x10000; ++hop) {
        std::uint32_t vtable = 0;
        std::uint32_t cached = 0;
        std::uint32_t parent = 0;
        __try {
            vtable = *reinterpret_cast<std::uint32_t*>(owner);
            cached = *reinterpret_cast<std::uint32_t*>(owner + 0x138);
            parent = *reinterpret_cast<std::uint32_t*>(owner + 0x0C);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            return;
        }
        if (g_diagnosticTracing && g_invalidationLogCount < 96) {
            LogFormat(
                "diag invalidate handle=%08X owner=%08X hop=%d vt=%08X cached=%08X stale=%08X parent=%08X clear=%u",
                handle,
                owner,
                hop,
                vtable,
                cached,
                stale,
                parent,
                (vtable >= g_imageBase && vtable < g_imageLimit && cached == stale)
                    ? 1u
                    : 0u);
            ++g_invalidationLogCount;
        }
        if (vtable >= g_imageBase && vtable < g_imageLimit && cached == stale) {
            __try {
                *reinterpret_cast<std::uint32_t*>(owner + 0x138) = 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return;
            }
        }
        owner = parent;
    }
}

bool ApplyRegistry(
    std::uint32_t handle,
    std::uint32_t tag,
    std::uint32_t registry) {
    if (!RegistryCandidate(registry)) {
        return false;
    }
    std::uint32_t previous = 0;
    std::uint32_t kind = 0;
    std::uint32_t id = 0;
    __try {
        previous = *reinterpret_cast<std::uint32_t*>(handle + 0x2C);
        kind = *reinterpret_cast<std::uint32_t*>(handle);
        id = *reinterpret_cast<std::uint32_t*>(handle + 0x14);
        *reinterpret_cast<std::uint32_t*>(handle + 0x2C) = registry;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    InvalidateWrapperChain(handle);
    if (g_rebindLogCount < 24) {
        const RegistrySnapshot snapshot = SnapshotRegistry(registry);
        LogFormat(
            "rebound handle=%08X kind=%u tag=%08X id=%08X previous=%08X registry=%08X count=%u first=%08X payload=%08X",
            handle,
            kind,
            tag,
            id,
            previous,
            registry,
            snapshot.count,
            snapshot.first,
            snapshot.payload);
        ++g_rebindLogCount;
    }
    return true;
}

void EnsureLiveRegistry(std::uint32_t handle) {
    if (handle < 0x10000) {
        return;
    }
    std::uint32_t kind = 0;
    std::uint32_t tag = 0;
    std::uint32_t id = 0;
    std::uint32_t current = 0;
    __try {
        kind = *reinterpret_cast<std::uint32_t*>(handle);
        tag = *reinterpret_cast<std::uint32_t*>(handle + 0x10);
        id = *reinterpret_cast<std::uint32_t*>(handle + 0x14);
        current = *reinterpret_cast<std::uint32_t*>(handle + 0x2C);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (RegistryValidForTag(tag, current)) {
        return;
    }
    if (g_diagnosticTracing && current != 0 && g_staleLogCount < 96) {
        const RegistrySnapshot snapshot = SnapshotRegistry(current);
        LogFormat(
            "diag stale handle=%08X kind=%u tag=%08X id=%08X registry=%08X count=%u first=%08X payload=%08X",
            handle,
            kind,
            tag,
            id,
            current,
            snapshot.count,
            snapshot.first,
            snapshot.payload);
        ++g_staleLogCount;
    }
    if (IsFourcc(tag)) {
        const std::uint32_t cached = FindCachedRegistry(tag);
        if (cached != 0) {
            ApplyRegistry(handle, tag, cached);
            return;
        }
        EnsureFrame* inflight = FindEnsureFrame(tag);
        if (inflight != nullptr) {
            if (current != 0) {
                ZeroHandleRegistry(handle);
            }
            AddPendingHandle(inflight, handle);
            return;
        }
    }
    if (current == 0) {
        return;
    }
    if (!IsFourcc(tag)) {
        ZeroHandleRegistry(handle);
        return;
    }
    if (g_ensureDepth >= kEnsureDepthCapacity) {
        ZeroHandleRegistry(handle);
        return;
    }

    EnsureFrame* frame = &g_ensureFrames[g_ensureDepth++];
    frame->tag = tag;
    frame->count = 0;
    __try {
        const std::uint32_t registry = PickRegistry(tag);
        if (registry == 0 || !RegistryCandidate(registry)) {
            InvalidateWrapperChain(handle);
            ZeroHandleRegistry(handle);
        } else {
            CacheRegistry(tag, registry);
            ApplyRegistry(handle, tag, registry);
            for (int index = 0; index < frame->count; ++index) {
                ApplyRegistry(frame->pending[index], tag, registry);
            }
        }
    } __finally {
        frame->tag = 0;
        frame->count = 0;
        --g_ensureDepth;
    }
    (void)kind;
}

void ComRelease(std::uint32_t pointer) {
    if (!IsGameVtable(pointer)) {
        return;
    }
    __try {
        __asm {
            mov ecx, pointer
            mov eax, dword ptr [ecx]
            mov edx, dword ptr [eax + 4]
            call edx
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

void ComAddRef(std::uint32_t pointer) {
    if (!IsGameVtable(pointer)) {
        return;
    }
    __try {
        __asm {
            mov ecx, pointer
            mov eax, dword ptr [ecx]
            mov edx, dword ptr [eax]
            call edx
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

void __stdcall SafeAssign(
    std::uint32_t owner,
    std::uint32_t incoming,
    std::uint32_t caller) {
    if (!IsStockRenderWrapper(incoming)) {
        incoming = 0;
    }
    if (owner < 0x10000) {
        return;
    }
    std::uint32_t previous = 0;
    __try {
        previous = *reinterpret_cast<std::uint32_t*>(owner + 0x28);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (incoming != 0) {
        ComAddRef(incoming);
    }
    const bool parityRetention = previous == incoming &&
        (!g_namedRetentionOnly ||
         caller == g_imageBase + g_profile->namedWrapperCopyCallerRva);
    const bool releasePrevious =
        previous != 0 && !parityRetention && IsStockRenderWrapper(previous);
    if (releasePrevious) {
        ComRelease(previous);
    }
    __try {
        *reinterpret_cast<std::uint32_t*>(owner + 0x28) = incoming;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (g_diagnosticTracing && g_assignmentLogCount < 128) {
        LogFormat(
            "diag assign caller=%08X owner=%08X previous=%08X previousVt=%08X incoming=%08X incomingVt=%08X same=%u released=%u",
            caller,
            owner,
            previous,
            VtableOf(previous),
            incoming,
            VtableOf(incoming),
            previous == incoming ? 1u : 0u,
            releasePrevious ? 1u : 0u);
        ++g_assignmentLogCount;
    }
}

std::uint32_t __stdcall FilterGetter(std::uint32_t owner) {
    if (owner < 0x10000) {
        return 0;
    }
    std::uint32_t result = 0;
    __try {
        __asm {
            mov ecx, owner
            mov eax, offset g_cacheGetterCopy
            call eax
            mov result, eax
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = 0;
    }
    if (IsStockRenderWrapper(result)) {
        return result;
    }
    __try {
        const std::uint32_t cached =
            *reinterpret_cast<std::uint32_t*>(owner + 0x138);
        if (cached == result ||
            (cached != 0 && !IsStockRenderWrapper(cached))) {
            *reinterpret_cast<std::uint32_t*>(owner + 0x138) = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

void ClearDeadSlot28(std::uint32_t owner) {
    if (owner < 0x10000) {
        return;
    }
    std::uint32_t pointer = 0;
    __try {
        pointer = *reinterpret_cast<std::uint32_t*>(owner + 0x28);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (pointer == 0 || IsStockRenderWrapper(pointer)) {
        return;
    }
    __try {
        *reinterpret_cast<std::uint32_t*>(owner + 0x28) = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    ClearRegistryCache();
    if (g_skipLogCount < 16) {
        LogFormat("skipped dead owner+0x28 wrapper=%08X", pointer);
        ++g_skipLogCount;
    }
}

void __stdcall SafeReleasePointer(std::uint32_t pointer) {
    if (IsStockRenderWrapper(pointer)) {
        ComRelease(pointer);
        return;
    }
    ClearRegistryCache();
}

void __stdcall SafeReleaseVtable8(std::uint32_t pointer) {
    if (HasStockVtableMethod(pointer, 0x08)) {
        __try {
            __asm {
                mov ecx, pointer
                mov eax, dword ptr [ecx]
                mov edx, dword ptr [eax + 8]
                call edx
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return;
    }
    ClearRegistryCache();
}

__declspec(naked) void HandleUseHook() {
    __asm {
        pushad
        push ecx
        call EnsureLiveRegistry
        add esp, 4
        popad
        mov eax, offset g_handleUseTrampoline
        jmp eax
    }
}

__declspec(naked) void HandleUse2Hook() {
    __asm {
        pushad
        push ecx
        call EnsureLiveRegistry
        add esp, 4
        popad
        mov eax, offset g_handleUse2Trampoline
        jmp eax
    }
}

__declspec(naked) void HandleFrameHook() {
    __asm {
        pushad
        push ecx
        call EnsureLiveRegistry
        add esp, 4
        popad
        mov eax, offset g_handleFrameTrampoline
        jmp eax
    }
}

__declspec(naked) void HandleGridHook() {
    __asm {
        pushad
        push ecx
        call EnsureLiveRegistry
        add esp, 4
        popad
        mov eax, offset g_handleGridTrampoline
        jmp eax
    }
}

__declspec(naked) void HandlePrescanHook() {
    __asm {
        pushad
        push ebp
        call EnsureLiveRegistry
        add esp, 4
        popad
        mov eax, offset g_handlePrescanTrampoline
        jmp eax
    }
}

__declspec(naked) void CacheGetterHook() {
    __asm {
        push ecx
        call FilterGetter
        ret
    }
}

__declspec(naked) void DestructorSlot28Hook() {
    __asm {
        pushad
        push esi
        call ClearDeadSlot28
        add esp, 4
        popad
        mov eax, offset g_destructorSlot28Trampoline
        jmp eax
    }
}

__declspec(naked) void WrapperAssignHook() {
    __asm {
        mov eax, dword ptr [esp]
        mov edx, dword ptr [esp + 4]
        push eax
        push edx
        push ecx
        call SafeAssign
        ret 4
    }
}

__declspec(naked) void ReleasePointerHook() {
    __asm {
        push dword ptr [esp + 4]
        call SafeReleasePointer
        ret
    }
}

bool MakeTrampoline(
    unsigned char* trampoline,
    std::size_t capacity,
    unsigned char* site,
    std::size_t stolen) {
    if (stolen + 5 > capacity) {
        return false;
    }
    std::memcpy(trampoline, site, stolen);
    trampoline[stolen] = 0xE9;
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(site + stolen) -
        (reinterpret_cast<std::uintptr_t>(trampoline + stolen) + 5));
    std::memcpy(trampoline + stolen + 1, &relative, sizeof(relative));
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            trampoline, capacity, PAGE_EXECUTE_READWRITE, &oldProtection)) {
        return false;
    }
    FlushInstructionCache(GetCurrentProcess(), trampoline, capacity);
    return true;
}

bool WritePatch(
    unsigned char* site,
    const unsigned char* patch,
    std::size_t size) {
    if (g_installedPatchCount >= kPatchCapacity || size > 9) {
        return false;
    }
    InstalledPatch& record = g_installedPatches[g_installedPatchCount];
    record.site = site;
    record.size = size;
    std::memcpy(record.original, site, size);
    DWORD oldProtection = 0;
    if (!VirtualProtect(site, size, PAGE_EXECUTE_READWRITE, &oldProtection)) {
        return false;
    }
    std::memcpy(site, patch, size);
    FlushInstructionCache(GetCurrentProcess(), site, size);
    DWORD ignored = 0;
    VirtualProtect(site, size, oldProtection, &ignored);
    ++g_installedPatchCount;
    return true;
}

bool WriteJump(unsigned char* site, const void* target) {
    unsigned char patch[5] = {0xE9, 0, 0, 0, 0};
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(target) -
        (reinterpret_cast<std::uintptr_t>(site) + 5));
    std::memcpy(patch + 1, &relative, sizeof(relative));
    return WritePatch(site, patch, sizeof(patch));
}

bool WriteReleaseVtable8Patch(unsigned char* site) {
    unsigned char patch[7] = {0x51, 0xE8, 0, 0, 0, 0, 0x90};
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&SafeReleaseVtable8) -
        (reinterpret_cast<std::uintptr_t>(site) + 6));
    std::memcpy(patch + 2, &relative, sizeof(relative));
    return WritePatch(site, patch, sizeof(patch));
}

void RollBackPatches() {
    while (g_installedPatchCount > 0) {
        InstalledPatch& record = g_installedPatches[--g_installedPatchCount];
        DWORD oldProtection = 0;
        if (VirtualProtect(
                record.site,
                record.size,
                PAGE_EXECUTE_READWRITE,
                &oldProtection)) {
            std::memcpy(record.site, record.original, record.size);
            FlushInstructionCache(GetCurrentProcess(), record.site, record.size);
            DWORD ignored = 0;
            VirtualProtect(record.site, record.size, oldProtection, &ignored);
        }
        record = {};
    }
}

bool PreflightProfile() {
    return Matches(
               g_profile->handleUseRva,
               kExpectedHandleUse,
               sizeof(kExpectedHandleUse),
               "IMAG handle use") &&
        Matches(
               g_profile->handleUse2Rva,
               kExpectedHandleUse2,
               sizeof(kExpectedHandleUse2),
               "named-construction IMAG handle use") &&
        Matches(
               g_profile->handleFrameRva,
               kExpectedHandleFrame,
               sizeof(kExpectedHandleFrame),
               "IMAG frame walk") &&
        Matches(
               g_profile->handleGridRva,
               kExpectedHandleGrid,
               sizeof(kExpectedHandleGrid),
               "IMAG grid draw") &&
        Matches(
               g_profile->handlePrescanRva,
               kExpectedHandlePrescan,
               sizeof(kExpectedHandlePrescan),
               "IMAG grid prescan") &&
        Matches(
               g_profile->cacheGetterRva,
               kExpectedCacheGetter,
               sizeof(kExpectedCacheGetter),
               "wrapper cache getter") &&
        Matches(
               g_profile->destructorSlot28Rva,
               kExpectedDestructorSlot28,
               sizeof(kExpectedDestructorSlot28),
               "load-UI owner destructor") &&
        Matches(
               g_profile->wrapperAssignRva,
               kExpectedWrapperAssign,
               sizeof(kExpectedWrapperAssign),
               "stock wrapper assignment") &&
        Matches(
               g_profile->releasePointerRva,
               kExpectedReleasePointer,
               sizeof(kExpectedReleasePointer),
               "stock release thunk") &&
        Matches(
               g_profile->releaseVtable8Rvas[0],
               kExpectedReleaseVtable8,
               sizeof(kExpectedReleaseVtable8),
               "load-UI release site one") &&
        Matches(
               g_profile->releaseVtable8Rvas[1],
               kExpectedReleaseVtable8,
               sizeof(kExpectedReleaseVtable8),
               "load-UI release site two") &&
        Matches(
               g_profile->managerLoadRva,
               g_profile->expectedManagerLoad,
               sizeof(g_profile->expectedManagerLoad),
               "resource-manager singleton load");
}

bool PrepareTrampolines() {
    if (!MakeTrampoline(
            g_handleUseTrampoline,
            sizeof(g_handleUseTrampoline),
            g_handleUseSite,
            5) ||
        !MakeTrampoline(
            g_handleUse2Trampoline,
            sizeof(g_handleUse2Trampoline),
            g_handleUse2Site,
            5) ||
        !MakeTrampoline(
            g_handleFrameTrampoline,
            sizeof(g_handleFrameTrampoline),
            g_handleFrameSite,
            9) ||
        !MakeTrampoline(
            g_handleGridTrampoline,
            sizeof(g_handleGridTrampoline),
            g_handleGridSite,
            5) ||
        !MakeTrampoline(
            g_handlePrescanTrampoline,
            sizeof(g_handlePrescanTrampoline),
            g_handlePrescanSite,
            7) ||
        !MakeTrampoline(
            g_destructorSlot28Trampoline,
            sizeof(g_destructorSlot28Trampoline),
            g_destructorSlot28Site,
            9)) {
        return false;
    }
    std::memcpy(g_cacheGetterCopy, g_cacheGetterSite, 0x52);
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            g_cacheGetterCopy,
            sizeof(g_cacheGetterCopy),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        return false;
    }
    FlushInstructionCache(
        GetCurrentProcess(), g_cacheGetterCopy, sizeof(g_cacheGetterCopy));
    return true;
}

bool InstallHooks() {
    const bool installed =
        WriteJump(g_handleUseSite, &HandleUseHook) &&
        WriteJump(g_handleUse2Site, &HandleUse2Hook) &&
        WriteJump(g_handleFrameSite, &HandleFrameHook) &&
        WriteJump(g_handleGridSite, &HandleGridHook) &&
        WriteJump(g_handlePrescanSite, &HandlePrescanHook) &&
        WriteJump(g_cacheGetterSite, &CacheGetterHook) &&
        WriteJump(g_destructorSlot28Site, &DestructorSlot28Hook) &&
        WriteJump(g_wrapperAssignSite, &WrapperAssignHook) &&
        WriteJump(g_releasePointerSite, &ReleasePointerHook) &&
        WriteReleaseVtable8Patch(g_releaseVtable8Sites[0]) &&
        WriteReleaseVtable8Patch(g_releaseVtable8Sites[1]);
    if (!installed) {
        RollBackPatches();
        return false;
    }
    return true;
}

}  // namespace

bool InstallFreestyleCamRuntime(HMODULE runtimeModule, const char* profileId) {
    g_runtimeModule = runtimeModule;
    g_imageBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    if (g_imageBase == 0 || profileId == nullptr) {
        Log("installation refused because the host image or profile is unavailable");
        return false;
    }
    if (std::strcmp(profileId, kPublicFreestyleProfile.id) == 0) {
        g_profile = &kPublicFreestyleProfile;
    } else if (std::strcmp(profileId, kBeta2FreestyleProfile.id) == 0) {
        g_profile = &kBeta2FreestyleProfile;
    } else if (std::strcmp(profileId, kGogFreestyleProfile.id) == 0) {
        if (g_diagnosticTracing) return false;
        g_profile = &kGogFreestyleProfile;
    } else {
        LogFormat("installation refused unknown runtime profile %s", profileId);
        return false;
    }

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(g_imageBase);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        Log("installation refused invalid host DOS header");
        return false;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
        g_imageBase + static_cast<std::uintptr_t>(dos->e_lfanew));
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) {
        Log("installation refused invalid host PE header");
        return false;
    }
    if (nt->OptionalHeader.SizeOfImage < kMajestyComVtableSpan) {
        Log("installation refused host image is smaller than Majesty's COM-vtable span");
        return false;
    }
    // Match the upstream checkpoint's measured live-COM predicate exactly.
    // Majesty's beta2 PE extends to 0x00832000, but the tail is not a vtable
    // range and must never authorize AddRef/Release or wrapper invalidation.
    g_imageLimit = g_imageBase + kMajestyComVtableSpan;
    const IMAGE_SECTION_HEADER* sections = IMAGE_FIRST_SECTION(nt);
    const std::uintptr_t stockCodeRva = g_profile->wrapperAssignRva;
    for (unsigned int index = 0; index < nt->FileHeader.NumberOfSections; ++index) {
        const IMAGE_SECTION_HEADER& section = sections[index];
        const std::uintptr_t extent =
            section.Misc.VirtualSize > section.SizeOfRawData
                ? section.Misc.VirtualSize
                : section.SizeOfRawData;
        if ((section.Characteristics & IMAGE_SCN_MEM_EXECUTE) == 0 ||
            stockCodeRva < section.VirtualAddress ||
            stockCodeRva >= section.VirtualAddress + extent) {
            continue;
        }
        g_codeStart = g_imageBase + section.VirtualAddress;
        g_codeLimit = g_codeStart + extent;
        break;
    }
    if (g_codeStart == 0 || g_codeLimit <= g_codeStart) {
        Log("installation refused because Majesty's stock code section was not found");
        return false;
    }
    g_managerSlot = reinterpret_cast<std::uint32_t*>(
        g_imageBase + g_profile->managerSingletonRva);

    g_handleUseSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->handleUseRva);
    g_handleUse2Site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->handleUse2Rva);
    g_handleFrameSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->handleFrameRva);
    g_handleGridSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->handleGridRva);
    g_handlePrescanSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->handlePrescanRva);
    g_cacheGetterSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->cacheGetterRva);
    g_destructorSlot28Site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->destructorSlot28Rva);
    g_wrapperAssignSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->wrapperAssignRva);
    g_releasePointerSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_profile->releasePointerRva);
    for (int index = 0; index < 2; ++index) {
        g_releaseVtable8Sites[index] = reinterpret_cast<unsigned char*>(
            g_imageBase + g_profile->releaseVtable8Rvas[index]);
    }

    if (!PreflightProfile()) {
        LogFormat("all-or-nothing preflight failed for %s; no Freestyle hooks written",
                  g_profile->id);
        return false;
    }
    if (!PrepareTrampolines()) {
        Log("trampoline preparation failed; no Freestyle hooks written");
        return false;
    }
    if (!InstallHooks()) {
        Log("hook installation failed and the complete Freestyle group was rolled back");
        return false;
    }
    LogFormat(
        "installed stock IMAG rebind and dead-wrapper teardown guards for %s mode=%s",
        g_profile->id,
        g_namedRetentionOnly
            ? "named-wrapper-retention-diagnostic"
            : (g_diagnosticTracing
                   ? "upstream-parity-diagnostic"
                   : "upstream-parity"));
    return true;
}
