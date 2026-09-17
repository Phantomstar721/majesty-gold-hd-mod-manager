#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "MapQueryRuntime.h"
#include "BoundedMapQuery.h"
#include "MovementRate.h"
#include <cstring>
#include <limits>

namespace {
struct Profile {
    std::uintptr_t registrationCall, registration, engine, registerFunction;
    std::uintptr_t stringConstructor, stringDestructor, argumentAt;
    std::uintptr_t worldGlobal, boardExtents, nearestHidden, pathCost;
};
constexpr Profile kPublic = {
    0x198EE7, 0x1C0A10, 0x15EEF0, 0x16BCE0, 0x227A80, 0x227C30,
    0x2DDF0, 0x3C544C, 0x1BC9C0, 0x1BE9F0, 0x1BE7A0};
constexpr Profile kBeta = {
    0x1ADE97, 0x1D5BF0, 0x175030, 0x181CF0, 0x23A220, 0x23A3D0,
    0x2ED50, 0x3E3FD4, 0x1D1930, 0x1D3BD0, 0x1D3980};
std::uintptr_t g_base = 0;
const Profile* g_profile = nullptr;
bool g_mapQuery = false, g_movementQuery = false;

struct MovementProfile {
    std::uintptr_t changeType, resolveUnit, findDescription, descriptionsGlobal;
    std::uintptr_t baseInterval, effectiveInterval, packedAttribute, clockGlobal;
    std::uintptr_t step, movementConstructor, movementVtable, movementDerived;
};
constexpr MovementProfile kMovementPublic = {
    0x031BB0, 0x158B20, 0x1AE060, 0x3C5304,
    0x1BA0F0, 0x0479E0, 0x1B9FD0, 0x3C52D0,
    0x1CDE80, 0x202F50, 0x34A240, 0x203460};
constexpr MovementProfile kMovementBeta = {
    0x032B10, 0x16EC60, 0x1C3000, 0x3E3E8C,
    0x1CF090, 0x0488F0, 0x1CEF70, 0x3E3E58,
    0x1E3060, 0x218290, 0x364310, 0x2187A0};
const MovementProfile* g_movementProfile = nullptr;

template<class T> T Read(const void* base, std::size_t offset) {
    T value{};
    std::memcpy(&value, static_cast<const unsigned char*>(base) + offset, sizeof(T));
    return value;
}
bool Bytes(std::uintptr_t rva, const unsigned char* expected, std::size_t size) {
    return std::memcmp(reinterpret_cast<const void*>(g_base+rva), expected, size) == 0;
}
bool Call(std::uintptr_t rva, std::uintptr_t target) {
    const auto* site = reinterpret_cast<const unsigned char*>(g_base+rva);
    return site[0] == 0xE8 &&
        g_base+rva+5+Read<std::int32_t>(site, 1) == g_base+target;
}
void* const* __fastcall OptionalPathCostUnit(void* arguments, void*, unsigned index) {
    // Stock PathCost documents an optional unit, and its null-value branch
    // already selects the average unit. Both supported executables nevertheless
    // dereference slot 5 before that branch, even if GPL supplied only four
    // arguments. Supply the missing *value slot*, never a NullAgent object.
    // This borrowed read-only slot is consumed immediately by stock code; it is
    // not appended to the GPL collection and owns no agent or allocated memory.
    if (arguments != nullptr && index == 5) {
        const auto first = Read<std::uintptr_t>(arguments, 0x0C);
        const auto last = Read<std::uintptr_t>(arguments, 0x10);
        if (first != 0 && last >= first && last-first == 5*sizeof(void*)) {
            static void* const omittedUnit = nullptr;
            return &omittedUnit;
        }
    }
    // Explicit units, including their stock validity errors, are unchanged.
    // Do not turn missing required arguments into optional ones.
    using At = void** (__thiscall*)(void*, unsigned);
    return reinterpret_cast<At>(g_base+g_profile->argumentAt)(arguments, index);
}
bool RedirectCall(std::uintptr_t rva, const void* target) {
    auto* site = reinterpret_cast<unsigned char*>(g_base+rva);
    DWORD old = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    const auto delta = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(target)-reinterpret_cast<std::uintptr_t>(site)-5);
    std::memcpy(site+1, &delta, sizeof(delta));
    FlushInstructionCache(GetCurrentProcess(), site, 5);
    DWORD ignored = 0;
    return VirtualProtect(site, 5, old, &ignored) != 0;
}
void* Argument(void* arguments, unsigned index) {
    if (arguments == nullptr) return nullptr;
    const auto first = Read<std::uintptr_t>(arguments, 0x0C);
    const auto last = Read<std::uintptr_t>(arguments, 0x10);
    if (first == 0 || last < first || last-first > 16*sizeof(void*) ||
        (last-first)%sizeof(void*) != 0 || index >= (last-first)/sizeof(void*)) return nullptr;
    using At = void** (__thiscall*)(void*, unsigned);
    void** entry = reinterpret_cast<At>(g_base+g_profile->argumentAt)(arguments, index);
    return entry == nullptr ? nullptr : *entry;
}
int* Integer(void* arguments, unsigned index) {
    void* value = Argument(arguments, index);
    if (value == nullptr) return nullptr;
    // GPL argument variables are references; the stock accessor resolves
    // them. Its returned integer storage is also the in/out cursor storage.
    using Reference = int* (__thiscall*)(void*);
    auto** table = *static_cast<void***>(value);
    return reinterpret_cast<Reference>(table[0x28/4])(value);
}
MajestyMapQuery::Coordinate* Point(void* arguments, unsigned index) {
    void* value = Argument(arguments, index);
    if (value == nullptr) return nullptr;
    using Reference = void* (__thiscall*)(void*);
    void* coordinate = reinterpret_cast<Reference>((*static_cast<void***>(value))[0x58/4])(value);
    if (coordinate == nullptr) return nullptr;
    return reinterpret_cast<MajestyMapQuery::Coordinate*>(
        reinterpret_cast<Reference>((*static_cast<void***>(coordinate))[0x3C/4])(coordinate));
}
std::uint32_t TileMask(const void* map, int x, int y) {
    const auto stride = Read<std::uint32_t>(map, 0x40);
    const auto* tiles = Read<const unsigned char*>(map, 0x54);
    return Read<std::uint32_t>(tiles, (std::size_t(y)*stride+x)*0x18+4);
}
MajestyMapQuery::View CurrentMap() {
    const void* root = *reinterpret_cast<void**>(g_base+g_profile->worldGlobal);
    if (root == nullptr) return {};
    const void* world = Read<void*>(root, 0x10);
    if (world == nullptr) return {};
    const void* map = Read<void*>(world, 0x88);
    if (map == nullptr) return {};
    const int width = Read<int>(map, 0x38), height = Read<int>(map, 0x3C);
    const int stride = Read<int>(map, 0x40), rows = Read<int>(map, 0x44);
    if (width <= 0 || height <= 0 || stride < width || rows < height ||
        static_cast<std::uint64_t>(stride)*rows > std::numeric_limits<std::uint32_t>::max()/0x18 ||
        Read<void*>(map, 0x54) == nullptr) return {};
    return {map, &TileMask, width, height};
}
void __cdecl Fog(void* arguments) {
    int* result = Integer(arguments, 0);
    if (result == nullptr) return;
    *result = -1;
    const int* player = Integer(arguments, 1);
    const auto* point = Point(arguments, 2);
    if (player != nullptr && point != nullptr)
        *result = MajestyMapQuery::FogAt(CurrentMap(), *player, *point);
}
void __cdecl Frontier(void* arguments) {
    int* result = Integer(arguments, 0);
    if (result == nullptr) return;
    *result = -1;
    const int* player = Integer(arguments, 1);
    const auto* origin = Point(arguments, 2);
    int* cursor = Integer(arguments, 3);
    const int* budget = Integer(arguments, 4);
    auto* output = Point(arguments, 5);
    if (player != nullptr && origin != nullptr && cursor != nullptr &&
        budget != nullptr && output != nullptr) {
        // Copy inputs before mutating in/out arguments: GPL callers may alias them.
        const auto start = *origin;
        const int owner = *player, work = *budget;
        *result = static_cast<int>(MajestyMapQuery::NextFrontier(
            CurrentMap(), owner, start, *cursor, work, *output));
    }
}

