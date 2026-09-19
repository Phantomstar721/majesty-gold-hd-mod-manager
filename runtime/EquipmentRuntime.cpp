#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstring>
#include "EquipmentRuntime.h"

namespace {
std::uintptr_t g_base = 0;
const MajestyRuntimeFeatures::Registry* g_registry = nullptr;
void (*g_fatal)(const char*) = nullptr;

template<class T> T Native(std::uintptr_t rva) {
    return reinterpret_cast<T>(g_base + rva);
}
bool Bytes(std::uintptr_t rva, const char* bytes, std::size_t length) {
    return std::memcmp(Native<const void*>(rva), bytes, length) == 0;
}
bool Call(std::uintptr_t rva, std::uintptr_t target) {
    const auto* site = Native<const unsigned char*>(rva);
    std::int32_t displacement = 0;
    std::memcpy(&displacement, site + 1, 4);
    return site[0] == 0xE8 && g_base + rva + 5 + displacement == g_base + target;
}
bool Pointer(std::uintptr_t rva, std::uintptr_t expected) {
    std::uintptr_t value = 0;
    std::memcpy(&value, Native<const void*>(rva), sizeof(value));
    return value == g_base + expected;
}
bool RedirectCall(std::uintptr_t rva, const void* target) {
    auto* site = Native<unsigned char*>(rva);
    DWORD old = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    const auto displacement = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(target) - (g_base + rva + 5));
    std::memcpy(site + 1, &displacement, 4);
    const bool flushed = FlushInstructionCache(GetCurrentProcess(), site, 5) != 0;
    DWORD ignored = 0;
    return VirtualProtect(site, 5, old, &ignored) != 0 && flushed;
}

void __cdecl InitializeEnums() {
    // Description catalog already owns initialization, ordering, and map cleanup.
    Native<void (__cdecl*)()>(0x021E40)();
    try {
        for (const auto& record : g_registry->equipment) {
            char name[16]{};
            std::snprintf(name, sizeof(name), "MME_%06X", record.equipmentId);
            alignas(4) unsigned char nativeString[12]{};
            Native<void* (__thiscall*)(void*, const char*)>(0x23A220)(nativeString, name);
            Native<void (__thiscall*)(void*, void*, int)>(0x1CAC30)(
                Native<void*>(record.slot == 0 ? 0x3DF4F0 : 0x3DF510),
                nativeString, static_cast<int>(record.equipmentId));
            Native<void (__thiscall*)(void*)>(0x23A3D0)(nativeString);
        }
    } catch (...) {
        g_fatal("Private equipment enum registration failed at the stock description boundary.");
    }
}

void* __fastcall ConstructPresenter(void* self, void*) {
    auto* result = static_cast<unsigned char*>(
        Native<void* (__thiscall*)(void*)>(0x1038D0)(self));
    if (result == nullptr) {
        g_fatal("Stock equipment presenter construction returned null.");
        return nullptr;
    }
    try {
        for (const auto& record : g_registry->equipment) {
            // Each stock constructor acquires its own STRT reference. The stock
            // destructor releases all entries, including ours, on return to menu.
            const int key = static_cast<int>(record.equipmentId);
            void** name = Native<void** (__thiscall*)(void*, const int*)>(0x102B20)(
                result + (record.slot == 0 ? 0x20 : 0), &key);
            auto* icon = Native<std::uint32_t* (__thiscall*)(void*, const int*)>(0x102BD0)(
                result + (record.slot == 0 ? 0x40 : 0x60), &key);
            if (name == nullptr || icon == nullptr || *name != nullptr || *icon != 0) {
                g_fatal("Private equipment collided with an existing stock presentation entry.");
                return result;
            }
            *name = Native<void* (__cdecl*)(int, std::uint32_t)>(0x279A80)(0, record.nameTable);
            if (*name == nullptr) {
                g_fatal("Private equipment name resource is unavailable in the prepared profile.");
                return result;
            }
            *icon = record.equipmentId;
        }
    } catch (...) {
        g_fatal("Private equipment presentation registration failed at the stock construction boundary.");
    }
    return result;
}
}

bool InstallEquipmentRuntime(std::uintptr_t imageBase, bool beta2,
    const MajestyRuntimeFeatures::Registry& registry, void (*fatal)(const char*)) {
    if (registry.equipment.empty()) return true;
    if (!beta2 || !imageBase || !fatal || g_registry != nullptr) return false;
    g_base = imageBase;
    // Stock audit: only two CALL sites change. Entry bytes and embedded map
    // addresses are checked separately so ASLR relocations remain valid.
    if (!Call(0x021E15, 0x021E40) || !Call(0x103DC9, 0x1038D0) ||
        !Bytes(0x021E40, "\x6a\xff\x68", 3) || !Pointer(0x021E43, 0x2F52E0) ||
        !Bytes(0x021E64, "\xb9", 1) || !Pointer(0x021E65, 0x3DF4F0) ||
        !Call(0x021E69, 0x1CAAB0) || !Call(0x021E77, 0x23A220) ||
        !Call(0x021E90, 0x1CAC30) || !Call(0x021EA0, 0x23A3D0) ||
        !Bytes(0x1038D0, "\x6a\xff\x68", 3) || !Pointer(0x1038D3, 0x315449) ||
        !Bytes(0x103914, "\x8d\x77\x20", 3) ||
        !Bytes(0x103931, "\x8d\x6f\x40", 3) ||
        !Call(0x10397A, 0x102B20) || !Call(0x10398A, 0x279A80) ||
        !Bytes(0x1CAC30, "\x83\xec\x08\x53\x56\x57\x8b\x7c\x24\x18", 10) ||
        !Bytes(0x102B20, "\x8b\x54\x24\x04\x83\xec\x10\x53\x55\x57", 10) ||
        !Bytes(0x102BD0, "\x8b\x54\x24\x04\x83\xec\x10\x53\x55\x57", 10) ||
        !Bytes(0x23A220, "\x53\x8b\x5c\x24\x08\x56\x57\x8b\xf9", 9) ||
        !Bytes(0x23A3D0, "\x8b\x11\x85\xd2\x74\x1a\x8b\x41\x04", 9) ||
        !Call(0x279A80, 0x246620)) return false;
    g_registry = &registry;
    g_fatal = fatal;
    // The caller terminates the suspended launch if either write fails; no
    // partially installed game is allowed to resume.
    return RedirectCall(0x021E15, &InitializeEnums) && RedirectCall(0x103DC9, &ConstructPresenter);
}
