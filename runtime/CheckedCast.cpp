#include "CheckedCast.h"
#include <cstdio>
namespace MajestyCheckedPlacement {
void StockCasts::Trace(Word actor,unsigned reason,const char* event) const {
    if(!diagnostic)return;auto i=records_.find(actor);if(i==records_.end())return;
    const auto& r=i->second;char text[240]{};
    std::snprintf(text,sizeof(text),"%s id=%u target=%u order=%08X action=%08X value=%08X definition=%08X animation=%u released=%u scheduled=%u invoked=%u",
        event,actor,r.target.id,r.order,r.action,r.functionValue,r.definition,r.animation,r.released,r.scheduled,r.invoked);
    diagnostic(r.actor.address,reason,text);
}
bool StockCasts::Submitted(const Identity& a,const Identity& t,Word action,Word order) {
    if(records_.count(a.id)||!casts_.Accepted(a,t,order,action))return false;
    records_.emplace(a.id,Record{a,t,action,order});return true;
}
bool StockCasts::Animation(Word actor,Word processing,Word animation,Word action,Word target) {
    auto i=records_.find(actor);
    if(i==records_.end())return false;
    auto& r=i->second;
    if(r.animation||r.released||r.order!=processing||r.action!=action||r.target.id!=target||
        !casts_.Transfer(actor,processing,animation,action)){Trace(actor,40,"animation refused");return false;}
    r.animation=true;r.order=animation;return true;
}
bool StockCasts::Turning(Word actor,Word processing,Word turn,Word action,Word target) {
    auto i=records_.find(actor);if(i==records_.end())return false;auto& r=i->second;
    if(r.turning)return r.turnParent==processing&&r.turnOrder==turn&&r.action==action&&r.target.id==target;
    if(r.turning||r.animation||r.released||r.order!=processing||r.action!=action||r.target.id!=target||
        !casts_.Transfer(actor,processing,turn,action))return false;
    r.turning=true;r.turnParent=processing;r.turnOrder=turn;r.order=turn;return true;
}
bool StockCasts::Release(Word actor,Word order,Word action,Word target) {
    auto i=records_.find(actor);
    if(i==records_.end())return false;
    auto& r=i->second;
    if(!r.animation||r.released||r.order!=order||r.action!=action||r.target.id!=target||
        !casts_.Release(actor,order,action)){Trace(actor,41,"release refused");return false;}
    r.released=true;return true;
}
bool StockCasts::Scheduled(Word actor,Word order,Word value,Word definition,bool idle) {
    auto i=records_.find(actor);
    if(i==records_.end())return false;
    auto& r=i->second;
    if(!r.released||r.scheduled||r.order!=order||!idle||!value||!definition){Trace(actor,38,"schedule refused");return false;}
    for(const auto& other:records_)if(other.second.functionValue==value)return false;
    r.functionValue=value;r.definition=definition;r.scheduled=true;return true;
}
bool StockCasts::EnterCallback(Word value,Word definition,const Identity& a,const Identity& t) {
    // Push a sentinel even for an unrelated nested callback. It cannot borrow
    // its parent's permission; LeaveCallback restores the exact parent scope.
    if(callbacks_.size()>=64){++overflowDepth_;Reset();return false;}
    callbacks_.push_back(0);
    auto i=records_.find(a.id);
    if(i==records_.end())return false;
    auto& r=i->second;
    if(!r.scheduled||r.invoked||r.functionValue!=value||r.definition!=definition||
        !Same(r.actor,a)||!Same(r.target,t)||!casts_.Matches(a,t,CastPhase::Released)){Trace(a.id,39,"callback refused");return false;}
    r.invoked=true;callbacks_.back()=a.id;return true;
}
bool StockCasts::InCallback(const Identity& a,const Identity& t) const {
    if(overflowDepth_||callbacks_.empty()||callbacks_.back()!=a.id)return false;
    auto i=records_.find(a.id);
    return i!=records_.end()&&Same(i->second.actor,a)&&Same(i->second.target,t)&&
        casts_.Matches(a,t,CastPhase::Released);
}
void StockCasts::LeaveCallback() {
    if(overflowDepth_){--overflowDepth_;return;}
    if(callbacks_.empty())return;
    auto actor=callbacks_.back();callbacks_.pop_back();
    if(actor){Trace(actor,42,"callback exit");Interrupted(actor,"callback completed");}
}
void StockCasts::Unlinked(Word actor,Word order) {
    auto i=records_.find(actor);
    if(i!=records_.end()&&i->second.order==order){Trace(actor,33,"order unlinked");if(!i->second.released)Interrupted(actor,"unlinked before release");}
}
void StockCasts::RetargetedOrder(Word order,Word target) {
    for(auto i=records_.begin();i!=records_.end();)
        if(i->second.order==order&&i->second.target.id!=target){Trace(i->first,37,"retargeted");casts_.InvalidateUnit(i->first);i=records_.erase(i);}else ++i;
}
void StockCasts::Interrupted(Word actor,const char* reason) {
    Trace(actor,32,reason);
    if(records_.erase(actor))casts_.InvalidateUnit(actor);
}
void StockCasts::InvalidateUnit(Word id) {
    casts_.InvalidateUnit(id);
    for(auto i=records_.begin();i!=records_.end();)
        if(i->second.actor.id==id||i->second.target.id==id){Trace(i->first,34,"identity invalidated");i=records_.erase(i);}else ++i;
}
void StockCasts::InvalidateFunction(Word value) {
    for(auto i=records_.begin();i!=records_.end();)
        if(i->second.functionValue==value){Trace(i->first,35,"function reset/destroy");casts_.InvalidateUnit(i->first);i=records_.erase(i);}else ++i;
}
void StockCasts::Reset() { if(diagnostic)for(const auto& r:records_)Trace(r.first,36,"world/binding reset");records_.clear();casts_.Reset(); }
}
