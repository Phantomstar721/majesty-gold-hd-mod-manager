#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "../runtime/ListObjectsAcceleration.h"
#include "../runtime/ListObjectsAccelerationProfiles.h"

// Offline x86 fixture for the $ListObjects acceleration
// (docs/listobjects-acceleration.md). Arguments: the default Steam, Steam beta2
// and GOG executables, in that order.
//
// Each executable is laid out at its preferred base in the fixed-address
// fixture section (GogFixtureMemory.cpp). For every build with an audited
// profile row the fixture proves that Install():
//   * refuses, without writing a byte, another build's identity, a moved image,
//     an unresolved string-comparison import, and one changed byte at the start,
//     middle or end of every guarded stock body;
//   * otherwise changes only the four-byte filter operand of the hand-over
//     site, and refuses a second installation.
// It then replaces the stock leaf helpers (unit position and distances, team
// lookup, unit components, agent resolution, attribute lookup, unit attributes,
// GPL value creation and the result push_back) with recording fakes, and runs
// the stock callback's own bytes and the accelerated callback over a matrix of
// synthetic units and $ListObjects search states. The agent reference
// constructor/destructor and the stock property getter run as stock code. For
// every unit both callbacks must return the same value, push the same records
// and make the same sequence of calls that can raise a script error or have a
// side effect (attribute lookups, unit attribute reads, GPL value creation,
// value assignment, push_back).
//
// A missing or deleted agent makes the stock property getter raise a script
// error, which cannot unwind through mapped game frames here. For those units
// the fixture records whether the stock callback reaches its property getter,
// and requires the accelerated callback to hand the unit to the stock callback
// in exactly those cases.

extern "C" unsigned char GogFixtureBytes[0x500000];

