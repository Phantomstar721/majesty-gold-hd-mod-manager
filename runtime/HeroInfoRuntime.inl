// AP78 presentation adapters. Stock owns list refresh, hit testing, hover,
// string/image copies and destruction. No game behavior or timer is added.
using HeroInfoRecord = MajestyRuntimeFeatures::HeroInfoRecord;
const HeroInfoRecord* g_heroSpellRow = nullptr;
const HeroInfoRecord* g_heroEffectRow = nullptr;
MajestyStringView g_heroSpellLabel = {};
MajestyStringView g_heroEffectLabel = {};
// Both stock append wrappers forward a 12-byte string object to message 0x60,
// not a char buffer. Stock synchronously parses/copies it into the owned row.
using HeroAppend = int (__thiscall*)(void*, int, const MajestyStringView*);
using HeroImageOp = void (__thiscall*)(void*, std::uint32_t);
using HeroImageLife = void (__thiscall*)(void*);
using HeroSelected = void* (__thiscall*)(void*);
HeroAppend g_heroAppend = nullptr;
HeroImageOp g_heroImageType = nullptr, g_heroImageId = nullptr,
    g_heroImageSet = nullptr, g_heroImageFrame = nullptr, g_heroImageFlags = nullptr;
HeroImageLife g_heroImageCtor = nullptr, g_heroImageDtor = nullptr;
HeroSelected g_heroSelected = nullptr;
std::uintptr_t g_heroPassiveResume = 0;

