#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

#if defined(CAM_SIEGE_CRASH_DIAGNOSTIC)
#include "CrashDumpDiagnostic.h"
#endif
#include "ControllerLifecycleRegistry.h"
#include "FreestyleCamRuntime.h"
#include "IntentTextRegistry.h"
#include "RuntimeCapabilityManifest.h"

namespace {

struct MajestyBuildProfile {
    const char* id;
    DWORD peTimestamp;
    std::uintptr_t secondaryControllerResultRva;
    unsigned char expectedResultSite[6];
    std::uintptr_t dialogCreationRva;
    unsigned char expectedCreationEntry[7];
    std::uintptr_t dialogFactoryRva;
    unsigned char expectedFactoryEntry[7];
    std::uintptr_t customGuildFallbackRva;
    std::uintptr_t sharedGuildControllerRva;
    std::uintptr_t uiManagerRva;
    std::uintptr_t removeDialogRva;
    std::uintptr_t getPanelContextRva;
    std::uintptr_t getCommandMetadataRva;
    std::uintptr_t getPlayerAgentRva;
    std::uintptr_t readPackedAttributeRva;
    std::uintptr_t submitBuildingCommandRva;
    std::uintptr_t rageCommandDispatchRva;
    unsigned char expectedRageCommandDispatch[6];
    std::uintptr_t ragePrivateBranchRva;
    unsigned char expectedRagePrivateBranch[5];
    std::uintptr_t rageGplConstructionResumeRva;
    std::uintptr_t simulationClockRva;
    std::uintptr_t gameUpdateCallRva;
    unsigned char expectedGameUpdateCall[5];
    std::uintptr_t gameUpdateRva;
    std::uintptr_t findStreamControlRva;
    std::uintptr_t refreshResearchRowsRva;
    unsigned char expectedRefreshResearchRowsEntry[9];
    std::uintptr_t refreshSingleResearchRowRva;
    unsigned char expectedRefreshSingleResearchRowEntry[7];
    std::uintptr_t canSubmitResearchRva;
    unsigned char expectedCanSubmitResearchEntry[8];
    std::uintptr_t submitResearchCommandRva;
    unsigned char expectedSubmitResearchCommandEntry[7];
    std::uintptr_t researchCompletionRva;
    unsigned char expectedResearchCompletionEntry[7];
    std::uintptr_t researchCompletionDispatchSlotRva;
    std::uintptr_t resolveResearchDescriptorRva;
    unsigned char expectedResolveResearchDescriptorEntry[10];
    std::uintptr_t resolveSpellDescriptorRva;
    unsigned char expectedResolveSpellDescriptorEntry[10];
    std::uintptr_t refreshSingleSpellRowRva;
    std::uintptr_t getCurrentPlayerRva;
    std::uintptr_t researchCompletionNamePushRva;
    unsigned char expectedResearchCompletionNamePush[5];
    std::uintptr_t heroEnchantmentsSwitchRva;
    unsigned char expectedHeroEnchantmentsSwitch[5];
    std::uintptr_t heroEnchantmentsSwitchResumeRva;
    std::uintptr_t speedTonicRowStringCallRva;
    unsigned char expectedSpeedTonicRowStringCall[5];
    std::uintptr_t stockStringAssignRva;
    unsigned char expectedStockStringAssignEntry[8];
    std::uintptr_t resolveIntentTextRva;
    unsigned char expectedResolveIntentTextEntry[6];
    std::uintptr_t intentTextTableProviderRva;
    std::uintptr_t resolveIntentTextResumeRva;
    std::uintptr_t nameRegistryCompletionRva;
    unsigned char expectedNameRegistryCompletion[7];
    std::uintptr_t stockOperatorNewRva;
    unsigned char expectedStockOperatorNewEntry[6];
    std::uintptr_t nameGeneratorFactoryRva;
    unsigned char expectedNameGeneratorFactoryEntry[7];
    std::uintptr_t nameGeneratorConstructRva;
    unsigned char expectedNameGeneratorConstructEntry[7];
    std::uintptr_t nameRegistryFindOrInsertRva;
    unsigned char expectedNameRegistryFindOrInsertEntry[8];
    std::uintptr_t sovereignSpellClickRva;
    unsigned char expectedSovereignSpellClickEntry[9];
    std::uintptr_t sovereignTargetManagerRva;
    unsigned char expectedSovereignTargetManagerEntry[7];
    std::uintptr_t sovereignTargetCancelRva;
    unsigned char expectedSovereignTargetCancelEntry[11];
    std::uintptr_t sovereignCursorTransitionRva;
    unsigned char expectedSovereignCursorTransition[23];
    std::uintptr_t sovereignTargetCommitCallRva;
    unsigned char expectedSovereignTargetCommitCall[5];
    std::uintptr_t sovereignSubmitCommandRva;
    std::uintptr_t sovereignExecutorEntryRva;
    unsigned char expectedSovereignExecutorEntry[7];
    std::uintptr_t sovereignConstructionOverrideRva;
    unsigned char expectedSovereignConstructionOverride[9];
    std::size_t sovereignConstructionOverrideSize;
};

// Each profile is traced independently from the same stock dialog, Rage,
// research, and UI lifecycles. Never derive one profile by applying a blanket
// offset to the other: beta2 reorganizes different code regions differently.
constexpr MajestyBuildProfile kPublicBuildProfile = {
    "public-1.5.2.24", 0x5897B72F,
    0x0002594A, {0x8B, 0x6B, 0x24, 0x83, 0xC3, 0x10},
    0x00025910, {0x83, 0xEC, 0x08, 0x53, 0x55, 0x56, 0x57},
    0x0010AC00, {0x6A, 0xFF, 0x68, 0x17, 0x0E, 0x70, 0x00},
    0x0010C03F, 0x0010BE9C,
    0x00025D00, 0x00025880, 0x00067540, 0x001C2060,
    0x00029580, 0x001B9FD0, 0x000C4CF0,
    0x000C4FE1, {0x8B, 0x4D, 0x0C, 0x51, 0x8B, 0xCF},
    0x000B1269, {0x68, 0x41, 0x45, 0x00, 0x00},
    0x000B12C9, 0x003C5454,
    0x0002526D, {0xE8, 0xDE, 0x13, 0x00, 0x00},
    0x00026650, 0x002524C0,
    0x000A8AE0, {0x55, 0x8B, 0x6C, 0x24, 0x08, 0x57, 0x8B, 0x7D, 0x04},
    0x000A8870, {0x6A, 0xFF, 0x68, 0x38, 0x2F, 0x6F, 0x00},
    0x000A8B40, {0x8B, 0x44, 0x24, 0x04, 0x53, 0x56, 0x57, 0x50},
    0x000C2C60, {0x6A, 0xFF, 0x68, 0x1B, 0x69, 0x6F, 0x00},
    0x000DFE20, {0x6A, 0xFF, 0x68, 0xA0, 0xAD, 0x6F, 0x00},
    0x003B647C,
    0x000A86E0, {0x83, 0xEC, 0x08, 0x80, 0x3D, 0x7C, 0x17, 0x7C, 0x00, 0x00},
    0x000AE3B0, {0x83, 0xEC, 0x08, 0x80, 0x3D, 0xB4, 0x17, 0x7C, 0x00, 0x00},
    0x000AE4D0, 0x00024A00,
    0x000DFFC7, {0x57, 0xC1, 0xF9, 0x17, 0x50},
    0x000A39A0, {0x3D, 0x43, 0x52, 0x42, 0x32},
    0x000A39A5,
    0x000A3A08, {0xE8, 0x43, 0x49, 0x18, 0x00},
    0x00228350, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0xF1},
    0x00108480, {0x56, 0xE8, 0x6A, 0x6A, 0x05, 0x00},
    0x0015EEF0, 0x00108486,
    0x0011090E, {0x8B, 0x44, 0x24, 0x1C, 0x89, 0x58, 0x24},
    0x002D8F7E, {0xFF, 0x25, 0x40, 0x53, 0x73, 0x00},
    0x0010C070, {0x6A, 0xFF, 0x68, 0x4E, 0x0E, 0x70, 0x00},
    0x0010AB70, {0x6A, 0xFF, 0x68, 0xFB, 0x0A, 0x70, 0x00},
    0x0010FB70, {0x8B, 0x54, 0x24, 0x04, 0x83, 0xEC, 0x10, 0x53},
    0x000AE420, {0x8B, 0x44, 0x24, 0x04, 0x3D, 0x46, 0x11, 0x00, 0x00},
    0x0005E5D0, {0x6A, 0xFF, 0x68, 0x2B, 0x9C, 0x6E, 0x00},
    0x0005E9D0, {
        0x8B, 0x44, 0x24, 0x04, 0x56, 0x50, 0xE8, 0x35, 0xBB, 0xFF, 0xFF},
    0x0005EE25, {
        0x8B, 0x16, 0x8B, 0x52, 0x48, 0x89, 0x46, 0x3C,
        0x89, 0x5E, 0x40, 0x89, 0x5E, 0x38, 0x8B, 0x47,
        0x04, 0x53, 0x50, 0x8B, 0xCE, 0xFF, 0xD2},
    0x00065FF5, {0xE8, 0x76, 0x3F, 0x07, 0x00}, 0x000D9F70,
    0x000DA020, {0x6A, 0xFF, 0x68, 0x07, 0xA0, 0x6F, 0x00},
    0x000DA0A8, {0x8B, 0x4C, 0x24, 0x1C, 0x8B, 0xD8, 0x00, 0x00, 0x00}, 6,
};

constexpr MajestyBuildProfile kBeta2BuildProfile = {
    "beta2-1.5.2.28", 0x5A8A11D5,
    0x0002691A, {0x8B, 0x6B, 0x24, 0x83, 0xC3, 0x10},
    0x000268E0, {0x83, 0xEC, 0x08, 0x53, 0x55, 0x56, 0x57},
    0x0011B150, {0x6A, 0xFF, 0x68, 0xB7, 0x90, 0x71, 0x00},
    0x0011C58F, 0x0011C3EC,
    0x00026CD0, 0x00026850, 0x00068780, 0x001D7240,
    0x0002B150, 0x001CEF70, 0x000C5730,
    0x000C5A21, {0x8B, 0x4D, 0x0C, 0x51, 0x8B, 0xCF},
    0x000B1B59, {0x68, 0x41, 0x45, 0x00, 0x00},
    0x000B1BB9, 0x003E3FDC,
    0x0002623D, {0xE8, 0x5E, 0x16, 0x00, 0x00},
    0x000278A0, 0x00267920,
    0x000A93D0, {0x55, 0x8B, 0x6C, 0x24, 0x08, 0x57, 0x8B, 0x7D, 0x04},
    0x000A9160, {0x6A, 0xFF, 0x68, 0x48, 0x88, 0x70, 0x00},
    0x000A9430, {0x8B, 0x44, 0x24, 0x04, 0x53, 0x56, 0x57, 0x50},
    0x000C36A0, {0x6A, 0xFF, 0x68, 0x5B, 0xC2, 0x70, 0x00},
    0x000E0430, {0x6A, 0xFF, 0x68, 0x70, 0x03, 0x71, 0x00},
    0x003D46DC,
    0x000A8FD0, {0x83, 0xEC, 0x08, 0x80, 0x3D, 0x64, 0x02, 0x7E, 0x00, 0x00},
    0x000AECA0, {0x83, 0xEC, 0x08, 0x80, 0x3D, 0x9C, 0x02, 0x7E, 0x00, 0x00},
    0x000AEDC0, 0x000259D0,
    0x000E05D7, {0x57, 0xC1, 0xF9, 0x17, 0x50},
    0x000A4280, {0x3D, 0x43, 0x52, 0x42, 0x32},
    0x000A4285,
    0x000A42E8, {0xE8, 0x03, 0x68, 0x19, 0x00},
    0x0023AAF0, {0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C, 0x8B, 0xF1},
    0x0010A650, {0x56, 0xE8, 0xDA, 0xA9, 0x06, 0x00},
    0x00175030, 0x0010A656,
    0x00120E5E, {0x8B, 0x44, 0x24, 0x1C, 0x89, 0x58, 0x24},
    0x002EE542, {0xFF, 0x25, 0x80, 0xE4, 0x74, 0x00},
    0x0011C5C0, {0x6A, 0xFF, 0x68, 0xEE, 0x90, 0x71, 0x00},
    0x0011B0C0, {0x6A, 0xFF, 0x68, 0x9B, 0x8D, 0x71, 0x00},
    0x001200C0, {0x8B, 0x54, 0x24, 0x04, 0x83, 0xEC, 0x10, 0x53},
    0x000AED10, {0x8B, 0x44, 0x24, 0x04, 0x3D, 0x46, 0x11, 0x00, 0x00},
    0x0005F600, {0x6A, 0xFF, 0x68, 0x3B, 0xF5, 0x6F, 0x00},
    0x0005FA00, {
        0x8B, 0x44, 0x24, 0x04, 0x56, 0x50, 0xE8, 0x35, 0xBB, 0xFF, 0xFF},
    0x0005FE55, {
        0x8B, 0x16, 0x8B, 0x52, 0x48, 0x89, 0x46, 0x3C,
        0x89, 0x5E, 0x40, 0x89, 0x5E, 0x38, 0x8B, 0x47,
        0x04, 0x53, 0x50, 0x8B, 0xCE, 0xFF, 0xD2},
    0x00067025, {0xE8, 0x56, 0x35, 0x07, 0x00}, 0x000DA580,
    0x000DA630, {0x6A, 0xFF, 0x68, 0xD7, 0xF5, 0x70, 0x00},
    0x000DA6B8, {0x8B, 0x4C, 0x24, 0x1C, 0x8B, 0xD8, 0x00, 0x00, 0x00}, 6,
};

const MajestyBuildProfile* g_buildProfile = nullptr;
constexpr std::uint32_t kCgalDialogId = 0x4C414743;
constexpr std::uint32_t kCgbrDialogId = 0x52424743;
constexpr std::uint32_t kAp10DialogId = 0x30315041;
constexpr std::uint32_t kAp69DialogId = 0x39365041;
constexpr std::uint32_t kBrewingParentCommandId = 0x00001F49;
constexpr std::uint32_t kBuildingUpgradeControlId = 0x00001F47;
constexpr std::uint32_t kBuildingUpgradePriceControlId = 0x00001F4F;
constexpr std::uint32_t kInvigoratingElixerControlId = 0x00002A10;
constexpr std::uint32_t kInvigoratingElixerIconControlId =
    kInvigoratingElixerControlId + 1000;
constexpr std::uint32_t kInvigoratingElixerPriceControlId =
    kInvigoratingElixerControlId - 1000;
constexpr std::uint32_t kInvigoratingElixerProgressControlId = 0x00002009;
constexpr std::uint32_t kInvigoratingElixerActiveDisplayControlId = 0x0000227A;
constexpr std::uint32_t kStockArrowsResearchControlId = 0x0000139C;
constexpr std::uint32_t kStockTeleportAmuletResearchControlId = 0x000013B3;
constexpr std::uint32_t kStockArrowsResearchPrice = 250;
constexpr std::size_t kResearchDescriptorDwordCount = 5;
constexpr std::size_t kResearchDescriptorSize =
    kResearchDescriptorDwordCount * sizeof(std::uint32_t);
constexpr std::uint32_t kWeaponOilResearchControlId = 0x00002A13;
constexpr std::uint32_t kWeaponOilResearchPriceControlId =
    kWeaponOilResearchControlId + 1000;
constexpr std::uint32_t kWeaponOilResearchPrice = 250;
constexpr std::uint32_t kWeaponOilProgressControlId = 0x00002A11;
constexpr std::uint32_t kWeaponOilActiveDisplayControlId = 0x00002A12;
constexpr std::uint32_t kPhoenixPhialResearchControlId = 0x00002A16;
constexpr std::uint32_t kPhoenixPhialResearchIconControlId =
    kPhoenixPhialResearchControlId + 500;
constexpr std::uint32_t kPhoenixPhialResearchPriceControlId =
    kPhoenixPhialResearchControlId + 1000;
constexpr std::uint32_t kPhoenixPhialResearchPrice = 750;
constexpr std::uint32_t kPhoenixPhialProgressControlId = 0x00002A17;
constexpr std::uint32_t kPhoenixPhialActiveDisplayControlId = 0x00002A18;
constexpr std::uint32_t kPhilosophersStoneControlId = 0x00002A21;
constexpr std::uint32_t kArcaneInfusionVisualControlId = 0x00001132;
constexpr std::uint32_t kPhilosophersStoneVisualControlId = 0x00001133;
constexpr std::uint32_t kArcaneInfusionVisualPriceControlId =
    kArcaneInfusionVisualControlId - 1000;
constexpr std::uint32_t kPhilosophersStoneVisualPriceControlId =
    kPhilosophersStoneVisualControlId - 1000;
constexpr std::uint32_t kReagentMeterLabelControlId = 0x00002A23;
constexpr std::uint32_t kReagentMeterCountControlId = 0x00002A24;
constexpr std::uint32_t kReagentMeterCountBindingId = 0x00002A25;
// Majesty registers #ATTRIB_ReturnAmount as the packed four-character ID
// APV0. The Laboratory mirrors its stock num_resources balance there so the
// native panel reads the same value that the GPL action commit consumes.
constexpr std::uint32_t kReagentStockAttributeId = 0x30565041;
constexpr int kReagentActionCost = 10;
constexpr int kInvigoratingElixerReagentCost = 1;
constexpr std::uint32_t kStockLightningStormControlId = 0x00001145;
constexpr std::uint32_t kStockLightningStormMode = 0x34317053;
constexpr std::uint32_t kStockVinesControlId = 0x00001132;
constexpr std::uint32_t kStockVinesMode = 0x33327053;
constexpr std::uint32_t kStockUnaffordableGoldCost = 0x3FFFFFFF;
constexpr std::uint32_t kStockFervusSecondSpellMode = 0x33327053;
constexpr std::uint32_t kStockFervusThirdSpellMode = 0x34327053;
constexpr std::uint32_t kPhilosophersStoneMode = 0x31536C41;
constexpr std::uint32_t kPhilosophersStoneUnitId = 0x31534C41;
constexpr std::uint32_t kPhilosophersStoneCursorOrdinal = 39;
constexpr std::uint32_t kRageOfKrolmCommandId = 1;
constexpr std::uint32_t kInvigoratingElixerGoldCost = 1500;
constexpr DWORD kInvigoratingElixerDurationMs = 30000;
constexpr std::uint32_t kRageOfKrolmCountAttributeId = 0x07425041;
constexpr std::uint32_t kPlayerGoldDataId = 0x00505041;
constexpr std::uint32_t kCurrentResearchAttributeId = 0x2C425041;
constexpr std::uint32_t kResearchStartedAtAttributeId = 0x38425041;
constexpr std::uint32_t kResearchDurationAttributeId = 0x0D425041;
constexpr std::uint32_t kWeaponOilCompletionAttributeId = 0x2A425041;
constexpr std::uint32_t kPhoenixPhialCompletionAttributeId = 0x29425041;
constexpr std::uint32_t kStockPetrifyControlId = 0x0000113E;
constexpr std::uint32_t kStockFervusHealingControlId = 0x00001140;
constexpr std::uint32_t kStockFervusBuildingClassId = 0x00514241;
constexpr std::uint32_t kLaboratoryBuildingClassId = 0x00424C41;
constexpr std::uint32_t kArrowsGlobalTextId = 0x000000CA;
constexpr std::uint32_t kParalyticOilOverlayId = 0x316F4C41;
constexpr std::uint32_t kTransmutationOilOverlayId = 0x326F4C41;
constexpr std::uint32_t kPoisonedWeaponOverlayId = 0x336F4C41;
constexpr std::uint32_t kSpeedTonicOverlayId = 0x31305258;
constexpr std::uint32_t kFirstStockEnchantmentOverlayId = 0x32425243;
constexpr std::uint32_t kStockLastNameGeneratorId = 0x37314D4E;
constexpr std::uint32_t kAlchemistNameGeneratorId = 0x38314D4E;
constexpr std::uint32_t kAlchemistGivenNamesId = 0x39364E48;
constexpr std::uint32_t kAlchemistEndingsId = 0x30374E48;
constexpr std::uint32_t kAlchemistThirdNamePartId = 0x31374E48;
constexpr std::uint32_t kAlchemistFourthNamePartId = 0x32374E48;
constexpr std::uint32_t kPhantomNameGeneratorId = 0x39314D4E;
constexpr std::uint32_t kPhantomGivenNamesId = 0x33374E48;
constexpr std::uint32_t kPhantomEndingsId = 0x34374E48;
constexpr std::uint32_t kPhantomThirdNamePartId = 0x35374E48;
constexpr std::uint32_t kPhantomFourthNamePartId = 0x36374E48;
constexpr wchar_t kIntentRegistryEnvironment[] =
    L"MAJESTY_MOD_MANAGER_INTENT_REGISTRY";
constexpr wchar_t kCapabilityManifestEnvironment[] =
    L"MAJESTY_MOD_MANAGER_CAPABILITIES";
constexpr wchar_t kRuntimeReadyEventEnvironment[] =
    L"MAJESTY_BUILDING_RUNTIME_READY_EVENT";
constexpr int kSidebarWidth = 200;
constexpr std::size_t kCustomGuildFactoryPatchSize = 30;
constexpr unsigned char kStockUnknownDialogEpilogue[
    kCustomGuildFactoryPatchSize] = {
    0x8B, 0x4C, 0x24, 0x04,
    0x64, 0x89, 0x0D, 0x00, 0x00, 0x00, 0x00,
    0x59,
    0x83, 0xC4, 0x0C,
    0xC2, 0x10, 0x00,
    0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC,
    0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC,
};
// Public AP10 vtable 0x0073D184 and beta2 vtable 0x00755E5C each contain
// 17 executable entries through +0x40; the following word begins the next
// RTTI-backed table. Runtime code copies the live table instead of selecting
// either address.
constexpr std::size_t kAp10VtableEntries = 17;
constexpr std::size_t kAp69VtableEntries = 11;

std::uintptr_t g_resumeWithController = 0;
std::uintptr_t g_creationTrampoline = 0;
std::uintptr_t g_factoryTrampoline = 0;
std::uintptr_t g_rageCommandDispatchResume = 0;
std::uintptr_t g_ragePrivateBranchResume = 0;
std::uintptr_t g_rageGplConstructionResume = 0;
std::uintptr_t g_researchCompletionNamePushResume = 0;
std::uintptr_t g_resolveResearchDescriptorTrampoline = 0;
std::uintptr_t g_researchDescriptorRegistryMap = 0;
std::uintptr_t g_researchDescriptorRegistryFindOrInsert = 0;
bool g_privateResearchDescriptorsRegistered = false;
using ResearchCompletion = void (__cdecl*)(
    std::uint32_t, void*, std::uint32_t, std::uint32_t, std::uint32_t);
ResearchCompletion g_stockResearchCompletion = nullptr;
std::uintptr_t g_resolveSpellDescriptorTrampoline = 0;
std::uintptr_t g_heroEnchantmentsSwitchResume = 0;
std::uintptr_t g_stockStringAssign = 0;
std::uintptr_t g_nameRegistryCompletionResume = 0;
std::uintptr_t g_sovereignCursorTransitionResume = 0;
std::uintptr_t g_sovereignExecutorResume = 0;
std::uintptr_t g_sovereignConstructionResume = 0;
LONG g_privateEnchantmentRowKind = 0;
const char g_paralyticOilEnchantmentText[] =
    "Paralytic Oil - brief stun on weapon hit";
const char g_transmutationOilEnchantmentText[] =
    "Transmutation Oil - +5 gold on weapon hit";
const char g_poisonedWeaponEnchantmentText[] =
    "Poisoned Weapon - poison on weapon hit";
