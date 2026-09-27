#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstring>
#include "EquipmentRuntime.h"
#include "FeatureParityProfiles.h"

namespace {
using Site = MajestyFeatureParity::Site;
MajestyBuildId g_equipmentBuild = MajestyBuildId::SteamBeta2;
std::uintptr_t Rva(Site site) { return MajestyFeatureParity::Rva(g_equipmentBuild,site); }
std::uintptr_t g_base = 0;
const MajestyRuntimeFeatures::Registry* g_registry = nullptr;
void (*g_fatal)(const char*) = nullptr;

template<class T> T Native(std::uintptr_t rva) {
    return reinterpret_cast<T>(g_base + rva);
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
    Native<void (__cdecl*)()>(Rva(Site::EnumInit))();
    try {
        for (const auto& record : g_registry->equipment) {
            char name[16]{};
            std::snprintf(name, sizeof(name), "MME_%06X", record.equipmentId);
            alignas(4) unsigned char nativeString[12]{};
            Native<void* (__thiscall*)(void*, const char*)>(Rva(Site::StringCtor))(nativeString, name);
            Native<void (__thiscall*)(void*, void*, int)>(Rva(Site::EnumInsert))(
                Native<void*>(record.slot == 0 ? Rva(Site::WeaponMap) : Rva(Site::ArmorMap)),
                nativeString, static_cast<int>(record.equipmentId));
            Native<void (__thiscall*)(void*)>(Rva(Site::StringDtor))(nativeString);
        }
    } catch (...) {
        g_fatal("Private equipment enum registration failed at the stock description boundary.");
    }
}

void* __fastcall ConstructPresenter(void* self, void*) {
    auto* result = static_cast<unsigned char*>(
        Native<void* (__thiscall*)(void*)>(Rva(Site::EquipmentCtor))(self));
    if (result == nullptr) {
        g_fatal("Stock equipment presenter construction returned null.");
        return nullptr;
    }
    try {
        for (const auto& record : g_registry->equipment) {
            // Each stock constructor acquires its own STRT reference. The stock
            // destructor releases all entries, including ours, on return to menu.
            const int key = static_cast<int>(record.equipmentId);
            void** name = Native<void** (__thiscall*)(void*, const int*)>(Rva(Site::NameInsert))(
                result + (record.slot == 0 ? 0x20 : 0), &key);
            auto* icon = Native<std::uint32_t* (__thiscall*)(void*, const int*)>(Rva(Site::IconInsert))(
                result + (record.slot == 0 ? 0x40 : 0x60), &key);
            if (name == nullptr || icon == nullptr || *name != nullptr || *icon != 0) {
                g_fatal("Private equipment collided with an existing stock presentation entry.");
                return result;
            }
            *name = Native<void* (__cdecl*)(int, std::uint32_t)>(Rva(Site::ResourceAcquire))(0, record.nameTable);
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

bool InstallEquipmentRuntime(std::uintptr_t imageBase, MajestyBuildId build,
    const MajestyRuntimeFeatures::Registry& registry, void (*fatal)(const char*)) {
    if (registry.equipment.empty()) return true;
    if (MajestyFeatureParity::Index(build) < 0 || !imageBase || !fatal || g_registry != nullptr) return false;
    g_base = imageBase;
    g_equipmentBuild = build;
    // Exact native construction/insertion/cleanup bodies for this executable.
    if (!MajestyFeatureParity::Validate(g_base,build,MajestyFeatureParity::Feature::Equipment) ||
        !Call(Rva(Site::EnumCall),Rva(Site::EnumInit)) ||
        !Call(Rva(Site::EquipmentCall),Rva(Site::EquipmentCtor)) ||
        !Pointer(Rva(Site::EnumInit)+0x25,Rva(Site::WeaponMap)) ||
        !Pointer(Rva(Site::EnumInit)+0x23A,Rva(Site::ArmorMap))) return false;
    g_registry = &registry;
    g_fatal = fatal;
    // The caller terminates the suspended launch if either write fails; no
    // partially installed game is allowed to resume.
    return RedirectCall(Rva(Site::EnumCall), &InitializeEnums) && RedirectCall(Rva(Site::EquipmentCall), &ConstructPresenter);
}
