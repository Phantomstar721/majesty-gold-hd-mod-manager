#include "AttackObservationFixture.h"
#include "../runtime/AttackObservationContext.h"
#include "../runtime/ResearchCompletionAttributes.h"
#include "../runtime/AttackObservationProof.h"
#include "../runtime/BcdDefinitionOwnership.h"
#include "../runtime/AttackObservationBaseline.h"
#include "../runtime/WorldAttachmentProfiles.h"
#include "../runtime/NativeImpactRegistry.h"
#include "../runtime/NativeImpactCompletion.h"
#include "../runtime/GplCallArguments.h"
#include <fstream>
#include <iterator>
int tests=0;
void Check(bool value,const char* label) { ++tests; if (!value) throw std::runtime_error(label); }
struct CountedMemory:Memory {
    const Memory& source;
    mutable unsigned reads=0;
    unsigned failAt=0;
    explicit CountedMemory(const Memory& m):source(m){}
    bool Read(Address p,void* output,std::size_t size)const override {
        return ++reads!=failAt && source.Read(p,output,size);
    }
};
int main(int argc,char** argv) {
    try {
        {
            Fixture f;
            // A deliberately deep index used to reread the same native nodes
            // for every unit. Two unrelated orders per unit remain validated.
            for(unsigned i=11;i<111;++i) {
                const auto unit=f.Unit(i);
                f.Order(unit,0,7,0);f.Order(unit,2,11,0);
            }
            CountedMemory memory(f);
            const auto result=Inspect(memory,f.profile,f.world,f.catalog,f.actor,10);
            Check(result.result==Result::Settled && result.units==101 && result.orders==200,"batched reads retain the complete census");
            Check(memory.reads<1200,"native reads are linear, not repeated per index search");
            const auto required=memory.reads;
            for(unsigned fail=1;fail<=required;++fail) {
                memory.reads=0;memory.failAt=fail;
                Check(Inspect(memory,f.profile,f.world,f.catalog,f.actor,10).result==Result::Unknown,"each required batched read remains fail-closed");
            }
            memory.failAt=0;memory.reads=0;
            f.Put(f.treeHead,4,f.treeHead);
            Check(Inspect(memory,f.profile,f.world,f.catalog,f.actor,10).result==Result::Unknown,"tree copies cannot survive into a later decision");
        }
        {
            FailureReportBudget budget;
            Check(!budget.Take(Result::Settled),"settled does not consume report budget");
            Check(!budget.Take(Result::Busy),"busy does not consume report budget");
            Check(budget.Take(Result::Unknown),"first failure receives one report");
            for(unsigned i=0;i<10000;++i)
                Check(!budget.Take(Result::Unknown),"repeated failures cannot spam");
            Fixture f;Lifecycle life;
            Check(life.Query(f,f.profile,f.actor,10).failure!=nullptr,"unattached failure has reason");
            Check(f.Attach(life),"reason fixture attaches");
            Check(life.Query(f,f.profile,f.actor,10).failure==nullptr,"settled clears failure reason");
            life.EnterOperation();
            Check(std::string(life.Query(f,f.profile,f.actor,10).failure)=="lifecycle-operation-active","nested query reports guard");
            life.LeaveOperation();
            f.Put(f.catalog,0,0);
            Check(std::string(life.Query(f,f.profile,f.actor,10).failure)=="catalog-header","invalid catalog reports its check");
        }
        {
            Fixture f;
            f.profile.stockAllUnitsVtable=0x7535BC;
            f.Put(f.catalog,0,f.profile.stockAllUnitsVtable);
            Check(f.InspectNow().result==Result::Settled,"stock AllUnitsList is a valid catalog");
            f.Order(f.actor,1,10,0);
            Check(f.InspectNow().result==Result::Busy,"stock AllUnitsList preserves pending attacks");
            f.Put(f.catalog,0,0x12345678);
            Check(f.InspectNow().result==Result::Unknown,"unrecognized catalog remains rejected");
            f.Put(f.catalog,0,0);f.profile.stockAllUnitsVtable=0;
            Check(f.InspectNow().result==Result::Unknown,"absent alternate binding never admits null table");
        }
        {
            unsigned slot=99;
            const int frame[]={100,200,300}; // implicit result, explicit out, actor
            Check(MajestyGplCall::FrameSlot(0,3,slot)&&frame[slot]==100,"return-value function uses implicit result");
            Check(MajestyGplCall::FrameSlot(1,3,slot)&&frame[slot]==200,"return-value function first written argument stays slot1");
            Check(MajestyGplCall::FrameSlot(0,1,slot)&&slot==0,"zero-argument return function keeps its result");
            Check(!MajestyGplCall::FrameSlot(0,0,slot),"empty raw frame rejects");
            Check(MajestyGplCall::ExplicitSlot(0,3,slot)&&frame[slot]==200,"procedure out skips implicit result");
            Check(MajestyGplCall::ExplicitSlot(1,3,slot)&&frame[slot]==300,"procedure actor follows explicit output");
            Check(!MajestyGplCall::ExplicitSlot(2,3,slot),"missing written argument rejects");
            Check(!MajestyGplCall::ExplicitSlot(0,0,slot),"empty frame rejects");
            Check(!MajestyGplCall::ExplicitSlot(0,1,slot),"result-only frame has no written arguments");
            Check(!MajestyGplCall::ExplicitSlot(~0u,3,slot),"argument index overflow rejects");
        }
        if(argc>2) {
            // Read-only replay of captured real BCD files. g:/b:/o: denotes
            // generated/baseline/other evidence, not a filename allowlist.
            std::ifstream file(argv[1],std::ios::binary);
            std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(file)),{});
            PackageProof proof;
            Check(ParsePackageProof(bytes.data(),bytes.size(),proof),"replay proof parses");
            MajestyBcdOwnership::BatchOwnership batch;
            for(int i=2;i<argc;++i) {
                const std::string item=argv[i];
                if(item=="--postload") { batch.Reset();continue; }
                Check(item.size()>2&&item[1]==':',"replay role supplied");
                std::ifstream source(item.substr(2),std::ios::binary);
                std::vector<unsigned char> data((std::istreambuf_iterator<char>(source)),{});
                MajestyBcdOwnership::Definitions definitions;
                if(!MajestyBcdOwnership::ReadDefinitions(data.data(),data.size(),definitions))
                    throw std::runtime_error("ownership replay parse rejected: "+item);
                if(!batch.Admit(definitions,proof.protectedNames,item[0]=='g',item[0]=='b'||item[0]=='s')) {
                    for(const auto& key:definitions)
                        if(!batch.Admit({key},proof.protectedNames,item[0]=='g',item[0]=='b'))
                            std::cerr<<"Unestablished definition: "<<key.first<<":"<<key.second<<"\n";
                    throw std::runtime_error("ownership replay rejected: "+item);
                }
                if(item[0]=='s' && !batch.BaselineRetainsWinners(definitions,proof.protectedNames))
                    throw std::runtime_error("shadowed baseline replay rejected: "+item);
                batch.Complete(definitions,proof.protectedNames,item[0]=='g');
            }
        }
        { // Same framed symbol layout as Python's BCD ownership reader.
            using Bytes=std::vector<unsigned char>;
            auto word=[](Bytes& b,unsigned v){for(unsigned s=0;s<32;s+=8)b.push_back(static_cast<unsigned char>(v>>s));};
            auto block=[&](unsigned version,Bytes body){Bytes b;word(b,static_cast<unsigned>(body.size()+16));word(b,version);b.insert(b.end(),body.begin(),body.end());word(b,0);word(b,0xffffffffu);return b;};
            auto archive=[&](const std::string& name){
                Bytes symbols;word(symbols,0);word(symbols,1);symbols.insert(symbols.end(),name.begin(),name.end());symbols.push_back(0);
                auto signature=block(1,{});symbols.insert(symbols.end(),signature.begin(),signature.end());word(symbols,0);
                Bytes records;word(records,0);Bytes root;word(root,0);
                for(auto part:{block(0,{}),block(1,symbols),block(1,records)})root.insert(root.end(),part.begin(),part.end());
                auto framed=block(0xffffffffu,root);Bytes b;word(b,static_cast<unsigned>(framed.size()));b.insert(b.end(),framed.begin(),framed.end());return b;
            };
            const std::set<std::string> protectedNames{"make_attack"};
            auto safe=archive("QuestStart"),conflict=archive("MAKE_ATTACK");
            Check(MajestyBcdOwnership::NonOverlapping(safe.data(),safe.size(),protectedNames),"unrelated quest definitions admitted");
            Check(!MajestyBcdOwnership::NonOverlapping(conflict.data(),conflict.size(),protectedNames),"actual protected override rejected case insensitively");
            for(std::size_t n=0;n<safe.size();++n)Check(!MajestyBcdOwnership::NonOverlapping(safe.data(),n,protectedNames),"truncated ownership table rejected");
            safe.push_back(0);Check(!MajestyBcdOwnership::NonOverlapping(safe.data(),safe.size(),protectedNames),"trailing ownership bytes rejected");
        }
        {
            using namespace MajestyBcdOwnership;
            const std::set<std::string> protectedNames{"attack_object","gettohit"};
            const Definitions generated{{1,"attack_object"},{1,"GetToHit"}};
            BatchOwnership batch;
            Check(!batch.Admit(generated,protectedNames,false,false),"unknown first protected winner rejected");
            Check(batch.Admit(generated,protectedNames,true,false),"generated first winner admitted");
            batch.Complete(generated,protectedNames,true);
            Check(batch.Admit(generated,protectedNames,false,false),"later exact duplicates are shadowed");
            batch.Complete(generated,protectedNames,false);
            Check(batch.Admit(generated,protectedNames,false,false),"duplicate cannot replace recorded winner");
            Check(!batch.Admit({{1,"gettohit"}},protectedNames,false,false),"symbol casing is not guessed equivalent");
            Check(!batch.Admit({{0,"attack_object"}},protectedNames,false,false),"separate symbol namespace is not shadowed");
            batch.Reset();
            Check(!batch.Admit(generated,protectedNames,false,false),"previous batch does not establish current publication");
            Check(batch.Admit(generated,protectedNames,false,true),"native baseline can load before profile");
            batch.Complete(generated,protectedNames,false);
            Check(!batch.Admit(generated,protectedNames,true,false),"generated loser cannot displace baseline winner in same batch");
            Check(!batch.Admit({{1,"gettohit"}},protectedNames,true,false),"case-only generated spelling cannot displace retained tape");
        }
        for(bool animated:{false,true}) {
            unsigned calls=0,removed=0;
            MajestyNativeImpact::FinishAbsorbed(123,[&](unsigned unit,unsigned animation,unsigned callback,unsigned a,unsigned b,unsigned c) {
                Check(unit==123&&animation==0x60&&callback==0x1005&&!a&&!b&&!c,"literal stock final-animation arguments");
                ++calls;return animated;
            },[&](unsigned unit){Check(calls==1&&unit==123,"removal follows failed animation once");++removed;});
            Check(calls==1&&removed==(animated?0u:1u),"stock absorption finish/removal ordering");
        }
        { std::vector<unsigned char> data;
          auto word=[&](unsigned value){for(unsigned shift=0;shift<32;shift+=8)data.push_back(static_cast<unsigned char>(value>>shift));};
          data.insert(data.end(),{'M','M','I','P'});word(1);word(1);data.resize(44);word(0x31655057);
          for(const std::string text:{"Deflect","fireball_missile","Fire_Ball_Hit"}) {
              word(static_cast<unsigned>(text.size()));data.insert(data.end(),text.begin(),text.end());
          }
          MajestyNativeImpact::Registry registry;
          Check(MajestyNativeImpact::Parse(data.data(),data.size(),registry)&&registry.bindings.size()==1,"native impact registry parses");
          Check(registry.bindings[0].id==0x31655057&&registry.bindings[0].provider=="Deflect","native provider binding preserved");
          for(std::size_t n=0;n<data.size();++n)Check(!MajestyNativeImpact::Parse(data.data(),n,registry),"truncated registry rejected");
          data.push_back(0);Check(!MajestyNativeImpact::Parse(data.data(),data.size(),registry),"trailing registry rejected");
        }
        for(unsigned version:{3u,4u,7u,8u}) {
            std::vector<unsigned char> bytes{'M','M','O','B',static_cast<unsigned char>(version),0,0,0};
            unsigned count=version%2==0?9:7;bytes.push_back(static_cast<unsigned char>(count));bytes.resize(12+count*32);
            for(unsigned n=0;n<count;++n)bytes[12+n*32]=static_cast<unsigned char>(n+1);
            if(version>4) {
                bytes.insert(bytes.end(),{1,0,0,0,11,0,0,0});
                const std::string name="make_attack";bytes.insert(bytes.end(),name.begin(),name.end());
            }
            PackageProof proof;
            Check(ParsePackageProof(bytes.data(),bytes.size(),proof)&&proof.actor.empty()&&proof.apiPrefix.empty(),"shared proof has no invented actor or aliases");
            Check(proof.scoped==(version%2==0),"shared proof preserves dataset semantics");
            Check(proof.protectedNames.size()==(version>4?1u:0u),"definition protection wire roundtrip");
            if(version>4) {
                const auto valid=bytes;
                for(unsigned char first:{static_cast<unsigned char>('1'),static_cast<unsigned char>('M'),static_cast<unsigned char>(0)}) {
                    bytes[12+count*32+8]=first;
                    Check(!ParsePackageProof(bytes.data(),bytes.size(),proof),"noncanonical protected name rejected");
                    Check(proof.protectedNames.empty()&&proof.digests.empty(),"failed proof clears old protection");
                    bytes=valid;
                }
            }
        }
        const unsigned char* baselineDigests[6]{};
        for(unsigned i=0;i<6;++i)baselineDigests[i]=MajestyAttackObservation::kBaselineDigests[i];
        Check(MajestyAttackObservation::KnownBaselineBundle(baselineDigests),"complete known bundle");
        unsigned char unknownDigest[32]{};
        baselineDigests[2]=unknownDigest;
        Check(!MajestyAttackObservation::KnownBaselineBundle(baselineDigests),"unknown or mixed bundle rejected");
        baselineDigests[2]=nullptr;
        Check(!MajestyAttackObservation::KnownBaselineBundle(baselineDigests),"missing archive rejected");
        if (argc==2) {
            std::ifstream file(argv[1],std::ios::binary);
            std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(file)),{});
            PackageProof proof;
            Check(ParsePackageProof(bytes.data(),bytes.size(),proof),"Python/native proof agreement");
            Check(proof.apiPrefix=="WHP" && proof.digests.size()>=7,"proof aliases and digest records");
            for (std::size_t i=0;i<proof.digests.size();++i)
                Check(proof.Find(proof.digests[i].data())==static_cast<int>(i),"actual proof digest identity preserved");
            const auto original=bytes;
            bytes[4]=3;Check(!ParsePackageProof(bytes.data(),bytes.size(),proof),"unknown proof version rejected");bytes=original;
            // Parse again: failed parsing deliberately clears the output.
            Check(ParsePackageProof(bytes.data(),bytes.size(),proof),"valid proof reparsed after rejection");
            std::size_t firstDigest=12;
            for(unsigned n=0;n<6;++n) {
                const unsigned length=bytes[firstDigest]|(unsigned(bytes[firstDigest+1])<<8)|
                    (unsigned(bytes[firstDigest+2])<<16)|(unsigned(bytes[firstDigest+3])<<24);
                firstDigest+=4+length;
            }
            std::copy(bytes.begin()+firstDigest,bytes.begin()+firstDigest+32,bytes.begin()+firstDigest+32);
            Check(!ParsePackageProof(bytes.data(),bytes.size(),proof),"duplicate proof digest rejected");bytes=original;
            for (std::size_t n=0;n<bytes.size();++n)
                Check(!ParsePackageProof(bytes.data(),n,proof),"truncated proof rejected");
            bytes.push_back(0);Check(!ParsePackageProof(bytes.data(),bytes.size(),proof),"trailing proof rejected");
        }
        auto baseline=[](LoadProof& proof) {
            for (int i=0;i<6;++i) Check(proof.Begin(i),"nested baseline entry");
            for (int i=5;i>=0;--i) Check(proof.Complete(i,true),"nested baseline completion");
            Check(!proof.Ready(),"baseline alone is never generated output proof");
        };
        { // Captured Public order: baseline, postload, dataset/common, trailing baseline.
          using namespace MajestyBcdOwnership;
          BatchOwnership batch; const std::set<std::string> names{"make_attack"};
          const Definitions generated{{1,"make_attack"},{3,"make_attack"}};
          const Definitions unrelated{{1,"QuestStart"}};
          Check(!batch.BaselineRetainsWinners(unrelated,names),"empty batch cannot borrow generated readiness");
          LoadProof proof(true);baseline(proof);
          Check(proof.Begin(8)&&proof.Complete(8,true),"captured dataset first");
          Check(proof.Begin(6)&&proof.Complete(6,true)&&proof.Ready(),"captured common second");
          batch.Complete(generated,names,true);
          Check(batch.BaselineRetainsWinners(generated,names),"exact duplicates retain generated winner");
          Check(!batch.BaselineRetainsWinners({{1,"MAKE_ATTACK"}},names),"case-only symbol cannot borrow winner");
          Check(batch.BaselineRetainsWinners({{1,"stock_hit"}},{"stock_hit"}),"audited baseline supplies unchanged protected callback");
          Check(!batch.Admit({{1,"stock_hit"}},{"stock_hit"},false,false),"optional mod cannot claim unchanged stock callback");
          Check(batch.ContinuationIndex(5,false,true,generated,names)==5,"unknown caller cannot preserve baseline readiness");
          Check(batch.ContinuationIndex(5,true,false,generated,names)==5,"incomplete output cannot preserve baseline readiness");
          Check(batch.ContinuationIndex(-1,true,true,generated,names)==-1,"unrecognized digest is not a baseline continuation");
          Check(batch.ContinuationIndex(6,true,true,generated,names)==6,"repeated generated output is not a baseline continuation");
          for(int i=5;i>=0;--i) {
              const int admitted=batch.ContinuationIndex(i,true,proof.Ready(),generated,names);
              Check(admitted==-2&&proof.Begin(admitted)&&!proof.Ready(),"trailing baseline in progress suspends readiness");
              Check(proof.Complete(admitted,true)&&proof.Ready(),"trailing same-batch duplicate preserves proof");
          }
          batch.Reset();Check(!batch.BaselineRetainsWinners(generated,names),"postload closes duplicate evidence");
          Check(proof.Begin(5)&&proof.Complete(5,true)&&!proof.Ready(),"real later baseline still resets proof");
          BatchOwnership stockFirst;stockFirst.Complete(generated,names,false);
          stockFirst.Complete(unrelated,names,true);
          Check(!stockFirst.Admit(generated,names,true,false),"stock-first owner rejects later generated replacement");
        }
        { LoadProof proof;baseline(proof);Check(proof.Begin(6),"generated output entry");
          Check(!proof.Ready(),"output load in progress is unknown");
          Check(proof.Complete(6,true) && proof.Ready(),"actual generated output completes");
          Check(proof.Begin(7) && !proof.Ready(),"optional load suppresses readiness");
          Check(proof.Complete(7,true) && proof.Ready(),"nonoverriding optional completion");
          baseline(proof);Check(proof.Begin(6) && proof.Complete(6,true) && proof.Ready(),"full script reload rebuilds proof"); }
        { LoadProof proof;Check(!proof.Begin(6) && proof.Faulted(),"output before baseline rejected"); }
        { LoadProof proof;Check(!proof.Begin(-1) && proof.Faulted(),"unknown digest rejected");
          Check(!proof.Begin(0) && !proof.Ready(),"script reload cannot erase provenance fault"); }
        { LoadProof proof;proof.Begin(0);proof.Begin(1);
          Check(!proof.Complete(0,true),"out of stack order completion rejected"); }
        { LoadProof proof;proof.Begin(0);
          Check(!proof.Complete(0,true),"missing nested baseline callbacks rejected"); }
        { LoadProof proof;baseline(proof);proof.Begin(6);
          Check(!proof.Complete(6,false) && !proof.Ready(),"native output load failure rejected"); }
        { LoadProof proof;baseline(proof);proof.Begin(6);proof.Complete(6,true);
          Check(!proof.Begin(6),"output replacement without baseline reset rejected"); }
        for (int dataset:{7,8}) {
          LoadProof proof(true);baseline(proof);proof.Begin(6);proof.Complete(6,true);
          Check(!proof.Ready(),"scoped common output is incomplete");
          Check(proof.Begin(dataset) && proof.Complete(dataset,true) && proof.Ready(),"exact dataset patch completes proof");
          Check(!proof.Begin(dataset==7?8:7),"mixed dataset patches rejected"); }
        for(int dataset:{7,8}) { LoadProof proof(true);
            for(int i=5;i>=0;--i)Check(proof.Begin(i)&&proof.Complete(i,true),"sequential native baseline");
            Check(proof.Begin(-2)&&proof.Complete(-2,true),"inspected unrelated quest admitted");
            Check(proof.Begin(dataset)&&proof.Complete(dataset,true)&&!proof.Ready(),"dataset first remains incomplete");
            Check(proof.Begin(6)&&proof.Complete(6,true)&&proof.Ready(),"native dataset-before-common accepted");
            Check(proof.Begin(-2)&&!proof.Ready()&&proof.Complete(-2,true)&&proof.Ready(),"unrelated later mod preserves proof");
        }
        for (unsigned i=0;i<6;++i) {
          const unsigned attribute=0x18425041u+(i<<24);
          Check(MajestyResearchCompletion::MatchesStockTemplate(5000+i,attribute),"stock research completion identity");
          Check(!MajestyResearchCompletion::MatchesStockTemplate(5000+i,attribute^0x01000000),"wrong research completion identity rejected"); }
        Check(MajestyResearchCompletion::MatchesStockTemplate(5010,0x1E425041),"tournament completion identity");
        Check(MajestyResearchCompletion::MatchesStockTemplate(5020,0x2A425041),"arrows completion identity");
        Check(MajestyResearchCompletion::MatchesStockTemplate(5021,0x2B425041),"guard completion identity");
        Check(!MajestyResearchCompletion::MatchesStockTemplate(5020,0x27425041),"unrelated potion flag rejected");
        Check(MajestyResearchCompletion::MatchesStockTemplate(0x13A6,0x1234),"other existing research templates retained");
        Check(!MajestyResearchCompletion::MatchesStockTemplate(0x139C,0),"missing completion attribute rejected");
        { CombatContext context{10,20,30,40,1};
          { CombatScope nested(context,{11,21,31,40,1});
            Check(ContextId(context,10,20)==0,"nested scope cannot borrow outer shot");
            Check(ContextId(context,11,21)==31,"nested scope owns its shot"); }
          Check(ContextId(context,10,20)==30,"outer scope restored");
          Check(ContextId(context,10,21)==0,"wrong target has no shot"); }
        { Fixture f;
          const auto order=f.Missile(30); Address unit{},stack{};
          f.Read(f.last+0xC,&unit,4); f.Read(unit+0x98,&stack,4);
          f.Put(order,0,0x740514); f.Put(order,0x38,20);
          unsigned reads=0,failAt=0;
          auto read=[&](Address p,unsigned offset,Address& value) {
              ++reads;
              return reads!=failAt && p && p<=UINT32_MAX-offset && f.Read(p+offset,&value,4);
          };
          auto capture=[&](unsigned event=2,Address table=0x740514) {
              reads=0;return CaptureTerminalMissile(read,stack,order,event,table,9);
          };
          const auto current=capture();
          Check(current.unit==unit && current.engine==f.profile.projectileEngine,
                "current dispatched projectile descriptor retained");
          Check(ContextId(current.identity,10,20)==30 && current.identity.generation==9,
                "terminal event captures source target and epoch");
          const auto requiredReads=reads;
          for(unsigned n=1;n<=requiredReads;++n) {
              failAt=n;const auto missing=capture();
              Check(!missing.unit && !missing.identity.projectile,
                    "partial read cannot publish partial impact context");
          }
          failAt=0;
          Check(!capture(1).unit && !capture(3).unit,"cancel and submit events excluded");
          Check(!capture(2,0).unit && !capture(2,0x759214).unit,"missing or other-profile vtable excluded");
          f.Put(order,0x10,2);Check(!capture().unit,"animation order excluded");
          f.Put(order,0x10,3);f.Put(order,0x2C,0x1005);
          Check(!capture().unit,"final animation is not missile impact");
        }
        for (unsigned id : {0u,2097152u,4194304u,2147483647u,4294967295u}) {
          Fixture f; Lifecycle l; ShotSnapshot s; f.Attach(l);
          Check(!l.ContextAllowed(f,f.profile,f.world,l.Generation(),10,id),"unsupported callback ID fails closed");
          const int token=s.Begin(f,f.profile,l,f.actor,10);
          Check(s.Pending(f,f.profile,l,f.actor,10,token,id)==-1,"unsupported snapshot ID is unknown not absent"); }
        { Fixture f; f.Missile(kMaximumIdentity);
          Check(f.InspectNow().result==Result::Busy,"highest supported identity preserved"); }
        { Fixture f; f.Missile(kMaximumIdentity+1);
          Check(f.InspectNow().result==Result::Unknown,"unsupported native identity never settles"); }
        { Fixture f; Check(f.InspectNow().result==Result::Settled,"empty actor"); }
        { Fixture f; f.Order(f.actor,1,10,0); Check(f.InspectNow().result==Result::Busy,"action pending"); }
        { Fixture f; auto o=f.Order(f.actor,2,11,0); f.Put(o,0x50,0x1000); f.Put(o,0x6C,1); Check(f.InspectNow().result==Result::Busy,"released animation still owned"); }
        { Fixture f; auto o=f.Order(f.actor,2,11,0); f.Put(o,0x50,0x1001); Check(f.InspectNow().result==Result::Settled,"unrelated follow on"); }
        { Fixture f; f.Order(f.actor,0,7,0x1008); Check(f.InspectNow().result==Result::Busy,"setup continuation"); }
        { Fixture f; f.Missile(11); f.Missile(12); auto c=f.InspectNow(); Check(c.result==Result::Busy && c.missiles==2,"all outstanding missiles"); }
        { Fixture f; auto o=f.Missile(11); f.Put(o,0x18,4); unsigned unit=0; f.Read(f.last+0xC,&unit,4); f.Put(unit,0x74,4); Check(f.InspectNow().result==Result::Busy,"projectile unit removal flag is not unlink"); }
        { Fixture f; f.Put(f.actor,0x74,4); Check(f.InspectNow().result==Result::Unknown,"actor removal request cancels decision"); }
        { Fixture f; f.profile.retirementMethod=0x448400; Check(f.InspectNow().result==Result::Unknown,"uncovered concrete retirement virtual"); }
        { Fixture f; f.Missile(11); f.Put(f.profile.movementEngine,0x24,4); Check(f.InspectNow().result==Result::Unknown,"physics route"); }
        { Fixture f; f.Missile(11); f.Put(f.profile.impactGlobal,0,0x999999); Check(f.InspectNow().result==Result::Unknown,"changed callback"); }
        { Fixture f; f.Missile(11); auto indirect=f.Alloc(); unsigned text=0; f.Read(f.profile.projectileEngine+0x90,&text,4); f.Put(indirect,0,text); f.Put(f.profile.projectileEngine,0x90,indirect); Check(f.InspectNow().result==Result::Unknown,"script descriptor must be embedded not double-indirected"); }
        { Fixture f; f.Unit(10); Check(f.InspectNow().result==Result::Unknown,"duplicate native identity"); }
        { Fixture f; f.Put(f.last,0,f.last); Check(f.InspectNow().result==Result::Unknown,"cyclic native list"); }
        { Fixture f; f.Put(f.catalog,0x20,0); Check(f.InspectNow().result==Result::Unknown,"missing catalog not empty"); }
        { Fixture f; f.Put(f.treeHead,4,f.treeHead); Check(f.InspectNow().result==Result::Unknown,"tree ID missing while list retains unit"); }
        { Fixture f; f.Put(f.last,8,99); Check(f.InspectNow().result==Result::Unknown,"list ID differs from unit ID"); }
        { Fixture f; f.profile.effectivePackage=false; Check(f.InspectNow().result==Result::Unknown,"unpinned package"); }
        { Fixture f; f.profile.lifecycleBound=false; Check(f.InspectNow().result==Result::Unknown,"unbound hooks"); }
        { Fixture f; f.Put(f.runtime,4,0); Check(f.InspectNow().result==Result::Unknown,"world mismatch"); }
        { Fixture f; Lifecycle l; f.Missile(11); Check(f.Attach(l,3) && l.Query(f,f.profile,f.actor,10).result==Result::Busy,"loaded direct insertion"); }
        for (int mode: {1,2,4}) { Fixture f; Lifecycle l; Check(!f.Attach(l,mode),"unsupported startup mode"); }
        { Fixture f; Lifecycle l; Check(!f.Attach(l,0,1),"failed load"); }
        for (auto build:{MajestyBuildId::SteamPublic,MajestyBuildId::SteamBeta2,MajestyBuildId::Gog}) {
            const auto* routes=WorldAttachmentFor(build);
            Check(routes!=nullptr,"explicit attachment profile");
            for(auto caller:{routes->createdReturn,routes->creationReturn2,routes->creationReturn3}) {
                Check(routes->Classify(caller,0,42,-1,0)==AttachmentRoute::Created,"direct completed builder route");
                Check(routes->Classify(caller,0,0,-1,0)==AttachmentRoute::None,"null created world");
                for(unsigned mode:{1u,2u,3u,4u})
                    Check(routes->Classify(caller,mode,42,0,42)==AttachmentRoute::None,"creation never borrows saved mode");
            }
            Check(routes->Classify(routes->createdReturn,0,42,-1,0)==AttachmentRoute::Created,"new world without save status");
            Check(routes->Classify(routes->createdReturn,0,42,7,99)==AttachmentRoute::Created,"stale failed load is not new-world evidence");
            Check(routes->Classify(routes->savedReturn,0,42,0,42)==AttachmentRoute::Saved,"matching saved world");
            Check(routes->Classify(routes->savedMenuReturn,0,42,0,42)==AttachmentRoute::Saved,"menu matching saved world");
            Check(routes->Classify(routes->savedMenuReturn,0,42,-1,42)==AttachmentRoute::None,"menu requires observed load");
            Check(routes->Classify(routes->savedMenuReturn,0,42,1,42)==AttachmentRoute::None,"menu failed load");
            Check(routes->Classify(routes->savedMenuReturn,0,42,0,99)==AttachmentRoute::None,"menu different output");
            Check(routes->Classify(routes->savedMenuReturn,0,0,0,0)==AttachmentRoute::None,"menu null output");
            for(unsigned mode:{1u,2u,3u,4u})
                Check(routes->Classify(routes->savedMenuReturn,mode,42,0,42)==AttachmentRoute::None,"menu only mode zero");
            Check(routes->Classify(routes->savedReturn,0,42,1,42)==AttachmentRoute::None,"failed save route never treated as creation");
            Check(routes->Classify(routes->savedReturn,0,42,0,99)==AttachmentRoute::None,"different restored world");
            Check(routes->Classify(routes->createdReturn,0,0,0,0)==AttachmentRoute::None,"failed builder cannot attach");
            Check(routes->Classify(routes->createdReturn+1,0,42,0,42)==AttachmentRoute::None,"unknown caller cannot attach");
            for (unsigned mode:{1u,2u,3u,4u})
                Check(routes->Classify(routes->createdReturn,mode,42,0,42)==AttachmentRoute::None,"creation admits only proved mode0");
        }
        Check(!WorldAttachmentFor(static_cast<MajestyBuildId>(255)),"unknown build has no attachment profile");
        { Fixture f; Lifecycle l;
          Check(std::string(l.Failure())=="never-attached","initial lifecycle reason");
          f.Attach(l);
          Check(std::string(l.Failure())=="none","accepted attachment clears reason");
          l.IdentityIncoherent("spawn-failed-readiness-invalidated");
          Check(std::string(l.Failure())=="spawn-failed-readiness-invalidated","retain explicit invalidation origin");
          Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"reason reporting never grants settlement");
          f.Attach(l);
          Check(std::string(l.Failure())=="none","new verified attachment clears old origin"); }
        { Fixture f; Lifecycle l; f.Missile(11);
          Check(l.AttachCreated(f,f.profile,0,f.world,f.catalog),"created world admitted after native attachment");
          Check(l.Query(f,f.profile,f.actor,10).result==Result::Busy,"created world observes already submitted orders"); }
        for (int mode:{1,2,3,4}) { Fixture f; Lifecycle l;f.Attach(l);
          Check(!l.AttachCreated(f,f.profile,mode,f.world,f.catalog),"invalid creation mode");
          Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"rejected creation invalidates previous world"); }
        { Fixture f; Lifecycle l;f.Put(f.runtime,0x10,f.world+4);
          Check(!l.AttachCreated(f,f.profile,0,f.world,f.catalog),"incomplete runtime attachment rejected");
          Check(std::string(l.Failure())=="attach-world-mismatch","world mismatch distinguished"); }
        { Fixture f; Lifecycle l;l.EnterOperation();
          Check(!l.AttachCreated(f,f.profile,0,f.world,f.catalog),"nested construction cannot publish readiness");l.LeaveOperation(); }
        { Fixture f; Lifecycle l;f.profile.effectivePackage=false;
          Check(!l.AttachCreated(f,f.profile,0,f.world,f.catalog),"creation does not bypass package provenance");
          Check(std::string(l.Failure())=="attach-package","package rejection distinguished"); }
        { Fixture f; Lifecycle l; f.Attach(l); l.EnterOperation(); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"outer callback nesting"); l.LeaveOperation(); Check(l.Query(f,f.profile,f.actor,10).result==Result::Settled,"outer return"); }
        { Fixture f; Lifecycle l; f.Attach(l); auto token=l.BeginRetirement(f.actor,10); l.EndRetirement(token,true); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"copied identity retired and reused"); }
        { Fixture f; Lifecycle l; f.Attach(l); auto a=l.BeginRetirement(f.actor,10),b=l.BeginRetirement(f.actor,10); l.EndRetirement(b,true); l.EndRetirement(a,true); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"same unit reentry"); }
        { Fixture f; Lifecycle l; f.Attach(l); auto a=l.BeginRetirement(0xAAA,20),b=l.BeginRetirement(0xBBB,21); l.EndRetirement(b,true); l.EndRetirement(a,true); Check(l.Query(f,f.profile,f.actor,10).result==Result::Settled,"nested distinct retirement identities"); }
        { Fixture f; Lifecycle l; f.Attach(l); auto token=l.BeginRetirement(0xAAA,20); l.EndRetirement(token,false); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"nonreturning retirement"); }
        { Fixture f; Lifecycle l; f.Attach(l); l.BeginWorldTeardown(); l.LeaveOperation(); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"bulk teardown independent of queue"); }
        { Fixture f; Lifecycle l; f.Attach(l); l.IdentityIncoherent(); Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"unlink AL1 cannot repair incoherent identity"); }
        { Fixture f; Lifecycle l; f.Attach(l); const auto generation=l.Generation();
          l.EnterOperation();
          Check(l.ContextAllowed(f,f.profile,f.world,generation,10,11),"synchronous callback context allowed while settled query remains unavailable");
          Check(l.Query(f,f.profile,f.actor,10).result==Result::Unknown,"callback context never grants settled status");
          l.LeaveOperation();
          Check(!l.ContextAllowed(f,f.profile,f.world+1,generation,10,11),"wrong callback world rejected");
          f.Put(f.runtime,4,0);
          Check(!l.ContextAllowed(f,f.profile,f.world,generation,10,11),"detached runtime world rejected"); }
        { Fixture f; Lifecycle l; f.Attach(l); const auto generation=l.Generation();
          l.BeginWorldTeardown();l.LeaveOperation();
          Check(!l.ContextAllowed(f,f.profile,f.world,generation,10,11),"teardown rejects in-flight old callback identity");
          f.Attach(l,3);
          Check(!l.ContextAllowed(f,f.profile,f.world,generation,10,11),"reused world pointer and numeric IDs cannot revive old scope generation");
          Check(l.ContextAllowed(f,f.profile,f.world,l.Generation(),10,11),"restored current world can issue a fresh scope"); }
        { Fixture f; Lifecycle l; f.Attach(l); const auto generation=l.Generation();
          auto token=l.BeginRetirement(0xAAA,11);
          Check(!l.ContextAllowed(f,f.profile,f.world,generation,10,11),"retirement in progress denies payload lookup");
          l.EndRetirement(token,true);
          Check(!l.ContextAllowed(f,f.profile,f.world,generation,10,11),"retired projectile identity cannot revive payload");
          l.IdentityIncoherent();
          Check(!l.ContextAllowed(f,f.profile,f.world,l.Generation(),10,12),"failed load or identity invalidation denies context"); }
        { Fixture f; Lifecycle l; for (unsigned i=0;i<64;++i) f.Missile(11+i);f.Attach(l,3);
          const auto capture=l.Query(f,f.profile,f.actor,10);
          Check(capture.result==Result::Busy && capture.missiles==64,"64 native outstanding bolts remain busy independently of 32 GPL payload slots"); }
        { Fixture f; Lifecycle l; ShotSnapshot s; f.Missile(11);f.Missile(43);f.Attach(l,3);
          const int token=s.Begin(f,f.profile,l,f.actor,10);
          Check(token>0,"snapshot opened from restored native lists");
          Check(s.Pending(f,f.profile,l,f.actor,10,token,11)==1 && s.Pending(f,f.profile,l,f.actor,10,token,43)==1,"same-modulo full IDs both pending");
          Check(s.Pending(f,f.profile,l,f.actor,10,token,75)==0,"absent exact ID reclaimable");
          Check(s.Pending(f,f.profile,l,f.actor+1,10,token,11)==-1,"wrong pointer unknown");
          Check(s.Pending(f,f.profile,l,f.actor,12,token,11)==-1,"wrong actor ID unknown");
          Check(s.Pending(f,f.profile,l,f.actor,10,token+1,11)==-1,"wrong token unknown");
          l.EnterOperation();l.LeaveOperation();
          Check(s.Pending(f,f.profile,l,f.actor,10,token,11)==-1,"completed native mutation invalidates snapshot");
          const int fresh=s.Begin(f,f.profile,l,f.actor,10);
          Check(fresh>token,"fresh token never aliases old token");s.End(token);
          Check(s.Pending(f,f.profile,l,f.actor,10,fresh,11)==1,"stale close cannot close new snapshot");s.End(fresh);
          Check(s.Pending(f,f.profile,l,f.actor,10,fresh,11)==-1,"explicit close invalidates snapshot"); }
        { Fixture f; Lifecycle l; ShotSnapshot s;f.Attach(l);const int old=s.Begin(f,f.profile,l,f.actor,10);
          f.Attach(l,3);
          Check(s.Pending(f,f.profile,l,f.actor,10,old,11)==-1,"save-load generation rejects stale snapshot with reused pointers");
          const int fresh=s.Begin(f,f.profile,l,f.actor,10);
          Check(s.Pending(f,f.profile,l,f.actor,10,fresh,11)==0,"new generation can prove absence");
          f.Put(f.runtime,4,0);
          Check(s.Pending(f,f.profile,l,f.actor,10,fresh,11)==-1,"world detachment rejects snapshot"); }
        { Fixture f; Lifecycle l; ShotSnapshot s;f.Attach(l);l.EnterOperation();
          Check(s.Begin(f,f.profile,l,f.actor,10)==0,"cannot snapshot during release or impact guard");l.LeaveOperation();
          f.Missile(11);f.Put(f.profile.movementEngine,0x24,4);
          Check(s.Begin(f,f.profile,l,f.actor,10)==0,"unproved projectile profile never proves absence"); }
        { Fixture f;Lifecycle l;f.Attach(l);
          Check(!l.RecordedRetirement(11),"no invented retirement");auto token=l.BeginRetirement(0xAAA,11);
          Check(!l.RecordedRetirement(11),"retirement request is not concrete return");l.EndRetirement(token,true);
          Check(l.RecordedRetirement(11),"completed concrete retirement can reclaim during later release");
          f.Attach(l,3);Check(!l.RecordedRetirement(11),"load clears old-generation retirement evidence"); }
        std::cout << "{\"native_fixture_assertions\":" << tests << ",\"live_game_tested\":false}\n";
    } catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}

