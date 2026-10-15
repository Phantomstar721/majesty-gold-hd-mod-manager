// Stock AP92 setup/event/hover/command lifecycle. No clock polling or diagnostics.
#include "CompactToolbarDiagnostic.h" // Shared exact vtable/code evidence only.
namespace CompactToolbar {
constexpr unsigned queryRvas[]={0x44840,0x45750,0x45670};
constexpr unsigned queryHashes[]={0x4c826811,0xfc1f75eb,0xa05a2f35};
constexpr unsigned helpRvas[]={0xac620,0xacf10,0xad4c0};
constexpr unsigned helpHashes[]={0xe51b765d,0x962d59ca,0xa69e4623};
using AppendHelp=void (__cdecl*)(void*,unsigned,const unsigned*,unsigned);
void StockHelp(void* panel,unsigned control,const unsigned* descriptor,unsigned output) {
    reinterpret_cast<AppendHelp>(g_imageBase+helpRvas[static_cast<unsigned>(g_buildProfile->buildId)])(
        panel,control,descriptor,output);
}
AppendHelp appendHelp=&StockHelp;
void* table[9]{};
LONG controller=0;
bool registered=false;
ControllerSetup setup=nullptr;
ControllerControl command=nullptr;
ControllerEvent event=nullptr;
using Hover=bool (__thiscall*)(void*,unsigned,unsigned,unsigned);
Hover hover=nullptr;

const MajestyStockControllers::SovereignTargetActionRecord* Action(
    const MajestyStockControllers::ToolbarActionRecord& row) {
    for(const auto& a:g_stockControllerRegistry.sovereignTargetActions)
        if(a.panelKey==row.panelKey&&a.actionKey==row.actionKey)return &a;
    return nullptr;
}
void* Player() {
    auto* manager=reinterpret_cast<void* (__cdecl*)()>(g_imageBase+g_buildProfile->uiManagerRva)();
    return manager?reinterpret_cast<void* (__thiscall*)(void*)>(g_imageBase+g_buildProfile->getCurrentPlayerRva)(manager):nullptr;
}
int FamilyQuery(void* player,unsigned family,void** source) {
    const auto index=static_cast<unsigned>(g_buildProfile->buildId);
    using Query=int (__thiscall*)(void*,unsigned,void**);
    return reinterpret_cast<Query>(g_imageBase+queryRvas[index])(player,family,source);
}
using PlayerLookup=void* (*)();
using FamilyLookup=int (*)(void*,unsigned,void**);
PlayerLookup playerLookup=&Player;
FamilyLookup familyLookup=&FamilyQuery;
// Returned pointer is consumed on this call stack only, never retained by UI.
unsigned Source(const MajestyStockControllers::ToolbarActionRecord& row) {
    const auto* panel=g_stockControllerRegistry.FindPanelByKey(row.panelKey);
    auto* player=playerLookup();
    if(!panel||!player)return 0;
    void* source=nullptr;
    const int level=familyLookup(player,panel->buildingFamilyId,&source);
    if(level<static_cast<int>(row.requiredLevel)||!source)return 0;
    const auto id=PaidWord(source,0x70);
    if(!PaidIdentity(source,id,g_paidWorld(),true))return 0;
    const int completed=SelectedBuildingLevel(source)-(ReadPackedAttributeValue(source,0x02425041,0)==0?1:0);
    if(ReadPackedAttributeValue(source,0x01425041,0)==0||completed<static_cast<int>(row.requiredLevel))return 0;
    return id;
}
void Refresh(void* object) {
    if(reinterpret_cast<std::uintptr_t>(object)!=static_cast<unsigned>(controller))return;
    const auto c=static_cast<unsigned>(controller);
    for(const auto& row:g_stockControllerRegistry.toolbarActions) {
        const auto* a=Action(row);if(!a)continue;
        const bool available=Source(row)!=0;
        // Literal stock panel presentation helper, controlling our own cloned
        // stock button. Stock controls and their presentation counters are untouched.
        SetControllerControlVisible(c,a->privateControlId,true);
        SendControllerMessage(c,a->privateControlId,0x0A,available?0u:1u,0);
    }
}
void __fastcall Setup(void* object,void*) { setup(object);Refresh(object); }
void __fastcall Event(void* object,void*,unsigned source,unsigned category,unsigned attribute,unsigned payload) {
    event(object,source,category,attribute,payload);
    if(attribute==0x02435358||attribute==0x09425041)Refresh(object);
}
bool __fastcall Help(void* object,void*,unsigned control,unsigned second,unsigned third) {
    const auto* row=ToolbarForControl(control);
    if(!row)return hover(object,control,second,third);
    // Preserve the stock base-hover followed by stock descriptor-help ordering.
    auto* panel=*reinterpret_cast<void**>(static_cast<unsigned char*>(object)+0x24);
    if(!panel)return false;
    auto** vtable=*reinterpret_cast<void***>(panel);
    const bool shown=reinterpret_cast<Hover>(vtable[0x18/4])(panel,control,second,third);
    const auto* action=Action(*row);
    const auto* sourcePanel=g_stockControllerRegistry.FindPanelByKey(row->panelKey);
    if(shown&&action&&sourcePanel) {
        // The helper consumes only family, required stage and price. A local
        // descriptor preserves the independent level-2 building-panel action.
        const unsigned descriptor[]={sourcePanel->buildingFamilyId,0,0,
            row->requiredLevel,action->sovereignGoldCost};
        appendHelp(panel,control,descriptor,third);
    }
    return shown;
}
int __fastcall Command(void* object,void*,unsigned control) {
    const auto* row=ToolbarForControl(control);
    if(!row)return command(object,control);
    if(reinterpret_cast<std::uintptr_t>(object)!=static_cast<unsigned>(controller))return 0;
    const auto* action=Action(*row);
    const unsigned source=Source(*row);
    if(!action||!source||StockCurrentPlayerGold()<static_cast<int>(action->sovereignGoldCost)) {
        Refresh(object);return 0;
    }
    g_pendingToolbarControl=control;
    InterlockedExchange(&g_pendingSovereignBuilding,static_cast<LONG>(source));
    g_pendingSovereignAction=action;
    reinterpret_cast<void (__cdecl*)(unsigned)>(g_imageBase+g_buildProfile->sovereignSpellClickRva)(control);
    return 0;
}
bool Capture(unsigned value) {
    if(g_stockControllerRegistry.toolbarActions.empty()||!value)return true;
    const auto index=static_cast<unsigned>(g_buildProfile->buildId);
    if(index>=3)return false;
    const auto& p=MajestyCompactDiagnostic::profiles[index];
    auto*** object=reinterpret_cast<void***>(value);auto** stock=*object;
    if(reinterpret_cast<std::uintptr_t>(stock)!=g_imageBase+p.table)return true;
    for(unsigned i=0;i<9;++i)
        if(reinterpret_cast<std::uintptr_t>(stock[i])!=g_imageBase+p.slots[i])return false;
    if(MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(stock[1]),0x89)!=p.setupHash||
       MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(stock[8]),0x43)!=p.eventHash||
       MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(g_imageBase+queryRvas[index]),0x146)!=queryHashes[index]||
       MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(g_imageBase+helpRvas[index]),0xf0)!=helpHashes[index])return false;
    if(!registered) {
        std::memcpy(table,stock,sizeof(table));
        if(!MajestyControllerLifecycle::RegisterManagedVtable(table,stock,9,&controller,nullptr,nullptr))return false;
        setup=reinterpret_cast<ControllerSetup>(stock[1]);hover=reinterpret_cast<Hover>(stock[2]);
        command=reinterpret_cast<ControllerControl>(stock[3]);event=reinterpret_cast<ControllerEvent>(stock[8]);
        table[1]=reinterpret_cast<void*>(&Setup);table[2]=reinterpret_cast<void*>(&Help);
        table[3]=reinterpret_cast<void*>(&Command);table[8]=reinterpret_cast<void*>(&Event);
        registered=true;
    }
    controller=static_cast<LONG>(value);*object=table;
    return true;
}
}
const MajestyStockControllers::ToolbarActionRecord* ToolbarForControl(std::uint32_t control) {
    for(const auto& row:g_stockControllerRegistry.toolbarActions) {
        const auto* action=CompactToolbar::Action(row);
        if(action&&action->privateControlId==control)return &row;
    }
    return nullptr;
}
