#include "../runtime/CosmeticActionCleanup.h"
#include "../runtime/CosmeticActionState.h"
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
using namespace MajestyCheckedPlacement;
static void Check(bool ok,int line){if(!ok){std::fprintf(stderr,"cosmetic cleanup failure %d\n",line);std::exit(1);}}
#define CHECK(x) Check((x),__LINE__)
static CosmeticActionCleanup cleanup;
static unsigned refreshed{};
static bool eligible=true,current=true,reenter=false,throws=false;
static bool Capture(Word unit,Word order,CosmeticPose& out) {
    out={{unit,unit,7,1,9,11},order,17,18,19,0x90,20,21};return eligible;
}
static bool Current(const CosmeticPose&) {return current;}
static void Refresh(Word unit) {
    ++refreshed;
    if(throws)throw std::runtime_error("fixture refresh failure");
    if(reenter){reenter=false;cleanup.Enter();cleanup.Invalidate(unit==1?2:1);cleanup.Leave();}
}
static void Reset() {cleanup.Reset();cleanup.Configure({Capture,Current,Refresh});refreshed=0;eligible=current=true;reenter=throws=false;}
static Identity live{0x100,3,7,1,0xB00,11};
static bool Identify(Word unit,Identity& out){out=live;return unit==live.address&&live.lifetime!=0;}
struct StateMemory final: MajestyAttackObservation::Memory {
    std::vector<unsigned char> bytes=std::vector<unsigned char>(0x2000);
    void Put(Word at,Word value){std::memcpy(bytes.data()+at,&value,4);}
    bool Read(Word at,void* out,std::size_t n) const override {
        if(at>bytes.size()||n>bytes.size()-at)return false;
        std::memcpy(out,bytes.data()+at,n);return true;
    }
};
static void StateChecks() {
    for(auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
        StateMemory m;const auto* types=CosmeticImagesFor(build);
        CosmeticActionState state{&m,types,Identify,0xB00,0x300,0x400,0x1234,0x42,8,0x4F534457};
        m.Put(0xB14,0xC00);m.Put(0xC58,0x4F534457);m.Put(0x504,0x4F534457);
        m.Put(0xD00,0xF00);m.Put(0xD04,0x1700);m.Put(0xF00,0x4F534457);m.Put(0xF10,0xD00);
        m.Put(0xD0C,1);m.Put(0xD10,0xE00);m.Put(0xE00,0x42);
        m.Put(0xE08,8);m.Put(0xE0C,0x10300);m.Put(0xE20,0x1000);
        for(Word i=0;i<8;++i)m.Put(0x1000+i*0x5C+0x58,9);
        m.Put(0x304,0x1234);m.Put(0x308,1);m.Put(0x314,0x400);
        m.Put(0x400,types->standardEngine);m.Put(0x408,0x42);m.Put(0x438,8);
        m.Put(0x128,0x500);m.Put(0x500,types->collection);m.Put(0x508,0xD00);
        m.Put(0x510,0x100);m.Put(0x518,2);m.Put(0x51C,0x600);
        m.Put(0x600,types->part);m.Put(0x604,0xD00);m.Put(0x608,8);
        m.Put(0x640,types->part);m.Put(0x644,0xD00);m.Put(0x648,0x42);
        m.Put(0x64C,0x100);m.Put(0x658,0x600);
        m.Put(0x1A0,0x800);m.Put(0x804,0x100);m.Put(0x81C,0x900);
        m.Put(0x900,0x940);m.Put(0x940,0x900);m.Put(0x948,0xA00);
        m.Put(0xA00,types->animation);m.Put(0xA10,11);m.Put(0xA2C,0x1001);
        m.Put(0xA34,0x150);m.Put(0xA38,1);m.Put(0xA50,0x1000);m.Put(0xA5C,0x1234);
        CosmeticPose pose;CHECK(state.Capture(0x100,0xA00,pose));
        CHECK(pose.part==0x640&&pose.imageSet==0x42);
        CHECK(!state.Current(pose)); // live animation still owns channel2
        const auto original=m.bytes;
        for(auto mutation:std::vector<std::pair<Word,Word>>{
            {0x408,0x43},{0x410,1},{0x414,1},{0x418,1},{0x440,1},{0x444,1},{0x448,1},
            {0x500,1},{0x510,2},{0x514,1},{0x518,1},{0x51C,0xFFFFFFC0},
            {0x504,1},{0xC58,1},{0xF00,1},{0xF10,1},{0xE14,1},{0x1040,1},{0x1044,1},
            {0x640,1},{0x648,8},{0x64C,8},{0x64C,0x1000},{0x650,1},{0x654,1},{0x658,0x680},
            {0xA00,1},{0xA10,5},{0xA38,2},{0xA38,0xFFFFFFFF},{0xA50,3},{0xA5C,9}}) {
            m.bytes=original;m.Put(mutation.first,mutation.second);
            CHECK(!state.Capture(0x100,0xA00,pose));
        }
        m.bytes=original;CHECK(state.Capture(0x100,0xA00,pose));
        m.Put(0x900,0x900);std::memset(m.bytes.data()+0xA00,0xDD,0x70);
        CHECK(state.Current(pose)); // freed order is deliberately unreadable as an order
        m.Put(0x64C,0);CHECK(!state.Current(pose)); // valid but different stream role
        m.Put(0x64C,0x100);m.Put(0x658,0);CHECK(!state.Current(pose));
        m.Put(0x658,0x600);CHECK(state.Current(pose));
        m.Put(0xD0C,1);m.Put(0xD10,0xE00);m.Put(0xE00,0x42);
        m.Put(0xE08,8);m.Put(0xE0C,0x10300);m.Put(0xE20,0x1000);
        for(Word i=0;i<8;++i)m.Put(0x1000+i*0x5C+0x58,9);
        CHECK(state.CanStart(0x100));
        // Captured ordinary WDSO metadata: cached descriptor+4 is not an ID;
        // set42 has flags101 and one stream in each direction.
        m.Put(0xE0C,0x101);
        for(Word i=0;i<8;++i)m.Put(0x1000+i*0x5C+0x54,0x00010001);
        CHECK(state.CanStart(0x100));
        m.Put(0x1000+0x54,0x00020001);CHECK(!state.CanStart(0x100));
        m.Put(0x1000+0x54,0x00010001);
        m.Put(0xE0C,0x301);CHECK(!state.CanStart(0x100));
        m.Put(0xE0C,0x10300);
        m.Put(0x1000+7*0x5C+0x58,0);CHECK(!state.CanStart(0x100));
        m.Put(0x1000+7*0x5C+0x58,9);
        m.Put(0xE00,0x01000042);CHECK(!state.CanStart(0x100));m.Put(0xE00,0x42);
        m.Put(0xE0C,0x300);CHECK(!state.CanStart(0x100));m.Put(0xE0C,0x10300);
        m.Put(0xE08,0xFFFFFFFF);CHECK(!state.CanStart(0x100));m.Put(0xE08,8);
        CHECK(state.CanStart(0x100));
        ++live.lifetime;CHECK(!state.Current(pose));--live.lifetime;
        m.Put(0x648,0x02000042);CHECK(!state.Current(pose)); // exact full key matters
        m.Put(0x648,0x42);m.Put(0x644,0xD40);CHECK(!state.Current(pose));
    }
}
int main() {
    Reset();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);cleanup.Leave();CHECK(!refreshed);
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);CHECK(!refreshed);
    cleanup.Leave();CHECK(refreshed==1);cleanup.Enter();cleanup.Leave();CHECK(refreshed==1);
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);
    cleanup.Configure({Capture,Current,Refresh}); // repeated effective check is idempotent
    cleanup.Unlinked(1,2);cleanup.Leave();CHECK(refreshed==1);
    // Failed/removed effective binding cannot leave the previous callback live.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);
    cleanup.Configure({});cleanup.Leave();CHECK(!refreshed);
    cleanup.Enter();cleanup.Cancelling(1,3);cleanup.Unlinked(1,3);cleanup.Leave();CHECK(!refreshed);
    // Callback refusal and an unrelated unlink never authorize restoration.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,3);cleanup.Leave();CHECK(!refreshed);
    // Normal finish already replaced the private pose; unrelated actions never qualify.
    Reset();eligible=false;cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);cleanup.Leave();CHECK(!refreshed);
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);current=false;cleanup.Leave();CHECK(!refreshed);
    // Native clear/dispatch can nest, but refresh cannot run within either scope.
    Reset();cleanup.Enter();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);
    cleanup.Leave();CHECK(!refreshed);cleanup.Leave();CHECK(refreshed==1);
    // A replacement submission, death, retirement or owner mutation invalidates
    // even if subsequent current fields happen to return to their original values.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Invalidate(1);
    cleanup.Unlinked(1,2);cleanup.Leave();CHECK(!refreshed);
    // World/load/configuration changes clear every candidate without replay.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);
    cleanup.Reset();cleanup.Leave();CHECK(!refreshed);
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);
    cleanup.Leave(false);cleanup.Enter();cleanup.Leave();CHECK(!refreshed);
    // Duplicate cancellation scopes cannot issue duplicate refreshes.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Cancelling(1,2);
    cleanup.Unlinked(1,2);cleanup.Leave();CHECK(refreshed==1);
    // Reentrant refresh can invalidate another queued owner, not a detached copy.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);
    cleanup.Cancelling(2,3);cleanup.Unlinked(2,3);reenter=true;
    cleanup.Leave();CHECK(refreshed==1);
    // A thrown stock operation cannot leave pending work for a later frame/load.
    Reset();cleanup.Enter();cleanup.Cancelling(1,2);cleanup.Unlinked(1,2);throws=true;
    bool caught=false;try{cleanup.Leave();}catch(const std::runtime_error&){caught=true;}
    CHECK(caught);throws=false;cleanup.Enter();cleanup.Leave();CHECK(refreshed==1);
    // No arbitrary per-unit capacity drops cleanup from a mass cancellation.
    Reset();cleanup.Enter();for(Word i=1;i<=200;++i){cleanup.Cancelling(i,i+1000);cleanup.Unlinked(i,i+1000);}
    cleanup.Leave();CHECK(refreshed==200);
    StateChecks();
    return 0;
}
