#pragma once
#include "CheckedNativeState.h"
#include "CheckedPlacementProfiles.h"
namespace MajestyCheckedPlacement {
// Internal native adapter. Callers must establish the exact active stock
// callback and loaded feature binding before constructing/using it.
class StockPlacement final: public Native {
public:
    StockPlacement(const StateServices& services,const PlacementQueryProfile& queries,Word actor,Word target):services_(services),queries_(queries),actor_(actor),target_(target){}
    bool Capture(Snapshot&) override;
    bool CompletePath(const Snapshot&,Point pixels) override;
    bool FitsTeleport(const Snapshot&,Point tile) override;
    bool SelectCheckedSeed(const Snapshot&,Point pixels) override;
    void Cancel(const Snapshot&) override;
    bool Relocate(const Snapshot&,Point pixels) override;
private:
    StateServices services_;const PlacementQueryProfile& queries_;Word actor_,target_;
    Snapshot expected_;Point destination_;
    static bool FinalCheck(void*);
    static bool StillOwned(void*);
};
}
