#include "StockControllerRegistry.h"
#include "StockBuildingControllerCatalog.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <map>
#include <set>
#include <tuple>
#include <utility>

namespace MajestyStockControllers {
namespace {

constexpr unsigned char kMagic[4] = {'M', 'M', 'C', 'R'};
constexpr std::size_t kHeaderBytes = 44;
// MMCR v2 clones the one sovereign executor family traced in the public
// 0x004DA020 and beta2 0x004DA630 dispatches.  Sp14 is the stock Lightning
// Storm executor used by that proven construction path.  A different executor
// family needs its own stock trace and a new bounded recipe version; an
// arbitrary FourCC must never be forwarded into the sovereign dispatcher.
constexpr std::uint32_t kProvenSovereignExecutorMode = 0x34317053u;  // Sp14

// AP99 constructs the same 26 stock research descriptors in both supported
// executables (public caller 0x004A7C20 -> 0x004A7AF0; beta2 caller
// 0x004A8510 -> 0x004A83E0): 1388-138D, 1392, 139C-139D, 13A6-13AB,
// 13B0-13B3, 13BA, and 13C5-13CA.  Its stock row iterators then discover
// controls only inside this literal half-open interval (public
// 0x004A8B13/1A; beta2 0x004A9403/0A).  Private AP99 command keys must stay
// outside the entire proven stock discovery namespace, including currently
// unused gaps.
constexpr std::uint32_t kFirstStockAp99ControlId = 0x00001388u;
constexpr std::uint32_t kAfterLastStockAp99ControlId = 0x000013ECu;

// MMCR v2 may clone only the stock template relationships that have been
// traced in both supported executables.  These constants mirror the
// manager-side validator so a tampered manager registry cannot postpone a bad
// template failure until the player opens the panel.
constexpr std::uint32_t kProvenTimedRageDescriptorTemplate = 0x00001140u;
constexpr std::uint32_t kProvenTimedRageLevelPriceTemplate = 0x0000113Eu;
constexpr std::uint32_t kProvenTimedRageLevel = 3u;
constexpr std::uint32_t kProvenTimedRagePrice = 1500u;
constexpr std::uint32_t kProvenRageVisualTemplate = 0x00001132u;
constexpr std::uint32_t kProvenRageVisualLevel = 3u;
constexpr std::uint32_t kProvenSovereignVisualTemplate = 0x00001133u;
constexpr std::uint32_t kProvenSovereignTargetTemplate = 0x00001132u;
constexpr std::uint32_t kProvenSovereignTargetMode = 0x33327053u;  // Sp23
constexpr std::uint32_t kProvenSovereignTargetLevel = 3u;

bool IsStockAp99ControlId(std::uint32_t value) {
    return value >= kFirstStockAp99ControlId &&
        value < kAfterLastStockAp99ControlId;
}

bool IsProvenStockAp99DescriptorControlId(std::uint32_t value) {
    // AP99 constructs exactly these 26 descriptors in both supported builds.
    // Gaps inside the stock row-discovery interval are reserved against
    // private actions but are not legal descriptor templates.
    switch (value) {
    case 0x00001388u:
    case 0x00001389u:
    case 0x0000138Au:
    case 0x0000138Bu:
    case 0x0000138Cu:
    case 0x0000138Du:
    case 0x00001392u:
    case 0x0000139Cu:
    case 0x0000139Du:
    case 0x000013A6u:
    case 0x000013A7u:
    case 0x000013A8u:
    case 0x000013A9u:
    case 0x000013AAu:
    case 0x000013ABu:
    case 0x000013B0u:
    case 0x000013B1u:
    case 0x000013B2u:
    case 0x000013B3u:
    case 0x000013BAu:
    case 0x000013C5u:
    case 0x000013C6u:
    case 0x000013C7u:
    case 0x000013C8u:
    case 0x000013C9u:
    case 0x000013CAu:
        return true;
    default:
        return false;
    }
}

void SetError(std::string* error, const char* message) {
    if (error != nullptr) {
        *error = message;
    }
}

bool Fail(std::string* error, const char* message) {
    SetError(error, message);
    return false;
}

bool IsDefinedCp1252Byte(unsigned char value) {
    return value != 0x81 && value != 0x8D && value != 0x8F &&
        value != 0x90 && value != 0x9D;
}

bool IsLogicalCharacter(unsigned char value, bool first) {
    if ((value >= 'A' && value <= 'Z') ||
        (value >= 'a' && value <= 'z')) {
        return true;
    }
    if (first) {
        return false;
    }
    return (value >= '0' && value <= '9') || value == '_' || value == '.' ||
        value == '-';
}

bool IsSymbolCharacter(unsigned char value, bool first) {
    if ((value >= 'A' && value <= 'Z') ||
        (value >= 'a' && value <= 'z') || value == '_') {
        return true;
    }
    return !first && value >= '0' && value <= '9';
}

std::string FoldAsciiCase(const std::string& value) {
    std::string folded = value;
    for (std::string::iterator character = folded.begin();
         character != folded.end(); ++character) {
        if (*character >= 'A' && *character <= 'Z') {
            *character = static_cast<char>(*character - 'A' + 'a');
        }
    }
    return folded;
}

bool IsPrintableFourCC(std::uint32_t value) {
    for (unsigned int index = 0; index < 4; ++index) {
        const unsigned char character = static_cast<unsigned char>(
            (value >> (index * 8)) & 0xFFu);
        if (character < 0x21 || character > 0x7E) {
            return false;
        }
    }
    return true;
}

bool HasFourCCPrefix(
    std::uint32_t value,
    unsigned char first,
    unsigned char second) {
    return static_cast<unsigned char>(value & 0xFFu) == first &&
        static_cast<unsigned char>((value >> 8) & 0xFFu) == second;
}

bool IsFamilyId(std::uint32_t value) {
    bool sawPadding = false;
    unsigned int characters = 0;
    for (unsigned int index = 0; index < 4; ++index) {
        const unsigned char character = static_cast<unsigned char>(
            (value >> (index * 8)) & 0xFFu);
        if (character == 0) {
            sawPadding = true;
        } else {
            if (sawPadding || character < 0x21 || character > 0x7E ||
                index == 3) {
                return false;
            }
            ++characters;
        }
    }
    return characters >= 1 && characters <= 3;
}

bool IsPackedAttributeId(std::uint32_t value) {
    bool sawPadding = false;
    unsigned int characters = 0;
    for (unsigned int index = 0; index < 4; ++index) {
        const unsigned char character = static_cast<unsigned char>(
            (value >> (index * 8)) & 0xFFu);
        if (character == 0) {
            sawPadding = true;
        } else {
            if (sawPadding || character < 0x21 || character > 0x7E) return false;
            ++characters;
        }
    }
    return characters >= 1 && characters <= 4;
}

bool FamilyPrefixesOverlap(std::uint32_t left, std::uint32_t right) {
    for (unsigned int index = 0; index < 3; ++index) {
        const unsigned char leftCharacter = static_cast<unsigned char>(
            (left >> (index * 8)) & 0xFFu);
        const unsigned char rightCharacter = static_cast<unsigned char>(
            (right >> (index * 8)) & 0xFFu);
        if (leftCharacter == 0 || rightCharacter == 0) {
            return true;
        }
        if (leftCharacter != rightCharacter) {
            return false;
        }
    }
    return true;
}

bool IsLevel(std::uint32_t value) {
    return value >= 1 && value <= 3;
}

bool IsNonnegativeGameValue(std::uint32_t value) {
    return value <= 0x7FFFFFFFu;
}

bool IsPositiveGameValue(std::uint32_t value) {
    return value >= 1 && value <= 0x7FFFFFFFu;
}

template <std::size_t N>
bool ControlsAreDistinct(const std::uint32_t (&values)[N]) {
    for (std::size_t left = 0; left < N; ++left) {
        for (std::size_t right = left + 1; right < N; ++right) {
            if (values[left] != 0 && values[left] == values[right]) {
                return false;
            }
        }
    }
    return true;
}

class Reader {
public:
    Reader(const unsigned char* bytes, std::size_t size)
        : bytes_(bytes), size_(size), cursor_(0) {}