struct MajestyStringView {
    const char* data;
    std::uint32_t capacityFlags;
    std::uint32_t length;
};
const MajestyStringView g_paralyticOilEnchantmentString = {
    g_paralyticOilEnchantmentText,
    sizeof(g_paralyticOilEnchantmentText) - 1,
    sizeof(g_paralyticOilEnchantmentText) - 1};
const MajestyStringView g_transmutationOilEnchantmentString = {
    g_transmutationOilEnchantmentText,
    sizeof(g_transmutationOilEnchantmentText) - 1,
    sizeof(g_transmutationOilEnchantmentText) - 1};
const MajestyStringView g_poisonedWeaponEnchantmentString = {
    g_poisonedWeaponEnchantmentText,
    sizeof(g_poisonedWeaponEnchantmentText) - 1,
    sizeof(g_poisonedWeaponEnchantmentText) - 1};
static_assert(sizeof(MajestyStringView) == 12, "Majesty x86 string view changed");

enum class PrivateIntentRegistryState {
    Absent,
    Empty,
    Loaded,
    Invalid,
};

enum class CapabilityManifestState {
    Absent,
    Loaded,
    Invalid,
};

using StockIntentTextResolver = bool (__cdecl*)(
    std::uint32_t, MajestyStringView*);
using StockStringAssign = MajestyStringView* (__thiscall*)(
    MajestyStringView*, const MajestyStringView*);
StockIntentTextResolver g_stockIntentTextResolver = nullptr;
StockStringAssign g_privateIntentStringAssign = nullptr;
std::vector<MajestyIntentText::RegistryRecord> g_privateIntentRecords;
std::vector<MajestyStringView> g_privateIntentViews;
MajestyRuntimeCapabilities::Manifest g_runtimeCapabilities;

const char* g_invigoratingGplFunctionName =
    "Alchemist_DoInvigoratingElixer";
const char* g_arcaneInfusionGplFunctionName =
    "Alchemist_Arcane_Infusion";
HMODULE g_runtimeModule = nullptr;
std::uintptr_t g_imageBase = 0;
WNDPROC g_originalWindowProcedure = nullptr;
LONG g_cgalSecondaryArmed = 0;
LONG g_ap10ControllerContext = 0;
LONG g_cgalControllerContext = 0;
LONG g_customBrewingActive = 0;
LONG g_customBrewingHandle = 0;
LONG g_captureCgalController = 0;
LONG g_captureBrewingController = 0;
LONG g_cgalController = 0;
LONG g_customBrewingController = 0;
LONG g_invigoratingElixerActive = 0;
LONG g_invigoratingRageHandle = 0;
LONG g_arcaneInfusionRageHandle = 0;
LONG g_invigoratingRageDispatch = 0;
bool g_stockResearchRouteReady = false;
const char g_weaponOilCompletionName[] = "Weapon Oil";
const char g_phoenixPhialCompletionName[] = "Phoenix Phial";
std::uint32_t* g_weaponOilResearchDescriptor = nullptr;
std::uint32_t* g_phoenixPhialResearchDescriptor = nullptr;
std::uint32_t g_invigoratingSpellDescriptor[6] = {};
std::uint32_t g_philosophersStoneSpellDescriptor[6] = {};
std::uint32_t g_arcaneInfusionVisualDescriptor[6] = {};
std::uint32_t g_philosophersStoneVisualDescriptor[6] = {};
LONG g_pendingSovereignControl = 0;
LONG g_pendingSovereignLaboratory = 0;
LONG g_executingSovereignKind = 0;

struct LaboratoryActivitySnapshot {
    int command;
    int startedAt;
    int duration;
};

struct LaboratoryResearchOwner {
    unsigned char* context;
    std::uint32_t recipe;
    DWORD startedAt;
    DWORD duration;
    bool pending;
    bool active;
};

LaboratoryResearchOwner g_laboratoryResearchOwner = {};
LONG g_laboratoryResearchCompletionStaged = 0;
LONG g_laboratoryResearchCompletedThisUpdate = 0;
DWORD g_invigoratingElixerStartedAt = 0;
DWORD g_lastBrewingProgressTraceSecond = 0xFFFFFFFF;
int g_lastReagentMeterTraceStock = -1;
void* g_customBrewingVtable[kAp69VtableEntries] = {};
void* g_customLaboratoryVtable[kAp10VtableEntries] = {};

using ControllerSetup = void (__thiscall*)(void*);
using ControllerControl = int (__thiscall*)(void*, std::uint32_t);
using ControllerEvent = void (__thiscall*)(
    void*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
using ControllerActivity = void (__thiscall*)(void*);
using GameUpdate = void (__thiscall*)(void*);
ControllerSetup g_stockAp69Setup = nullptr;
ControllerControl g_stockAp69Control = nullptr;
ControllerEvent g_stockAp69Event = nullptr;
ControllerSetup g_stockLaboratorySetup = nullptr;
ControllerControl g_stockLaboratoryControl = nullptr;
ControllerEvent g_stockLaboratoryEvent = nullptr;
ControllerActivity g_stockLaboratoryActivity = nullptr;
GameUpdate g_stockGameUpdate = nullptr;

bool StockArcaneInfusionComplete();

void WriteLog(const char* message) {
    char modulePath[MAX_PATH] = {};
    if (!GetModuleFileNameA(g_runtimeModule, modulePath, MAX_PATH)) {
        return;
    }
    char* separator = std::strrchr(modulePath, '\\');
    if (separator != nullptr) {
        separator[1] = '\0';
    }
    strcat_s(modulePath, "MajestyBuildingRuntime.log");
    FILE* stream = nullptr;
    if (fopen_s(&stream, modulePath, "a") != 0 || stream == nullptr) {
        return;
    }
    SYSTEMTIME now = {};
    GetLocalTime(&now);
    std::fprintf(
        stream,
        "%04u-%02u-%02u %02u:%02u:%02u.%03u %s\n",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    std::fclose(stream);
}

__declspec(noreturn) void StopUnsafeManagerRuntimeLaunch(const char* reason) {
    WriteLog(reason);
    MessageBoxW(
        nullptr,
        L"Majesty Mod Manager could not safely install its required runtime support. "
        L"Majesty will close before loading a game. Rebuild the selected mods in the Mod "
        L"Manager; if the problem continues, review MajestyBuildingRuntime.log beside the "
        L"runtime DLL.",
        L"Majesty Mod Manager",
        MB_OK | MB_ICONERROR);
    TerminateProcess(GetCurrentProcess(), 0x4D4D5458u);
    ExitProcess(0x4D4D5458u);
}

bool RequireManagerRuntimeInstall(
    bool installed,
    bool managerLaunch,
    const char* failureReason) {
    if (!installed && managerLaunch) {
        StopUnsafeManagerRuntimeLaunch(failureReason);
    }
    return installed;
}

bool SignalManagerRuntimeReady() {
    wchar_t eventName[128] = {};
    const DWORD length = GetEnvironmentVariableW(
        kRuntimeReadyEventEnvironment,
        eventName,
        static_cast<DWORD>(sizeof(eventName) / sizeof(eventName[0])));
    if (length == 0 || length >= sizeof(eventName) / sizeof(eventName[0])) {
        WriteLog(
            "Manager runtime barrier failed: the launcher event name is absent or invalid.");
        return false;
    }
    const HANDLE event = OpenEventW(
        EVENT_MODIFY_STATE, FALSE, eventName);
    if (event == nullptr) {
        WriteLog(
            "Manager runtime barrier failed: the launcher event could not be opened.");
        return false;
    }
    const bool signaled = SetEvent(event) != FALSE;
    CloseHandle(event);
    if (signaled) {
        WriteLog(
            "Signaled the launcher after completing all pre-window manager runtime initialization.");
    } else {
        WriteLog(
            "Manager runtime barrier failed: the ready event could not be signaled.");
    }
    return signaled;
}

bool IsCanonicalAbsolutePath(const wchar_t* path) {
    if (path == nullptr || path[0] == L'\0') {
        return false;
    }
    wchar_t resolved[32768] = {};
    const DWORD length = GetFullPathNameW(
        path,
        static_cast<DWORD>(sizeof(resolved) / sizeof(resolved[0])),
        resolved,
        nullptr);
    return length != 0 &&
        length < sizeof(resolved) / sizeof(resolved[0]) &&
        _wcsicmp(path, resolved) == 0;
}

CapabilityManifestState LoadRuntimeCapabilityManifest() {
    wchar_t manifestPath[32768] = {};
    SetLastError(ERROR_SUCCESS);
    const DWORD pathLength = GetEnvironmentVariableW(
        kCapabilityManifestEnvironment,
        manifestPath,
        static_cast<DWORD>(sizeof(manifestPath) / sizeof(manifestPath[0])));
    if (pathLength == 0) {
        if (GetLastError() == ERROR_ENVVAR_NOT_FOUND) {
            WriteLog(
                "No manager capability manifest was supplied; no optional runtime hooks will be installed.");
            return CapabilityManifestState::Absent;
        }
        WriteLog(
            "Manager capability manifest rejected: its environment path is empty or unreadable.");
        return CapabilityManifestState::Invalid;
    }
    if (pathLength >= sizeof(manifestPath) / sizeof(manifestPath[0]) ||
        !IsCanonicalAbsolutePath(manifestPath)) {
        WriteLog(
            "Manager capability manifest rejected: its environment path is not a canonical absolute path.");
        return CapabilityManifestState::Invalid;
    }

    const HANDLE file = CreateFileW(
        manifestPath,
        GENERIC_READ,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        char message[192] = {};
        sprintf_s(
            message,
            "Manager capability manifest rejected: the supplied file could not be opened (error %lu).",
            GetLastError());
        WriteLog(message);
        return CapabilityManifestState::Invalid;
    }

    LARGE_INTEGER fileSize = {};
    if (!GetFileSizeEx(file, &fileSize) || fileSize.QuadPart < 0 ||
        static_cast<unsigned long long>(fileSize.QuadPart) >
            MajestyRuntimeCapabilities::kMaximumManifestBytes) {
        WriteLog(
            "Manager capability manifest rejected: its file size is outside the supported bounds.");
        CloseHandle(file);
        return CapabilityManifestState::Invalid;
    }
    std::vector<unsigned char> bytes(
        static_cast<std::size_t>(fileSize.QuadPart));
    std::size_t totalRead = 0;
    while (totalRead < bytes.size()) {
        DWORD readNow = 0;
        const DWORD request = static_cast<DWORD>(bytes.size() - totalRead);
        if (!ReadFile(
                file,
                bytes.data() + totalRead,
                request,
                &readNow,
                nullptr) || readNow == 0) {
            WriteLog(
                "Manager capability manifest rejected: its file could not be read completely.");
            CloseHandle(file);
            return CapabilityManifestState::Invalid;
        }
        totalRead += readNow;
    }
    CloseHandle(file);

    MajestyRuntimeCapabilities::Manifest manifest;
    std::string parseError;
    if (!MajestyRuntimeCapabilities::ParseManifest(
            bytes.data(), bytes.size(), &manifest, &parseError)) {
        char message[384] = {};
        sprintf_s(
            message,
            "Manager capability manifest rejected before hook installation: %s.",
            parseError.c_str());
        WriteLog(message);
        return CapabilityManifestState::Invalid;
    }
    g_runtimeCapabilities = std::move(manifest);
    char message[192] = {};
    sprintf_s(
        message,
        "Loaded %u declared runtime capabilities from the validated MMCP manifest.",
        static_cast<unsigned int>(g_runtimeCapabilities.capabilities.size()));
    WriteLog(message);
    return CapabilityManifestState::Loaded;
}

bool HasRuntimeCapability(const char* capability) {
    return g_runtimeCapabilities.Has(capability);
}

PrivateIntentRegistryState LoadPrivateIntentRegistry() {
    wchar_t registryPath[32768] = {};
    SetLastError(ERROR_SUCCESS);
    const DWORD pathLength = GetEnvironmentVariableW(
        kIntentRegistryEnvironment,
        registryPath,
        static_cast<DWORD>(sizeof(registryPath) / sizeof(registryPath[0])));
    if (pathLength == 0) {
        if (GetLastError() == ERROR_ENVVAR_NOT_FOUND) {
            WriteLog(
                "No manager intent registry was supplied; the stock activity-text resolver remains unchanged.");
            return PrivateIntentRegistryState::Absent;
        }
        WriteLog(
            "Manager intent registry rejected: its environment path is empty or unreadable.");
        return PrivateIntentRegistryState::Invalid;
    }
    if (pathLength >= sizeof(registryPath) / sizeof(registryPath[0])) {
        WriteLog(
            "Manager intent registry rejected: its environment path is too long.");
        return PrivateIntentRegistryState::Invalid;
    }

    const HANDLE file = CreateFileW(
        registryPath,
        GENERIC_READ,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        char message[192] = {};
        sprintf_s(
            message,
            "Manager intent registry rejected: the supplied file could not be opened (error %lu).",
            GetLastError());
        WriteLog(message);
        return PrivateIntentRegistryState::Invalid;
    }

    LARGE_INTEGER fileSize = {};
    if (!GetFileSizeEx(file, &fileSize) || fileSize.QuadPart < 0 ||
        static_cast<unsigned long long>(fileSize.QuadPart) >
            MajestyIntentText::kMaximumRegistryBytes) {
        WriteLog(
            "Manager intent registry rejected: its file size is outside the supported bounds.");
        CloseHandle(file);
        return PrivateIntentRegistryState::Invalid;
    }
    std::vector<unsigned char> bytes(
        static_cast<std::size_t>(fileSize.QuadPart));
    std::size_t totalRead = 0;
    while (totalRead < bytes.size()) {
        DWORD readNow = 0;
        const DWORD request = static_cast<DWORD>(bytes.size() - totalRead);
        if (!ReadFile(
                file,
                bytes.data() + totalRead,
                request,
                &readNow,
                nullptr) || readNow == 0) {
            WriteLog(
                "Manager intent registry rejected: its file could not be read completely.");
            CloseHandle(file);
            return PrivateIntentRegistryState::Invalid;
        }
        totalRead += readNow;
    }
    CloseHandle(file);

    std::vector<MajestyIntentText::RegistryRecord> records;
    std::string parseError;
    if (!MajestyIntentText::ParseRegistry(
            bytes.data(), bytes.size(), &records, &parseError)) {
        char message[384] = {};
        sprintf_s(
            message,
            "Manager intent registry rejected before hook installation: %s.",
            parseError.c_str());
        WriteLog(message);
        return PrivateIntentRegistryState::Invalid;
    }
    if (records.empty()) {
        WriteLog(
            "Manager intent registry is valid but empty; the stock activity-text resolver remains unchanged.");
        return PrivateIntentRegistryState::Empty;
    }

    g_privateIntentRecords = std::move(records);
    g_privateIntentViews.clear();
    g_privateIntentViews.reserve(g_privateIntentRecords.size());
    for (const auto& record : g_privateIntentRecords) {
        const auto length = static_cast<std::uint32_t>(record.text.size());
        const MajestyStringView view = {record.text.c_str(), length, length};
        g_privateIntentViews.push_back(view);
    }
    char message[192] = {};
    sprintf_s(
        message,
        "Loaded %u manager-owned activity-text entries from the validated MMTX registry.",
        static_cast<unsigned int>(g_privateIntentRecords.size()));
    WriteLog(message);
    return PrivateIntentRegistryState::Loaded;
}

const MajestyStringView* FindPrivateIntentText(std::uint32_t id) {
    const auto found = std::lower_bound(
        g_privateIntentRecords.begin(),
        g_privateIntentRecords.end(),
        id,
        [](const MajestyIntentText::RegistryRecord& record, std::uint32_t value) {
            return record.id < value;
        });
    if (found == g_privateIntentRecords.end() || found->id != id) {
        return nullptr;
    }
    const auto index = static_cast<std::size_t>(
        found - g_privateIntentRecords.begin());
    return &g_privateIntentViews[index];
}

bool SelectMajestyBuildProfile() {
    if (g_imageBase == 0) {
        WriteLog("Runtime profile selection failed: Majesty module base is unavailable.");
        return false;
    }
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(g_imageBase);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        WriteLog("Runtime profile selection failed: host has no valid DOS header.");
        return false;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
        g_imageBase + static_cast<std::uintptr_t>(dos->e_lfanew));
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) {
        WriteLog("Runtime profile selection failed: host is not the supported x86 Majesty image.");
        return false;
    }
    if (nt->FileHeader.TimeDateStamp == kPublicBuildProfile.peTimestamp) {
        g_buildProfile = &kPublicBuildProfile;
    } else if (nt->FileHeader.TimeDateStamp == kBeta2BuildProfile.peTimestamp) {
        g_buildProfile = &kBeta2BuildProfile;
    } else {
        char message[192] = {};
        sprintf_s(
            message,
            "Runtime refused unknown Majesty build timestamp 0x%08X; supported profiles are public-1.5.2.24 and beta2-1.5.2.28.",
            nt->FileHeader.TimeDateStamp);
        WriteLog(message);
        return false;
    }
    char message[128] = {};
    sprintf_s(message, "Selected Majesty runtime profile: %s.", g_buildProfile->id);
    WriteLog(message);
    return true;
}

bool MatchesProfileBytes(
    std::uintptr_t rva,
    const unsigned char* expected,
    std::size_t size,
    const char* label) {
    if (std::memcmp(
            reinterpret_cast<const void*>(g_imageBase + rva),
            expected,
            size) == 0) {
        return true;
    }
    char message[192] = {};
    sprintf_s(
        message,
        "Runtime profile %s rejected: %s bytes differ at RVA 0x%08X.",
        g_buildProfile->id,
        label,
        static_cast<unsigned int>(rva));
    WriteLog(message);
    return false;
}

bool ValidatePrivateIntentTextProfile() {
    if (g_buildProfile->resolveIntentTextResumeRva !=
            g_buildProfile->resolveIntentTextRva +
                sizeof(g_buildProfile->expectedResolveIntentTextEntry) ||
        g_buildProfile->expectedResolveIntentTextEntry[0] != 0x56 ||
        g_buildProfile->expectedResolveIntentTextEntry[1] != 0xE8) {
        WriteLog(
            "Manager intent hook rejected: its stock resolver profile is internally inconsistent.");
        return false;
    }
    std::int32_t providerDisplacement = 0;
    std::memcpy(
        &providerDisplacement,
        g_buildProfile->expectedResolveIntentTextEntry + 2,
        sizeof(providerDisplacement));
    const auto profiledProvider = static_cast<std::uintptr_t>(
        static_cast<std::intptr_t>(
            g_buildProfile->resolveIntentTextResumeRva) +
        providerDisplacement);
    if (profiledProvider != g_buildProfile->intentTextTableProviderRva) {
        WriteLog(
            "Manager intent hook rejected: its stock table-provider call target is inconsistent.");
        return false;
    }
    return MatchesProfileBytes(
               g_buildProfile->resolveIntentTextRva,
               g_buildProfile->expectedResolveIntentTextEntry,
               sizeof(g_buildProfile->expectedResolveIntentTextEntry),
               "shared activity-text resolver") &&
        MatchesProfileBytes(
               g_buildProfile->stockStringAssignRva,
               g_buildProfile->expectedStockStringAssignEntry,
               sizeof(g_buildProfile->expectedStockStringAssignEntry),
               "activity-text stock string assignment function");
}

void BuildCustomGuildFactoryPatch(
    unsigned char (&patch)[kCustomGuildFactoryPatchSize]) {
    // This is the proven manager custom-guild fallback. At the
    // stock unknown-ID epilogue ECX still owns the requested FourCC. Preserve
    // that ID and both constructor arguments, recognize only the reserved CG
    // prefix, and enter the unchanged AP07/AP10 allocation block. All other
    // IDs execute the byte-identical stock epilogue.
    const unsigned char prototype[kCustomGuildFactoryPatchSize] = {
        0x66, 0x81, 0xF9, 0x43, 0x47,       // cmp cx, 0x4743 ("CG")
        0x75, 0x05,                         // jne stock_epilogue
        0xE9, 0x00, 0x00, 0x00, 0x00,       // jmp shared AP07/AP10 allocation
        0x8B, 0x4C, 0x24, 0x04,
        0x64, 0x89, 0x0D, 0x00, 0x00, 0x00, 0x00,
        0x59,
        0x83, 0xC4, 0x0C,
        0xC2, 0x10, 0x00,
    };
    std::memcpy(patch, prototype, sizeof(prototype));
    const auto jumpFrom = g_buildProfile->customGuildFallbackRva + 12;
    const auto relative = static_cast<std::int32_t>(
        g_buildProfile->sharedGuildControllerRva - jumpFrom);
    std::memcpy(patch + 8, &relative, sizeof(relative));
}

bool ValidateCustomGuildFactoryFallback() {
    const auto* site = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->customGuildFallbackRva);
    if (std::memcmp(
            site,
            kStockUnknownDialogEpilogue,
            sizeof(kStockUnknownDialogEpilogue)) == 0) {
        return true;
    }
    unsigned char installed[kCustomGuildFactoryPatchSize] = {};
    BuildCustomGuildFactoryPatch(installed);
    if (std::memcmp(site, installed, sizeof(installed)) == 0) {
        return true;
    }
    char message[192] = {};
    sprintf_s(
        message,
        "Runtime profile %s rejected: custom-guild fallback bytes differ at RVA 0x%08X.",
        g_buildProfile->id,
        static_cast<unsigned int>(g_buildProfile->customGuildFallbackRva));
    WriteLog(message);
    return false;
}

void LogInstalledProfileSite(const char* label, std::uintptr_t rva) {
    char message[192] = {};
    sprintf_s(
        message,
        "Installed %s for %s at MajestyHD.exe+0x%08X.",
        label,
        g_buildProfile->id,
        static_cast<unsigned int>(rva));
    WriteLog(message);
}

bool ValidateResearchCompletionDispatchSlot() {
    const auto* dispatchSlot = reinterpret_cast<const std::uint32_t*>(
        g_imageBase + g_buildProfile->researchCompletionDispatchSlotRva);
    const std::uint32_t stockCompletion = static_cast<std::uint32_t>(
        g_imageBase + g_buildProfile->researchCompletionRva);
    if (dispatchSlot[-1] == 0x00002009u &&
        dispatchSlot[0] == stockCompletion &&
        dispatchSlot[1] == 0x0000200Bu) {
        return true;
    }
    WriteLog(
        "Runtime profile mismatch at stock research event 0x2009 dispatch.");
    return false;
}

