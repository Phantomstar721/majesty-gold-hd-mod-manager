#pragma once
#include "AttackObservation.h"
#include "MajestyBuildId.h"
#include <array>
#include <set>
#include <limits>
namespace MajestyCheckedPlacement {
// Exact primary RTTI tables from the three admitted images. No factory,
// callback or movement-controller replacement is introduced.
struct TravelCastProfile { std::array<unsigned,5> movement; };
inline const TravelCastProfile* TravelCastFor(MajestyBuildId build) {
    static const TravelCastProfile publicBuild{{0x748B88,0x7404EC,0x7496B4,0x7497EC,0x7498B4}};
    static const TravelCastProfile betaBuild{{0x762C58,0x7591EC,0x763784,0x7638BC,0x763984}};
    static const TravelCastProfile gogBuild{{0x761B18,0x7583A4,0x762644,0x76277C,0x762844}};
    switch(build) {
    case MajestyBuildId::SteamPublic:return &publicBuild;
    case MajestyBuildId::SteamBeta2:return &betaBuild;
    case MajestyBuildId::Gog:return &gogBuild;
    default:return nullptr;
    }
}
// Caller has already established current actor/world/epoch and effective
// placement bindings. Inspect only that actor, never the global unit catalog.
inline bool TravelCastReady(const MajestyAttackObservation::Memory& memory,
                            unsigned unit,const TravelCastProfile* profile) {
    if(!unit||!profile)return false;
    const auto read=[&](unsigned base,unsigned offset,unsigned& value) {
        return base && base<=UINT32_MAX-offset && base+offset<=UINT32_MAX-3 &&
            memory.Read(base+offset,&value,sizeof(value));
    };
    std::set<unsigned> orders;
    for(unsigned channel=0;channel<3;++channel) {
        unsigned stack{},owner{},head{},node{},count{},last{};
        if(!read(unit,0x98+4*channel,stack))return false;
        if(!stack)continue;
        if(!read(stack,4,owner)||owner!=unit||!read(stack,0x1C,head)||!head||
           !read(stack,0x20,count)||count>16||!read(head,0,node)||!read(head,4,last))return false;
        // Stock kind10 waits on channel2; never enqueue behind an animation.
        if(channel==2 && count)return false;
        unsigned previous=head,visited=0;
        std::set<unsigned> nodes;
        while(node!=head) {
            unsigned next{},back{},order{},table{};
            if(++visited>count||!nodes.insert(node).second||!read(node,0,next)||
               !read(node,4,back)||back!=previous||!read(node,8,order)||
               !orders.insert(order).second||!read(order,0,table))return false;
            bool movement=false;
            for(auto expected:profile->movement)if(table==expected)movement=true;
            if(!movement)return false;
            previous=node;node=next;
        }
        if(visited!=count||last!=previous)return false;
    }
    return true;
}
}