bool HeroEffectRowsSelected() {
    return std::any_of(g_runtimeFeatureRegistry.heroInfoRows.begin(),
        g_runtimeFeatureRegistry.heroInfoRows.end(), [](const HeroInfoRecord& r) { return r.kind == 2; });
}
bool ValidateHeroInfoProfile() {
    return g_buildProfile && MajestyFeatureParity::Validate(
        g_imageBase,g_buildProfile->buildId,MajestyFeatureParity::Feature::HeroInfo);
}
std::uintptr_t g_inventorySpellContinue = 0, g_inventorySpellSkip = 0;
bool __stdcall HideInventorySpell(unsigned actionId) {
    const auto& ids = g_runtimeFeatureRegistry.hiddenInventoryActions;
    return std::binary_search(ids.begin(), ids.end(), actionId);
}
// Stock gate: cmp byte ptr [eax+14h], bl; je next-node. EAX is the
// borrowed learned-spell node. Preserve it and all stock loop registers.
// No writes to the node, inventory, cooldown, or saved data.
__declspec(naked) void InventorySpellGate() {
    __asm {
        pushfd
        pushad
        push dword ptr [eax+8]
        call HideInventorySpell
        test al, al
        jnz filtered
        popad
        popfd
        cmp byte ptr [eax+14h], bl
        je skip
        jmp dword ptr [g_inventorySpellContinue]
    filtered:
        popad
        popfd
    skip:
        jmp dword ptr [g_inventorySpellSkip]
    }
}
bool InstallInventorySpellDisplay() {
    const auto body = ParityRva(ParitySite::HeroLearned);
    const unsigned char gate[] = {0x38,0x58,0x14,0x0F,0x84,0xB0,0x01,0,0};
    // The complete body was validated before any presentation hooks installed.
    if (!MatchesProfileBytes(body+0xD9,gate,sizeof(gate),"inventory spell display gate")) return false;
    g_inventorySpellContinue = g_imageBase+body+0xE2;
    g_inventorySpellSkip = g_imageBase+body+0x292;
    return WriteOccupantBranch(g_imageBase+body+0xD9,
        reinterpret_cast<void*>(&InventorySpellGate),0xE9,sizeof(gate));
}
MajestyStringView HeroInfoString(const std::string& text) {
    return {text.c_str(), static_cast<std::uint32_t>(text.size()), static_cast<std::uint32_t>(text.size())};
}
void HeroRowMessage(void* list, unsigned message, unsigned row, const void* data) {
    using Message = void (__thiscall*)(void*, unsigned, unsigned, const void*);
    auto* table = *static_cast<std::uintptr_t**>(list);
    reinterpret_cast<Message>(table[0x9C/4])(list, message, row, data);
}
void __stdcall HeroRowTooltip(void* list, int index, const HeroInfoRecord* row) {
    if (!row || index < 0) return;
    auto text = HeroInfoString(row->tooltipText);
    HeroRowMessage(list, 0x62, static_cast<unsigned>(index), &text);
}
void SetHeroImage(void* image, unsigned stockSet, const HeroInfoRecord* row) {
    if (row) g_heroImageId(image, row->imageId);
    g_heroImageSet(image, row ? row->imageSet : stockSet);
}
void __fastcall HeroSpellImage(void* image, void*, unsigned stockSet) {
    SetHeroImage(image, stockSet, g_heroSpellRow);
}
void __fastcall HeroEffectImage(void* image, void*, unsigned stockSet) {
    SetHeroImage(image, stockSet, g_heroEffectRow);
}
const MajestyStringView* __stdcall SelectHeroSpell(
    unsigned actionId, const MajestyStringView* stockText) {
    g_heroSpellRow = g_runtimeFeatureRegistry.FindHeroInfo(1, actionId);
    if (!g_heroSpellRow) return stockText;
    // The naked adapter tail-calls stock after this helper returns, so the
    // view must outlive this stack frame. Registry text is immutable in-game;
    // the view is borrowed only until the synchronous stock append returns.
    g_heroSpellLabel = HeroInfoString(g_heroSpellRow->displayText);
    return &g_heroSpellLabel;
}
__declspec(naked) void HeroSpellAppendHook() {
    __asm {
        pushfd
        pushad
        // Original return, index, text follow the saved 36-byte frame.
        push dword ptr [esp+44]
        push dword ptr [edi+4]
        call SelectHeroSpell
        mov dword ptr [esp+44], eax
        popad
        popfd
        jmp dword ptr [g_heroAppend]
    }
}
__declspec(naked) void HeroSpellFinishHook() {
    __asm {
        pushfd
        pushad
        push dword ptr [g_heroSpellRow]
        push edi
        push ebp
        call HeroRowTooltip
        popad
        popfd
        jmp dword ptr [g_heroImageDtor]
    }
}
__declspec(naked) void HeroEffectFinishHook() {
    __asm {
        pushfd
        pushad
        push dword ptr [g_heroEffectRow]
        push ebp
        push ebx
        call HeroRowTooltip
        popad
        popfd
        jmp dword ptr [g_heroImageDtor]
    }
}
void __stdcall AppendHeroPassives(void* controller, void* list) {
    auto* unit = static_cast<unsigned char*>(g_heroSelected(controller));
    if (!unit) return;
    const auto subject = *reinterpret_cast<const std::uint32_t*>(unit+0x7C);
    const auto* row = g_runtimeFeatureRegistry.FindHeroInfo(3, subject);
    if (!row) return;
    const int level = ReadPackedAttributeValue(unit, 0x0B565041u);
    const auto* end = g_runtimeFeatureRegistry.heroInfoRows.data()+g_runtimeFeatureRegistry.heroInfoRows.size();
    for (; row != end && row->kind == 3 && row->subjectId == subject; ++row) {
        if (level < static_cast<int>(row->unlockLevel)) continue;
        const auto text = HeroInfoString(row->displayText);
        const int index = g_heroAppend(list, -1, &text);
        if (index < 0) continue;
        alignas(4) unsigned char image[0x6C] = {};
        g_heroImageCtor(image);
        g_heroImageType(image, 1);
        g_heroImageId(image, row->imageId);
        g_heroImageSet(image, row->imageSet);
        g_heroImageFrame(image, 0);
        *reinterpret_cast<std::uint32_t*>(image+0x1C) = 0;
        g_heroImageFlags(image, 9);
        HeroRowMessage(list, 0x24, static_cast<unsigned>(index), image);
        g_heroImageDtor(image);
        HeroRowTooltip(list, index, row);
    }
}
__declspec(naked) void HeroPassivesHook() {
    __asm {
        mov esi, dword ptr [esp+18h]
        pushfd
        pushad
        push ebp
        push esi
        call AppendHeroPassives
        popad
        popfd
        mov ecx, dword ptr [esi+24h]
        jmp dword ptr [g_heroPassiveResume]
    }
}
bool InstallHeroInfo() {
    // Run before the legacy enchantment adapter changes the audited switch.
    if (!ValidateHeroInfoProfile()) return false;
    g_heroAppend = reinterpret_cast<HeroAppend>(g_imageBase+ParityRva(ParitySite::HeroAppend));
    g_heroImageCtor = reinterpret_cast<HeroImageLife>(g_imageBase+ParityRva(ParitySite::ImageCtor));
    g_heroImageDtor = reinterpret_cast<HeroImageLife>(g_imageBase+ParityRva(ParitySite::ImageDtor));
    g_heroImageType = reinterpret_cast<HeroImageOp>(g_imageBase+ParityRva(ParitySite::ImageType));
    g_heroImageId = reinterpret_cast<HeroImageOp>(g_imageBase+ParityRva(ParitySite::ImageId));
    g_heroImageSet = reinterpret_cast<HeroImageOp>(g_imageBase+ParityRva(ParitySite::ImageSet));
    g_heroImageFrame = reinterpret_cast<HeroImageOp>(g_imageBase+ParityRva(ParitySite::ImageFrame));
    g_heroImageFlags = reinterpret_cast<HeroImageOp>(g_imageBase+ParityRva(ParitySite::ImageFlags));
    g_heroSelected = reinterpret_cast<HeroSelected>(g_imageBase+ParityRva(ParitySite::HeroSelected));
    g_heroPassiveResume = g_imageBase+ParityRva(ParitySite::HeroLearned)+0x483;
    // A failed install stops before Majesty resumes; never continue partially.
    return WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroLearned)+0x216, reinterpret_cast<void*>(&HeroSpellAppendHook), 0xE8) &&
        WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroLearned)+0x24B, reinterpret_cast<void*>(&HeroSpellImage), 0xE8) &&
        WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroLearned)+0x28D, reinterpret_cast<void*>(&HeroSpellFinishHook), 0xE8) &&
        WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroLearned)+0x47C, reinterpret_cast<void*>(&HeroPassivesHook), 0xE9, 7) &&
        WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroEffects)+0x7EF, reinterpret_cast<void*>(&HeroEffectImage), 0xE8) &&
        WriteOccupantBranch(g_imageBase+ParityRva(ParitySite::HeroEffects)+0x832, reinterpret_cast<void*>(&HeroEffectFinishHook), 0xE8);
}
