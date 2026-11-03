#include "../runtime/CheckedPlacementRuntime.cpp"
#include <cassert>
static unsigned registrations=0;
static void RegisterFixture(const char*,void (__cdecl*)(void*)) { ++registrations; }
int main() {
    prepared=false;assert(MajestyCheckedPlacement::InstallPreparedRuntime(nullptr));
    for(auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
        prepared=true;installed=true;preparedBuild=build;
        observation=ObservationNativeFor(build);stateProfile=PlacementStateFor(build);
        config.prefix="Fixture";registrations=0;
        assert(MajestyCheckedPlacement::InstallPreparedRuntime(&RegisterFixture));
        assert(MajestyCheckedPlacement::InstallPreparedRuntime(&RegisterFixture));assert(registrations==8);
        assert(!MajestyCheckedPlacement::InstallPreparedRuntime(nullptr));
        stateProfile=nullptr;assert(!MajestyCheckedPlacement::InstallPreparedRuntime(&RegisterFixture));
        stateProfile=PlacementStateFor(build);installed=false;
        assert(!MajestyCheckedPlacement::InstallPreparedRuntime(&RegisterFixture));
    }
}
