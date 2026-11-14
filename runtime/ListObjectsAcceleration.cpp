#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>

#include "ListObjectsAcceleration.h"
#include "ListObjectsAccelerationProfiles.h"

// Stock $ListObjects (docs/listobjects-acceleration.md) parses its arguments
// into .data search state, then hands one per-unit callback to the ForEach of
// each candidate collection, sorts the collected {distance, agent component,
// GPL value} records and writes the GPL list. Only that callback is replaced.
//
// The stock callback tests, in order: indoor units, the anchor itself, the
// footprint distance (computed for every unit, even for an unlimited range),
// player and team filters, the agent component, the GPL type (through an agent
// reference that resolves the same agent twice), the title/subtype (resolving
// it a third time) and attribute pairs. All of those tests are pure lookups,
// so this callback evaluates the same conjunction in a cheaper order:
//   * player filter before the distance (two integer reads);
//   * the distance only when the range filters (limit >= 0, in stock order,
//     before any type lookup) or for a match (its sort key);
//   * the agent resolved once; type and title read through the same stock
//     attribute lookup the stock property getter calls;
//   * the agent component found once and reused for the result record.
// Every helper that can raise a script error is called for exactly the units
// for which stock calls it. A missing or deleted agent - where the stock
// property getter raises its error - is delegated to the stock callback, so
// that error is stock's own. Matches push the identical record through the
// stock push_back after building the GPL value with the stock calls.
namespace ListObjectsAcceleration {
namespace {
namespace P = ListObjectsAccelerationProfiles;

using FilterFn = int(__cdecl*)(void* unit, void* first, void* second);
using ComponentFindFn = void*(__thiscall*)(void* components, std::uint32_t key);
using AgentRefCtorFn = void*(__thiscall*)(void* reference, void* component);
using AgentRefDtorFn = void(__thiscall*)(void* reference);
using GplManagerFn = void*(__cdecl*)();
using ResolveAgentFn = void*(__thiscall*)(void* manager, void* component);
using AttributeLookupFn = void*(__thiscall*)(void* agent, const void* key);
using ValueNewFn = void*(__thiscall*)(void* factory, int kind);
using PushBackFn = void(__thiscall*)(void* results, const void* record);
using AnchorDistanceFn = int(__thiscall*)(void* anchor, void* unit);
using UnitPositionFn = void*(__thiscall*)(void* unit, void* position);
using RectDistanceFn = int(__thiscall*)(void* unit, void* position, void* other,
                                        const void* otherPosition);
using TeamOfFn = int(__thiscall*)(void* table, int player);
using UnitAttributeFn = int(__thiscall*)(void* unit, int id, int zero);
using StricmpFn = int(__cdecl*)(const char*, const char*);
using TextFn = const char* const*(__thiscall*)(void* value);
using PlayerFn = int(__thiscall*)(void* unit);
using SetFromReferenceFn = void(__thiscall*)(void* value, void* reference);

constexpr std::uint32_t kAgentComponent = 0x4541;  // 'AE'
constexpr int kAgentValueKind = 5;

struct Record {
    int distance;
    void* component;
    void* value;
};
static_assert(sizeof(Record) == 12, "stock result records are 12 bytes");

struct Bound {
    FilterFn stockFilter;
    ComponentFindFn componentFind;
    AgentRefCtorFn agentRefCtor;
    AgentRefDtorFn agentRefDtor;
    GplManagerFn gplManager;
    ResolveAgentFn resolveAgent;
    AttributeLookupFn attributeLookup;
    ValueNewFn valueNew;
    PushBackFn pushBack;
    AnchorDistanceFn anchorDistance;
    UnitPositionFn unitPosition;
    RectDistanceFn rectDistance;
    TeamOfFn teamOf;
    UnitAttributeFn unitAttribute;
    StricmpFn stricmpFn;
    const volatile std::uint8_t* inside;
    void* const volatile* anchor;
    const volatile std::uint8_t* pointGiven;
    const void* point;
    const volatile int* rangeLimit;
    const volatile int* playerFilter;
    const volatile int* teamFilter;
    void* const volatile* teamTable;
    const void* typeKey;
    const char* const volatile* typeString;
    void* const volatile* checkKey;
    void* const volatile* checkString;
    const volatile int* attributeCount;
    const volatile int* attributeIds;
    const volatile int* attributeValues;
    const volatile std::uint8_t* firstOnly;
    void* results;
};
Bound g{};
void (*g_log)(const char*) = nullptr;
std::uint64_t g_units = 0;

template <class T>
T At(const void* base, std::uint32_t offset) {
    T value;
    std::memcpy(&value, static_cast<const unsigned char*>(base) + offset, sizeof(T));
    return value;
}
template <class F>
F Virtual(void* object, std::uint32_t offset) {
    return At<F>(At<const void*>(object, 0), offset);
}

void Log(const char* message) {
    if (g_log != nullptr) g_log(message);
}

int Distance(void* unit) {
    if (*g.pointGiven != 0) {
        alignas(4) unsigned char position[8]{};
        void* here = g.unitPosition(unit, position);
        return g.rectDistance(unit, here, nullptr, g.point);
    }
    return g.anchorDistance(*g.anchor, unit);
}

bool TeamRejects(void* unit, void* anchor) {
    const int teamFilter = *g.teamFilter;
    if (teamFilter == 0) return false;
    const int anchorTeam = g.teamOf(*g.teamTable, At<int>(anchor, 0x80));
    const int unitPlayer = Virtual<PlayerFn>(unit, 0x1C)(unit);
    const int unitTeam = g.teamOf(*g.teamTable, unitPlayer);
    return teamFilter > 0 ? anchorTeam != unitTeam : anchorTeam == unitTeam;
}

bool TextDiffers(void* value, const char* wanted) {
    const char* const* text = Virtual<TextFn>(value, 0x30)(value);
    return g.stricmpFn(*text, wanted) != 0;
}

enum class Outcome { Reject, Match, Stock };
struct Decision {
    Outcome outcome;
    int distance;
    void* component;
};

Decision Evaluate(void* unit) {
    Decision decision{Outcome::Reject, 0, nullptr};
    if (At<std::uint32_t>(unit, 0x84) != 0 && *g.inside == 0) return decision;
    void* const anchor = *g.anchor;
    if (unit == anchor) return decision;
    const int playerFilter = *g.playerFilter;
    if (playerFilter != 0) {
        const bool samePlayer = At<int>(anchor, 0x80) == At<int>(unit, 0x80);
        if (playerFilter > 0 ? !samePlayer : samePlayer) return decision;
    }
    const int limit = *g.rangeLimit;
    bool haveDistance = false;
    if (limit >= 0) {
        decision.distance = Distance(unit);
        haveDistance = true;
        if (decision.distance > limit) return decision;
    }
    if (TeamRejects(unit, anchor)) return decision;
    void* const component =
        g.componentFind(static_cast<unsigned char*>(unit) + 4, kAgentComponent);
    if (component == nullptr) return decision;
    void* const agent = g.resolveAgent(g.gplManager(), component);
    if (agent == nullptr || At<std::uint8_t>(agent, 0x38) != 0) {
        decision.outcome = Outcome::Stock;
        return decision;
    }
    void* const typeValue = g.attributeLookup(agent, g.typeKey);
    const char* const typeString = *g.typeString;
    if (typeString != nullptr && TextDiffers(typeValue, typeString)) return decision;
    void* const checkKey = *g.checkKey;
    void* const checkString = *g.checkString;
    if (checkKey != nullptr && checkString != nullptr) {
        void* const value = g.attributeLookup(agent, checkKey);
        if (TextDiffers(value, At<const char*>(checkString, 0))) return decision;
    }
    for (int index = *g.attributeCount; index != 0; --index) {
        if (g.unitAttribute(unit, g.attributeIds[index], 0) != g.attributeValues[index]) {
            return decision;
        }
    }
    if (!haveDistance) decision.distance = Distance(unit);
    decision.outcome = Outcome::Match;
    decision.component = component;
    return decision;
}

void NoteActive() {
    if (++g_units == 4096) Log("ListObjects acceleration: accelerated filter active.");
}

#if !defined(MAJESTY_LISTOBJECTS_DIFFERENTIAL)
// Match the stock scoped temporary: assignment can throw a GPL error, and
// the successfully constructed reference must be destroyed during unwinding.
class AgentReference {
public:
    explicit AgentReference(void* component) { g.agentRefCtor(storage_, component); }
    ~AgentReference() { g.agentRefDtor(storage_); }
    void* data() { return storage_; }
    AgentReference(const AgentReference&) = delete;
    AgentReference& operator=(const AgentReference&) = delete;
private:
    alignas(4) unsigned char storage_[16]{};
};
// The stock match tail: a new agent GPL value set from a stock agent reference,
// then the {distance, component, value} record through the stock push_back.
int Emit(const Decision& decision) {
    void* const factory = At<void*>(g.gplManager(), 0x1C);
    void* const value = g.valueNew(factory, kAgentValueKind);
    {
        AgentReference reference(decision.component);
        Virtual<SetFromReferenceFn>(value, 0x18)(value, reference.data());
    }
    const Record record{decision.distance, decision.component, value};
    g.pushBack(g.results, &record);
    return *g.firstOnly != 0 ? 1 : 0;
}

int __cdecl AcceleratedFilter(void* unit, void* first, void* second) {
    NoteActive();
    const Decision decision = Evaluate(unit);
    if (decision.outcome == Outcome::Reject) return 0;
    if (decision.outcome == Outcome::Stock) return g.stockFilter(unit, first, second);
    return Emit(decision);
}
#else
// Verification build: our decision is evaluated without side effects, the
// stock callback then produces the real result, and the two are compared on
// every unit. Exceptions are reported from the SEH filter and keep their
// normal stock propagation.
std::uint64_t g_matches = 0, g_delegated = 0, g_mismatches = 0;

int ReportException(const char* who, void* unit, DWORD code) {
    char line[256];
    std::snprintf(line, sizeof(line),
        "ListObjects differential: %s callback raised exception %08lX for unit %p (anchor %p).",
        who, static_cast<unsigned long>(code), unit, *g.anchor);
    Log(line);
    return EXCEPTION_CONTINUE_SEARCH;
}
Decision EvaluateObserved(void* unit) {
    __try {
        return Evaluate(unit);
    } __except (ReportException("accelerated", unit, GetExceptionCode())) {
        return Decision{Outcome::Reject, 0, nullptr};
    }
}
int StockObserved(void* unit, void* first, void* second) {
    __try {
        return g.stockFilter(unit, first, second);
    } __except (ReportException("stock", unit, GetExceptionCode())) {
        return 0;
    }
}
std::uint32_t ResultCount() {
    const auto first = At<std::uintptr_t>(g.results, 0x0C);
    const auto last = At<std::uintptr_t>(g.results, 0x10);
    return static_cast<std::uint32_t>((last - first) / sizeof(Record));
}
Record LastRecord() {
    const auto last = At<std::uintptr_t>(g.results, 0x10);
    return At<Record>(reinterpret_cast<const void*>(last - sizeof(Record)), 0);
}
void Summary() {
    char line[256];
    std::snprintf(line, sizeof(line),
        "ListObjects differential: units=%llu matches=%llu delegated=%llu mismatches=%llu.",
        g_units, g_matches, g_delegated, g_mismatches);
    Log(line);
}
int __cdecl AcceleratedFilter(void* unit, void* first, void* second) {
    NoteActive();
    const Decision ours = EvaluateObserved(unit);
    const std::uint32_t before = ResultCount();
    const int stock = StockObserved(unit, first, second);
    const std::uint32_t added = ResultCount() - before;
    if (added == 1) ++g_matches;
    if (ours.outcome == Outcome::Stock) {
        ++g_delegated;
    } else {
        const bool oursMatched = ours.outcome == Outcome::Match;
        bool same = added == (oursMatched ? 1u : 0u);
        Record record{};
        if (same && oursMatched) {
            record = LastRecord();
            same = record.distance == ours.distance && record.component == ours.component;
        }
        same = same && stock == (oursMatched && *g.firstOnly != 0 ? 1 : 0);
        if (!same && ++g_mismatches <= 64) {
            char line[512];
            const char* type = *g.typeString;
            std::snprintf(line, sizeof(line),
                "ListObjects differential MISMATCH: unit=%p anchor=%p type=%.40s limit=%d player=%d "
                "team=%d attrs=%d first=%u ours=%d/%d/%p stock=%u/%d record=%d/%p",
                unit, *g.anchor, type ? type : "(null)", *g.rangeLimit, *g.playerFilter,
                *g.teamFilter, *g.attributeCount, static_cast<unsigned>(*g.firstOnly),
                static_cast<int>(ours.outcome), ours.distance, ours.component, added, stock,
                record.distance, record.component);
            Log(line);
        }
    }
    if ((g_units & 0xFFFFF) == 0 || g_units == 4096) Summary();
    return stock;
}
#endif

std::uint32_t Fnv1a(std::uintptr_t address, std::uint32_t size) {
    const auto* bytes = reinterpret_cast<const unsigned char*>(address);
    std::uint32_t hash = 2166136261u;
    for (std::uint32_t i = 0; i < size; ++i) hash = (hash ^ bytes[i]) * 16777619u;
    return hash;
}

struct ImageRange {
    std::uintptr_t textStart, textEnd, imageEnd;
};
bool ReadImageRange(std::uintptr_t base, ImageRange* range) {
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return false;
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return false;
    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++section) {
        if (std::memcmp(section->Name, ".text", 6) == 0) {
            range->textStart = base + section->VirtualAddress;
            range->textEnd = range->textStart + section->Misc.VirtualSize;
            range->imageEnd = base + nt->OptionalHeader.SizeOfImage;
            return true;
        }
    }
    return false;
}

bool InCode(const ImageRange& range, std::uintptr_t address, std::uint32_t size) {
    return address >= range.textStart && address + size <= range.textEnd && address + size > address;
}
bool InImage(std::uintptr_t base, const ImageRange& range, std::uintptr_t address) {
    return address >= base && address < range.imageEnd;
}

std::uintptr_t Relative(std::uintptr_t function, std::uint32_t operand) {
    return function + operand + 4 + static_cast<std::uintptr_t>(At<std::int32_t>(
        reinterpret_cast<const void*>(function), operand));
}
std::uintptr_t Absolute(std::uintptr_t function, std::uint32_t operand) {
    return At<std::uint32_t>(reinterpret_cast<const void*>(function), operand);
}

bool Refuse(const char* reason) {
    char line[256];
    std::snprintf(line, sizeof(line),
        "ListObjects acceleration not installed (%s); stock $ListObjects is unchanged.", reason);
    Log(line);
    return false;
}

}  // namespace