bool ValidateAlchemistSecondaryControllerProfile() {
    return MatchesProfileBytes(
               g_buildProfile->secondaryControllerResultRva,
               g_buildProfile->expectedResultSite,
               sizeof(g_buildProfile->expectedResultSite),
               "secondary-controller result") &&
        MatchesProfileBytes(
               g_buildProfile->dialogCreationRva,
               g_buildProfile->expectedCreationEntry,
               sizeof(g_buildProfile->expectedCreationEntry),
               "dialog creation") &&
        MatchesProfileBytes(
               g_buildProfile->dialogFactoryRva,
               g_buildProfile->expectedFactoryEntry,
               sizeof(g_buildProfile->expectedFactoryEntry),
               "dialog factory") &&
        MatchesProfileBytes(
               g_buildProfile->gameUpdateCallRva,
               g_buildProfile->expectedGameUpdateCall,
               sizeof(g_buildProfile->expectedGameUpdateCall),
               "game update call") &&
        MatchesProfileBytes(
               g_buildProfile->resolveResearchDescriptorRva,
               g_buildProfile->expectedResolveResearchDescriptorEntry,
               sizeof(g_buildProfile->expectedResolveResearchDescriptorEntry),
               "research descriptor resolver") &&
        MatchesProfileBytes(
               g_buildProfile->resolveSpellDescriptorRva,
               g_buildProfile->expectedResolveSpellDescriptorEntry,
               sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry),
               "spell descriptor resolver") &&
        MatchesProfileBytes(
               g_buildProfile->researchCompletionNamePushRva,
               g_buildProfile->expectedResearchCompletionNamePush,
               sizeof(g_buildProfile->expectedResearchCompletionNamePush),
               "research completion name") &&
        MatchesProfileBytes(
               g_buildProfile->refreshResearchRowsRva,
               g_buildProfile->expectedRefreshResearchRowsEntry,
               sizeof(g_buildProfile->expectedRefreshResearchRowsEntry),
               "research rows refresh") &&
        MatchesProfileBytes(
               g_buildProfile->refreshSingleResearchRowRva,
               g_buildProfile->expectedRefreshSingleResearchRowEntry,
               sizeof(g_buildProfile->expectedRefreshSingleResearchRowEntry),
               "research row refresh") &&
        MatchesProfileBytes(
               g_buildProfile->canSubmitResearchRva,
               g_buildProfile->expectedCanSubmitResearchEntry,
               sizeof(g_buildProfile->expectedCanSubmitResearchEntry),
               "research validation") &&
        MatchesProfileBytes(
               g_buildProfile->submitResearchCommandRva,
               g_buildProfile->expectedSubmitResearchCommandEntry,
               sizeof(g_buildProfile->expectedSubmitResearchCommandEntry),
               "research command submission") &&
        MatchesProfileBytes(
               g_buildProfile->researchCompletionRva,
               g_buildProfile->expectedResearchCompletionEntry,
               sizeof(g_buildProfile->expectedResearchCompletionEntry),
               "research completion") &&
        ValidateResearchCompletionDispatchSlot() &&
        MatchesProfileBytes(
               g_buildProfile->rageCommandDispatchRva,
               g_buildProfile->expectedRageCommandDispatch,
               sizeof(g_buildProfile->expectedRageCommandDispatch),
               "Rage command dispatch") &&
        MatchesProfileBytes(
               g_buildProfile->ragePrivateBranchRva,
               g_buildProfile->expectedRagePrivateBranch,
               sizeof(g_buildProfile->expectedRagePrivateBranch),
               "Rage GPL branch") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignSpellClickRva,
               g_buildProfile->expectedSovereignSpellClickEntry,
               sizeof(g_buildProfile->expectedSovereignSpellClickEntry),
               "sovereign spell target start") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignTargetManagerRva,
               g_buildProfile->expectedSovereignTargetManagerEntry,
               sizeof(g_buildProfile->expectedSovereignTargetManagerEntry),
               "sovereign target manager") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignTargetCancelRva,
               g_buildProfile->expectedSovereignTargetCancelEntry,
               sizeof(g_buildProfile->expectedSovereignTargetCancelEntry),
               "sovereign target cancellation entry") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignCursorTransitionRva,
               g_buildProfile->expectedSovereignCursorTransition,
               sizeof(g_buildProfile->expectedSovereignCursorTransition),
               "sovereign cursor transition") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignTargetCommitCallRva,
               g_buildProfile->expectedSovereignTargetCommitCall,
               sizeof(g_buildProfile->expectedSovereignTargetCommitCall),
               "sovereign target commit") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignExecutorEntryRva,
               g_buildProfile->expectedSovereignExecutorEntry,
               sizeof(g_buildProfile->expectedSovereignExecutorEntry),
               "sovereign command executor") &&
        MatchesProfileBytes(
               g_buildProfile->sovereignConstructionOverrideRva,
               g_buildProfile->expectedSovereignConstructionOverride,
               g_buildProfile->sovereignConstructionOverrideSize,
               "sovereign spell-unit selection");
}

bool ValidateAlchemistPrivateOilRowsProfile() {
    return MatchesProfileBytes(
               g_buildProfile->heroEnchantmentsSwitchRva,
               g_buildProfile->expectedHeroEnchantmentsSwitch,
               sizeof(g_buildProfile->expectedHeroEnchantmentsSwitch),
               "AP78 Enchantments stock switch") &&
        MatchesProfileBytes(
               g_buildProfile->speedTonicRowStringCallRva,
               g_buildProfile->expectedSpeedTonicRowStringCall,
               sizeof(g_buildProfile->expectedSpeedTonicRowStringCall),
               "AP78 Speed Tonic row string assignment") &&
        MatchesProfileBytes(
               g_buildProfile->stockStringAssignRva,
               g_buildProfile->expectedStockStringAssignEntry,
               sizeof(g_buildProfile->expectedStockStringAssignEntry),
               "AP78 stock string assignment function");
}

bool ValidatePrivateNameGeneratorProfile() {
    return MatchesProfileBytes(
               g_buildProfile->nameRegistryCompletionRva,
               g_buildProfile->expectedNameRegistryCompletion,
               sizeof(g_buildProfile->expectedNameRegistryCompletion),
               "name registry completion") &&
        MatchesProfileBytes(
               g_buildProfile->stockOperatorNewRva,
               g_buildProfile->expectedStockOperatorNewEntry,
               sizeof(g_buildProfile->expectedStockOperatorNewEntry),
               "stock operator new") &&
        MatchesProfileBytes(
               g_buildProfile->nameGeneratorFactoryRva,
               g_buildProfile->expectedNameGeneratorFactoryEntry,
               sizeof(g_buildProfile->expectedNameGeneratorFactoryEntry),
               "name generator factory") &&
        MatchesProfileBytes(
               g_buildProfile->nameGeneratorConstructRva,
               g_buildProfile->expectedNameGeneratorConstructEntry,
               sizeof(g_buildProfile->expectedNameGeneratorConstructEntry),
               "name generator constructor") &&
        MatchesProfileBytes(
               g_buildProfile->nameRegistryFindOrInsertRva,
               g_buildProfile->expectedNameRegistryFindOrInsertEntry,
               sizeof(g_buildProfile->expectedNameRegistryFindOrInsertEntry),
               "name registry insertion");
}

bool ValidateMajestyBuildProfile() {
    // Preflight every site selected by MMCP before installing any hook from
    // those groups. Unselected specialized sites are deliberately untouched
    // and cannot reject an otherwise generic manager launch.
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kExpandedBuildingSlots) &&
        !ValidateCustomGuildFactoryFallback()) {
        return false;
    }
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kAlchemistSecondaryController) &&
        !ValidateAlchemistSecondaryControllerProfile()) {
        return false;
    }
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kAlchemistPrivateOilRows) &&
        !ValidateAlchemistPrivateOilRowsProfile()) {
        return false;
    }
    if ((HasRuntimeCapability(
             MajestyRuntimeCapabilities::kAlchemistNameGenerator) ||
         HasRuntimeCapability(
             MajestyRuntimeCapabilities::kPhantomNameGenerator)) &&
        !ValidatePrivateNameGeneratorProfile()) {
        return false;
    }
    return true;
}

bool __cdecl ResolveManagerIntentText(
    std::uint32_t intentId,
    MajestyStringView* destination) {
    const MajestyStringView* privateText = FindPrivateIntentText(intentId);
    if (privateText == nullptr) {
        // Preserve the complete stock resolver for every ID not explicitly
        // present in the manager registry, including unknown high values.
        return g_stockIntentTextResolver(intentId, destination);
    }
    // This is the stock resolver's successful assignment lifecycle: a null
    // destination is still success; otherwise use Majesty's own string-copy
    // routine with the same 12-byte source view consumed by stock AITX rows.
    if (destination != nullptr) {
        g_privateIntentStringAssign(destination, privateText);
    }
    return true;
}

bool InstallPrivateIntentTextResolver() {
    auto* entry = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->resolveIntentTextRva);
    if (std::memcmp(
            entry,
            g_buildProfile->expectedResolveIntentTextEntry,
            sizeof(g_buildProfile->expectedResolveIntentTextEntry)) != 0) {
        WriteLog(
            "Manager intent hook refused: stock resolver bytes changed after preflight.");
        return false;
    }

    // The first six stock bytes are `push esi; call table_provider`. Recreate
    // that relative call rather than copying it to a different address, then
    // resume at the first unchanged stock instruction. The trampoline thereby
    // preserves stock stack ownership, fallback logging, return value, and
    // destination-string behavior byte for byte.
    constexpr std::size_t kTrampolineBytes = 11;
    auto* trampoline = reinterpret_cast<unsigned char*>(VirtualAlloc(
        nullptr,
        kTrampolineBytes,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        WriteLog(
            "Manager intent hook failed: trampoline allocation was rejected.");
        return false;
    }
    trampoline[0] = 0x56;
    trampoline[1] = 0xE8;
    const auto provider =
        g_imageBase + g_buildProfile->intentTextTableProviderRva;
    const auto providerRelative = static_cast<std::int32_t>(
        provider - (reinterpret_cast<std::uintptr_t>(trampoline) + 6));
    std::memcpy(trampoline + 2, &providerRelative, sizeof(providerRelative));
    trampoline[6] = 0xE9;
    const auto resume =
        g_imageBase + g_buildProfile->resolveIntentTextResumeRva;
    const auto resumeRelative = static_cast<std::int32_t>(
        resume - (reinterpret_cast<std::uintptr_t>(trampoline) + 11));
    std::memcpy(trampoline + 7, &resumeRelative, sizeof(resumeRelative));

    g_stockIntentTextResolver =
        reinterpret_cast<StockIntentTextResolver>(trampoline);
    g_privateIntentStringAssign = reinterpret_cast<StockStringAssign>(
        g_imageBase + g_buildProfile->stockStringAssignRva);

    const auto hookRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&ResolveManagerIntentText) -
        (reinterpret_cast<std::uintptr_t>(entry) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedResolveIntentTextEntry)] = {
        0xE9, 0, 0, 0, 0, 0x90};
    std::memcpy(patch + 1, &hookRelative, sizeof(hookRelative));
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            entry,
            sizeof(patch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        g_stockIntentTextResolver = nullptr;
        g_privateIntentStringAssign = nullptr;
        VirtualFree(trampoline, 0, MEM_RELEASE);
        WriteLog(
            "Manager intent hook failed: the stock resolver is not writable.");
        return false;
    }
    std::memcpy(entry, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(entry, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite(
        "manager-owned activity-text resolver",
        g_buildProfile->resolveIntentTextRva);
    return true;
}

bool InstallCustomGuildFactoryFallback() {
    auto* site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->customGuildFallbackRva);
    unsigned char patch[kCustomGuildFactoryPatchSize] = {};
    BuildCustomGuildFactoryPatch(patch);
    if (std::memcmp(site, patch, sizeof(patch)) == 0) {
        char message[192] = {};
        sprintf_s(
            message,
            "Reused installed stock CG-prefix guild-controller fallback for %s.",
            g_buildProfile->id);
        WriteLog(message);
        return true;
    }
    if (std::memcmp(
            site,
            kStockUnknownDialogEpilogue,
            sizeof(kStockUnknownDialogEpilogue)) != 0) {
        WriteLog("Custom-guild fallback installation refused: stock epilogue bytes are unknown.");
        return false;
    }
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            site, sizeof(patch), PAGE_EXECUTE_READWRITE, &oldProtection)) {
        WriteLog("Custom-guild fallback installation failed: VirtualProtect rejected the stock epilogue.");
        return false;
    }
    std::memcpy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite(
        "in-memory stock CG-prefix guild-controller fallback",
        g_buildProfile->customGuildFallbackRva);
    return true;
}

std::uint32_t SendControllerMessage(
    std::uint32_t controller,
    std::uint32_t controlId,
    std::uint32_t message,
    std::uint32_t parameter,
    std::uint32_t value) {
    if (controller == 0) {
        return 0;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    if (panel == nullptr) {
        return 0;
    }
    auto** vtable = *reinterpret_cast<void***>(panel);
    using SendControlMessage = std::uint32_t (__thiscall*)(
        void*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
    auto send = reinterpret_cast<SendControlMessage>(vtable[0x68 / sizeof(void*)]);
    return send(panel, controlId, message, parameter, value);
}

bool SetControllerControlInteger(
    std::uint32_t controller,
    std::uint32_t bindingId,
    int value) {
    if (controller == 0) {
        return false;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    if (panel == nullptr) {
        return false;
    }
    auto** vtable = *reinterpret_cast<void***>(panel);
    using SetControlInteger = void (__thiscall*)(
        void*, std::uint32_t, int, std::uint32_t);
    auto setInteger = reinterpret_cast<SetControlInteger>(
        vtable[0x5C / sizeof(void*)]);
    // Literal AP22 Healing Potion count dispatch at Beta2
    // 0x004A34B1..0x004A34D0. AP22 targets the numeric binding embedded in
    // the type-5 quantity record, passes the calculated integer, and preserves
    // the stock trailing zero consumed by the three-argument panel virtual.
    setInteger(panel, bindingId, value, 0u);
    return true;
}

void SetControllerControlVisible(
    std::uint32_t controller, std::uint32_t controlId, bool visible) {
    if (controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    if (panel == nullptr) {
        return;
    }
    auto** vtable = *reinterpret_cast<void***>(panel);
    using SetControlVisible = void (__thiscall*)(void*, std::uint32_t, std::uint32_t);
    auto setVisible = reinterpret_cast<SetControlVisible>(vtable[0x20 / sizeof(void*)]);
    setVisible(panel, controlId, visible ? 1u : 0u);
}

DWORD SimulationClock() {
    return *reinterpret_cast<volatile DWORD*>(g_imageBase + g_buildProfile->simulationClockRva);
}

unsigned char* LaboratoryPanelContext() {
    using GetPanelContext = void* (__thiscall*)(void*);
    const auto parentController = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_cgalController, 0, 0));
    if (parentController == 0) {
        return nullptr;
    }
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    return static_cast<unsigned char*>(
        getPanelContext(reinterpret_cast<void*>(parentController)));
}

int ReadPackedAttributeValue(
    void* context, std::uint32_t attributeId, std::uint32_t fallback = 0) {
    using ReadPackedAttribute = int (__thiscall*)(
        void*, std::uint32_t, std::uint32_t);
    auto readPackedAttribute = reinterpret_cast<ReadPackedAttribute>(
        g_imageBase + g_buildProfile->readPackedAttributeRva);
    return readPackedAttribute(context, attributeId, fallback);
}

void WritePackedAttributeValue(
    void* context, std::uint32_t attributeId, int value) {
    // Stock research completion writes packed attributes through the agent's
    // virtual +0x124 setter. Use that same entry and exact (attribute, value)
    // argument order for the short ownership handoff around native calls.
    auto** vtable = *reinterpret_cast<void***>(context);
    using WritePackedAttribute = void (__thiscall*)(
        void*, std::uint32_t, int);
    auto writePackedAttribute = reinterpret_cast<WritePackedAttribute>(
        vtable[0x124 / sizeof(void*)]);
    writePackedAttribute(context, attributeId, value);
}

LaboratoryActivitySnapshot CaptureLaboratoryActivity(void* context) {
    LaboratoryActivitySnapshot snapshot = {};
    snapshot.command = ReadPackedAttributeValue(
        context, kCurrentResearchAttributeId);
    snapshot.startedAt = ReadPackedAttributeValue(
        context, kResearchStartedAtAttributeId);
    snapshot.duration = ReadPackedAttributeValue(
        context, kResearchDurationAttributeId);
    return snapshot;
}

void RestoreLaboratoryActivity(
    void* context, const LaboratoryActivitySnapshot& snapshot) {
    WritePackedAttributeValue(
        context, kCurrentResearchAttributeId, snapshot.command);
    WritePackedAttributeValue(
        context, kResearchStartedAtAttributeId, snapshot.startedAt);
    WritePackedAttributeValue(
        context, kResearchDurationAttributeId, snapshot.duration);
}

void ClearLaboratoryActivity(void* context) {
    const LaboratoryActivitySnapshot empty = {};
    RestoreLaboratoryActivity(context, empty);
}

bool LaboratoryResearchIsActive() {
    return g_laboratoryResearchOwner.pending ||
        g_laboratoryResearchOwner.active;
}

bool LaboratoryResearchMatches(
    const void* context, std::uint32_t recipe) {
    return g_laboratoryResearchOwner.active &&
        g_laboratoryResearchOwner.context == context &&
        g_laboratoryResearchOwner.recipe == recipe;
}

int LaboratoryBuildingLevel(const void* context) {
    // AP99 0x004A91A2 derives the research tier from the high byte of +0x7C:
    // 0x32 is level 2, 0x33 is level 3, and every other stock value is level 1.
    const auto encoded =
        *reinterpret_cast<const std::uint32_t*>(
            static_cast<const unsigned char*>(context) + 0x7C) &
        0xFF000000u;
    if (encoded == 0x32000000u) {
        return 2;
    }
    return encoded == 0x33000000u ? 3 : 1;
}

bool LaboratoryUpgradeResearchComplete(void* context) {
    if (context == nullptr) {
        return false;
    }
    const int level = LaboratoryBuildingLevel(context);
    if (level == 1) {
        return ReadPackedAttributeValue(
            context, kWeaponOilCompletionAttributeId, 0) != 0;
    }
    if (level == 2) {
        return ReadPackedAttributeValue(
            context, kPhoenixPhialCompletionAttributeId, 0) != 0;
    }
    return true;
}

void ApplyLaboratoryUpgradeResearchGate(
    std::uint32_t controller, void* context) {
    if (controller == 0 || context == nullptr ||
        LaboratoryUpgradeResearchComplete(context)) {
        return;
    }
    // Guardhouse AP17 delegates its main-panel upgrade row to the stock base
    // presenter. An unmet prerequisite keeps control 0x1F47 visible but sends
    // its disabled message, then hides the 0x1F4F price child. Privatize only
    // the prerequisite attribute selection for the Laboratory's two tiers.
    SendControllerMessage(
        controller, kBuildingUpgradeControlId, 0x0A, 1, 0);
    SetControllerControlVisible(
        controller, kBuildingUpgradePriceControlId, false);
}

void RefreshWeaponOilResearch(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    unsigned char* context = LaboratoryPanelContext();
    if (panel == nullptr || context == nullptr) {
        return;
    }
    // AP99's iterator at 0x004A93D0 discovers only stock control IDs in the
    // hard-coded [0x1388,0x13EC) range, then calls this exact row presenter.
    // Our private 0x2A13 row must enter after that discovery filter. The stock
    // presenter still owns level/current-research checks, completion-attribute
    // lockout, price, enabled state, art swap, and tooltip refresh.
    using RefreshSingleResearchRow = void (__cdecl*)(
        void*, void*, std::uint32_t);
    auto refreshSingleResearchRow = reinterpret_cast<RefreshSingleResearchRow>(
        g_imageBase + g_buildProfile->refreshSingleResearchRowRva);
    refreshSingleResearchRow(panel, context, kWeaponOilResearchControlId);
}

void RefreshPhoenixPhialResearch(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    unsigned char* context = LaboratoryPanelContext();
    if (panel == nullptr || context == nullptr) {
        return;
    }
    using RefreshSingleResearchRow = void (__cdecl*)(
        void*, void*, std::uint32_t);
    auto refreshSingleResearchRow = reinterpret_cast<RefreshSingleResearchRow>(
        g_imageBase + g_buildProfile->refreshSingleResearchRowRva);
    refreshSingleResearchRow(panel, context, kPhoenixPhialResearchControlId);
}

void RefreshInvigoratingElixer(std::uint32_t controller) {
    if (controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    using GetUiManager = void* (__cdecl*)();
    using GetCurrentPlayer = void* (__thiscall*)(void*);
    using RefreshSingleSpellRow = void (__cdecl*)(
        void*, void*, std::uint32_t, std::uint32_t);
    auto getUiManager = reinterpret_cast<GetUiManager>(
        g_imageBase + g_buildProfile->uiManagerRva);
    auto getCurrentPlayer = reinterpret_cast<GetCurrentPlayer>(
        g_imageBase + g_buildProfile->getCurrentPlayerRva);
    void* manager = getUiManager();
    void* player = manager == nullptr ? nullptr : getCurrentPlayer(manager);
    if (panel == nullptr || player == nullptr) {
        return;
    }
    // AP69's iterator at 0x004AE5C0 discovers only stock spell IDs. Invoke
    // its exact per-row worker for the private Vigor family, preserving the
    // native descriptor level comparison, icon/price state, and text update.
    auto refreshSingleSpellRow = reinterpret_cast<RefreshSingleSpellRow>(
        g_imageBase + g_buildProfile->refreshSingleSpellRowRva);
    refreshSingleSpellRow(
        panel, player, kInvigoratingElixerControlId, 0);
}

int LaboratoryReagentStock() {
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        return 0;
    }
    const int value = ReadPackedAttributeValue(
        context, kReagentStockAttributeId, 0);
    return value < 0 ? 0 : value;
}

void UpdateLaboratoryReagentMeter(std::uint32_t controller) {
    if (controller == 0) {
        return;
    }
    const int stock = LaboratoryReagentStock();
    // The AP22-style inventory count is ordinary Laboratory storage, not a
    // level-3 sovereign-spell control. Keep it visible at every Laboratory
    // level while the level gate continues to hide only Infusion and Stone.
    SetControllerControlVisible(controller, kReagentMeterLabelControlId, true);
    SetControllerControlVisible(controller, kReagentMeterCountControlId, true);
    const bool countPublished = SetControllerControlInteger(
        controller, kReagentMeterCountBindingId, stock);
    if (stock != g_lastReagentMeterTraceStock) {
        g_lastReagentMeterTraceStock = stock;
        char trace[160] = {};
        sprintf_s(
            trace,
            "Reagent count refresh: stock=%d AP22-binding=%s.",
            stock,
            countPublished ? "published" : "unavailable");
        WriteLog(trace);
    }
}

void RefreshSovereignBrewingRow(
    std::uint32_t controller, std::uint32_t controlId) {
    if (controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    unsigned char* context = LaboratoryPanelContext();
    using GetUiManager = void* (__cdecl*)();
    using GetCurrentPlayer = void* (__thiscall*)(void*);
    using RefreshSingleSpellRow = void (__cdecl*)(
        void*, void*, std::uint32_t, std::uint32_t);
    auto getUiManager = reinterpret_cast<GetUiManager>(
        g_imageBase + g_buildProfile->uiManagerRva);
    auto getCurrentPlayer = reinterpret_cast<GetCurrentPlayer>(
        g_imageBase + g_buildProfile->getCurrentPlayerRva);
    void* manager = getUiManager();
    void* player = manager == nullptr ? nullptr : getCurrentPlayer(manager);
    if (panel == nullptr || context == nullptr || player == nullptr) {
        return;
    }
    auto refreshSingleSpellRow = reinterpret_cast<RefreshSingleSpellRow>(
        g_imageBase + g_buildProfile->refreshSingleSpellRowRva);
    refreshSingleSpellRow(panel, player, controlId, 0);

    // AP69's stock level gate owns the compound row. Preserve its exact result
    // for the Laboratory: the action and icon do not exist before level 3;
    // once unlocked, only the private Reagent/completion availability differs.
    const bool levelAvailable = LaboratoryBuildingLevel(context) >= 3;
    SetControllerControlVisible(controller, controlId, levelAvailable);
    SetControllerControlVisible(
        controller, controlId + 1000, levelAvailable);
    SetControllerControlVisible(controller, controlId - 1000, false);
    if (levelAvailable) {
        const bool unavailable =
            LaboratoryReagentStock() < kReagentActionCost ||
            (controlId == kArcaneInfusionVisualControlId &&
                StockArcaneInfusionComplete());
        SendControllerMessage(
            controller, controlId, 0x0A, unavailable ? 1 : 0, 0);
    }
}

void RefreshSovereignBrewingRows(std::uint32_t controller) {
    RefreshSovereignBrewingRow(controller, kArcaneInfusionVisualControlId);
    RefreshSovereignBrewingRow(controller, kPhilosophersStoneVisualControlId);
}

void UpdateSovereignBrewingGate(std::uint32_t controller) {
    if (controller == 0) {
        return;
    }
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        return;
    }
    const bool levelAvailable = LaboratoryBuildingLevel(context) >= 3;
    const std::uint32_t controlIds[2] = {
        kArcaneInfusionVisualControlId,
        kPhilosophersStoneVisualControlId};
    for (const std::uint32_t controlId : controlIds) {
        // AP69 has already constructed and presented this complete stock row.
        // The Laboratory changes only the private Reagent gate and suppresses
        // the unused stock gold child; do not run AP69's presenter again from
        // the game-update loop.
        SetControllerControlVisible(controller, controlId, levelAvailable);
        SetControllerControlVisible(
            controller, controlId + 1000, levelAvailable);
        SetControllerControlVisible(controller, controlId - 1000, false);
        if (levelAvailable) {
            const bool unavailable =
                LaboratoryReagentStock() < kReagentActionCost ||
                (controlId == kArcaneInfusionVisualControlId &&
                    (StockArcaneInfusionComplete() ||
                     InterlockedCompareExchange(
                         &g_arcaneInfusionRageHandle, 0, 0) != 0));
            SendControllerMessage(
                controller, controlId, 0x0A, unavailable ? 1 : 0, 0);
        }
    }
}

void UpdateWeaponOilPresentation(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        return;
    }
    const bool active = LaboratoryResearchMatches(
        context, kWeaponOilResearchControlId);

    if (active) {
        // AP17's exact active display-swap order, with its progress surface
        // privatized to the AP24 control class already proven stable in CGBR.
        SetControllerControlVisible(
            controller, kWeaponOilResearchControlId, false);
        SetControllerControlVisible(
            controller, kWeaponOilResearchPriceControlId, false);
        SetControllerControlVisible(
            controller, kWeaponOilActiveDisplayControlId, true);
        SetControllerControlVisible(
            controller, kWeaponOilProgressControlId, true);
        const DWORD now = SimulationClock();
        const DWORD elapsed = now > g_laboratoryResearchOwner.startedAt
            ? now - g_laboratoryResearchOwner.startedAt
            : 0;
        std::uint32_t progress[4] = {
            7, elapsed, 0, g_laboratoryResearchOwner.duration};
        SendControllerMessage(
            controller,
            kWeaponOilProgressControlId,
            0x29,
            0,
            reinterpret_cast<std::uint32_t>(progress));
        SendControllerMessage(
            controller, kWeaponOilProgressControlId, 0x08, 0, 0);
    } else {
        // AP17's exact inverse swap. AP99 refresh owns whether the restored
        // Weapon Oil row is visible, enabled, researching, or permanently
        // completed. Do not re-show the action here: AP99 0x004A9160 may
        // have hidden its complete compound row for a building-level gate.
        SetControllerControlVisible(
            controller, kWeaponOilProgressControlId, false);
        SetControllerControlVisible(
            controller, kWeaponOilActiveDisplayControlId, false);
        if (LaboratoryResearchIsActive()) {
            SendControllerMessage(
                controller, kWeaponOilResearchControlId, 0x0A, 1, 0);
        }
    }
}

void UpdatePhoenixPhialPresentation(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        return;
    }
    const bool active = LaboratoryResearchMatches(
        context, kPhoenixPhialResearchControlId);

    if (active) {
        SetControllerControlVisible(controller, kPhoenixPhialResearchControlId, false);
        SetControllerControlVisible(
            controller, kPhoenixPhialResearchPriceControlId, false);
        SetControllerControlVisible(controller, kPhoenixPhialActiveDisplayControlId, true);
        SetControllerControlVisible(controller, kPhoenixPhialProgressControlId, true);
        const DWORD now = SimulationClock();
        const DWORD elapsed = now > g_laboratoryResearchOwner.startedAt
            ? now - g_laboratoryResearchOwner.startedAt
            : 0;
        std::uint32_t progress[4] = {
            7, elapsed, 0, g_laboratoryResearchOwner.duration};
        SendControllerMessage(
            controller,
            kPhoenixPhialProgressControlId,
            0x29,
            0,
            reinterpret_cast<std::uint32_t>(progress));
        SendControllerMessage(
            controller, kPhoenixPhialProgressControlId, 0x08, 0, 0);
    } else {
        // As with Weapon Oil, AP99 0x004A9160 exclusively owns restoration
        // of the compound Phoenix row. In particular, its descriptor-level
        // gate hides action, icon, and price together at Laboratory level 1.
        SetControllerControlVisible(controller, kPhoenixPhialProgressControlId, false);
        SetControllerControlVisible(controller, kPhoenixPhialActiveDisplayControlId, false);
        if (LaboratoryResearchIsActive()) {
            SendControllerMessage(
                controller, kPhoenixPhialResearchControlId, 0x0A, 1, 0);
        }
    }
}

