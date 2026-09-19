// Run actual x86 AP78 adapters with stock-shaped list/hero memory.
namespace {
std::vector<std::string> heroLabels, heroTips;
std::vector<unsigned> heroImages, heroSets;
unsigned heroConstructed = 0, heroDestroyed = 0;
unsigned heroUnit[0x180/4] = {};
void* __fastcall HeroTestSelected(void*, void*) { return heroUnit; }
int __fastcall HeroTestAttribute(void*, void*, unsigned key, unsigned) {
    assert(key == 0x0B565041); return static_cast<int>(heroUnit[0]);
}
int __fastcall HeroTestAppend(void*, void*, int index, const char* text) {
    assert(index == -1);
    heroLabels.emplace_back(text);
    return static_cast<int>(heroLabels.size()-1);
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
void __fastcall HeroTestMessage(void*, void*, unsigned message, unsigned row, const void* data) {
    assert(row < heroLabels.size());
    if (message == 0x62) {
        const auto* view = static_cast<const MajestyStringView*>(data);
        assert(view->length == std::strlen(view->data));
        // Copy, as stock does. This remains valid after the temporary view dies.
        heroTips.emplace_back(view->data, view->length);
    } else assert(message == 0x24);
}
void RunHeroInfoRuntimeTests() {
    const auto savedBase = g_imageBase;
    const auto* savedProfile = g_buildProfile;
    auto savedRegistry = g_runtimeFeatureRegistry;
    MajestyBuildProfile profile = kBeta2BuildProfile;
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&HeroTestAttribute);
    g_imageBase = 0;
    g_buildProfile = &profile;
    g_heroSelected = reinterpret_cast<HeroSelected>(&HeroTestSelected);
    g_heroAppend = reinterpret_cast<HeroAppend>(&HeroTestAppend);
    g_heroImageCtor = reinterpret_cast<HeroImageLife>(&HeroTestCtor);
    g_heroImageDtor = reinterpret_cast<HeroImageLife>(&HeroTestDtor);
    g_heroImageType = reinterpret_cast<HeroImageOp>(&HeroTestType);
    g_heroImageId = reinterpret_cast<HeroImageOp>(&HeroTestImage);
    g_heroImageSet = reinterpret_cast<HeroImageOp>(&HeroTestSet);
    g_heroImageFrame = reinterpret_cast<HeroImageOp>(&HeroTestFrame);
    g_heroImageFlags = reinterpret_cast<HeroImageOp>(&HeroTestFlags);
    g_runtimeFeatureRegistry.heroInfoRows = {
        {1, 0x3130415A, 0, 0x3130495A, 1019, "spell", "A private spell", "Its explanation"},
        {2, 0x3130455A, 0, 0x3230495A, 1019, "effect", "An active effect", "While active"},
        {3, 0x3130485A, 2, 0x3330495A, 1019, "passive-a", "First passive", "First explanation"},
        {3, 0x3130485A, 4, 0x3430495A, 1019, "passive-b", "Second passive", "Second explanation"},
    };
    std::uintptr_t vtable[40] = {};
    vtable[0x9C/4] = reinterpret_cast<std::uintptr_t>(&HeroTestMessage);
    auto* list = vtable;
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
    assert(std::strcmp(SelectHeroSpell(0x3130415A, "stock"), "A private spell") == 0);
    HeroSpellImage(nullptr, nullptr, 0xFFFFFFFFu);
    assert(heroImages.back() == 0x3130495A && heroSets.back() == 1019);
    const auto before = heroImages.size();
    assert(std::strcmp(SelectHeroSpell(0x11111111, "stock"), "stock") == 0);
    HeroSpellImage(nullptr, nullptr, 55);
    assert(g_heroSpellRow == nullptr && heroImages.size() == before && heroSets.back() == 55);
    SelectPrivateEnchantmentRow(0x3130455A);
    assert(g_heroEffectRow && std::strcmp(g_privateEnchantmentRowString->data, "An active effect") == 0);
    HeroEffectImage(nullptr, nullptr, 1019);
    assert(heroImages.back() == 0x3230495A);
    SelectPrivateEnchantmentRow(0x11111111);
    assert(g_heroEffectRow == nullptr && g_privateEnchantmentRowString == nullptr);
    // Exercise the naked learned-row wrapper: it must replace only text, retain
    // the caller's index and this pointer, and preserve stack/register ownership.
    unsigned action[5] = {}; action[1] = 0x3130415A;
    auto* actionPtr = action;
    const char* original = "stock label";
    void* listPtr = &list;
    int appended = -1;
    __asm {
        push edi
        mov edi, actionPtr
        push original
        push -1
        mov ecx, listPtr
        call HeroSpellAppendHook
        mov appended, eax
        pop edi
    }
    assert(appended == 2 && heroLabels.back() == "A private spell");
    g_runtimeFeatureRegistry = std::move(savedRegistry);
    g_heroSpellRow = g_heroEffectRow = nullptr;
    g_privateEnchantmentRowString = nullptr;
    g_imageBase = savedBase;
    g_buildProfile = savedProfile;
}
}