    bool ReadBytes(std::size_t count, const unsigned char** value) {
        if (cursor_ > size_ || count > size_ - cursor_) {
            return false;
        }
        *value = bytes_ + cursor_;
        cursor_ += count;
        return true;
    }

    bool ReadU32(std::uint32_t* value) {
        const unsigned char* source = nullptr;
        if (!ReadBytes(4, &source)) {
            return false;
        }
        *value =
            static_cast<std::uint32_t>(source[0]) |
            (static_cast<std::uint32_t>(source[1]) << 8) |
            (static_cast<std::uint32_t>(source[2]) << 16) |
            (static_cast<std::uint32_t>(source[3]) << 24);
        return true;
    }

    bool ReadLogical(std::string* value) {
        return ReadIdentifier(value, kMaximumLogicalKeyBytes, false);
    }

    bool ReadSymbol(std::string* value) {
        return ReadIdentifier(value, kMaximumCallbackBytes, true);
    }

    bool ReadText(std::string* value) {
        std::uint32_t length = 0;
        if (!ReadU32(&length) || length == 0 ||
            length > kMaximumCompletionTextBytes) {
            return false;
        }
        const unsigned char* source = nullptr;
        if (!ReadBytes(length, &source)) {
            return false;
        }
        for (std::uint32_t index = 0; index < length; ++index) {
            if (source[index] == 0 || !IsDefinedCp1252Byte(source[index])) {
                return false;
            }
        }
        value->assign(reinterpret_cast<const char*>(source), length);
        return true;
    }

    std::size_t cursor() const { return cursor_; }

private:
    bool ReadIdentifier(
        std::string* value,
        std::size_t maximum,
        bool symbol) {
        std::uint32_t length = 0;
        if (!ReadU32(&length) || length == 0 || length > maximum) {
            return false;
        }
        const unsigned char* source = nullptr;
        if (!ReadBytes(length, &source)) {
            return false;
        }
        for (std::uint32_t index = 0; index < length; ++index) {
            const bool valid = symbol
                ? IsSymbolCharacter(source[index], index == 0)
                : IsLogicalCharacter(source[index], index == 0);
            if (!valid) {
                return false;
            }
        }
        value->assign(reinterpret_cast<const char*>(source), length);
        return true;
    }

