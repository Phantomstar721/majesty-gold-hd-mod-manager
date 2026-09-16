#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "MapQueryRuntime.h"
#include "BoundedMapQuery.h"
#include <cstring>
#include <limits>

namespace {
struct Profile {
    std::uintptr_t registrationCall, registration, engine, registerFunction;
    std::uintptr_t stringConstructor, stringDestructor, argumentAt;
    std::uintptr_t worldGlobal, boardExtents, nearestHidden;
};
constexpr Profile kPublic = {
    0x198EE7, 0x1C0A10, 0x15EEF0, 0x16BCE0, 0x227A80, 0x227C30,
    0x2DDF0, 0x3C544C, 0x1BC9C0, 0x1BE9F0};
constexpr Profile kBeta = {
    0x1ADE97, 0x1D5BF0, 0x175030, 0x181CF0, 0x23A220, 0x23A3D0,
    0x2ED50, 0x3E3FD4, 0x1D1930, 0x1D3BD0};
std::uintptr_t g_base = 0;
const Profile* g_profile = nullptr;

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
    Register("MM_MapFog", &Fog);
    Register("MM_MapNextFrontier", &Frontier);
}
}

bool InstallMapQueryRuntime(std::uintptr_t imageBase, bool publicBuild) {
    g_base = imageBase;
    g_profile = publicBuild ? &kPublic : &kBeta;
    // Pin the stock registration boundary and field accesses on both audited
    // builds. A different build is not permitted to guess its map layout.
    constexpr unsigned char extents[] = {0x8B,0x48,0x10,0x8B,0x81,0x88,0,0,0,
        0xDB,0x40,0x38,0x8D,0x4C,0x24,0x10,0xD9,0x5C,0x24,4,0xDB,0x40,0x3C};
    constexpr unsigned char nativeMap[] = {0x8B,0x8E,0x94,0,0,0,0x8B,0x91,0x88,0,0,0};
    if (!Call(g_profile->registrationCall, g_profile->registration) ||
        !Call(g_profile->registration+0x7F1, g_profile->stringConstructor) ||
        !Call(g_profile->registration+0x800, g_profile->engine) ||
        !Call(g_profile->registration+0x814, g_profile->registerFunction) ||
        !Call(g_profile->registration+0x821, g_profile->stringDestructor) ||
        !Call(g_profile->nearestHidden+0x2F, g_profile->argumentAt) ||
        !Bytes(g_profile->boardExtents+0x1A, extents, sizeof(extents)) ||
        !Bytes(g_profile->nearestHidden+0x6F, nativeMap, sizeof(nativeMap)) ||
        Read<std::uint32_t>(reinterpret_cast<void*>(imageBase+g_profile->boardExtents), 6)
            != imageBase+g_profile->worldGlobal) return false;
    auto* site = reinterpret_cast<unsigned char*>(imageBase+g_profile->registrationCall);
    DWORD old = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    const auto delta = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&RegisterAfterStock)-reinterpret_cast<std::uintptr_t>(site)-5);
    std::memcpy(site+1, &delta, sizeof(delta));
    FlushInstructionCache(GetCurrentProcess(), site, 5);
    DWORD ignored = 0;
    return VirtualProtect(site, 5, old, &ignored) != 0;
}
