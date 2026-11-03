#pragma once
#include <cstdint>

// Normal-return adapter for the researched MX05 AddSubject / Execute calls.
// Callers retain stock validation, price-zero debit, construction and destruction.
// No retained agent pointer, alternate payment implementation or exception retry.
namespace MajestyPairedOccupantAction {
struct Context;
using Trace = void (*)(const char*, const Context&, void*);
struct Context {
    bool paired;
    std::uint32_t building;
    void* evaluator = nullptr;
    bool admitted = false;
    bool executed = false;
    void* resolvedBuilding = nullptr;
    void* validatedHero = nullptr;
    unsigned appended = 0;
    Trace trace = nullptr;
    unsigned diagnosticId = 0;
};
inline void Observe(Context* context, const char* stage, void* evaluator) {
    if (context && context->paired && context->trace) context->trace(stage, *context, evaluator);
}

class Scope {
    Context*& current_;
    Context* previous_;
    Context value_;
public:
    Scope(Context*& current, bool paired, std::uint32_t building, Trace trace = nullptr, unsigned diagnosticId = 0)
        : current_(current), previous_(current), value_{paired, building} {
        // Even a legacy nested command masks its outer paired context.
        current_ = &value_;
        value_.trace = trace;
        value_.diagnosticId = diagnosticId;
    }
    ~Scope() { current_ = previous_; }
    Scope(const Scope&) = delete;
    Scope& operator=(const Scope&) = delete;
};

template<class Resolve, class Admit, class Append>
void AddSubject(Context* context, void* evaluator, void* validatedHero,
                Resolve resolve, Admit admit, Append append) {
    if (!context || !context->paired) {
        append(evaluator, validatedHero);
        return;
    }
    // A second unexpected invocation cannot grow a valid two-agent frame.
    if (context->evaluator) {
        context->admitted = false;
        Observe(context, "duplicate-append-rejected", evaluator);
        return;
    }
    context->evaluator = evaluator;
    context->validatedHero = validatedHero;
    void* building = resolve(context->building);
    context->resolvedBuilding = building;
    context->admitted = building && admit(building, validatedHero);
    Observe(context, "pair-resolved", evaluator);
    if (context->admitted) { append(evaluator, building); ++context->appended; }
    // Keep stock's original append even for a missing building. Execute below
    // skips that incomplete pair, then the native continuation destroys it.
    append(evaluator, validatedHero);
    ++context->appended;
    Observe(context, "arguments-appended", evaluator);
}

template<class Invoke>
void Execute(Context* context, void* evaluator, Invoke invoke) {
    if (!context || !context->paired) {
        invoke(evaluator);
        return;
    }
    if (context->evaluator != evaluator || !context->admitted || context->executed) {
        Observe(context, "execute-rejected", evaluator);
        return;
    }
    context->executed = true;
    invoke(evaluator);
    Observe(context, "executed", evaluator);
}

inline bool AdmitPacket(bool paired, std::uint32_t quotedPrice) {
    return !paired || quotedPrice == 0;
}

#if defined(_MSC_VER) && defined(_M_IX86)
// Installer fills these only after all profile guards, before redirecting calls.
// Kept separate from registration so no development declaration installs a hook.
using StockAppend = void (__thiscall*)(void*, void*);
using StockExecute = void (__thiscall*)(void*);
struct Binding {
    Context* current = nullptr;
    StockAppend append = nullptr;
    StockExecute execute = nullptr;
    void* (*resolve)(std::uint32_t) = nullptr;
    bool (*admit)(void*, void*) = nullptr;
    bool Ready() const { return append && execute && resolve && admit; }
};
inline Binding& NativeBinding() {
    static Binding value;
    return value;
}
// Fastcall's unused EDX accommodates the original thiscall ABI. The one stack
// argument is callee-popped by AddSubjectShim, matching original AddAgent RET4.
inline void __fastcall AddSubjectShim(void* evaluator, void*, void* hero) {
    auto& binding = NativeBinding();
    AddSubject(binding.current, evaluator, hero,
               binding.resolve, binding.admit, binding.append);
}
inline void __fastcall ExecuteShim(void* evaluator, void*) {
    auto& binding = NativeBinding();
    Execute(binding.current, evaluator, binding.execute);
}
#endif
} // namespace MajestyPairedOccupantAction
