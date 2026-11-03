#include "../runtime/PairedOccupantAction.h"
#include "../runtime/PairedOccupantProfiles.h"
#include <cassert>
#include <vector>
#include <string>
using namespace MajestyPairedOccupantAction;

namespace {
std::vector<void*> nativeArgs;
unsigned nativeExecutions = 0;
int nativeBuilding, nativeHero, nativeEvaluator;
std::vector<std::string> diagnosticStages;
void DiagnosticProbe(const char* stage, const Context& context, void*) {
    assert(context.diagnosticId == 7);
    diagnosticStages.push_back(stage);
}
void __fastcall NativeAppendProbe(void* evaluator, void*, void* hero) {
    assert(evaluator == &nativeEvaluator);
    nativeArgs.push_back(hero);
}
void __fastcall NativeExecuteProbe(void* evaluator, void*) {
    assert(evaluator == &nativeEvaluator);
    ++nativeExecutions;
}
void* NativeResolve(std::uint32_t id) { return id == 5 ? &nativeBuilding : nullptr; }
bool NativeAdmit(void* building, void* hero) { return building == &nativeBuilding && hero == &nativeHero; }
}

int main() {
    unsigned reads = 0;
    auto unavailable = [&](std::uintptr_t, unsigned) -> const unsigned char* { ++reads; return nullptr; };
    assert(!ValidateProfile(static_cast<MajestyBuildId>(255), 0x400000u, unavailable));
    assert(!ValidateProfile(MajestyBuildId::SteamPublic, 0x500000u, unavailable));
    assert(reads == 0);
    for (auto build : {MajestyBuildId::SteamPublic, MajestyBuildId::SteamBeta2, MajestyBuildId::Gog}) {
        assert(!ValidateProfile(build, 0x400000u, unavailable));
    }
    assert(reads == 3);
    Context* current = nullptr;
    int evaluator{}, otherEvaluator{}, building{}, hero{};
    std::vector<void*> arguments;
    int executes = 0, resolves = 0;
    auto append = [&](void* e, void* agent) { assert(e == &evaluator); arguments.push_back(agent); };
    auto resolve = [&](std::uint32_t id) -> void* { ++resolves; return id == 42 ? &building : nullptr; };
    auto admit = [&](void* b, void* h) { return b == &building && h == &hero; };
    auto execute = [&](void* e) { assert(e == &evaluator); ++executes; };
    assert(AdmitPacket(true, 0));
    assert(!AdmitPacket(true, 1));
    assert(!AdmitPacket(true, 0xFFFFFFFFu));
    assert(AdmitPacket(false, 123));
    {
        Scope outer(current, true, 42);
        Context* saved = current;
        AddSubject(current, &evaluator, &hero, resolve, admit, append);
        assert(arguments.size() == 2 && arguments[0] == &building && arguments[1] == &hero);
        Execute(current, &otherEvaluator, execute);
        assert(executes == 0);
        {
            Scope legacy(current, false, 99);
            arguments.clear();
            AddSubject(current, &evaluator, &hero, resolve, admit, append);
            Execute(current, &evaluator, execute);
            assert(arguments.size() == 1 && arguments[0] == &hero && resolves == 1);
        }
        assert(current == saved);
        Execute(current, &evaluator, execute);
        Execute(current, &evaluator, execute);
        assert(executes == 2);
    }
    assert(current == nullptr);
    for (bool reject : {false, true}) {
        Scope missing(current, true, reject ? 42 : 0);
        arguments.clear();
        AddSubject(current, &evaluator, &hero, resolve,
                   [&](void*, void*) { return !reject; }, append);
        Execute(current, &evaluator, execute);
        assert(arguments.size() == 1 && arguments[0] == &hero);
        assert(executes == 2);
    }
    {
        Scope outer(current, true, 42);
        AddSubject(current, &evaluator, &hero, resolve, admit, append);
        auto* saved = current;
        {
            Scope inner(current, true, 0);
            AddSubject(current, &evaluator, &hero, resolve, admit, append);
            Execute(current, &evaluator, execute);
        }
        assert(current == saved);
        Execute(current, &evaluator, execute);
        assert(executes == 3);
    }
    assert(current == nullptr);
    auto& binding = NativeBinding();
    binding.append = reinterpret_cast<StockAppend>(&NativeAppendProbe);
    binding.execute = reinterpret_cast<StockExecute>(&NativeExecuteProbe);
    binding.resolve = &NativeResolve;
    binding.admit = &NativeAdmit;
    assert(binding.Ready());
    // Invoke the actual compiled shims through the original native signatures.
    // This exercises ECX/stack argument shape, not just the portable templates.
    auto addCall = reinterpret_cast<StockAppend>(&AddSubjectShim);
    auto executeCall = reinterpret_cast<StockExecute>(&ExecuteShim);
    for (unsigned id : {5u, 0u}) {
        nativeArgs.clear();
        Scope scope(binding.current, true, id);
        addCall(&nativeEvaluator, &nativeHero);
        executeCall(&nativeEvaluator);
        assert(nativeArgs.size() == (id ? 2u : 1u));
        assert(nativeArgs.back() == &nativeHero);
    }
    assert(nativeExecutions == 1 && binding.current == nullptr);
    for (unsigned id : {5u, 0u}) {
        diagnosticStages.clear(); nativeArgs.clear();
        const auto before = nativeExecutions;
        Scope scope(binding.current, true, id, &DiagnosticProbe, 7);
        addCall(&nativeEvaluator, &nativeHero);
        executeCall(&nativeEvaluator);
        Observe(binding.current, "dispatch-return", nullptr);
        assert(diagnosticStages == std::vector<std::string>({"pair-resolved", "arguments-appended",
            id ? "executed" : "execute-rejected", "dispatch-return"}));
        assert(nativeExecutions == before + (id ? 1 : 0));
        assert(nativeArgs.size() == (id ? 2u : 1u));
    }
}
