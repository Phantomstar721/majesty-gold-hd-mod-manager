// Included after the native map-query fixture: exercises the production GPL
// wrappers and borrowed native layouts without running or mutating Majesty.
namespace MovementTest {
using NativeTest::Put;
void* live = nullptr;
void* named = nullptr;
void* catalog = nullptr;
int modifier = 0, intervalCalls = 0, lookupCalls = 0;
int ScaleDistance(void* unit, int distance) {
    assert(unit == live); return distance * 115 / 100;
}
void* __fastcall Reference(void* object, void*) { return object; }
void* __fastcall Resolve(void* reference, void*) {
    assert(Read<unsigned>(reference, 8) == 42);
    Put(reference, 0x0C, 123u); // stock's disposable handle cache
    return live;
}
void* __fastcall Find(void* registry, void*, const char* name) {
    assert(registry == catalog);
    ++lookupCalls;
    return std::strcmp(name, "Example") == 0 ? named : nullptr;
}
int __fastcall Attribute(void* unit, void*, unsigned key, int fallback) {
    assert(unit == live && key == 0x22565041u && fallback == 0);
    return modifier;
}
int __fastcall Interval(void* unit, void*) {
    assert(unit == live);
    ++intervalCalls;
    auto movement = Read<void*>(Read<void*>(unit, 0x54), 0x14);
    return MajestyMovement::NormalInterval(Read<int>(movement, 0x0C)+modifier, MovementQuantum());
}
struct StringValue { void** table; const char* text; };
const char** __fastcall AsString(void* value, void*) {
    return &static_cast<StringValue*>(value)->text;
}
void Run() {
    using namespace MajestyMovement;
    assert(NormalInterval(59,40) == 40 && NormalInterval(60,40) == 80);
    assert(NormalInterval(5,40) == 5 && NormalInterval(0,40) == 1);
    assert(NormalInterval(-50,40) == 1 && NormalInterval(10,0) == kInvalidData);
    assert(NormalInterval(0x7fffffff,40) == kInvalidData);
    assert(Rate(10,40) == 512 && Rate(10,80) == 256 && Rate(6,5) == 2457);
    assert(Rate(0,1) == 0 && Rate(-1,10) == kInvalidData);
    assert(Rate(32768,10) == kInvalidData && Rate(10,0) == kInvalidData);
    assert(InstallMapQueryRuntime(0,MajestyBuildId::SteamBeta2,false,false));

    unsigned char unit[0x94] = {}, dunt[0x18] = {}, unitEngine[0x134] = {};
    unsigned char dmov[0x18] = {}, movementEngine[0x38] = {}, clock[0x24] = {};
    void* currentClock = clock;
    void* currentCatalog = dunt;
    catalog = currentCatalog; live = unit; named = dunt;
    void* unitTable[0x15C/4] = {};
    void* valueTable[24] = {};
    void* movementTable[4] = {};
    unitTable[0x158/4] = reinterpret_cast<void*>(&Interval);
    valueTable[0x5C/4] = reinterpret_cast<void*>(&Reference);
    valueTable[0x28/4] = reinterpret_cast<void*>(&NativeTest::AsInt);
    valueTable[0x30/4] = reinterpret_cast<void*>(&AsString);
    Put(unit,0,static_cast<void*>(unitTable)); Put(unit,0x54,static_cast<void*>(dmov));
    Put(dunt,8,1); Put(dunt,0x14,static_cast<void*>(unitEngine));
    Put(dmov,8,1); Put(dmov,0x14,static_cast<void*>(movementEngine));
    Put(movementEngine,0,static_cast<void*>(movementTable));
    Put(movementEngine,0x0C,50); Put(movementEngine,0x10,10); Put(clock,0x20,40);
    Put(unitEngine,0xD4+7*12,1u);
    Put(unitEngine,0xD4+7*12+8,static_cast<void*>(dmov));

    Profile profile = kBeta;
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&NativeTest::At);
    MovementProfile movement = kMovementBeta;
    movement.resolveUnit = reinterpret_cast<std::uintptr_t>(&Resolve);
    movement.findDescription = reinterpret_cast<std::uintptr_t>(&Find);
    movement.descriptionsGlobal = reinterpret_cast<std::uintptr_t>(&currentCatalog);
    movement.clockGlobal = reinterpret_cast<std::uintptr_t>(&currentClock);
    movement.effectiveInterval = reinterpret_cast<std::uintptr_t>(&Interval);
    movement.packedAttribute = reinterpret_cast<std::uintptr_t>(&Attribute);
    movement.movementVtable = reinterpret_cast<std::uintptr_t>(movementTable);
    g_base = 0; g_profile = &profile; g_movementProfile = &movement;
    NativeTest::Value value{valueTable,0,42,999};
    const auto original = value;
    unsigned char originalUnit[sizeof(unit)]; std::memcpy(originalUnit,unit,sizeof(unit));
    modifier = 40;
    assert(UnitMovementRate(&value,0) == 512 && intervalCalls == 0);
    assert(UnitMovementRate(&value,1) == 256 && intervalCalls == 1);
    g_movementDistance = &ScaleDistance;
    assert(UnitMovementRate(&value,1) == 294);
    assert(UnitMovementRate(&value,0) == 512);
    assert(UnitTypeMovementRate("Example") == 512);
    g_movementDistance = nullptr;
    intervalCalls = 1;
    assert(std::memcmp(&value,&original,sizeof(value)) == 0);
    assert(std::memcmp(unit,originalUnit,sizeof(unit)) == 0);
    assert(UnitMovementRate(&value,2) == kInvalid && UnitMovementRate(nullptr,0) == kInvalid);
    live = nullptr; assert(UnitMovementRate(&value,0) == kInvalid); live = unit;
    unitTable[0x158/4] = nullptr;
    assert(UnitMovementRate(&value,0) == kUnsupported);
    unitTable[0x158/4] = reinterpret_cast<void*>(&Interval);
    for (int subtype : {1,2,3}) {
        Put(dunt,8,subtype);
        assert(UnitTypeMovementRate("Example") == 512);
    }
    assert(UnitTypeMovementRate("Missing") == kInvalid);
    int lookups = lookupCalls;
    assert(UnitTypeMovementRate("") == kInvalid && UnitTypeMovementRate(nullptr) == kInvalid);
    assert(lookups == lookupCalls);
    Put(dunt,8,4); assert(UnitTypeMovementRate("Example") == kUnsupported); Put(dunt,8,1);
    Put(unitEngine,0xD4+7*12,2u);
    assert(UnitTypeMovementRate("Example") == kUnsupported);
    assert(UnitMovementRate(&value,0) == 512); // live attachment, not DUNT slot
    Put(unitEngine,0xD4+7*12,1u);
    currentClock = nullptr;
    assert(UnitTypeMovementRate("Example") == kInvalidData);
    assert(UnitMovementRate(&value,0) == kInvalidData); currentClock = clock;
    Put(dmov,8,2); assert(UnitMovementRate(&value,0) == kUnsupported); Put(dmov,8,1);
    Put(movementEngine,0x10,0); assert(UnitMovementRate(&value,0) == 0);
    Put(movementEngine,0x10,-1); assert(UnitTypeMovementRate("Example") == kInvalidData);
    Put(movementEngine,0x10,10);
    modifier = 0x7fffffff;
    assert(UnitMovementRate(&value,1) == kInvalidData && intervalCalls == 1);
    modifier = 40;

    NativeTest::Value result{valueTable,1,0,0}, mode{valueTable,1,1,0};
    void* objects[] = {&result,&value,&mode};
    void** entries[] = {&objects[0],&objects[1],&objects[2]};
    NativeTest::Args args{nullptr,{},entries,entries+3};
    Movement(&args); assert(result.x == 256);
    objects[2] = &result; result.x = 0;
    Movement(&args); assert(result.x == 512); // aliased integer consumed first
    args.end = args.first+2;
    Movement(&args); assert(result.x == kInvalid);
    StringValue string{valueTable,"Example"}; objects[1] = &string;
    TypeMovement(&args); assert(result.x == 512);
    string.text = "Missing"; TypeMovement(&args); assert(result.x == kInvalid);
    g_profile = nullptr; g_movementProfile = nullptr;
}
}
