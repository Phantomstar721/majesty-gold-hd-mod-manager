#include "../runtime/PaidSourceTargetCommand.h"
#include <cassert>
#include <cstring>
using namespace MajestyPaidSourceTarget;
int main() {
    // Stock prefix is exactly mode/context/player/x/y/target/cost, followed by
    // an independent source. The fixture uses deliberately distinct values.
    const unsigned char expected[]={0x31,0x32,0x33,0x34,0x44,0x33,0x22,0x11,
        3,0,0,0,0x2c,1,0,0,0x90,1,0,0,0x11,1,0,0,0xf4,1,0,0,0x22,2,0,0};
    const Record initial{0x34333231,0x11223344,3,300,400,0x111,500,0x222};
    Payload bytes;assert(Encode(initial,bytes));assert(!std::memcmp(expected,bytes.data(),sizeof(expected)));
    Record restored;assert(Decode(CommandTag,expected,sizeof(expected),restored));
    assert(restored.source==0x222&&restored.target==0x111&&restored.gold==500);
    for(std::size_t n=0;n<PayloadSize+2;++n) {
        if(n==PayloadSize)continue;
        restored=initial;assert(!Decode(CommandTag,bytes.data(),n,restored));
        assert(!restored.source&&!restored.target&&!restored.gold);
    }
    assert(!Decode(0x3F1,bytes.data(),bytes.size(),restored));
    assert(!Decode(CommandTag,nullptr,bytes.size(),restored));
    for(unsigned field=0;field<4;++field) {
        auto bad=initial;
        if(field==0)bad.source=0; if(field==1)bad.target=0x200000;
        if(field==2)bad.player=8; if(field==3)bad.gold=0x80000000;
        assert(!Encode(bad,bytes));for(auto b:bytes)assert(!b);
    }
    auto boundary=initial;boundary.source=0x1FFFFF;boundary.target=0x1FFFFF;
    boundary.gold=0x7FFFFFFF;assert(Encode(boundary,bytes));
    assert(Decode(CommandTag,bytes.data(),bytes.size(),restored));
    assert(restored.source==boundary.source&&restored.gold==boundary.gold);
    auto toolbar=initial;toolbar.toolbarControl=31248;
    ToolbarPayload extended;
    assert(EncodeToolbar(toolbar,extended));
    assert(!std::memcmp(expected,extended.data(),sizeof(expected)));
    assert(Decode(ToolbarCommandTag,extended.data(),extended.size(),restored));
    assert(restored.toolbarControl==31248&&restored.gold==500&&restored.source==initial.source);
    assert(!Encode(toolbar,bytes));
    assert(!Decode(CommandTag,extended.data(),extended.size(),restored));
    assert(!Decode(ToolbarCommandTag,expected,sizeof(expected),restored));
    assert(!restored.source&&!restored.toolbarControl);
    assert(Decode(CommandTag,expected,sizeof(expected),restored));
    assert(restored.toolbarControl==0);
    for(auto id:{0u,65536u,0xffffffffu}) {
        toolbar.toolbarControl=id;assert(!EncodeToolbar(toolbar,extended));
        for(auto byte:extended)assert(!byte);
    }
}
