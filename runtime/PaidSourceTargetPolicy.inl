// Exact current identity before dereferencing an object retained across native callbacks.
void* PaidWorld() {
    auto* root=*reinterpret_cast<unsigned char**>(g_imageBase+SourceTargetProfile().worldPointer);
    return root ? *reinterpret_cast<void**>(root+4) : nullptr;
}
using PaidWorldLookup=void* (*)();
PaidWorldLookup g_paidWorld=&PaidWorld;
std::uint32_t PaidWord(void* unit,unsigned offset) {
    return *reinterpret_cast<const std::uint32_t*>(static_cast<unsigned char*>(unit)+offset);
}
const char* PaidIdentityRejection(void* unit,std::uint32_t id,void* world,bool living) {
    if(!unit || !id || !world)return "missing-unit-id-or-world";
    if(g_sovereignUnitResolver(id)!=unit)return "id-resolves-to-other-unit";
    if(PaidWord(unit,0x70)!=id)return "full-id-mismatch";
    if(PaidWord(unit,0x74)&0x14)return "retirement-flags";
    if(PaidWord(unit,0x94)!=reinterpret_cast<std::uintptr_t>(world))return "unit-world-mismatch";
    if(living) {
        if(PaidWord(unit,0x84)!=0)return "unit-contained";
        if(PaidWord(unit,0x80)>=8)return "unit-owner-out-of-range";
        if(ReadPackedAttributeValue(unit,0x00555041,0)<=0)return "unit-no-hitpoints";
    }
    return nullptr;
}
bool PaidIdentity(void* unit,std::uint32_t id,void* world,bool living) {
    return PaidIdentityRejection(unit,id,world,living)==nullptr;
}
bool NativePaidLair(void* unit) {
    const auto& p=PaidProfile();
    using Find=void* (__thiscall*)(void*,std::uint32_t);
    void* component=reinterpret_cast<Find>(g_imageBase+p.component_lookup)(static_cast<unsigned char*>(unit)+4,0x4541);
    if(!component)return false;
    struct Reference {
        std::uint32_t words[4]{};
        bool made=false;
        ~Reference(){if(made)reinterpret_cast<void (__thiscall*)(void*)>(g_imageBase+PaidProfile().reference_destroy)(words);}
    } reference;
    try {
        reinterpret_cast<void (__thiscall*)(void*,void*)>(g_imageBase+p.reference_ctor)(reference.words,component);
        reference.made=true;
        void* value=reinterpret_cast<void* (__thiscall*)(void*,void*)>(g_imageBase+p.property_get)(reference.words,reinterpret_cast<void*>(g_imageBase+p.type_name));
        if(!value || PaidWord(value,4)!=3)return false;
        auto** table=*reinterpret_cast<void***>(value);
        void* string=reinterpret_cast<void* (__thiscall*)(void*)>(table[0x30/4])(value);
        if(!string)return false;
        const char* text=*reinterpret_cast<const char**>(string);
        return text && _stricmp(text,"lair")==0;
    } catch(...) {return false;}
}
bool NativePaidHostileVisible(void* target,std::uint32_t player,void* world) {
    const auto& p=PaidProfile();
    const auto owner=PaidWord(target,0x80);
    if(player>=8 || owner>=8 || owner==player)return false;
    auto* masks=static_cast<unsigned char*>(world)+0x128;
    unsigned ownGroups=0,targetGroups=0;
    for(unsigned i=0;i<8;++i) {
        const auto mask=*reinterpret_cast<const std::uint32_t*>(masks+4*i);
        ownGroups+=(mask>>player)&1;targetGroups+=(mask>>owner)&1;
    }
    if(ownGroups!=1 || targetGroups!=1)return false;
    using Team=unsigned (__thiscall*)(void*,std::uint32_t);
    const auto team=reinterpret_cast<Team>(g_imageBase+p.team_lookup);
    if(team(masks,player)==team(masks,owner))return false;
    auto** table=*reinterpret_cast<void***>(target);
    if(reinterpret_cast<std::uintptr_t>(table[0x6C/4])!=g_imageBase+p.visibility)return false;
    return reinterpret_cast<int (__thiscall*)(void*,std::uint32_t)>(table[0x6C/4])(target,player)!=0;
}
using PaidLairPredicate=bool (*)(void*);
using PaidHostilePredicate=bool (*)(void*,std::uint32_t,void*);
PaidLairPredicate g_paidLair=&NativePaidLair;
PaidHostilePredicate g_paidHostileVisible=&NativePaidHostileVisible;
const char* PaidActorsRejection(const PaidRecord& record,const MajestyStockControllers::SovereignTargetActionRecord& action,
    void* source,void* target,void* world) {
    if(world!=g_paidWorld())return "world-changed";
    if(const char* reason=PaidIdentityRejection(source,record.source,world,true))return reason;
    if(!SourceMatchesAction(source,record.player,action))return "source-family-owner-or-level";
    if(record.toolbarControl) {
        const auto* toolbar=ToolbarForControl(record.toolbarControl);
        if(!toolbar||toolbar->panelKey!=action.panelKey||toolbar->actionKey!=action.actionKey)
            return "toolbar-origin-mismatch";
        const int completed=SelectedBuildingLevel(source)-
            (ReadPackedAttributeValue(source,0x02425041,0)==0?1:0);
        if(ReadPackedAttributeValue(source,0x01425041,0)==0||completed<static_cast<int>(toolbar->requiredLevel))
            return "toolbar-source-incomplete-or-level";
    }
    if(const char* reason=PaidIdentityRejection(target,record.target,world,true))return reason;
    if(ReadPackedAttributeValue(target,0x0A555041,0)!=0)return "target-NotSpellTarget";
    if(!g_paidLair(target))return "target-not-lair";
    if(!g_paidHostileVisible(target,record.player,world))return "target-team-or-visibility";
    return nullptr;
}
bool PaidActors(const PaidRecord& record,const MajestyStockControllers::SovereignTargetActionRecord& action,
    void* source,void* target,void* world) {
    return PaidActorsRejection(record,action,source,target,world)==nullptr;
}
void LogPaidClick(const char*,const char*,const PaidRecord&) {}
