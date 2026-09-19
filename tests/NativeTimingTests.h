// Production GPL wrappers exercised against borrowed stock-layout fixtures.
namespace TimingTest {
using NativeTest::Put;
void* live = nullptr;
void* effect = nullptr;
void* expiry = nullptr;
void* descriptor = nullptr;
void* catalog = nullptr;
int effectCalls = 0, orderCalls = 0;
constexpr unsigned actionId = 0x3130615Au; // Za01
void* __fastcall Reference(void* object,void*) { return object; }
void* __fastcall Resolve(void* reference,void*) {
    assert(Read<unsigned>(reference,8) == 42);
    Put(reference,0x0C,123u);
    return live;
}
void* __fastcall Find(void* current,void*,const char* name) {
    assert(current == catalog);
    return std::strcmp(name,"Example") == 0 ? descriptor : nullptr;
}
void* __fastcall Effect(void* current,void*,unsigned id) {
    assert(current == live && id == actionId);
    ++effectCalls;
    return effect;
}
void* __fastcall Order(void* current,void*,int group,int kind) {
    assert(current == effect && group == 1 && kind == 9);
    ++orderCalls;
    return expiry;
}
void Run() {
    using namespace MajestyNativeTiming;
    assert(Elapsed(2000,1000) == 1000 && Elapsed(1000,1000) == 0);
    assert(Elapsed(50,0xfffffff0u) == 66 && Elapsed(0xffffffffu,0) == 0x7fffffff);
    assert(Remaining(1500,1000,2000,0) == 1500);
    assert(Remaining(3000,1000,2000,0) == 0 && Remaining(4000,1000,2000,0) == 0);
    assert(Remaining(50,0xfffffff0u,100,0) == 34);
    assert(Remaining(4000,1000,2000,1) == kNoExpiry);
    assert(Remaining(0,0,0xffffffffu,0) == 0x7fffffff);
    MajestyRuntimeFeatures::Registry registry;
    assert(!InstallMapQueryRuntime(0,MajestyBuildId::SteamBeta2,false,false,&registry));
    registry.nativeTiming = true;
    registry.timingSpellIds = {actionId};
    registry.timingEffectorIds = {actionId};
    g_timing = &registry;

    unsigned char unit[0x184] = {}, desc[0x1C] = {}, game[0x20] = {};
    unsigned char dmov[0x18] = {}, movementEngine[0x38] = {}, actionEngine[0x4C] = {};
    unsigned char overlay[0xA8] = {}, order[0x34] = {}, head[0x18] = {}, node[0x18] = {};
    void* unitTable[0x184/4] = {};
    void* effectTable[0x184/4] = {};
    void* valueTable[24] = {};
    void* movementTable[4] = {};
    void* actionTable[4] = {};
    unitTable[0x140/4] = reinterpret_cast<void*>(&Effect);
    unitTable[0x158/4] = reinterpret_cast<void*>(&MovementTest::Interval);
    effectTable[0x180/4] = reinterpret_cast<void*>(&Order);
    valueTable[0x5C/4] = reinterpret_cast<void*>(&Reference);
    valueTable[0x28/4] = reinterpret_cast<void*>(&NativeTest::AsInt);
    valueTable[0x30/4] = reinterpret_cast<void*>(&MovementTest::AsString);
    Put(unit,0,static_cast<void*>(unitTable));
    Put(overlay,0,static_cast<void*>(effectTable));
    Put(desc,4,actionId); Put(desc,0x18,static_cast<void*>(game));
    Put(desc,8,1); Put(desc,0x14,static_cast<void*>(actionEngine));
    Put(actionEngine,0,static_cast<void*>(actionTable)); Put(actionEngine,0x28,1100);
    Put(unit,0x54,static_cast<void*>(dmov)); Put(dmov,8,1);
    Put(dmov,0x14,static_cast<void*>(movementEngine));
    Put(movementEngine,0,static_cast<void*>(movementTable)); Put(movementEngine,0x0C,57);
    Put(game,0x0C,5000u);
    Put(unit,0x17C,static_cast<void*>(head)); Put(unit,0x180,1u);
    Put(head,0,static_cast<void*>(node)); Put(head,4,static_cast<void*>(node));
    Put(node,0,static_cast<void*>(head)); Put(node,4,static_cast<void*>(head));
    Put(node,8,actionId); Put(node,0x0C,10u); Put(node,0x10,99u); Put(node,0x14,0xabcdef01u);
    Put(order,8,1000u); Put(order,0x0C,2000u); Put(order,0x10,9u); Put(order,0x2C,0x100Du);
    std::uint32_t clock = 2000;
    live = unit; effect = overlay; expiry = order; descriptor = desc;
    void* currentCatalog = desc;
    catalog = currentCatalog;
    Profile profile = kBeta;
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&NativeTest::At);
    TimingProfile timing = kTimingBeta;
    timing.resolveUnit = reinterpret_cast<std::uintptr_t>(&Resolve);
    timing.findDescription = reinterpret_cast<std::uintptr_t>(&Find);
    timing.actionCatalog = timing.unitCatalog = reinterpret_cast<std::uintptr_t>(&currentCatalog);
    timing.clockGlobal = reinterpret_cast<std::uintptr_t>(&clock);
    timing.getEffector = reinterpret_cast<std::uintptr_t>(&Effect);
    timing.getOrder = reinterpret_cast<std::uintptr_t>(&Order);
    timing.vehicleVtable = reinterpret_cast<std::uintptr_t>(unitTable);
    timing.actionEngineVtable = reinterpret_cast<std::uintptr_t>(actionTable);
    MovementProfile movement = kMovementBeta;
    movement.resolveUnit = reinterpret_cast<std::uintptr_t>(&Resolve);
    movement.movementVtable = reinterpret_cast<std::uintptr_t>(movementTable);
    movement.effectiveInterval = reinterpret_cast<std::uintptr_t>(&MovementTest::Interval);
    g_movementProfile = &movement;
    g_base = 0; g_profile = &profile; g_timingProfile = &timing;
    NativeTest::Value value{valueTable,5,42,999};
    const auto originalValue = value;
    unsigned char originalUnit[sizeof(unit)]; std::memcpy(originalUnit,unit,sizeof(unit));
    unsigned char originalAction[sizeof(actionEngine)]; std::memcpy(originalAction,actionEngine,sizeof(actionEngine));
    unsigned char originalMovement[sizeof(movementEngine)]; std::memcpy(originalMovement,movementEngine,sizeof(movementEngine));
    // Raw periods: neither rounding nor attributes nor learned-spell ownership
    // affects a read-only loaded-description query. No native state is touched.
    registry.timingSpellIds.clear(); registry.timingEffectorIds.clear();
    for (int i = 0; i < 100; ++i) {
        assert(UnitMovementBasePeriod(&value) == 57);
        assert(ActionBasePeriod("Example") == 1100);
    }
    assert(std::memcmp(unit,originalUnit,sizeof(unit)) == 0);
    assert(std::memcmp(actionEngine,originalAction,sizeof(actionEngine)) == 0);
    assert(std::memcmp(movementEngine,originalMovement,sizeof(movementEngine)) == 0);
    assert(std::memcmp(&value,&originalValue,sizeof(value)) == 0);
    Put(actionEngine,0x28,500); assert(ActionBasePeriod("Example") == 500);
    Put(actionEngine,0x28,0); assert(ActionBasePeriod("Example") == 0);
    Put(actionEngine,0x28,-1); assert(ActionBasePeriod("Example") == kUnsupported);
    Put(actionEngine,0x28,0x7fffffff); assert(ActionBasePeriod("Example") == 0x7fffffff);
    Put(actionEngine,0x28,1100);
    Put(desc,8,2); assert(ActionBasePeriod("Example") == kUnsupported); Put(desc,8,1);
    Put(actionEngine,0,static_cast<void*>(movementTable));
    assert(ActionBasePeriod("Example") == kUnsupported); Put(actionEngine,0,static_cast<void*>(actionTable));
    Put(desc,0x14,static_cast<void*>(nullptr)); assert(ActionBasePeriod("Example") == kUnsupported);
    Put(desc,0x14,static_cast<void*>(actionEngine));
    assert(ActionBasePeriod("Missing") == kInvalid && ActionBasePeriod("") == kInvalid);
    assert(ActionBasePeriod(nullptr) == kInvalid);
    void* savedCatalog = currentCatalog; currentCatalog = nullptr;
    assert(ActionBasePeriod("Example") == kInvalid); currentCatalog = savedCatalog;
    live = nullptr; assert(UnitMovementBasePeriod(&value) == kInvalid); live = unit;
    assert(UnitMovementBasePeriod(nullptr) == kInvalid);
    Put(unit,0x54,static_cast<void*>(nullptr)); assert(UnitMovementBasePeriod(&value) == kUnsupported);
    Put(unit,0x54,static_cast<void*>(dmov));
    Put(dmov,8,2); assert(UnitMovementBasePeriod(&value) == kUnsupported); Put(dmov,8,1);
    unitTable[0x158/4] = nullptr; assert(UnitMovementBasePeriod(&value) == kUnsupported);
    unitTable[0x158/4] = reinterpret_cast<void*>(&MovementTest::Interval);
    Put(movementEngine,0x0C,0); assert(UnitMovementBasePeriod(&value) == 0);
    Put(movementEngine,0x0C,-1); assert(UnitMovementBasePeriod(&value) == kUnsupported);
    Put(movementEngine,0x0C,57);
    registry.timingSpellIds = {actionId}; registry.timingEffectorIds = {actionId};
    unsigned char originalOrder[sizeof(order)]; std::memcpy(originalOrder,order,sizeof(order));
    unsigned char originalNode[sizeof(node)]; std::memcpy(originalNode,node,sizeof(node));
    for (int i = 0; i < 100; ++i) assert(EffectorRemaining(&value,"Example") == 1000);
    assert(std::memcmp(order,originalOrder,sizeof(order)) == 0);
    assert(std::memcmp(node,originalNode,sizeof(node)) == 0);
    assert(std::memcmp(&value,&originalValue,sizeof(value)) == 0);
    clock = 3000; assert(EffectorRemaining(&value,"Example") == 0);
    // A native refresh is visible immediately, without stale Manager state.
    Put(order,8,3000u); assert(EffectorRemaining(&value,"Example") == 2000);
    Put(order,0x18,1u); assert(EffectorRemaining(&value,"Example") == kNoExpiry); Put(order,0x18,0u);
    expiry = nullptr; assert(EffectorRemaining(&value,"Example") == kNoExpiry); expiry = order;
    effect = nullptr; assert(EffectorRemaining(&value,"Example") == 0); effect = overlay;
    live = nullptr; assert(EffectorRemaining(&value,"Example") == kInvalid);
    assert(CommitSpellCooldown(&value,"Example") == kInvalid); live = unit;
    Put(order,0x2C,0x100Eu); assert(EffectorRemaining(&value,"Example") == kUnsupported); Put(order,0x2C,0x100Du);
    effectTable[0x180/4] = nullptr;
    assert(EffectorRemaining(&value,"Example") == kUnsupported);
    effectTable[0x180/4] = reinterpret_cast<void*>(&Order);
    registry.timingEffectorIds.clear(); registry.timingSpellIds.clear();
    const int queries = effectCalls;
    assert(EffectorRemaining(&value,"Example") == kUndeclared && effectCalls == queries);
    assert(CommitSpellCooldown(&value,"Example") == kUndeclared);
    registry.timingEffectorIds = {actionId}; registry.timingSpellIds = {actionId};
    assert(CommitSpellCooldown(&value,"Missing") == kInvalid);
    assert(CommitSpellCooldown(&value,"") == kInvalid);
    // Only the native timeout and timestamp change, preserving every byte of
    // links, ID, availability and padding. Nothing happens before completion.
    assert(std::memcmp(node,originalNode,sizeof(node)) == 0);
    assert(CommitSpellCooldown(&value,"Example") == 1);
    Put(originalNode,0x0C,clock); Put(originalNode,0x10,5000u);
    assert(std::memcmp(node,originalNode,sizeof(node)) == 0);
    assert(std::memcmp(&value,&originalValue,sizeof(value)) == 0);
    Put(node,8,actionId+1); assert(CommitSpellCooldown(&value,"Example") == 0); Put(node,8,actionId);
    Put(unit,0,static_cast<void*>(effectTable));
    assert(CommitSpellCooldown(&value,"Example") == kUnsupported); Put(unit,0,static_cast<void*>(unitTable));
    Put(game,0x0C,0xffffffffu); assert(CommitSpellCooldown(&value,"Example") == kUnsupported); Put(game,0x0C,5000u);
    Put(node,4,static_cast<void*>(node)); assert(CommitSpellCooldown(&value,"Example") == kUnsupported);
    Put(node,4,static_cast<void*>(head));