void* StockCurrentPlayerAgent() {
    // AP24 constructor 0x004B1620 obtains the player's agent from the panel
    // context's +0x80 player slot, and refresh 0x004B1340 reads packed
    // attribute APB\x07 through 0x005B9FD0. Reproduce that exact read so Vigor
    // and Rage share Majesty's native Palace-owned exclusion state.
    using GetPanelContext = void* (__thiscall*)(void*);
    using GetUiManager = void* (__cdecl*)();
    using GetPlayerAgent = void* (__thiscall*)(void*, std::uint32_t);
    const auto parentController = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_cgalController, 0, 0));
    if (parentController == 0) {
        return nullptr;
    }
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    auto* context = static_cast<unsigned char*>(
        getPanelContext(reinterpret_cast<void*>(parentController)));
    if (context == nullptr) {
        return nullptr;
    }
    auto getUiManager = reinterpret_cast<GetUiManager>(g_imageBase + g_buildProfile->uiManagerRva);
    auto getPlayerAgent = reinterpret_cast<GetPlayerAgent>(
        g_imageBase + g_buildProfile->getPlayerAgentRva);
    void* manager = getUiManager();
    if (manager == nullptr) {
        return nullptr;
    }
    return getPlayerAgent(
        manager, *reinterpret_cast<std::uint32_t*>(context + 0x80));
}

int StockRageOfKrolmCount() {
    void* playerAgent = StockCurrentPlayerAgent();
    if (playerAgent == nullptr) {
        return 0;
    }
    return ReadPackedAttributeValue(playerAgent, kRageOfKrolmCountAttributeId, 0);
}

bool StockArcaneInfusionComplete() {
    // ResearchArrows is a stock persistent completion bit. The Palace never
    // owns Guardhouse research, so the same per-agent attribute is a clean,
    // save-safe owner for this one-per-kingdom Alchemist infusion.
    void* playerAgent = StockCurrentPlayerAgent();
    return playerAgent != nullptr && ReadPackedAttributeValue(
        playerAgent, kWeaponOilCompletionAttributeId, 0) != 0;
}

int StockCurrentPlayerGold() {
    // AP24 click handler 0x004B2A60 obtains the UI manager, resolves its
    // current player, and invokes that player's vtable +0x20 data reader with
    // APP (Gold) before it deducts or submits Rage. Reproduce the same read at
    // Vigor's private boundary; its GPL remains the payment/effect owner.
    using GetUiManager = void* (__cdecl*)();
    using GetCurrentPlayer = void* (__thiscall*)(void*);
    using GetPlayerData = int (__thiscall*)(void*, std::uint32_t);
    auto getUiManager = reinterpret_cast<GetUiManager>(
        g_imageBase + g_buildProfile->uiManagerRva);
    auto getCurrentPlayer = reinterpret_cast<GetCurrentPlayer>(
        g_imageBase + g_buildProfile->getCurrentPlayerRva);
    void* manager = getUiManager();
    void* player = manager == nullptr ? nullptr : getCurrentPlayer(manager);
    if (player == nullptr) {
        return -1;
    }
    auto** vtable = *reinterpret_cast<void***>(player);
    if (vtable == nullptr || vtable[0x20 / sizeof(void*)] == nullptr) {
        return -1;
    }
    auto getPlayerData = reinterpret_cast<GetPlayerData>(
        vtable[0x20 / sizeof(void*)]);
    return getPlayerData(player, kPlayerGoldDataId);
}

void UpdateBrewingPresentation(std::uint32_t controller) {
    if (controller == 0 ||
        controller != static_cast<std::uint32_t>(
            InterlockedCompareExchange(&g_customBrewingController, 0, 0))) {
        return;
    }
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        return;
    }
    const bool vigorLevelAvailable = LaboratoryBuildingLevel(context) >= 3;
    const DWORD now = SimulationClock();
    DWORD elapsed = now - g_invigoratingElixerStartedAt;
    bool active = InterlockedCompareExchange(
        &g_invigoratingElixerActive, 0, 0) != 0;
    if (active && elapsed >= kInvigoratingElixerDurationMs) {
        InterlockedExchange(&g_invigoratingElixerActive, 0);
        active = false;
        elapsed = 0;
    }

    UpdateWeaponOilPresentation(controller);
    UpdatePhoenixPhialPresentation(controller);
    UpdateLaboratoryReagentMeter(controller);
    UpdateSovereignBrewingGate(controller);
    if (active && vigorLevelAvailable) {
        const DWORD traceSecond = elapsed / 1000;
        const bool traceProgress =
            traceSecond != g_lastBrewingProgressTraceSecond;
        if (traceProgress) {
            g_lastBrewingProgressTraceSecond = traceSecond;
            char trace[160] = {};
            sprintf_s(
                trace,
                "Brewing progress dispatch: controller=0x%08X now=%u start=%u elapsed=%u.",
                controller,
                now,
                g_invigoratingElixerStartedAt,
                elapsed);
            WriteLog(trace);
        }
        // AP24's active branch, in stock order: replace the ordinary Rage
        // button/price pair with the complete 0x227A/INSr display pair.
        SetControllerControlVisible(
            controller, kInvigoratingElixerControlId, false);
        SetControllerControlVisible(
            controller, kInvigoratingElixerIconControlId, true);
        SetControllerControlVisible(
            controller, kInvigoratingElixerPriceControlId, false);
        SetControllerControlVisible(
            controller, kInvigoratingElixerActiveDisplayControlId, true);
        SetControllerControlVisible(
            controller, kInvigoratingElixerProgressControlId, true);
        // This is AP24's exact INSr message contract: operation 7, elapsed
        // simulation time, zero origin, and total simulation duration.
        std::uint32_t progress[4] = {
            7, elapsed, 0, kInvigoratingElixerDurationMs};
        const auto progressDispatchResult = SendControllerMessage(
            controller,
            kInvigoratingElixerProgressControlId,
            0x29,
            0,
            reinterpret_cast<std::uint32_t>(progress));
        if (traceProgress) {
            char trace[128] = {};
            sprintf_s(
                trace,
                "Brewing progress message result: 0x%08X.",
                progressDispatchResult);
            WriteLog(trace);
        }
        SendControllerMessage(
            controller,
            kInvigoratingElixerProgressControlId,
            0x08,
            0,
            0);
    } else {
        // AP24's inactive branch performs the exact inverse display swap. An
        // active Palace count remains global, but a selected under-level Lab
        // must still hide the complete Vigor family just as AP69 hides its
        // ordinary action/icon/price row before descriptor level 3.
        // AP69 0x004AE4D0 already presented this row during setup/event
        // refresh and owns its level-3 enabled state and registered price.
        // Restore only the AP24 display swap; never send an enabled state or
        // price text here because either would overwrite AP69's stock gate.
        SetControllerControlVisible(
            controller, kInvigoratingElixerControlId, vigorLevelAvailable);
        SetControllerControlVisible(
            controller, kInvigoratingElixerIconControlId, vigorLevelAvailable);
        SetControllerControlVisible(
            controller, kInvigoratingElixerPriceControlId, vigorLevelAvailable);
        SetControllerControlVisible(
            controller, kInvigoratingElixerActiveDisplayControlId, false);
        SetControllerControlVisible(
            controller, kInvigoratingElixerProgressControlId, false);
        if (StockRageOfKrolmCount() != 0 ||
            LaboratoryReagentStock() < kInvigoratingElixerReagentCost ||
            InterlockedCompareExchange(&g_arcaneInfusionRageHandle, 0, 0) != 0) {
            // AP24's Palace-owned mutual-exclusion state can only make an
            // otherwise stock-presented row more restrictive.
            SendControllerMessage(
                controller, kInvigoratingElixerControlId, 0x0A, 1, 0);
        }
    }
}

bool CaptureSubmittedLaboratoryResearch(
    const LaboratoryActivitySnapshot& activityToRestore) {
    if (!g_laboratoryResearchOwner.pending ||
        g_laboratoryResearchOwner.context == nullptr) {
        return false;
    }
    const LaboratoryActivitySnapshot submitted =
        CaptureLaboratoryActivity(g_laboratoryResearchOwner.context);
    if (submitted.command !=
            static_cast<int>(g_laboratoryResearchOwner.recipe) ||
        submitted.duration <= 0) {
        return false;
    }

    RestoreLaboratoryActivity(
        g_laboratoryResearchOwner.context, activityToRestore);
    g_laboratoryResearchOwner.startedAt =
        static_cast<DWORD>(submitted.startedAt);
    g_laboratoryResearchOwner.duration =
        static_cast<DWORD>(submitted.duration);
    g_laboratoryResearchOwner.pending = false;
    g_laboratoryResearchOwner.active = true;

    char trace[192] = {};
    sprintf_s(
        trace,
        "Captured queued Laboratory research 0x%08X tuple %u/%u and restored AP10 activity.",
        g_laboratoryResearchOwner.recipe,
        g_laboratoryResearchOwner.startedAt,
        g_laboratoryResearchOwner.duration);
    WriteLog(trace);
    return true;
}

void StageLaboratoryResearchForStockCompletion() {
    unsigned char* context = g_laboratoryResearchOwner.context;
    WritePackedAttributeValue(
        context,
        kCurrentResearchAttributeId,
        static_cast<int>(g_laboratoryResearchOwner.recipe));
    WritePackedAttributeValue(
        context,
        kResearchStartedAtAttributeId,
        static_cast<int>(g_laboratoryResearchOwner.startedAt));
    WritePackedAttributeValue(
        context,
        kResearchDurationAttributeId,
        static_cast<int>(g_laboratoryResearchOwner.duration));
}

void __cdecl ResearchCompletionBridge(
    std::uint32_t commandOwner,
    void* context,
    std::uint32_t eventRecord,
    std::uint32_t eventArgument,
    std::uint32_t eventType) {
    const bool privateLaboratoryCompletion =
        eventType == 2 &&
        g_laboratoryResearchOwner.active &&
        g_laboratoryResearchOwner.context == context;
    if (!privateLaboratoryCompletion) {
        g_stockResearchCompletion(
            commandOwner, context, eventRecord, eventArgument, eventType);
        return;
    }

    // Stock event 0x2009 is the authoritative Blacksmith completion boundary.
    // The private owner keeps AP10 recruitment in the building's packed tuple,
    // so publish AP99's captured tuple only for this literal stock callback.
    // This avoids predicting the event from elapsed time and preserves the
    // original descriptor lookup, attribute write, alert, and cleanup order.
    const LaboratoryActivitySnapshot liveActivity =
        CaptureLaboratoryActivity(context);
    StageLaboratoryResearchForStockCompletion();

    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveResearchDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    const std::uint32_t recipe = g_laboratoryResearchOwner.recipe;
    const auto* expectedDescriptor = recipe == kWeaponOilResearchControlId
        ? g_weaponOilResearchDescriptor
        : g_phoenixPhialResearchDescriptor;
    if (resolveResearchDescriptor(recipe) != expectedDescriptor) {
        RestoreLaboratoryActivity(context, liveActivity);
        WriteLog(
            "Laboratory research completion refused: AP99 lost its private descriptor registration.");
        return;
    }

    InterlockedExchange(&g_laboratoryResearchCompletionStaged, 1);
    g_stockResearchCompletion(
        commandOwner, context, eventRecord, eventArgument, eventType);
    const LaboratoryActivitySnapshot stockResult =
        CaptureLaboratoryActivity(context);
    const bool completed = stockResult.command != static_cast<int>(recipe);
    RestoreLaboratoryActivity(context, liveActivity);
    if (!completed) {
        InterlockedExchange(&g_laboratoryResearchCompletionStaged, 0);
        WriteLog(
            "Stock event 0x2009 returned without retiring Laboratory research.");
        return;
    }

    g_laboratoryResearchOwner = {};
    InterlockedExchange(&g_laboratoryResearchCompletedThisUpdate, 1);
    char trace[128] = {};
    sprintf_s(
        trace,
        "Observed native event 0x2009 complete Laboratory research 0x%08X.",
        recipe);
    WriteLog(trace);
}

void __fastcall GameUpdateRefreshBridge(void* gameState, void*) {
    // This call site is Majesty's stock state-3 update dispatch. Run the
    // original update first, exactly as the unmodified main loop does, then
    // refresh the live Brewing row on that same main/UI thread. The custom
    // Laboratory research owner also advances here so it uses the stock
    // simulation clock and never introduces a timer or worker thread.
    LaboratoryActivitySnapshot activityBeforeUpdate = {};
    const bool researchSubmissionPending =
        g_laboratoryResearchOwner.pending &&
        g_laboratoryResearchOwner.context != nullptr;
    if (researchSubmissionPending) {
        activityBeforeUpdate = CaptureLaboratoryActivity(
            g_laboratoryResearchOwner.context);
    }

    g_stockGameUpdate(gameState);
    if (researchSubmissionPending &&
        CaptureSubmittedLaboratoryResearch(activityBeforeUpdate) &&
        InterlockedCompareExchange(&g_customBrewingActive, 0, 0) != 0) {
        const auto controller = static_cast<std::uint32_t>(
            InterlockedCompareExchange(&g_customBrewingController, 0, 0));
        RefreshWeaponOilResearch(controller);
        RefreshPhoenixPhialResearch(controller);
    }
    if (InterlockedExchange(
            &g_laboratoryResearchCompletedThisUpdate, 0) != 0) {
        if (InterlockedCompareExchange(&g_customBrewingActive, 0, 0) != 0) {
            const auto controller = static_cast<std::uint32_t>(
                InterlockedCompareExchange(&g_customBrewingController, 0, 0));
            RefreshWeaponOilResearch(controller);
            RefreshPhoenixPhialResearch(controller);
        }
        InterlockedExchange(&g_laboratoryResearchCompletionStaged, 0);
        // Event 0x2009 has already completed and refreshed the private rows in
        // this update. Resume ordinary AP69 presentation on the next update.
        return;
    }
    if (InterlockedCompareExchange(&g_customBrewingActive, 0, 0) == 0) {
        return;
    }
    const auto controller = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_customBrewingController, 0, 0));
    UpdateBrewingPresentation(controller);
}

bool InstallGameUpdateRefreshBridge() {
    auto* callSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->gameUpdateCallRva);
    if (std::memcmp(
            callSite,
            g_buildProfile->expectedGameUpdateCall,
            sizeof(g_buildProfile->expectedGameUpdateCall)) != 0) {
        WriteLog(
            "Brewing refresh bridge refused: stock game-update call bytes are unknown.");
        return false;
    }
    g_stockGameUpdate = reinterpret_cast<GameUpdate>(
        g_imageBase + g_buildProfile->gameUpdateRva);
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&GameUpdateRefreshBridge) -
        (reinterpret_cast<std::uintptr_t>(callSite) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedGameUpdateCall)] = {
        0xE8, 0, 0, 0, 0};
    std::memcpy(patch + 1, &relative, sizeof(relative));

    DWORD oldProtection = 0;
    if (!VirtualProtect(
            callSite,
            sizeof(patch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        WriteLog(
            "Brewing refresh bridge failed: VirtualProtect rejected the call site.");
        return false;
    }
    std::memcpy(callSite, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), callSite, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(callSite, sizeof(patch), oldProtection, &ignored);
    WriteLog(
        "Installed Brewing refresh bridge on Majesty's stock state-3 update dispatch.");
    return true;
}

int HandleInvigoratingElixer(std::uint32_t controller) {
    if (InterlockedCompareExchange(&g_invigoratingElixerActive, 0, 0) != 0) {
        WriteLog("Ignored Invigorating Elixer while its thirty-second effect is active.");
        return 0;
    }
    if (StockRageOfKrolmCount() != 0) {
        WriteLog("Ignored Invigorating Elixer while stock Rage owns the Palace count.");
        return 0;
    }
    if (InterlockedCompareExchange(&g_arcaneInfusionRageHandle, 0, 0) != 0) {
        WriteLog("Ignored Invigorating Elixer while Arcane Infusion is pending.");
        return 0;
    }
    if (LaboratoryReagentStock() < kInvigoratingElixerReagentCost) {
        UpdateBrewingPresentation(controller);
        WriteLog("Stock-style private gate rejected Vigor: no Reagent is stored.");
        return 0;
    }
    const int currentGold = StockCurrentPlayerGold();
    if (currentGold < static_cast<int>(kInvigoratingElixerGoldCost)) {
        char trace[160] = {};
        sprintf_s(
            trace,
            "Stock AP24 affordability gate rejected Invigorating Elixer: gold=%d cost=%u.",
            currentGold,
            kInvigoratingElixerGoldCost);
        WriteLog(trace);
        return 0;
    }
    using GetPanelContext = void* (__thiscall*)(void*);
    struct CommandMetadata {
        std::uint32_t first;
        std::uint32_t second;
    };
    using GetCommandMetadata = void (__thiscall*)(void*, CommandMetadata*);
    using SubmitBuildingCommand = void (__cdecl*)(
        std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    auto getCommandMetadata = reinterpret_cast<GetCommandMetadata>(
        g_imageBase + g_buildProfile->getCommandMetadataRva);
    auto submitBuildingCommand = reinterpret_cast<SubmitBuildingCommand>(
        g_imageBase + g_buildProfile->submitBuildingCommandRva);
    const auto parentController = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_cgalController, 0, 0));
    if (parentController == 0) {
        WriteLog("Invigorating Elixer had no captured Laboratory controller.");
        return 0;
    }
    // CGBR borrows AP10's context only to construct its stock secondary-panel
    // surface. Gameplay must resolve through the captured CGAL parent or the
    // deterministic command targets the borrowed Fervus building instead.
    auto* context = static_cast<unsigned char*>(
        getPanelContext(reinterpret_cast<void*>(parentController)));
    if (context == nullptr) {
        WriteLog("Invigorating Elixer had no selected-building context.");
        return 0;
    }
    const auto building = *reinterpret_cast<std::uint32_t*>(context + 0x70);
    if (building == 0) {
        WriteLog("Invigorating Elixer selected-building agent was null.");
        return 0;
    }
    // Stock AP24 carries both metadata words from this panel context in Rage
    // command 1. Preserve that command packet exactly.
    CommandMetadata metadata = {};
    getCommandMetadata(context, &metadata);
    InterlockedExchange(&g_invigoratingRageHandle, static_cast<LONG>(building));
    submitBuildingCommand(
        kRageOfKrolmCommandId,
        building,
        metadata.first,
        metadata.second);
    g_invigoratingElixerStartedAt = SimulationClock();
    g_lastBrewingProgressTraceSecond = 0xFFFFFFFF;
    InterlockedExchange(&g_invigoratingElixerActive, 1);
    UpdateBrewingPresentation(controller);
    char trace[192] = {};
    sprintf_s(
        trace,
        "Submitted Invigorating Elixer through stock Rage command metadata "
        "0x%08X:0x%08X.",
        metadata.first,
        metadata.second);
    WriteLog(trace);
    return 0;
}

