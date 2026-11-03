#pragma once
#include <cstdint>
#include <map>
#include <vector>

// Feature-local checks for the guarded stock cast/teleport adapter. These types
// contain no engine addresses, own no actors/orders, and never schedule work.
namespace MajestyCheckedPlacement {
// Twice the largest supported map side covers its diagonal; range never
// expands the target-local landing perimeter or starts a map-wide scan.
constexpr int MaximumRange = 2 * 65535 * 16;
using Word = std::uint32_t;
struct Point { int x{}, y{}; };
inline bool operator==(Point a, Point b) { return a.x==b.x && a.y==b.y; }
struct Identity {
    Word address{}, id{}, world{}, player{}, description{};
    std::uint64_t lifetime{};
};
bool Same(const Identity&, const Identity&);
struct Footprint {
    // Exact occupied tile offsets, decoded from a validated stock bitmap or
    // rectangle. Empty, repeated, or unbounded metadata is not an empty actor.
    std::vector<Point> cells;
    bool Valid() const;
};
// Decode the stock row-major, least-significant-bit-first bitmap. Inputs must
// be copied from the guarded effective descriptor before calling this helper.
bool DecodeBitmap(int width, int height, int stride, Point offset,
    const std::vector<std::uint8_t>& bytes, Footprint&);
// Stock rectangle traversal is [left,right) x [top,bottom).
bool DecodeRectangle(int left, int top, int right, int bottom, Footprint&);
bool FitsBounds(const Footprint&, Point tile, int width, int height);
bool Intersects(const Footprint&, Point, const Footprint&, Point);
std::vector<Point> ExteriorSeeds(const Footprint& target, Point targetTile,
    const Footprint& mover, Point sourcePixels, int width, int height, int range);

enum class CastPhase { Submitted, Released };
struct Cast {
    Identity actor, target;
    Word order{}, action{};
    CastPhase phase{CastPhase::Submitted};
};
class Casts {
public:
    // Bracket the complete synchronous commit, including its first capture.
    // Reject fresh authorizations during callbacks from that operation too.
    bool EnterCommit();
    void LeaveCommit();
    std::uint64_t Invalidation() const { return invalidation_; }
    // A native owner must have actually accepted the declared order before
    // this is called. A GPL request or a restored bare ID cannot authorize it.
    bool Accepted(const Identity&, const Identity&, Word order, Word action);
    bool Transfer(Word actorId, Word oldOrder, Word newOrder, Word action);
    bool Release(Word actorId, Word order, Word action);
    bool Matches(const Identity&, const Identity&, CastPhase) const;
    bool Consume(const Identity&, const Identity&);
    void RemovedOrder(Word actorId, Word order);
    void InvalidateUnit(Word id);
    void Reset();
private:
    std::map<Word,Cast> casts_;
    bool committing_{};
    std::uint64_t invalidation_{};
    bool exhausted_{};
    void Invalidate();
};

struct Snapshot {
    Identity actor, target;
    Footprint mover, targetShape;
    Point sourcePixels, targetTile;
    Word map{};
    int width{}, height{};
    // Native mutation epoch: equality of current values alone cannot detect
    // owner/target/descriptor changes that were subsequently reversed.
    std::uint64_t revision{};
    // Populated by the native adapter only after loaded-description/provenance,
    // living/outside, cast-boundary and supported-map checks.
    bool verified{};
};
bool SamePlacement(const Snapshot&, const Snapshot&);

class Native {
public:
    virtual bool Capture(Snapshot&) = 0;
    virtual bool CompletePath(const Snapshot&, Point pixels) = 0;
    virtual bool FitsTeleport(const Snapshot&, Point tile) = 0;
    // Call stock placement search with its ordinary teleport arguments. True
    // means its success byte is set AND its output equals the checked seed.
    virtual bool SelectCheckedSeed(const Snapshot&, Point pixels) = 0;
    // Literal stock channel cancellation. This is allowed to invalidate the
    // checked state; Capture and both predicates are repeated after it.
    virtual void Cancel(const Snapshot&) = 0;
    // Only called at the stock relocation boundary after the final recheck.
    // The concrete adapter must additionally prove the native notifications
    // before its coordinate write cannot invalidate those checks. This core
    // does not establish that property for an arbitrary engine function.
    // No fallback search or raw coordinate result may be substituted here.
    virtual bool Relocate(const Snapshot&, Point pixels) = 0;
    virtual ~Native() = default;
};
// Return1 only after one relocation,0 for refusal. The cast is consumed before
// any cancellation callback; nested or repeated attempts cannot reuse it.
int Commit(Casts&, Native&, int range,const char** diagnostic=nullptr);
}
