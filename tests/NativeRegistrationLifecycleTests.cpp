// Data-only executable fixtures. Never calls game code or loads user profiles.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <cassert>
#include <fstream>
#include <vector>
#include <cstdio>
static HMODULE FixtureModuleHandle(LPCWSTR) { return reinterpret_cast<HMODULE>(0x400000); }
#define GetModuleHandleW FixtureModuleHandle
#include "../runtime/NativeImpactRuntime.cpp"
#undef GetModuleHandleW
extern "C" unsigned char GogFixtureBytes[0x500000];

// The prepared-package boundary is seeded below. Body guards still compare
// actual fixture bytes; no evaluator or native game function is executed.
bool MajestyBooleanRuntime::GuardBodies(const MajestyAttackObservation::ObserverBody* bodies,unsigned count) {
    for(unsigned i=0;i<count;++i) {
        BCRYPT_ALG_HANDLE alg{}; unsigned char digest[32]{};
        if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return false;
        const auto status=BCryptHash(alg,nullptr,0,reinterpret_cast<PUCHAR>(bodies[i].address),bodies[i].size,digest,32);
        BCryptCloseAlgorithmProvider(alg,0);
        if(status<0 || std::memcmp(digest,bodies[i].sha256,32))return false;
    }
    return true;
}
bool MajestyBooleanRuntime::BindOwnerThread() { return true; }
MajestyBooleanRuntime::Decision MajestyBooleanRuntime::Invoke(const char*,void*,void*) { return Decision::Unavailable; }
static void RegisterFixture(const char*,void (__cdecl*)(void*)) {}
static std::vector<std::string> logRows;
static void Log(const char* line) { logRows.emplace_back(line); std::puts(line); }
static bool __stdcall NoGameBcd(const void*) { return false; }
static bool __stdcall SuccessfulFixtureBcd(const void*) { return true; }
static DWORD WINAPI WrongThread(void*) {
    return MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log)?1:0;
}
int main(int argc,char** argv) {
    if(argc!=3)return 2;
    const auto build=static_cast<MajestyBuildId>(std::atoi(argv[2]));
    std::ifstream file(argv[1],std::ios::binary|std::ios::ate);
    if(!file)return 3;
    std::vector<char> bytes(static_cast<size_t>(file.tellg()));
    file.seekg(0);file.read(bytes.data(),bytes.size());
    const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(bytes.data());
    const auto* pe=reinterpret_cast<const IMAGE_NT_HEADERS32*>(bytes.data()+dos->e_lfanew);
    if(pe->OptionalHeader.ImageBase!=0x400000 || pe->OptionalHeader.SizeOfImage>0x500000 || GogFixtureBytes!=reinterpret_cast<void*>(0x400000))return 4;
    std::memset(GogFixtureBytes,0,0x500000);
    std::memcpy(GogFixtureBytes,bytes.data(),pe->OptionalHeader.SizeOfHeaders);
    const auto* sections=IMAGE_FIRST_SECTION(pe);
    for(unsigned i=0;i<pe->FileHeader.NumberOfSections;++i)
        std::memcpy(GogFixtureBytes+sections[i].VirtualAddress,bytes.data()+sections[i].PointerToRawData,sections[i].SizeOfRawData);
    prepared=true;preparedBuild=build;impactPrepared=true;
    // Same empty actor-binding contract used by the interception-only release.
    assert(packageProof.actor.empty());
    assert(MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log));
    assert(installed);
    void* before[kObservationHookCount]{};
    std::memcpy(before,original,sizeof(before));
    assert(MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log));
    Word worldSlots[8]{};
    *reinterpret_cast<Word*>(nativeProfile->runtimeGlobal)=reinterpret_cast<Word>(worldSlots);
    worldSlots[1]=0x12345678;worldSlots[4]=0x23456789;
    if(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log)) {
        std::fprintf(stderr,"FAIL: installed runtime rejects stock table re-registration with an active world (profile %u)\n",unsigned(build));return 10;
    }
    assert(std::memcmp(before,original,sizeof(before))==0);
    preparedBuild=static_cast<MajestyBuildId>((unsigned(build)+1)%3);
    assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log));
    preparedBuild=build;
    HANDLE thread=CreateThread(nullptr,0,&WrongThread,nullptr,0,nullptr);
    assert(thread);WaitForSingleObject(thread,INFINITE);DWORD result=1;
    GetExitCodeThread(thread,&result);CloseHandle(thread);assert(result==0);
    fault=true;assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log));fault=false;
    assert(!MajestyAttackObservation::InstallRuntime(0x500000,&RegisterFixture,&Log));
    // Replay both real stock bundles through the production hook, with only
    // the original game loader replaced by a successful nonexecuting stub.
    for(const char* fixtureVariable:{"MAJESTY_BCD_GAME","MAJESTY_BCD_GOG_GAME"}) {
    const char* fixtureGame=std::getenv(fixtureVariable);
    assert(fixtureGame);
    const char* relative[]={"Data/Bytecode.bcd","DataMX/MX_Compatibility.bcd",
        "DataMX/MX_Build.bcd","DataMX/MX_Data.bcd","DataMX/MX_Decision.bcd","DataMX/MX_Task.bcd"};
    packageProof.digests.clear();
    for(const char* path:relative) {
        const auto full=std::string(fixtureGame)+"/"+path;
        HANDLE input=CreateFileA(full.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
        assert(input!=INVALID_HANDLE_VALUE);unsigned char rawHash[32]{};
        assert(Digest(input,rawHash));CloseHandle(input);
        std::array<unsigned char,32> hash{};std::memcpy(hash.data(),rawHash,32);
        packageProof.digests.push_back(hash);
    }
    packageProof.protectedNames={"acid_bolt_hit"};
    original[10]=reinterpret_cast<void*>(&SuccessfulFixtureBcd);
    for(const char* prefix:{"/","/SDK/OriginalQuests/"}) {
        fault=false;loadProof=LoadProof(true);batchOwnership.Reset();categoryFile=true;
        for(int i=5;i>=0;--i) {
            const auto path=std::string(fixtureGame)+prefix+relative[i];
            if(i==5 && std::strlen(prefix)>1) {
                std::ifstream sdkInput(path,std::ios::binary|std::ios::ate);
                assert(sdkInput);std::vector<unsigned char> data(static_cast<size_t>(sdkInput.tellg()));
                sdkInput.seekg(0);sdkInput.read(reinterpret_cast<char*>(data.data()),data.size());
                MajestyBcdOwnership::Definitions definitions;
                assert(MajestyBcdOwnership::ReadDefinitions(data.data(),data.size(),definitions));
                const MajestyBcdOwnership::Key* rejected=nullptr;const char* reason=nullptr;
                // Pre-fix classification was optional, before any generated
                // owner. Reproduce the reported rejection with the real file.
                assert(!batchOwnership.Admit(definitions,packageProof.protectedNames,false,false,&rejected,&reason));
                assert(std::string(reason)=="optional-protected-definition-not-shadowed");
                assert(rejected && rejected->second=="Acid_Bolt_Hit");
            }
            const Word filename[]={reinterpret_cast<Word>(path.c_str()),0,static_cast<Word>(path.size())};
            assert(Bcd(filename));assert(!fault);
        }
        assert(loadProof.DiagnosticState().completed==6);
        assert(loadProof.Begin(6));assert(loadProof.Complete(6,true));
        assert(loadProof.Begin(8));assert(loadProof.Complete(8,true));assert(loadProof.Ready());
    }
    unsigned char unknown[32]{};assert(packageProof.Find(unknown)==-1);
    auto saved=packageProof.digests[0];packageProof.digests[0][0]^=1;
    const auto sdkPath=std::string(fixtureGame)+"/SDK/OriginalQuests/DataMX/MX_Task.bcd";
    HANDLE sdkFile=CreateFileA(sdkPath.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    assert(sdkFile!=INVALID_HANDLE_VALUE);unsigned char sdkHash[32]{};
    assert(Digest(sdkFile,sdkHash));CloseHandle(sdkFile);
    assert(packageProof.Find(sdkHash)==-1);packageProof.digests[0]=saved;
    categoryFile=false;fault=false;packageProof={};
    }
    // First-time late installation remains refused, even after the correction.
    installed=false;assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,&Log));
