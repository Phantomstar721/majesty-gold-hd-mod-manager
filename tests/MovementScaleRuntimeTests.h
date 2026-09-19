// Execute the literal stock linear-order body with isolated native-shaped
// unit/order callbacks. No game process, injection, or profile composition.
#include <cmath>
namespace MovementScaleTest {
struct Point { int x, y, z; };
Point position{};
void* expectedUnit = nullptr;
bool activeFirst = false, activeSecond = false, blocked = false;
bool invalidateAfterCallback = false;
int lookups = 0, callbacks = 0, retirements = 0, lazySteps = 0;
int clockValue = 1000, stockStepCap = 30720;
unsigned char capInitialized = 1;
void* __fastcall Effector(void* unit, void*, unsigned id) {
    assert(unit == expectedUnit);
    ++lookups;
    return ((id == 0x3130455A && activeFirst) || (id == 0x3230455A && activeSecond))
        ? expectedUnit : nullptr;
}
Point* __fastcall Position(void* unit, void*, Point* out) {
    assert(unit == expectedUnit); *out = position; return out;
}
void __fastcall UpdateTarget(void*, void*, void* unit) { assert(unit == expectedUnit); }
void __fastcall Move(void*, void*, void* unit, Point next) {
    assert(unit == expectedUnit);
    if (!blocked) position = next;
}
void __fastcall Notify(void*, void*, void* order, void* scratch, unsigned reason) {
    assert(scratch == static_cast<unsigned char*>(order)+0x4C && reason == 0);
    ++callbacks;
    if (invalidateAfterCallback) {
        const std::uintptr_t invalid = 1;
        std::memcpy(static_cast<unsigned char*>(expectedUnit)+0x54, &invalid, 4);
    }
}
void __fastcall Retire(void*, void*, void* order) {
    ++retirements;
    // Stock is allowed to dispose of the order here. Any post-call restore of
    // a temporarily changed cache would corrupt this tombstone.
    std::memset(order, 0xDD, 0x58);
}
int __cdecl Root(int squared, int fractional) {
    assert(fractional == 16 && squared >= 0);
    return static_cast<int>(std::sqrt(static_cast<double>(squared)/65536.0)*65536.0);
}
int* __cdecl LazyStep(int* out, void* unit, int interval, unsigned) {
    assert(unit == expectedUnit && interval == 50); ++lazySteps; *out = 16384; return out;
}
void Put(void* base, unsigned offset, std::uintptr_t value) {
    std::memcpy(static_cast<unsigned char*>(base)+offset, &value, 4);
}
void CopyHex(unsigned char* target, const char* text) {
    const auto hex = [](char c) { return c <= '9' ? c-'0' : c-'a'+10; };
    for (; *text; text += 2) *target++ = static_cast<unsigned char>((hex(text[0])<<4)|hex(text[1]));
}
void Relative(unsigned char* site, const void* function) {
    const auto delta = static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(function)
        -reinterpret_cast<std::uintptr_t>(site)-5);
    std::memcpy(site+1, &delta, 4);
}
// RVA, exact unmodified stock body. Python independently checks these bytes.
const char* orderHex = "83ec18837c242400535556578bf10f85800100008b7c242c8d44241c508bcfe89c3fffff8b168b421c578bceffd0f64634208b4c24247403894e448b46448b7e3c8b5e402b7c241c2b5c24202bc15050897c2418895c241c89442420e8779f090053538be8e86e9f09006a1057578bd8e8639f090003c303c550e8c198e4ff8b6c24348d5e4883c408833b008bf8897c2434751a8b4e348b461451508d5424345552e899feffff8b0083c410890385ff7e788b0385c07e723bf87f09f74634004000007465538d4c2414e821f7ffff8d4c2434518d4c2414e853f7fffff746340040000074178d54241052e810feffff8d44241850e806feffff83c4088b4c241c8b5424108b4424148b7c241803ca8b54242003d08b44242403f883ec0c8bc48908895004897808eb168b4e3c83ec0c8bc489088b56408950048b4e448948088b168b4220558bceffd08b7c24308b178b52446a008d464c50568bcfffd28b44243485c07e248b1b85db7e1e3bc37e1aa1dc3f7e008b4e14894608894e0cb0015f5e5d5b83c418c20c008b178b424c568bcfffd05f5e5db0015b83c418c20c00";
const char* multiplyHex = "56578b7c240c8b078bf18b0e5051e8d5a7090089068b178b46045250e8c7a709008946048b0f8b56085152e8b8a709008946085f8bc65ec20400";
const char* divideHex = "56578b7c240c8b078bf18b0e5051e8aea7090089068b178b46045250e8a0a709008946048b0f8b56085152e891a709008946085f8bc65ec20400";
const char* fixedMultiplyHex = "558bec528b45088b550cf7eac1e810c1e2100bc25ac9c20800";
const char* fixedDivideHex = "558bec52538b45088b550c8bda990fa4c210c1e010f7fb5b5ac9c20800";
const char* clampHex = "803d30407e0000751d68000020006800000f00e8d9a00900a334407e00c60530407e0001eb05a134407e008b5424048b0a3bc87f06f7d83bc87d028902c3";