bool Install(std::uintptr_t imageBase, MajestyBuildId build, void (*log)(const char*)) {
    g_log = log;
    const P::Profile* profile = nullptr;
    for (const auto& row : P::kProfiles) {
        if (row.build == build) profile = &row;
    }
    if (profile == nullptr) return Refuse("no audited profile for this executable");
    ImageRange range{};
    if (imageBase != 0x400000 || !ReadImageRange(imageBase, &range)) {
        return Refuse("unexpected image layout");
    }
    const std::uintptr_t listObjects = imageBase + profile->listObjects;
    const std::uintptr_t filter = imageBase + profile->filter;
    if (!InCode(range, listObjects, P::kListObjectsSize) || !InCode(range, filter, P::kFilterSize) ||
        Fnv1a(listObjects, P::kListObjectsSize) != profile->listObjectsHash ||
        Fnv1a(filter, P::kFilterSize) != profile->filterHash) {
        return Refuse("stock $ListObjects or its filter does not match the audited bytes");
    }
    const std::uintptr_t push = listObjects + P::kPushSite;
    const unsigned char pushPrefix[] = {0x6A, 0x00, 0x6A, 0x00, 0x68};
    const unsigned char callEax[] = {0xFF, 0xD0};
    if (std::memcmp(reinterpret_cast<const void*>(push - 4), pushPrefix, sizeof(pushPrefix)) != 0 ||
        Absolute(push, 1) != filter ||
        std::memcmp(reinterpret_cast<const void*>(push + 5), callEax, sizeof(callEax)) != 0) {
        return Refuse("the filter hand-over site does not match");
    }

    namespace F = P::FilterOperand;
    const std::uintptr_t getProperty = Relative(filter, F::GetProperty);
    const std::uintptr_t pushBack = Relative(filter, F::PushBack);
    if (!InCode(range, getProperty, P::kGetPropertySize) || !InCode(range, pushBack, P::kPushBackSize) ||
        Fnv1a(getProperty, P::kGetPropertySize) != profile->getPropertyHash ||
        Fnv1a(pushBack, P::kPushBackSize) != profile->pushBackHash ||
        Relative(getProperty, P::GetPropertyOperand::GplManager) != Relative(filter, F::GplManager)) {
        return Refuse("the stock property lookup or result push_back does not match");
    }
    const std::uintptr_t resolveAgent = Relative(getProperty, P::GetPropertyOperand::ResolveAgent);
    const std::uintptr_t attributeLookup =
        Relative(getProperty, P::GetPropertyOperand::AttributeLookup);
    if (!InCode(range, resolveAgent, P::kResolveAgentSize) ||
        !InCode(range, attributeLookup, P::kAttributeLookupSize) ||
        Fnv1a(resolveAgent, P::kResolveAgentSize) != profile->resolveAgentHash ||
        Fnv1a(attributeLookup, P::kAttributeLookupSize) != profile->attributeLookupHash) {
        return Refuse("the stock agent resolver or attribute lookup does not match");
    }

    const std::uint32_t calls[] = {F::UnitPosition, F::RectDistance, F::AnchorDistance, F::TeamOf,
        F::ComponentFind, F::AgentRefCtor, F::UnitAttribute, F::GplManager, F::ValueNew,
        F::AgentRefDtor};
    for (const std::uint32_t operand : calls) {
        if (!InCode(range, Relative(filter, operand), 1)) return Refuse("a decoded helper is outside the code");
    }
    const std::uint32_t data[] = {F::Inside, F::Anchor, F::PointGiven, F::Point, F::RangeLimit,
        F::PlayerFilter, F::TeamFilter, F::TeamTable, F::TypeKey, F::TypeString, F::StricmpImport,
        F::CheckKey, F::CheckString, F::AttributeCount, F::AttributeIds, F::AttributeValues,
        F::Results, F::FirstOnly};
    for (const std::uint32_t operand : data) {
        if (!InImage(imageBase, range, Absolute(filter, operand))) {
            return Refuse("a decoded global is outside the image");
        }
    }
    const auto stricmpFn = At<StricmpFn>(reinterpret_cast<const void*>(Absolute(filter, F::StricmpImport)), 0);
    if (stricmpFn == nullptr) return Refuse("the stock string comparison import is unresolved");

    g.stockFilter = reinterpret_cast<FilterFn>(filter);
    g.componentFind = reinterpret_cast<ComponentFindFn>(Relative(filter, F::ComponentFind));
    g.agentRefCtor = reinterpret_cast<AgentRefCtorFn>(Relative(filter, F::AgentRefCtor));
    g.agentRefDtor = reinterpret_cast<AgentRefDtorFn>(Relative(filter, F::AgentRefDtor));
    g.gplManager = reinterpret_cast<GplManagerFn>(Relative(filter, F::GplManager));
    g.resolveAgent = reinterpret_cast<ResolveAgentFn>(resolveAgent);
    g.attributeLookup = reinterpret_cast<AttributeLookupFn>(attributeLookup);
    g.valueNew = reinterpret_cast<ValueNewFn>(Relative(filter, F::ValueNew));
    g.pushBack = reinterpret_cast<PushBackFn>(pushBack);
    g.anchorDistance = reinterpret_cast<AnchorDistanceFn>(Relative(filter, F::AnchorDistance));
    g.unitPosition = reinterpret_cast<UnitPositionFn>(Relative(filter, F::UnitPosition));
    g.rectDistance = reinterpret_cast<RectDistanceFn>(Relative(filter, F::RectDistance));
    g.teamOf = reinterpret_cast<TeamOfFn>(Relative(filter, F::TeamOf));
    g.unitAttribute = reinterpret_cast<UnitAttributeFn>(Relative(filter, F::UnitAttribute));
    g.stricmpFn = stricmpFn;
    g.inside = reinterpret_cast<const volatile std::uint8_t*>(Absolute(filter, F::Inside));
    g.anchor = reinterpret_cast<void* const volatile*>(Absolute(filter, F::Anchor));
    g.pointGiven = reinterpret_cast<const volatile std::uint8_t*>(Absolute(filter, F::PointGiven));
    g.point = reinterpret_cast<const void*>(Absolute(filter, F::Point));
    g.rangeLimit = reinterpret_cast<const volatile int*>(Absolute(filter, F::RangeLimit));
    g.playerFilter = reinterpret_cast<const volatile int*>(Absolute(filter, F::PlayerFilter));
    g.teamFilter = reinterpret_cast<const volatile int*>(Absolute(filter, F::TeamFilter));
    g.teamTable = reinterpret_cast<void* const volatile*>(Absolute(filter, F::TeamTable));
    g.typeKey = reinterpret_cast<const void*>(Absolute(filter, F::TypeKey));
    g.typeString = reinterpret_cast<const char* const volatile*>(Absolute(filter, F::TypeString));
    g.checkKey = reinterpret_cast<void* const volatile*>(Absolute(filter, F::CheckKey));
    g.checkString = reinterpret_cast<void* const volatile*>(Absolute(filter, F::CheckString));
    g.attributeCount = reinterpret_cast<const volatile int*>(Absolute(filter, F::AttributeCount));
    g.attributeIds = reinterpret_cast<const volatile int*>(Absolute(filter, F::AttributeIds));
    g.attributeValues = reinterpret_cast<const volatile int*>(Absolute(filter, F::AttributeValues));
    g.firstOnly = reinterpret_cast<const volatile std::uint8_t*>(Absolute(filter, F::FirstOnly));
    g.results = reinterpret_cast<void*>(Absolute(filter, F::Results));

    const std::uint32_t replacement =
        static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&AcceleratedFilter));
    auto* site = reinterpret_cast<void*>(push + 1);
    DWORD previous = 0;
    if (!VirtualProtect(site, sizeof(replacement), PAGE_EXECUTE_READWRITE, &previous)) {
        return Refuse("the hand-over site could not be made writable");
    }
    std::memcpy(site, &replacement, sizeof(replacement));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(replacement));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(replacement), previous, &ignored);
#if defined(MAJESTY_LISTOBJECTS_DIFFERENTIAL)
    Log("ListObjects acceleration installed in DIFFERENTIAL verification mode: every unit is "
        "evaluated by both callbacks; the stock result is used.");
#else
    Log("ListObjects acceleration installed: exact per-unit filter behind stock $ListObjects.");
#endif
    return true;
}

}  // namespace ListObjectsAcceleration
