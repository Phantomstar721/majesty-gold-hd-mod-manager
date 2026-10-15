namespace CompactChecks {
using namespace PaidChecks;
void* chosen=nullptr;
int stage=0, setupCalls=0, eventCalls=0, hoverCalls=0;
bool completed=true;
int helpAppendCalls=0;
void __cdecl Append(void*,unsigned control,const unsigned* descriptor,unsigned output) {
    assert(control==31248&&output==9);
    assert(descriptor[0]==g_stockControllerRegistry.panels[0].buildingFamilyId);
    assert(descriptor[3]==3&&descriptor[4]==500);
    assert(g_stockControllerRegistry.sovereignTargetActions[0].requiredLevel==2);
    ++helpAppendCalls;
}
void* Current(){return &playerRecord;}
int Query(void* player,unsigned family,void** out) {
    assert(player==&playerRecord && family==g_stockControllerRegistry.panels[0].buildingFamilyId);
    *out=chosen;return stage;
}
int __fastcall Attribute(void* unit,void*,unsigned key,unsigned fallback) {
    if(key==0x02425041)return completed?1:0;
    return Attributes(unit,nullptr,key,fallback);
}
void __fastcall Setup(void*,void*){++setupCalls;}
void __fastcall Event(void*,void*,unsigned,unsigned,unsigned,unsigned){++eventCalls;}
bool __fastcall Help(void*,void*,unsigned control,unsigned second,unsigned third) {
    assert(control==g_stockControllerRegistry.sovereignTargetActions[0].privateControlId);
    assert(second==7&&third==9);++hoverCalls;return true;
}
void Run() {
    auto& action=g_stockControllerRegistry.sovereignTargetActions[0];
    // The older execution-only fixture has no UI command identity. Supply the
    // nonzero, admitted command identity required for a toolbar-origin record.
    action.privateControlId=31248;
    action.actionKey="example-paid";
    g_stockControllerRegistry.toolbarActions={{action.panelKey,action.actionKey,3,0x63697845,1015,"Example"}};
    const auto& row=g_stockControllerRegistry.toolbarActions[0];
    CompactToolbar::playerLookup=&Current;CompactToolbar::familyLookup=&Query;
    CompactToolbar::controller=reinterpret_cast<LONG>(&parent);
    // x86 thiscall passes the receiver in ECX and arguments on the stack.
    // These fastcall adapters consume the unused EDX slot explicitly, leaving
    // the same stack arguments and callee cleanup as the stock methods.
    CompactToolbar::setup=reinterpret_cast<ControllerSetup>(&Setup);
    CompactToolbar::event=reinterpret_cast<ControllerEvent>(&Event);
    CompactToolbar::appendHelp=&Append;
    streamTable[0x20/4]=reinterpret_cast<void*>(&Visible);
    streamTable[0x68/4]=reinterpret_cast<void*>(&Send);
    streamTable[0x18/4]=reinterpret_cast<void*>(&Help);
    profile.streamMessageSlot=0x68;
    profile.readPackedAttributeRva=reinterpret_cast<std::uintptr_t>(&Attribute);
    sourcePresent=true;targetPresent=true;hostile=true;lair=true;visible=true;retireSpell=false;
    auto type=*reinterpret_cast<unsigned*>(sourceA+0x7C);
    auto typeB=*reinterpret_cast<unsigned*>(sourceB+0x7C);
    for(unsigned index=0;index<3;++index) {
        profile.buildId=static_cast<MajestyBuildId>(index);
        chosen=nullptr;stage=0;
        CompactToolbar::Setup(&parent,nullptr);
        assert(lastVisibleControl==action.privateControlId&&lastVisibleValue);
        assert(disabledControls[action.privateControlId]);
        assert(CompactToolbar::Help(&parent,nullptr,action.privateControlId,7,9));
        *reinterpret_cast<unsigned*>(sourceA+0x7C)=(type&0xffffff)|0x33000000;
        *reinterpret_cast<unsigned*>(sourceB+0x7C)=(typeB&0xffffff)|0x33000000;
        chosen=sourceA;stage=3;completed=true;
        CompactToolbar::Event(&parent,nullptr,0,0,0x02435358,0);
        assert(lastVisibleValue&&!disabledControls[action.privateControlId]);
        assert(CompactToolbar::Source(row)==101);
        assert(CompactToolbar::Help(&parent,nullptr,action.privateControlId,7,9));
        CompactToolbar::Event(&parent,nullptr,0,0,0x02435358,0);
        assert(lastVisibleValue&&!disabledControls[action.privateControlId]);
        chosen=sourceB; // Stock query supplies another surviving qualifying source.
        assert(CompactToolbar::Source(row)==102);
        chosen=nullptr;stage=0;
        CompactToolbar::Event(&parent,nullptr,0,0,0x02435358,0);
        assert(lastVisibleValue&&disabledControls[action.privateControlId]);
        chosen=sourceA;stage=3;completed=false;
        assert(CompactToolbar::Source(row)==0); // raw stage 3 still upgrading
        completed=true;sourcePresent=false;assert(CompactToolbar::Source(row)==0);sourcePresent=true;
        PaidRecord record{action.privateMode,9,1,700,800,303,500,101,action.privateControlId};
        assert(PaidActors(record,action,sourceA,victim,world));
        *reinterpret_cast<unsigned*>(sourceA+0x7C)=(type&0xffffff)|0x32000000;
        assert(!PaidActors(record,action,sourceA,victim,world));
        auto panel=record;panel.toolbarControl=0;
        assert(PaidActors(panel,action,sourceA,victim,world)); // unchanged level-2 origin
        *reinterpret_cast<unsigned*>(sourceA+0x7C)=(type&0xffffff)|0x33000000;
        record.toolbarControl++;
        assert(!PaidActors(record,action,sourceA,victim,world));
        record.toolbarControl=action.privateControlId;
        *reinterpret_cast<unsigned*>(sourceA+0x80)=2;
        assert(!PaidActors(record,action,sourceA,victim,world));
        *reinterpret_cast<unsigned*>(sourceA+0x80)=1;
        targetPresent=false;assert(!PaidActors(record,action,sourceA,victim,world));targetPresent=true;
        assert(CompactToolbar::Help(&parent,nullptr,action.privateControlId,7,9));
        gold=1000;int before=callbackCalls;
        Dispatch(record);assert(gold==500&&callbackCalls==before+1);
        *reinterpret_cast<unsigned*>(sourceA+0x7C)=(type&0xffffff)|0x32000000;
        gold=1000;Dispatch(record);assert(gold==1000&&callbackCalls==before+1);
    }
    assert(setupCalls==3&&eventCalls==9&&hoverCalls==9&&helpAppendCalls==9);
    CompactToolbar::appendHelp=&CompactToolbar::StockHelp;
    *reinterpret_cast<unsigned*>(sourceA+0x7C)=type;
    *reinterpret_cast<unsigned*>(sourceB+0x7C)=typeB;
    CompactToolbar::controller=0;
    CompactToolbar::playerLookup=&CompactToolbar::Player;CompactToolbar::familyLookup=&CompactToolbar::FamilyQuery;
    g_stockControllerRegistry.toolbarActions.clear();
}
}
