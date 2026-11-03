#pragma once
#include <array>
#include <cstdint>
#include <map>
#include <vector>

// Authored presentation logic, not a model of undocumented actor behavior.
// No engine calls, actor writes, movement, damage, audio or persistent handles.
namespace MajestyEffectSequence {
enum class Profile { Unsupported, AuditedModifiedBeta2 };
struct Support {
    Profile profile{Profile::Unsupported};
    // Supplied by the Manager adapter after composed resource and renderer
    // validation, never by mod JSON. No production adapter currently supplies it.
    bool checkedPlacement{}, replaceableWorldFrame{};
    bool Ready() const {
        return profile == Profile::AuditedModifiedBeta2 && checkedPlacement && replaceableWorldFrame;
    }
};
struct Owner {
    std::uint32_t id{};
    std::uint64_t life{}, world{};
};
inline bool operator==(Owner a, Owner b) { return a.id==b.id && a.life==b.life && a.world==b.world; }
struct Point { int x{}, y{}; };
enum class Phase { Departure, Meteor, Impact, Fade };
struct Visual {
    std::uint64_t ticket{};
    Owner owner;
    Phase phase{};
    Point anchor; // fixed world location captured by the trusted placement adapter
    Point offset; // presentation only, never a relocation destination
    std::array<Point,8> trail{};
    unsigned trailCount{};
    unsigned opacity{1000};
};
struct OwnerSample { Owner owner; bool livingOutside{}; };
struct Timing {
    unsigned departureTimeout{1200}; // retain stock release lifetime
    unsigned descent{500}, impact{200}, fade{200};
};

class Sequence {
public:
    explicit Sequence(Support support, Timing timing = {});
    // Called at an observed cast release, with a current validated owner.
    // Release is cosmetic; it neither creates nor extends relocation authority.
    std::uint64_t Release(Owner, Point source, std::uint64_t now);
    // Only an adapter observing successful guarded Commit may call this.
    // One-shot. It accepts the ACTUAL resulting position, not a reserved seed.
    bool Placed(std::uint64_t ticket, Owner, Point actual, std::uint64_t now);
    // Each output wholly replaces the previous draw batch. Missing identity,
    // expired sequence or refusal produces no remaining drawing for that ticket.
    // Engine adapter must provide a coherent current owner sample each frame.
    std::vector<Visual> Frame(std::uint64_t now, const std::vector<OwnerSample>&);
    void Cancel(std::uint64_t ticket);
    void Removed(Owner);
    // Save/load/world teardown: transient visuals are discarded, never restored.
    // No native appearance was changed, so no actor restoration call is needed.
    void Reset(std::uint64_t world);
    bool Ready() const { return support_.Ready() && validTiming_; }
    std::size_t Active() const { return entries_.size(); }
private:
    struct Entry { Owner owner; Point anchor; std::uint64_t started; bool placed; };
    Support support_;
    Timing timing_;
    bool validTiming_{}, clockSet_{};
    std::uint64_t world_{}, lastTime_{}, nextTicket_{1};
    std::map<std::uint64_t,Entry> entries_;
    bool Clock(std::uint64_t);
    static bool Valid(Owner);
    static Point Descent(unsigned elapsed, unsigned duration);
};
}
