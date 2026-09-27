#pragma once
#include <cstdint>
#include "MajestyBuildId.h"
// Fixed audited addresses; no runtime scanning. See docs/runtime-feature-parity.md.
namespace MajestyFeatureParity {
enum class Site { EnumInit, EnumCall, EnumInsert, WeaponMap, ArmorMap, StringCtor, StringDtor, EquipmentCtor, EquipmentCall, NameInsert, IconInsert, ResourceAcquire, EquipmentDtor, MoveStep, MoveExecute, MoveVector, GetEffector, EffectorLookup, EffectorIterator, EffectorCollection, LinearEngine, HeroLearned, HeroEffects, HeroAppend, ImageCopy, TextDispatch, TextChannel, TextSet, TextParseCopy, TextParse, StringAssign, TooltipSet, RowDtor, HeroTooltip, ImageCtor, ImageDtor, ImageType, ImageId, ImageSet, ImageFrame, ImageFlags, HeroSelected, ResearchExecute, ResearchComplete, OrderGetter, RawSetter, ResearchSlot, BuildingSet, BuildingSetSlot, BuildingOwner, BuildingOwnerSlot, BuildingList, WorldRoot, WorldJoin };
enum class Feature { Equipment, Movement, HeroInfo, Research, ResearchVisual };
// Columns: beta2, default Steam, GOG. Unknown identities are rejected.
constexpr std::uintptr_t kRvas[][3] = {
    {0x21E40, 0x20E80, 0x210D0}, // EnumInit
    {0x21E15, 0x20E55, 0x210A5}, // EnumCall
    {0x1CAC30, 0x1B5C90, 0x1C9F80}, // EnumInsert
    {0x3DF4F0, 0x3C0A38, 0x3DF790}, // WeaponMap
    {0x3DF510, 0x3C0A58, 0x3DF7B0}, // ArmorMap
    {0x23A220, 0x227A80, 0x23C370}, // StringCtor
    {0x23A3D0, 0x227C30, 0x23C520}, // StringDtor
    {0x1038D0, 0x101720, 0x104060}, // EquipmentCtor
    {0x103DC9, 0x101C19, 0x104559}, // EquipmentCall
    {0x102B20, 0x100970, 0x1032B0}, // NameInsert
    {0x102BD0, 0x100A20, 0x103360}, // IconInsert
    {0x279A80, 0x264620, 0x278F70}, // ResourceAcquire
    {0x102FC0, 0x100E10, 0x103750}, // EquipmentDtor
    {0x1E3060, 0x1CDE80, 0x1E23B0}, // MoveStep
    {0x1E3120, 0x1CDF40, 0x1E2470}, // MoveExecute
    {0x1E2910, 0x1CD730, 0x1E1C60}, // MoveVector
    {0x1DE7B0, 0x1C95D0, 0x1DDB00}, // GetEffector
    {0x1BC6E0, 0x1A7730, 0x1BBA30}, // EffectorLookup
    {0x1BBE60, 0x1A6EB0, 0x1BB1B0}, // EffectorIterator
    {0x1BC320, 0x1A7370, 0x1BB670}, // EffectorCollection
    {0x364310, 0x34A240, 0x3631D0}, // LinearEngine
    {0xA3C00, 0xA3320, 0xA41B0}, // HeroLearned
    {0xA4110, 0xA3830, 0xA46C0}, // HeroEffects
    {0x272410, 0x25CFB0, 0x271900}, // HeroAppend
    {0x288030, 0x272BD0, 0x287520}, // ImageCopy
    {0x273A72, 0x25E612, 0x272F62}, // TextDispatch
    {0x2D0660, 0x2BB0D0, 0x2CFB50}, // TextChannel
    {0x2CD7E0, 0x2B8250, 0x2CCCD0}, // TextSet
    {0x285050, 0x26FBF0, 0x284540}, // TextParseCopy
    {0x284A40, 0x26F5E0, 0x283F30}, // TextParse
    {0x23AAF0, 0x228350, 0x23CC40}, // StringAssign
    {0x2CE250, 0x2B8CC0, 0x2CD740}, // TooltipSet
    {0x2CE0C0, 0x2B8B30, 0x2CD5B0}, // RowDtor
    {0xB4C00, 0xB4310, 0xB5200}, // HeroTooltip
    {0x287E50, 0x2729F0, 0x287340}, // ImageCtor
    {0x287770, 0x272310, 0x286C60}, // ImageDtor
    {0x2877A0, 0x272340, 0x286C90}, // ImageType
    {0x2877F0, 0x272390, 0x286CE0}, // ImageId
    {0x287F30, 0x272AD0, 0x287420}, // ImageSet
    {0x2873A0, 0x271F40, 0x286890}, // ImageFrame
    {0x287600, 0x2721A0, 0x286AF0}, // ImageFlags
    {0x68780, 0x67540, 0x686A0}, // HeroSelected
    {0xE02F0, 0xDFCE0, 0xE0A30}, // ResearchExecute
    {0xE0430, 0xDFE20, 0xE0B70}, // ResearchComplete
    {0x1DF010, 0x1C9E30, 0x1DE360}, // OrderGetter
    {0x1DE410, 0x1C9230, 0x1DD760}, // RawSetter
    {0x358E1C, 0x34011C, 0x357FD4}, // ResearchSlot
    {0x49950, 0x48A40, 0x49870}, // BuildingSet
    {0x3531E8, 0x33A128, 0x352230}, // BuildingSetSlot
    {0x1CF320, 0x1BA380, 0x1CE670}, // BuildingOwner
    {0x3530E4, 0x33A024, 0x35212C}, // BuildingOwnerSlot
    {0x1B9030, 0x1A4080, 0x1B8380}, // BuildingList
    {0x3E3FD4, 0x3C544C, 0x3E426C}, // WorldRoot
    {0x2ACA8, 0x290C9, 0x29EE8}, // WorldJoin
};
struct Range { Feature feature; Site site; unsigned size; std::uint32_t hashes[3]; };
constexpr Range kRanges[] = {
    {Feature::Equipment, Site::EnumInit, 0x5C9, {0xFF2EA130, 0x931DA3F3, 0x273FA51F}},
    {Feature::Equipment, Site::EnumInsert, 0x80, {0x8C701C23, 0x403E12D2, 0x6B63B83D}},
    {Feature::Equipment, Site::StringCtor, 0x60, {0x72B79531, 0x33D2650D, 0xA024BB6D}},
    {Feature::Equipment, Site::StringDtor, 0x25, {0x55704D82, 0xC1E3EA69, 0x1467E782}},
    {Feature::Equipment, Site::EquipmentCtor, 0x4B0, {0xC58A7935, 0x997BDE9C, 0x84880A32}},
    {Feature::Equipment, Site::NameInsert, 0xAF, {0xB6880EEC, 0x52EF7EA8, 0xEA6A23E4}},
    {Feature::Equipment, Site::IconInsert, 0xAF, {0xB6395FF3, 0x9EF6CFF7, 0x19520B5B}},
    {Feature::Equipment, Site::ResourceAcquire, 0x14, {0x6B08DB94, 0x0FEF6DB7, 0x8666D417}},
    {Feature::Equipment, Site::EquipmentDtor, 0x1D0, {0xCDC86C41, 0xE0EFEB1D, 0x44BFA516}},
    {Feature::Movement, Site::MoveStep, 0xB3, {0x32294614, 0xB6D5EA03, 0x73C75413}},
    {Feature::Movement, Site::MoveExecute, 0x1A0, {0x375BDD45, 0x1F713168, 0x6DEA9D45}},
    {Feature::Movement, Site::MoveVector, 0x3A, {0x4F386949, 0xCFD538CB, 0x3AD78117}},
    {Feature::Movement, Site::GetEffector, 0x15, {0x3AF7B250, 0x2550C00A, 0x3AF7B250}},
    {Feature::Movement, Site::EffectorLookup, 0x1F3, {0x785CF9D8, 0x73E3F7C0, 0x2DDD5A18}},
    {Feature::Movement, Site::EffectorIterator, 0xD1, {0x6F8C6967, 0x19E9A0BD, 0x290F9C0B}},
    {Feature::Movement, Site::EffectorCollection, 0x180, {0xC5719213, 0xD40DB0DD, 0x99D6B12F}},
    {Feature::Movement, Site::LinearEngine, 0x10, {0xB113BBEF, 0x7E9CE93C, 0x0AE35C97}},
    {Feature::HeroInfo, Site::HeroLearned, 0x510, {0x436F242B, 0x8EA38E4A, 0x96381380}},
    {Feature::HeroInfo, Site::HeroEffects, 0x910, {0xE1D159B5, 0x1B20A177, 0xB6D460C9}},
    {Feature::HeroInfo, Site::HeroAppend, 0x80, {0x5EA93191, 0x5EA93191, 0x5EA93191}},
    {Feature::HeroInfo, Site::ImageCopy, 0x240, {0xE4111E50, 0xEEC6DDF2, 0xFECFCC3D}},
    {Feature::HeroInfo, Site::TextDispatch, 0x49, {0xC7F425DE, 0xC7F425DE, 0xC7F425DE}},
    {Feature::HeroInfo, Site::TextChannel, 0x9F, {0x822927BF, 0x3979D1E3, 0xB45D53F0}},
    {Feature::HeroInfo, Site::TextSet, 0x80, {0x793158B2, 0x151A236F, 0x7180BF2B}},
    {Feature::HeroInfo, Site::TextParseCopy, 0xC6, {0x2AE088E8, 0x006FAE00, 0x484EB421}},
    {Feature::HeroInfo, Site::TextParse, 0xA0, {0x5C06EA1B, 0x60F4506C, 0xE2E3E70B}},
    {Feature::HeroInfo, Site::StringAssign, 0x80, {0x18E7D978, 0x14E292AF, 0x7D5B3798}},
    {Feature::HeroInfo, Site::TooltipSet, 0xE0, {0xCF9EA6EF, 0x79A8C60C, 0x68D7D19D}},
    {Feature::HeroInfo, Site::RowDtor, 0x90, {0xBC344AF3, 0xA983A1A4, 0x93E81411}},
    {Feature::HeroInfo, Site::HeroTooltip, 0x100, {0xD541CFCF, 0x6D29F4C2, 0x7752F3BB}},
    {Feature::HeroInfo, Site::HeroSelected, 0x13, {0x4E36D26F, 0x8A2DE680, 0x0F9D96AB}},
    {Feature::Research, Site::ResearchExecute, 0x131, {0x1ED81331, 0x1CC3FAA8, 0x31071BD4}},
    {Feature::Research, Site::ResearchComplete, 0x24C, {0x21D00DDF, 0x626F360E, 0xD5254490}},
    {Feature::Research, Site::OrderGetter, 0x1B, {0x43D252E8, 0x43D252E8, 0x43D252E8}},
    {Feature::Research, Site::RawSetter, 0x8, {0x7F4FC095, 0x7C33EB0A, 0xC91C52AE}},
    {Feature::ResearchVisual, Site::BuildingSet, 0x259, {0x79A54DEE, 0x78C25C90, 0x2C151195}},
    {Feature::ResearchVisual, Site::BuildingOwner, 0x25, {0xBA1A13F1, 0xBA1A13F1, 0xBA1A13F1}},
    {Feature::ResearchVisual, Site::BuildingList, 0x68, {0xA33A9A12, 0x2D67165C, 0x0A323716}},
    {Feature::ResearchVisual, Site::WorldJoin, 0x31, {0x2ADF73B1, 0x06663486, 0xF8CA0C27}},
};
inline int Index(MajestyBuildId id) {
    switch (id) { case MajestyBuildId::SteamBeta2: return 0; case MajestyBuildId::SteamPublic: return 1; case MajestyBuildId::Gog: return 2; default: return -1; }
}
inline std::uintptr_t Rva(MajestyBuildId id, Site site) {
    const int index = Index(id); return index < 0 ? 0 : kRvas[static_cast<unsigned>(site)][index];
}
inline bool Validate(std::uintptr_t base, MajestyBuildId id, Feature feature) {
    const int index = Index(id); if (!base || index < 0) return false;
    for (const auto& range : kRanges) {
        if (range.feature != feature) continue;
        const auto* bytes = reinterpret_cast<const unsigned char*>(base+Rva(id,range.site));
        std::uint32_t hash = 2166136261u;
        for (unsigned i=0;i<range.size;++i) hash=(hash^bytes[i])*16777619u;
        if (hash != range.hashes[index]) return false;
    }
    return true;
}
} // namespace MajestyFeatureParity