    NativeTest::Value result{valueTable,1,0,0};
    MovementTest::StringValue string{valueTable,"Example"};
    void* objects[] = {&result,&value,&string};
    void** entries[] = {&objects[0],&objects[1],&objects[2]};
    NativeTest::Args args{nullptr,{},entries,entries+3};
    MovementBasePeriod(&args); assert(result.x == 57);
    objects[1] = &string; NamedActionBasePeriod(&args); assert(result.x == 1100);
    objects[1] = &value;
    CommitCooldown(&args); assert(result.x == 1);
    RemainingEffector(&args); assert(result.x == 2000);
    SimulationTime(&args); assert(result.x == 3000);
    objects[1] = &result; result.x = 1000;
    SimulationElapsed(&args); assert(result.x == 2000); // aliased timestamp
    clock = 0xfffffff0u; SimulationTime(&args); assert(static_cast<unsigned>(result.x) == clock);
    clock = 50; SimulationElapsed(&args); assert(result.x == 66);
    args.end = entries+1; SimulationElapsed(&args); assert(result.x == kInvalid);
    args.end = entries+2; RemainingEffector(&args); assert(result.x == kInvalid);
    args.end = entries+1;
    MovementBasePeriod(&args); assert(result.x == kInvalid);
    NamedActionBasePeriod(&args); assert(result.x == kInvalid);
    g_profile = nullptr; g_timingProfile = nullptr; g_timing = nullptr; g_movementProfile = nullptr;
}
}
