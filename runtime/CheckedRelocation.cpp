#include "CheckedRelocation.h"
namespace MajestyCheckedPlacement {
bool WriteBoundary::Arm(Word actor) {
    if(!actor||actor_)return false;
    actor_=actor;frame_=0;invalid_=checking_=written_=false;return true;
}
bool WriteBoundary::IsExpected(Word actor,Word frame) const {
    return actor_&&frame_&&actor==actor_&&frame==frame_;
}
void WriteBoundary::OtherWrite() { if(actor_&&!written_)invalid_=true; }
bool WriteBoundary::CanCheck() const { return actor_&&frame_&&!invalid_&&!checking_&&!written_; }
bool WriteBoundary::BeginCheck() { if(!CanCheck())return false;checking_=true;return true; }
bool WriteBoundary::FinishCheck(bool valid) {
    if(!checking_)return false;
    checking_=false;
    if(!valid||invalid_||written_){invalid_=true;return false;}
    written_=true;return true;
}
void WriteBoundary::Clear() { actor_=frame_=0;invalid_=checking_=written_=false; }
}
