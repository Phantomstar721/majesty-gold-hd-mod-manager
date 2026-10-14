#include <climits>
#include "AttackObservation.h"
#include <cstring>
#include <limits>
#include <string>
#include <algorithm>
#include <array>
#include <unordered_map>

namespace MajestyAttackObservation {
namespace {
template<class T> bool Read(const Memory& memory, Address address, unsigned offset, T& value) {
    if (!address || address > UINT32_MAX-offset || sizeof(T) > UINT32_MAX-address-offset) return false;
    return memory.Read(address+offset, &value, sizeof(value));
}
bool WorldMatches(const Memory& m, const Profile& p, Address world) {
    Address runtime=0, attached=0, current=0;
    return world && Read(m,p.runtimeGlobal,0,runtime) && runtime &&
        Read(m,runtime,4,attached) && Read(m,runtime,0x10,current) && attached==world && current==world;
}
class QueryTree {
    // GE_AllUnitsList tree at +28; literal unsigned lower-bound topology from
    // 5B8CC0. Inspect only; never call the destructive 5B93C0/5B9670 helpers.
    // Only this synchronous query owns these copied nodes. There are no game
    // calls/mutations while reading, and no data survives the query boundary.
    struct Node { Address left,parent,right; std::uint32_t key,payload; unsigned char tail[4]; };
    static_assert(sizeof(Node)==0x18,"stock tree node extent");
    const Memory& memory_;
    Address head_=0,root_=0;
    bool valid_=false;
    std::unordered_map<Address,Node> nodes_;
public:
    QueryTree(const Memory& m,Address catalog):memory_(m) {
        valid_=Read(m,catalog,0x40,head_) && head_ && Read(m,head_,4,root_);
    }
    bool Contains(std::uint32_t id) {
        if(!valid_)return false;
        Address node=root_;
        std::array<Address,256> seen{}; unsigned count=0;
        while(node!=head_) {
            if(count==seen.size() || std::find(seen.begin(),seen.begin()+count,node)!=seen.begin()+count)return false;
            seen[count++]=node;
            auto it=nodes_.find(node);
            if(it==nodes_.end()) {
                Node value{};
                if(nodes_.size()>=65536 || !Read(memory_,node,0,value))return false;
                it=nodes_.emplace(node,value).first;
            }
            const auto& value=it->second;
            if(value.tail[1])return false; // native nil byte +15
            if(value.key==id)return true;
            node=value.key<id?value.right:value.left;
        }
        return false;
    }
};
struct UnitFields {
    std::uint32_t id,flags,opaque78,type,opaque80[4];
    Address description,world,stacks[3];
};
static_assert(sizeof(UnitFields)==0x34,"stock unit +70 through +A0");
struct UnitNode { Address next,previous; std::uint32_t id; Address unit; };
struct StackFields { Address owner; std::uint32_t opaque[5]; Address sentinel; };
struct OrderNode { Address next,previous,order; };
struct OrderFields { Address vtable; std::uint32_t words[11]; };
static_assert(sizeof(StackFields)==0x1C && sizeof(OrderFields)==0x30,"stock order extents");
bool CoveredRetirement(const Memory& m,const Profile& p,Address unit) {
    if (!p.retirementMethod) return true;
    Address vtable=0,method=0;
    return Read(m,unit,0,vtable) && Read(m,vtable,0x30,method) && method==p.retirementMethod;
}
bool MissileProfile(const Memory& m, const Profile& p, Address unit) {
    Address type=0, desc=0, engine=0, movement=0, movementEngine=0, text=0, impact=0;
    std::uint32_t flags=0, scriptFlags=0;
    char name[12]{};
    return CoveredRetirement(m,p,unit) && Read(m,unit,0x7C,type) && type==p.projectileId &&
        Read(m,unit,0x90,desc) && Read(m,desc,0x14,engine) && engine==p.projectileEngine &&
        Read(m,unit,0x54,movement) && Read(m,movement,0x14,movementEngine) && (!p.movementEngine || movementEngine==p.movementEngine) &&
        Read(m,movementEngine,0x24,flags) && !(flags & 4) && (!p.requireStockMovementFlags || flags==2) &&
        // Script descriptor is EMBEDDED at engine+90 (4DCF66 ADD EBX,90),
        // not a pointer to another descriptor. +90 is text, +94 flags.
        Read(m,engine,0x90,text) && Read(m,engine,0x94,scriptFlags) && scriptFlags==p.scriptFlags &&
        m.Read(text,name,sizeof(name)) && name[11]==0 && _stricmp(name,"make_attack")==0 &&
        Read(m,p.impactGlobal,0,impact) && impact==p.impactFunction;
}
}
Capture Inspect(const Memory& m, const Profile& p, Address world, Address catalog, Address actor, std::uint32_t actorId) {
    Capture out;
    out.failure="inspect-admission/world";
    if (!p.exactExecutable || !p.effectivePackage || !p.lifecycleBound || !actor || !Representable(actorId) || !WorldMatches(m,p,world)) return out;
    Address vtable=0, head=0, node=0;
    out.failure="catalog-header";
    if (!Read(m,catalog,0,vtable) || !vtable ||
        (vtable!=p.allUnitsVtable && vtable!=p.stockAllUnitsVtable) ||
        !Read(m,catalog,0x20,head) || !head || !Read(m,head,0,node)) return out;
    std::set<Address> nodes, units, orders;
    std::set<std::uint32_t> ids;
    QueryTree tree(m,catalog);
    bool foundActor=false;
    while (node!=head) {
        out.failure="catalog-node";
        if (nodes.size()>=65536 || !nodes.insert(node).second) return out;
        UnitNode entry{};UnitFields fields{};
        if(!Read(m,node,0,entry) || !entry.unit || !units.insert(entry.unit).second ||
           !Read(m,entry.unit,0x70,fields) || fields.world!=world || !fields.id || !ids.insert(fields.id).second)return out;
        const Address unit=entry.unit;const auto id=fields.id;
        if(entry.id!=id || !tree.Contains(id))return out;
        ++out.units;
        if (unit==actor) {
            out.failure="actor-identity/descriptor/retirement";
            if (id!=actorId || !CoveredRetirement(m,p,unit) || (fields.flags&4) || (p.actorDescriptor && fields.description!=p.actorDescriptor)) return out;
            foundActor=true;
        }
        for (unsigned channel=0; channel<3; ++channel) {
            out.failure="order-stack";
            const Address stack=fields.stacks[channel];
            Address link=0;StackFields stackFields{};
            if (!stack) continue;
            if (!Read(m,stack,4,stackFields) || stackFields.owner!=unit || !stackFields.sentinel || !Read(m,stackFields.sentinel,0,link)) return out;
            const Address sentinel=stackFields.sentinel;
            std::set<Address> links;
            while (link!=sentinel) {
                out.failure="order-node";
                OrderNode orderNode{};OrderFields orderFields{};
                std::uint32_t phase=0,shooter=0;
                if (links.size()>=65536 || orders.size()>=262144 || !links.insert(link).second || !Read(m,link,0,orderNode) || !orderNode.order || !orders.insert(orderNode.order).second || !Read(m,orderNode.order,0,orderFields)) return out;
                const Address order=orderNode.order;
                const auto kind=orderFields.words[3],terminal=orderFields.words[10];
                ++out.orders;
                if (unit==actor) {
                    out.failure="actor-order";
                    if (kind==11 && !Read(m,order,0x50,phase)) return out;
                    if (kind==11 && phase==0x1000 && p.animationVtable && orderFields.vtable!=p.animationVtable) return out;
                    if (kind==10 || terminal==0x1008 || (kind==11 && phase==0x1000)) ++out.actorPending;
                }
                if (kind==3 && terminal==0x100A) {
                    out.failure="missile-owner/profile";
                    if (!Read(m,order,0x5C,shooter)) return out;
                    if (shooter==actorId) {
                        if (!Representable(id)) return out;
                        if (p.missileVtable && orderFields.vtable!=p.missileVtable) return out;
                        if (!MissileProfile(m,p,unit)) return out;
                        ++out.missiles; // Removal requests and released flags never clear this.
                        out.missileIds.push_back(id);
                    }
                }
                out.failure="order-next";
                link=orderNode.next;
            }
        }
        out.failure="catalog-next";
        node=entry.next;
    }
    out.failure="actor-membership/final-world";
    if (!foundActor || !WorldMatches(m,p,world)) return out;
    out.result = out.actorPending || out.missiles ? Result::Busy : Result::Settled;
    out.failure=nullptr;
    return out;
}
void Lifecycle::Invalidate() { ++generation_; ++revision_; coherent_=false; world_=catalog_=0; retiredIds_.clear(); }
bool Lifecycle::Attach(const Memory& m,const Profile& p,int status,int mode,Address world,Address catalog) {
    return AttachWorld(m,p,status==0 && (mode==0 || mode==3),world,catalog);
}
bool Lifecycle::AttachCreated(const Memory& m,const Profile& p,int mode,Address world,Address catalog) {
    return AttachWorld(m,p,mode==0,world,catalog);
}
bool Lifecycle::AttachWorld(const Memory& m,const Profile& p,bool accepted,Address world,Address catalog) {
    Invalidate();
    if (depth_ || !retirements_.empty() || !accepted || !p.exactExecutable || !p.effectivePackage || !p.lifecycleBound || !catalog || !WorldMatches(m,p,world)) return false;
    world_=world; catalog_=catalog; coherent_=true;
    // Every Query reconstructs current native lists, including directly restored orders.
    return true;
}
void Lifecycle::EnterOperation() { ++revision_; if (depth_==UINT_MAX) { Invalidate(); return; } ++depth_; }
void Lifecycle::LeaveOperation() { if (!depth_) { Invalidate(); return; } --depth_; }
void Lifecycle::BeginWorldTeardown() { Invalidate(); EnterOperation(); }
void Lifecycle::IdentityIncoherent() { Invalidate(); }
RetirementToken Lifecycle::BeginRetirement(Address pointer,std::uint32_t id) {
    EnterOperation();
    for (const auto& active:retirements_) if (active.actor==pointer) coherent_=false;
    RetirementToken token{generation_,++serial_,pointer,id};
    if (!pointer || !id) coherent_=false;
    retirements_.push_back(token); return token;
}
void Lifecycle::EndRetirement(RetirementToken token,bool normalReturn) {
    if (retirements_.empty() || retirements_.back().serial!=token.serial) { Invalidate(); return; }
    const auto captured=retirements_.back(); retirements_.pop_back();
    if (!normalReturn || captured.generation!=generation_) coherent_=false;
    else retiredIds_.insert(captured.id);
    // No read through captured.actor: the concrete deleting call has returned.
    LeaveOperation();
}
Capture Lifecycle::Query(const Memory& m,const Profile& p,Address actor,std::uint32_t id) const {
    Capture rejected;
    if (!coherent_) { rejected.failure="lifecycle-not-attached/coherent"; return rejected; }
    if (depth_) { rejected.failure="lifecycle-operation-active"; return rejected; }
    if (!retirements_.empty()) { rejected.failure="lifecycle-retirement-active"; return rejected; }
    if (retiredIds_.count(id)) { rejected.failure="lifecycle-retired-identity"; return rejected; }
    return Inspect(m,p,world_,catalog_,actor,id);
}
bool Lifecycle::ContextAllowed(const Memory& m,const Profile& p,Address world,
                               std::uint64_t generation,std::uint32_t actorId,
                               std::uint32_t projectileId) const {
    // Unlike the settled query, this is intentionally called inside a guarded
    // synchronous callback. It grants no permission to change weapons.
    return coherent_ && generation==generation_ && world && world==world_ &&
        Representable(actorId) && Representable(projectileId) && retirements_.empty() &&
        !retiredIds_.count(actorId) && !retiredIds_.count(projectileId) &&
        p.exactExecutable && p.effectivePackage && p.lifecycleBound &&
        WorldMatches(m,p,world);
}
bool Lifecycle::SnapshotCurrent(const Memory& m,const Profile& p,std::uint64_t generation,std::uint64_t revision) const {
    return coherent_ && !depth_ && retirements_.empty() && generation==generation_ && revision==revision_ &&
        p.exactExecutable && p.effectivePackage && p.lifecycleBound && WorldMatches(m,p,world_);
}
int ShotSnapshot::Begin(const Memory& m,const Profile& p,const Lifecycle& life,Address actor,std::uint32_t actorId) {
    token_=0;ids_.clear();
    if (serial_==static_cast<int>(kMaximumIdentity)) return 0;
    const auto capture=life.Query(m,p,actor,actorId);
    if (capture.result==Result::Unknown) return 0;
    actor_=actor;actorId_=actorId;generation_=life.Generation();revision_=life.Revision();ids_=capture.missileIds;
    token_=++serial_;return token_;
}
int ShotSnapshot::Pending(const Memory& m,const Profile& p,const Lifecycle& life,Address actor,std::uint32_t actorId,int token,std::uint32_t projectileId) const {
    if (!token || token!=token_ || actor!=actor_ || actorId!=actorId_ || !Representable(projectileId) ||
        !life.SnapshotCurrent(m,p,generation_,revision_)) return -1;
    return std::find(ids_.begin(),ids_.end(),projectileId)!=ids_.end()?1:0;
}
void ShotSnapshot::End(int token) { if (token==token_) { token_=0;ids_.clear(); } }


} // namespace MajestyAttackObservation
