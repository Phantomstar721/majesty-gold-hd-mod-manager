#pragma once
#include <cstdint>
#include <cstddef>
#include <set>
#include <vector>
#include <atomic>

// Feature-local read-only core for the existing typed Manager runtime.
// No hooks, launcher, replacement scheduler, timers, or game writes here.
namespace MajestyAttackObservation {
using Address = std::uint32_t;
// Conservative GPL expression range. Native int32 storage is not proof that
// every source comparison avoids fixed10 coercion. Never truncate identities.
constexpr std::uint32_t kMaximumIdentity = 2097151;
inline bool Representable(std::uint32_t id) { return id && id <= kMaximumIdentity; }
enum class Result : int { Unknown = -1, Busy = 0, Settled = 1 };
struct Memory {
    virtual bool Read(Address address, void* output, std::size_t bytes) const = 0;
    virtual ~Memory() = default;
};
struct Profile {
    Address imageBase{}, runtimeGlobal{}, allUnitsVtable{}, impactGlobal{}, impactFunction{};
    Address projectileId{}, projectileEngine{}, movementEngine{};
    std::uint32_t scriptFlags{};
    // Populated only by the guarded effective-package/lifecycle adapter.
    // Disk hash alone cannot certify loaded BCD precedence or action mappings.
    bool exactExecutable{}, effectivePackage{}, lifecycleBound{};
    Address actorDescriptor{}, missileVtable{}, animationVtable{};
    bool requireStockMovementFlags{};
    Address retirementMethod{};
    Address stockAllUnitsVtable{}; // Exact second stock class, never arbitrary RTTI.
};
struct Capture {
    Result result{Result::Unknown};
    const char* failure{"not-inspected"}; // Literal stage; never a native pointer.
    std::size_t units{}, orders{}, actorPending{}, missiles{};
    std::vector<std::uint32_t> missileIds;
};
// Process-lifetime budget: successful queries do not consume it. There is no
// reset at world changes, actor changes or registry re-registration.
class FailureReportBudget {
    std::atomic<bool> used_{false};
public:
    bool Take(Result result) {
        return result==Result::Unknown && !used_.exchange(true);
    }
};
// The same bounded native-list reader is exercised by fixture tests.
// Caller MUST be on the owning game thread, outside all guarded operations.
Capture Inspect(const Memory&, const Profile&, Address world, Address catalog,
                Address actor, std::uint32_t actorId);

struct RetirementToken { std::uint64_t generation{}, serial{}; Address actor{}; std::uint32_t id{}; };
class Lifecycle {
public:
    bool Attach(const Memory&, const Profile&, int loadStatus, int mode, Address world, Address catalog);
    // Only the adapter's guarded post-construction stock caller may use this.
    // A new world has no load status; never fabricate one or restore counters.
    bool AttachCreated(const Memory&, const Profile&, int mode, Address world, Address catalog);
    void EnterOperation();
    void LeaveOperation();
    void BeginWorldTeardown(); // Invalidate BEFORE the direct bulk-retirement path.
    void IdentityIncoherent(); // AL1 from catalog unlink is NOT retirement proof.
    RetirementToken BeginRetirement(Address copiedPointer, std::uint32_t copiedId);
    void EndRetirement(RetirementToken token, bool normalConcreteReturn);
    Capture Query(const Memory&, const Profile&, Address actor, std::uint32_t id) const;
    bool ContextAllowed(const Memory&, const Profile&, Address world,
                        std::uint64_t generation, std::uint32_t actorId,
                        std::uint32_t projectileId) const;
    std::uint64_t Generation() const { return generation_; }
    std::uint64_t Revision() const { return revision_; }
    bool RecordedRetirement(std::uint32_t id) const { return coherent_ && Representable(id) && retiredIds_.count(id)!=0; }
    bool SnapshotCurrent(const Memory&,const Profile&,std::uint64_t generation,std::uint64_t revision) const;
private:
    bool AttachWorld(const Memory&, const Profile&, bool accepted, Address world, Address catalog);
    void Invalidate();
    std::uint64_t generation_{}, serial_{}, revision_{};
    Address world_{}, catalog_{};
    unsigned depth_{};
    bool coherent_{false};
    std::vector<RetirementToken> retirements_;
    std::set<std::uint32_t> retiredIds_; // Fail closed on same-world numeric reuse.
};
// One synchronous snapshot for a full 32-slot store. Native mutations, world
// changes, token mismatch and explicit close invalidate it; it is never saved.
class ShotSnapshot {
public:
    int Begin(const Memory&,const Profile&,const Lifecycle&,Address actor,std::uint32_t actorId);
    int Pending(const Memory&,const Profile&,const Lifecycle&,Address actor,std::uint32_t actorId,int token,std::uint32_t projectileId) const;
    void End(int token);
private:
    std::vector<std::uint32_t> ids_;
    Address actor_{}; std::uint32_t actorId_{};
    std::uint64_t generation_{}, revision_{};
    int serial_{}, token_{};
};

} // namespace MajestyAttackObservation