    const unsigned char* bytes_;
    std::size_t size_;
    std::size_t cursor_;
};

bool ClaimControls(
    std::map<std::string, std::map<std::uint32_t, int> >* controls,
    const std::string& panel,
    const std::uint32_t* values,
    std::size_t count) {
    std::map<std::uint32_t, int>& claimed = (*controls)[panel];
    for (std::size_t index = 0; index < count; ++index) {
        if (values[index] == 0) {
            continue;
        }
        if (claimed.find(values[index]) != claimed.end()) {
            return false;
        }
        claimed[values[index]] = 1;
    }
    return true;
}

bool ValidateComposition(const Registry& registry, std::string* error) {
    std::map<std::string, const SecondaryPanelRecord*> panels;
    std::set<std::uint32_t> childDialogs;
    std::set<std::uint32_t> buildingFamilies;
    std::set<std::pair<std::uint32_t, std::uint32_t> > parentCommands;
    std::map<std::string, std::map<std::uint32_t, int> > controls;
    for (std::vector<SecondaryPanelRecord>::const_iterator item =
             registry.panels.begin(); item != registry.panels.end(); ++item) {
        for (std::set<std::uint32_t>::const_iterator family =
                 buildingFamilies.begin(); family != buildingFamilies.end();
                 ++family) {
            if (*family != item->buildingFamilyId &&
                FamilyPrefixesOverlap(*family, item->buildingFamilyId)) {
                return Fail(
                    error,
                    "MMCR secondary panel building-family prefixes overlap");
            }
        }
        if (!panels.insert(std::make_pair(item->panelKey, &*item)).second ||
            !childDialogs.insert(item->childDialogId).second ||
            !buildingFamilies.insert(item->buildingFamilyId).second ||
            !parentCommands.insert(std::make_pair(
                item->parentDialogId, item->openCommandId)).second) {
            return Fail(error, "MMCR secondary panel identity is duplicated");
        }
        controls[item->panelKey] = std::map<std::uint32_t, int>();
    }
    std::set<std::string> rewardPanelKeys;
    for (const auto& item : registry.rewardPanels) {
        if (panels.find(item.panelKey) != panels.end() ||
            !rewardPanelKeys.insert(item.panelKey).second ||
            !childDialogs.insert(item.childDialogId).second ||
            !parentCommands.insert(std::make_pair(
                item.parentDialogId, item.openCommandId)).second) {
            return Fail(error, "MMCR reward panel identity is duplicated");
        }
    }

    std::set<std::pair<std::string, std::string> > meters;
    // The packed AP22 value is stored under one global Description attribute
    // FourCC. Two otherwise unrelated panels cannot safely reinterpret the
    // same attribute as different manager-owned resources.
    std::set<std::uint32_t> meterAttributes;
    for (std::vector<ResourceMeterRecord>::const_iterator item =
             registry.meters.begin(); item != registry.meters.end(); ++item) {
        if (panels.find(item->panelKey) == panels.end() ||
            !meters.insert(std::make_pair(item->panelKey, item->resourceKey)).second ||
            !meterAttributes.insert(item->attributeId).second) {
            return Fail(error, "MMCR resource meter references are invalid");
        }
        const std::uint32_t ids[] = {
            item->labelControlId, item->countControlId, item->bindingControlId};
        if (!ClaimControls(&controls, item->panelKey, ids, 3)) {
            return Fail(error, "MMCR panel control ID is claimed twice");
        }
    }

    std::set<std::pair<std::string, std::string> > research;
    std::set<std::uint32_t> globalCommands;
    for (std::vector<ResearchRowRecord>::const_iterator item =
             registry.researchRows.begin(); item != registry.researchRows.end(); ++item) {
        if (panels.find(item->panelKey) == panels.end() ||
            !research.insert(std::make_pair(item->panelKey, item->recipeKey)).second ||
            !globalCommands.insert(item->actionControlId).second) {
            return Fail(error, "MMCR AP99 research identity is invalid");
        }
        const std::uint32_t ids[] = {
            item->actionControlId, item->priceControlId, item->progressControlId,
            item->activeDisplayControlId, item->iconControlId};
        if (!ClaimControls(&controls, item->panelKey, ids, 5)) {
            return Fail(error, "MMCR panel control ID is claimed twice");
        }
    }

    std::set<std::string> gatedPanels;
    for (std::vector<UpgradeGateRecord>::const_iterator item =
             registry.upgradeGates.begin(); item != registry.upgradeGates.end(); ++item) {
        std::map<std::string, const SecondaryPanelRecord*>::const_iterator panel =
            panels.find(item->panelKey);
        if (panel == panels.end() ||
            !gatedPanels.insert(item->panelKey).second) {
            return Fail(error, "MMCR AP17 upgrade gate ownership is invalid");
        }
        for (std::vector<UpgradeRequirement>::const_iterator requirement =
                 item->requirements.begin();
             requirement != item->requirements.end(); ++requirement) {
            if (research.find(std::make_pair(
                    item->panelKey, requirement->recipeKey)) == research.end()) {
                return Fail(error, "MMCR AP17 gate references unknown AP99 research");
            }
        }
    }

    std::set<std::pair<std::string, std::string> > actions;
    std::set<std::string> callbacks;
    for (std::vector<TimedRageActionRecord>::const_iterator item =
             registry.timedRageActions.begin();
         item != registry.timedRageActions.end(); ++item) {
        if (panels.find(item->panelKey) == panels.end() ||
            meters.find(std::make_pair(item->panelKey, item->resourceKey)) == meters.end() ||
            !actions.insert(std::make_pair(item->panelKey, item->actionKey)).second ||
            !callbacks.insert(FoldAsciiCase(item->callbackSymbol)).second ||
            !globalCommands.insert(item->actionControlId).second) {
            return Fail(error, "MMCR timed Rage action references are invalid");
        }
        const std::uint32_t ids[] = {
            item->actionControlId, item->iconControlId, item->priceControlId,
            item->progressControlId, item->activeDisplayControlId};
        if (!ClaimControls(&controls, item->panelKey, ids, 5)) {
            return Fail(error, "MMCR panel control ID is claimed twice");
        }
    }

    for (std::vector<RageCommandActionRecord>::const_iterator item =
             registry.rageCommandActions.begin();
         item != registry.rageCommandActions.end(); ++item) {
        if (panels.find(item->panelKey) == panels.end() ||
            meters.find(std::make_pair(item->panelKey, item->resourceKey)) == meters.end() ||
            !actions.insert(std::make_pair(item->panelKey, item->actionKey)).second ||
            !callbacks.insert(FoldAsciiCase(item->callbackSymbol)).second) {
            return Fail(error, "MMCR Rage command action references are invalid");
        }
        const std::uint32_t ids[] = {
            item->actionControlId, item->iconControlId, item->priceControlId};
        if (!ClaimControls(&controls, item->panelKey, ids, 3)) {
            return Fail(error, "MMCR panel control ID is claimed twice");
        }
    }

    std::set<std::uint32_t> privateModes;
    std::set<std::uint32_t> stockTargetModes;
    std::set<std::uint32_t> stockExecutorModes;
    std::set<std::uint32_t> privateUnits;
    for (std::vector<SovereignTargetActionRecord>::const_iterator item =
             registry.sovereignTargetActions.begin();
         item != registry.sovereignTargetActions.end(); ++item) {
        if (panels.find(item->panelKey) == panels.end() ||
            meters.find(std::make_pair(item->panelKey, item->resourceKey)) == meters.end() ||
            !actions.insert(std::make_pair(item->panelKey, item->actionKey)).second ||
            !globalCommands.insert(item->privateControlId).second ||
            !privateModes.insert(item->privateMode).second ||
            !privateUnits.insert(item->privateUnitId).second) {
            return Fail(error, "MMCR sovereign action references are invalid");
        }
        stockTargetModes.insert(item->stockTargetMode);
        stockExecutorModes.insert(item->stockExecutorMode);
        const std::uint32_t ids[] = {
            item->visualControlId, item->privateControlId,
            item->iconControlId, item->priceControlId};
        if (!ClaimControls(&controls, item->panelKey, ids, 4)) {
            return Fail(error, "MMCR panel control ID is claimed twice");
        }
    }
    for (std::set<std::uint32_t>::const_iterator mode = privateModes.begin();
         mode != privateModes.end(); ++mode) {
        if (stockTargetModes.find(*mode) != stockTargetModes.end() ||
            stockExecutorModes.find(*mode) != stockExecutorModes.end()) {
            return Fail(
                error,
                "MMCR private sovereign mode collides with a stock mode");
        }
    }
    std::set<std::string> rewardActionKeys;
    std::set<std::string> rewardActionPanels;
    std::set<std::uint32_t> rewardFlags;
    std::set<std::uint32_t> rewardCursors;
    for (const auto& item : registry.hostileMonsterFlags) {
        if (rewardPanelKeys.find(item.panelKey) == rewardPanelKeys.end() ||
            !rewardActionKeys.insert(item.actionKey).second ||
            !rewardActionPanels.insert(item.panelKey).second ||
            !privateModes.insert(item.privateMode).second ||
            !privateUnits.insert(item.privateFlagId).second ||
            !rewardFlags.insert(item.privateFlagId).second ||
            !rewardCursors.insert(item.cursorOrdinal).second) {
            return Fail(error, "MMCR hostile-monster flag identity is duplicated");
        }
    }
    if (rewardActionPanels != rewardPanelKeys) {
        return Fail(error, "MMCR reward panels require exactly one hostile-monster action");
    }
    std::set<std::string> occupantKeys;
    std::set<std::uint32_t> parentDialogs;
    for (const auto& item : registry.panels) parentDialogs.insert(item.parentDialogId);
    for (const auto& item : registry.rewardPanels) parentDialogs.insert(item.parentDialogId);
    for (const auto& item : registry.occupantActionPanels) parentDialogs.insert(item.parentDialogId);
    for (const auto& item : registry.occupantActionPanels) {
        if (panels.count(item.panelKey) || rewardPanelKeys.count(item.panelKey) ||
            !occupantKeys.insert(item.panelKey).second ||
            !childDialogs.insert(item.childDialogId).second ||
            !parentCommands.insert({item.parentDialogId, item.openCommandId}).second ||
            !callbacks.insert(FoldAsciiCase(item.costCallbackSymbol)).second ||
            !callbacks.insert(FoldAsciiCase(item.actionCallbackSymbol)).second) {
            return Fail(error, "MMCR occupant panel identity/callback is duplicated");
        }
    }
    std::set<std::string> toggleKeys;
    std::set<std::uint32_t> toggleParents;
    std::set<std::uint32_t> toggleCommands;
    std::map<std::uint32_t, std::uint32_t> parentBases;
    for (const auto& item : registry.panels) {
        parentBases[item.parentDialogId] = 0x30315041u;
    }
    for (const auto& item : registry.rewardPanels) {
        parentBases[item.parentDialogId] = 0x3930584Du;
    }
    for (const auto& item : registry.occupantActionPanels) {
        const auto prior = parentBases.find(item.parentDialogId);
        if (prior != parentBases.end() && prior->second != item.parentControllerBase) {
            return Fail(error, "MMCR parent controller bases conflict");
        }
        parentBases[item.parentDialogId] = item.parentControllerBase;
    }
    for (const auto& item : registry.buildingOpenToggles) {
        const auto prior = parentBases.find(item.parentDialogId);
        if (!toggleKeys.insert(item.toggleKey).second ||
            !toggleParents.insert(item.parentDialogId).second ||
            !toggleCommands.insert(item.openCommandId).second ||
            !toggleCommands.insert(item.closeCommandId).second ||
            parentCommands.count({item.parentDialogId, item.openCommandId}) ||
            parentCommands.count({item.parentDialogId, item.closeCommandId}) ||
            (prior != parentBases.end() &&
             prior->second != item.parentControllerBase)) {
            return Fail(error, "MMCR building toggle identity/command is duplicated");
        }
        parentDialogs.insert(item.parentDialogId);
        parentBases[item.parentDialogId] = item.parentControllerBase;
        parentCommands.insert({item.parentDialogId, item.openCommandId});
        parentCommands.insert({item.parentDialogId, item.closeCommandId});
    }
    std::set<std::string> listKeys;
    for (const auto& item : registry.liveAgentLists) {
        const auto validPrivateTextId = [](std::uint32_t value) {
            return value == 0 ||
                (value >= 0x60000000u && value < 0x70000000u);
        };
        std::set<std::uint32_t> privateTextIds;
        for (const auto value : {
                 item.rowTitleIntentId,
                 item.rowTextIntentId,
                 item.rowValueSuffixIntentId}) {
            if (value != 0 && !privateTextIds.insert(value).second) {
                return Fail(error, "MMCR live-agent-list private text ID is duplicated");
            }
        }
        for (const auto& variant : item.rowVariants) {
            for (const auto value : {
                     variant.rowTitleIntentId,
                     variant.rowTextIntentId}) {
                if (value != 0 && !privateTextIds.insert(value).second) {
                    return Fail(error, "MMCR live-agent-list private text ID is duplicated");
                }
            }
        }
        if (panels.count(item.panelKey) || rewardPanelKeys.count(item.panelKey) ||
            occupantKeys.count(item.panelKey) || !listKeys.insert(item.panelKey).second ||
            !childDialogs.insert(item.childDialogId).second ||
            !parentCommands.insert({item.parentDialogId, item.openCommandId}).second ||
            !callbacks.insert(FoldAsciiCase(item.rowCountCallbackSymbol)).second ||
            !callbacks.insert(FoldAsciiCase(item.rowAgentIdCallbackSymbol)).second ||
            !callbacks.insert(FoldAsciiCase(item.revisionCallbackSymbol)).second ||
            (item.hasRowVariants &&
             !callbacks.insert(FoldAsciiCase(item.rowVariantCallbackSymbol)).second) ||
            (item.hasRowValue &&
             !callbacks.insert(FoldAsciiCase(item.rowValueCallbackSymbol)).second) ||
            !callbacks.insert(FoldAsciiCase(item.actionCostCallbackSymbol)).second ||
            !callbacks.insert(FoldAsciiCase(item.actionCallbackSymbol)).second ||
            !validPrivateTextId(item.rowTitleIntentId) ||
            !validPrivateTextId(item.rowTextIntentId) ||
            !validPrivateTextId(item.rowValueSuffixIntentId) ||
            item.rowVariants.size() > kMaximumLiveAgentListVariants ||
            item.hasRowVariants != !item.rowVariants.empty() ||
            (!item.hasRowVariants && !item.rowVariantCallbackSymbol.empty()) ||
            (item.hasRowVariants && item.rowVariantCallbackSymbol.empty()) ||
            (item.hasRowVariants &&
             (item.rowTitleIntentId != 0 || item.rowTextIntentId != 0)) ||
            item.hasRowValue != (item.rowValueSuffixIntentId != 0) ||
            (!item.hasRowValue && !item.rowValueCallbackSymbol.empty()) ||
            (item.hasRowValue && item.rowValueCallbackSymbol.empty()))
            return Fail(error, "MMCR live-agent-list identity is duplicated or invalid");
        for (const auto& variant : item.rowVariants) {
            if ((!validPrivateTextId(variant.rowTitleIntentId) ||
                 !validPrivateTextId(variant.rowTextIntentId)) ||
                (variant.rowTitleIntentId == 0 && variant.rowTextIntentId == 0)) {
                return Fail(error, "MMCR live-agent-list row variant is invalid");
            }
        }
        parentDialogs.insert(item.parentDialogId);
        const auto prior = parentBases.find(item.parentDialogId);
        if (prior != parentBases.end() && prior->second != item.parentControllerBase)
            return Fail(error, "MMCR live-agent-list parent controller conflicts");
        parentBases[item.parentDialogId] = item.parentControllerBase;
    }
    for (const auto child : childDialogs) {
        if (parentDialogs.count(child)) return Fail(error, "MMCR child dialog collides with a parent dialog");
    }
    return true;
}

}  // namespace

void Registry::Clear() {
    liveAgentLists.clear();
    buildingOpenToggles.clear();
    occupantActionPanels.clear();
    panels.clear();
    meters.clear();
    researchRows.clear();
    upgradeGates.clear();
    timedRageActions.clear();
    rageCommandActions.clear();
    sovereignTargetActions.clear();
    rewardPanels.clear();
    hostileMonsterFlags.clear();
}

const SecondaryPanelRecord* Registry::FindPanelByKey(
    const std::string& panelKey) const {
    for (std::vector<SecondaryPanelRecord>::const_iterator item = panels.begin();
         item != panels.end(); ++item) {
        if (item->panelKey == panelKey) return &*item;
    }
    return nullptr;
}

const SecondaryPanelRecord* Registry::FindPanelByChildDialog(
    std::uint32_t childDialogId) const {
    for (std::vector<SecondaryPanelRecord>::const_iterator item = panels.begin();
         item != panels.end(); ++item) {
        if (item->childDialogId == childDialogId) return &*item;
    }
    return nullptr;
}

const SecondaryPanelRecord* Registry::FindPanelByParentDialog(
    std::uint32_t parentDialogId) const {
    for (std::vector<SecondaryPanelRecord>::const_iterator item = panels.begin();
         item != panels.end(); ++item) {
        if (item->parentDialogId == parentDialogId) return &*item;
    }
    return nullptr;
}

const SecondaryPanelRecord* Registry::FindPanelByParentCommand(
    std::uint32_t parentDialogId,
    std::uint32_t commandId) const {
    for (std::vector<SecondaryPanelRecord>::const_iterator item = panels.begin();
         item != panels.end(); ++item) {
        if (item->parentDialogId == parentDialogId &&
            item->openCommandId == commandId) return &*item;
    }
    return nullptr;
}

const ResourceMeterRecord* Registry::FindMeter(
    const std::string& panelKey,
    const std::string& resourceKey) const {
    for (std::vector<ResourceMeterRecord>::const_iterator item = meters.begin();
         item != meters.end(); ++item) {
        if (item->panelKey == panelKey && item->resourceKey == resourceKey) return &*item;
    }
    return nullptr;
}

const ResearchRowRecord* Registry::FindResearchByCommand(
    std::uint32_t commandId) const {
    for (std::vector<ResearchRowRecord>::const_iterator item = researchRows.begin();
         item != researchRows.end(); ++item) {
        if (item->actionControlId == commandId) return &*item;
    }
    return nullptr;
}

const TimedRageActionRecord* Registry::FindTimedRageByCommand(
    std::uint32_t commandId) const {
    for (std::vector<TimedRageActionRecord>::const_iterator item =
             timedRageActions.begin(); item != timedRageActions.end(); ++item) {
        if (item->actionControlId == commandId) return &*item;
    }
    return nullptr;
}

const RageCommandActionRecord* Registry::FindRageCommand(
    const std::string& panelKey,
    std::uint32_t commandId) const {
    for (std::vector<RageCommandActionRecord>::const_iterator item =
             rageCommandActions.begin(); item != rageCommandActions.end(); ++item) {
        if (item->panelKey == panelKey && item->actionControlId == commandId) return &*item;
    }
    return nullptr;
}

const SovereignTargetActionRecord* Registry::FindSovereignByPrivateMode(
    std::uint32_t privateMode) const {
    for (std::vector<SovereignTargetActionRecord>::const_iterator item =
             sovereignTargetActions.begin();
         item != sovereignTargetActions.end(); ++item) {
        if (item->privateMode == privateMode) return &*item;
    }
    return nullptr;
}

const RewardPanelRecord* Registry::FindRewardPanelByKey(
    const std::string& panelKey) const {
    for (const auto& item : rewardPanels) if (item.panelKey == panelKey) return &item;
    return nullptr;
}

const RewardPanelRecord* Registry::FindRewardPanelByChildDialog(
    std::uint32_t childDialogId) const {
    for (const auto& item : rewardPanels) if (item.childDialogId == childDialogId) return &item;
    return nullptr;
}

const RewardPanelRecord* Registry::FindRewardPanelByParentDialog(
    std::uint32_t parentDialogId) const {
    for (const auto& item : rewardPanels) if (item.parentDialogId == parentDialogId) return &item;
    return nullptr;
}

const RewardPanelRecord* Registry::FindRewardPanelByParentCommand(
    std::uint32_t parentDialogId, std::uint32_t commandId) const {
    for (const auto& item : rewardPanels) {
        if (item.parentDialogId == parentDialogId && item.openCommandId == commandId) return &item;
    }
    return nullptr;
}

const HostileMonsterFlagRecord* Registry::FindHostileMonsterFlagByPanel(
    const std::string& panelKey) const {
    for (const auto& item : hostileMonsterFlags) if (item.panelKey == panelKey) return &item;
    return nullptr;
}

const HostileMonsterFlagRecord* Registry::FindHostileMonsterFlagByMode(
    std::uint32_t privateMode) const {
    for (const auto& item : hostileMonsterFlags) if (item.privateMode == privateMode) return &item;
    return nullptr;
}

const OccupantActionPanelRecord* Registry::FindOccupantPanelByChild(std::uint32_t id) const {
    for (const auto& item : occupantActionPanels) if (item.childDialogId == id) return &item;
    return nullptr;
}

const OccupantActionPanelRecord* Registry::FindOccupantPanelByParent(std::uint32_t id) const {
    for (const auto& item : occupantActionPanels) if (item.parentDialogId == id) return &item;
    return nullptr;
}

const OccupantActionPanelRecord* Registry::FindOccupantPanelByCommand(std::uint32_t id) const {
    for (const auto& item : occupantActionPanels) if (item.actionCommandId == id) return &item;
    return nullptr;
}

const LiveAgentListRecord* Registry::FindLiveAgentListByChild(std::uint32_t id) const {
    for (const auto& item : liveAgentLists) {
        if (item.childDialogId == id) return &item;
    }
    return nullptr;
}

const LiveAgentListRecord* Registry::FindLiveAgentListByParent(std::uint32_t id) const {
    for (const auto& item : liveAgentLists) {
        if (item.parentDialogId == id) return &item;
    }
    return nullptr;
}

const LiveAgentListRecord* Registry::FindLiveAgentListByCommand(std::uint32_t id) const {
    for (const auto& item : liveAgentLists) {
        if (item.actionCommandId == id) return &item;
    }
    return nullptr;
}

const BuildingOpenToggleRecord* Registry::FindBuildingOpenToggleByParent(
    std::uint32_t id) const {
    for (const auto& item : buildingOpenToggles) {
        if (item.parentDialogId == id) return &item;
    }
    return nullptr;
}

bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    Registry* registry,
    std::string* error) {
    if (registry == nullptr || bytes == nullptr) {
        return Fail(error, "MMCR registry buffer or output is null");
    }
    registry->Clear();
    if (error != nullptr) error->clear();
    if (size < kHeaderBytes || size > kMaximumRegistryBytes) {
        return Fail(error, "MMCR registry size is outside supported bounds");
    }
    Reader reader(bytes, size);
    const unsigned char* magic = nullptr;
    if (!reader.ReadBytes(4, &magic) || std::memcmp(magic, kMagic, 4) != 0) {
        return Fail(error, "MMCR registry magic is invalid");
    }
    std::uint32_t version = 0;
    std::uint32_t counts[12] = {};
    if (!reader.ReadU32(&version)) return Fail(error, "MMCR header is truncated");
    if (version < 2 || version > kRegistryVersion) return Fail(error, "MMCR version is unsupported");
    const std::size_t countSize = version >= 5 ? 12u : version == 4 ? 11u : version == 3 ? 10u : 9u;
    for (std::size_t index = 0; index < countSize; ++index) {
        if (!reader.ReadU32(&counts[index])) return Fail(error, "MMCR header is truncated");
    }
    if (version == 3 && counts[9] == 0) return Fail(error, "MMCR v3 without occupant panels is noncanonical");
    if (version == 4 && counts[10] == 0) return Fail(error, "MMCR v4 without building toggles is noncanonical");
    if (version == 5) return Fail(error, "MMCR v5 fixed-row quest boards are unsupported; rebuild with the current Manager");
    if (version == 6) return Fail(error, "MMCR v6 quest rows lack private display callbacks; rebuild with the current Manager");
    if (version == 7) return Fail(error, "MMCR v7 quest rows use unsupported GPL agent/boolean return contracts; rebuild with the current Manager");
    if (version == 8) return Fail(error, "MMCR v8 quest rows use unsupported GPL string return contracts; rebuild with the current Manager");
    if (version == 9) return Fail(error, "MMCR v9 quest boards contain a non-stock duplicate Refresh row; rebuild with the current Manager");
    if (version == 10) return Fail(error, "MMCR v10 one-row quest lists are unsupported; rebuild with the current Manager");
    if (version == 11) return Fail(error, "MMCR v11 live-agent lists lack per-row static variants; rebuild with the current Manager");
    if (version == 12) return Fail(error, "MMCR v12 live-agent lists lack the post-action panel policy; rebuild with the current Manager");
    if (version == 13) return Fail(error, "MMCR v13 live-agent lists lack the row-focus policy; rebuild with the current Manager");
    if ((version == 14 || version == 15 || version == 16) && counts[11] == 0)
        return Fail(error, "MMCR live-agent-list version without live-agent lists is noncanonical");
    std::uint64_t total = 0;
    for (std::size_t index = 0; index < 12; ++index) total += counts[index];
    if (total > kMaximumRecordCount ||
        static_cast<std::uint64_t>(counts[0]) + counts[7] + counts[9] + counts[11] > kMaximumPanelCount) {
        return Fail(error, "MMCR record count is outside supported bounds");
    }

    Registry parsed;
    parsed.panels.reserve(counts[0]);
    parsed.meters.reserve(counts[1]);
    parsed.researchRows.reserve(counts[2]);
    parsed.upgradeGates.reserve(counts[3]);
    parsed.timedRageActions.reserve(counts[4]);
    parsed.rageCommandActions.reserve(counts[5]);
    parsed.sovereignTargetActions.reserve(counts[6]);
    parsed.rewardPanels.reserve(counts[7]);
    parsed.hostileMonsterFlags.reserve(counts[8]);
    parsed.occupantActionPanels.reserve(counts[9]);
    parsed.buildingOpenToggles.reserve(counts[10]);
    parsed.liveAgentLists.reserve(counts[11]);

    for (std::uint32_t index = 0; index < counts[0]; ++index) {
        SecondaryPanelRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadU32(&item.parentDialogId) ||
            !reader.ReadU32(&item.childDialogId) ||
            !reader.ReadU32(&item.buildingFamilyId) ||
            !reader.ReadU32(&item.openCommandId) ||
            !IsPrintableFourCC(item.parentDialogId) ||
            !IsPrintableFourCC(item.childDialogId) ||
            !IsFamilyId(item.buildingFamilyId) || item.openCommandId == 0 ||
            (!parsed.panels.empty() && parsed.panels.back().panelKey >= item.panelKey)) {
            return Fail(error, "MMCR secondary panel record is invalid or noncanonical");
        }
        parsed.panels.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[1]; ++index) {
        ResourceMeterRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.resourceKey) ||
            !reader.ReadU32(&item.attributeId) ||
            !reader.ReadU32(&item.labelControlId) ||
            !reader.ReadU32(&item.countControlId) ||
            !reader.ReadU32(&item.bindingControlId)) {
            return Fail(error, "MMCR resource meter record is truncated");
        }
        const std::uint32_t ids[] = {
            item.labelControlId, item.countControlId, item.bindingControlId};
        if (!IsPrintableFourCC(item.attributeId) ||
            !ControlsAreDistinct(ids) ||
            (!parsed.meters.empty() &&
             std::tie(parsed.meters.back().panelKey, parsed.meters.back().resourceKey) >=
             std::tie(item.panelKey, item.resourceKey))) {
            return Fail(error, "MMCR resource meter record is invalid or noncanonical");
        }
        parsed.meters.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[2]; ++index) {
        ResearchRowRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.recipeKey) ||
            !reader.ReadU32(&item.actionControlId) ||
            !reader.ReadU32(&item.descriptorTemplateControlId) ||
            !reader.ReadU32(&item.completionTemplateControlId) ||
            !reader.ReadU32(&item.requiredLevel) ||
            !reader.ReadU32(&item.price) ||
            !reader.ReadU32(&item.priceControlId) ||
            !reader.ReadU32(&item.progressControlId) ||
            !reader.ReadU32(&item.activeDisplayControlId) ||
            !reader.ReadU32(&item.iconControlId) ||
            !reader.ReadText(&item.completionText)) {
            return Fail(error, "MMCR AP99 research row is truncated or invalid");
        }
        const std::uint32_t ids[] = {
            item.actionControlId, item.priceControlId, item.progressControlId,
            item.activeDisplayControlId, item.iconControlId};
        if (item.actionControlId == 0 ||
            IsStockAp99ControlId(item.actionControlId) ||
            !IsProvenStockAp99DescriptorControlId(
                item.descriptorTemplateControlId) ||
            !IsProvenStockAp99DescriptorControlId(
                item.completionTemplateControlId) ||
            !IsLevel(item.requiredLevel) ||
            !IsNonnegativeGameValue(item.price) || item.priceControlId == 0 ||
            item.progressControlId == 0 || item.activeDisplayControlId == 0 ||
            !ControlsAreDistinct(ids) ||
            (!parsed.researchRows.empty() &&
             std::tie(parsed.researchRows.back().panelKey,
                      parsed.researchRows.back().recipeKey) >=
             std::tie(item.panelKey, item.recipeKey))) {
            return Fail(
                error,
                "MMCR AP99 research row is invalid, stock-owned, or noncanonical");
        }
        parsed.researchRows.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[3]; ++index) {
        UpgradeGateRecord item = {};
        std::uint32_t requirementCount = 0;
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadU32(&item.upgradeControlId) ||
            !reader.ReadU32(&item.upgradePriceControlId) ||
            !reader.ReadU32(&requirementCount) ||
            requirementCount < 1 || requirementCount > 3 ||
            (item.upgradeControlId != 0 &&
             item.upgradeControlId == item.upgradePriceControlId) ||
            (!parsed.upgradeGates.empty() &&
             parsed.upgradeGates.back().panelKey >= item.panelKey)) {
            return Fail(error, "MMCR AP17 upgrade gate is invalid or noncanonical");
        }
        std::uint32_t previousLevel = 0;
        std::set<std::string> recipes;
        for (std::uint32_t requirement = 0; requirement < requirementCount; ++requirement) {
            UpgradeRequirement value = {};
            if (!reader.ReadU32(&value.buildingLevel) ||
                !reader.ReadLogical(&value.recipeKey) ||
                !IsLevel(value.buildingLevel) || value.buildingLevel <= previousLevel ||
                !recipes.insert(value.recipeKey).second) {
                return Fail(error, "MMCR AP17 requirement is invalid or noncanonical");
            }
            previousLevel = value.buildingLevel;
            item.requirements.push_back(std::move(value));
        }
        parsed.upgradeGates.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[4]; ++index) {
        TimedRageActionRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.actionKey) ||
            !reader.ReadU32(&item.actionControlId) ||
            !reader.ReadU32(&item.descriptorTemplateControlId) ||
            !reader.ReadU32(&item.levelPriceTemplateControlId) ||
            !reader.ReadU32(&item.requiredLevel) ||
            !reader.ReadU32(&item.goldCost) ||
            !reader.ReadLogical(&item.resourceKey) ||
            !reader.ReadU32(&item.resourceCost) ||
            !reader.ReadSymbol(&item.callbackSymbol) ||
            !reader.ReadU32(&item.durationMs) ||
            !reader.ReadU32(&item.iconControlId) ||
            !reader.ReadU32(&item.priceControlId) ||
            !reader.ReadU32(&item.progressControlId) ||
            !reader.ReadU32(&item.activeDisplayControlId)) {
            return Fail(error, "MMCR timed Rage action is truncated or invalid");
        }
        const std::uint32_t ids[] = {
            item.actionControlId, item.iconControlId, item.priceControlId,
            item.progressControlId, item.activeDisplayControlId};
        if (item.descriptorTemplateControlId !=
                kProvenTimedRageDescriptorTemplate ||
            item.levelPriceTemplateControlId !=
                kProvenTimedRageLevelPriceTemplate ||
            item.requiredLevel != kProvenTimedRageLevel ||
            item.goldCost != kProvenTimedRagePrice ||
            !IsNonnegativeGameValue(item.goldCost) ||
            !IsPositiveGameValue(item.resourceCost) || item.durationMs < 1 ||
            item.durationMs > 86400000u || !ControlsAreDistinct(ids) ||
            (!parsed.timedRageActions.empty() &&
             std::tie(parsed.timedRageActions.back().panelKey,
                      parsed.timedRageActions.back().actionKey) >=
             std::tie(item.panelKey, item.actionKey))) {
            return Fail(error, "MMCR timed Rage action is invalid or noncanonical");
        }
        parsed.timedRageActions.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[5]; ++index) {
        RageCommandActionRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.actionKey) ||
            !reader.ReadU32(&item.actionControlId) ||
            !reader.ReadU32(&item.visualTemplateControlId) ||
            !reader.ReadU32(&item.completionTemplateResearchControlId) ||
            !reader.ReadU32(&item.requiredLevel) ||
            !reader.ReadLogical(&item.resourceKey) ||
            !reader.ReadU32(&item.resourceCost) ||
            !reader.ReadSymbol(&item.callbackSymbol) ||
            !reader.ReadU32(&item.iconControlId) ||
            !reader.ReadU32(&item.priceControlId)) {
            return Fail(error, "MMCR Rage command action is truncated or invalid");
        }
        const std::uint32_t ids[] = {
            item.actionControlId, item.iconControlId, item.priceControlId};
        if (item.visualTemplateControlId != kProvenRageVisualTemplate ||
            !IsProvenStockAp99DescriptorControlId(
                item.completionTemplateResearchControlId) ||
            item.requiredLevel != kProvenRageVisualLevel ||
            !IsPositiveGameValue(item.resourceCost) ||
            !ControlsAreDistinct(ids) ||
            (!parsed.rageCommandActions.empty() &&
             std::tie(parsed.rageCommandActions.back().panelKey,
                      parsed.rageCommandActions.back().actionKey) >=
             std::tie(item.panelKey, item.actionKey))) {
            return Fail(error, "MMCR Rage command action is invalid or noncanonical");
        }
        parsed.rageCommandActions.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[6]; ++index) {
        SovereignTargetActionRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.actionKey) ||
            !reader.ReadU32(&item.visualControlId) ||
            !reader.ReadU32(&item.privateControlId) ||
            !reader.ReadU32(&item.visualTemplateControlId) ||
            !reader.ReadU32(&item.targetTemplateControlId) ||
            !reader.ReadU32(&item.stockTargetMode) ||
            !reader.ReadU32(&item.stockExecutorMode) ||
            !reader.ReadU32(&item.privateMode) ||
            !reader.ReadU32(&item.privateUnitId) ||
            !reader.ReadU32(&item.cursorOrdinal) ||
            !reader.ReadU32(&item.requiredLevel) ||
            !reader.ReadLogical(&item.resourceKey) ||
            !reader.ReadU32(&item.resourceCost) ||
            !reader.ReadU32(&item.iconControlId) ||
            !reader.ReadU32(&item.priceControlId)) {
            return Fail(error, "MMCR sovereign action is truncated or invalid");
        }
        const std::uint32_t ids[] = {
            item.visualControlId, item.privateControlId,
            item.iconControlId, item.priceControlId};
        if (item.visualTemplateControlId != kProvenSovereignVisualTemplate ||
            item.targetTemplateControlId != kProvenSovereignTargetTemplate ||
            !IsPrintableFourCC(item.stockTargetMode) ||
            !IsPrintableFourCC(item.stockExecutorMode) ||
            !IsPrintableFourCC(item.privateMode) ||
            !IsPrintableFourCC(item.privateUnitId) ||
            item.stockTargetMode != kProvenSovereignTargetMode ||
            item.stockExecutorMode != kProvenSovereignExecutorMode ||
            HasFourCCPrefix(item.privateMode, 'S', 'p') ||
            item.privateMode == item.stockTargetMode || item.cursorOrdinal > 255 ||
            item.requiredLevel != kProvenSovereignTargetLevel ||
            !IsPositiveGameValue(item.resourceCost) ||
            !ControlsAreDistinct(ids) ||
            (!parsed.sovereignTargetActions.empty() &&
             std::tie(parsed.sovereignTargetActions.back().panelKey,
                      parsed.sovereignTargetActions.back().actionKey) >=
             std::tie(item.panelKey, item.actionKey))) {
            return Fail(error, "MMCR sovereign action is invalid or noncanonical");
        }
        parsed.sovereignTargetActions.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[7]; ++index) {
        RewardPanelRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadU32(&item.parentDialogId) ||
            !reader.ReadU32(&item.childDialogId) ||
            !reader.ReadU32(&item.openCommandId) ||
            !IsPrintableFourCC(item.parentDialogId) ||
            !IsPrintableFourCC(item.childDialogId) || item.openCommandId == 0 ||
            (!parsed.rewardPanels.empty() &&
             parsed.rewardPanels.back().panelKey >= item.panelKey)) {
            return Fail(error, "MMCR reward panel is invalid or noncanonical");
        }
        parsed.rewardPanels.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[8]; ++index) {
        HostileMonsterFlagRecord item = {};
        std::uint32_t hasGate = 0;
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadLogical(&item.actionKey) ||
            !reader.ReadU32(&item.privateMode) ||
            !reader.ReadU32(&item.privateFlagId) ||
            !reader.ReadSymbol(&item.flagPrototypeName) ||
            !reader.ReadU32(&item.cursorOrdinal) ||
            !reader.ReadU32(&hasGate) || hasGate > 1) {
            return Fail(error, "MMCR hostile-monster flag is truncated or invalid");
        }
        item.hasAvailabilityGate = hasGate != 0;
        if (item.hasAvailabilityGate &&
            (!reader.ReadU32(&item.availabilityAttributeId) ||
             !reader.ReadText(&item.unavailableAlertText))) {
            return Fail(error, "MMCR hostile-monster availability gate is truncated");
        }
        if (!IsPrintableFourCC(item.privateMode) ||
            !IsPrintableFourCC(item.privateFlagId) ||
            item.privateMode != item.privateFlagId ||
            item.privateMode == 0x30306C46u ||
            item.privateFlagId == 0x32415241u ||
            item.cursorOrdinal < 32 || item.cursorOrdinal > 255 ||
            (item.hasAvailabilityGate &&
             !IsPackedAttributeId(item.availabilityAttributeId)) ||
            (!parsed.hostileMonsterFlags.empty() &&
             std::tie(parsed.hostileMonsterFlags.back().panelKey,
                      parsed.hostileMonsterFlags.back().actionKey) >=
             std::tie(item.panelKey, item.actionKey))) {
            return Fail(error, "MMCR hostile-monster flag is invalid or noncanonical");
        }
        parsed.hostileMonsterFlags.push_back(std::move(item));
    }

    for (std::uint32_t index = 0; index < counts[9]; ++index) {
        OccupantActionPanelRecord item = {};
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadU32(&item.parentDialogId) ||
            !reader.ReadU32(&item.childDialogId) ||
            !reader.ReadU32(&item.openCommandId) ||
            !reader.ReadU32(&item.actionCommandId) ||
            !reader.ReadSymbol(&item.costCallbackSymbol) ||
            !reader.ReadSymbol(&item.actionCallbackSymbol) ||
            !reader.ReadU32(&item.parentControllerBase) ||
            !MajestyStockBuildingControllers::IsSupported(
                item.parentControllerBase) ||
            !IsPrintableFourCC(item.parentDialogId) ||
            !IsPrintableFourCC(item.childDialogId) || item.openCommandId == 0 ||
            item.actionCommandId != 0x10000u + index ||
            (!parsed.occupantActionPanels.empty() &&
             parsed.occupantActionPanels.back().panelKey >= item.panelKey)) {
            return Fail(error, "MMCR occupant panel is invalid or noncanonical");
        }
        parsed.occupantActionPanels.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[10]; ++index) {
        BuildingOpenToggleRecord item = {};
        if (!reader.ReadLogical(&item.toggleKey) ||
            !reader.ReadU32(&item.parentDialogId) ||
            !reader.ReadU32(&item.openCommandId) ||
            !reader.ReadU32(&item.closeCommandId) ||
            !reader.ReadU32(&item.parentControllerBase) ||
            !IsPrintableFourCC(item.parentDialogId) ||
            item.openCommandId == 0 || item.closeCommandId == 0 ||
            item.openCommandId == item.closeCommandId ||
            item.openCommandId == 0x22ABu || item.openCommandId == 0x22ACu ||
            item.closeCommandId == 0x22ABu || item.closeCommandId == 0x22ACu ||
            !MajestyStockBuildingControllers::IsSupported(
                item.parentControllerBase) ||
            (!parsed.buildingOpenToggles.empty() &&
             parsed.buildingOpenToggles.back().toggleKey >= item.toggleKey)) {
            return Fail(error, "MMCR building open toggle is invalid or noncanonical");
        }
        parsed.buildingOpenToggles.push_back(std::move(item));
    }
    for (std::uint32_t index = 0; index < counts[11]; ++index) {
        LiveAgentListRecord item = {};
        std::uint32_t hasRowVariants = 0;
        std::uint32_t hasRowValue = 0;
        std::uint32_t stayOnPanelAfterAction = 0;
        std::uint32_t focusSelectedRowOnClick = 0;
        std::uint32_t actionUsesParent = 0;
        std::uint32_t dataRecordRows = 0;
        if (!reader.ReadLogical(&item.panelKey) ||
            !reader.ReadU32(&item.parentDialogId) || !reader.ReadU32(&item.childDialogId) ||
            !reader.ReadU32(&item.openCommandId))
            return Fail(error, "MMCR live-agent-list header is truncated");
        if (!reader.ReadU32(&item.actionCommandId))
            return Fail(error, "MMCR live-agent-list action command is truncated");
        if (!reader.ReadSymbol(&item.rowCountCallbackSymbol) ||
            !reader.ReadSymbol(&item.rowAgentIdCallbackSymbol) ||
            !reader.ReadSymbol(&item.revisionCallbackSymbol) ||
            !reader.ReadU32(&item.rowTitleIntentId) ||
            !reader.ReadU32(&item.rowTextIntentId) ||
            !reader.ReadU32(&hasRowVariants))
            return Fail(error, "MMCR live-agent-list presentation is truncated");
        if (hasRowVariants > 1)
            return Fail(error, "MMCR live-agent-list variant marker is invalid");
        item.hasRowVariants = hasRowVariants != 0;
        if (item.hasRowVariants) {
            std::uint32_t variantCount = 0;
            if (!reader.ReadSymbol(&item.rowVariantCallbackSymbol) ||
                !reader.ReadU32(&variantCount) || variantCount == 0 ||
                variantCount > kMaximumLiveAgentListVariants)
                return Fail(error, "MMCR live-agent-list variants are truncated or invalid");
            item.rowVariants.reserve(variantCount);
            for (std::uint32_t variantIndex = 0;
                 variantIndex < variantCount; ++variantIndex) {
                LiveAgentListRowVariant variant = {};
                if (!reader.ReadU32(&variant.rowTitleIntentId) ||
                    !reader.ReadU32(&variant.rowTextIntentId))
                    return Fail(error, "MMCR live-agent-list variants are truncated");
                item.rowVariants.push_back(variant);
            }
        }
        if (!reader.ReadU32(&hasRowValue))
            return Fail(error, "MMCR live-agent-list value marker is truncated");
        if (hasRowValue > 1)
            return Fail(error, "MMCR live-agent-list value marker is invalid");
        item.hasRowValue = hasRowValue != 0;
        if (item.hasRowValue &&
            (!reader.ReadSymbol(&item.rowValueCallbackSymbol) ||
             !reader.ReadU32(&item.rowValueSuffixIntentId)))
            return Fail(error, "MMCR live-agent-list value is truncated");
        if (!reader.ReadSymbol(&item.actionCostCallbackSymbol) ||
            !reader.ReadSymbol(&item.actionCallbackSymbol) ||
            !reader.ReadU32(&item.parentControllerBase) ||
            !reader.ReadU32(&stayOnPanelAfterAction) ||
            !reader.ReadU32(&focusSelectedRowOnClick) ||
            (version >= 15 && !reader.ReadU32(&actionUsesParent)) ||
            (version >= 16 && !reader.ReadU32(&dataRecordRows)) ||
            dataRecordRows > 1 ||
            stayOnPanelAfterAction > 1 || focusSelectedRowOnClick > 1 ||
            actionUsesParent > 1 ||
            !IsPrintableFourCC(item.parentDialogId) ||
            !IsPrintableFourCC(item.childDialogId) || item.openCommandId == 0 ||
            !MajestyStockBuildingControllers::IsSupported(
                item.parentControllerBase))
            return Fail(error, "MMCR live-agent-list record is invalid");
        item.stayOnPanelAfterAction = stayOnPanelAfterAction != 0;
        item.focusSelectedRowOnClick = focusSelectedRowOnClick != 0;
        item.actionUsesParent = actionUsesParent != 0;
        item.dataRecordRows = dataRecordRows != 0;
        if (item.dataRecordRows && (!item.actionUsesParent || item.focusSelectedRowOnClick ||
            !item.stayOnPanelAfterAction ||
            (!item.hasRowVariants && item.rowTitleIntentId == 0) ||
            std::any_of(item.rowVariants.begin(), item.rowVariants.end(),
                [](const LiveAgentListRowVariant& row) { return row.rowTitleIntentId == 0; })))
            return Fail(error, "MMCR data-record list requires parent action, explicit titles, and no world focus");
        const std::uint32_t commandId = 0x20000u + index;
        if (item.actionCommandId != commandId ||
            (!parsed.liveAgentLists.empty() && parsed.liveAgentLists.back().panelKey >= item.panelKey))
            return Fail(error, "MMCR live-agent-list record is noncanonical");
        parsed.liveAgentLists.push_back(std::move(item));
    }
    if (reader.cursor() != size) return Fail(error, "MMCR registry contains trailing bytes");
    if (!ValidateComposition(parsed, error)) return false;
    *registry = std::move(parsed);
    return true;
}

}  // namespace MajestyStockControllers
