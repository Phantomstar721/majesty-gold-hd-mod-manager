// Offline asset adapter input: samples the ACTUAL authored sequence core.
// It never connects to Majesty, and emits no image pixels or installable mod.
#include "../runtime/EffectSequence.h"
#include <cstdio>
using namespace MajestyEffectSequence;
int main() {
    Sequence sequence({Profile::AuditedModifiedBeta2,true,true});
    sequence.Reset(1);Owner owner{1,1,1};
    auto ticket=sequence.Release(owner,{0,0},0);
    if(!ticket || !sequence.Placed(ticket,owner,{0,0},600))return 1;
    std::printf("{\"schema\":1,\"period\":100,\"duration\":900,\"frames\":[");
    for(unsigned elapsed=0;elapsed<900;elapsed+=100) {
        const auto batch=sequence.Frame(600+elapsed,{{owner,true}});
        if(batch.size()!=1)return 2;
        const auto& frame=batch[0];
        std::printf("%s{\"phase\":%u,\"xy\":[%d,%d],\"opacity\":%u,\"trail\":[",
                    elapsed?",":"",static_cast<unsigned>(frame.phase),frame.offset.x,frame.offset.y,frame.opacity);
        for(unsigned i=0;i<frame.trailCount;++i)
            std::printf("%s[%d,%d]",i?",":"",frame.trail[i].x,frame.trail[i].y);
        std::printf("]}");
    }
    std::printf("]}\n");
    return 0;
}
