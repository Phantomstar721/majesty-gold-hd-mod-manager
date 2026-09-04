#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace MajestyStockControllers {

constexpr std::uint32_t kRegistryVersion = 4;
constexpr std::uint32_t kMaximumRecordCount = 256;
constexpr std::uint32_t kMaximumPanelCount = 32;
constexpr std::size_t kMaximumRegistryBytes = 512u * 1024u;
constexpr std::size_t kMaximumLogicalKeyBytes = 64;
constexpr std::size_t kMaximumCallbackBytes = 64;
constexpr std::size_t kMaximumCompletionTextBytes = 96;
constexpr const char* kEnvironmentVariable =
    "MAJESTY_MOD_MANAGER_CONTROLLERS";
constexpr const char* kRelativeRegistryPath =
    "DataMX/majesty_mod_manager_controllers.bin";

struct SecondaryPanelRecord {
    std::string panelKey;
    std::uint32_t parentDialogId;
    std::uint32_t childDialogId;
    std::uint32_t buildingFamilyId;
    std::uint32_t openCommandId;
};

struct ResourceMeterRecord {
    std::string panelKey;
    std::string resourceKey;
    std::uint32_t attributeId;
    std::uint32_t labelControlId;
    std::uint32_t countControlId;
    std::uint32_t bindingControlId;
};

struct ResearchRowRecord {
    std::string panelKey;
    std::string recipeKey;
    std::uint32_t actionControlId;
    std::uint32_t descriptorTemplateControlId;
    std::uint32_t completionTemplateControlId;
    std::uint32_t requiredLevel;
    std::uint32_t price;
    std::uint32_t priceControlId;
    std::uint32_t progressControlId;
    std::uint32_t activeDisplayControlId;
    std::uint32_t iconControlId;
    std::string completionText;
};

struct UpgradeRequirement {
    std::uint32_t buildingLevel;
    std::string recipeKey;
};

struct UpgradeGateRecord {
    std::string panelKey;
    std::uint32_t upgradeControlId;
    std::uint32_t upgradePriceControlId;
    std::vector<UpgradeRequirement> requirements;
};

struct TimedRageActionRecord {
    std::string panelKey;
    std::string actionKey;
    std::uint32_t actionControlId;
    std::uint32_t descriptorTemplateControlId;
    std::uint32_t levelPriceTemplateControlId;
    std::uint32_t requiredLevel;
    std::uint32_t goldCost;
    std::string resourceKey;
    std::uint32_t resourceCost;
    std::string callbackSymbol;
    std::uint32_t durationMs;
    std::uint32_t iconControlId;
    std::uint32_t priceControlId;
    std::uint32_t progressControlId;
    std::uint32_t activeDisplayControlId;
};

struct RageCommandActionRecord {
    std::string panelKey;
    std::string actionKey;
    std::uint32_t actionControlId;
    std::uint32_t visualTemplateControlId;
    std::uint32_t completionTemplateResearchControlId;
    std::uint32_t requiredLevel;
    std::string resourceKey;
    std::uint32_t resourceCost;
    std::string callbackSymbol;
    std::uint32_t iconControlId;
    std::uint32_t priceControlId;
};

struct SovereignTargetActionRecord {
    std::string panelKey;
    std::string actionKey;
    std::uint32_t visualControlId;
    std::uint32_t privateControlId;
    std::uint32_t visualTemplateControlId;
    std::uint32_t targetTemplateControlId;
    std::uint32_t stockTargetMode;
    std::uint32_t stockExecutorMode;
    std::uint32_t privateMode;
    std::uint32_t privateUnitId;
    std::uint32_t cursorOrdinal;
    std::uint32_t requiredLevel;
    std::string resourceKey;
    std::uint32_t resourceCost;
    std::uint32_t iconControlId;
    std::uint32_t priceControlId;
};

struct RewardPanelRecord {
    std::string panelKey;
    std::uint32_t parentDialogId;
    std::uint32_t childDialogId;
    std::uint32_t openCommandId;
};

