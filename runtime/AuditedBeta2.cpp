#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <cstdint>
#include <cstring>
#include <vector>
#include "AuditedBeta2.h"
#include "ObserverBodyProfiles.h"
#include "CastBodyProfiles.h"
#include "ActionBodyProfiles.h"
#include "ImageBodyProfiles.h"
#include "AttackObservationNativeProfiles.h"
namespace {
bool Read(std::uint32_t address,void* bytes,std::size_t size) {
    SIZE_T copied{};
    return address&&size<=UINT32_MAX-address&&ReadProcessMemory(GetCurrentProcess(),
        reinterpret_cast<void*>(address),bytes,size,&copied)&&copied==size;
}
bool HashBodies(const MajestyAttackObservation::ObserverBody* bodies,std::size_t count) {
    if(!bodies)return false;
    BCRYPT_ALG_HANDLE algorithm{};
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return false;
    bool ok=true;
    for(std::size_t i=0;ok&&i<count;++i) {
        std::vector<unsigned char> bytes(bodies[i].size);unsigned char digest[32]{};
        BCRYPT_HASH_HANDLE hash{};
        ok=Read(bodies[i].address,bytes.data(),bytes.size())&&
            BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0;
        if(ok)ok=BCryptHashData(hash,bytes.data(),static_cast<ULONG>(bytes.size()),0)>=0&&
            BCryptFinishHash(hash,digest,sizeof(digest),0)>=0&&
            !std::memcmp(digest,bodies[i].sha256,sizeof(digest));
        if(hash)BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm,0);return ok;
}
bool ActionBodies(MajestyBuildId build) {
    const auto* bodies=MajestyCheckedPlacement::ActionBodiesFor(build);if(!bodies)return false;
    for(unsigned i=0;i<MajestyCheckedPlacement::ActionBodyCount;++i) {
        std::vector<unsigned char> bytes(bodies[i].size);if(!Read(bodies[i].address,bytes.data(),bytes.size()))return false;
        std::uint32_t hash=2166136261u;for(auto byte:bytes)hash=(hash^byte)*16777619u;
        if(hash!=bodies[i].hash)return false;
    }
    return true;
}
}
bool MajestyCheckedPlacement::AuditedStartup(MajestyBuildId build) {
    using namespace MajestyAttackObservation;
    if(reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr))!=0x400000)return false;
    const auto* profile=ObservationNativeFor(build);if(!profile)return false;
    // First called at preparation, before this provider changes its entries.
    // Subsequent installers retain that certificate because our own hooks
    // replace some bodies. Each installer still guards its own write sites.
    static bool certified=false;static MajestyBuildId certifiedBuild{};
    if(certified&&certifiedBuild!=build)return false;
    if(!certified) {
        if(!HashBodies(ObserverBodiesFor(build),ObserverBodyCount)||
            !HashBodies(CastBodiesFor(build),CastBodyCount)||
            !HashBodies(ImageBodiesFor(build),ImageBodyCount)||!ActionBodies(build))return false;
        certifiedBuild=build;certified=true;
    }
    std::uint32_t runtime{},attached{},current{};
    return Read(profile->runtimeGlobal,&runtime,4)&&(!runtime||(runtime<=UINT32_MAX-0x14&&
        Read(runtime+4,&attached,4)&&Read(runtime+0x10,&current,4)&&!attached&&!current));
}
