#include "../runtime/BoundedMapQuery.cpp"
#include "../runtime/MapQueryRuntime.cpp"
#include <cassert>
#include <cstdio>
#include <set>
#include <vector>
using namespace MajestyMapQuery;
struct Grid {
    int width, height; mutable int reads = 0; std::vector<std::uint32_t> cells;
    mutable std::vector<int> visited;
};
std::uint32_t Mask(const void* context, int x, int y) {
    const auto& grid = *static_cast<const Grid*>(context);
    assert(x >= 0 && y >= 0 && x < grid.width && y < grid.height);
    ++grid.reads;
    grid.visited.push_back(y*grid.width+x);
    return grid.cells[y*grid.width+x];
}
// Literal first-orientation native rectangle loops, including stock's
// clamped/padded borders. Filter repeated/padded cells for the unique-query
// contract. This oracle intentionally uses no production Ring/Covered code.
std::vector<int> StockFirstVisits(int width, int height, int ox, int oy) {
    std::vector<int> result;
    std::set<int> seen;
    auto visit = [&](int x, int y) {
        if (x < width && y < height && seen.insert(y*width+x).second)
            result.push_back(y*width+x);
    };
    for (int r = 0; result.size() < static_cast<unsigned>(width*height); ++r) {
        const int left = std::max(0,ox-r), top = std::max(0,oy-r);
        const int right = std::min(width,ox+1+r), bottom = std::min(height,oy+1+r);
        int x = left, y = top;
        for (; x < right; ++x) visit(x,y);
        for (; y < bottom; ++y) visit(x,y);
        for (; x > left; --x) visit(x,y);
        for (; y > top; --y) visit(x,y);
    }
    return result;
}
struct SparseGrid { mutable int reads = 0; std::vector<Coordinate> hidden; };
std::uint32_t SparseMask(const void* context, int x, int y) {
    auto& grid = *static_cast<const SparseGrid*>(context);
    ++grid.reads;
    for (const auto point : grid.hidden) if (point.x == x && point.y == y) return 0;
    return 1;
}
std::uint32_t HiddenMask(const void* context, int, int) {
    ++static_cast<const SparseGrid*>(context)->reads;
    return 0;
}
void VerifyOutwardTraversal() {
    for (int w = 1; w <= 8; ++w) for (int h = 1; h <= 8; ++h)
    for (int ox = 0; ox < w; ++ox) for (int oy = 0; oy < h; ++oy) {
        Grid grid{w,h,0,std::vector<std::uint32_t>(w*h,1)};
        View map{&grid,&Mask,w,h}; Coordinate out{999,999}; int cursor = 0;
        const auto expected = StockFirstVisits(w,h,ox,oy);
        while (cursor < w*h) {
            // Vary boundaries, including stopping in the middle of a side.
            const int budget = 1+cursor%7;
            int work = 0, before = cursor;
            const auto status = NextFrontier(map,0,{ox*32,oy*32},cursor,budget,out,&work);
            assert(work == cursor-before && work <= budget);
            assert(status == (cursor == w*h ? SearchStatus::Complete : SearchStatus::Exhausted));
        }
        if (grid.visited != expected) {
            std::fprintf(stderr,"Traversal differs: %dx%d origin %d,%d\nActual:",w,h,ox,oy);
            for (const auto id : grid.visited) std::fprintf(stderr," %d",id);
            std::fprintf(stderr,"\nStock:");
            for (const auto id : expected) std::fprintf(stderr," %d",id);
            std::fprintf(stderr,"\n");
        }
        assert(grid.visited == expected && grid.reads == w*h && out.x == 999);
        // Resume each possible ordinal directly, not just sequential calls.
        for (int ordinal = 0; ordinal < w*h; ++ordinal) {
            cursor = ordinal; grid.visited.clear();
            NextFrontier(map,0,{ox*32,oy*32},cursor,1,out);
            assert(grid.visited == std::vector<int>({expected[ordinal]}));
        }
    }
    // Huge map: an adjacent frontier above the origin must beat a faraway
    // frontier on the origin's horizontal row, within a single small budget.
    SparseGrid sparse{0,{{500000,499},{500200,500}}};
    View huge{&sparse,&SparseMask,1000000,1000};
    Coordinate out{}; int cursor = 0, work = 0;
    assert(NextFrontier(huge,0,{500000*32,500*32},cursor,8,out,&work) == SearchStatus::Found);
    assert(out.x == 500000*32+16 && out.y == 499*32+16 && work == 6 && sparse.reads <= work*5);
    // Caller-imposed eight-attempt limit does not turn budget exhaustion into
    // completion, or trigger any exhaustive scan on a wholly hidden map.
    View hidden{&sparse,&HiddenMask,1000000,1000}; cursor = 0;
    const auto unchanged = out;
    for (int attempt = 0; attempt < 8; ++attempt) {
        sparse.reads = 0;
        assert(NextFrontier(hidden,0,{500000*32,500*32},cursor,256,out,&work) == SearchStatus::Exhausted);
        assert(work == 256 && sparse.reads <= 1280 && cursor == (attempt+1)*256);
        assert(out.x == unchanged.x && out.y == unchanged.y);
    }
    // No allocation, tile replay, overflow, or skinny-map skip loop when
    // resuming near the largest legal ordinal/dimension.
    sparse.hidden.clear(); sparse.reads = 0;
    View largestDimension{&sparse,&SparseMask,0x7fffffff/32,1};
    cursor = largestDimension.width-1;
    assert(NextFrontier(largestDimension,0,{0,0},cursor,1,out,&work) == SearchStatus::Complete);
    assert(work == 1 && sparse.reads == 1);
    View largestArea{&sparse,&SparseMask,46340,46340};
    cursor = largestArea.width*largestArea.height-1; sparse.reads = 0;
    assert(NextFrontier(largestArea,0,{23170*32,23170*32},cursor,1,out,&work) == SearchStatus::Complete);
    assert(work == 1 && sparse.reads == 1);
}
namespace NativeTest {
struct Value { void** table; int type, x, y; };
struct Args { void* owner; int pad[2]; void*** first; void*** end; };
int* __fastcall AsInt(void* object, void*) { return &static_cast<Value*>(object)->x; }
void* __fastcall AsPoint(void* object, void*) { return object; }
void* __fastcall PointData(void* object, void*) { return &static_cast<Value*>(object)->x; }
void** __fastcall At(void* args, void*, unsigned index) { return static_cast<Args*>(args)->first[index]; }
int optionalAtCalls = 0;
void* suppliedUnit = reinterpret_cast<void*>(0x12345678u);
void** __fastcall OptionalAt(void*, void*, unsigned) {
    ++optionalAtCalls;
    return &suppliedUnit;
}
void VerifyOptionalPathCostUnit() {
    Profile profile = kBeta;
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&OptionalAt);
    g_base = 0; g_profile = &profile;
    // Put the omitted sixth slot in a no-access page: this mirrors the dump's
    // five-entry argument collection and catches any out-of-bounds lookup.
    SYSTEM_INFO system{};
    GetSystemInfo(&system);
    auto* pages = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 2*system.dwPageSize, MEM_RESERVE|MEM_COMMIT, PAGE_READWRITE));
    assert(pages != nullptr);
    DWORD old = 0;
    assert(VirtualProtect(pages+system.dwPageSize, system.dwPageSize, PAGE_NOACCESS, &old));
    auto** entries = reinterpret_cast<void***>(pages+system.dwPageSize)-5;
    for (int i = 0; i < 5; ++i) entries[i] = &suppliedUnit;
    Args args{nullptr,{},entries,entries+5};
    const Args original = args;
    for (int repeat = 0; repeat < 100; ++repeat) {
        void* const* result = OptionalPathCostUnit(&args, nullptr, 5);
        assert(result != nullptr && *result == nullptr && optionalAtCalls == 0);
        assert(std::memcmp(&args, &original, sizeof(args)) == 0);
    }
    // The x86 call site is __thiscall (ECX + one callee-popped argument).
    using StockAt = void* const* (__thiscall*)(void*, unsigned);
    auto at = reinterpret_cast<StockAt>(&OptionalPathCostUnit);
    assert(*at(&args, 5) == nullptr && optionalAtCalls == 0);
    // Required slots and malformed/other arities keep the original accessor.
    assert(at(&args, 4) == &suppliedUnit && optionalAtCalls == 1);
    args.end = args.first+4;
    assert(at(&args, 5) == &suppliedUnit && optionalAtCalls == 2);
    args.end = args.first;
    assert(at(&args, 5) == &suppliedUnit && optionalAtCalls == 3);
    args.first = nullptr;
    assert(at(&args, 5) == &suppliedUnit && optionalAtCalls == 4);
    assert(at(nullptr, 5) == &suppliedUnit && optionalAtCalls == 5);
    assert(VirtualFree(pages, 0, MEM_RELEASE));
    // With an explicit slot, return precisely what stock returns. A supplied
    // NullAgent object is not rewritten to the omitted-unit default either.
    void** full[6] = {};
    args = {nullptr,{},full,full+6};
    assert(at(&args, 5) == &suppliedUnit && *at(&args, 5) == suppliedUnit);
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&At);
    full[5] = &suppliedUnit;
    assert(at(&args, 5) == full[5]);
    void* explicitNull = nullptr;
    full[5] = &explicitNull;
    assert(at(&args, 5) == &explicitNull && *at(&args, 5) == nullptr);
    g_profile = nullptr;
}
template<class T> void Put(void* memory, int offset, T value) {
    std::memcpy(static_cast<unsigned char*>(memory)+offset, &value, sizeof(value));
}
void Run() {
    void* table[24] = {};
    table[0x28/4] = reinterpret_cast<void*>(&AsInt);
    table[0x58/4] = reinterpret_cast<void*>(&AsPoint);
    table[0x3C/4] = reinterpret_cast<void*>(&PointData);
    Value values[6] = {{table,1,0,0},{table,1,0,0},{table,7,0,0},
                       {table,1,0,0},{table,1,1,0},{table,7,999,999}};
    void* objects[6]; void** entries[6];
    for (int i = 0; i < 6; ++i) { objects[i] = &values[i]; entries[i] = &objects[i]; }
    Args args{nullptr,{},entries,entries+6};
    unsigned char root[0x14] = {}, world[0x8C] = {}, map[0x58] = {}, tiles[72] = {};
    void* current = root;
    Put(root,0x10,static_cast<void*>(world)); Put(world,0x88,static_cast<void*>(map));
    Put(map,0x38,3); Put(map,0x3C,1); Put(map,0x40,3); Put(map,0x44,1);
    Put(map,0x54,static_cast<void*>(tiles)); Put(tiles,4,1u);
    Profile profile = kBeta;
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&At);
    profile.worldGlobal = reinterpret_cast<std::uintptr_t>(&current);
    g_base = 0; g_profile = &profile;
    Fog(&args); assert(values[0].x == 1);
    Frontier(&args);
    assert(values[0].x == 0 && values[3].x == 1 && values[5].x == 999);
    Frontier(&args);
    assert(values[0].x == 1 && values[3].x == 2 && values[5].x == 48 && values[5].y == 16);
    Frontier(&args); assert(values[0].x == 2 && values[3].x == 3);
    values[3].x = 0; current = nullptr;
    Frontier(&args); assert(values[0].x == -1 && values[3].x == 0);
    Fog(&args); assert(values[0].x == -1);
    args.end = args.first+2; // arity failure cannot read nonexistent arguments
    Fog(&args); assert(values[0].x == -1);
}
}
#include "MovementQueryTests.h"
#include "NativeTimingTests.h"
int main() {
    MovementTest::Run();
    TimingTest::Run();
    VerifyOutwardTraversal();
    NativeTest::VerifyOptionalPathCostUnit();
    NativeTest::Run();
    Grid grid{7, 5, 0, std::vector<std::uint32_t>(35)};
    View map{&grid, &Mask, 7, 5};
    Coordinate out{999,999}; int cursor = 0, work = -1;
    assert(FogAt(map, 0, {-1,0}) == -1 && grid.reads == 0);
    assert(FogAt(map, 0, {224,0}) == -1 && grid.reads == 0);
    assert(FogAt(map, 32, {0,0}) == -1 && grid.reads == 0);
    assert(NextFrontier(map, 0, {0,0}, cursor, 257, out) == SearchStatus::Invalid);
    assert(cursor == 0 && grid.reads == 0 && out.x == 999);
    assert(NextFrontier(map, 0, {0,0}, cursor, 3, out, &work) == SearchStatus::Exhausted);
    assert(cursor == 3 && work == 3 && grid.reads <= 15 && out.x == 999);
    grid.cells[2*7+3] = 1u << 7;
    assert(FogAt(map, 7, {3*32+31,2*32+31}) == 1);
    assert(FogAt(map, 6, {3*32,2*32}) == 0);
    std::set<int> found;
    cursor = 0;
    for (int calls = 0; calls < 35; ++calls) {
        const int previous = cursor; grid.reads = 0;
        const auto status = NextFrontier(map, 7, {32,32}, cursor, 2, out, &work);
        assert(cursor-previous == work && work <= 2 && grid.reads <= work*5);
        if (status == SearchStatus::Found) {
            assert(FogAt(map,7,out) == 0);
            assert(found.insert(out.y/32*7+out.x/32).second);
        }
        if (status == SearchStatus::Complete) break;
    }
    assert(cursor == 35 && found == std::set<int>({10,16,18,24}));
    // Completion is idempotent, does no tile work, and never changes output.
    grid.reads = 0; const auto saved = out;
    assert(NextFrontier(map,7,{32,32},cursor,1,out,&work) == SearchStatus::Complete);
    assert(work == 0 && grid.reads == 0 && out.x == saved.x && out.y == saved.y);
    // Fully explored and completely unexplored are different map states,
    // but neither contains a hidden/explored boundary. Budget exhaustion is
    // never returned as completion until every cell has actually been read.
    for (auto fill : {0u, 0xFFFFFFFFu}) {
        for (auto& cell : grid.cells) cell = fill;
        cursor = 0;
        assert(NextFrontier(map,31,{0,0},cursor,1,out) == SearchStatus::Exhausted);
        assert(NextFrontier(map,31,{0,0},cursor,256,out) == SearchStatus::Complete);
    }
    Grid line{1,3,0,{0,1,0}}; View thin{&line,&Mask,1,3}; cursor = 0;
    assert(NextFrontier(thin,0,{0,0},cursor,256,out) == SearchStatus::Found && out.y == 16);
    assert(NextFrontier(thin,0,{0,0},cursor,256,out) == SearchStatus::Found && out.y == 80);
    assert(NextFrontier(thin,0,{0,0},cursor,256,out) == SearchStatus::Complete);
    View overflow{&line,&Mask,0x7FFFFFFF,0x7FFFFFFF};
    assert(!Valid(overflow));
    return 0;
}