int BeginLaboratoryResearch(
    std::uint32_t controller,
    std::uint32_t recipe,
    const char* recipeName) {
    if (!g_stockResearchRouteReady) {
        WriteLog("Laboratory research refused: stock research route was not validated.");
        return 0;
    }
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr) {
        WriteLog("Laboratory research had no selected Laboratory context.");
        return 0;
    }
    const auto commandOwner = *reinterpret_cast<std::uint32_t*>(context + 0x94);
    if (commandOwner == 0 ||
        *reinterpret_cast<std::uint32_t*>(context + 0x70) == 0) {
        WriteLog("Laboratory research had no native command owner or building.");
        return 0;
    }
    if (LaboratoryResearchIsActive()) {
        UpdateBrewingPresentation(controller);
        WriteLog("Laboratory research rejected: its private owner is already active.");
        return 0;
    }

    // AP10 recruitment and stock AP99 research both use APB, / APB8 /
    // APB\r as their one building-activity tuple. Preserve AP10's tuple, expose
    // an empty activity only for native validation/submission, capture the
    // exact research tuple stock produces, then restore AP10.
    // Payment, level/completion checks, duration selection, and command
    // construction therefore remain native while ownership is separated.
    const LaboratoryActivitySnapshot liveActivity =
        CaptureLaboratoryActivity(context);
    ClearLaboratoryActivity(context);

    using CanSubmitResearch = bool (__thiscall*)(void*, std::uint32_t);
    auto canSubmitResearch = reinterpret_cast<CanSubmitResearch>(
        g_imageBase + g_buildProfile->canSubmitResearchRva);
    if (!canSubmitResearch(reinterpret_cast<void*>(controller), recipe)) {
        RestoreLaboratoryActivity(context, liveActivity);
        RefreshWeaponOilResearch(controller);
        RefreshPhoenixPhialResearch(controller);
        char trace[160] = {};
        sprintf_s(trace, "Stock eligibility gate rejected %s research.", recipeName);
        WriteLog(trace);
        return 0;
    }

    using SubmitResearchCommand = void (__cdecl*)(
        std::uint32_t, void*, std::uint32_t);
    auto submitResearchCommand = reinterpret_cast<SubmitResearchCommand>(
        g_imageBase + g_buildProfile->submitResearchCommandRva);
    g_laboratoryResearchOwner.context = context;
    g_laboratoryResearchOwner.recipe = recipe;
    g_laboratoryResearchOwner.startedAt = 0;
    g_laboratoryResearchOwner.duration = 0;
    g_laboratoryResearchOwner.pending = true;
    g_laboratoryResearchOwner.active = false;
    submitResearchCommand(commandOwner, context, recipe);

    // Networked building commands normally apply on the next stock game
    // update, not inside SubmitResearchCommand. Handle the synchronous shape
    // if present; otherwise restore AP10 now and let GameUpdateRefreshBridge
    // capture the queued tuple on the exact update where stock installs it.
    const bool capturedSynchronously =
        CaptureSubmittedLaboratoryResearch(liveActivity);
    if (!capturedSynchronously) {
        RestoreLaboratoryActivity(context, liveActivity);
    }

    RefreshWeaponOilResearch(controller);
    RefreshPhoenixPhialResearch(controller);
    UpdateBrewingPresentation(controller);
    char trace[224] = {};
    sprintf_s(
        trace,
        "Submitted %s through stock research; private capture is %s.",
        recipeName,
        capturedSynchronously ? "complete" : "pending queued command");
    WriteLog(trace);
    return 0;
}

int HandleWeaponOilResearch(std::uint32_t controller) {
    return BeginLaboratoryResearch(
        controller, kWeaponOilResearchControlId, "Weapon Oil");
}

int HandlePhoenixPhialResearch(std::uint32_t controller) {
    return BeginLaboratoryResearch(
        controller, kPhoenixPhialResearchControlId, "Phoenix Phial");
}

int HandleArcaneInfusion(std::uint32_t controller) {
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr || LaboratoryBuildingLevel(context) < 3 ||
        LaboratoryReagentStock() < kReagentActionCost ||
        StockArcaneInfusionComplete()) {
        RefreshSovereignBrewingRows(controller);
        WriteLog("Stock-style private gate rejected Arcane Infusion.");
        return 0;
    }
    if (InterlockedCompareExchange(&g_invigoratingRageHandle, 0, 0) != 0 ||
        InterlockedCompareExchange(&g_arcaneInfusionRageHandle, 0, 0) != 0) {
        WriteLog("Arcane Infusion rejected while a Laboratory Rage command is pending.");
        return 0;
    }

    const auto building = *reinterpret_cast<std::uint32_t*>(context + 0x70);
    if (building == 0) {
        WriteLog("Arcane Infusion had no selected Laboratory agent.");
        return 0;
    }
    struct CommandMetadata {
        std::uint32_t first;
        std::uint32_t second;
    };
    using GetCommandMetadata = void (__thiscall*)(void*, CommandMetadata*);
    using SubmitBuildingCommand = void (__cdecl*)(
        std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
    auto getCommandMetadata = reinterpret_cast<GetCommandMetadata>(
        g_imageBase + g_buildProfile->getCommandMetadataRva);
    auto submitBuildingCommand = reinterpret_cast<SubmitBuildingCommand>(
        g_imageBase + g_buildProfile->submitBuildingCommandRva);
    CommandMetadata metadata = {};
    getCommandMetadata(context, &metadata);
    InterlockedExchange(&g_arcaneInfusionRageHandle, static_cast<LONG>(building));
    submitBuildingCommand(
        kRageOfKrolmCommandId,
        building,
        metadata.first,
        metadata.second);
    UpdateBrewingPresentation(controller);
    WriteLog("Submitted Arcane Infusion through stock Rage command metadata.");
    return 0;
}

int HandlePhilosophersStone(std::uint32_t controller) {
    unsigned char* context = LaboratoryPanelContext();
    if (context == nullptr || LaboratoryBuildingLevel(context) < 3 ||
        LaboratoryReagentStock() < kReagentActionCost) {
        RefreshSovereignBrewingRows(controller);
        WriteLog("Rejected a reagent action through the Laboratory's private stock gate.");
        return 0;
    }
    const auto laboratory = *reinterpret_cast<std::uint32_t*>(context + 0x70);
    if (laboratory == 0) {
        WriteLog("Reagent action had no selected Laboratory agent.");
        return 0;
    }
    const std::uint32_t privateControlId = kPhilosophersStoneControlId;
    // The visible controls remain AP69's literal, proven 0x1132/0x1133 rows.
    // Stone's private descriptor enters Majesty's literal Vines mode. Target
    // construction, validation, cancellation, and click dispatch therefore
    // remain stock. The scoped transition changes only the cursor artwork,
    // and the target commit changes only private mode, Lab owner, and cost.
    // Publish the selected Lab first; the pending control is the commit hook's
    // sentinel and therefore becomes visible last.
    InterlockedExchange(
        &g_pendingSovereignLaboratory, static_cast<LONG>(laboratory));
    InterlockedExchange(
        &g_pendingSovereignControl, static_cast<LONG>(privateControlId));
    // AP69's stock slot-3 handler accepts only 0x1131..0x114C, then calls this
    // exact cdecl helper.  Invoke that same helper with the private descriptor
    // identity; calling the vtable with 0x2A20/0x2A21 would fall through to the
    // unrelated base-controller handler and never enter target mode.
    using BeginSovereignTarget = void (__cdecl*)(std::uint32_t);
    auto beginSovereignTarget = reinterpret_cast<BeginSovereignTarget>(
        g_imageBase + g_buildProfile->sovereignSpellClickRva);
    beginSovereignTarget(privateControlId);
    return 0;
}

// 0x004A7F40 constructs stock Arrows as a five-dword research descriptor:
// duration, required building level, base research price, GMTX name, and
// completion attribute APB* / ResearchArrows. Clone that descriptor under a
// private command key and change only the explicitly private gameplay price.
// Every stock consumer can then run unchanged while completion remains
// distinguishable from real Guardhouse Arrows by descriptor identity.
extern "C" const std::uint32_t* __stdcall ResolvePrivateWeaponOilDescriptor() {
    if (g_weaponOilResearchDescriptor != nullptr) {
        return g_weaponOilResearchDescriptor;
    }
    if (g_resolveResearchDescriptorTrampoline == 0) {
        return nullptr;
    }
    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    // Resolve lazily from the first real UI/command lookup. Majesty's stock
    // resolver performs its own registry initialization here; calling it from
    // the DLL startup thread is earlier than stock permits.
    const auto* stockArrows = resolveStockDescriptor(
        kStockArrowsResearchControlId);
    if (stockArrows == nullptr ||
        stockArrows[2] != kStockArrowsResearchPrice ||
        stockArrows[3] != kArrowsGlobalTextId ||
        stockArrows[4] != 0x2A425041) {
        WriteLog(
            "Weapon Oil descriptor lookup failed: stock Arrows descriptor contract changed.");
        return nullptr;
    }
    // Stock 0x004A83E0 allocates every five-dword descriptor with Majesty's
    // operator new immediately before inserting it into the AP99 registry.
    // The registry owns that allocation and frees it at 0x004A8190 when the
    // quest is unloaded. Use the same ownership contract; a DLL-static array
    // is not a legal registry value and will be passed to stock free on the
    // next quest load.
    using StockOperatorNew = void* (__cdecl*)(std::size_t);
    auto stockOperatorNew = reinterpret_cast<StockOperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    g_weaponOilResearchDescriptor = static_cast<std::uint32_t*>(
        stockOperatorNew(kResearchDescriptorSize));
    if (g_weaponOilResearchDescriptor == nullptr) {
        WriteLog(
            "Weapon Oil descriptor lookup failed: stock allocation returned null.");
        return nullptr;
    }
    std::memcpy(
        g_weaponOilResearchDescriptor,
        stockArrows,
        kResearchDescriptorSize);
    g_weaponOilResearchDescriptor[1] = 1;
    g_weaponOilResearchDescriptor[2] = kWeaponOilResearchPrice;
    WriteLog("Lazily cloned Majesty's initialized stock Arrows descriptor for Weapon Oil.");
    return g_weaponOilResearchDescriptor;
}

extern "C" const std::uint32_t* __stdcall ResolvePrivatePhoenixPhialDescriptor() {
    if (g_phoenixPhialResearchDescriptor != nullptr) {
        return g_phoenixPhialResearchDescriptor;
    }
    if (g_resolveResearchDescriptorTrampoline == 0) {
        return nullptr;
    }
    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    // Keep AP99 Arrows' level-1 timing gate, use the private testing price,
    // and copy AP99 Teleportation Amulets' one-time ResearchPowerfulItem
    // completion attribute. Building-level tuning is intentionally deferred.
    const auto* stockArrows = resolveStockDescriptor(
        kStockArrowsResearchControlId);
    const auto* stockAmulet = resolveStockDescriptor(
        kStockTeleportAmuletResearchControlId);
    if (stockArrows == nullptr || stockAmulet == nullptr ||
        stockArrows[2] != kStockArrowsResearchPrice ||
        stockArrows[4] == 0 || stockAmulet[4] == 0) {
        WriteLog(
            "Phoenix Phial descriptor lookup failed: stock Teleportation Amulet descriptor changed.");
        return nullptr;
    }
    using StockOperatorNew = void* (__cdecl*)(std::size_t);
    auto stockOperatorNew = reinterpret_cast<StockOperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    g_phoenixPhialResearchDescriptor = static_cast<std::uint32_t*>(
        stockOperatorNew(kResearchDescriptorSize));
    if (g_phoenixPhialResearchDescriptor == nullptr) {
        WriteLog(
            "Phoenix Phial descriptor lookup failed: stock allocation returned null.");
        return nullptr;
    }
    std::memcpy(
        g_phoenixPhialResearchDescriptor,
        stockArrows,
        kResearchDescriptorSize);
    // AP99 0x004A9160 owns the complete stock level gate, including the
    // preceding-tier construction check and all three compound row children.
    g_phoenixPhialResearchDescriptor[1] = 2;
    g_phoenixPhialResearchDescriptor[2] = kPhoenixPhialResearchPrice;
    g_phoenixPhialResearchDescriptor[4] = stockAmulet[4];
    WriteLog(
        "Lazily composed Phoenix Phial from stock Arrows research and Teleportation Amulet completion.");
    return g_phoenixPhialResearchDescriptor;
}

bool RegisterPrivateResearchDescriptors() {
    if (g_researchDescriptorRegistryMap == 0 ||
        g_researchDescriptorRegistryFindOrInsert == 0) {
        return false;
    }
    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveResearchDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    const auto* registeredWeaponOil =
        resolveResearchDescriptor(kWeaponOilResearchControlId);
    const auto* registeredPhoenixPhial =
        resolveResearchDescriptor(kPhoenixPhialResearchControlId);
    if (registeredWeaponOil != nullptr &&
        registeredWeaponOil == g_weaponOilResearchDescriptor &&
        registeredPhoenixPhial != nullptr &&
        registeredPhoenixPhial == g_phoenixPhialResearchDescriptor) {
        return true;
    }
    if (registeredWeaponOil != nullptr || registeredPhoenixPhial != nullptr) {
        WriteLog(
            "Private Laboratory research registration failed: AP99 returned an occupied descriptor key.");
        return false;
    }

    // A null lookup for both private keys is the same boundary stock uses when
    // rebuilding this registry for a newly loaded quest. Stock has already
    // freed the previous quest's owned descriptors, so retire our borrowed
    // identities before allocating their replacements through 0x006EE542.
    g_weaponOilResearchDescriptor = nullptr;
    g_phoenixPhialResearchDescriptor = nullptr;
    const auto* weaponOil = ResolvePrivateWeaponOilDescriptor();
    const auto* phoenixPhial = ResolvePrivatePhoenixPhialDescriptor();
    if (weaponOil == nullptr || phoenixPhial == nullptr) {
        return false;
    }

    // AP99's stock descriptor construction at 0x004A83E0 inserts every
    // Blacksmith research recipe into this map with 0x004A8030, and every
    // later consumer, including completion at 0x004E0430, resolves through
    // the same map. Majesty clears and rebuilds this registry when a quest is
    // loaded without unloading this DLL. Re-resolve the private keys on every
    // CGBR setup and create new stock-owned clones after that rebuild has
    // removed and freed the previous ones. Presentation, submission, and
    // completion therefore receive one stable identity for the current quest
    // while stock retains its normal teardown ownership.
    using FindOrInsert = void** (__thiscall*)(void*, const std::uint32_t*);
    auto findOrInsert = reinterpret_cast<FindOrInsert>(
        g_researchDescriptorRegistryFindOrInsert);
    const std::uint32_t keys[2] = {
        kWeaponOilResearchControlId,
        kPhoenixPhialResearchControlId};
    void* const descriptors[2] = {
        g_weaponOilResearchDescriptor,
        g_phoenixPhialResearchDescriptor};
    for (std::size_t index = 0; index < 2; ++index) {
        const std::uint32_t key = keys[index];
        void** slot = findOrInsert(
            reinterpret_cast<void*>(g_researchDescriptorRegistryMap), &key);
        if (slot == nullptr || (*slot != nullptr && *slot != descriptors[index])) {
            WriteLog(
                "Private Laboratory research registration failed: AP99 returned an occupied descriptor slot.");
            return false;
        }
        *slot = descriptors[index];
    }
    if (resolveResearchDescriptor(kWeaponOilResearchControlId) != weaponOil ||
        resolveResearchDescriptor(kPhoenixPhialResearchControlId) != phoenixPhial) {
        WriteLog(
            "Private Laboratory research registration failed: AP99 could not resolve the inserted descriptors.");
        return false;
    }
    const bool registryWasPreviouslyObserved =
        g_privateResearchDescriptorsRegistered;
    g_privateResearchDescriptorsRegistered = true;
    WriteLog(registryWasPreviouslyObserved
        ? "Re-registered Weapon Oil and Phoenix Phial after AP99 rebuilt its stock research registry."
        : "Registered Weapon Oil and Phoenix Phial through AP99's stock Blacksmith research registry.");
    return true;
}

bool InstallPrivateWeaponOilResearchDescriptor() {
    auto* entry = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->resolveResearchDescriptorRva);
    if (std::memcmp(
            entry,
            g_buildProfile->expectedResolveResearchDescriptorEntry,
            sizeof(g_buildProfile->expectedResolveResearchDescriptorEntry)) != 0) {
        WriteLog(
            "Weapon Oil descriptor refused: stock research resolver bytes are unknown.");
        return false;
    }
    // AP99's resolver contains two literal `mov ecx, registry; call ...`
    // pairs: its lookup and its stock find-or-insert path. Decode that exact
    // contract from the validated stock function instead of hard-coding data
    // addresses that differ between the public and beta2 executables.
    std::uintptr_t registryMap = 0;
    std::uintptr_t findOrInsert = 0;
    int matchingMapLoads = 0;
    for (std::size_t offset = 10; offset + 10 <= 0x70; ++offset) {
        if (entry[offset] != 0xB9 || entry[offset + 5] != 0xE8) {
            continue;
        }
        std::uint32_t mapAddress = 0;
        std::int32_t callRelative = 0;
        std::memcpy(&mapAddress, entry + offset + 1, sizeof(mapAddress));
        std::memcpy(&callRelative, entry + offset + 6, sizeof(callRelative));
        if (registryMap == 0) {
            registryMap = mapAddress;
            matchingMapLoads = 1;
            continue;
        }
        if (mapAddress != registryMap) {
            continue;
        }
        ++matchingMapLoads;
        findOrInsert = reinterpret_cast<std::uintptr_t>(entry + offset + 10) +
            callRelative;
    }
    if (matchingMapLoads < 2 || registryMap == 0 || findOrInsert == 0) {
        WriteLog(
            "Private Laboratory research refused: AP99 registry insertion contract changed.");
        return false;
    }
    g_resolveResearchDescriptorTrampoline =
        reinterpret_cast<std::uintptr_t>(entry);
    g_researchDescriptorRegistryMap = registryMap;
    g_researchDescriptorRegistryFindOrInsert = findOrInsert;
    WriteLog(
        "Validated AP99's stock Blacksmith research descriptor registry for private registration.");
    return true;
}

bool InstallResearchCompletionBridge() {
    auto* dispatchSlot = reinterpret_cast<std::uint32_t*>(
        g_imageBase + g_buildProfile->researchCompletionDispatchSlotRva);
    const std::uint32_t stockCompletion = static_cast<std::uint32_t>(
        g_imageBase + g_buildProfile->researchCompletionRva);
    // The stock order-processor table stores event ID 0x2009 immediately
    // before its completion callback and event ID 0x200B immediately after.
    // Validate that full Blacksmith dispatch tuple before privatizing the one
    // callback pointer for the Laboratory's scoped AP10/AP99 ownership handoff.
    if (dispatchSlot[-1] != 0x00002009u ||
        dispatchSlot[0] != stockCompletion ||
        dispatchSlot[1] != 0x0000200Bu) {
        WriteLog(
            "Laboratory research completion bridge refused: stock event 0x2009 dispatch changed.");
        return false;
    }
    g_stockResearchCompletion = reinterpret_cast<ResearchCompletion>(
        dispatchSlot[0]);
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            dispatchSlot,
            sizeof(*dispatchSlot),
            PAGE_READWRITE,
            &oldProtection)) {
        WriteLog(
            "Laboratory research completion bridge failed: event 0x2009 dispatch is not writable.");
        return false;
    }
    dispatchSlot[0] = reinterpret_cast<std::uint32_t>(&ResearchCompletionBridge);
    DWORD ignored = 0;
    VirtualProtect(
        dispatchSlot, sizeof(*dispatchSlot), oldProtection, &ignored);
    WriteLog(
        "Installed scoped Laboratory bridge on stock Blacksmith event 0x2009 completion.");
    return true;
}

extern "C" const std::uint32_t* __stdcall ResolvePrivateInvigoratingDescriptor() {
    if (g_invigoratingSpellDescriptor[4] != 0) {
        return g_invigoratingSpellDescriptor;
    }
    if (g_resolveSpellDescriptorTrampoline == 0) {
        return nullptr;
    }
    using ResolveSpellDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveSpellDescriptor>(
        g_resolveSpellDescriptorTrampoline);
    const auto* stockHealing = resolveStockDescriptor(kStockFervusHealingControlId);
    const auto* stockPetrify = resolveStockDescriptor(kStockPetrifyControlId);
    if (stockHealing == nullptr || stockPetrify == nullptr ||
        stockHealing[0] != kStockFervusBuildingClassId ||
        stockHealing[1] != kAp69DialogId ||
        stockHealing[3] != 1 ||
        stockPetrify[3] != 3 || stockPetrify[4] == 0) {
        WriteLog(
            "Vigor descriptor lookup failed: stock Healing/Petrify contract changed.");
        return nullptr;
    }
    std::memcpy(
        g_invigoratingSpellDescriptor,
        stockHealing,
        sizeof(g_invigoratingSpellDescriptor));
    g_invigoratingSpellDescriptor[0] = kLaboratoryBuildingClassId;
    g_invigoratingSpellDescriptor[1] = kCgbrDialogId;
    g_invigoratingSpellDescriptor[3] = stockPetrify[3];
    g_invigoratingSpellDescriptor[4] = stockPetrify[4];
    WriteLog(
        "Lazily composed Vigor from AP69 Healing and level-3 1500-gold Petrify.");
    return g_invigoratingSpellDescriptor;
}

extern "C" const std::uint32_t* __stdcall ResolvePrivateSovereignVisualDescriptor(
    std::uint32_t controlId) {
    const bool infusion = controlId == kArcaneInfusionVisualControlId;
    std::uint32_t* descriptor = infusion
        ? g_arcaneInfusionVisualDescriptor
        : g_philosophersStoneVisualDescriptor;
    if (descriptor[1] == 0) {
        if (g_resolveSpellDescriptorTrampoline == 0) {
            return nullptr;
        }
        using ResolveSpellDescriptor = const std::uint32_t* (__cdecl*)(
            std::uint32_t);
        auto resolveStockDescriptor = reinterpret_cast<ResolveSpellDescriptor>(
            g_resolveSpellDescriptorTrampoline);
        const auto* stock = resolveStockDescriptor(controlId);
        const std::uint32_t expectedMode = infusion
            ? kStockFervusSecondSpellMode
            : kStockFervusThirdSpellMode;
        const std::uint32_t expectedLevel = infusion ? 3u : 2u;
        const std::uint32_t expectedCost = infusion ? 1000u : 500u;
        if (stock == nullptr || stock[0] != kStockFervusBuildingClassId ||
            stock[1] != kAp69DialogId || stock[2] != expectedMode ||
            stock[3] != expectedLevel || stock[4] != expectedCost) {
            WriteLog("Sovereign visual descriptor failed: stock Fervus row changed.");
            return nullptr;
        }
        std::memcpy(
            descriptor, stock, sizeof(g_arcaneInfusionVisualDescriptor));
        descriptor[1] = kCgbrDialogId;
        descriptor[4] = 0;
        WriteLog(
            "Composed a private sovereign visual from its matching stock Fervus row.");
    }

    // AP69's unavailable tooltip always formats descriptor[0]/[3] as a
    // building prerequisite when the row is disabled. Keep the real private
    // Laboratory requirement below level three. Once it is satisfied, use
    // level zero of that same private class. Stock's checked lookup has no
    // level-zero description to append, so the independent 10-Reagent gate
    // can disable the row without falsely naming an unrelated building.
    unsigned char* context = LaboratoryPanelContext();
    const bool laboratoryLevelMet = context != nullptr &&
        LaboratoryBuildingLevel(context) >= 3;
    descriptor[0] = kLaboratoryBuildingClassId;
    descriptor[3] = laboratoryLevelMet ? 0u : 3u;
    return descriptor;
}

