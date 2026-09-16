#include "BoundedMapQuery.h"
#include <algorithm>
#include <limits>

namespace MajestyMapQuery {
bool Valid(const View& map) {
    return map.context != nullptr && map.readMask != nullptr &&
        map.width > 0 && map.height > 0 &&
        map.width <= std::numeric_limits<int>::max() / kTileScale &&
        map.height <= std::numeric_limits<int>::max() / kTileScale &&
        map.width <= std::numeric_limits<int>::max() / map.height;
}
static bool InBounds(const View& map, Coordinate point) {
    return point.x >= 0 && point.y >= 0 &&
        point.x / kTileScale < map.width && point.y / kTileScale < map.height;
}
int FogAt(const View& map, int player, Coordinate point) {
    if (!Valid(map) || player < 0 || player >= 32 || !InBounds(map, point)) return -1;
    return (map.readMask(map.context, point.x / kTileScale, point.y / kTileScale)
            & (std::uint32_t{1} << player)) != 0 ? 1 : 0;
}

namespace {
// Stock GetNearestHiddenCoord starts at [x,y,x+1,y+1], then grows
// every side by one. Its first orientation walks top/right/bottom/left.
// Keep that first-visit order, excluding padding and previously visited
// clamped edges. No random draw, retained state, or replay of prior tiles.
int Covered(const View& map, Coordinate tile, int radius) {
    if (radius < 0) return 0;
    const int left = std::max(0, tile.x-radius);
    const int top = std::max(0, tile.y-radius);
    const int right = std::min(map.width-1, tile.x+1+radius);
    const int bottom = std::min(map.height-1, tile.y+1+radius);
    return (right-left+1)*(bottom-top+1); // Valid() bounds total to INT_MAX.
}
struct Segment {
    Coordinate first{};
    int dx = 0, dy = 0, count = 0;
};
struct Ring {
    Segment sides[8];
    int count = 0;
    Ring(const View& map, Coordinate tile, int radius) {
        const int left = std::max(0,tile.x-radius), top = std::max(0,tile.y-radius);
        const int right = std::min(map.width,tile.x+1+radius);
        const int bottom = std::min(map.height,tile.y+1+radius);
        const int oldLeft = std::max(0,tile.x-radius+1);
        const int oldTop = std::max(0,tile.y-radius+1);
        const int oldRight = std::min(map.width-1,tile.x+radius);
        const int oldBottom = std::min(map.height-1,tile.y+radius);
        int used = 0;
        auto emit = [&](bool horizontal, int fixed, int lo, int hi, int step) {
            if (lo > hi) return;
            const int first = step > 0 ? lo : hi;
            sides[used++] = {horizontal ? Coordinate{first,fixed} : Coordinate{fixed,first},
                            horizontal ? step : 0, horizontal ? 0 : step, hi-lo+1};
            count += hi-lo+1;
        };
        auto add = [&](bool horizontal, int fixed, int first, int last, int step) {
            if (fixed < 0 || fixed >= (horizontal ? map.height : map.width) ||
                (step > 0 ? first > last : first < last)) return;
            const int lo = std::max(0,std::min(first,last));
            const int hi = std::min((horizontal ? map.width : map.height)-1,std::max(first,last));
            // Preserve the clamped native side's order. Subtracting the old
            // rectangle can leave two runs; jumping them costs no tile reads.
            const int oldLo = horizontal ? oldLeft : oldTop;
            const int oldHi = horizontal ? oldRight : oldBottom;
            if (radius == 0 || fixed < (horizontal ? oldTop : oldLeft) ||
                fixed > (horizontal ? oldBottom : oldRight)) {
                emit(horizontal,fixed,lo,hi,step);
            } else if (step > 0) {
                emit(horizontal,fixed,lo,std::min(hi,oldLo-1),step);
                emit(horizontal,fixed,std::max(lo,oldHi+1),hi,step);
            } else {
                emit(horizontal,fixed,std::max(lo,oldHi+1),hi,step);
                emit(horizontal,fixed,lo,std::min(hi,oldLo-1),step);
            }
        };
        // Corners belong to exactly one side, as in the native loops.
        add(true,top,left,right-1,1);
        add(false,right,top,bottom-1,1);
        add(true,bottom,right,left+1,-1);
        add(false,left,bottom,top+1,-1);
    }
    Coordinate At(int offset) const {
        for (const auto& side : sides) {
            if (offset < side.count)
                return {side.first.x+side.dx*offset, side.first.y+side.dy*offset};
            offset -= side.count;
        }
        return {-1,-1}; // Unreachable for an ordinal within Covered().
    }
};
}
SearchStatus NextFrontier(const View& map, int player, Coordinate origin,
                          int& cursor, int budget, Coordinate& output, int* workDone) {
    if (workDone != nullptr) *workDone = 0;
    if (!Valid(map) || player < 0 || player >= 32 || !InBounds(map, origin) ||
        budget < 1 || budget > kMaximumWork || cursor < 0 ||
        cursor > map.width * map.height) return SearchStatus::Invalid;
    const int total = map.width * map.height;
    if (cursor == total) return SearchStatus::Complete;
    const Coordinate tile{origin.x/kTileScale, origin.y/kTileScale};
    // Locate the continuation ring without visiting earlier tiles/rings.
    // Valid() limits dimensions to INT_MAX/32: at most 26 arithmetic steps.
    int low = 0, high = std::max(map.width,map.height)-1;
    while (low < high) {
        const int middle = low+(high-low)/2;
        if (Covered(map,tile,middle) > cursor) high = middle;
        else low = middle+1;
    }
    int radius = low, offset = cursor-Covered(map,tile,radius-1);
    Ring ring(map,tile,radius);
    const auto bit = std::uint32_t{1} << player;
    for (int work = 0; work < budget && cursor < total; ++work) {
        const Coordinate next = ring.At(offset++);
        ++cursor;
        if (workDone != nullptr) ++*workDone;
        if (offset == ring.count && cursor < total) {
            ring = Ring(map,tile,++radius);
            offset = 0;
        }
        const int x = next.x, y = next.y;
        if ((map.readMask(map.context, x, y) & bit) != 0) continue;
        const bool frontier =
            (x > 0 && (map.readMask(map.context, x-1, y) & bit) != 0) ||
            (x+1 < map.width && (map.readMask(map.context, x+1, y) & bit) != 0) ||
            (y > 0 && (map.readMask(map.context, x, y-1) & bit) != 0) ||
            (y+1 < map.height && (map.readMask(map.context, x, y+1) & bit) != 0);
        if (frontier) {
            output = {x * kTileScale + kTileScale/2, y * kTileScale + kTileScale/2};
            return SearchStatus::Found;
        }
    }
    return cursor == total ? SearchStatus::Complete : SearchStatus::Exhausted;
}
}
