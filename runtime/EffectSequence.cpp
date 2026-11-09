#include "EffectSequence.h"
#include <algorithm>
#include <limits>

namespace MajestyEffectSequence {
Sequence::Sequence(Support support, Timing timing):support_(support),timing_(timing) {
    validTiming_ = timing.departureTimeout==1200 && timing.descent>=100 && timing.descent<=2000 &&
        timing.impact>=100 && timing.impact<=1000 && timing.fade>=100 && timing.fade<=1000;
}
bool Sequence::Valid(Owner o) { return o.id && o.id<=2097151 && o.life && o.world; }
bool Sequence::Clock(std::uint64_t now) {
    if(clockSet_ && now<lastTime_) { entries_.clear(); lastTime_=now; return false; }
    clockSet_=true; lastTime_=now; return true;
}
void Sequence::Reset(std::uint64_t world) {
    entries_.clear(); world_=world; clockSet_=false;
    // Ticket identities are not recycled across resets in this process.
}
std::uint64_t Sequence::Release(Owner owner, Point source, std::uint64_t now) {
    if(!Clock(now) || !Ready() || !Valid(owner) || owner.world!=world_ || entries_.size()>=128 ||
       nextTicket_==std::numeric_limits<std::uint64_t>::max())return 0;
    for(const auto& item:entries_)if(item.second.owner.id==owner.id)return 0;
    const auto ticket=nextTicket_++;
    entries_.emplace(ticket,Entry{owner,source,now,false});
    return ticket;
}
bool Sequence::Placed(std::uint64_t ticket, Owner owner, Point actual, std::uint64_t now) {
    if(!Clock(now))return false;
    const auto it=entries_.find(ticket);
    if(it==entries_.end() || !(it->second.owner==owner) || it->second.placed)return false;
    if(now-it->second.started>=timing_.departureTimeout) {entries_.erase(it);return false;}
    it->second.anchor=actual; it->second.started=now; it->second.placed=true;
    return true;
}
void Sequence::Cancel(std::uint64_t ticket) { entries_.erase(ticket); }
void Sequence::Removed(Owner owner) {
    for(auto it=entries_.begin();it!=entries_.end();)
        if(it->second.owner==owner)it=entries_.erase(it);else ++it;
}
Point Sequence::Descent(unsigned elapsed, unsigned duration) {
    // Quadratic progress increases speed throughout a diagonal approach.
    // 64-bit arithmetic is bounded by validated duration <=2000.
    const auto t=std::min(elapsed,duration);
    const auto denominator=static_cast<std::uint64_t>(duration)*duration;
    const auto remaining=denominator-static_cast<std::uint64_t>(t)*t;
    return {-static_cast<int>(160*remaining/denominator),-static_cast<int>(240*remaining/denominator)};
}
std::vector<Visual> Sequence::Frame(std::uint64_t now,const std::vector<OwnerSample>& samples) {
    std::vector<Visual> result;
    if(!Clock(now))return result;
    for(auto it=entries_.begin();it!=entries_.end();) {
        const auto& e=it->second;
        const bool current=std::count_if(samples.begin(),samples.end(),[&](const OwnerSample& s){
            return s.owner.id==e.owner.id;
        })==1 && std::any_of(samples.begin(),samples.end(),[&](const OwnerSample& s){
            return s.owner==e.owner && s.livingOutside;
        });
        const auto elapsed=now-e.started;
        const auto end=e.placed?timing_.descent+timing_.impact+timing_.fade:timing_.departureTimeout;
        if(!current || elapsed>=end) {it=entries_.erase(it);continue;}
        Visual v{};v.ticket=it->first;v.owner=e.owner;v.anchor=e.anchor;
        if(!e.placed)v.phase=Phase::Departure;
        else if(elapsed<timing_.descent) {
            v.phase=Phase::Meteor;v.offset=Descent(static_cast<unsigned>(elapsed),timing_.descent);
            // Samples span 280ms behind the head, without introducing a second
            // clock, projectile, native movement or delayed impact callback.
            for(unsigned i=0;i<v.trail.size();++i) {
                const auto lag=(i+1)*35u;
                if(elapsed<lag)break;
                v.trail[v.trailCount++]=Descent(static_cast<unsigned>(elapsed)-lag,timing_.descent);
            }
        } else if(elapsed<timing_.descent+timing_.impact)v.phase=Phase::Impact;
        else {
            v.phase=Phase::Fade;
            v.opacity=1000u-static_cast<unsigned>((elapsed-timing_.descent-timing_.impact)*1000/timing_.fade);
        }
        result.push_back(v);++it;
    }
    return result;
}
}
