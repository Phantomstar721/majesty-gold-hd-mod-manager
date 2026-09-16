#pragma once

#include <cstdint>

// Read-only view of Majesty's native explored mask. No fog copy, world
// objects, saved state, random source, pathfinding, or maintenance work.
namespace MajestyMapQuery {
constexpr int kTileScale = 32;
constexpr int kMaximumWork = 256;
enum class SearchStatus : int { Invalid = -1, Exhausted = 0, Found = 1, Complete = 2 };
struct Coordinate { int x = 0, y = 0; };
using ReadMask = std::uint32_t (*)(const void*, int, int);
struct View {
    const void* context = nullptr;
    ReadMask readMask = nullptr;
    int width = 0, height = 0;
};
bool Valid(const View& map);
// -1 invalid, 0 unexplored, 1 explored; this is NOT current line of sight.
int FogAt(const View& map, int player, Coordinate point);
// Cursor counts examined cells, not results. Keep origin/player/map fixed
// for a traversal; reset cursor to zero for a new traversal. One work unit
// examines one cell and at most its four cardinal neighbours (five reads).
// Traversal follows stock expanding rectangles, clockwise from the top edge;
// resume locates the next ring arithmetically, not by replaying earlier cells.
// A frontier is an unexplored tile adjacent to an explored tile. Complete
// means no unvisited cells remain, not that previously yielded rows vanished.
SearchStatus NextFrontier(const View& map, int player, Coordinate origin,
                          int& cursor, int budget, Coordinate& output,
                          int* workDone = nullptr);
}
