#pragma once
#include "CheckedPlacement.h"
#include <vector>
#include <cstddef>

// Synchronous cancellation bookkeeping only. Nothing survives the outer native
// operation, is serialized, or runs on a timer. Native code still owns the order
// and pose. A caller may nominate only an effective, declared cosmetic action.
namespace MajestyCheckedPlacement {
struct CosmeticPose {
    Identity actor;
    Word order{}, action{}, collection{}, part{}, imageSet{}, actionDescriptor{}, imageDescriptor{};
    Word streamRole{},association{};
};
struct CosmeticCleanupBindings {
    bool (*capture)(Word unit,Word order,CosmeticPose&){};
    // Recheck the full live identity, effective declaration, selected private
    // part/set, and absence of a replacement animation. Must not invoke GPL.
    bool (*current)(const CosmeticPose&){};
    // The guarded stock state-aware refresh, with force=false. Never force Stand.
    void (*refresh)(Word unit){};
};
class CosmeticActionCleanup {
public:
    void Configure(CosmeticCleanupBindings bindings) {
        if(bindings_.capture==bindings.capture&&bindings_.current==bindings.current&&
            bindings_.refresh==bindings.refresh)return;
        Reset();bindings_=bindings;
    }
    void Enter() { ++depth_; }
    void Leave(bool normal=true) {
        if(!depth_)return;
        if(!normal)Reset();
        if(--depth_ || !normal)return;
        // Native refresh can submit/retire orders reentrantly. Keep this outer
        // scope alive, consume before calling out, and let invalidation remove
        // any other queued owners before their turn.
        depth_=1;
        try {
            while(!entries_.empty()) {
                const Entry entry=entries_.back(); entries_.pop_back();
                if(entry.unlinked && bindings_.current && bindings_.refresh &&
                    bindings_.current(entry.pose))bindings_.refresh(entry.pose.actor.address);
            }
        } catch(...) { Reset();depth_=0;throw; }
        Reset();depth_=0;
    }
    void Cancelling(Word unit,Word order) {
        if(!depth_||!bindings_.capture||!bindings_.current||!bindings_.refresh)return;
        CosmeticPose pose;
        if(!bindings_.capture(unit,order,pose)||pose.actor.address!=unit||
            !pose.actor.id||!pose.actor.world||!pose.actor.description||!pose.actor.lifetime||
            pose.order!=order||!order||!pose.action||!pose.collection||!pose.part||!pose.imageSet||
            !pose.actionDescriptor||!pose.imageDescriptor)return;
        for(const auto& entry:entries_)
            if(entry.pose.actor.address==unit && entry.pose.order==order)return;
        for(auto& entry:entries_)if(!entry.pose.order){entry={pose,false};return;}
        entries_.push_back({pose,false});
    }
    void Unlinked(Word unit,Word order) {
        for(auto& entry:entries_)
            if(entry.pose.actor.address==unit&&entry.pose.order==order)entry.unlinked=true;
    }
    void Invalidate(Word unit) {
        for(auto& entry:entries_)if(entry.pose.actor.address==unit)entry={};
    }
    void Reset() { entries_.clear(); }
private:
    struct Entry { CosmeticPose pose;bool unlinked{}; };
    std::vector<Entry> entries_;
    CosmeticCleanupBindings bindings_{};
    unsigned depth_{};
};
}
