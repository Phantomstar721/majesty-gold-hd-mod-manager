// Opt-in distance adapter for stock linear movement orders. No timers, unit
// bookkeeping or order-cache mutation. See stock-overlay-movement-scale.md.
using MovementEffectorLookup = void* (__thiscall*)(void*, std::uint32_t);
MovementEffectorLookup g_movementEffectorLookup = nullptr;
std::uintptr_t g_movementCompareResume = 0, g_movementDestinationResume = 0;

bool ValidateMovementScaleProfile() {
    if (g_buildProfile != &kBeta2BuildProfile) return false;
    const auto hash = [](std::uintptr_t rva, std::size_t size) {
        std::uint32_t result = 2166136261u;
        const auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+rva);
        for (std::size_t i = 0; i < size; ++i) result = (result ^ bytes[i])*16777619u;
        return result;
    };
    return hash(0x1E3060, 0xB3) == 0x32294614u &&
        hash(0x1E3120, 0x1A0) == 0x375BDD45u &&
        hash(0x1E2910, 0x3A) == 0x4F386949u &&
        hash(0x1DE7B0, 0x15) == 0x3AF7B250u &&
        hash(0x1BC6E0, 0x1F3) == 0x785CF9D8u &&
        hash(0x1BBE60, 0xD1) == 0x6F8C6967u &&
        hash(0x1BC320, 0x180) == 0xC5719213u;
}

int __stdcall CurrentMovementStep(void* unit, int baseStep, unsigned flags) {
    if (!unit || baseStep <= 0 || g_runtimeFeatureRegistry.movementScales.empty()) return baseStep;
    const auto* bytes = static_cast<const unsigned char*>(unit);
    const auto* descriptor = *reinterpret_cast<const unsigned char* const*>(bytes+0x54);
    if (!descriptor || !*reinterpret_cast<void* const*>(bytes+0xA4)) return baseStep;
    const auto* engine = *reinterpret_cast<const unsigned char* const*>(descriptor+0x14);
    if (!engine || *reinterpret_cast<const std::uintptr_t*>(engine) != g_imageBase+0x364310) return baseStep;
    int percent = 100;
    for (const auto& record : g_runtimeFeatureRegistry.movementScales) {
        if (record.percent != 100 && g_movementEffectorLookup(unit, record.overlayId)) {
            percent += static_cast<int>(record.percent)-100;
        }
    }
    if (percent == 100) return baseStep;
    // Like stock packed modifiers, distinct bonuses add. Retain a positive
    // minimum when several slowing overlays overlap; widening avoids wrap.
    const auto value = static_cast<std::int64_t>(baseStep)*(percent > 0 ? percent : 1)/100;
    const int maximum = flags & 0x4000 ? 30720 : (std::numeric_limits<int>::max)();
    return value < 1 ? 1 : value > maximum ? maximum : static_cast<int>(value);
}

int MovementQueryDistance(void* unit, int distance) {
    return CurrentMovementStep(unit, distance, 0);
}

__declspec(naked) void MovementCompareHook() {
    __asm {
        pushad
        push dword ptr [esi+34h]
        push dword ptr [ebx]
        push ebp
        call CurrentMovementStep
        mov dword ptr [esp+28], eax
        popad
        // Stock already reuses the consumed unit-argument slot for its lazy
        // step output (unit survives in EBP). Borrow that same slot for this
        // update's scaled value, and redirect the local step pointer. Native
        // vector math and the continuation test then read one consistent
        // value without another lookup after movement/callbacks.
        mov dword ptr [esp+2Ch], eax
        lea ebx, [esp+2Ch]
        test eax, eax
        jle destination
        jmp dword ptr [g_movementCompareResume]
    destination:
        jmp dword ptr [g_movementDestinationResume]
    }
}

bool InstallMovementScale() {
    if (g_runtimeFeatureRegistry.movementScales.empty()) return true;
    if (!ValidateMovementScaleProfile()) return false;
    g_movementEffectorLookup = reinterpret_cast<MovementEffectorLookup>(g_imageBase+0x1DE7B0);
    g_movementCompareResume = g_imageBase+0x1E31D8;
    g_movementDestinationResume = g_imageBase+0x1E324A;
    return WriteOccupantBranch(g_imageBase+0x1E31D2, reinterpret_cast<void*>(&MovementCompareHook), 0xE9, 6);
}
