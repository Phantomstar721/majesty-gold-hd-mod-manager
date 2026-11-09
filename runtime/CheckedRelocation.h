#pragma once
#include <cstdint>
#include "CheckedPlacement.h"
#include "MajestyBuildId.h"

namespace MajestyCheckedPlacement {
// One synchronous invocation. Not saved, not a replacement movement order.
// Foreign/reentrant stock moves are preserved but invalidate the pending check.
class WriteBoundary {
public:
    bool Arm(Word actor);
    void SetFrame(Word frame) { frame_=frame; }
    bool IsArmed() const { return actor_!=0; }
    bool IsExpected(Word actor, Word frame) const;
    void OtherWrite();
    bool CanCheck() const;
    bool BeginCheck();
    bool FinishCheck(bool valid);
    bool Committed() const { return written_; }
    void Clear();
private:
    Word actor_{},frame_{};
    bool invalid_{},checking_{},written_{};
};

// Installation is owned by the feature's exact-image startup gate, before
// any world is attached. This does not register or advertise a GPL capability.
bool InstallWriteBoundary(MajestyBuildId);
using FinalPlacementCheck = bool (*)(void* context);
// Calls unmodified stock point conversion and spatial-notification sequence.
// FinalPlacementCheck executes after pre-write notifications, immediately
// before the original coordinate stores. On refusal, a still-owned actor runs
// the native post-notification sequence at its current coordinates. A retired
// actor/world uses the native epilogue; no stale unit is dereferenced.
bool RelocateChecked(Word actor, Point pixels, FinalPlacementCheck,
    FinalPlacementCheck stillOwned, void* context);
}