extern "C" const std::uint32_t* __stdcall ResolvePrivateSovereignDescriptor(
    std::uint32_t) {
    std::uint32_t* descriptor = g_philosophersStoneSpellDescriptor;
    if (descriptor[0] != 0) {
        return descriptor;
    }
    if (g_resolveSpellDescriptorTrampoline == 0) {
        return nullptr;
    }
    using ResolveSpellDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveSpellDescriptor>(
        g_resolveSpellDescriptorTrampoline);
    const std::uint32_t stockControlId = kStockVinesControlId;
    const std::uint32_t stockBuildingClassId = kStockFervusBuildingClassId;
    const std::uint32_t stockDialogId = kAp69DialogId;
    const std::uint32_t stockMode = kStockVinesMode;
    const std::uint32_t stockLevel = 3u;
    const std::uint32_t stockCost = 1000;
    const auto* stock = resolveStockDescriptor(stockControlId);
    if (stock == nullptr || stock[0] != stockBuildingClassId ||
        stock[1] != stockDialogId || stock[2] != stockMode ||
        stock[3] != stockLevel || stock[4] != stockCost) {
        WriteLog("Sovereign execution descriptor failed: stock temple spell changed.");
        return nullptr;
    }
    std::memcpy(descriptor, stock, sizeof(g_philosophersStoneSpellDescriptor));
    descriptor[0] = kLaboratoryBuildingClassId;
    descriptor[1] = kCgbrDialogId;
    descriptor[2] = stockMode;
    // Stone keeps Vines' global unit targeting. The Lab owns the
    // level-three/10-Reagent gate and the GPL birth commit consumes stock, so
    // the private command carries no temple-gold charge.
    descriptor[3] = 1;
    descriptor[4] = 0;
    WriteLog("Composed private sovereign targeting from its matching stock temple spell.");
    return descriptor;
}

__declspec(naked) void ResolveSpellDescriptorHook() {
    __asm {
        cmp dword ptr [esp + 4], 2A10h
        je check_private_context
        cmp dword ptr [esp + 4], 1132h
        je sovereign_visual_descriptor
        cmp dword ptr [esp + 4], 1133h
        je sovereign_visual_descriptor
        cmp dword ptr [esp + 4], 2A21h
        jne stock_resolver

        cmp dword ptr [g_customBrewingActive], 1
        jne stock_resolver
        push dword ptr [esp + 4]
        call ResolvePrivateSovereignDescriptor
        ret

    sovereign_visual_descriptor:
        cmp dword ptr [g_customBrewingActive], 1
        jne stock_resolver
        push dword ptr [esp + 4]
        call ResolvePrivateSovereignVisualDescriptor
        ret

    check_private_context:
        cmp dword ptr [g_customBrewingActive], 1
        jne stock_resolver
        call ResolvePrivateInvigoratingDescriptor
        ret

    stock_resolver:
        jmp dword ptr [g_resolveSpellDescriptorTrampoline]
    }
}

bool InstallPrivateInvigoratingSpellDescriptor() {
    auto* entry = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->resolveSpellDescriptorRva);
    if (std::memcmp(
            entry,
            g_buildProfile->expectedResolveSpellDescriptorEntry,
            sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry)) != 0) {
        WriteLog(
            "Vigor descriptor refused: stock spell resolver bytes are unknown.");
        return false;
    }
    auto* trampoline = reinterpret_cast<unsigned char*>(VirtualAlloc(
        nullptr,
        sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry) + 5,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        WriteLog("Vigor descriptor failed: trampoline allocation was rejected.");
        return false;
    }
    std::memcpy(
        trampoline,
        g_buildProfile->expectedResolveSpellDescriptorEntry,
        sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry));
    trampoline[sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry)] = 0xE9;
    const auto returnAddress = reinterpret_cast<std::uintptr_t>(entry) +
        sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry);
    const auto trampolineJump = static_cast<std::int32_t>(
        returnAddress -
        (reinterpret_cast<std::uintptr_t>(trampoline) +
         sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry) + 5));
    std::memcpy(
        trampoline + sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry) + 1,
        &trampolineJump,
        sizeof(trampolineJump));
    g_resolveSpellDescriptorTrampoline =
        reinterpret_cast<std::uintptr_t>(trampoline);
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&ResolveSpellDescriptorHook) -
        (reinterpret_cast<std::uintptr_t>(entry) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry)] = {
        0xE9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90, 0x90};
    std::memcpy(patch + 1, &relative, sizeof(relative));
    DWORD oldProtection = 0;
    if (!VirtualProtect(
            entry,
            sizeof(patch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        WriteLog(
            "Vigor descriptor failed: VirtualProtect rejected the resolver.");
        return false;
    }
    std::memcpy(entry, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(entry, sizeof(patch), oldProtection, &ignored);
    WriteLog("Installed scoped stock AP69 descriptor alias for Vigor.");
    return true;
}

// Majesty has no data-driven cursor override for a private action that must
// retain a hard-coded stock target mode. Reproduce the stock transition
// literally and privatize only the cursor ordinal while the matching Lab
// action owns that Vines target session.
__declspec(naked) void SovereignCursorTransitionHook() {
    __asm {
        mov edx, dword ptr [esi]
        mov edx, dword ptr [edx + 48h]
        mov dword ptr [esi + 3Ch], eax
        mov dword ptr [esi + 40h], ebx
        mov dword ptr [esi + 38h], ebx
        mov eax, dword ptr [edi + 4]

        cmp dword ptr [g_pendingSovereignControl], 2A21h
        jne present_cursor
        cmp dword ptr [edi], 33327053h
        jne present_cursor
        mov eax, 39

    present_cursor:
        push ebx
        push eax
        mov ecx, esi
        call edx
        jmp dword ptr [g_sovereignCursorTransitionResume]
    }
}

extern "C" void __cdecl SubmitPrivateSovereignCommand(
    std::uint32_t mode,
    std::uint32_t player,
    std::uint32_t x,
    std::uint32_t y,
    std::uint32_t target,
    std::uint32_t cost) {
    const auto pending = static_cast<std::uint32_t>(InterlockedCompareExchange(
        &g_pendingSovereignControl, 0, 0));
    const auto laboratory = static_cast<std::uint32_t>(InterlockedCompareExchange(
        &g_pendingSovereignLaboratory, 0, 0));
    const bool matchingStone = mode == kStockVinesMode &&
        pending == kPhilosophersStoneControlId;
    if (laboratory != 0 && matchingStone) {
        if (LaboratoryReagentStock() < kReagentActionCost) {
            // Stock temple spells still submit their current target packet
            // when the player cannot afford another cast. Their sovereign
            // executor rejects that packet at its native gold-affordability
            // branch, presents the stock failure feedback, and leaves the
            // repeat-cast target lifecycle intact. Preserve the stock mode and
            // use an unreachable cost only as the private Reagent predicate's
            // input to that exact downstream branch.
            cost = kStockUnaffordableGoldCost;
            WriteLog("Submitted a depleted private target through Majesty's stock unaffordable-spell route.");
        } else {
            mode = kPhilosophersStoneMode;
            target = laboratory;
            cost = 0;
            WriteLog("Committed a private reagent action through its stock temple target packet.");
        }
    }
    using SubmitCommand = void (__cdecl*)(
        std::uint32_t, std::uint32_t, std::uint32_t,
        std::uint32_t, std::uint32_t, std::uint32_t);
    auto submit = reinterpret_cast<SubmitCommand>(
        g_imageBase + g_buildProfile->sovereignSubmitCommandRva);
    submit(mode, player, x, y, target, cost);
}

__declspec(naked) void PublicSovereignExecutorHook() {
    __asm {
        mov eax, dword ptr [esp + 4]
        cmp eax, 31536C41h
        je private_stone
        jmp stock_entry
    private_stone:
        mov dword ptr [g_executingSovereignKind], 2
        mov dword ptr [esp + 4], 34317053h
    stock_entry:
        push -1
        push 006FA007h
        jmp dword ptr [g_sovereignExecutorResume]
    }
}

__declspec(naked) void Beta2SovereignExecutorHook() {
    __asm {
        mov eax, dword ptr [esp + 4]
        cmp eax, 31536C41h
        je private_stone
        jmp stock_entry
    private_stone:
        mov dword ptr [g_executingSovereignKind], 2
        mov dword ptr [esp + 4], 34317053h
    stock_entry:
        push -1
        push 0070F5D7h
        jmp dword ptr [g_sovereignExecutorResume]
    }
}

__declspec(naked) void PublicSovereignConstructionHook() {
    __asm {
        cmp dword ptr [g_executingSovereignKind], 2
        jne stock_result
        mov eax, 31534C41h
        jmp clear_result
    clear_result:
        mov dword ptr [g_executingSovereignKind], 0
    stock_result:
        mov ecx, dword ptr [esp + 1Ch]
        mov ebx, eax
        jmp dword ptr [g_sovereignConstructionResume]
    }
}

__declspec(naked) void Beta2SovereignConstructionHook() {
    __asm {
        cmp dword ptr [g_executingSovereignKind], 2
        jne stock_result
        mov eax, 31534C41h
        jmp clear_result
    clear_result:
        mov dword ptr [g_executingSovereignKind], 0
    stock_result:
        mov ecx, dword ptr [esp + 1Ch]
        mov ebx, eax
        jmp dword ptr [g_sovereignConstructionResume]
    }
}

bool InstallPrivateSovereignSpellRoute() {
    auto* commit = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->sovereignTargetCommitCallRva);
    auto* cursorTransition = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->sovereignCursorTransitionRva);
    auto* executor = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->sovereignExecutorEntryRva);
    auto* construction = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->sovereignConstructionOverrideRva);
    if (std::memcmp(
            commit,
            g_buildProfile->expectedSovereignTargetCommitCall,
            sizeof(g_buildProfile->expectedSovereignTargetCommitCall)) != 0 ||
        std::memcmp(
            cursorTransition,
            g_buildProfile->expectedSovereignCursorTransition,
            sizeof(g_buildProfile->expectedSovereignCursorTransition)) != 0 ||
        std::memcmp(
            executor,
            g_buildProfile->expectedSovereignExecutorEntry,
            sizeof(g_buildProfile->expectedSovereignExecutorEntry)) != 0 ||
        std::memcmp(
            construction,
            g_buildProfile->expectedSovereignConstructionOverride,
            g_buildProfile->sovereignConstructionOverrideSize) != 0) {
        WriteLog("Private sovereign spell route refused: traced stock bytes changed.");
        return false;
    }

    DWORD oldProtection = 0;
    if (!VirtualProtect(commit, 5, PAGE_EXECUTE_READWRITE, &oldProtection)) {
        return false;
    }
    const auto commitRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&SubmitPrivateSovereignCommand) -
        (reinterpret_cast<std::uintptr_t>(commit) + 5));
    unsigned char callPatch[5] = {0xE8, 0, 0, 0, 0};
    std::memcpy(callPatch + 1, &commitRelative, sizeof(commitRelative));
    std::memcpy(commit, callPatch, sizeof(callPatch));
    FlushInstructionCache(GetCurrentProcess(), commit, sizeof(callPatch));
    DWORD ignored = 0;
    VirtualProtect(commit, 5, oldProtection, &ignored);

    const auto cursorTransitionSize =
        sizeof(g_buildProfile->expectedSovereignCursorTransition);
    g_sovereignCursorTransitionResume =
        reinterpret_cast<std::uintptr_t>(cursorTransition) +
        cursorTransitionSize;
    oldProtection = 0;
    if (!VirtualProtect(
            cursorTransition,
            cursorTransitionSize,
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        return false;
    }
    unsigned char cursorPatch[
        sizeof(g_buildProfile->expectedSovereignCursorTransition)];
    std::memset(cursorPatch, 0x90, sizeof(cursorPatch));
    cursorPatch[0] = 0xE9;
    const auto cursorRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&SovereignCursorTransitionHook) -
        (reinterpret_cast<std::uintptr_t>(cursorTransition) + 5));
    std::memcpy(cursorPatch + 1, &cursorRelative, sizeof(cursorRelative));
    std::memcpy(cursorTransition, cursorPatch, sizeof(cursorPatch));
    FlushInstructionCache(
        GetCurrentProcess(), cursorTransition, sizeof(cursorPatch));
    VirtualProtect(
        cursorTransition,
        cursorTransitionSize,
        oldProtection,
        &ignored);

    g_sovereignExecutorResume =
        reinterpret_cast<std::uintptr_t>(executor) + 7;
    oldProtection = 0;
    if (!VirtualProtect(executor, 7, PAGE_EXECUTE_READWRITE, &oldProtection)) {
        return false;
    }
    const void* executorHook = g_buildProfile == &kPublicBuildProfile
        ? reinterpret_cast<const void*>(&PublicSovereignExecutorHook)
        : reinterpret_cast<const void*>(&Beta2SovereignExecutorHook);
    const auto executorRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(executorHook) -
        (reinterpret_cast<std::uintptr_t>(executor) + 5));
    unsigned char executorPatch[7] = {0xE9, 0, 0, 0, 0, 0x90, 0x90};
    std::memcpy(executorPatch + 1, &executorRelative, sizeof(executorRelative));
    std::memcpy(executor, executorPatch, sizeof(executorPatch));
    FlushInstructionCache(GetCurrentProcess(), executor, sizeof(executorPatch));
    VirtualProtect(executor, 7, oldProtection, &ignored);

    const auto constructionSize =
        g_buildProfile->sovereignConstructionOverrideSize;
    g_sovereignConstructionResume =
        reinterpret_cast<std::uintptr_t>(construction) + constructionSize;
    oldProtection = 0;
    if (!VirtualProtect(
            construction, constructionSize, PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        return false;
    }
    const void* constructionHook = g_buildProfile == &kPublicBuildProfile
        ? reinterpret_cast<const void*>(&PublicSovereignConstructionHook)
        : reinterpret_cast<const void*>(&Beta2SovereignConstructionHook);
    const auto constructionRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(constructionHook) -
        (reinterpret_cast<std::uintptr_t>(construction) + 5));
    unsigned char constructionPatch[9] = {
        0xE9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90};
    std::memcpy(
        constructionPatch + 1, &constructionRelative,
        sizeof(constructionRelative));
    std::memcpy(construction, constructionPatch, constructionSize);
    FlushInstructionCache(GetCurrentProcess(), construction, constructionSize);
    VirtualProtect(construction, constructionSize, oldProtection, &ignored);
    WriteLog("Installed private Philosopher's Stone temple target and cursor route.");
    return true;
}

// Stock completion at 0x004DFE20 resolves the descriptor, applies its
// completion attribute, formats GMTX 0xBC ("Research Complete") with its name,
// posts the green alert, and clears the activity attributes. At 0x004DFFC7 EDI
// is the resolved name pointer. Keep that exact call and replace only EDI when
// EBX is our private Arrows descriptor clone.

__declspec(naked) void ResearchCompletionNamePushHook() {
    __asm {
        cmp ebx, dword ptr [g_weaponOilResearchDescriptor]
        jne check_phoenix_name
        push offset g_weaponOilCompletionName
        jmp finish_stock_sequence

    check_phoenix_name:
        cmp ebx, dword ptr [g_phoenixPhialResearchDescriptor]
        jne stock_name
        push offset g_phoenixPhialCompletionName
        jmp finish_stock_sequence

    stock_name:
        push edi

    finish_stock_sequence:
        sar ecx, 17h
        push eax
        jmp dword ptr [g_researchCompletionNamePushResume]
    }
}

bool InstallResearchCompletionNameClone() {
    auto* site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->researchCompletionNamePushRva);
    if (std::memcmp(
            site,
            g_buildProfile->expectedResearchCompletionNamePush,
            sizeof(g_buildProfile->expectedResearchCompletionNamePush)) != 0) {
        WriteLog(
            "Weapon Oil completion label refused: stock research-completion bytes are unknown.");
        return false;
    }
    g_researchCompletionNamePushResume =
        reinterpret_cast<std::uintptr_t>(site) +
        sizeof(g_buildProfile->expectedResearchCompletionNamePush);
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&ResearchCompletionNamePushHook) -
        (reinterpret_cast<std::uintptr_t>(site) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedResearchCompletionNamePush)] = {
        0xE9, 0, 0, 0, 0};
    std::memcpy(patch + 1, &relative, sizeof(relative));

    DWORD oldProtection = 0;
    if (!VirtualProtect(
            site,
            sizeof(patch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        WriteLog(
            "Weapon Oil completion label failed: VirtualProtect rejected the stock site.");
        return false;
    }
    std::memcpy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(patch), oldProtection, &ignored);
    WriteLog(
        "Installed scoped Weapon Oil name substitution in Majesty's stock research-completion alert.");
    return true;
}

bool ValidateStockResearchRoute() {
    const auto* refreshEntry = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->refreshResearchRowsRva);
    const auto* singleRowEntry = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->refreshSingleResearchRowRva);
    const auto* eligibilityEntry = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->canSubmitResearchRva);
    const auto* submitEntry = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->submitResearchCommandRva);
    const auto* completionEntry = reinterpret_cast<const unsigned char*>(
        g_imageBase + g_buildProfile->researchCompletionRva);
    if (std::memcmp(
            refreshEntry,
            g_buildProfile->expectedRefreshResearchRowsEntry,
            sizeof(g_buildProfile->expectedRefreshResearchRowsEntry)) != 0 ||
        std::memcmp(
            singleRowEntry,
            g_buildProfile->expectedRefreshSingleResearchRowEntry,
            sizeof(g_buildProfile->expectedRefreshSingleResearchRowEntry)) != 0 ||
        std::memcmp(
            eligibilityEntry,
            g_buildProfile->expectedCanSubmitResearchEntry,
            sizeof(g_buildProfile->expectedCanSubmitResearchEntry)) != 0 ||
        std::memcmp(
            submitEntry,
            g_buildProfile->expectedSubmitResearchCommandEntry,
            sizeof(g_buildProfile->expectedSubmitResearchCommandEntry)) != 0 ||
        std::memcmp(
            completionEntry,
            g_buildProfile->expectedResearchCompletionEntry,
            sizeof(g_buildProfile->expectedResearchCompletionEntry)) != 0) {
        WriteLog("Weapon Oil refused: Majesty's stock AP99 research bytes are unknown.");
        return false;
    }
    WriteLog("Validated AP99 native research refresh and command route.");
    return true;
}

__declspec(naked) void RageCommandDispatchHook() {
    __asm {
        mov ecx, dword ptr [ebp + 0Ch]
        cmp ecx, dword ptr [g_invigoratingRageHandle]
        je vigor_dispatch
        cmp ecx, dword ptr [g_arcaneInfusionRageHandle]
        jne stock_dispatch
        mov dword ptr [g_invigoratingRageDispatch], 2
        jmp stock_dispatch

    vigor_dispatch:
        mov dword ptr [g_invigoratingRageDispatch], 1

    stock_dispatch:
        push ecx
        mov ecx, edi
        jmp dword ptr [g_rageCommandDispatchResume]
    }
}

void LogPrivateRageDispatch() {
    WriteLog("Matched the Laboratory Rage command; invoking its private GPL clone.");
}

__declspec(naked) void RagePrivateBranchHook() {
    __asm {
        cmp dword ptr [g_invigoratingRageDispatch], 1
        je vigor
        cmp dword ptr [g_invigoratingRageDispatch], 2
        je infusion
        jmp stock_rage

    vigor:
        mov dword ptr [g_invigoratingRageDispatch], 0
        mov dword ptr [g_invigoratingRageHandle], 0
        pushfd
        pushad
        call LogPrivateRageDispatch
        popad
        popfd
        push dword ptr [g_invigoratingGplFunctionName]
        jmp dword ptr [g_rageGplConstructionResume]

    infusion:
        mov dword ptr [g_invigoratingRageDispatch], 0
        mov dword ptr [g_arcaneInfusionRageHandle], 0
        pushfd
        pushad
        call LogPrivateRageDispatch
        popad
        popfd
        push dword ptr [g_arcaneInfusionGplFunctionName]
        jmp dword ptr [g_rageGplConstructionResume]

    stock_rage:
        push 4541h
        jmp dword ptr [g_ragePrivateBranchResume]
    }
}

bool InstallPrivateRageRoute() {
    auto* commandDispatch = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->rageCommandDispatchRva);
    auto* privateBranch = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->ragePrivateBranchRva);
    if (std::memcmp(
            commandDispatch,
            g_buildProfile->expectedRageCommandDispatch,
            sizeof(g_buildProfile->expectedRageCommandDispatch)) != 0 ||
        std::memcmp(
            privateBranch,
            g_buildProfile->expectedRagePrivateBranch,
            sizeof(g_buildProfile->expectedRagePrivateBranch)) != 0) {
        WriteLog("Private Rage route refused: traced stock bytes are unknown.");
        return false;
    }
    g_rageCommandDispatchResume =
        reinterpret_cast<std::uintptr_t>(commandDispatch) +
        sizeof(g_buildProfile->expectedRageCommandDispatch);
    g_ragePrivateBranchResume =
        reinterpret_cast<std::uintptr_t>(privateBranch) +
        sizeof(g_buildProfile->expectedRagePrivateBranch);
    g_rageGplConstructionResume =
        g_imageBase + g_buildProfile->rageGplConstructionResumeRva;

    DWORD oldProtection = 0;
    if (!VirtualProtect(
            commandDispatch,
            sizeof(g_buildProfile->expectedRageCommandDispatch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        return false;
    }
    const auto dispatchRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&RageCommandDispatchHook) -
        (reinterpret_cast<std::uintptr_t>(commandDispatch) + 5));
    unsigned char dispatchPatch[sizeof(g_buildProfile->expectedRageCommandDispatch)] = {
        0xE9, 0, 0, 0, 0, 0x90};
    std::memcpy(dispatchPatch + 1, &dispatchRelative, sizeof(dispatchRelative));
    std::memcpy(commandDispatch, dispatchPatch, sizeof(dispatchPatch));
    FlushInstructionCache(GetCurrentProcess(), commandDispatch, sizeof(dispatchPatch));
    DWORD ignored = 0;
    VirtualProtect(commandDispatch, sizeof(dispatchPatch), oldProtection, &ignored);

    oldProtection = 0;
    if (!VirtualProtect(
            privateBranch,
            sizeof(g_buildProfile->expectedRagePrivateBranch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        return false;
    }
    const auto branchRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&RagePrivateBranchHook) -
        (reinterpret_cast<std::uintptr_t>(privateBranch) + 5));
    unsigned char branchPatch[sizeof(g_buildProfile->expectedRagePrivateBranch)] = {
        0xE9, 0, 0, 0, 0};
    std::memcpy(branchPatch + 1, &branchRelative, sizeof(branchRelative));
    std::memcpy(privateBranch, branchPatch, sizeof(branchPatch));
    FlushInstructionCache(GetCurrentProcess(), privateBranch, sizeof(branchPatch));
    VirtualProtect(privateBranch, sizeof(branchPatch), oldProtection, &ignored);
    WriteLog("Installed the exact-handle private Rage GPL route.");
    return true;
}

void __fastcall BrewingControllerSetup(void* controller, void*) {
    g_stockAp69Setup(controller);
    if (!RegisterPrivateResearchDescriptors()) {
        WriteLog(
            "Brewing setup could not register its private AP99 research descriptors.");
        return;
    }
    // AP69 owns initial construction and presentation of the two literal stock
    // Fervus rows. Invoke that presenter once at setup, then retain only the
    // private Reagent gate during ordinary game updates.
    RefreshSovereignBrewingRows(reinterpret_cast<std::uint32_t>(controller));
    // Custom active-display swaps run before the native row presenters so
    // AP99/AP69 remain the final authority for inactive availability, price,
    // and building-level gating.
    UpdateBrewingPresentation(reinterpret_cast<std::uint32_t>(controller));
    RefreshInvigoratingElixer(reinterpret_cast<std::uint32_t>(controller));
    RefreshWeaponOilResearch(reinterpret_cast<std::uint32_t>(controller));
    RefreshPhoenixPhialResearch(reinterpret_cast<std::uint32_t>(controller));

    // Focused stock-boundary trace for multi-Laboratory eligibility. AP69's
    // row presenter owns the building-class/level gate, AP24 owns the shared
    // Palace Rage count, and AP24's click path owns the treasury check. Log
    // those same inputs once when CGBR is constructed; do not alter any state.
    unsigned char* context = LaboratoryPanelContext();
    char eligibilityTrace[256] = {};
    sprintf_s(
        eligibilityTrace,
        "Vigor eligibility at Brewing setup: context=0x%08X building=0x%08X "
        "selectedLevel=%d encodedClass=0x%08X rageCount=%d gold=%d active=%d.",
        reinterpret_cast<std::uint32_t>(context),
        context == nullptr ? 0u : *reinterpret_cast<std::uint32_t*>(context + 0x70),
        context == nullptr ? 0 : LaboratoryBuildingLevel(context),
        context == nullptr ? 0u : *reinterpret_cast<std::uint32_t*>(context + 0x7C),
        StockRageOfKrolmCount(),
        StockCurrentPlayerGold(),
        static_cast<int>(InterlockedCompareExchange(
            &g_invigoratingElixerActive, 0, 0)));
    WriteLog(eligibilityTrace);
}

