#pragma once

#include "MajestyBuildId.h"
#include "PrivateRecruitmentProfiles.h"
#include <windows.h>
#include <cstring>

// Private, literal copies of the stock presenters. Never patch stock AP52 or
// replace recruitment/upgrade orders. See docs/stock-ap52-private-recruitment.md.
namespace MajestyPrivateRecruitment {

static std::uintptr_t imageBase = 0;
static const std::uint32_t* helpers = nullptr;
using Presenter = void (__thiscall*)(void*);
using Tooltip = bool (__thiscall*)(void*, std::uint32_t, std::uint32_t, void*);

inline void RefreshCapacityChange(void* controller, std::uint32_t notification) {
    if (notification != 0x00425041u) return; // native MaxGuildMembers
    // Literal AP52 building-change refresh order. Its stock event switch does
    // not cover a GPL capacity correction made after description initialization.
    // Re-enter the installed slots, not the clones directly: an opener keeps
    // its rows hidden, a child suppresses counts, and research retains its gate.
    auto** table = *static_cast<void***>(controller);
    reinterpret_cast<Presenter>(table[13])(controller);
    reinterpret_cast<Presenter>(table[16])(controller);
}

inline std::uint32_t Fingerprint(const unsigned char* bytes, const Code& code) {
    std::uint32_t hash = 2166136261u;
    std::size_t relocation = 0;
    for (std::size_t i = 0; i < code.size; ++i) {
        while (relocation < code.relocationCount &&
               i >= code.relocations[relocation] + 4) ++relocation;
        const bool masked = relocation < code.relocationCount &&
            i >= code.relocations[relocation];
        hash = (hash ^ (masked ? 0u : bytes[i])) * 16777619u;
    }
    return hash;
}

inline const Code* Profile(MajestyBuildId buildId) {
    switch (buildId) {
    case MajestyBuildId::SteamPublic: return kPublic;
    case MajestyBuildId::SteamBeta2: return kBeta;
    case MajestyBuildId::Gog: return kGog;
    default: return nullptr;
    }
}
inline bool Validate(std::uintptr_t base, MajestyBuildId buildId) {
    const auto* profile = Profile(buildId);
    if (profile == nullptr) return false;
    for (std::size_t index = 0; index < sizeof(kPublic) / sizeof(kPublic[0]); ++index) {
        const auto& code = profile[index];
        const auto* source = reinterpret_cast<const unsigned char*>(base + code.rva);
        if (Fingerprint(source, code) != code.hash) return false;
        for (std::size_t i = 0; i < code.branchCount; ++i) {
            const auto& branch = code.branches[i];
            std::int32_t relative = 0;
            std::memcpy(&relative, source + branch.offset + 1, 4);
            if ((source[branch.offset] != 0xE8 && source[branch.offset] != 0xE9) ||
                base + code.rva + branch.offset + 5 + relative != base + branch.targetRva)
                return false;
        }
    }
    return true;
}

template <unsigned Index> std::uint32_t __cdecl Produced(void* unit, unsigned) {
    using Fn = std::uint32_t (__cdecl*)(void*, unsigned);
    return reinterpret_cast<Fn>(imageBase + helpers[0])(unit, Index);
}
template <unsigned Index> void __fastcall Name(void* controller, void*, unsigned, void* text) {
    using Fn = void (__thiscall*)(void*, unsigned, void*);
    reinterpret_cast<Fn>(imageBase + helpers[1])(controller, Index, text);
}
template <unsigned Index> bool __fastcall Quote(void* controller, void*, unsigned, int* price) {
    using Fn = bool (__thiscall*)(void*, unsigned, int*);
    return reinterpret_cast<Fn>(imageBase + helpers[2])(controller, Index, price);
}
template <unsigned Index> bool __fastcall Affordable(void* controller, void*, unsigned) {
    using Fn = bool (__thiscall*)(void*, unsigned);
    return reinterpret_cast<Fn>(imageBase + helpers[3])(controller, Index);
}
template <unsigned Index> void __fastcall TooltipPrice(void* controller, void*, void* text, unsigned) {
    using Fn = void (__thiscall*)(void*, void*, unsigned);
    reinterpret_cast<Fn>(imageBase + helpers[4])(controller, text, Index);
}
inline void __fastcall ThreeCounts(void*, void*, std::uint32_t* first, std::uint32_t* second) {
    *first = 1;
    *second = 1;
}
inline void __fastcall NoCallToArms(void*, void*) {}

template <unsigned Index> std::uintptr_t Replacement(unsigned role) {
    switch (role) {
    case 1: return reinterpret_cast<std::uintptr_t>(static_cast<std::uint32_t (__cdecl*)(void*, unsigned)>(&Produced<Index>));
    case 2: return reinterpret_cast<std::uintptr_t>(static_cast<void (__fastcall*)(void*, void*, unsigned, void*)>(&Name<Index>));
    case 3: return reinterpret_cast<std::uintptr_t>(static_cast<bool (__fastcall*)(void*, void*, unsigned, int*)>(&Quote<Index>));
    case 4: return reinterpret_cast<std::uintptr_t>(static_cast<bool (__fastcall*)(void*, void*, unsigned)>(&Affordable<Index>));
    case 5: return reinterpret_cast<std::uintptr_t>(static_cast<void (__fastcall*)(void*, void*, void*, unsigned)>(&TooltipPrice<Index>));
    case 6: return reinterpret_cast<std::uintptr_t>(&ThreeCounts);
    case 7: return reinterpret_cast<std::uintptr_t>(&NoCallToArms);
    default: return 0;
    }
}

template <unsigned Index> void* Clone(const Code& code, std::uint32_t command, std::uint32_t price) {
    auto* copy = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, code.size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (copy == nullptr) return nullptr;
    std::memcpy(copy, reinterpret_cast<const void*>(imageBase + code.rva), code.size);
    for (std::size_t i = 0; i < code.branchCount; ++i) {
        const auto& branch = code.branches[i];
        const auto replacement = Replacement<Index>(branch.role);
        const auto target = replacement ? replacement : imageBase + branch.targetRva;
        const auto relative = static_cast<std::int32_t>(target -
            (reinterpret_cast<std::uintptr_t>(copy) + branch.offset + 5));
        std::memcpy(copy + branch.offset + 1, &relative, 4);
    }
    for (std::size_t i = 0; i < code.controlCount; ++i) {
        const auto& control = code.controls[i];
        const auto value = control.id == 0x1F48u ? command : price;
        std::memcpy(copy + control.offset, &value, 4);
    }
    DWORD oldProtection = 0;
    if (!VirtualProtect(copy, code.size, PAGE_EXECUTE_READ, &oldProtection)) {
        VirtualFree(copy, 0, MEM_RELEASE);
        return nullptr;
    }
    FlushInstructionCache(GetCurrentProcess(), copy, code.size);
    return copy;
}

struct Presenters {
    void* recruit[3] = {};
    void* tooltip[3] = {};
    void* count = nullptr;
    void* setup = nullptr;
    void* event = nullptr;

