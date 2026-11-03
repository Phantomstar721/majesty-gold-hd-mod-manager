#pragma once
#include "CheckedPlacement.h"

namespace MajestyCheckedPlacement {
// Observation of one stock action -> animation -> RunThread function value.
// The native adapter supplies identities only after its loaded-world checks.
// No callback is scheduled here and no identity survives restoration.
class StockCasts {
public:
    void (*diagnostic)(Word,unsigned,const char*){};
    bool Submitted(const Identity&,const Identity&,Word action,Word order);
    bool Animation(Word actor,Word processingOrder,Word animation,Word action,Word target);
    bool Turning(Word actor,Word processingOrder,Word turn,Word action,Word target);
    bool Release(Word actor,Word order,Word action,Word target);
    bool Scheduled(Word actor,Word order,Word functionValue,Word definition,bool previouslyIdle);
    // Exact stock timer invocation, not a caller assertion or bare agent IDs.
    bool EnterCallback(Word functionValue,Word definition,const Identity&,const Identity&);
    void LeaveCallback();
    bool InCallback(const Identity&,const Identity&) const;
    bool Pending(Word actor) const { return records_.count(actor)!=0; }
    void Unlinked(Word actor,Word order);
    void RetargetedOrder(Word order,Word target);
    void Interrupted(Word actor,const char* reason="interrupted");
    void InvalidateUnit(Word id);
    void InvalidateFunction(Word functionValue);
    void Reset();
    Casts& Authorizations() { return casts_; }
private:
    void Trace(Word actor,unsigned reason,const char* event) const;
    struct Record {
        Identity actor,target;
        Word action{},order{},functionValue{},definition{};
        bool animation{},released{},scheduled{},invoked{},turning{};
        Word turnParent{},turnOrder{};
    };
    std::map<Word,Record> records_;
    std::vector<Word> callbacks_;
    std::size_t overflowDepth_{};
    Casts casts_;
};
}
