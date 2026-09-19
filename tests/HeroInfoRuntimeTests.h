// Run actual x86 AP78 adapters with stock-shaped list/hero memory.
namespace {
std::vector<std::string> heroLabels, heroTips;
std::vector<unsigned> heroImages, heroSets;
unsigned heroConstructed = 0, heroDestroyed = 0;
void* heroExpectedList = nullptr;
const MajestyStringView* heroLastLabel = nullptr;
const MajestyStringView* heroLastAssignment = nullptr;
std::string heroAssignedText;
bool heroRejectAppend = false;
unsigned heroUnit[0x180/4] = {};
void* __fastcall HeroTestSelected(void*, void*) { return heroUnit; }
int __fastcall HeroTestAttribute(void*, void*, unsigned key, unsigned) {
    assert(key == 0x0B565041); return static_cast<int>(heroUnit[0]);
}
std::string HeroTestCopyString(const void* text) {
    // Read the native object, not a char buffer. A raw "Ball..." buffer must
    // fail these bounds before its first four letters become a data pointer.
    const auto* view = static_cast<const MajestyStringView*>(text);
    assert(view && view->length > 0 && view->length <= 512);
    assert((view->capacityFlags & 0x01000000u) == 0);
    assert((view->capacityFlags & 0x00FFFFFFu) >= view->length);
    assert(view->data && view->length == std::strlen(view->data));
    return std::string(view->data, view->length);
}
void __fastcall HeroTestCtor(void* image, void*) {
    ++heroConstructed; std::memset(image, 0xCC, 0x6C);
}
void __fastcall HeroTestDtor(void*, void*) { ++heroDestroyed; }
void __fastcall HeroTestType(void*, void*, unsigned value) { assert(value == 1); }
void __fastcall HeroTestImage(void*, void*, unsigned value) { heroImages.push_back(value); }
void __fastcall HeroTestSet(void*, void*, unsigned value) { heroSets.push_back(value); }
void __fastcall HeroTestFrame(void*, void*, unsigned value) { assert(value == 0); }
void __fastcall HeroTestFlags(void* image, void*, unsigned value) {
    assert(value == 9 && static_cast<unsigned*>(image)[0x1C/4] == 0);
}
int __fastcall HeroTestMessage(void* list, void*, unsigned message, unsigned row, const void* data) {
    assert(list == heroExpectedList);
    if (message == 0x26) {
        assert(row == 0xFFFFFFFFu && data == nullptr);
        if (heroRejectAppend) return -1;
        heroLabels.emplace_back(); heroTips.emplace_back();
        return static_cast<int>(heroLabels.size()-1);
    }
    assert(row < heroLabels.size());
    if (message == 0x60) {
        heroLastLabel = static_cast<const MajestyStringView*>(data);
        heroLabels[row] = HeroTestCopyString(data);
    } else if (message == 0x62) {
        // Both setters copy synchronously; no borrowed string/view survives.
        heroTips[row] = HeroTestCopyString(data);
    } else assert(message == 0x24);
    return 1;
}
MajestyStringView* __fastcall HeroTestAssign(
    MajestyStringView* destination, void*, const MajestyStringView* source) {
    heroLastAssignment = source;
    heroAssignedText = HeroTestCopyString(source);
    *destination = HeroInfoString(heroAssignedText);
    return destination;
}
int HeroTestAppendSpell(void* list, unsigned actionId, const MajestyStringView* original) {
    unsigned action[5] = {}; action[1] = actionId;
    auto* actionPtr = action;
    int result = -1;
    __asm {
        push edi
        mov edi, actionPtr
        push original
        push -1
        mov ecx, list
        call HeroSpellAppendHook
        mov result, eax
        pop edi
    }
    return result;
}
// Supply the real call-site registers, including image this in ECX. The hook
// must finish by tail-calling the stock destructor without changing ownership.
__declspec(naked) void HeroTestFinishSpell(void*, int, void*) {
    __asm {
        push ebp
        push edi
        mov ebp, [esp+12]
        mov edi, [esp+16]
        mov ecx, [esp+20]
        call HeroSpellFinishHook
        pop edi
        pop ebp
        ret
    }
}
__declspec(naked) void HeroTestFinishEffect(void*, int, void*) {
    __asm {
        push ebx
        push ebp
        mov ebx, [esp+12]
        mov ebp, [esp+16]
        mov ecx, [esp+20]
        call HeroEffectFinishHook
        pop ebp
        pop ebx
        ret
    }
}
void RunHeroInfoRuntimeTests() {
    const auto savedBase = g_imageBase;
    const auto* savedProfile = g_buildProfile;
    auto savedRegistry = g_runtimeFeatureRegistry;
    const auto savedAssign = g_stockStringAssign;
    // Literal beta2 0x672410/0x672450 body, including thiscall ret 8 and
    // message 0x26 -> 0x60 dispatch. No relative/absolute game references.
    // Executing stock's wrapper prevents a mock signature hiding an ABI bug.
    const unsigned char stockAppend[] = {
        0x56,0x57,0x6A,0x00,0x8B,0xF1,0x8B,0x06,0x8B,0x90,0x9C,0x00,0x00,0x00,
        0x6A,0xFF,0x6A,0x26,0xFF,0xD2,0x8B,0xF8,0x83,0xFF,0xFF,0x74,0x16,
        0x8B,0x4C,0x24,0x10,0x8B,0x06,0x8B,0x90,0x9C,0x00,0x00,0x00,0x51,
        0x57,0x6A,0x60,0x8B,0xCE,0xFF,0xD2,0x8B,0xC7,0x5F,0x5E,0xC2,0x08,0x00,
    };
    void* appendCode = VirtualAlloc(nullptr, sizeof(stockAppend), MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE);
    assert(appendCode);
    std::memcpy(appendCode, stockAppend, sizeof(stockAppend));
    DWORD oldProtection = 0;
    const BOOL protectedCode = VirtualProtect(appendCode, sizeof(stockAppend), PAGE_EXECUTE_READ, &oldProtection);
    assert(protectedCode);
    FlushInstructionCache(GetCurrentProcess(), appendCode, sizeof(stockAppend));
    MajestyBuildProfile profile = kBeta2BuildProfile;
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&HeroTestAttribute);
    g_imageBase = 0;
    g_buildProfile = &profile;
    g_heroSelected = reinterpret_cast<HeroSelected>(&HeroTestSelected);
    g_heroAppend = reinterpret_cast<HeroAppend>(appendCode);
    g_stockStringAssign = reinterpret_cast<std::uintptr_t>(&HeroTestAssign);
    g_heroImageCtor = reinterpret_cast<HeroImageLife>(&HeroTestCtor);
    g_heroImageDtor = reinterpret_cast<HeroImageLife>(&HeroTestDtor);
    g_heroImageType = reinterpret_cast<HeroImageOp>(&HeroTestType);
    g_heroImageId = reinterpret_cast<HeroImageOp>(&HeroTestImage);
    g_heroImageSet = reinterpret_cast<HeroImageOp>(&HeroTestSet);
    g_heroImageFrame = reinterpret_cast<HeroImageOp>(&HeroTestFrame);
    g_heroImageFlags = reinterpret_cast<HeroImageOp>(&HeroTestFlags);
    g_runtimeFeatureRegistry.heroInfoRows = {
        {1, 0x3130415A, 0, 0x3130495A, 1019, "spell", "Ballad of courage", "Its explanation"},
        {2, 0x3130455A, 0, 0x3230495A, 1019, "effect", "An active effect", "While active"},
        {3, 0x3130485A, 2, 0x3330495A, 1019, "passive-a", "First passive", "First explanation"},
        {3, 0x3130485A, 4, 0x3430495A, 1019, "passive-b", "Second passive", "Second explanation"},
    };
    std::uintptr_t vtable[40] = {};
    vtable[0x9C/4] = reinterpret_cast<std::uintptr_t>(&HeroTestMessage);
    auto* list = vtable;
    heroExpectedList = &list;
    heroLabels.clear(); heroTips.clear(); heroImages.clear(); heroSets.clear();
    heroConstructed = heroDestroyed = 0;
    heroUnit[0] = 10;
    heroUnit[0x7C/4] = 0x3030485A; // another hero
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.empty());
    heroUnit[0x7C/4] = 0x3130485A;
    heroUnit[0] = 1;
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.empty());
    heroUnit[0] = 3;
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.size() == 1 && heroTips[0] == "First explanation");
    heroLabels.clear(); heroTips.clear();
    heroUnit[0] = 4;
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.size() == 2 && heroLabels[1] == "Second passive");
    assert(heroTips.size() == 2 && heroTips[1] == "Second explanation");
    assert(heroConstructed == 3 && heroDestroyed == 3);
    heroRejectAppend = true;
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.size() == 2 && heroConstructed == 3 && heroDestroyed == 3);
    heroRejectAppend = false;
    const std::string stockText = "stock label";
    const auto stock = HeroInfoString(stockText);
    assert(HeroTestCopyString(SelectHeroSpell(0x3130415A, &stock)) == "Ballad of courage");
    HeroSpellImage(nullptr, nullptr, 0xFFFFFFFFu);
    assert(heroImages.back() == 0x3130495A && heroSets.back() == 1019);
    const auto before = heroImages.size();
    assert(SelectHeroSpell(0x11111111, &stock) == &stock);
    HeroSpellImage(nullptr, nullptr, 55);
    assert(g_heroSpellRow == nullptr && heroImages.size() == before && heroSets.back() == 55);
    // Exercise the naked learned-row wrapper: it must replace only text, retain
    // the caller's index and this pointer, and preserve stack/register ownership.
    const int spellIndex = HeroTestAppendSpell(&list, 0x3130415A, &stock);
    assert(spellIndex == 2 && heroLabels.back() == "Ballad of courage");
    assert(heroLastLabel == &g_heroSpellLabel);
    alignas(4) unsigned char image[0x6C] = {};
    HeroTestCtor(image, nullptr);
    HeroTestFinishSpell(&list, spellIndex, image);
    assert(heroTips[spellIndex] == "Its explanation" && heroDestroyed == heroConstructed);
    const int stockIndex = HeroTestAppendSpell(&list, 0x11111111, &stock);
    assert(stockIndex == 3 && heroLabels.back() == stockText && heroLastLabel == &stock);
    HeroTestCtor(image, nullptr);
    HeroTestFinishSpell(&list, stockIndex, image);
    assert(heroTips[stockIndex].empty() && heroDestroyed == heroConstructed);

    // Effect string assignment, append, tooltip finish and unclaimed fallback
    // are distinct native boundaries, even though all use the same view ABI.
    auto assignEffect = reinterpret_cast<StockStringAssign>(&PrivateEnchantmentRowStringHook);
    MajestyStringView effectText = {};
    SelectPrivateEnchantmentRow(0x3130455A);
    assert(g_heroEffectRow);
    assert(assignEffect(&effectText, &stock) == &effectText);
    assert(heroLastAssignment == &g_heroEffectLabel);
    const int effectIndex = g_heroAppend(&list, -1, &effectText);
    assert(heroLabels[effectIndex] == "An active effect");
    HeroTestCtor(image, nullptr);
    HeroEffectImage(image, nullptr, 1019);
    HeroTestFinishEffect(&list, effectIndex, image);
    assert(heroImages.back() == 0x3230495A && heroTips[effectIndex] == "While active");
    assert(heroDestroyed == heroConstructed);
    SelectPrivateEnchantmentRow(0x11111111);
    assert(g_heroEffectRow == nullptr && g_privateEnchantmentRowString == nullptr);
    assignEffect(&effectText, &stock);
    assert(heroLastAssignment == &stock && heroAssignedText == stockText);

    // Refresh replaces the temporary view, not previously copied rows. Then
    // destroy source text before inspecting copied labels/tooltips.
    g_runtimeFeatureRegistry.heroInfoRows[0].displayText = "Replacement label";
    const int nextIndex = HeroTestAppendSpell(&list, 0x3130415A, &stock);
    assert(heroLabels[nextIndex] == "Replacement label");
    g_runtimeFeatureRegistry.heroInfoRows.clear();
    heroAssignedText.clear();
    assert(heroLabels[spellIndex] == "Ballad of courage");
    assert(heroLabels[effectIndex] == "An active effect" && heroTips[effectIndex] == "While active");
    assert(heroTips[0] == "First explanation" && heroTips[spellIndex] == "Its explanation");
    heroLabels.clear(); heroTips.clear();
    AppendHeroPassives(nullptr, &list);
    assert(heroLabels.empty());
    g_runtimeFeatureRegistry = std::move(savedRegistry);
    g_heroSpellRow = g_heroEffectRow = nullptr;
    g_privateEnchantmentRowString = nullptr;
    g_heroSpellLabel = {}; g_heroEffectLabel = {};
    g_stockStringAssign = savedAssign;
    g_heroAppend = nullptr;
    VirtualFree(appendCode, 0, MEM_RELEASE);
    g_imageBase = savedBase;
    g_buildProfile = savedProfile;
}
}