int MovementQuantum() {
    const void* clock = *reinterpret_cast<void**>(g_base+g_movementProfile->clockGlobal);
    if (clock == nullptr) return MajestyMovement::kInvalidData;
    const int quantum = Read<int>(clock, 0x20);
    // Native Q16 conversion shifts the quantum into a signed 32-bit word.
    return quantum > 0 && quantum <= 32767 ? quantum : MajestyMovement::kInvalidData;
}
const void* LinearMovement(const void* descriptor) {
    if (descriptor == nullptr || Read<int>(descriptor, 8) != 1) return nullptr;
    const void* engine = Read<void*>(descriptor, 0x14);
    return engine != nullptr && Read<std::uintptr_t>(engine, 0) ==
        g_base+g_movementProfile->movementVtable ? engine : nullptr;
}
int UnitMovementRate(void* value, int mode) {
    using namespace MajestyMovement;
    if (value == nullptr || (mode != 0 && mode != 1)) return kInvalid;
    using Reference = void* (__thiscall*)(void*);
    void* reference = reinterpret_cast<Reference>((*static_cast<void***>(value))[0x5C/4])(value);
    if (reference == nullptr) return kInvalid;
    // The stock nonthrowing resolver writes only its disposable +0C cache.
    // Borrow the identity in a local reference, never retain a caller's handle.
    std::uint32_t temporary[4] = {};
    temporary[2] = Read<std::uint32_t>(reference, 8);
    void* unit = reinterpret_cast<Reference>(g_base+g_movementProfile->resolveUnit)(temporary);
    if (unit == nullptr) return kInvalid;
    const void* movement = LinearMovement(Read<void*>(unit, 0x54));
    if (movement == nullptr) return kUnsupported;
    const auto intervalMethod = Read<std::uintptr_t>(Read<void*>(unit, 0), 0x158);
    if (intervalMethod != g_base+g_movementProfile->effectiveInterval) return kUnsupported;
    const int quantum = MovementQuantum();
    if (quantum <= 0) return kInvalidData;
    int interval = NormalInterval(Read<int>(movement, 0x0C), quantum);
    if (interval <= 0) return kInvalidData;
    if (mode == 1) {
        using Attribute = int (__thiscall*)(void*, std::uint32_t, int);
        const int modifier = reinterpret_cast<Attribute>(g_base+g_movementProfile->packedAttribute)(
            unit, 0x22565041u, 0);
        const std::int64_t sum = static_cast<std::int64_t>(Read<int>(movement, 0x0C))+modifier;
        if (sum < std::numeric_limits<int>::min() ||
            sum > std::numeric_limits<int>::max()-quantum/2) return kInvalidData;
        using Interval = int (__thiscall*)(void*);
        interval = reinterpret_cast<Interval>(intervalMethod)(unit);
    }
    return Rate(Read<int>(movement, 0x10), interval);
}
int UnitTypeMovementRate(const char* name) {
    using namespace MajestyMovement;
    if (name == nullptr || *name == '\0') return kInvalid;
    void* registry = *reinterpret_cast<void**>(g_base+g_movementProfile->descriptionsGlobal);
    if (registry == nullptr) return kInvalid;
    using Find = void* (__thiscall*)(void*, const char*);
    const void* descriptor = reinterpret_cast<Find>(g_base+g_movementProfile->findDescription)(registry, name);
    if (descriptor == nullptr) return kInvalid;
    const int subtype = Read<int>(descriptor, 8);
    if (subtype < 1 || subtype > 3) return kUnsupported;
    const void* engine = Read<void*>(descriptor, 0x14);
    if (engine == nullptr) return kUnsupported;
    // Literal stock DUNT attachment traversal, not class-name special cases.
    for (unsigned i = 0; i < 8; ++i) {
        if (Read<std::uint32_t>(engine, 0xD4+i*12) != 1) continue;
        const void* movement = LinearMovement(Read<void*>(engine, 0xD4+i*12+8));
        if (movement == nullptr) return kUnsupported;
        const int quantum = MovementQuantum();
        if (quantum <= 0) return kInvalidData;
        const int interval = NormalInterval(Read<int>(movement, 0x0C), quantum);
        return Rate(Read<int>(movement, 0x10), interval);
    }
    return kUnsupported;
}
void __cdecl Movement(void* arguments) {
    int* result = Integer(arguments, 0);
    if (result == nullptr) return;
    void* value = Argument(arguments, 1);
    const int* mode = Integer(arguments, 2);
    *result = value != nullptr && mode != nullptr
        ? UnitMovementRate(value, *mode) : MajestyMovement::kInvalid;
}
void __cdecl TypeMovement(void* arguments) {
    int* result = Integer(arguments, 0);
    if (result == nullptr) return;
    *result = MajestyMovement::kInvalid;
    void* value = Argument(arguments, 1);
    if (value == nullptr) return;
    using String = const char** (__thiscall*)(void*);
    const char** name = reinterpret_cast<String>((*static_cast<void***>(value))[0x30/4])(value);
    if (name != nullptr) *result = UnitTypeMovementRate(*name);
}
bool ValidateMovementQuery() {
    const auto& p = *g_movementProfile;
    constexpr unsigned char interval[] = {0x8B,0x41,0x54,0x8B,0x48,0x14,0x8B,0x41,0x0C,0xC3};
    constexpr unsigned char modifier[] = {0x6A,0,0x68,0x41,0x50,0x56,0x22};
    constexpr unsigned char rounding[] = {0x8B,0x70,0x20,0x03,0xCF,0x3B,0xCE,0x7C,0x11,
        0x8B,0xC6,0x99,0x2B,0xC2,0xD1,0xF8,0x03,0xC1,0x99,0xF7,0xFE,0x0F,0xAF,0xC6,
        0x8B,0xC8,0x83,0xF9,1,0x5F,0x5E,0xB8,1,0,0,0,0x7E,2,0x8B,0xC1,0xC3};
    constexpr unsigned char step[] = {0x53,0x55,0x56,0x57,0x8B,0x7C,0x24,0x18,
        0x8B,0x47,0x54,0x8B,0x48,0x14,0x8B,0x41,0x10,0xC1,0xE0,0x10,
        0x68,0,0,0x20,0,0x50};
    constexpr unsigned char attachments[] = {0x8B,0x81,0x90,0,0,0,0x8B,0x48,8,
        0x83,0xF9,1,0x74,0x0A,0x83,0xF9,2,0x74,5,0x83,0xF9,3,0x75,0x1B,
        0x8B,0x40,0x14,0x8B,0x54,0x24,4,5,0xD4,0,0,0,0x33,0xC9,0x39,0x10,
        0x74,0x0E,0x41,0x83,0xC0,0x0C,0x83,0xF9,8,0x7C,0xF3,0x33,0xC0,
        0xC2,4,0,0x8B,0x40,8,0xC2,4,0};
    constexpr unsigned char resolveIdentity[] = {0x56,0x8B,0xF1,0x8B,0x46,8,0x50};
    constexpr unsigned char resolveDeleted[] = {0x89,0x46,0x0C,0x5E,0x85,0xC0,
        0x74,0x0D,0x80,0x78,0x38,0,0x75,7,0x8B,0xC8};
    constexpr unsigned char agentArgument[] = {0x8B,8,0x8B,1,0x8B,0x50,0x5C,0xFF,0xD2};
    constexpr unsigned char stringArgument[] = {0x8B,8,0x8B,1,0x8B,0x50,0x30,0xFF,0xD2};
    return Call(p.changeType+0x0E, g_profile->argumentAt) &&
        Bytes(p.changeType+0x13, agentArgument, sizeof(agentArgument)) &&
        Bytes(p.changeType+0x27, stringArgument, sizeof(stringArgument)) &&
        Call(p.changeType+0x34, p.resolveUnit) && Call(p.changeType+0x69, p.findDescription) &&
        Bytes(p.resolveUnit, resolveIdentity, sizeof(resolveIdentity)) &&
        Bytes(p.resolveUnit+0x13, resolveDeleted, sizeof(resolveDeleted)) &&
        Call(p.resolveUnit+7, g_profile->engine) &&
        Read<std::uintptr_t>(reinterpret_cast<void*>(g_base+p.changeType), 0x64) == g_base+p.descriptionsGlobal &&
        Bytes(p.baseInterval, interval, sizeof(interval)) &&
        Bytes(p.baseInterval-0xE0, attachments, sizeof(attachments)) &&
        Call(p.effectiveInterval+4, p.baseInterval) && Bytes(p.effectiveInterval+9, modifier, sizeof(modifier)) &&
        Call(p.effectiveInterval+0x14, p.packedAttribute) &&
        Read<std::uintptr_t>(reinterpret_cast<void*>(g_base+p.effectiveInterval), 0x1C) == g_base+p.clockGlobal &&
        Bytes(p.effectiveInterval+0x20, rounding, sizeof(rounding)) && Bytes(p.step, step, sizeof(step)) &&
        Read<std::uintptr_t>(reinterpret_cast<void*>(g_base+p.movementConstructor), 0x35) == g_base+p.movementVtable &&
        Read<std::uintptr_t>(reinterpret_cast<void*>(g_base+p.movementVtable), 0x0C) == g_base+p.movementDerived;
}
void Register(const char* name, void (__cdecl* callback)(void*)) {
    using Construct = void* (__thiscall*)(void*, const char*);
    using Destroy = void (__thiscall*)(void*);
    using Engine = void* (__cdecl*)();
    using Function = void (__thiscall*)(void*, const void*, void*, int, int, int);
    std::uint32_t text[3] = {};
    reinterpret_cast<Construct>(g_base+g_profile->stringConstructor)(text, name);
    void* engine = reinterpret_cast<Engine>(g_base+g_profile->engine)();
    reinterpret_cast<Function>(g_base+g_profile->registerFunction)(
        Read<void*>(engine, 8), text, reinterpret_cast<void*>(callback), 1, 0, 0);
    reinterpret_cast<Destroy>(g_base+g_profile->stringDestructor)(text);
}
void __cdecl RegisterAfterStock() {
    reinterpret_cast<void (__cdecl*)()>(g_base+g_profile->registration)();
    if (g_mapQuery) {
        Register("MM_MapFog", &Fog);
        Register("MM_MapNextFrontier", &Frontier);
    }
    if (g_movementQuery) {
        Register("MM_UnitMovementRate", &Movement);
        Register("MM_UnitTypeMovementRate", &TypeMovement);
    }
}
}