struct HostileMonsterFlagRecord {
    std::string panelKey;
    std::string actionKey;
    std::uint32_t privateMode;
    std::uint32_t privateFlagId;
    std::string flagPrototypeName;
    std::uint32_t cursorOrdinal;
    bool hasAvailabilityGate;
    std::uint32_t availabilityAttributeId;
    std::string unavailableAlertText;
};

struct OccupantActionPanelRecord {
    std::string panelKey;
    std::uint32_t parentDialogId;
    std::uint32_t childDialogId;
    std::uint32_t openCommandId;
    std::uint32_t actionCommandId;
    std::string costCallbackSymbol;
    std::string actionCallbackSymbol;
    std::uint32_t parentControllerBase;
};

struct BuildingOpenToggleRecord {
    std::string toggleKey;
    std::uint32_t parentDialogId;
    std::uint32_t openCommandId;
    std::uint32_t closeCommandId;
    std::uint32_t parentControllerBase;
};

struct Registry {
    std::vector<SecondaryPanelRecord> panels;
    std::vector<ResourceMeterRecord> meters;
    std::vector<ResearchRowRecord> researchRows;
    std::vector<UpgradeGateRecord> upgradeGates;
    std::vector<TimedRageActionRecord> timedRageActions;
    std::vector<RageCommandActionRecord> rageCommandActions;
    std::vector<SovereignTargetActionRecord> sovereignTargetActions;
    std::vector<RewardPanelRecord> rewardPanels;
    std::vector<HostileMonsterFlagRecord> hostileMonsterFlags;
    std::vector<OccupantActionPanelRecord> occupantActionPanels;
    std::vector<BuildingOpenToggleRecord> buildingOpenToggles;

    void Clear();
    const OccupantActionPanelRecord* FindOccupantPanelByChild(std::uint32_t id) const;
    const OccupantActionPanelRecord* FindOccupantPanelByParent(std::uint32_t id) const;
    const OccupantActionPanelRecord* FindOccupantPanelByCommand(std::uint32_t id) const;
    const BuildingOpenToggleRecord* FindBuildingOpenToggleByParent(
        std::uint32_t id) const;
    const SecondaryPanelRecord* FindPanelByKey(const std::string& panelKey) const;
    const SecondaryPanelRecord* FindPanelByChildDialog(
        std::uint32_t childDialogId) const;
    const SecondaryPanelRecord* FindPanelByParentDialog(
        std::uint32_t parentDialogId) const;
    const SecondaryPanelRecord* FindPanelByParentCommand(
        std::uint32_t parentDialogId,
        std::uint32_t commandId) const;
    const ResourceMeterRecord* FindMeter(
        const std::string& panelKey,
        const std::string& resourceKey) const;
    const ResearchRowRecord* FindResearchByCommand(
        std::uint32_t commandId) const;
    const TimedRageActionRecord* FindTimedRageByCommand(
        std::uint32_t commandId) const;
    const RageCommandActionRecord* FindRageCommand(
        const std::string& panelKey,
        std::uint32_t commandId) const;
    const SovereignTargetActionRecord* FindSovereignByPrivateMode(
        std::uint32_t privateMode) const;
    const RewardPanelRecord* FindRewardPanelByKey(const std::string& panelKey) const;
    const RewardPanelRecord* FindRewardPanelByChildDialog(
        std::uint32_t childDialogId) const;
    const RewardPanelRecord* FindRewardPanelByParentDialog(
        std::uint32_t parentDialogId) const;
    const RewardPanelRecord* FindRewardPanelByParentCommand(
        std::uint32_t parentDialogId, std::uint32_t commandId) const;
    const HostileMonsterFlagRecord* FindHostileMonsterFlagByPanel(
        const std::string& panelKey) const;
    const HostileMonsterFlagRecord* FindHostileMonsterFlagByMode(
        std::uint32_t privateMode) const;
};

// Parses manager-owned MMCR v2/v3/v4 registries without Win32 or executable
// dependencies.  Records are immutable alternatives for the existing stock-
// shaped singleton sessions; the registry does not create per-mod controllers,
// parallel AP99 owners, queued Rage commands, or parallel target sessions.
bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    Registry* registry,
    std::string* error);

}  // namespace MajestyStockControllers
