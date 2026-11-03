#include "../runtime/CheckedPlacement.h"
#include "../runtime/CheckedRelocation.h"
#include "../runtime/CheckedCast.h"
#include "../runtime/CheckedNativeState.h"
#include "../runtime/CheckedPlacementProof.h"
#include "../runtime/TravelCastAdmission.h"
#include "../runtime/PlacementDiagnosticBudget.h"
#include <fstream>
#include <iterator>
#include <cstring>
#include <cstdio>
#include <functional>
#include <cstdlib>
using namespace MajestyCheckedPlacement;
static void Check(bool ok,int line) { if(!ok){std::fprintf(stderr,"checked placement fixture failed at line %d\n",line);std::exit(1);} }
#define CHECK(x) Check((x),__LINE__)
static Snapshot Example() {
    Snapshot s;
    s.actor={0x100,1,0x300,1,0x400,1};s.target={0x200,2,0x300,2,0x500,1};
    s.mover.cells={{0,0},{1,0}};s.targetShape.cells={{0,0},{1,0},{0,1},{1,1}};
    s.sourcePixels={16,16};s.targetTile={10,10};s.map=0x600;s.width=64;s.height=64;s.verified=true;return s;
}
static void Arm(Casts& c,const Snapshot& s) {
    CHECK(c.Accepted(s.actor,s.target,10,20));CHECK(c.Transfer(s.actor.id,10,11,20));CHECK(c.Release(s.actor.id,11,20));
}
struct Fixture final: Native {
    Snapshot state=Example();int moves=0,cancels=0,paths=0,fits=0;
    bool complete=true,fit=true,sameSeed=true,allowWrite=true;
    Point moved{};std::function<void()> onCapture,onPath,onCancel;
    bool Capture(Snapshot& out) override { if(onCapture)onCapture();out=state;return true; }
    bool CompletePath(const Snapshot&,Point) override { ++paths;if(onPath)onPath();return complete; }
    bool FitsTeleport(const Snapshot&,Point) override { ++fits;return fit; }
    bool SelectCheckedSeed(const Snapshot&,Point) override { return sameSeed; }
    void Cancel(const Snapshot&) override { ++cancels;if(onCancel)onCancel(); }
    bool Relocate(const Snapshot&,Point p) override { if(!allowWrite)return false;++moves;moved=p;return true; }
};
struct StateMemory final: MajestyAttackObservation::Memory {
    std::map<Word,unsigned char> bytes;
    bool Read(Word p,void* output,std::size_t size) const override {
        auto* out=static_cast<unsigned char*>(output);
        for(std::size_t i=0;i<size;++i){auto it=bytes.find(p+static_cast<Word>(i));if(it==bytes.end())return false;out[i]=it->second;}return true;
    }
    void Put(Word p,Word value){for(unsigned i=0;i<4;++i)bytes[p+i]=static_cast<unsigned char>(value>>(8*i));}
};
static bool stateCurrent=true;static int stateHp=10;static std::uint64_t stateRevision=1;
static bool Current(Word,Word,Word,Word){return stateCurrent;}
static int Hp(Word){return stateHp;}
static std::uint64_t Epoch(Word,Word){return 1;}
static std::uint64_t Revision(){return stateRevision;}
static unsigned diagnosticActor{},diagnosticReason{},diagnosticCalls{};
static void DiagnosticReceipt(Word actor,unsigned reason,const char* text){
    CHECK(text&&*text);diagnosticActor=actor;diagnosticReason=reason;++diagnosticCalls;
}
static StateMemory NativeExample(const PlacementStateProfile& p) {
    StateMemory m;
    for(Word table:{p.unit,p.vehicle,p.building}) {
        m.Put(table+0x30,p.retirement);m.Put(table+0xC0,p.footprint);m.Put(table+0x124,p.attribute);
    }
    for(Word unit:{0x1000u,0x2000u}) {
        const bool actor=unit==0x1000;const Word desc=actor?0x4000:0x5000,engine=desc+0x200;
        m.Put(unit,actor?p.unit:p.building);m.Put(unit+0x70,actor?1:2);m.Put(unit+0x74,0);
        m.Put(unit+0x7C,actor?10:20);m.Put(unit+0x80,actor?1:2);m.Put(unit+0x84,0);
        m.Put(unit+0x90,desc);m.Put(unit+0x94,0x3000);m.Put(unit+0x54,0x6000);
        m.Put(unit+0x58,(actor?32:160)*2048);m.Put(unit+0x5C,(actor?32:160)*2048);
        m.Put(desc+4,actor?10:20);m.Put(desc+8,actor?1:5);m.Put(desc+0x14,engine);
        m.Put(engine+0x3C,5);m.Put(engine+0x2C,0);
        m.Put(engine+0x14,0);m.Put(engine+0x18,0);m.Put(engine+0x1C,1);m.Put(engine+0x20,1);
        m.Put(engine+0x80,0x10);
        for(unsigned i=0;i<8;++i){m.Put(engine+0xD4+12*i,i==0?1:0);m.Put(engine+0xDC+12*i,i==0?0x6000:0);}
    }
    m.Put(0x6008,1);m.Put(0x6014,0x6200);m.Put(0x6200,p.linearMovement);
    for(unsigned i=0;i<8;++i)m.Put(0x3000+0x128+4*i,1u<<i);
    m.Put(0x3090,0x7000);m.Put(0x7050,64);m.Put(0x7054,64);return m;
}
static void NativeStateCases(const PlacementStateProfile& p) {
    auto m=NativeExample(p);StateServices services{&m,0x4000,&Current,&Hp,&Epoch,&Revision,&p};Snapshot s;
    services.profile=nullptr;CHECK(!ReadPlacement(services,0x1000,0x2000,s));services.profile=&p;
    CHECK(ReadPlacement(services,0x1000,0x2000,s));CHECK(s.sourcePixels==Point({32,32}));CHECK(s.targetTile==Point({10,10}));
    m.Put(p.building+0x124,0x12345678);
    CHECK(!ReadPlacement(services,0x1000,0x2000,s));
    services.buildingAttributeReplacement=0x12345678;
    CHECK(ReadPlacement(services,0x1000,0x2000,s));
    m.Put(p.building+0x124,0x12345679);
    CHECK(!ReadPlacement(services,0x1000,0x2000,s));
    m.Put(p.building+0x124,0x12345678);m.Put(p.unit+0x124,0x12345678);
    CHECK(!ReadPlacement(services,0x1000,0x2000,s));
    m=NativeExample(p);services.buildingAttributeReplacement=0;
    stateCurrent=false;CHECK(!ReadPlacement(services,0x1000,0x2000,s));stateCurrent=true;
    stateHp=0;CHECK(!ReadPlacement(services,0x1000,0x2000,s));stateHp=10;
    const std::pair<Word,Word> bad[]={
        {0x1074,0x10},{0x1074,4},{0x1084,1},{0x1080,8},{0x1070,2097152},
        {0x1054,0x6100},{0x4280,0x20},{0x423C,0},{0x421C,0},{0x7050,0},
        {0x312C,6},{0x5004,21},{0x2000,0x999999},{0x1058,0xFFFFFFFF}};
    for(auto change:bad){m=NativeExample(p);m.Put(change.first,change.second);CHECK(!ReadPlacement(services,0x1000,0x2000,s));}
    m=NativeExample(p);m.Put(0x422C,0x8000);m.Put(0x8000,2);m.Put(0x8004,1);m.Put(0x8008,1);
    m.Put(0x800C,0);m.Put(0x8010,0);m.Put(0x8014,0x9000);m.bytes[0x9000]=3;
    CHECK(ReadPlacement(services,0x1000,0x2000,s));CHECK(s.mover.cells.size()==2);
    m.bytes[0x9000]=0;CHECK(!ReadPlacement(services,0x1000,0x2000,s));
}
int main(int argc,char** argv) {
    {
        const auto s=Example();StockCasts c;
        CHECK(c.Submitted(s.actor,s.target,20,10));
        CHECK(!c.Turning(s.actor.id,99,11,20,s.target.id));
        CHECK(!c.Turning(s.actor.id,10,11,20,99));
        CHECK(c.Turning(s.actor.id,10,11,20,s.target.id));
        CHECK(c.Turning(s.actor.id,10,11,20,s.target.id));
        c.Unlinked(s.actor.id,10);CHECK(c.Pending(s.actor.id));
        CHECK(!c.Turning(s.actor.id,11,12,20,s.target.id));
        CHECK(c.Animation(s.actor.id,11,12,20,s.target.id));
        CHECK(c.Turning(s.actor.id,10,11,20,s.target.id));
        c.Unlinked(s.actor.id,11);CHECK(c.Pending(s.actor.id));
        CHECK(c.Release(s.actor.id,12,20,s.target.id));
        CHECK(c.Scheduled(s.actor.id,12,30,40,true));
        CHECK(c.EnterCallback(30,40,s.actor,s.target));c.LeaveCallback();
        CHECK(!c.Pending(s.actor.id));
        CHECK(c.Submitted(s.actor,s.target,20,10));
        CHECK(c.Turning(s.actor.id,10,11,20,s.target.id));
        c.Unlinked(s.actor.id,11);CHECK(!c.Pending(s.actor.id));
    }
    {
        StockCasts observed;observed.diagnostic=&DiagnosticReceipt;
        const auto sample=Example();
        CHECK(observed.Submitted(sample.actor,sample.target,20,10));
        observed.Interrupted(sample.actor.id,"fixture clear-orders");
        CHECK(diagnosticActor==sample.actor.address&&diagnosticReason==32&&diagnosticCalls==1);
        CHECK(!observed.Pending(sample.actor.id));
        observed.Interrupted(sample.actor.id);CHECK(diagnosticCalls==1);
    }
    {
        DiagnosticBudget budget;
        CHECK(!budget.Take(0,0));CHECK(!budget.Take(1,64));
        CHECK(budget.Take(1,0));
        for(unsigned i=0;i<10000;++i)CHECK(!budget.Take(1,0));
        for(unsigned i=1;i<64;++i)CHECK(budget.Take(1,i));
        for(unsigned i=0;i<32;++i)CHECK(budget.Take(2,i));
        CHECK(budget.emitted==96);CHECK(!budget.Take(2,32));CHECK(!budget.Take(3,0));
        DiagnosticBudget actors;
        for(unsigned i=1;i<=8;++i)CHECK(actors.Take(i,0));
        CHECK(!actors.Take(9,0));CHECK(actors.Take(1,1));
    }
    for(auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
        const auto* p=TravelCastFor(build);CHECK(p);
        StateMemory m;
        for(unsigned c=0;c<3;++c)m.Put(0x1000+0x98+4*c,0);
        CHECK(TravelCastReady(m,0x1000,p));
        auto add=[&](unsigned channel,unsigned table) {
            const unsigned stack=0x2000+channel*0x100,head=stack+0x40,node=stack+0x50,order=stack+0x70;
            m.Put(0x1000+0x98+4*channel,stack);m.Put(stack+4,0x1000);
            m.Put(stack+0x1C,head);m.Put(stack+0x20,1);
            m.Put(head,node);m.Put(head+4,node);m.Put(node,head);m.Put(node+4,head);
            m.Put(node+8,order);m.Put(order,table);
        };
        for(auto table:p->movement) { add(0,table);CHECK(TravelCastReady(m,0x1000,p)); }
        add(1,p->movement[3]);CHECK(TravelCastReady(m,0x1000,p));
        const auto original=m.bytes;
        add(2,p->movement[0]);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        add(1,0xDEAD);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        m.Put(0x2104,0x9999);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        m.Put(0x2150,0x2150);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        m.Put(0x2120,17);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        m.bytes.erase(0x2170);CHECK(!TravelCastReady(m,0x1000,p));m.bytes=original;
        CHECK(!TravelCastReady(m,0x1000,nullptr));CHECK(m.bytes==original);
    }
    CHECK(!TravelCastFor(static_cast<MajestyBuildId>(255)));
    // Independently construct each wire version. No generated profile needed.
    for(unsigned version:{1u,2u,3u}) {
        std::vector<unsigned char> bytes={'M','M','P','L'};
        const auto word=[&](unsigned value){for(unsigned i=0;i<4;++i)bytes.push_back(static_cast<unsigned char>(value>>(i*8)));};
        const auto name=[&](const char* value){word(static_cast<unsigned>(std::strlen(value)));bytes.insert(bytes.end(),value,value+std::strlen(value));};
        word(version);word(600);bytes.insert(bytes.end(),32,0xA5);
        for(const char* value:{"placement","Fixture","Solarus","PrivateCast","PrivateRelease","PrivateMove"})name(value);
        if(version>=2){name("PrivateArrival");word(0x4F534457);}
        if(version==3)word(6);
        PlacementProof proof;CHECK(ParsePlacementProof(bytes.data(),bytes.size(),proof));
        CHECK(proof.arrival==(version>=2?"PrivateArrival":""));
        CHECK(proof.imageId==(version>=2?0x4F534457u:0u));
        CHECK(proof.requiredLevel==(version==3?6u:0u));
        CHECK(proof.observerDigest[0]==0xA5&&proof.range==600);
        for(unsigned range:{601u,static_cast<unsigned>(MaximumRange)}) {
            for(unsigned i=0;i<4;++i)bytes[8+i]=static_cast<unsigned char>(range>>(i*8));
            CHECK(ParsePlacementProof(bytes.data(),bytes.size(),proof)&&proof.range==static_cast<int>(range));
        }
        for(unsigned range:{0u,static_cast<unsigned>(MaximumRange)+1u,0xFFFFFFFFu}) {
            for(unsigned i=0;i<4;++i)bytes[8+i]=static_cast<unsigned char>(range>>(i*8));
            CHECK(!ParsePlacementProof(bytes.data(),bytes.size(),proof));
        }
        for(unsigned i=0;i<4;++i)bytes[8+i]=static_cast<unsigned char>(600u>>(i*8));
        for(std::size_t size=0;size<bytes.size();++size)CHECK(!ParsePlacementProof(bytes.data(),size,proof));
        if(version==3) {
            const auto offset=bytes.size()-4;
            for(unsigned invalid:{0u,1001u,0xFFFFFFFFu}) {
                for(unsigned i=0;i<4;++i)bytes[offset+i]=static_cast<unsigned char>(invalid>>(i*8));
                CHECK(!ParsePlacementProof(bytes.data(),bytes.size(),proof));
            }
        }
        bytes[4]=4;CHECK(!ParsePlacementProof(bytes.data(),bytes.size(),proof));
    }
    if(argc==2) {
        std::ifstream file(argv[1],std::ios::binary);
        std::vector<unsigned char> data((std::istreambuf_iterator<char>(file)),{});PlacementProof proof;
        CHECK(ParsePlacementProof(data.data(),data.size(),proof));CHECK(proof.range>0&&proof.range<=MaximumRange);
        data.push_back(0);CHECK(!ParsePlacementProof(data.data(),data.size(),proof));
        data.pop_back();data[8]=data[9]=data[10]=data[11]=0;CHECK(!ParsePlacementProof(data.data(),data.size(),proof));
    }
    for(auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
        const auto* p=PlacementStateFor(build);CHECK(p);NativeStateCases(*p);
    }
    CHECK(!PlacementStateFor(static_cast<MajestyBuildId>(255)));
    CHECK(!PlacementQueriesFor(static_cast<MajestyBuildId>(255)));
    CHECK(!RelocationFor(static_cast<MajestyBuildId>(255)));
    {
        StockCasts c;const auto s=Example();
        CHECK(c.Submitted(s.actor,s.target,20,10));
        CHECK(!c.Release(1,10,20,2));
        CHECK(!c.Animation(1,99,11,20,2));CHECK(c.Animation(1,10,11,20,2));
        c.Unlinked(1,10);CHECK(c.Pending(1));
        CHECK(!c.Scheduled(1,11,100,200,true));CHECK(c.Release(1,11,20,2));
        c.Unlinked(1,11);CHECK(c.Pending(1));
        CHECK(!c.Scheduled(1,11,100,200,false));CHECK(c.Scheduled(1,11,100,200,true));
        CHECK(!c.EnterCallback(101,200,s.actor,s.target));CHECK(!c.InCallback(s.actor,s.target));c.LeaveCallback();
        CHECK(c.EnterCallback(100,200,s.actor,s.target));CHECK(c.InCallback(s.actor,s.target));
        CHECK(!c.EnterCallback(100,200,s.actor,s.target));CHECK(!c.InCallback(s.actor,s.target));
        c.LeaveCallback();CHECK(c.InCallback(s.actor,s.target));
        CHECK(c.Authorizations().Consume(s.actor,s.target));CHECK(!c.InCallback(s.actor,s.target));
        c.LeaveCallback();CHECK(!c.Pending(1));
    }
    for(int event=0;event<6;++event) {
        StockCasts c;const auto s=Example();
        CHECK(c.Submitted(s.actor,s.target,20,10));CHECK(c.Animation(1,10,11,20,2));
        CHECK(c.Release(1,11,20,2));CHECK(c.Scheduled(1,11,100,200,true));
        switch(event){case 0:c.Interrupted(1);break;case 1:c.InvalidateUnit(1);break;
        case 2:c.InvalidateUnit(2);break;case 3:c.InvalidateFunction(100);break;case 4:c.Reset();break;case 5:c.RetargetedOrder(11,3);c.RetargetedOrder(11,2);break;}
        CHECK(!c.EnterCallback(100,200,s.actor,s.target));c.LeaveCallback();CHECK(!c.Pending(1));
    }
    {
        WriteBoundary b;CHECK(b.Arm(1));b.SetFrame(100);
        CHECK(!b.IsExpected(1,99)&&!b.IsExpected(2,100));
        CHECK(b.BeginCheck());CHECK(!b.BeginCheck());
        CHECK(b.FinishCheck(true));CHECK(b.Committed());CHECK(!b.BeginCheck());
        b.Clear();CHECK(b.Arm(1));b.SetFrame(100);
        b.OtherWrite();CHECK(!b.BeginCheck()&&!b.Committed());
        b.Clear();CHECK(b.Arm(1));b.SetFrame(100);CHECK(b.BeginCheck());
        b.OtherWrite();CHECK(!b.FinishCheck(true)&&!b.Committed());
        b.Clear();CHECK(b.Arm(1));b.SetFrame(100);CHECK(b.BeginCheck());
        CHECK(!b.FinishCheck(false)&&!b.BeginCheck());
    }
    // Fixture adapters exercise ordering/invalidation, not native gameplay.
    {
        Casts c;Fixture f;Arm(c,f.state);
        CHECK(Commit(c,f,600)==1);CHECK(f.moves==1&&f.cancels==1&&f.paths==2&&f.fits==2);
        CHECK(f.moved.x%16==0&&f.moved.y%16==0);
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==1);
    }
    for(int variant=0;variant<13;++variant) {
        Casts c;Fixture f;Arm(c,f.state);
        f.onCancel=[&] {
            switch(variant) {
            case 0:f.state.actor.world++;break;case 1:f.state.target.world++;break;
            case 2:f.state.actor.lifetime++;break;case 3:f.state.target.lifetime++;break;
            case 4:f.state.actor.player++;break;case 5:f.state.target.player++;break;
            case 6:f.state.actor.description++;break;case 7:f.state.map++;break;
            case 8:f.state.mover.cells={{0,0}};break;case 9:f.state.targetTile.x++;break;
            case 10:f.fit=false;break;case 11:f.complete=false;break;
            case 12:f.state.revision++;break;
            }
        };
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0&&f.cancels==1);
        f.onCancel={};f.state=Example();f.fit=f.complete=true;CHECK(Commit(c,f,600)==0);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);int nested=-1;
        f.onCapture=[&] { nested=Commit(c,f,600); };
        CHECK(Commit(c,f,600)==1);CHECK(nested==0&&f.moves==1);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);
        f.onCancel=[&] {
            c.Reset();
            CHECK(!c.Accepted(f.state.actor,f.state.target,10,20));
            CHECK(Commit(c,f,600)==0);
        };
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0);
        CHECK(c.Accepted(f.state.actor,f.state.target,10,20));
    }
    {
        Casts c;Fixture f;Arm(c,f.state);
        f.onCancel=[&] { c.InvalidateUnit(f.state.target.id); };
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);int nested=-1;
        f.onPath=[&] { nested=Commit(c,f,600); };
        CHECK(Commit(c,f,600)==1);CHECK(nested==0&&f.moves==1);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);int nested=-1;
        f.onCancel=[&] { nested=Commit(c,f,600); };
        CHECK(Commit(c,f,600)==1);CHECK(nested==0&&f.moves==1);
    }
    for(bool complete:{false,true}) {
        Casts c;Fixture f;Arm(c,f.state);f.complete=complete;f.fit=false;
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0&&f.cancels==0);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);f.allowWrite=false;
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0&&f.cancels==1);
        f.allowWrite=true;CHECK(Commit(c,f,600)==0);
    }
    {
        Casts c;Fixture f;Arm(c,f.state);f.sameSeed=false;
        CHECK(Commit(c,f,600)==0);CHECK(f.moves==0&&f.cancels==0);
    }
    {
        auto s=Example();Casts c;
        CHECK(c.Accepted(s.actor,s.target,10,20));CHECK(!c.Release(1,99,20));
        c.RemovedOrder(1,10);CHECK(!c.Release(1,10,20));
        Arm(c,s);c.InvalidateUnit(2);CHECK(!c.Consume(s.actor,s.target));
        Arm(c,s);c.Reset();CHECK(!c.Consume(s.actor,s.target));
        Arm(c,s);s.actor.lifetime++;CHECK(!c.Consume(s.actor,s.target));
    }
    {
        Footprint decoded;
        // Row stride includes unused bits/bytes. Padding never occupies a cell.
        CHECK(DecodeBitmap(9,2,3,{-4,-1},{0x81,0x81,0xff,0x02,0x80,0xff},decoded));
        CHECK((decoded.cells==std::vector<Point>{{-4,-1},{3,-1},{4,-1},{-3,0}}));
        CHECK(!DecodeBitmap(9,2,1,{0,0},{0xff,0xff},decoded));CHECK(decoded.cells.empty());
        CHECK(!DecodeBitmap(1,1,1,{0,0},{0},decoded));
        CHECK(!DecodeBitmap(2,1,1,{64,0},{3},decoded));
        CHECK(!DecodeBitmap(1,1,1,{0,0},{1,1},decoded));
        CHECK(DecodeRectangle(-1,-1,1,1,decoded));CHECK(decoded.cells.size()==4);
        CHECK(!DecodeRectangle(0,0,0,1,decoded));CHECK(decoded.cells.empty());
        CHECK(!DecodeRectangle(-64,-64,65,65,decoded));
    }
    {
        Footprint empty,duplicate{{{0,0},{0,0}}},mover{{{0,0},{1,0}}},target{{{0,0}}};
        CHECK(!empty.Valid()&&!duplicate.Valid());
        CHECK(!FitsBounds(mover,{63,0},64,64));
        CHECK(Intersects(mover,{9,10},target,{10,10}));
        auto seeds=ExteriorSeeds(target,{10,10},mover,{16,16},64,64,600);
        CHECK(!seeds.empty());
        for(auto p:seeds)CHECK(!Intersects(mover,p,target,{10,10})&&FitsBounds(mover,p,64,64));
        CHECK(ExteriorSeeds(target,{-1,10},mover,{16,16},64,64,600).empty());
        CHECK(ExteriorSeeds(target,{10,10},mover,{16,16},64,64,MaximumRange+1).empty());
        CHECK(ExteriorSeeds(target,{60000,60000},mover,{16,16},65535,65535,600).empty());
        auto distant=ExteriorSeeds(target,{60000,60000},mover,{16,16},65535,65535,MaximumRange);
        CHECK(!distant.empty() && distant.size()==seeds.size());
        for(auto p:distant)CHECK(FitsBounds(mover,p,65535,65535)&&!Intersects(mover,p,target,{60000,60000}));
    }
    return 0;
}