bool InstallMapQueryRuntime(std::uintptr_t imageBase, bool publicBuild,
                           bool mapQuery, bool movementQuery) {
    if (!mapQuery && !movementQuery) return true;
    g_base = imageBase;
    g_profile = publicBuild ? &kPublic : &kBeta;
    g_movementProfile = publicBuild ? &kMovementPublic : &kMovementBeta;
    g_mapQuery = mapQuery;
    g_movementQuery = movementQuery;
    // Pin the stock registration boundary and field accesses on both audited
    // builds. A different build is not permitted to guess its map layout.
    constexpr unsigned char extents[] = {0x8B,0x48,0x10,0x8B,0x81,0x88,0,0,0,
        0xDB,0x40,0x38,0x8D,0x4C,0x24,0x10,0xD9,0x5C,0x24,4,0xDB,0x40,0x3C};
    constexpr unsigned char nativeMap[] = {0x8B,0x8E,0x94,0,0,0,0x8B,0x91,0x88,0,0,0};
    constexpr unsigned char optionalUnitLookup[] = {0x6A,0x05,0x8B,0xCE,0x8B,0xE8};
    constexpr unsigned char optionalUnitRead[] = {0x8B,0x00,0x8B,0x4C,0x24,0x1C};
    constexpr unsigned char averageUnitDefault[] = {0xC7,0x44,0x24,0x24,0,0,0,0};
    constexpr unsigned char averageUnitBranch[] = {0x8B,0x4C,0x24,0x24,0x85,0xC9,0x74,0x5F};
    if (movementQuery && !ValidateMovementQuery()) return false;
    if (!Call(g_profile->registrationCall, g_profile->registration) ||
        !Call(g_profile->registration+0x7F1, g_profile->stringConstructor) ||
        !Call(g_profile->registration+0x800, g_profile->engine) ||
        !Call(g_profile->registration+0x814, g_profile->registerFunction) ||
        !Call(g_profile->registration+0x821, g_profile->stringDestructor) ||
        (mapQuery && (!Call(g_profile->nearestHidden+0x2F, g_profile->argumentAt) ||
        !Bytes(g_profile->pathCost+0x7B, optionalUnitLookup, sizeof(optionalUnitLookup)) ||
        !Call(g_profile->pathCost+0x81, g_profile->argumentAt) ||
        !Bytes(g_profile->pathCost+0x86, optionalUnitRead, sizeof(optionalUnitRead)) ||
        !Bytes(g_profile->pathCost+0x95, averageUnitDefault, sizeof(averageUnitDefault)) ||
        !Bytes(g_profile->pathCost+0x128, averageUnitBranch, sizeof(averageUnitBranch)) ||
        !Bytes(g_profile->boardExtents+0x1A, extents, sizeof(extents)) ||
        !Bytes(g_profile->nearestHidden+0x6F, nativeMap, sizeof(nativeMap)) ||
        Read<std::uint32_t>(reinterpret_cast<void*>(imageBase+g_profile->boardExtents), 6)
            != imageBase+g_profile->worldGlobal))) return false;
    return (!mapQuery || RedirectCall(g_profile->pathCost+0x81,
                        reinterpret_cast<const void*>(&OptionalPathCostUnit))) &&
        RedirectCall(g_profile->registrationCall,
                     reinterpret_cast<const void*>(&RegisterAfterStock));
}
