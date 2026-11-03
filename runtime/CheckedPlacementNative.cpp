#include "CheckedPlacementNative.h"
#include "CheckedCastWindows.h"
#include "CheckedRelocation.h"
#include "CheckedPlacementRuntime.h"
namespace MajestyCheckedPlacement {
bool StockPlacement::Capture(Snapshot& snapshot){return ReadPlacement(services_,actor_,target_,snapshot);}
bool StockPlacement::CompletePath(const Snapshot& s,Point pixels) {
    bool complete=false;
    using Query=int (__cdecl*)(bool*,Word,Word,Point,Point,Word);
    reinterpret_cast<Query>(queries_.path)(&complete,s.actor.world,s.actor.address,s.sourcePixels,pixels,0x400);
    return complete;
}
bool StockPlacement::FitsTeleport(const Snapshot& s,Point tile) {
    using Fit=unsigned char (__thiscall*)(void*,Word,int,int,Word,Word,Word);
    return reinterpret_cast<Fit>(queries_.fit)(reinterpret_cast<void*>(s.map),s.actor.address,tile.x,tile.y,0x800,0,0)==0;
}
bool StockPlacement::SelectCheckedSeed(const Snapshot& s,Point pixels) {
    Point selected{};bool success=false;
    using Select=void (__cdecl*)(Point*,bool*,Word,Word,int,int,Word,Word,Word);
    reinterpret_cast<Select>(queries_.seed)(&selected,&success,s.actor.world,s.actor.address,pixels.x,pixels.y,0,0,0);
    return success&&selected==pixels;
}
void StockPlacement::Cancel(const Snapshot& s){CancelObservedCast(s.actor.address);}
bool StockPlacement::FinalCheck(void* context) {
    auto& self=*static_cast<StockPlacement*>(context);
    auto same=[&]{Snapshot now;return self.Capture(now)&&SamePlacement(self.expected_,now);};
    // This runs after stock +B8/+BC notifications and before the first
    // coordinate store. Each indirect query is followed by another capture.
    const char* stage="post-notification identity/state";
    bool ok=same();
    if(ok){stage="post-notification path";ok=self.CompletePath(self.expected_,self.destination_);}
    if(ok){stage="state after post-notification path";ok=same();}
    if(ok){stage="post-notification footprint fit";ok=self.FitsTeleport(self.expected_,{self.destination_.x/16,self.destination_.y/16});}
    if(ok){stage="state after post-notification fit";ok=same();}
    TracePlacementStage(self.expected_.actor.address,ok?56:57,ok?"Coordinate write: authorized":stage);
    return ok;
}
bool StockPlacement::StillOwned(void* context) {
    auto& self=*static_cast<StockPlacement*>(context);
    const auto& a=self.expected_.actor;Word description{},table{};
    // Death/containment/description changes revoke movement, but a live native
    // object still needs the paired spatial notifications. Concrete retirement
    // and a different world/ID decline before another native method call.
    return self.services_.profile&&self.services_.memory&&self.services_.currentIdentity&&
        self.services_.memory->Read(a.address,&table,4)&&
        self.services_.profile->Supports(table)&&
        self.services_.memory->Read(a.address+0x90,&description,4)&&
        self.services_.currentIdentity(a.address,a.id,a.world,description);
}
bool StockPlacement::Relocate(const Snapshot& s,Point pixels) {
    expected_=s;destination_=pixels;
    return RelocateChecked(s.actor.address,pixels,&FinalCheck,&StillOwned,this);
}
}