int __fastcall BrewingControllerControl(
    void* controller, void*, std::uint32_t controlId) {
    if (controlId == kInvigoratingElixerControlId) {
        return HandleInvigoratingElixer(
            reinterpret_cast<std::uint32_t>(controller));
    }
    if (controlId == kWeaponOilResearchControlId) {
        return HandleWeaponOilResearch(
            reinterpret_cast<std::uint32_t>(controller));
    }
    if (controlId == kPhoenixPhialResearchControlId) {
        return HandlePhoenixPhialResearch(
            reinterpret_cast<std::uint32_t>(controller));
    }
    if (controlId == kArcaneInfusionVisualControlId) {
        return HandleArcaneInfusion(
            reinterpret_cast<std::uint32_t>(controller));
    }
    if (controlId == kPhilosophersStoneVisualControlId) {
        return HandlePhilosophersStone(
            reinterpret_cast<std::uint32_t>(controller));
    }
    return g_stockAp69Control(controller, controlId);
}

void __fastcall BrewingControllerEvent(
    void* controller,
    void*,
    std::uint32_t argument1,
    std::uint32_t argument2,
    std::uint32_t argument3,
    std::uint32_t argument4) {
    if (InterlockedCompareExchange(
            &g_laboratoryResearchCompletionStaged, 0, 0) != 0) {
        // CGBR inherits AP69 only for its stable streamed-panel controller.
        // A stock AP17 research completion never enters AP69's Fervus spell
        // event renderer. Preserve that class boundary during the one staged
        // completion update; the post-update AP99 refresh below the bridge
        // restores the completed private research rows immediately afterward.
        return;
    }
    g_stockAp69Event(controller, argument1, argument2, argument3, argument4);
    UpdateBrewingPresentation(reinterpret_cast<std::uint32_t>(controller));
    // AP99 0x004A9600 refreshes its research rows only for this exact event
    // set. Do not repaint the compound control every frame; doing so resets
    // its native in-progress drawing to the disabled base state.
    const bool stockResearchRefresh =
        (argument3 >= 0x18000000 && argument3 <= 0x2B000000) ||
        (argument2 == 0 && argument3 == 0x00505041) ||
        (argument2 == 1 &&
            (argument3 == kCurrentResearchAttributeId ||
             argument3 == 0x02425041));
    if (stockResearchRefresh) {
        RefreshInvigoratingElixer(reinterpret_cast<std::uint32_t>(controller));
        RefreshWeaponOilResearch(reinterpret_cast<std::uint32_t>(controller));
        RefreshPhoenixPhialResearch(reinterpret_cast<std::uint32_t>(controller));
    }
}

void ClearBrewingControllerOwnedState() {
    InterlockedExchange(&g_customBrewingHandle, 0);
    InterlockedExchange(&g_customBrewingActive, 0);
    InterlockedExchange(&g_captureBrewingController, 0);
    InterlockedExchange(&g_pendingSovereignControl, 0);
    InterlockedExchange(&g_pendingSovereignLaboratory, 0);
}

void __cdecl BrewingControllerDestroyed(void*, void*) {
    // The generic registry has already cleared g_customBrewingController after
    // proving this is still the exact captured instance. Invalidate only state
    // owned by that private child dialog; the live parent remains valid when
    // Majesty performs an ordinary secondary-panel transition.
    ClearBrewingControllerOwnedState();
    WriteLog(
        "Invalidated manager-owned secondary-controller state at Majesty's stock teardown boundary.");
}

bool InstallBrewingControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockAp69Setup == nullptr) {
        std::memcpy(
            g_customBrewingVtable,
            stockVtable,
            sizeof(g_customBrewingVtable));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_customBrewingVtable,
                stockVtable,
                kAp69VtableEntries,
                &g_customBrewingController,
                &BrewingControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private secondary controller because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockAp69Setup = reinterpret_cast<ControllerSetup>(stockVtable[1]);
        g_stockAp69Control = reinterpret_cast<ControllerControl>(stockVtable[3]);
        g_stockAp69Event = reinterpret_cast<ControllerEvent>(stockVtable[8]);
        g_customBrewingVtable[1] = reinterpret_cast<void*>(&BrewingControllerSetup);
        g_customBrewingVtable[3] = reinterpret_cast<void*>(&BrewingControllerControl);
        g_customBrewingVtable[8] = reinterpret_cast<void*>(&BrewingControllerEvent);
    }
    *objectVtable = g_customBrewingVtable;
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    if (panel != nullptr) {
        auto** panelVtable = *reinterpret_cast<void***>(panel);
        void* streamedDialog = *reinterpret_cast<void**>(
            reinterpret_cast<std::uintptr_t>(panel) + 4);
        auto** streamedDialogVtable = streamedDialog == nullptr
            ? nullptr
            : *reinterpret_cast<void***>(streamedDialog);
        char trace[256] = {};
        sprintf_s(
            trace,
            "Brewing panel dispatch: panel=0x%08X vtable=0x%08X visible=0x%08X "
            "message=0x%08X stream=0x%08X streamVtable=0x%08X streamMessage=0x%08X.",
            reinterpret_cast<std::uint32_t>(panel),
            reinterpret_cast<std::uint32_t>(panelVtable),
            reinterpret_cast<std::uint32_t>(panelVtable[0x20 / sizeof(void*)]),
            reinterpret_cast<std::uint32_t>(panelVtable[0x68 / sizeof(void*)]),
            reinterpret_cast<std::uint32_t>(streamedDialog),
            reinterpret_cast<std::uint32_t>(streamedDialogVtable),
            streamedDialogVtable == nullptr
                ? 0
                : reinterpret_cast<std::uint32_t>(
                      streamedDialogVtable[0x64 / sizeof(void*)]));
        WriteLog(trace);
        if (streamedDialog != nullptr) {
            using FindStreamControl = void* (__thiscall*)(void*, std::uint32_t);
            auto findControl = reinterpret_cast<FindStreamControl>(
                g_imageBase + g_buildProfile->findStreamControlRva);
            void* progress = findControl(
                streamedDialog, kInvigoratingElixerProgressControlId);
            void* activeDisplay = findControl(
                streamedDialog, kInvigoratingElixerActiveDisplayControlId);
            void* weaponOilProgress = findControl(
                streamedDialog, kWeaponOilProgressControlId);
            void* weaponOilActiveDisplay = findControl(
                streamedDialog, kWeaponOilActiveDisplayControlId);
            sprintf_s(
                trace,
                "Brewing stock control lookup: INSr/0x2009=0x%08X "
                "active/0x227A=0x%08X.",
                reinterpret_cast<std::uint32_t>(progress),
                reinterpret_cast<std::uint32_t>(activeDisplay));
            WriteLog(trace);
            sprintf_s(
                trace,
                "Weapon Oil AP24 display lookup: progress/0x2A11=0x%08X "
                "active/0x2A12=0x%08X.",
                reinterpret_cast<std::uint32_t>(weaponOilProgress),
                reinterpret_cast<std::uint32_t>(weaponOilActiveDisplay));
            WriteLog(trace);
        }
    }
    InterlockedExchange(
        &g_customBrewingController, static_cast<LONG>(controller));
    UpdateBrewingPresentation(controller);
    return true;
}

int __fastcall LaboratoryControllerControl(
    void* controller, void*, std::uint32_t controlId) {
    if (controlId == kBuildingUpgradeControlId) {
        using GetPanelContext = void* (__thiscall*)(void*);
        auto getPanelContext = reinterpret_cast<GetPanelContext>(
            g_imageBase + g_buildProfile->getPanelContextRva);
        void* context = getPanelContext(controller);
        if (!LaboratoryUpgradeResearchComplete(context)) {
            ApplyLaboratoryUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            WriteLog(
                "Rejected Laboratory upgrade through the stock Guardhouse prerequisite result.");
            return 0;
        }
    }
    if (controlId == kBrewingParentCommandId) {
        if (InterlockedCompareExchange(&g_customBrewingActive, 0, 0) == 1) {
            // AP10 translates visual control 0x1F44 into command 0x1F49. Consume
            // that command before stock closes the primary panel and opens AP69.
            WriteLog("Ignored repeated Brewing command with AP10's stock no-action result.");
            return 0;
        }
        // Arm on AP10's actual secondary-panel command, not when the parent
        // CGAL panel opens. Stock APd1 guild-member navigation may legitimately
        // occur between parent-panel creations; it must not own or cancel this
        // one-command handoff.
        InterlockedExchange(&g_cgalSecondaryArmed, 1);
        WriteLog("Armed CGAL secondary mapping from AP10's stock Brewing command.");
        return g_stockLaboratoryControl(controller, controlId);
    }
    const int result = g_stockLaboratoryControl(controller, controlId);
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    ApplyLaboratoryUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), getPanelContext(controller));
    return result;
}

void __fastcall LaboratoryControllerSetup(void* controller, void*) {
    g_stockLaboratorySetup(controller);

    // The stock dialog-creation lifecycle does not finish at the factory
    // result. It inserts and lays out the returned controller, then invokes
    // vtable slot 1 as the final setup presenter. AP17 applies its Guardhouse
    // prerequisite at this boundary. Run the same disabled-control/hidden-
    // price presentation only after AP10 has finished publishing its normal
    // upgrade row, changing solely the Laboratory's prerequisite attribute.
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    void* context = getPanelContext(controller);
    ApplyLaboratoryUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), context);
}

void __fastcall LaboratoryControllerActivity(void* controller, void*) {
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    auto* context = static_cast<unsigned char*>(getPanelContext(controller));
    if (context != nullptr) {
        if (InterlockedCompareExchange(
                &g_laboratoryResearchCompletionStaged, 0, 0) != 0) {
            // AP17 never invokes AP10's guild-activity renderer during its
            // stock research completion update. CurrentResearch is cleared
            // partway through that update, and an upgrade may replace CGAL's
            // live panel context. This vtable exists only on CGAL, so preserve
            // the stock class boundary for every CGAL activity pass across
            // the complete staged lifecycle.
            ApplyLaboratoryUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            return;
        }
        using ReadPackedAttribute = int (__thiscall*)(
            void*, std::uint32_t, std::uint32_t);
        auto readPackedAttribute = reinterpret_cast<ReadPackedAttribute>(
            g_imageBase + g_buildProfile->readPackedAttributeRva);
        const int currentResearch = readPackedAttribute(
            context, kCurrentResearchAttributeId, 0);
        if (currentResearch == static_cast<int>(kWeaponOilResearchControlId) ||
            currentResearch == static_cast<int>(kPhoenixPhialResearchControlId)) {
            // AP17 does not run AP10's guild-activity renderer while its
            // native research command owns CurrentResearch. Preserve that
            // stock class boundary for the combined CGAL/AP99 surface.
            ApplyLaboratoryUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            return;
        }
    }
    g_stockLaboratoryActivity(controller);
    ApplyLaboratoryUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), context);
}

void __fastcall LaboratoryControllerEvent(
    void* controller,
    void*,
    std::uint32_t argument1,
    std::uint32_t argument2,
    std::uint32_t argument3,
    std::uint32_t argument4) {
    // AP10 slot 8 is its native building/event refresh boundary. It calls the
    // base upgrade presenter directly at beta2 0x004969DD and again from the
    // shared attribute-event handler at 0x00496241/67/D3, so neither call
    // passes through AP10 slot 1 or slot 13. Let that complete unchanged, then
    // apply the prerequisite presentation to the final stock row state.
    g_stockLaboratoryEvent(
        controller, argument1, argument2, argument3, argument4);
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    ApplyLaboratoryUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), getPanelContext(controller));
}

void __cdecl LaboratoryControllerDestroyed(void*, void*) {
    // The parent controller owns every borrowed context used by its private
    // secondary panel. Once stock destroys that exact parent, invalidate the
    // complete dependent UI chain. Gameplay state and active effects remain
    // under their native simulation lifecycles.
    InterlockedExchange(&g_captureCgalController, 0);
    InterlockedExchange(&g_cgalSecondaryArmed, 0);
    InterlockedExchange(&g_ap10ControllerContext, 0);
    InterlockedExchange(&g_cgalControllerContext, 0);
    InterlockedExchange(&g_customBrewingController, 0);
    ClearBrewingControllerOwnedState();
    WriteLog(
        "Invalidated manager-owned parent-controller state at Majesty's stock teardown boundary.");
}

bool InstallLaboratoryControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockLaboratoryControl == nullptr) {
        std::memcpy(
            g_customLaboratoryVtable,
            stockVtable,
            sizeof(g_customLaboratoryVtable));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_customLaboratoryVtable,
                stockVtable,
                kAp10VtableEntries,
                &g_cgalController,
                &LaboratoryControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private parent controller because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockLaboratorySetup =
            reinterpret_cast<ControllerSetup>(stockVtable[1]);
        g_stockLaboratoryControl =
            reinterpret_cast<ControllerControl>(stockVtable[3]);
        g_stockLaboratoryEvent =
            reinterpret_cast<ControllerEvent>(stockVtable[8]);
        g_stockLaboratoryActivity =
            reinterpret_cast<ControllerActivity>(stockVtable[13]);
        g_customLaboratoryVtable[1] =
            reinterpret_cast<void*>(&LaboratoryControllerSetup);
        g_customLaboratoryVtable[3] =
            reinterpret_cast<void*>(&LaboratoryControllerControl);
        g_customLaboratoryVtable[8] =
            reinterpret_cast<void*>(&LaboratoryControllerEvent);
        g_customLaboratoryVtable[13] =
            reinterpret_cast<void*>(&LaboratoryControllerActivity);
    }
    *objectVtable = g_customLaboratoryVtable;
    return true;
}

extern "C" void __stdcall CaptureSecondaryController(
    std::uint32_t controller,
    std::uint32_t creationHandle) {
    if (controller == 0) {
        return;
    }
    if (InterlockedExchange(&g_captureCgalController, 0) == 1) {
        InterlockedExchange(&g_cgalController, static_cast<LONG>(controller));
        if (!InstallLaboratoryControllerVtable(controller)) {
            InterlockedCompareExchange(
                &g_cgalController, 0, static_cast<LONG>(controller));
            return;
        }
        WriteLog("Captured the Laboratory and installed its scoped AP10 command guard.");
        return;
    }
    if (InterlockedExchange(&g_captureBrewingController, 0) == 1) {
        InterlockedExchange(
            &g_customBrewingHandle, static_cast<LONG>(creationHandle));
        if (!InstallBrewingControllerVtable(controller)) {
            ClearBrewingControllerOwnedState();
            return;
        }
        WriteLog("Captured the custom Brewing controller and installed its scoped vtable.");
    }
}

void DismissCustomBrewing() {
    const auto handle = static_cast<std::uint32_t>(
        InterlockedExchange(&g_customBrewingHandle, 0));
    InterlockedExchange(&g_customBrewingController, 0);
    InterlockedExchange(&g_cgalController, 0);
    ClearBrewingControllerOwnedState();
    if (handle == 0 || g_imageBase == 0) {
        return;
    }
    using GetUiManager = void* (__cdecl*)();
    using RemoveDialog = void (__thiscall*)(void*, void*);
    auto getUiManager = reinterpret_cast<GetUiManager>(g_imageBase + g_buildProfile->uiManagerRva);
    auto removeDialog = reinterpret_cast<RemoveDialog>(g_imageBase + g_buildProfile->removeDialogRva);
    void* manager = getUiManager();
    if (manager != nullptr) {
        removeDialog(manager, reinterpret_cast<void*>(handle));
        WriteLog("Dismissed custom Brewing with Majesty's native dialog-removal API.");
    }
}

LRESULT CALLBACK RuntimeWindowProcedure(
    HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    const LRESULT result = CallWindowProcA(
        g_originalWindowProcedure, window, message, wParam, lParam);
    if (message == WM_RBUTTONDOWN && static_cast<short>(LOWORD(lParam)) >= kSidebarWidth) {
        InterlockedExchange(&g_pendingSovereignControl, 0);
        InterlockedExchange(&g_pendingSovereignLaboratory, 0);
        DismissCustomBrewing();
    }
    return result;
}

BOOL CALLBACK FindRuntimeWindow(HWND window, LPARAM parameter) {
    DWORD processId = 0;
    GetWindowThreadProcessId(window, &processId);
    if (processId != GetCurrentProcessId() || GetWindow(window, GW_OWNER) != nullptr) {
        return TRUE;
    }
    *reinterpret_cast<HWND*>(parameter) = window;
    return FALSE;
}

bool InstallWindowProcedureHook() {
    HWND window = nullptr;
    for (int attempt = 0; attempt < 300 && window == nullptr; ++attempt) {
        EnumWindows(FindRuntimeWindow, reinterpret_cast<LPARAM>(&window));
        if (window == nullptr) {
            Sleep(100);
        }
    }
    if (window == nullptr) {
        WriteLog("Window hook failed: Majesty's top-level window was not found.");
        return false;
    }
    SetLastError(0);
    const auto previous = SetWindowLongPtrA(
        window, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&RuntimeWindowProcedure));
    if (previous == 0 && GetLastError() != 0) {
        WriteLog("Window hook failed: SetWindowLongPtr rejected the subclass.");
        return false;
    }
    g_originalWindowProcedure = reinterpret_cast<WNDPROC>(previous);
    WriteLog("Installed scoped map-right-click lifecycle hook.");
    return true;
}

extern "C" void __stdcall LogSuppressedNullSecondaryController() {
    WriteLog("Suppressed a null secondary controller result without opening a diagnostic window.");
}

void LogDialogFactoryRequest(
    const std::uint32_t* arguments,
    std::uint32_t requestedId,
    const char* suffix = "") {
    char text[256] = {};
    const char a = static_cast<char>(requestedId & 0xFF);
    const char b = static_cast<char>((requestedId >> 8) & 0xFF);
    const char c = static_cast<char>((requestedId >> 16) & 0xFF);
    const char d = static_cast<char>((requestedId >> 24) & 0xFF);
    sprintf_s(
        text,
        "Dialog factory request: original=0x%08X ('%c%c%c%c') effective=0x%08X "
        "arg2=0x%08X arg3=0x%08X arg4=0x%08X caller=0x%08X.%s",
        requestedId,
        a >= 32 && a <= 126 ? a : '.',
        b >= 32 && b <= 126 ? b : '.',
        c >= 32 && c <= 126 ? c : '.',
        d >= 32 && d <= 126 ? d : '.',
        arguments[0],
        arguments[1],
        arguments[2],
        arguments[3],
        arguments[-1],
        suffix);
    WriteLog(text);
}

extern "C" void __stdcall ResolveDialogFactoryRequest(std::uint32_t* idAddress) {
    const std::uint32_t requested = *idAddress;
    if (requested == kCgbrDialogId) {
        *idAddress = kAp69DialogId;
        LogDialogFactoryRequest(
            idAddress,
            requested,
            " Mapped CGBR resources to the stock AP69 controller class.");
        return;
    }
    if (requested == kAp10DialogId && idAddress[2] != 0) {
        InterlockedExchange(
            &g_ap10ControllerContext, static_cast<LONG>(idAddress[2]));
        InterlockedExchange(&g_cgalSecondaryArmed, 0);
        LogDialogFactoryRequest(
            idAddress, requested, " Captured AP10 controller context.");
        return;
    }
    if (requested == kCgalDialogId) {
        LogDialogFactoryRequest(idAddress, requested);
        return;
    }
    if (requested == 0 && InterlockedCompareExchange(&g_cgalSecondaryArmed, 0, 1) == 1) {
        const auto cgalContext = idAddress[2] != 0
            ? idAddress[2]
            : static_cast<std::uint32_t>(InterlockedCompareExchange(
                  &g_cgalControllerContext, 0, 0));
        if (cgalContext == 0) {
            LogDialogFactoryRequest(
                idAddress, requested,
                " Laboratory controller context unavailable; left request unmapped.");
            return;
        }
        *idAddress = kAp69DialogId;
        idAddress[2] = cgalContext;
        LogDialogFactoryRequest(
            idAddress, requested,
            " Translated armed CGAL secondary request to AP69 with its Laboratory context.");
        return;
    }
    if (InterlockedExchange(&g_cgalSecondaryArmed, 0) == 1) {
        LogDialogFactoryRequest(
            idAddress, requested, " Disarmed CGAL mapping on a nonzero intervening request.");
        return;
    }
    LogDialogFactoryRequest(idAddress, requested);
}

extern "C" void __stdcall ResolveDialogCreationRequest(std::uint32_t* arguments) {
    const std::uint32_t requested = arguments[0];
    char trace[224] = {};
    sprintf_s(
        trace,
        "Dialog creation entry: id=0x%08X context=0x%08X owner=0x%08X arg4=0x%08X.",
        arguments[0], arguments[1], arguments[2], arguments[3]);
    WriteLog(trace);
    const bool brewingActive =
        InterlockedCompareExchange(&g_customBrewingActive, 0, 0) == 1;
    const auto cgalContext = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_cgalControllerContext, 0, 0));
    if (brewingActive && requested == kAp10DialogId &&
        InterlockedCompareExchange(&g_customBrewingActive, 0, 1) == 1) {
        InterlockedExchange(&g_customBrewingHandle, 0);
        InterlockedExchange(&g_customBrewingController, 0);
        if (cgalContext != 0) {
            arguments[0] = kCgalDialogId;
            arguments[1] = cgalContext;
            InterlockedExchange(&g_captureCgalController, 1);
            WriteLog("Redirected custom Brewing Back request from AP10 to CGAL.");
            return;
        }
        WriteLog("Brewing Back request had no captured CGAL context; left AP10 unchanged.");
    } else if (brewingActive && arguments[1] != 0 &&
        InterlockedCompareExchange(&g_customBrewingActive, 0, 1) == 1) {
        // Majesty's controller-backed sidebar dialogs carry a nonzero context.
        // Auxiliary notifications such as AP36 carry context zero and do not
        // replace or destroy the still-live Brewing controller.
        InterlockedExchange(&g_customBrewingHandle, 0);
        InterlockedExchange(&g_customBrewingController, 0);
        WriteLog("Cleared custom Brewing state on a controller-backed dialog replacement.");
    }
    if (requested == kAp10DialogId && arguments[1] != 0) {
        InterlockedExchange(
            &g_ap10ControllerContext, static_cast<LONG>(arguments[1]));
        InterlockedExchange(&g_cgalSecondaryArmed, 0);
        WriteLog("Creation entry captured AP10 context before setup-object construction.");
        return;
    }
    if (requested == kCgalDialogId) {
        if (arguments[1] != 0) {
            InterlockedExchange(
                &g_cgalControllerContext, static_cast<LONG>(arguments[1]));
        }
        InterlockedExchange(&g_captureCgalController, 1);
        WriteLog("Creation entry captured CGAL without arming a secondary request.");
        return;
    }
    if (requested == 0 && InterlockedCompareExchange(&g_cgalSecondaryArmed, 0, 1) == 1) {
        const auto requestContext = arguments[1] != 0
            ? arguments[1]
            : static_cast<std::uint32_t>(InterlockedCompareExchange(
                  &g_cgalControllerContext, 0, 0));
        if (requestContext == 0) {
            WriteLog(
                "Creation entry found no Laboratory context; left CGAL secondary request unmapped.");
            return;
        }
        arguments[0] = kCgbrDialogId;
        arguments[1] = requestContext;
        InterlockedExchange(&g_customBrewingActive, 1);
        InterlockedExchange(&g_captureBrewingController, 1);
        WriteLog(
            "Creation entry translated CGAL secondary request to CGBR with its Laboratory context.");
        return;
    }
    InterlockedExchange(&g_cgalSecondaryArmed, 0);
}

