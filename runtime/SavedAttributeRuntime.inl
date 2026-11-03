// Stock HasAttribute then required read, scoped to one fresh AP78 refresh.
// No saved-property insertion, GPL callback, conversion, retained unit or timer.
bool SavedAttributeRowsSelected() {
    return std::any_of(g_runtimeFeatureRegistry.heroInfoRows.begin(),g_runtimeFeatureRegistry.heroInfoRows.end(),
        [](const MajestyRuntimeFeatures::HeroInfoRecord& row){return row.kind==4;});
}
bool ValidateSavedAttributeProfile() {
    if(!SavedAttributeRowsSelected())return true;
    const auto index=MajestySavedAttribute::Index(g_buildProfile->buildId);
    if(index>=3 || g_imageBase!=0x400000)return false;
    for(const auto& window:MajestySavedAttribute::Windows[index]) {
        std::uint32_t hash=2166136261u;
        const auto* bytes=reinterpret_cast<const unsigned char*>(g_imageBase+window.rva);
        for(unsigned i=0;i<window.size;++i)hash=(hash^bytes[i])*16777619u;
        if(hash!=window.hash)return false;
    }
    return true;
}
const MajestySavedAttribute::Profile& SavedAttributeProfile() {
    return MajestySavedAttribute::Profiles[MajestySavedAttribute::Index(g_buildProfile->buildId)];
}
std::uint32_t NativeSavedAttributeComponent(void* unit) {
    return reinterpret_cast<std::uint32_t (__thiscall*)(void*,std::uint32_t)>(
        g_imageBase+SavedAttributeProfile().component)(static_cast<unsigned char*>(unit)+4,0x4541);
}
void NativeSavedAttributeReference(void* reference,std::uint32_t handle) {
    reinterpret_cast<void (__thiscall*)(void*,std::uint32_t)>(
        g_imageBase+SavedAttributeProfile().referenceCtor)(reference,handle);
}
void NativeSavedAttributeReferenceEnd(void* reference) {
    reinterpret_cast<void (__thiscall*)(void*)>(g_imageBase+SavedAttributeProfile().referenceDtor)(reference);
}
bool NativeSavedAttributeExists(void* agent,const MajestyStringView* name) {
    // Native result is AL, not a fresh DWORD in EAX.
    return reinterpret_cast<bool (__thiscall*)(void*,const MajestyStringView*)>(
        g_imageBase+SavedAttributeProfile().exists)(agent,name);
}
void* NativeSavedAttributeRequired(void* agent,const MajestyStringView* name) {
    return reinterpret_cast<void* (__thiscall*)(void*,const MajestyStringView*)>(
        g_imageBase+SavedAttributeProfile().required)(agent,name);
}
using SavedComponent=std::uint32_t (*)(void*);
using SavedReference=void (*)(void*,std::uint32_t);
using SavedReferenceEnd=void (*)(void*);
using SavedExists=bool (*)(void*,const MajestyStringView*);
using SavedRequired=void* (*)(void*,const MajestyStringView*);
SavedComponent g_savedComponent=&NativeSavedAttributeComponent;
SavedReference g_savedReference=&NativeSavedAttributeReference;
SavedReferenceEnd g_savedReferenceEnd=&NativeSavedAttributeReferenceEnd;
SavedExists g_savedExists=&NativeSavedAttributeExists;
SavedRequired g_savedRequired=&NativeSavedAttributeRequired;
bool SavedAttributePositive(void* unit,const std::string& attribute) {
    if(!unit || attribute.empty())return false;
    const auto* native=static_cast<const unsigned char*>(unit);
    if((*reinterpret_cast<const std::uint32_t*>(native+0x74)&0x14) ||
        ReadPackedAttributeValue(unit,0x00555041u,0)<=0)return false;
    const auto handle=g_savedComponent(unit);
    if(!handle || handle==0xFFFFFFFFu)return false;
    struct Reference {
        std::uint32_t words[4]{};
        bool constructed=false;
        ~Reference(){if(constructed)g_savedReferenceEnd(words);}
    } reference;
    g_savedReference(reference.words,handle);reference.constructed=true;
    auto* agent=reinterpret_cast<unsigned char*>(reference.words[3]);
    if(!agent || agent[0x38])return false;
    // Borrowed narrow key; no string destructor may own this registry storage.
    const MajestyStringView key={attribute.c_str(),0,static_cast<std::uint32_t>(attribute.size())};
    if(!g_savedExists(agent,&key))return false;
    // HasAttribute and the getter only read this tree; neither invokes gameplay
    // callbacks between the existence test and the guarded typed value read.
    auto* value=static_cast<const unsigned char*>(g_savedRequired(agent,&key));
    if(!value || *reinterpret_cast<const std::uint32_t*>(value+4)!=1)return false;
    return *reinterpret_cast<const std::int32_t*>(value+8)>0;
}
