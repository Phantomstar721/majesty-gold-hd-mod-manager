// Execute the production repeat-registration path; never launch or call game code.
#include "../runtime/AttackObservationRuntime.cpp"
#include <cassert>
static unsigned registrations=0;
static void RegisterFixture(const char*,void (__cdecl*)(void*)) { ++registrations; }
static DWORD WINAPI OtherThread(void*) {
    return MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr)?1:0;
}
int main() {
    // This process is not a game and cannot satisfy AuditedStartup. The cached
    // installed path must not request that startup-only certificate again.
    for(auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
        prepared=true;installed=true;preparedBuild=build;ownerThread=GetCurrentThreadId();fault=false;
        nativeProfile=ObservationNativeFor(build);impactPrepared=true;
        for(const char* prefix:{"","Fixture"}) {
            packageProof.apiPrefix=prefix;registrations=0;
            assert(MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr));
            assert(MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr));
            assert(registrations==(prefix[0]?16u:0u));
        }
        assert(!MajestyAttackObservation::InstallRuntime(0x500000,&RegisterFixture,nullptr));
        const auto saved=nativeProfile;nativeProfile=nullptr;
        assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr));nativeProfile=saved;
        fault=true;assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr));fault=false;
        HANDLE thread=CreateThread(nullptr,0,&OtherThread,nullptr,0,nullptr);assert(thread);
        WaitForSingleObject(thread,INFINITE);DWORD result=1;GetExitCodeThread(thread,&result);CloseHandle(thread);assert(!result);
        installed=false;assert(!MajestyAttackObservation::InstallRuntime(0x400000,&RegisterFixture,nullptr));
    }
}