__declspec(naked) void DialogCreationHook() {
    __asm {
        lea eax, dword ptr [esp + 4]
        pushfd
        pushad
        push eax
        call ResolveDialogCreationRequest
        popad
        popfd
        jmp dword ptr [g_creationTrampoline]
    }
}

__declspec(naked) void DialogFactoryTraceHook() {
    __asm {
        lea eax, dword ptr [esp + 4]
        pushfd
        pushad
        push eax
        call ResolveDialogFactoryRequest
        popad
        popfd
        jmp dword ptr [g_factoryTrampoline]
    }
}

__declspec(naked) void SecondaryControllerResultHook() {
    __asm {
        pushfd
        pushad
        push esi
        push eax
        call CaptureSecondaryController
        popad
        popfd

        test eax, eax
        jz no_controller

        mov ebp, dword ptr [ebx + 24h]
        add ebx, 10h
        jmp dword ptr [g_resumeWithController]

    no_controller:
        pushfd
        pushad
        call LogSuppressedNullSecondaryController
        popad
        popfd
        pop edi
        xor eax, eax
        pop esi
        pop ebp
        pop ebx
        add esp, 8
        ret 10h
    }
}

// AP78 has no generic data-driven Enchantments presenter. Its stock refresh
// reads each active effector's overlay FourCC and switches over a fixed list.
// Preserve that entire switch and row builder: only alias the three private
// persistent coating presenters to the existing XR01 row, then substitute the
// row text at XR01's unchanged stock string-assignment call.
__declspec(naked) void HeroEnchantmentsSwitchHook() {
    __asm {
        mov dword ptr [g_privateEnchantmentRowKind], 0
        cmp eax, 316F4C41h
        je paralytic_oil
        cmp eax, 326F4C41h
        je transmutation_oil
        cmp eax, 336F4C41h
        je poisoned_weapon
    replay_stock_compare:
        cmp eax, 32425243h
        jmp dword ptr [g_heroEnchantmentsSwitchResume]
    paralytic_oil:
        mov dword ptr [g_privateEnchantmentRowKind], 1
        mov eax, 31305258h
        jmp replay_stock_compare
    transmutation_oil:
        mov dword ptr [g_privateEnchantmentRowKind], 2
        mov eax, 31305258h
        jmp replay_stock_compare
    poisoned_weapon:
        mov dword ptr [g_privateEnchantmentRowKind], 3
        mov eax, 31305258h
        jmp replay_stock_compare
    }
}

__declspec(naked) void PrivateEnchantmentRowStringHook() {
    __asm {
        mov eax, dword ptr [g_privateEnchantmentRowKind]
        cmp eax, 1
        je paralytic_oil
        cmp eax, 2
        je transmutation_oil
        cmp eax, 3
        je poisoned_weapon
        jmp dword ptr [g_stockStringAssign]
    paralytic_oil:
        mov eax, offset g_paralyticOilEnchantmentString
        mov dword ptr [esp + 4], eax
        jmp dword ptr [g_stockStringAssign]
    transmutation_oil:
        mov eax, offset g_transmutationOilEnchantmentString
        mov dword ptr [esp + 4], eax
        jmp dword ptr [g_stockStringAssign]
    poisoned_weapon:
        mov eax, offset g_poisonedWeaponEnchantmentString
        mov dword ptr [esp + 4], eax
        jmp dword ptr [g_stockStringAssign]
    }
}

bool InstallPrivateEnchantmentRows() {
    auto* switchSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->heroEnchantmentsSwitchRva);
    auto* stringCall = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->speedTonicRowStringCallRva);
    if (g_buildProfile->heroEnchantmentsSwitchResumeRva !=
            g_buildProfile->heroEnchantmentsSwitchRva + 5 ||
        std::memcmp(
            switchSite,
            g_buildProfile->expectedHeroEnchantmentsSwitch,
            sizeof(g_buildProfile->expectedHeroEnchantmentsSwitch)) != 0 ||
        std::memcmp(
            stringCall,
            g_buildProfile->expectedSpeedTonicRowStringCall,
            sizeof(g_buildProfile->expectedSpeedTonicRowStringCall)) != 0) {
        WriteLog("Private Enchantments rows refused: AP78 stock bytes changed after preflight.");
        return false;
    }

    g_heroEnchantmentsSwitchResume =
        g_imageBase + g_buildProfile->heroEnchantmentsSwitchResumeRva;
    g_stockStringAssign = g_imageBase + g_buildProfile->stockStringAssignRva;
    const auto switchRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&HeroEnchantmentsSwitchHook) -
        (reinterpret_cast<std::uintptr_t>(switchSite) + 5));
    const auto stringRelative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&PrivateEnchantmentRowStringHook) -
        (reinterpret_cast<std::uintptr_t>(stringCall) + 5));
    unsigned char switchPatch[5] = {0xE9, 0, 0, 0, 0};
    unsigned char stringPatch[5] = {0xE8, 0, 0, 0, 0};
    std::memcpy(switchPatch + 1, &switchRelative, sizeof(switchRelative));
    std::memcpy(stringPatch + 1, &stringRelative, sizeof(stringRelative));

    DWORD switchProtection = 0;
    if (!VirtualProtect(
            switchSite,
            sizeof(switchPatch),
            PAGE_EXECUTE_READWRITE,
            &switchProtection)) {
        WriteLog("Private Enchantments rows failed: AP78 switch is not writable.");
        return false;
    }
    DWORD stringProtection = 0;
    if (!VirtualProtect(
            stringCall,
            sizeof(stringPatch),
            PAGE_EXECUTE_READWRITE,
            &stringProtection)) {
        DWORD ignored = 0;
        VirtualProtect(
            switchSite,
            sizeof(switchPatch),
            switchProtection,
            &ignored);
        WriteLog("Private Enchantments rows failed: AP78 string call is not writable.");
        return false;
    }

    std::memcpy(switchSite, switchPatch, sizeof(switchPatch));
    std::memcpy(stringCall, stringPatch, sizeof(stringPatch));
    FlushInstructionCache(GetCurrentProcess(), switchSite, sizeof(switchPatch));
    FlushInstructionCache(GetCurrentProcess(), stringCall, sizeof(stringPatch));
    DWORD ignored = 0;
    VirtualProtect(
        switchSite,
        sizeof(switchPatch),
        switchProtection,
        &ignored);
    VirtualProtect(
        stringCall,
        sizeof(stringPatch),
        stringProtection,
        &ignored);
    WriteLog("Installed scoped AP78 rows for Paralytic Oil, Transmutation Oil, and Poisoned Weapon.");
    return true;
}

void WritePrivateNameGeneratorLog(
    const char* generatorId,
    const char* detail) {
    char message[256] = {};
    std::snprintf(
        message,
        sizeof(message),
        "Private %s registration %s",
        generatorId,
        detail);
    WriteLog(message);
}

void RegisterPrivateStockNameGenerator(
    void* registry,
    void* resourceManager,
    std::uint32_t generatorId,
    std::uint32_t firstNamePartId,
    std::uint32_t secondNamePartId,
    std::uint32_t thirdNamePartId,
    std::uint32_t fourthNamePartId,
    const char* generatorLabel) {
    if (registry == nullptr || resourceManager == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "skipped: the stock registry context was incomplete.");
        return;
    }

    using FindOrInsert = void** (__thiscall*)(void*, const std::uint32_t*);
    auto findOrInsert = reinterpret_cast<FindOrInsert>(
        g_imageBase + g_buildProfile->nameRegistryFindOrInsertRva);
    auto* map = static_cast<unsigned char*>(registry) + 4;

    // Stock inserts NM01 through NM17 into this exact map before setting the
    // registry's ready flag. Read NM17 only to copy the wrapper vtable that
    // stock has already established for every entry. This avoids introducing
    // any private object layout or destructor path.
    std::uint32_t stockKey = kStockLastNameGeneratorId;
    void** stockSlot = findOrInsert(map, &stockKey);
    if (stockSlot == nullptr || *stockSlot == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: stock NM17 was not present at registry completion.");
        return;
    }

    std::uint32_t privateKey = generatorId;
    void** privateSlot = findOrInsert(map, &privateKey);
    if (privateSlot == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: the stock map returned no value slot.");
        return;
    }
    if (*privateSlot != nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "refused: another generator already owns that ID.");
        return;
    }

    using StockOperatorNew = void* (__cdecl*)(std::size_t);
    auto stockOperatorNew = reinterpret_cast<StockOperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    auto* wrapper = static_cast<void**>(stockOperatorNew(8));
    if (wrapper == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: the stock allocator returned null.");
        return;
    }

    // This is the literal stock NMxx construction sequence. The factory owns
    // the 0x40-byte name generator, the four HN IDs are its ordered name
    // fragments, and the game's resource manager remains the final argument.
    using NameGeneratorFactory = void* (__cdecl*)();
    using ConstructNameGenerator = void* (__thiscall*)(
        void*,
        std::uint32_t,
        std::uint32_t,
        std::uint32_t,
        std::uint32_t,
        void*);
    auto getFactory = reinterpret_cast<NameGeneratorFactory>(
        g_imageBase + g_buildProfile->nameGeneratorFactoryRva);
    auto construct = reinterpret_cast<ConstructNameGenerator>(
        g_imageBase + g_buildProfile->nameGeneratorConstructRva);
    void* generator = construct(
        getFactory(),
        firstNamePartId,
        secondNamePartId,
        thirdNamePartId,
        fourthNamePartId,
        resourceManager);
    if (generator == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: the stock name generator constructor returned null.");
        return;
    }

    wrapper[0] = *static_cast<void***>(*stockSlot);
    wrapper[1] = generator;
    *privateSlot = wrapper;
    char message[256] = {};
    std::snprintf(
        message,
        sizeof(message),
        "Registered private %s through Majesty's stock name-generator registry lifecycle.",
        generatorLabel);
    WriteLog(message);
}

extern "C" void __stdcall RegisterRequestedPrivateNameGenerators(
    void* registry,
    void* resourceManager) {
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kAlchemistNameGenerator)) {
        RegisterPrivateStockNameGenerator(
            registry,
            resourceManager,
            kAlchemistNameGeneratorId,
            kAlchemistGivenNamesId,
            kAlchemistEndingsId,
            kAlchemistThirdNamePartId,
            kAlchemistFourthNamePartId,
            "NM18");
    }
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kPhantomNameGenerator)) {
        RegisterPrivateStockNameGenerator(
            registry,
            resourceManager,
            kPhantomNameGeneratorId,
            kPhantomGivenNamesId,
            kPhantomEndingsId,
            kPhantomThirdNamePartId,
            kPhantomFourthNamePartId,
            "NM19");
    }
}

__declspec(naked) void NameRegistryCompletionHook() {
    __asm {
        mov eax, dword ptr [esp + 1Ch]
        pushfd
        pushad
        push ebp
        push eax
        call RegisterRequestedPrivateNameGenerators
        popad
        popfd

        mov eax, dword ptr [esp + 1Ch]
        mov dword ptr [eax + 24h], ebx
        jmp dword ptr [g_nameRegistryCompletionResume]
    }
}

bool InstallPrivateNameGenerators() {
    auto* site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->nameRegistryCompletionRva);
    if (std::memcmp(
            site,
            g_buildProfile->expectedNameRegistryCompletion,
            sizeof(g_buildProfile->expectedNameRegistryCompletion)) != 0) {
        WriteLog(
            "Private name-generator registration refused: stock registry completion bytes changed after preflight.");
        return false;
    }
    g_nameRegistryCompletionResume =
        reinterpret_cast<std::uintptr_t>(site) +
        sizeof(g_buildProfile->expectedNameRegistryCompletion);
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&NameRegistryCompletionHook) -
        (reinterpret_cast<std::uintptr_t>(site) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedNameRegistryCompletion)] = {
        0xE9, 0, 0, 0, 0, 0x90, 0x90};
    std::memcpy(patch + 1, &relative, sizeof(relative));

    DWORD oldProtection = 0;
    if (!VirtualProtect(
            site,
            sizeof(patch),
            PAGE_EXECUTE_READWRITE,
            &oldProtection)) {
        WriteLog(
            "Private name-generator registration failed: registry completion is not writable.");
        return false;
    }
    std::memcpy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite(
        "stock name-registry extension for requested private generators",
        g_buildProfile->nameRegistryCompletionRva);
    return true;
}

bool InstallDialogFactoryTrace() {
    const auto imageBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    auto* entry = reinterpret_cast<unsigned char*>(imageBase + g_buildProfile->dialogFactoryRva);
    if (std::memcmp(entry, g_buildProfile->expectedFactoryEntry, sizeof(g_buildProfile->expectedFactoryEntry)) != 0) {
        WriteLog("Factory trace refused: dialog-factory entry bytes are unknown.");
        return false;
    }
    auto* trampoline = reinterpret_cast<unsigned char*>(VirtualAlloc(
        nullptr, sizeof(g_buildProfile->expectedFactoryEntry) + 5, MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        WriteLog("Factory trace failed: trampoline allocation was rejected.");
        return false;
    }
    std::memcpy(trampoline, g_buildProfile->expectedFactoryEntry, sizeof(g_buildProfile->expectedFactoryEntry));
    trampoline[sizeof(g_buildProfile->expectedFactoryEntry)] = 0xE9;
    const auto returnAddress = imageBase + g_buildProfile->dialogFactoryRva + sizeof(g_buildProfile->expectedFactoryEntry);
    const auto trampolineJump = static_cast<std::int32_t>(
        returnAddress - (reinterpret_cast<std::uintptr_t>(trampoline) +
                         sizeof(g_buildProfile->expectedFactoryEntry) + 5));
    std::memcpy(trampoline + sizeof(g_buildProfile->expectedFactoryEntry) + 1, &trampolineJump, 4);
    g_factoryTrampoline = reinterpret_cast<std::uintptr_t>(trampoline);

    const auto hookAddress = reinterpret_cast<std::uintptr_t>(&DialogFactoryTraceHook);
    const auto relative = static_cast<std::int32_t>(
        hookAddress - (reinterpret_cast<std::uintptr_t>(entry) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedFactoryEntry)] = {0xE9, 0, 0, 0, 0, 0x90, 0x90};
    std::memcpy(patch + 1, &relative, 4);
    DWORD oldProtection = 0;
    if (!VirtualProtect(entry, sizeof(patch), PAGE_EXECUTE_READWRITE, &oldProtection)) {
        WriteLog("Factory trace failed: VirtualProtect rejected the entry.");
        return false;
    }
    std::memcpy(entry, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(entry, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite("read-only dialog-factory request trace", g_buildProfile->dialogFactoryRva);
    return true;
}

bool InstallDialogCreationHook() {
    const auto imageBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    auto* entry = reinterpret_cast<unsigned char*>(imageBase + g_buildProfile->dialogCreationRva);
    if (std::memcmp(entry, g_buildProfile->expectedCreationEntry, sizeof(g_buildProfile->expectedCreationEntry)) != 0) {
        WriteLog("Creation hook refused: dialog-creation entry bytes are unknown.");
        return false;
    }
    auto* trampoline = reinterpret_cast<unsigned char*>(VirtualAlloc(
        nullptr, sizeof(g_buildProfile->expectedCreationEntry) + 5, MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        WriteLog("Creation hook failed: trampoline allocation was rejected.");
        return false;
    }
    std::memcpy(trampoline, g_buildProfile->expectedCreationEntry, sizeof(g_buildProfile->expectedCreationEntry));
    trampoline[sizeof(g_buildProfile->expectedCreationEntry)] = 0xE9;
    const auto returnAddress = imageBase + g_buildProfile->dialogCreationRva + sizeof(g_buildProfile->expectedCreationEntry);
    const auto trampolineJump = static_cast<std::int32_t>(
        returnAddress - (reinterpret_cast<std::uintptr_t>(trampoline) +
                         sizeof(g_buildProfile->expectedCreationEntry) + 5));
    std::memcpy(trampoline + sizeof(g_buildProfile->expectedCreationEntry) + 1, &trampolineJump, 4);
    g_creationTrampoline = reinterpret_cast<std::uintptr_t>(trampoline);

    const auto hookAddress = reinterpret_cast<std::uintptr_t>(&DialogCreationHook);
    const auto relative = static_cast<std::int32_t>(
        hookAddress - (reinterpret_cast<std::uintptr_t>(entry) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedCreationEntry)] = {0xE9, 0, 0, 0, 0, 0x90, 0x90};
    std::memcpy(patch + 1, &relative, 4);
    DWORD oldProtection = 0;
    if (!VirtualProtect(entry, sizeof(patch), PAGE_EXECUTE_READWRITE, &oldProtection)) {
        WriteLog("Creation hook failed: VirtualProtect rejected the entry.");
        return false;
    }
    std::memcpy(entry, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(entry, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite("pre-setup dialog-creation hook", g_buildProfile->dialogCreationRva);
    return true;
}

bool InstallSecondaryControllerHook() {
    const auto imageBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    if (imageBase == 0) {
        WriteLog("Runtime installation failed: Majesty module base is unavailable.");
        return false;
    }
    auto* resultSite = reinterpret_cast<unsigned char*>(imageBase + g_buildProfile->secondaryControllerResultRva);
    if (std::memcmp(resultSite, g_buildProfile->expectedResultSite, sizeof(g_buildProfile->expectedResultSite)) != 0) {
        WriteLog("Runtime installation refused: secondary-controller result-site bytes are unknown.");
        return false;
    }

    g_resumeWithController = imageBase + g_buildProfile->secondaryControllerResultRva + sizeof(g_buildProfile->expectedResultSite);

    const auto hookAddress = reinterpret_cast<std::uintptr_t>(&SecondaryControllerResultHook);
    const auto relative = static_cast<std::int32_t>(
        hookAddress - (reinterpret_cast<std::uintptr_t>(resultSite) + 5));
    unsigned char patch[sizeof(g_buildProfile->expectedResultSite)] = {0xE9, 0, 0, 0, 0, 0x90};
    std::memcpy(patch + 1, &relative, sizeof(relative));

    DWORD oldProtection = 0;
    if (!VirtualProtect(resultSite, sizeof(patch), PAGE_EXECUTE_READWRITE, &oldProtection)) {
        WriteLog("Runtime installation failed: VirtualProtect rejected the hook site.");
        return false;
    }
    std::memcpy(resultSite, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), resultSite, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(resultSite, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite(
        "pre-insertion CGAL secondary-controller hook",
        g_buildProfile->secondaryControllerResultRva);
    return true;
}

DWORD WINAPI InitializeRuntime(void*) {
    g_imageBase = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    const CapabilityManifestState capabilityManifest =
        LoadRuntimeCapabilityManifest();
    if (capabilityManifest == CapabilityManifestState::Absent) {
        // A DLL injection without MMCP is not a Mod Manager launch. Fail
        // closed by leaving every optional stock hook untouched.
        return 0;
    }
    if (capabilityManifest == CapabilityManifestState::Invalid) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the supplied capability manifest is invalid.");
    }
    const bool managerLaunch = true;
    const bool privateActivityText = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kPrivateActivityText);
    const bool freestyleCam = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kFreestyleCamRebind);
    const bool expandedBuildingSlots = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kExpandedBuildingSlots);
    const bool alchemistNames = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kAlchemistNameGenerator);
    const bool phantomNames = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kPhantomNameGenerator);
    const bool alchemistSecondary = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kAlchemistSecondaryController);
    const bool alchemistOilRows = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kAlchemistPrivateOilRows);

    if (!SelectMajestyBuildProfile() || !ValidateMajestyBuildProfile()) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the executable does not match every declared runtime capability profile.");
    }

    if (privateActivityText) {
        const PrivateIntentRegistryState intentRegistry =
            LoadPrivateIntentRegistry();
        if (intentRegistry != PrivateIntentRegistryState::Loaded) {
            StopUnsafeManagerRuntimeLaunch(
                "Terminating manager launch before Majesty resumes: private activity text was declared without a valid non-empty intent registry.");
        }
        if (!ValidatePrivateIntentTextProfile()) {
            StopUnsafeManagerRuntimeLaunch(
                "Terminating manager launch before Majesty resumes: the shared activity-text resolver does not match its selected profile.");
        }
    }
#if defined(CAM_SIEGE_CRASH_DIAGNOSTIC)
    if (!InstallCrashDumpDiagnostic(
            g_runtimeModule, g_imageBase, g_buildProfile->id)) {
        WriteLog("Siege crash full-memory diagnostic was not installed.");
    } else {
        WriteLog("Installed logging-only full-memory capture for the diagnosed GPL evaluator fault.");
    }
#endif

    if (privateActivityText) {
        RequireManagerRuntimeInstall(
            InstallPrivateIntentTextResolver(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the manager-owned activity-text resolver could not be installed.");
    }
    if (freestyleCam) {
        RequireManagerRuntimeInstall(
            InstallFreestyleCamRuntime(g_runtimeModule, g_buildProfile->id),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the Freestyle CAM lifecycle repair could not be installed.");
    }
    if (expandedBuildingSlots) {
        RequireManagerRuntimeInstall(
            InstallCustomGuildFactoryFallback(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the custom-guild factory fallback could not be installed.");
    }
    if (alchemistNames || phantomNames) {
        RequireManagerRuntimeInstall(
            InstallPrivateNameGenerators(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private name registry could not be installed.");
    }

    if (alchemistSecondary) {
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            ValidateStockResearchRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the stock research route did not match the selected executable profile.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallPrivateWeaponOilResearchDescriptor(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private Weapon Oil research descriptor could not be installed.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallResearchCompletionBridge(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the stock research-completion bridge could not be installed.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallResearchCompletionNameClone(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private research-completion name clone could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateInvigoratingSpellDescriptor(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private spell descriptor resolver could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateSovereignSpellRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private reagent spell route could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateRageRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private Rage command route could not be installed.");
        RequireManagerRuntimeInstall(
            InstallDialogCreationHook(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the dialog-creation hook could not be installed.");
        RequireManagerRuntimeInstall(
            InstallDialogFactoryTrace(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the dialog-factory hook could not be installed.");
        RequireManagerRuntimeInstall(
            InstallSecondaryControllerHook(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the secondary-controller hook could not be installed.");
        RequireManagerRuntimeInstall(
            InstallGameUpdateRefreshBridge(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the game-update refresh bridge could not be installed.");
    }
    if (alchemistOilRows) {
        RequireManagerRuntimeInstall(
            InstallPrivateEnchantmentRows(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private enchantment rows could not be installed.");
    }

    // The stock main thread must run before Majesty creates its top-level
    // window. Release the launcher only after every static executable patch is
    // complete, then install this one lifecycle hook while the window appears.
    if (!SignalManagerRuntimeReady()) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the complete pre-window runtime could not release the launcher barrier.");
    }
    if (alchemistSecondary) {
        RequireManagerRuntimeInstall(
            InstallWindowProcedureHook(),
            managerLaunch,
            "Terminating manager launch after Majesty resumed: the window lifecycle hook could not be installed.");
    }
    return 0;
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_runtimeModule = instance;
        DisableThreadLibraryCalls(instance);
        const HANDLE thread = CreateThread(nullptr, 0, InitializeRuntime, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