#if defined(MAJESTY_REGISTRATION_DIAGNOSTIC)
    // Full ring keeps only the most recent sixteen script-load records.
    for(unsigned i=0;i<40;++i){char row[80]{};std::snprintf(row,sizeof(row),"history-test-%u",i);diagnosticHistory.Add(row);}
    auto historyStart=logRows.size();diagnosticHistory.Dump(&Log);
    assert(logRows.size()==historyStart+16);
    assert(logRows[historyStart]=="history-test-24" && logRows.back()=="history-test-39");
    diagnosticHistory={};
    const auto start=logRows.size();
    {
        BcdDiagnostic context;
        DiagnosticPath("fixture\\selected.bcd");
        context.rawIndex=6;context.finalIndex=-1;context.parsed=1;
        { BcdDiagnostic nested;assert(BcdDiagnostic::current==&nested); }
        assert(BcdDiagnostic::current==&context);
        diagnosticHistory={};
        Fault("fixture-first",7,9);
        for(unsigned i=0;i<1000;++i)Fault("must-not-repeat",i);
        assert(logRows.size()==start+5);
        assert(logRows[start].find("reason=fixture-first")!=std::string::npos);
        assert(logRows[start+2].find("raw=6 classified=-1 parsed=1")!=std::string::npos);
        assert(logRows[start+4].find("fixture\\selected.bcd")!=std::string::npos);
    }
    assert(BcdDiagnostic::current==nullptr);
    // Exercise actual loader failure decisions and their before/after state,
    // rather than only passing an invented reason to the logger.
    fault=false;loadProof=LoadProof(true);
    {
        BcdDiagnostic context;context.before=loadProof.DiagnosticState();
        assert(loadProof.Begin(5));assert(loadProof.Complete(5,true));
        context.before=loadProof.DiagnosticState();
        assert(!loadProof.Begin(6));
        Fault("first-fault/bcd-begin",6);
        assert(logRows[logRows.size()-4].find("completed=1")!=std::string::npos);
        assert(logRows[logRows.size()-2].find("completed=1")!=std::string::npos);
    }
    using namespace MajestyBcdOwnership;
    BatchOwnership ownership;Definitions originalDefs{{0,"Protected"}};
    std::set<std::string> names{"protected"};const Key* key=nullptr;const char* why=nullptr;
    assert(!ownership.Admit(originalDefs,names,false,false,&key,&why));
    assert(key && std::string(why)=="optional-protected-definition-not-shadowed");
    ownership.Complete(originalDefs,names,false);
    assert(!ownership.Admit(originalDefs,names,true,false,&key,&why));
    assert(std::string(why)=="generated-after-other-owner");
    ownership.Reset();ownership.Complete(originalDefs,names,true);
    Definitions caseDefs{{0,"PROTECTED"}};
    assert(!ownership.Admit(caseDefs,names,true,false,&key,&why));
    assert(std::string(why)=="case-only-owner-collision");
    // Missing-file integration runs the production BCD hook with a fixture
    // original-call stub. No game function or user package is executed.
    fault=false;loadProof=LoadProof(true);diagnosticHistory={};
    const char absent[]=".\\__MMM_ABSENT_DIAGNOSTIC_FIXTURE__.bcd";
    assert(GetFileAttributesA(absent)==INVALID_FILE_ATTRIBUTES);
    const Word nativeName[]={reinterpret_cast<Word>(absent),0,sizeof(absent)-1};
    original[10]=reinterpret_cast<void*>(&NoGameBcd);
    const auto absentStart=logRows.size();
    assert(!Bcd(nativeName));
    assert(logRows[absentStart].find("reason=first-fault/bcd-begin boundary=Bcd")!=std::string::npos);
    assert(logRows[absentStart+2].find("openAttempted=1")!=std::string::npos);
    assert(logRows[absentStart+4].find(absent)!=std::string::npos);
    // Every non-file fault also retains the originating hook boundary.
    fault=false;const auto readStart=logRows.size();
    { DiagnosticBoundary scope("read-fixture");Value<Word>(nullptr,4); }
    assert(logRows[readStart].find("first-fault/read boundary=read-fixture")!=std::string::npos);
    fault=false;const auto unwindStart=logRows.size();
    try { Guard guard("unwind-fixture");throw 1; } catch(int) {}
    assert(logRows[unwindStart].find("first-fault/unwind boundary=unwind-fixture")!=std::string::npos);
    fault=false;const auto postStart=logRows.size();categoryFile=true;BeforeBcdPostload();categoryFile=false;
    assert(logRows[postStart].find("first-fault/postload-during-file boundary=BeforeBcdPostload")!=std::string::npos);
    fault=false;const auto threadStart=logRows.size();const auto savedOwner=ownerThread;ownerThread=0;
    assert(!Owner("owner-fixture"));ownerThread=savedOwner;
    assert(logRows[threadStart].find("first-fault/thread boundary=owner-fixture")!=std::string::npos);
    assert(logRows.size()==threadStart+1); // no cross-thread proof/container reads
#endif
}
