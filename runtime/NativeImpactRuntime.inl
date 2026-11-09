// Included in the existing loaded-content/world observer; no parallel hooks or
// world tracker. Native profiles and descriptor policy are Manager generated.
MajestyNativeImpact::Registry impactPolicy;
const MajestyNativeImpact::Profile* impactNative{};
TerminalMissileContext nativeImpactContext;
bool impactPrepared=false,impactBound=false,impactInvoking=false;
using NativeImpactCall=void (__cdecl*)(Word,Word,Word,Word,Word);
NativeImpactCall originalImpact{};
void __cdecl InterceptImpact(Word,Word,Word,Word,Word);

bool PrepareImpactPolicy(const wchar_t* manifest,MajestyBuildId build) {
    impactNative=MajestyNativeImpact::For(build);
    if(!impactNative || !MajestyBooleanRuntime::GuardBodies(impactNative->bodies,impactNative->count))return false;
    std::wstring path(manifest);const auto slash=path.find_last_of(L"\\/");
    if(slash==std::wstring::npos)return false;
    path.resize(slash+1);path+=L"majesty_mod_manager_projectile_interception.bin";
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER size{};DWORD count{};
    bool ok=GetFileSizeEx(file,&size)&&size.QuadPart>=44&&size.QuadPart<=320*1024;
    std::vector<unsigned char> bytes(ok?static_cast<std::size_t>(size.QuadPart):0);
    if(ok)ok=ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&count,nullptr)&&count==bytes.size();
    CloseHandle(file);
    if(!ok||!MajestyNativeImpact::Parse(bytes.data(),bytes.size(),impactPolicy)||
        std::memcmp(impactPolicy.proof.data(),preparedProofDigest,32))return false;
    impactPrepared=true;return true;
}
bool ImpactGate() {
    if(!impactPrepared)return true;
    Word current{};const auto adapter=static_cast<Word>(reinterpret_cast<std::uintptr_t>(&InterceptImpact));
    if(!Read(impactNative->global,0,current))return false;
    if(impactBound)return current==adapter;
    // Install only at this existing, loaded-world admission edge. A stock
    // default or another owner's replacement is never overwritten.
    if(current!=impactNative->original)return false;
    using Set=Word (__cdecl*)(Word);
    const auto previous=reinterpret_cast<Set>(impactNative->setter)(adapter);
    if(previous!=current){Fault("first-fault/impact-binding");return false;}
    originalImpact=reinterpret_cast<NativeImpactCall>(previous);
    profile.impactFunction=adapter;impactBound=true;return true;
}
bool ImpactIdentity(Word unit,Word id,Word world,std::uint64_t generation) {
    if(!unit||!life.ContextAllowed(memory,profile,world,generation,id,id))return false;
    using FindUnit=Word (__thiscall*)(void*,Word);
    Word actual{},owner{},flags{};
    return reinterpret_cast<FindUnit>(nativeProfile->findUnit)(reinterpret_cast<void*>(world),id)==unit &&
        Read(unit,0x70,actual)&&actual==id&&Read(unit,0x94,owner)&&owner==world&&
        Read(unit,0x74,flags)&&!(flags&4);
}
bool ImpactDescriptor(const MajestyNativeImpact::Binding& binding,const TerminalMissileContext& current) {
    Word id{},unitId{},engine{},text{},flags{},movement{},movementEngine{},movementFlags{};
    if(Find(nativeProfile->unitCatalog,binding.projectile.c_str())!=current.description ||
        !Read(current.unit,0x7C,unitId)||unitId!=binding.id ||
        !Read(current.description,4,id)||id!=binding.id ||
        !Read(current.description,0x14,engine)||engine!=current.engine ||
        !Read(engine,0x90,text)||!Read(engine,0x94,flags)||flags ||
        !Read(current.unit,0x54,movement)||!Read(movement,0x14,movementEngine)||
        !Read(movementEngine,0x24,movementFlags)||(movementFlags&4))return false;
    std::vector<char> name(binding.script.size()+1);
    return text&&memory.Read(text,name.data(),name.size())&&!name.back()&&
        !_stricmp(name.data(),binding.script.c_str())&&_stricmp(name.data(),"make_attack");
}
void __cdecl InterceptImpact(Word projectile,Word source,Word target,Word x,Word y) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress());
    const auto current=nativeImpactContext;
    auto fallback=[&] { originalImpact(projectile,source,target,x,y); };
    const auto& c=current.identity;
    if(!originalImpact)return; // Unreachable before stock setter publishes us.
    if(!Owner()||fault||!loadProof.Ready()||impactInvoking||
        caller!=impactNative->terminal+0x5A||current.unit!=projectile||!source||!target||
        !ImpactGate()||!ImpactIdentity(projectile,c.projectile,c.world,c.generation)||
        !ImpactIdentity(source,c.actor,c.world,c.generation)||!ImpactIdentity(target,c.target,c.world,c.generation)) {
        fallback();return;
    }
    struct Invocation { Invocation(){impactInvoking=true;}~Invocation(){impactInvoking=false;} };
    std::string lastProvider;
    for(const auto& binding:impactPolicy.bindings) {
        if(binding.provider==lastProvider||!ImpactDescriptor(binding,current))continue;
        lastProvider=binding.provider;
        MajestyBooleanRuntime::Decision decision;
        { Invocation invocation;decision=MajestyBooleanRuntime::Invoke(binding.provider.c_str(),
              reinterpret_cast<void*>(source),reinterpret_cast<void*>(target)); }
        if(decision==MajestyBooleanRuntime::Decision::Unavailable)continue;
        // Never retry or apply a second outcome after an invalid provider result
        // or loss of native ownership. No exceptional recovery is asserted.
        if(decision==MajestyBooleanRuntime::Decision::InvalidResult||
            !ImpactIdentity(projectile,c.projectile,c.world,c.generation)||
            !ImpactIdentity(source,c.actor,c.world,c.generation)||!ImpactIdentity(target,c.target,c.world,c.generation)) {
            Fault("first-fault/impact-provider");if(logger)logger("Projectile interception provider invalidated its result or native impact ownership.");
            TerminateProcess(GetCurrentProcess(),ERROR_INVALID_DATA);return;
        }
        if(decision!=MajestyBooleanRuntime::Decision::Absorb)continue;
        using Animate=bool (__cdecl*)(Word,Word,Word,Word,Word,Word);
        MajestyNativeImpact::FinishAbsorbed(projectile,reinterpret_cast<Animate>(impactNative->animation),[](Word projectile) {
            Word table{},remove{};
            if(!Read(projectile,0,table)||!Read(table,0x74,remove)||!remove) {
                Fault("first-fault/impact-retirement");TerminateProcess(GetCurrentProcess(),ERROR_INVALID_DATA);return;
            }
            reinterpret_cast<void (__thiscall*)(void*)>(remove)(reinterpret_cast<void*>(projectile));
        });
        return;
    }
    fallback();
}