void Run() {
    unsigned registryWords[] = {0x52464D4D, 8, 0, 0, 64, 1, 0x3130455A, 115};
    auto* registryBytes = reinterpret_cast<unsigned char*>(registryWords);
    MajestyRuntimeFeatures::Registry parsed;
    std::string error;
    assert(MajestyRuntimeFeatures::ParseRegistry(registryBytes, sizeof(registryWords), &parsed, &error));
    assert(parsed.movementScales.size() == 1 && parsed.movementScales[0].overlayId == 0x3130455A &&
           parsed.movementScales[0].percent == 115);
    for (unsigned size = 0; size < sizeof(registryWords); ++size) {
        assert(!MajestyRuntimeFeatures::ParseRegistry(registryBytes, size, &parsed, &error));
        assert(parsed.movementScales.empty());
    }
    for (unsigned percent : {0u, 1001u, 0xFFFFFFFFu}) {
        registryWords[7] = percent;
        assert(!MajestyRuntimeFeatures::ParseRegistry(registryBytes, sizeof(registryWords), &parsed, &error));
    }
    registryWords[7] = 115;
    for (unsigned flags : {0u, 128u}) {
        registryWords[4] = flags;
        assert(!MajestyRuntimeFeatures::ParseRegistry(registryBytes, sizeof(registryWords), &parsed, &error));
    }
    assert(MajestyRuntimeCapabilities::IsSupportedCapability(MajestyRuntimeCapabilities::kMovementScale));
    const auto savedBase = g_imageBase;
    const auto savedRegistry = g_runtimeFeatureRegistry;
    const auto savedLookup = g_movementEffectorLookup;
    auto* code = static_cast<unsigned char*>(VirtualAlloc(nullptr, 4096, MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE));
    assert(code);
    auto* multiply = code+512;
    auto* divide = code+640;
    auto* fixedMultiply = code+768;
    auto* fixedDivide = code+832;
    auto* clamp = code+896;
    CopyHex(code, orderHex); CopyHex(multiply, multiplyHex); CopyHex(divide, divideHex);
    CopyHex(fixedMultiply, fixedMultiplyHex); CopyHex(fixedDivide, fixedDivideHex); CopyHex(clamp, clampHex);
    Relative(code+0x1F, reinterpret_cast<void*>(&Position));
    for (unsigned offset : {0x5Cu, 0x65u, 0x70u}) Relative(code+offset, fixedMultiply);
    Relative(code+0x7A, reinterpret_cast<void*>(&Root));
    Relative(code+0xA2, reinterpret_cast<void*>(&LazyStep));
    Relative(code+0xCA, multiply); Relative(code+0xD8, divide);
    Relative(code+0xEB, clamp); Relative(code+0xF5, clamp);
    Put(code, 0x171, reinterpret_cast<std::uintptr_t>(&clockValue));
    for (unsigned offset : {0xEu, 0x1Cu, 0x2Bu}) {
        Relative(multiply+offset, fixedMultiply);
        Relative(divide+offset, fixedDivide);
    }
    Put(clamp, 2, reinterpret_cast<std::uintptr_t>(&capInitialized));
    Put(clamp, 0x19, reinterpret_cast<std::uintptr_t>(&stockStepCap));
    Put(clamp, 0x1F, reinterpret_cast<std::uintptr_t>(&capInitialized));
    Put(clamp, 0x27, reinterpret_cast<std::uintptr_t>(&stockStepCap));
    Relative(clamp+0x13, fixedDivide);
    DWORD old = 0;
    assert(VirtualProtect(code, 4096, PAGE_EXECUTE_READ, &old));
    FlushInstructionCache(GetCurrentProcess(), code, 4096);

    g_runtimeFeatureRegistry = {};
    g_runtimeFeatureRegistry.movementScales = {{0x3130455A, 115}};
    g_movementEffectorLookup = reinterpret_cast<MovementEffectorLookup>(&Effector);
    g_movementCompareResume = reinterpret_cast<std::uintptr_t>(code+0xB8);
    g_movementDestinationResume = reinterpret_cast<std::uintptr_t>(code+0x12A);
    g_imageBase = 0;
    unsigned char unit[0xA8] = {}, descriptor[0x18] = {}, engine[0x18] = {};
    Put(unit, 0x54, reinterpret_cast<std::uintptr_t>(descriptor));
    Put(unit, 0xA4, 1);
    Put(descriptor, 0x14, reinterpret_cast<std::uintptr_t>(engine));
    Put(engine, 0, 0x364310);
    expectedUnit = unit;
    void* orderTable[9] = {};
    orderTable[7] = reinterpret_cast<void*>(&UpdateTarget);
    orderTable[8] = reinterpret_cast<void*>(&Move);
    void* managerTable[20] = {};
    managerTable[17] = reinterpret_cast<void*>(&Notify);
    managerTable[19] = reinterpret_cast<void*>(&Retire);
    void** manager = managerTable;
    unsigned char order[0x58] = {};
    const auto reset = [&]() {
        std::memset(order, 0, sizeof(order));
        Put(order, 0, reinterpret_cast<std::uintptr_t>(orderTable));
        Put(order, 0x14, 50); Put(order, 0x3C, 8*65536); Put(order, 0x48, 16384);
        position = {}; callbacks = retirements = lazySteps = lookups = 0;
        blocked = invalidateAfterCallback = false;
        Put(unit, 0x54, reinterpret_cast<std::uintptr_t>(descriptor));
    };
    using Execute = bool (__thiscall*)(void*, void*, void*, unsigned);
    auto execute = reinterpret_cast<Execute>(code);
    // Capture original native behavior before installing the distance adapter.
    reset(); activeFirst = true;
    assert(execute(order, unit, &manager, 0) == 1);
    assert(position.x == 16384 && callbacks == 1 && retirements == 0);
    assert(*reinterpret_cast<int*>(order+0x48) == 16384);

    assert(WriteOccupantBranch(reinterpret_cast<std::uintptr_t>(code+0xB2),
        reinterpret_cast<void*>(&MovementCompareHook), 0xE9, 6));
    reset(); activeFirst = false;
    execute(order, unit, &manager, 0);
    assert(position.x == 16384 && lookups == 1);
    // Same native order: apply, expire, restore; never change its cached base.
    activeFirst = true;
    execute(order, unit, &manager, 0);
    assert(position.x-16384 >= 18840 && position.x-16384 <= 18841);
    assert(*reinterpret_cast<int*>(order+0x48) == 16384);
    int prior = position.x;
    activeFirst = false;
    execute(order, unit, &manager, 0);
    assert(position.x-prior >= 16383 && position.x-prior <= 16384);
    activeFirst = true;
    prior = position.x;
    execute(order, unit, &manager, 0);
    assert(position.x-prior >= 18840 && position.x-prior <= 18841);
    assert(*reinterpret_cast<int*>(order+0x48) == 16384);
    assert(*reinterpret_cast<int*>(order+8) == clockValue && *reinterpret_cast<int*>(order+0xC) == 50);
    assert(retirements == 0);

    reset(); invalidateAfterCallback = true;
    execute(order, unit, &manager, 0);
    assert(callbacks == 1 && lookups == 1 && position.x == 18841);

    // The distance comparison must also use the scaled value: this target is
    // beyond the stock step but inside the scaled step.
    reset(); Put(order, 0x3C, 18000);
    execute(order, unit, &manager, 0);
    assert(position.x == 18000 && callbacks == 1 && retirements == 1);
    assert(order[0x48] == 0xDD);
    reset(); blocked = true;
    execute(order, unit, &manager, 0);
    assert(position.x == 0 && callbacks == 1);
    reset(); Put(order, 0x48, 0);
    execute(order, unit, &manager, 0);
    assert(lazySteps == 1 && *reinterpret_cast<int*>(order+0x48) == 16384);
    reset(); execute(order, unit, &manager, 1);
    assert(position.x == 0 && callbacks == 0 && retirements == 0);

    // Stock flag-specific clamping remains in both scalar and vector paths.
    reset(); Put(order, 0x48, 30000); Put(order, 0x34, 0x4000);
    execute(order, unit, &manager, 0);
    assert(position.x == 30720 && *reinterpret_cast<int*>(order+0x48) == 30000);
    g_runtimeFeatureRegistry.movementScales.push_back({0x3230455A, 115});
    activeSecond = true;
    assert(CurrentMovementStep(unit, 20000, 0) == 26000);
    assert(MovementQueryDistance(unit, 16384)/100 == 212);
    g_runtimeFeatureRegistry.movementScales[1].percent = 85;
    assert(CurrentMovementStep(unit, 20000, 0) == 20000);
    g_runtimeFeatureRegistry.movementScales[0].percent = 1;
    assert(CurrentMovementStep(unit, 20000, 0) == 200);
    g_runtimeFeatureRegistry.movementScales[0].percent = 1000;
    activeSecond = false;
    assert(CurrentMovementStep(unit, 0x7FFFFFFF, 0) == 0x7FFFFFFF);
    assert(CurrentMovementStep(unit, 1, 0) == 10);
    assert(CurrentMovementStep(unit, 0, 0) == 0 && CurrentMovementStep(unit, -1, 0) == -1);
    Put(unit, 0xA4, 0); lookups = 0;
    assert(CurrentMovementStep(unit, 20000, 0) == 20000 && lookups == 0);
    Put(unit, 0xA4, 1); Put(engine, 0, 123);
    assert(CurrentMovementStep(unit, 20000, 0) == 20000 && lookups == 0);
    g_runtimeFeatureRegistry.movementScales.clear();
    assert(InstallMovementScale()); // No profile access or patches when unused.
    g_imageBase = savedBase; g_runtimeFeatureRegistry = savedRegistry;
    g_movementEffectorLookup = savedLookup;
    g_movementCompareResume = g_movementDestinationResume = 0;
    assert(VirtualFree(code, 0, MEM_RELEASE));
}
} // namespace MovementScaleTest
