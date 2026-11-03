#include "../runtime/EffectSequence.h"
#include <cstdio>
#include <cstdlib>
using namespace MajestyEffectSequence;
static void Check(bool ok,int line) {if(!ok){std::fprintf(stderr,"effect sequence failure line %d\n",line);std::exit(1);}}
#define CHECK(x) Check((x),__LINE__)
static Support Supported() {return {Profile::AuditedModifiedBeta2,true,true};}
static Owner actor{7,11,3};
static std::vector<OwnerSample> current{{actor,true}};
int main() {
    // Concrete authored sequence arithmetic, not simulated engine acceptance.
    Sequence s(Supported());s.Reset(3);
    auto t=s.Release(actor,{20,30},0);CHECK(t);
    auto frame=s.Frame(599,current);CHECK(frame.size()==1 && frame[0].phase==Phase::Departure);
    CHECK(!s.Release(actor,{20,30},599)); // duplicate cannot restart the lifetime
    CHECK(s.Placed(t,actor,{100,200},600));
    CHECK(!s.Placed(t,actor,{999,999},600)); // repeated commit cannot move the anchor
    auto a=s.Frame(600,current)[0];CHECK(a.phase==Phase::Meteor && a.offset.x==-160 && a.offset.y==-240);
    auto b=s.Frame(725,current)[0],c=s.Frame(850,current)[0],d=s.Frame(975,current)[0];
    CHECK(b.offset.x-a.offset.x<c.offset.x-b.offset.x);
    CHECK(c.offset.x-b.offset.x<d.offset.x-c.offset.x);
    CHECK(d.offset.x<0 && d.offset.y<0 && d.trailCount==8);
    CHECK(d.anchor.x==100 && d.anchor.y==200 && d.trail[7].y<d.offset.y);
    auto hit=s.Frame(1100,current)[0];CHECK(hit.phase==Phase::Impact && hit.offset.x==0 && hit.offset.y==0);
    CHECK(s.Frame(1350,current)[0].opacity==750);
    CHECK(s.Frame(1500,current).empty());CHECK(!s.Placed(t,actor,{0,0},1500));

    // Refusal, interruption, removed identity and failed frame validation leave
    // no deferred completion/attack/movement event to execute.
    for(int kind=0;kind<7;++kind) {
      for(bool afterPlacement: {false,true}) {
        Sequence q(Supported());q.Reset(3);auto id=q.Release(actor,{1,2},0);CHECK(id);
        if(afterPlacement)CHECK(q.Placed(id,actor,{4,5},500));
        if(kind==0)q.Cancel(id);
        if(kind==1)q.Removed(actor);
        if(kind==2)q.Reset(4);
        auto owners=current;
        if(kind==3)owners[0].livingOutside=false;
        if(kind==4)owners[0].owner.life++;
        if(kind==5)owners.clear();
        if(kind==6)owners.push_back(owners[0]);
        CHECK(q.Frame(600,owners).empty());CHECK(!q.Placed(id,actor,{4,5},600));
      }
    }
    Sequence q(Supported());q.Reset(3);auto first=q.Release(actor,{1,2},0);
    CHECK(q.Frame(1200,current).empty());CHECK(!q.Placed(first,actor,{4,5},1200));
    q.Reset(3);auto second=q.Release(actor,{1,2},0);CHECK(second!=first);
    CHECK(!q.Placed(first,actor,{4,5},0));
    CHECK(q.Placed(second,actor,{4,5},600));CHECK(q.Frame(599,current).empty()); // clock reversal
    q.Reset(3);auto third=q.Release(actor,{1,2},0);CHECK(third);
    CHECK(!q.Placed(third,{7,12,3},{4,5},600)); // owner mismatch doesn't transfer authority
    CHECK(q.Frame(5000,current).empty()); // lag doesn't replay impact
    for(Support caps: {Support{},Support{Profile::AuditedModifiedBeta2,false,true},
                       Support{Profile::AuditedModifiedBeta2,true,false},
                       Support{Profile::Unsupported,true,true}}) {
        Sequence unsupported(caps);unsupported.Reset(3);CHECK(!unsupported.Release(actor,{0,0},0));
    }
    Sequence invalid(Supported(),Timing{1200,0,200,200});CHECK(!invalid.Ready());
    Sequence bounds(Supported());bounds.Reset(3);
    CHECK(!bounds.Release({2097152,1,3},{0,0},0));CHECK(!bounds.Release({1,1,4},{0,0},0));
    for(unsigned i=1;i<=128;++i)CHECK(bounds.Release({i,1,3},{0,0},0));
    CHECK(!bounds.Release({129,1,3},{0,0},0));
    return 0;
}
