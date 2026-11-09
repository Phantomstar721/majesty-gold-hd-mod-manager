#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <cstring>
#include <vector>
#include "BooleanRuntime.h"
#include "BooleanRuntimeProfiles.h"
#include "FeatureExecutableIdentity.h"

namespace {
using namespace MajestyBooleanRuntime;
const Profile* profile{};
std::uintptr_t makeText{},destroyText{};
DWORD ownerThread{};
bool ownerBound=false;
bool Read(std::uintptr_t p, void* out, std::size_t size) {
    SIZE_T count{};
    return p && size<=UINT32_MAX-p && ReadProcessMemory(GetCurrentProcess(),
        reinterpret_cast<const void*>(p),out,size,&count) && count==size;
}
bool Word(std::uintptr_t p,unsigned offset,std::uint32_t& out) {
    return p && p<=UINT32_MAX-offset && Read(p+offset,&out,4);
}
bool Digest(const unsigned char* bytes,ULONG size,unsigned char* output) {
    BCRYPT_ALG_HANDLE algorithm{};BCRYPT_HASH_HANDLE hash{};
    bool ok=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0;
    if(ok)ok=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0;
    if(ok)ok=BCryptHashData(hash,const_cast<unsigned char*>(bytes),size,0)>=0 &&
        BCryptFinishHash(hash,output,32,0)>=0;
    if(hash)BCryptDestroyHash(hash);
    if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);
    return ok;
}
bool ExactImage(const Profile& p,MajestyBuildId build) {
    if(reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr))!=0x400000)return false;
    wchar_t path[32768]{};const auto length=GetModuleFileNameW(nullptr,path,32768);
    if(!length || length==32768)return false;
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER size{};DWORD count{};unsigned char digest[32]{};
    bool ok=GetFileSizeEx(file,&size) && size.QuadPart>0 && size.QuadPart<=64*1024*1024;
    std::vector<unsigned char> bytes(ok?static_cast<std::size_t>(size.QuadPart):0);
    if(ok)ok=ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&count,nullptr) && count==bytes.size();
    CloseHandle(file);
    if(!ok || !MajestyFeatureImage::Matches(bytes,build))return false;
    for(unsigned i=0;i<p.count;++i) {
        const auto& body=p.bodies[i];bytes.resize(body.size);
        if(!Read(body.address,bytes.data(),bytes.size()) || !Digest(bytes.data(),body.size,digest) ||
            std::memcmp(digest,body.sha256,32))return false;
    }
    return true;
}
}
bool MajestyBooleanRuntime::Prepare(MajestyBuildId build,std::uintptr_t constructString,std::uintptr_t destructString) {
    const auto* candidate=For(build);
    if(profile)return candidate==profile && makeText==constructString && destroyText==destructString && GetCurrentThreadId()==ownerThread;
    if(!candidate || !constructString || !destructString || !ExactImage(*candidate,build))return false;
    profile=candidate;makeText=constructString;destroyText=destructString;ownerThread=GetCurrentThreadId();return true;
}
bool MajestyBooleanRuntime::GuardBodies(const MajestyAttackObservation::ObserverBody* bodies,unsigned count) {
    if(!profile || !bodies || !count || GetCurrentThreadId()!=ownerThread)return false;
    for(unsigned i=0;i<count;++i) {
        std::vector<unsigned char> bytes(bodies[i].size);unsigned char digest[32]{};
        if(!Read(bodies[i].address,bytes.data(),bytes.size()) || !Digest(bytes.data(),bodies[i].size,digest) ||
            std::memcmp(digest,bodies[i].sha256,32))return false;
    }
    return true;
}
bool MajestyBooleanRuntime::BindOwnerThread() {
    if(!profile)return false;
    if(ownerBound)return GetCurrentThreadId()==ownerThread;
    ownerThread=GetCurrentThreadId();ownerBound=true;return true;
}
MajestyBooleanRuntime::Decision MajestyBooleanRuntime::Invoke(const char* symbol,void* source,void* target) {
    if(!profile || !ownerBound || GetCurrentThreadId()!=ownerThread || !symbol || !*symbol || !source || !target)return Decision::Unavailable;
    using Call=void (__thiscall*)(void*);
    using Context=std::uint32_t (__cdecl*)();
    using Construct=void* (__thiscall*)(void*,const void*);
    using String=void* (__thiscall*)(void*,const char*);
    using Present=bool (__thiscall*)(void*,const void*);
    using Lookup=std::uint32_t (__thiscall*)(void*,const void*);
    using Append=void (__thiscall*)(void*,void*);
    using Boolean=void (__thiscall*)(void*,bool);
    using At=void** (__thiscall*)(void*,unsigned);
    using Getter=bool (__thiscall*)(void*);
    const auto context=reinterpret_cast<Context>(profile->context)();
    std::uint32_t dispatcher{},pool{},disabled{};
    if(!Word(context,8,dispatcher) || !dispatcher || !Word(context,0x1C,pool) || !pool ||
        !Word(pool,0xF0,disabled) || disabled)return Decision::Unavailable;
    std::uint32_t text[3]{};
    reinterpret_cast<String>(makeText)(text,symbol);
    const bool present=reinterpret_cast<Present>(profile->present)(reinterpret_cast<void*>(dispatcher),text);
    const auto handle=present?reinterpret_cast<Lookup>(profile->lookup)(reinterpret_cast<void*>(dispatcher),text):0;
    std::uint32_t callback{};
    if(!handle || !Word(handle,0x14,callback) || callback!=profile->vm) {
        reinterpret_cast<Call>(destroyText)(text);return Decision::Unavailable;
    }
    __declspec(align(4)) unsigned char evaluator[0x40]{};
    // Deliberately no catch/retry or invented partial-construction cleanup.
    // These stock helpers expose only their normal-return ownership contract.
    reinterpret_cast<Construct>(profile->construct)(evaluator,text);
    reinterpret_cast<Call>(destroyText)(text);
    std::uint32_t resolved{};std::memcpy(&resolved,evaluator+4,4);
    if(resolved!=handle) {
        reinterpret_cast<Call>(profile->destroy)(evaluator);return Decision::Unavailable;
    }
    reinterpret_cast<Call>(profile->drain)(evaluator+8);
    reinterpret_cast<Boolean>(profile->append)(evaluator+8,false);
    reinterpret_cast<Append>(profile->rebuild)(evaluator+0x24,evaluator+8);
    reinterpret_cast<Append>(profile->addAgent)(evaluator,source);
    reinterpret_cast<Append>(profile->addAgent)(evaluator,target);
    reinterpret_cast<Call>(profile->execute)(evaluator);
    void** entry=reinterpret_cast<At>(profile->resultAt)(evaluator+0x24,0);
    std::uint32_t value{},tag{},table{},getter{};
    const bool valid=Read(reinterpret_cast<std::uintptr_t>(entry),&value,4) &&
        Word(value,4,tag) && tag==6 && Word(value,0,table) && table==profile->table &&
        Word(table,0x64,getter) && getter==profile->getter;
    Decision decision=Decision::InvalidResult;
    if(valid)decision=reinterpret_cast<Getter>(getter)(reinterpret_cast<void*>(value))?Decision::Absorb:Decision::Allow;
    reinterpret_cast<Call>(profile->destroy)(evaluator);
    return decision;
}
