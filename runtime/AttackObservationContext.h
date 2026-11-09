#pragma once
#include "AttackObservation.h"

namespace MajestyAttackObservation {
// Scoped synchronous identity. Nested callbacks restore their caller's context;
// a mismatch never borrows another actor or target's projectile.
struct CombatContext {
    Address actor{}, target{}, projectile{}, world{};
    std::uint64_t generation{};
};
// Read only the order currently being dispatched, never a queued-order search.
// This is route evidence, not lifetime, package or spell-policy admission.
struct TerminalMissileContext {
    CombatContext identity{};
    Address unit{}, description{}, engine{};
};
template<class ReadWord>
TerminalMissileContext CaptureTerminalMissile(
    ReadWord read, Address stack, Address order, std::uint32_t event,
    Address missileVtable, std::uint64_t generation) {
    TerminalMissileContext result{};
    std::uint32_t kind{}, terminal{}, vtable{};
    if (event != 2 || !missileVtable ||
        !read(order, 0x10, kind) || kind != 3 ||
        !read(order, 0x2C, terminal) || terminal != 0x100A ||
        !read(order, 0, vtable) || vtable != missileVtable ||
        !read(stack, 4, result.unit) ||
        !read(result.unit, 0x90, result.description) ||
        !read(result.description, 0x14, result.engine) ||
        !read(result.unit, 0x70, result.identity.projectile) ||
        !read(result.unit, 0x94, result.identity.world) ||
        !read(order, 0x5C, result.identity.actor) ||
        !read(order, 0x38, result.identity.target)) return {};
    result.identity.generation = generation;
    return result;
}
class CombatScope {
    CombatContext& slot_;
    CombatContext previous_;
public:
    CombatScope(CombatContext& slot, CombatContext current)
        : slot_(slot), previous_(slot) { slot_ = current; }
    ~CombatScope() { slot_ = previous_; }
    CombatScope(const CombatScope&) = delete;
    CombatScope& operator=(const CombatScope&) = delete;
};
inline std::uint32_t ContextId(const CombatContext& c, std::uint32_t actor,
                               std::uint32_t target) {
    return Representable(actor) && Representable(target) && Representable(c.projectile)
        && actor == c.actor && target == c.target ? c.projectile : 0;
}
}