namespace {
namespace P = ListObjectsAccelerationProfiles;
namespace F = P::FilterOperand;

constexpr std::uintptr_t kBase = 0x400000;
constexpr std::uint32_t kAgentComponent = 0x4541;  // 'AE'
constexpr int kAttributeA = 0x101;
constexpr int kAttributeB = 0x102;
constexpr int kStockResult = 0x51;

using FilterFn = int(__cdecl*)(void* unit, void* first, void* second);

// ---- failure reporting -----------------------------------------------------

const char* g_build = "";
const char* g_phase = "";
int g_state = -1;
int g_unit = -1;
int g_failures = 0;

void Fail(const char* what, int line) {
    std::fprintf(stderr, "FAILED [%s] %s, state %d, unit %d (line %d): %s\n", g_build, g_phase,
                 g_state, g_unit, line, what);
    if (++g_failures >= 25) std::exit(1);
}
#define CHECK(condition) ((condition) ? static_cast<void>(0) : Fail(#condition, __LINE__))

// ---- memory helpers --------------------------------------------------------

unsigned char* Bytes(std::uintptr_t va) {
    return reinterpret_cast<unsigned char*>(va);
}
template <class T>
std::uintptr_t Address(T* pointer) {
    return reinterpret_cast<std::uintptr_t>(pointer);
}
template <class Function>
std::uintptr_t Code(Function function) {
    return reinterpret_cast<std::uintptr_t>(function);
}
std::uint32_t Word(std::uintptr_t va) {
    std::uint32_t value = 0;
    std::memcpy(&value, Bytes(va), sizeof(value));
    return value;
}
void PutWord(std::uintptr_t va, std::uintptr_t value) {
    const auto word = static_cast<std::uint32_t>(value);
    std::memcpy(Bytes(va), &word, sizeof(word));
}
std::uintptr_t Relative(std::uintptr_t function, std::uint32_t operand) {
    return function + operand + 4 +
           static_cast<std::uintptr_t>(static_cast<std::int32_t>(Word(function + operand)));
}
std::uintptr_t Absolute(std::uintptr_t function, std::uint32_t operand) {
    return Word(function + operand);
}
std::uint32_t Fnv1a(std::uintptr_t start, std::uint32_t size) {
    std::uint32_t hash = 2166136261u;
    for (std::uint32_t i = 0; i < size; ++i) hash = (hash ^ Bytes(start)[i]) * 16777619u;
    return hash;
}

std::vector<char> LoadFile(const char* path) {
    std::ifstream file(path, std::ios::binary);
    return std::vector<char>(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}

// Lays the executable out at its preferred base as the loader would, without
// relocations or import binding. Returns SizeOfImage, or 0 if it cannot.
std::uint32_t Map(const std::vector<char>& file) {
    std::memset(GogFixtureBytes, 0, sizeof(GogFixtureBytes));
    if (file.size() < sizeof(IMAGE_DOS_HEADER)) return 0;
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(file.data());
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 ||
        static_cast<std::size_t>(dos->e_lfanew) + sizeof(IMAGE_NT_HEADERS32) > file.size()) {
        return 0;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(file.data() + dos->e_lfanew);
    const IMAGE_OPTIONAL_HEADER32& optional = nt->OptionalHeader;
    if (nt->Signature != IMAGE_NT_SIGNATURE || optional.ImageBase != kBase ||
        optional.SizeOfImage > sizeof(GogFixtureBytes) || optional.SizeOfHeaders > file.size()) {
        return 0;
    }
    std::memcpy(GogFixtureBytes, file.data(), optional.SizeOfHeaders);
    const IMAGE_SECTION_HEADER* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const std::uint32_t size = section->SizeOfRawData < section->Misc.VirtualSize
                                       ? section->SizeOfRawData
                                       : section->Misc.VirtualSize;
        if (static_cast<std::size_t>(section->PointerToRawData) + size > file.size() ||
            static_cast<std::size_t>(section->VirtualAddress) + size > sizeof(GogFixtureBytes)) {
            return 0;
        }
        std::memcpy(GogFixtureBytes + section->VirtualAddress, file.data() + section->PointerToRawData,
                    size);
    }
    return optional.SizeOfImage;
}

std::vector<unsigned char> Snapshot(std::uint32_t size) {
    return std::vector<unsigned char>(GogFixtureBytes, GogFixtureBytes + size);
}
bool Unchanged(const std::vector<unsigned char>& expected) {
    return std::memcmp(GogFixtureBytes, expected.data(), expected.size()) == 0;
}

struct Diversion {
    std::uintptr_t at;
    unsigned char original[5];
};
void WriteCode(std::uintptr_t at, const unsigned char* bytes) {
    std::memcpy(Bytes(at), bytes, 5);
    FlushInstructionCache(GetCurrentProcess(), Bytes(at), 5);
}
// Replaces the first instruction bytes of a mapped stock function with a JMP.
Diversion Divert(std::uintptr_t at, std::uintptr_t target) {
    Diversion saved{at, {}};
    std::memcpy(saved.original, Bytes(at), sizeof(saved.original));
    unsigned char jump[5] = {0xE9};
    const auto displacement = static_cast<std::uint32_t>(target - at - 5);
    std::memcpy(jump + 1, &displacement, sizeof(displacement));
    WriteCode(at, jump);
    return saved;
}
void Restore(const Diversion& saved) {
    WriteCode(saved.at, saved.original);
}

// ---- Install() log -----------------------------------------------------------

std::vector<std::string> g_lines;
bool g_sawActive = false;
bool g_sawMismatch = false;

void Capture(const char* line) {
    g_lines.emplace_back(line);
    if (std::strstr(line, "accelerated filter active") != nullptr) g_sawActive = true;
    if (std::strstr(line, "MISMATCH") != nullptr || std::strstr(line, "raised exception") != nullptr) {
        g_sawMismatch = true;
    }
}
bool LastLineHas(const char* text) {
    return !g_lines.empty() && g_lines.back().find(text) != std::string::npos;
}
bool TryInstall(std::uintptr_t base, MajestyBuildId build) {
    g_lines.clear();
    return ListObjectsAcceleration::Install(base, build, &Capture);
}
void ExpectRefusal(std::uintptr_t base, MajestyBuildId build, const std::vector<unsigned char>& image,
                   const char* reason) {
    CHECK(!TryInstall(base, build));
    CHECK(Unchanged(image));
    CHECK(LastLineHas(reason));
    CHECK(LastLineHas("stock $ListObjects is unchanged"));
}
const P::Profile* Row(MajestyBuildId build) {
    for (const P::Profile& row : P::kProfiles) {
        if (row.build == build) return &row;
    }
    return nullptr;
}

// ---- synthetic game objects --------------------------------------------------

struct FakeAgent;
struct FakeComponent {
    FakeAgent* agent;
};
struct FakeValue {
    const void* const* vtable;  // +0x18 set from an agent reference, +0x30 text
    const char* text;
    int kind;
    int serial;
};
struct FakeAgent {
    unsigned char opaque[0x38];
    std::uint8_t deleted;  // tested by the stock property getter and attribute lookup
    FakeValue* type;
    FakeValue* check;
};
struct FakeUnit {
    const void* const* vtable;       // virtual +0x1C = owning player, for team tests
    unsigned char components[0x7C];  // the unit's component container (opaque here)
    int player;
    std::uint32_t host;              // nonzero while inside another unit
    int x, y, anchorDistance, pointDistance;  // fixture data: never read by stock code
    FakeComponent* component;
    int attributeA, attributeB;
};
struct FakeManager {
    unsigned char opaque[0x1C];
    void* factory;  // the GPL value factory
};
struct Record {
    int distance;
    void* component;
    void* value;
};
static_assert(offsetof(FakeAgent, deleted) == 0x38, "stock deleted-agent flag");
static_assert(offsetof(FakeUnit, components) == 0x04 && offsetof(FakeUnit, player) == 0x80 &&
                  offsetof(FakeUnit, host) == 0x84,
              "stock unit layout");
static_assert(offsetof(FakeManager, factory) == 0x1C, "stock value factory");
static_assert(sizeof(Record) == 12, "stock result record");

// Calls that can raise a script error or have a side effect, in call order.
struct Event {
    char kind;  // L attribute lookup, U unit attribute, N new value, S value set, P push_back
    std::uintptr_t a, b, c;
    bool operator==(const Event& other) const {
        return kind == other.kind && a == other.a && b == other.b && c == other.c;
    }
};

// The stock .data search state, decoded from the filter exactly as Install() does.
struct Globals {
    std::uintptr_t inside, anchor, pointGiven, point, rangeLimit, playerFilter, teamFilter, teamTable,
        typeKey, typeString, checkKey, checkString, attributeCount, attributeIds, attributeValues,
        results, firstOnly;
};
Globals G{};

std::vector<Event> g_events;
std::vector<const FakeUnit*> g_distances;
int g_helperErrors = 0;

const void* g_unitVtable[8] = {};
const void* g_valueVtable[13] = {};
FakeValue g_noValue{g_valueVtable, "\x7F", 0, -1};
FakeValue g_created[8] = {};
int g_createdCount = 0;
Record g_stored[64] = {};
unsigned char g_factory[4] = {};
FakeManager g_manager{{}, g_factory};
unsigned char g_teamTable[4] = {};
unsigned char g_checkKey[4] = {};
const char* g_checkText = nullptr;  // the stock check-string object starts with its text

// Stock helpers are __thiscall. __fastcall with an unused EDX parameter has the
// same register and stack contract on x86.
void* __fastcall UnitPosition(FakeUnit* unit, void*, int* position) {
    position[0] = unit->x;
    position[1] = unit->y;
    return position;
}
int __fastcall RectDistance(FakeUnit* unit, void*, const int* here, const void* other,
                            const void* point) {
    if (here == nullptr || here[0] != unit->x || here[1] != unit->y || other != nullptr ||
        Address(point) != G.point) {
        ++g_helperErrors;
    }
    g_distances.push_back(unit);
    return unit->pointDistance;
}
int __fastcall AnchorDistance(FakeUnit* anchor, void*, FakeUnit* unit) {
    if (Address(anchor) != Word(G.anchor)) ++g_helperErrors;
    g_distances.push_back(unit);
    return unit->anchorDistance;
}
int __fastcall TeamOf(void* table, void*, int player) {
    if (table != g_teamTable) ++g_helperErrors;
    return player == 3 ? 2 : 1;  // players 1 and 2 are allied; player 3 is not
}
int __fastcall UnitPlayer(FakeUnit* unit, void*) {
    return unit->player;
}
void* __fastcall ComponentFind(unsigned char* components, void*, std::uint32_t key) {
    if (key != kAgentComponent) ++g_helperErrors;
    return reinterpret_cast<FakeUnit*>(components - offsetof(FakeUnit, components))->component;
}
void* __cdecl GplManager() {
    return &g_manager;
}
FakeAgent* __fastcall ResolveAgent(void* manager, void*, FakeComponent* component) {
    if (manager != &g_manager || component == nullptr) {
        ++g_helperErrors;
        return nullptr;
    }
    return component->agent;
}
FakeValue* __fastcall AttributeLookup(FakeAgent* agent, void*, const void* key) {
    g_events.push_back({'L', Address(agent), Address(key), 0});
    if (agent == nullptr || agent->deleted != 0) {  // stock raises a script error here
        ++g_helperErrors;
        return &g_noValue;
    }
    if (Address(key) == G.typeKey) return agent->type;
    if (key == g_checkKey) return agent->check;
    ++g_helperErrors;
    return &g_noValue;
}
int __fastcall UnitAttribute(FakeUnit* unit, void*, int id, int zero) {
    g_events.push_back(
        {'U', Address(unit), static_cast<std::uintptr_t>(id), static_cast<std::uintptr_t>(zero)});
    return id == kAttributeA ? unit->attributeA : id == kAttributeB ? unit->attributeB : -1;
}
FakeValue* __fastcall ValueNew(void* factory, void*, int kind) {
    g_events.push_back({'N', static_cast<std::uintptr_t>(kind), 0, 0});
    if (factory != g_factory || g_createdCount == 8) {
        ++g_helperErrors;
        return &g_noValue;
    }
    FakeValue* value = &g_created[g_createdCount];
    *value = FakeValue{g_valueVtable, "", kind, g_createdCount};
    ++g_createdCount;
    return value;
}
// A stock agent reference is {vtable, value kind 5, 'AE' component, resolved agent}.
void __fastcall ValueSet(FakeValue* value, void*, const std::uint32_t* reference) {
    g_events.push_back({'S', static_cast<std::uintptr_t>(value->serial), reference[2], reference[3]});
    if (reference[1] != 5) ++g_helperErrors;
}
const char* const* __fastcall ValueText(FakeValue* value, void*) {
    return &value->text;
}
void __fastcall PushBack(void* results, void*, const Record* record) {
    const auto* value = static_cast<const FakeValue*>(record->value);
    g_events.push_back({'P', static_cast<std::uint32_t>(record->distance), Address(record->component),
                        static_cast<std::uintptr_t>(value != nullptr ? value->serial : -1)});
    const std::uintptr_t last = Word(G.results + 0x10);
    if (Address(results) != G.results || last >= Address(g_stored + 64)) {
        ++g_helperErrors;
        return;
    }
    // Keep the stock vector's first/last pointers current: the differential
    // verification build counts records through them.
    std::memcpy(Bytes(last), record, sizeof(Record));
    PutWord(G.results + 0x10, last + sizeof(Record));
}

void* const kFirst = reinterpret_cast<void*>(static_cast<std::uintptr_t>(0x1111));
void* const kSecond = reinterpret_cast<void*>(static_cast<std::uintptr_t>(0x2222));
int g_stockCalls = 0;
int g_stockReturn = 0;
const FakeUnit* g_stockUnit = nullptr;
bool g_reachedGetter = false;

int __cdecl FakeStock(void* unit, void* first, void* second) {
    ++g_stockCalls;
    if (unit != g_stockUnit || first != kFirst || second != kSecond) ++g_helperErrors;
    return g_stockReturn;
}
FakeValue* __fastcall ProbeGetProperty(void*, void*, const void*) {
    g_reachedGetter = true;
    return &g_noValue;
}

// ---- units and search states -----------------------------------------------

enum class Agent { None, Live, Missing, Deleted };
struct UnitSpec {
    int player;
    std::uint32_t host;
    int anchorDistance, pointDistance;
    Agent agent;
    const char* type;
    const char* check;
    int attributeA, attributeB;
};
// Unit 0 is the anchor (player 1). Distances from the anchor and from a point
// differ, so a distance taken in the wrong mode changes the outcome.
const UnitSpec kUnits[] = {
    {1, 0, 0, 0, Agent::Live, "Hero", "Warrior", 1, 7},
    {1, 0, 10, 13, Agent::Live, "Hero", "Warrior", 1, 7},
    {2, 0, 40, 38, Agent::Live, "Hero", "warrior", 1, 3},
    {3, 0, 41, 45, Agent::Live, "Monster", "Goblin", 0, 7},
    {3, 0, 500, 2, Agent::Live, "Hero", "Warrior", 1, 7},
    {1, 77, 5, 5, Agent::Live, "Hero", "Warrior", 1, 7},  // inside another unit
    {2, 0, 0, 0, Agent::Live, "Building", "Guild", 1, 7},
    {2, 0, 30, 30, Agent::Live, "hero", "WARRIOR", 1, 7},
    {1, 0, 12, 12, Agent::None, "", "", 1, 7},             // no agent component
    {1, 0, 10, 10, Agent::Missing, "", "", 1, 7},
    {3, 0, 41, 41, Agent::Deleted, "", "", 1, 7},
    {1, 9, 5, 5, Agent::Deleted, "", "", 1, 7},            // inside another unit
    {2, 0, 600, 600, Agent::Missing, "", "", 1, 7},
};
constexpr int kUnitCount = static_cast<int>(sizeof(kUnits) / sizeof(kUnits[0]));
FakeUnit g_units[kUnitCount] = {};
FakeComponent g_components[kUnitCount] = {};
FakeAgent g_agents[kUnitCount] = {};
FakeValue g_types[kUnitCount] = {};
FakeValue g_checks[kUnitCount] = {};

void BuildUnits() {
    g_unitVtable[0x1C / 4] = reinterpret_cast<const void*>(&UnitPlayer);
    g_valueVtable[0x18 / 4] = reinterpret_cast<const void*>(&ValueSet);
    g_valueVtable[0x30 / 4] = reinterpret_cast<const void*>(&ValueText);
    for (int index = 0; index < kUnitCount; ++index) {
        const UnitSpec& spec = kUnits[index];
        FakeUnit& unit = g_units[index];
        unit.vtable = g_unitVtable;
        unit.player = spec.player;
        unit.host = spec.host;
        unit.x = 100 + index;
        unit.y = 200 + index;
        unit.anchorDistance = spec.anchorDistance;
        unit.pointDistance = spec.pointDistance;
        unit.attributeA = spec.attributeA;
        unit.attributeB = spec.attributeB;
        g_types[index] = FakeValue{g_valueVtable, spec.type, 0, -1};
        g_checks[index] = FakeValue{g_valueVtable, spec.check, 0, -1};
        g_agents[index].type = &g_types[index];
        g_agents[index].check = &g_checks[index];
        g_agents[index].deleted = static_cast<std::uint8_t>(spec.agent == Agent::Deleted);
        g_components[index].agent = spec.agent == Agent::Missing ? nullptr : &g_agents[index];
        unit.component = spec.agent == Agent::None ? nullptr : &g_components[index];
    }
}
bool Dead(int index) {
    return kUnits[index].agent == Agent::Missing || kUnits[index].agent == Agent::Deleted;
}

struct Check {
    bool key;
    const char* text;
};
struct State {
    bool inside, point, firstOnly;
    int limit, player, team, pairs;
    const char* type;
    Check check;
};

void Apply(const State& state) {
    *Bytes(G.inside) = static_cast<unsigned char>(state.inside);
    *Bytes(G.pointGiven) = static_cast<unsigned char>(state.point);
    *Bytes(G.firstOnly) = static_cast<unsigned char>(state.firstOnly);
    PutWord(G.anchor, Address(&g_units[0]));
    PutWord(G.rangeLimit, static_cast<std::uint32_t>(state.limit));
    PutWord(G.playerFilter, static_cast<std::uint32_t>(state.player));
    PutWord(G.teamFilter, static_cast<std::uint32_t>(state.team));
    PutWord(G.teamTable, Address(g_teamTable));
    PutWord(G.typeString, Address(state.type));
    g_checkText = state.check.text;
    PutWord(G.checkKey, state.check.key ? Address(g_checkKey) : 0);
    PutWord(G.checkString, state.check.text != nullptr ? Address(&g_checkText) : 0);
    // Stock attribute pairs are 1-based: id i at ids + 4i, value i at count + 4i.
    PutWord(G.attributeCount, static_cast<std::uint32_t>(state.pairs));
    PutWord(G.attributeIds + 4, kAttributeA);
    PutWord(G.attributeValues + 4, 1);
    PutWord(G.attributeIds + 8, kAttributeB);
    PutWord(G.attributeValues + 8, 7);
}

struct Run {
    int result;
    std::vector<Event> events;
    std::vector<const FakeUnit*> distances;
};
Run Execute(FilterFn filter, FakeUnit* unit) {
    g_events.clear();
    g_distances.clear();
    g_createdCount = 0;
    PutWord(G.results + 0x0C, Address(g_stored));
    PutWord(G.results + 0x10, Address(g_stored));
    const int result = filter(unit, kFirst, kSecond);
    return Run{result, g_events, g_distances};
}
bool Pushed(const std::vector<Event>& events) {
    for (const Event& event : events) {
        if (event.kind == 'P') return true;
    }
    return false;
}
// Value creation, assignment and push_back only.
std::vector<Event> Effects(const std::vector<Event>& events) {
    std::vector<Event> effects;
    for (const Event& event : events) {
        if (event.kind == 'N' || event.kind == 'S' || event.kind == 'P') effects.push_back(event);
    }
    return effects;
}

struct Tally {
    int live, matches, pointMatches, unlimitedMatches, limitedMatches, stops, lookups, reads;
    int dead, delegated, rejectedFirst;
};

void CompareLive(FilterFn stock, FilterFn accelerated, FakeUnit* unit, const State& state,
                 Tally& tally) {
    const int errors = g_helperErrors;
    const Run expected = Execute(stock, unit);
    const Run actual = Execute(accelerated, unit);
    CHECK(g_helperErrors == errors);
    CHECK(actual.result == expected.result);
    CHECK(Effects(actual.events) == Effects(expected.events));
#if !defined(MAJESTY_LISTOBJECTS_DIFFERENTIAL)
    // The verification build evaluates its own decision and then runs the stock
    // callback, so only the release callback has a single call sequence.
    CHECK(actual.events == expected.events);
    const bool matched = Pushed(actual.events);
    CHECK(actual.distances.size() <= 1);
    if (!actual.distances.empty()) CHECK(!expected.distances.empty());
    if (state.limit < 0) {
        CHECK(actual.distances.empty() != matched);  // unlimited: distance only for a match
    } else if (matched) {
        CHECK(actual.distances.size() == 1);
    }
#endif
    ++tally.live;
    if (Pushed(expected.events)) {
        ++tally.matches;
        if (state.point) ++tally.pointMatches;
        if (state.limit < 0) {
            ++tally.unlimitedMatches;
        } else {
            ++tally.limitedMatches;
        }
        if (expected.result == 1) ++tally.stops;
    }
    for (const Event& event : expected.events) {
        if (event.kind == 'L') ++tally.lookups;
        if (event.kind == 'U') ++tally.reads;
    }
}

void CompareDead(FilterFn stock, FilterFn accelerated, std::uintptr_t stockEntry,
                 std::uintptr_t getProperty, Tally& tally) {
    bool reached[kUnitCount] = {};
    g_phase = "stock property-getter probe";
    const Diversion getter = Divert(getProperty, Code(&ProbeGetProperty));
    for (int index = 0; index < kUnitCount; ++index) {
        if (!Dead(index)) continue;
        g_unit = index;
        g_reachedGetter = false;
        Execute(stock, &g_units[index]);
        reached[index] = g_reachedGetter;
    }
    Restore(getter);

    g_phase = "missing or deleted agent";
    const Diversion entry = Divert(stockEntry, Code(&FakeStock));
    for (int index = 0; index < kUnitCount; ++index) {
        if (!Dead(index)) continue;
        g_unit = index;
        g_stockCalls = 0;
        g_stockUnit = &g_units[index];
        g_stockReturn = reached[index] ? kStockResult : 0;
        const int errors = g_helperErrors;
        const Run actual = Execute(accelerated, &g_units[index]);
        CHECK(g_helperErrors == errors);
        CHECK(actual.events.empty());
        CHECK(actual.result == g_stockReturn);
#if defined(MAJESTY_LISTOBJECTS_DIFFERENTIAL)
        CHECK(g_stockCalls == 1);
#else
        CHECK(g_stockCalls == (reached[index] ? 1 : 0));
#endif
        ++tally.dead;
        if (reached[index]) {
            ++tally.delegated;
        } else {
            ++tally.rejectedFirst;
        }
    }
    Restore(entry);
}

void RunMatrix(FilterFn stock, FilterFn accelerated, std::uintptr_t stockEntry,
               std::uintptr_t getProperty, Tally& tally) {
    const int limits[] = {-1, 0, 40, 1000};
    const int sides[] = {0, 1, -1};  // player/team filter: off, same, different
    const char* const types[] = {nullptr, "Hero", "HERO", "Monster"};
    const Check checks[] = {{false, nullptr}, {true, "Warrior"}, {true, nullptr}, {false, "Warrior"}};
    int index = 0;
    for (const bool inside : {false, true})
    for (const bool point : {false, true})
    for (const int limit : limits)
    for (const int player : sides)
    for (const int team : sides)
    for (const char* type : types)
    for (const Check& check : checks)
    for (const int pairs : {0, 1, 2})
    for (const bool firstOnly : {false, true}) {
        const State state{inside, point, firstOnly, limit, player, team, pairs, type, check};
        g_state = index++;
        Apply(state);
        g_phase = "live agents";
        for (int unit = 0; unit < kUnitCount; ++unit) {
            if (Dead(unit)) continue;
            g_unit = unit;
            CompareLive(stock, accelerated, &g_units[unit], state, tally);
        }
        CompareDead(stock, accelerated, stockEntry, getProperty, tally);
    }
    g_state = g_unit = -1;
}

bool BodyMatches(std::uintptr_t start, std::uint32_t size, std::uint32_t hash, std::uint32_t imageSize) {
    return start >= kBase && start + size <= kBase + imageSize && Fnv1a(start, size) == hash;
}

void CheckBuild(MajestyBuildId build, const P::Profile& profile, std::uint32_t imageSize) {
    const std::uintptr_t listObjects = kBase + profile.listObjects;
    const std::uintptr_t filter = kBase + profile.filter;
    g_phase = "fixture identity";
    if (!BodyMatches(listObjects, P::kListObjectsSize, profile.listObjectsHash, imageSize) ||
        !BodyMatches(filter, P::kFilterSize, profile.filterHash, imageSize)) {
        Fail("the executable does not match its profile row (wrong fixture argument?)", __LINE__);
        return;
    }
    const std::uintptr_t push = listObjects + P::kPushSite;
    const std::uintptr_t getProperty = Relative(filter, F::GetProperty);
    const std::uintptr_t pushBack = Relative(filter, F::PushBack);
    const std::uintptr_t resolveAgent = Relative(getProperty, P::GetPropertyOperand::ResolveAgent);
    const std::uintptr_t attributeLookup =
        Relative(getProperty, P::GetPropertyOperand::AttributeLookup);
    const std::uintptr_t importSlot = Absolute(filter, F::StricmpImport);
    // The loader binds this import in the game process; the mapped file holds
    // the unbound thunk.
    PutWord(importSlot, Code(&_stricmp));
    std::vector<unsigned char> image = Snapshot(imageSize);

    g_phase = "refusals";
    for (const MajestyBuildId other :
         {MajestyBuildId::SteamPublic, MajestyBuildId::SteamBeta2, MajestyBuildId::Gog}) {
        if (other == build) continue;
        ExpectRefusal(kBase, other, image,
                      Row(other) != nullptr ? "does not match the audited bytes" : "no audited profile");
    }
    ExpectRefusal(kBase + 0x10000, build, image, "unexpected image layout");
    PutWord(importSlot, 0);
    std::memset(&image[importSlot - kBase], 0, 4);
    ExpectRefusal(kBase, build, image, "import is unresolved");
    PutWord(importSlot, Code(&_stricmp));
    std::memcpy(&image[importSlot - kBase], Bytes(importSlot), 4);

    struct Body {
        std::uintptr_t start;
        std::uint32_t size;
        const char* reason;
    };
    const Body bodies[] = {
        {listObjects, P::kListObjectsSize, "does not match the audited bytes"},
        {filter, P::kFilterSize, "does not match the audited bytes"},
        {getProperty, P::kGetPropertySize, "property lookup or result push_back"},
        {pushBack, P::kPushBackSize, "property lookup or result push_back"},
        {resolveAgent, P::kResolveAgentSize, "agent resolver or attribute lookup"},
        {attributeLookup, P::kAttributeLookupSize, "agent resolver or attribute lookup"},
    };
    g_phase = "changed guarded byte";
    for (const Body& body : bodies) {
        for (const std::uint32_t at : {0u, body.size / 2, body.size - 1}) {
            unsigned char& live = *Bytes(body.start + at);
            unsigned char& kept = image[body.start + at - kBase];
            live = static_cast<unsigned char>(live ^ 0x5A);
            kept = live;
            ExpectRefusal(kBase, build, image, body.reason);
            live = static_cast<unsigned char>(live ^ 0x5A);
            kept = live;
        }
    }

    g_phase = "install";
    CHECK(TryInstall(kBase, build));
#if defined(MAJESTY_LISTOBJECTS_DIFFERENTIAL)
    CHECK(LastLineHas("installed in DIFFERENTIAL verification mode"));
#else
    CHECK(LastLineHas("installed: exact per-unit filter behind stock $ListObjects"));
#endif
    for (std::uint32_t offset = 0; offset < imageSize; ++offset) {
        if (GogFixtureBytes[offset] != image[offset]) {
            CHECK(offset >= push + 1 - kBase && offset < push + 5 - kBase);
        }
    }
    const std::uintptr_t callback = Word(push + 1);
    CHECK(callback != filter);
    CHECK(callback < kBase || callback >= kBase + sizeof(GogFixtureBytes));
    g_phase = "second install";
    ExpectRefusal(kBase, build, Snapshot(imageSize), "does not match the audited bytes");

    g_phase = "bind fakes";
    G = Globals{Absolute(filter, F::Inside), Absolute(filter, F::Anchor),
                Absolute(filter, F::PointGiven), Absolute(filter, F::Point),
                Absolute(filter, F::RangeLimit), Absolute(filter, F::PlayerFilter),
                Absolute(filter, F::TeamFilter), Absolute(filter, F::TeamTable),
                Absolute(filter, F::TypeKey), Absolute(filter, F::TypeString),
                Absolute(filter, F::CheckKey), Absolute(filter, F::CheckString),
                Absolute(filter, F::AttributeCount), Absolute(filter, F::AttributeIds),
                Absolute(filter, F::AttributeValues), Absolute(filter, F::Results),
                Absolute(filter, F::FirstOnly)};
    // The leaves stay diverted until the next executable is mapped.
    Divert(Relative(filter, F::UnitPosition), Code(&UnitPosition));
    Divert(Relative(filter, F::RectDistance), Code(&RectDistance));
    Divert(Relative(filter, F::AnchorDistance), Code(&AnchorDistance));
    Divert(Relative(filter, F::TeamOf), Code(&TeamOf));
    Divert(Relative(filter, F::ComponentFind), Code(&ComponentFind));
    Divert(Relative(filter, F::GplManager), Code(&GplManager));
    Divert(Relative(filter, F::UnitAttribute), Code(&UnitAttribute));
    Divert(Relative(filter, F::ValueNew), Code(&ValueNew));
    Divert(resolveAgent, Code(&ResolveAgent));
    Divert(attributeLookup, Code(&AttributeLookup));
    Divert(pushBack, Code(&PushBack));

    Tally tally{};
    RunMatrix(reinterpret_cast<FilterFn>(filter), reinterpret_cast<FilterFn>(callback), filter,
              getProperty, tally);
    g_phase = "coverage";
    CHECK(tally.matches > 0);
    CHECK(tally.pointMatches > 0);
    CHECK(tally.unlimitedMatches > 0);
    CHECK(tally.limitedMatches > 0);
    CHECK(tally.stops > 0);
    CHECK(tally.lookups > 0);
    CHECK(tally.reads > 0);
    CHECK(tally.delegated > 0);
    CHECK(tally.rejectedFirst > 0);
    std::printf("%s: %d live-agent unit comparisons (%d matches, %d first-match stops), "
                "%d missing/deleted-agent checks (%d handed to the stock callback).\n",
                g_build, tally.live, tally.matches, tally.stops, tally.dead, tally.delegated);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 4) {
        std::fprintf(stderr,
                     "usage: ListObjectsAccelerationTests <default Steam exe> <Steam beta2 exe> <GOG exe>\n");
        return 2;
    }
    DWORD previous = 0;
    if (Address(GogFixtureBytes) != kBase ||
        !VirtualProtect(GogFixtureBytes, sizeof(GogFixtureBytes), PAGE_EXECUTE_READWRITE, &previous)) {
        std::fprintf(stderr, "the fixture section is not at 0x400000\n");
        return 2;
    }
    BuildUnits();
    const MajestyBuildId builds[] = {MajestyBuildId::SteamPublic, MajestyBuildId::SteamBeta2,
                                     MajestyBuildId::Gog};
    const char* const names[] = {"default Steam", "Steam beta2", "GOG"};
    for (int index = 0; index < 3; ++index) {
        g_build = names[index];
        g_phase = "map";
        const std::uint32_t size = Map(LoadFile(argv[index + 1]));
        const P::Profile* row = Row(builds[index]);
        if (row == nullptr) {
            // Without an audited row Install() must refuse before reading anything.
            g_phase = "unaudited build";
            ExpectRefusal(kBase, builds[index], Snapshot(size != 0 ? size : sizeof(GogFixtureBytes)),
                          "no audited profile");
            std::printf("%s: no audited profile; Install() keeps the stock callback.\n", g_build);
            continue;
        }
        if (size == 0) {
            Fail("cannot map the executable", __LINE__);
            continue;
        }
        CheckBuild(builds[index], *row, size);
    }
    g_build = "all builds";
    g_phase = "log";
    CHECK(g_sawActive);
    CHECK(!g_sawMismatch);
    if (g_failures != 0) return 1;
    std::printf("ListObjects acceleration fixture passed.\n");
    return 0;
}
