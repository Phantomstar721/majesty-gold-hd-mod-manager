// AP78 presentation adapters. Stock owns list refresh, hit testing, hover,
// string/image copies and destruction. No game behavior or timer is added.
using HeroInfoRecord = MajestyRuntimeFeatures::HeroInfoRecord;
const HeroInfoRecord* g_heroSpellRow = nullptr;
const HeroInfoRecord* g_heroEffectRow = nullptr;
MajestyStringView g_heroEffectLabel = {};
using HeroAppend = int (__thiscall*)(void*, int, const char*);
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
    if (g_buildProfile != &kBeta2BuildProfile) return false;
    const auto hash = [](std::uintptr_t rva, std::size_t size) {
        std::uint32_t value = 2166136261u;
        const auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+rva);
        for (std::size_t i = 0; i < size; ++i) value = (value ^ bytes[i])*16777619u;
        return value;
    };
    return hash(0xA3C00, 0x510) == 0x436F242Bu &&
        hash(0xA4110, 0x910) == 0xE1D159B5u &&
        hash(0x272410, 0x80) == 0x5EA93191u &&
        hash(0x288030, 0x240) == 0xE4111E50u &&
        hash(0x2CE250, 0x80) == 0x08372856u &&
        hash(0xB4C00, 0x100) == 0xD541CFCFu;
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
const char* __stdcall SelectHeroSpell(unsigned actionId, const char* stockText) {
    g_heroSpellRow = g_runtimeFeatureRegistry.FindHeroInfo(1, actionId);
    return g_heroSpellRow ? g_heroSpellRow->displayText.c_str() : stockText;
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
        const int index = g_heroAppend(list, -1, row->displayText.c_str());
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
    g_heroAppend = reinterpret_cast<HeroAppend>(g_imageBase+0x272410);
    g_heroImageCtor = reinterpret_cast<HeroImageLife>(g_imageBase+0x287E50);
    g_heroImageDtor = reinterpret_cast<HeroImageLife>(g_imageBase+0x287770);
    g_heroImageType = reinterpret_cast<HeroImageOp>(g_imageBase+0x2877A0);
    g_heroImageId = reinterpret_cast<HeroImageOp>(g_imageBase+0x2877F0);
    g_heroImageSet = reinterpret_cast<HeroImageOp>(g_imageBase+0x287F30);
    g_heroImageFrame = reinterpret_cast<HeroImageOp>(g_imageBase+0x2873A0);
    g_heroImageFlags = reinterpret_cast<HeroImageOp>(g_imageBase+0x287600);
    g_heroSelected = reinterpret_cast<HeroSelected>(g_imageBase+0x68780);
    g_heroPassiveResume = g_imageBase+0xA4083;
    // A failed install stops before Majesty resumes; never continue partially.
    return WriteOccupantBranch(g_imageBase+0xA3E16, reinterpret_cast<void*>(&HeroSpellAppendHook), 0xE8) &&
        WriteOccupantBranch(g_imageBase+0xA3E4B, reinterpret_cast<void*>(&HeroSpellImage), 0xE8) &&
        WriteOccupantBranch(g_imageBase+0xA3E8D, reinterpret_cast<void*>(&HeroSpellFinishHook), 0xE8) &&
        WriteOccupantBranch(g_imageBase+0xA407C, reinterpret_cast<void*>(&HeroPassivesHook), 0xE9, 7) &&
        WriteOccupantBranch(g_imageBase+0xA48FF, reinterpret_cast<void*>(&HeroEffectImage), 0xE8) &&
        WriteOccupantBranch(g_imageBase+0xA4942, reinterpret_cast<void*>(&HeroEffectFinishHook), 0xE8);
}