    Presenters() = default;
    Presenters(const Presenters&) = delete;
    Presenters& operator=(const Presenters&) = delete;
    ~Presenters() {
        for (void* code : recruit) if (code) VirtualFree(code, 0, MEM_RELEASE);
        for (void* code : tooltip) if (code) VirtualFree(code, 0, MEM_RELEASE);
        for (void* code : {count, setup, event}) if (code) VirtualFree(code, 0, MEM_RELEASE);
    }
    bool Initialize(std::uintptr_t base, MajestyBuildId buildId, std::uint32_t thirdPrice) {
        if (recruit[0] != nullptr || thirdPrice <= 0x22CEu || !Validate(base, buildId)) return false;
        imageBase = base;
        switch (buildId) {
        case MajestyBuildId::SteamPublic: helpers = kPublicHelpers; break;
        case MajestyBuildId::SteamBeta2: helpers = kBetaHelpers; break;
        case MajestyBuildId::Gog: helpers = kGogHelpers; break;
        default: return false;
        }
        const auto* profile = Profile(buildId);
        recruit[0] = Clone<0>(profile[0], 0x1F48u, 0x1752u);
        recruit[1] = Clone<1>(profile[0], 0x1389u, 0x1F51u);
        recruit[2] = Clone<2>(profile[0], 0x1388u, thirdPrice);
        tooltip[0] = Clone<0>(profile[1], 0x1F48u, 0x1752u);
        tooltip[1] = Clone<1>(profile[1], 0x1389u, 0x1F51u);
        tooltip[2] = Clone<2>(profile[1], 0x1388u, thirdPrice);
        count = Clone<0>(profile[2], 0, 0);
        setup = Clone<0>(profile[3], 0, 0);
        event = Clone<0>(profile[4], 0, 0);
        return recruit[0] && recruit[1] && recruit[2] &&
            tooltip[0] && tooltip[1] && tooltip[2] && count && setup && event;
    }
    void Refresh(void* controller) const {
        for (auto code : recruit) reinterpret_cast<Presenter>(code)(controller);
    }
    bool Describe(void* controller, std::uint32_t command, std::uint32_t a2, void* text) const {
        const auto index = command == 0x1388u ? 2 : command == 0x1389u ? 1 : 0;
        return reinterpret_cast<Tooltip>(tooltip[index])(controller, command, a2, text);
    }
};
}  // namespace MajestyPrivateRecruitment
