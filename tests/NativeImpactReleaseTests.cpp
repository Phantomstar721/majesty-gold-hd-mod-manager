#include "../runtime/AttackObservationProof.h"
#include "../runtime/NativeImpactCompletion.h"
#include "../runtime/AttackObservationContext.h"
#include <stdexcept>
#include <cstdio>

void Require(bool condition) { if(!condition)throw std::runtime_error("projectile release contract failed"); }
int main() {
    try {
        using namespace MajestyAttackObservation;
        for(bool scoped:{false,true})for(int chosen:{7,8}) {
            LoadProof load(scoped);
            for(int i=0;i<6;++i)Require(load.Begin(i));
            for(int i=5;i>=0;--i)Require(load.Complete(i,true));
            Require(!load.Ready());
            Require(load.Begin(6)); Require(load.Complete(6,true));
            if(scoped) {
                Require(!load.Ready());
                Require(load.Begin(chosen));Require(load.Complete(chosen,true));
            }
            Require(load.Ready());
            Require(load.Begin(-2));Require(load.Complete(-2,true));Require(load.Ready());
            Require(!load.Begin(-1));Require(!load.Ready());
        }
        LoadProof premature(true);Require(!premature.Begin(6));
        for(bool animated:{false,true}) {
            unsigned animations=0,removals=0;
            MajestyNativeImpact::FinishAbsorbed(42,[&](unsigned unit,unsigned animation,unsigned callback,unsigned a,unsigned b,unsigned c) {
                ++animations;Require(unit==42&&animation==0x60&&callback==0x1005&&!a&&!b&&!c);return animated;
            },[&](unsigned unit){++removals;Require(unit==42);});
            Require(animations==1&&removals==(animated?0u:1u));
        }
        unsigned reads=0;
        auto unavailable=[&](unsigned,unsigned,unsigned&){++reads;return false;};
        Require(!CaptureTerminalMissile(unavailable,1,2,1,3,4).unit && reads==0);
        Require(!CaptureTerminalMissile(unavailable,1,2,2,3,4).unit && reads==1);
        return 0;
    } catch(const std::exception& e) {std::fprintf(stderr,"%s\n",e.what());return 1;}
}
