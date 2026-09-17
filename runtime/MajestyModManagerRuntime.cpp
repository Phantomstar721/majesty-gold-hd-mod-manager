#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cwchar>
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
#include "MapQueryRuntime.h"
#include "RuntimeCapabilityManifest.h"
#include "RuntimeFeatureRegistry.h"
#include "StockBuildingControllerCatalog.h"
#include "StockControllerRegistry.h"

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
    std::uintptr_t openDialogRva;
    std::uintptr_t stockAp41HandlerRva;
    std::uintptr_t stockAp41ActivationRva;
    std::uintptr_t stockAp41RefreshRva;
    std::uintptr_t attackRewardAmountRva;
    std::uintptr_t flagModeOwnerRva;
    std::uintptr_t getFlagModeManagerRva;
    std::uintptr_t getSelectedFlagModeRva;
    std::uintptr_t setFlagModeRva;
    std::uintptr_t modeRegistryCompletionRva;
    unsigned char expectedModeRegistryCompletion[11];
    std::uintptr_t modeRegistryResumeRva;
    std::uintptr_t stockCaptureCallbackRva;
    unsigned char expectedStockCallbackCreate[11];
    std::uintptr_t stockCaptureValidatorRva;
    std::uintptr_t stockFlagTargetCheckRva;
    std::uintptr_t displayClassifierRva;
    std::uintptr_t selectedAgentRva;
    std::uintptr_t findAttachedRelationRva;
    std::uintptr_t systemAlertOwnerRva;
    std::uintptr_t prepareSystemAlertRva;
    std::uintptr_t postLiteralSystemAlertRva;
    std::uintptr_t flagModeConstructorRva;
    std::uintptr_t getFlagModeRegistryRva;
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
    0x00026650,
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
    0x000B03F0, 0x000A92F0, 0x000A9230, 0x000A94A0,
    0x003C17A4, 0x003C12F0, 0x00054B90, 0x000556D0, 0x00054E70,
    0x0005E4E4, {0x8B,0x4C,0x24,0x10,0x64,0x89,0x0D,0,0,0,0}, 0x0005E4EF,
    0x0005D400, {0x57,0x68,0x04,0xBA,0x73,0x00,0xE8,0xB6,0xF7,0xFF,0xFF},
    0x0005D360, 0x0005D2D0, 0x00108510, 0x00067540, 0x001A7730,
    0x003C1394, 0x0006ABE0, 0x0006ACE0, 0x0019D1E0, 0x0019EF30,
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
    0x000278A0,
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
    0x000B0CE0, 0x000A9BE0, 0x000A9B20, 0x000A9D90,
    0x003E028C, 0x003DFDA8, 0x00055BC0, 0x00056700, 0x00055EA0,
    0x0005F514, {0x8B,0x4C,0x24,0x10,0x64,0x89,0x0D,0,0,0,0}, 0x0005F51F,
    0x0005E430, {0x57,0x68,0xD4,0x4A,0x75,0x00,0xE8,0xB6,0xF7,0xFF,0xFF},
    0x0005E390, 0x0005E300, 0x0010A6E0, 0x00068780, 0x001BC6E0,
    0x003DFE4C, 0x0006BE70, 0x0006BFE0, 0x001B2190, 0x001B3EE0,
};

const MajestyBuildProfile* g_buildProfile = nullptr;
using OccupantPanel = MajestyStockControllers::OccupantActionPanelRecord;
using QuestBoard = MajestyStockControllers::LiveAgentListRecord;
// The internal QuestBoard names below identify the reverse-engineered MX05
// seam that first proved this route. The registry and package contract are
// generic live-agent lists and contain no Guild or quest-specific behavior.
const OccupantPanel* g_parentOccupantPanel = nullptr;
const OccupantPanel* g_activeOccupantPanel = nullptr;
const OccupantPanel* g_executingOccupantPanel = nullptr;
const QuestBoard* g_parentQuestBoard = nullptr;
const QuestBoard* g_activeQuestBoard = nullptr;
const QuestBoard* g_executingQuestBoard = nullptr;
int g_activeQuestRevision = -1;
int g_requestedQuestRevision = -1;
bool g_questBoardPopulationRequested = false;
bool g_activeQuestBoardFaulted = false;
constexpr std::uint32_t kMx05DialogId = 0x3530584D;
bool ValidateOccupantPanelProfile();
bool ValidateSelectedParentControllerProfiles();
bool ValidateQuestBoardProfile();
bool OccupantCallMatches(std::uintptr_t callRva, std::uintptr_t targetRva);
bool QuestSummaryCallMatches(
    std::uintptr_t callRva,
    std::uintptr_t targetRva,
    std::uint32_t expectedTextId);
std::uintptr_t RelativeCallTarget(const unsigned char* call);
bool InstallOccupantPanelRoute();
bool InstallOccupantChildVtable(std::uint32_t controller);
bool InstallQuestBoardChildVtable(std::uint32_t controller);
bool InstallOccupantParentVtable(std::uint32_t controller);
bool OpenOccupantPanel(void* controller, std::uint32_t command, int* result);
bool OpenQuestBoardPanel(void* controller, std::uint32_t command, int* result);
bool IsLiveQuestBoardController(
    const void* controller,
    const QuestBoard* expectedBoard);
void __fastcall QuestBoardRefresh(void* controller, void*);
void RefreshQuestBoardAfterAction(const QuestBoard* board, std::uint32_t building);
constexpr std::uint32_t kAp10DialogId = 0x30315041;
constexpr std::uint32_t kAp69DialogId = 0x39365041;
constexpr std::uint32_t kAp41DialogId = 0x31345041;
constexpr std::uint32_t kMx09DialogId = 0x3930584D;
constexpr std::size_t kResearchDescriptorDwordCount = 5;
constexpr std::size_t kResearchDescriptorSize =
    kResearchDescriptorDwordCount * sizeof(std::uint32_t);
constexpr std::uint32_t kStockUnaffordableGoldCost = 0x3FFFFFFF;
constexpr std::uint32_t kRageOfKrolmCommandId = 1;
constexpr std::uint32_t kRageOfKrolmCountAttributeId = 0x07425041;
constexpr std::uint32_t kPlayerGoldDataId = 0x00505041;
constexpr std::uint32_t kCurrentResearchAttributeId = 0x2C425041;
constexpr std::uint32_t kResearchStartedAtAttributeId = 0x38425041;
constexpr std::uint32_t kResearchDurationAttributeId = 0x0D425041;
constexpr std::uint32_t kStockLastNameGeneratorId = 0x37314D4E;
constexpr wchar_t kIntentRegistryEnvironment[] =
    L"MAJESTY_MOD_MANAGER_INTENT_REGISTRY";
constexpr wchar_t kCapabilityManifestEnvironment[] =
    L"MAJESTY_MOD_MANAGER_CAPABILITIES";
constexpr wchar_t kRuntimeFeatureRegistryEnvironment[] =
    L"MAJESTY_MOD_MANAGER_FEATURES";
constexpr wchar_t kStockControllerRegistryEnvironment[] =
    L"MAJESTY_MOD_MANAGER_CONTROLLERS";
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
struct MajestyStringView {
    const char* data;
    std::uint32_t capacityFlags;
    std::uint32_t length;
};
static_assert(sizeof(MajestyStringView) == 12, "Majesty x86 string view changed");
const MajestyStringView* g_privateEnchantmentRowString = nullptr;
MajestyRuntimeFeatures::Registry g_runtimeFeatureRegistry;
MajestyStockControllers::Registry g_stockControllerRegistry;
std::vector<MajestyStringView> g_runtimeEnchantmentViews;

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

enum class RuntimeFeatureRegistryState {
    Absent,
    Loaded,
    Invalid,
};

enum class StockControllerRegistryState {
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

constexpr std::uint32_t kFirstQuestOfferIntentId = 0x70000000u;
constexpr std::size_t kMaximumQuestOffers = 64;
constexpr int kDataRecordListRowHeight = 40;
struct QuestOfferPresentation {
    void* agent;
    std::uint32_t recordKey = 0;
    std::string name;
    std::string detail;
    std::string summaryTemplate;
    MajestyStringView summaryView;
    MajestyStringView detailView;
};
QuestOfferPresentation g_questOfferPresentations[kMaximumQuestOffers] = {};
std::size_t g_questOfferPresentationCount = 0;
int g_renderedDataRecordRevision = -1;
const QuestOfferPresentation* g_paintingQuestOffer = nullptr;
bool g_suppressQuestStatusIconsForCurrentRow = false;

HMODULE g_runtimeModule = nullptr;
std::uintptr_t g_imageBase = 0;
WNDPROC g_originalWindowProcedure = nullptr;
LONG g_secondaryPanelArmed = 0;
LONG g_ap10ControllerContext = 0;
LONG g_secondaryPanelActive = 0;
LONG g_secondaryPanelHandle = 0;
LONG g_captureParentController = 0;
LONG g_captureChildController = 0;
LONG g_parentController = 0;
LONG g_childController = 0;
const MajestyStockControllers::SecondaryPanelRecord* g_parentPanelRecord = nullptr;
const MajestyStockControllers::SecondaryPanelRecord* g_activePanelRecord = nullptr;
const MajestyStockControllers::RewardPanelRecord* g_parentRewardPanelRecord = nullptr;
const MajestyStockControllers::RewardPanelRecord* g_activeRewardPanelRecord = nullptr;
const MajestyStockControllers::BuildingOpenToggleRecord* g_parentOpenToggleRecord = nullptr;
const MajestyStockControllers::TimedRageActionRecord* g_activeTimedRageAction = nullptr;
LONG g_timedRageActive = 0;
const MajestyStockControllers::TimedRageActionRecord* g_pendingTimedRageAction = nullptr;
const MajestyStockControllers::RageCommandActionRecord* g_pendingRageCommandAction = nullptr;
LONG g_pendingRageHandle = 0;
LONG g_privateRageDispatch = 0;
const char* g_privateRageCallback = nullptr;
bool g_stockResearchRouteReady = false;
struct PrivateResearchDescriptor {
    const MajestyStockControllers::ResearchRowRecord* record;
    std::uint32_t* descriptor;
};
std::vector<PrivateResearchDescriptor> g_privateResearchDescriptors;
const char* g_privateResearchCompletionText = nullptr;

enum class PrivateSpellDescriptorKind {
    TimedRage,
    RageCommandVisual,
    SovereignVisual,
    SovereignTarget,
};
struct PrivateSpellDescriptor {
    PrivateSpellDescriptorKind kind;
    const void* record;
    std::uint32_t descriptor[6];
};
std::vector<PrivateSpellDescriptor> g_privateSpellDescriptors;

const MajestyStockControllers::SovereignTargetActionRecord*
    g_pendingSovereignAction = nullptr;
LONG g_pendingSovereignBuilding = 0;
LONG g_executingSovereignUnit = 0;

struct RewardFlagRuntimeState {
    const MajestyStockControllers::HostileMonsterFlagRecord* record;
    void* modeObject;
    void* completionCallback;
    void* selectedBuilding;
    int rewardAmount;
    void* lastValidationTarget;
    int lastStockValidationResult;
    int lastPrivateValidationResult;
};
std::vector<RewardFlagRuntimeState> g_rewardFlagStates;
RewardFlagRuntimeState* g_activeRewardFlagState = nullptr;
void* g_rewardParentVtable[kAp10VtableEntries] = {};
void* g_rewardPanelVtable[kAp69VtableEntries] = {};
using RewardControllerControl = int (__thiscall*)(void*, std::uint32_t);
using RewardControllerSetup = void (__thiscall*)(void*);
using RewardControllerEvent = void (__thiscall*)(
    void*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
using RewardControllerActivation = std::uintptr_t (__thiscall*)(void*);
using RewardControllerRefresh = std::uintptr_t (__thiscall*)(
    void*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
RewardControllerControl g_stockRewardParentControl = nullptr;
RewardControllerSetup g_stockRewardParentSetup = nullptr;
RewardControllerEvent g_stockRewardParentEvent = nullptr;
RewardControllerControl g_stockRewardPanelControl = nullptr;
RewardControllerActivation g_stockRewardPanelActivation = nullptr;
RewardControllerRefresh g_stockRewardPanelRefresh = nullptr;
std::uintptr_t g_modeRegistryResume = 0;

struct BuildingActivitySnapshot {
    int command;
    int startedAt;
    int duration;
};

struct ResearchOwner {
    unsigned char* context;
    const MajestyStockControllers::ResearchRowRecord* record;
    DWORD startedAt;
    DWORD duration;
    bool pending;
    bool active;
};

ResearchOwner g_researchOwner = {};
LONG g_researchCompletionStaged = 0;
LONG g_researchCompletedThisUpdate = 0;
DWORD g_timedRageStartedAt = 0;
void* g_childControllerVtable[kAp69VtableEntries] = {};
void* g_parentControllerVtable[kAp10VtableEntries] = {};

using ControllerSetup = void (__thiscall*)(void*);
using ControllerControl = int (__thiscall*)(void*, std::uint32_t);
using ControllerEvent = void (__thiscall*)(
    void*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
using ControllerActivity = void (__thiscall*)(void*);
using GameUpdate = void (__thiscall*)(void*);
ControllerSetup g_stockAp69Setup = nullptr;
ControllerControl g_stockAp69Control = nullptr;
ControllerEvent g_stockAp69Event = nullptr;
ControllerSetup g_stockParentSetup = nullptr;
ControllerControl g_stockParentControl = nullptr;
ControllerEvent g_stockParentEvent = nullptr;
ControllerControl g_stockQuestBoardControl = nullptr;
ControllerControl g_stockQuestBoardSharedControl = nullptr;
ControllerActivity g_stockParentActivity = nullptr;
GameUpdate g_stockGameUpdate = nullptr;

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

RuntimeFeatureRegistryState LoadRuntimeFeatureRegistry() {
    wchar_t registryPath[32768] = {};
    SetLastError(ERROR_SUCCESS);
    const DWORD pathLength = GetEnvironmentVariableW(
        kRuntimeFeatureRegistryEnvironment,
        registryPath,
        static_cast<DWORD>(sizeof(registryPath) / sizeof(registryPath[0])));
    if (pathLength == 0) {
        if (GetLastError() == ERROR_ENVVAR_NOT_FOUND) {
            WriteLog(
                "No manager runtime feature registry was supplied; manager launch is incomplete.");
            return RuntimeFeatureRegistryState::Absent;
        }
        WriteLog(
            "Manager runtime feature registry rejected: its environment path is empty or unreadable.");
        return RuntimeFeatureRegistryState::Invalid;
    }
    if (pathLength >= sizeof(registryPath) / sizeof(registryPath[0]) ||
        !IsCanonicalAbsolutePath(registryPath)) {
        WriteLog(
            "Manager runtime feature registry rejected: its environment path is not a canonical absolute path.");
        return RuntimeFeatureRegistryState::Invalid;
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
            "Manager runtime feature registry rejected: the supplied file could not be opened (error %lu).",
            GetLastError());
        WriteLog(message);
        return RuntimeFeatureRegistryState::Invalid;
    }

    LARGE_INTEGER fileSize = {};
    if (!GetFileSizeEx(file, &fileSize) || fileSize.QuadPart < 0 ||
        static_cast<unsigned long long>(fileSize.QuadPart) >
            MajestyRuntimeFeatures::kMaximumRegistryBytes) {
        WriteLog(
            "Manager runtime feature registry rejected: its file size is outside the supported bounds.");
        CloseHandle(file);
        return RuntimeFeatureRegistryState::Invalid;
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
                "Manager runtime feature registry rejected: its file could not be read completely.");
            CloseHandle(file);
            return RuntimeFeatureRegistryState::Invalid;
        }
        totalRead += readNow;
    }
    CloseHandle(file);

    MajestyRuntimeFeatures::Registry registry;
    std::string parseError;
    if (!MajestyRuntimeFeatures::ParseRegistry(
            bytes.data(), bytes.size(), &registry, &parseError)) {
        char message[384] = {};
        sprintf_s(
            message,
            "Manager runtime feature registry rejected before hook installation: %s.",
            parseError.c_str());
        WriteLog(message);
        return RuntimeFeatureRegistryState::Invalid;
    }
    g_runtimeFeatureRegistry = std::move(registry);
    g_runtimeEnchantmentViews.clear();
    g_runtimeEnchantmentViews.reserve(
        g_runtimeFeatureRegistry.enchantmentRows.size());
    for (const auto& row : g_runtimeFeatureRegistry.enchantmentRows) {
        MajestyStringView view = {};
        view.data = row.displayText.data();
        view.capacityFlags = static_cast<std::uint32_t>(row.displayText.size());
        view.length = static_cast<std::uint32_t>(row.displayText.size());
        g_runtimeEnchantmentViews.push_back(view);
    }
    char message[256] = {};
    sprintf_s(
        message,
        "Loaded validated MMFR registry with %u name generators and %u enchantment rows.",
        static_cast<unsigned int>(
            g_runtimeFeatureRegistry.nameGenerators.size()),
        static_cast<unsigned int>(
            g_runtimeFeatureRegistry.enchantmentRows.size()));
    WriteLog(message);
    return RuntimeFeatureRegistryState::Loaded;
}

StockControllerRegistryState LoadStockControllerRegistry() {
    wchar_t registryPath[32768] = {};
    SetLastError(ERROR_SUCCESS);
    const DWORD pathLength = GetEnvironmentVariableW(
        kStockControllerRegistryEnvironment,
        registryPath,
        static_cast<DWORD>(sizeof(registryPath) / sizeof(registryPath[0])));
    if (pathLength == 0) {
        if (GetLastError() == ERROR_ENVVAR_NOT_FOUND) {
            WriteLog(
                "No manager stock-controller registry was supplied; manager launch is incomplete.");
            return StockControllerRegistryState::Absent;
        }
        WriteLog(
            "Manager stock-controller registry rejected: its environment path is empty or unreadable.");
        return StockControllerRegistryState::Invalid;
    }
    if (pathLength >= sizeof(registryPath) / sizeof(registryPath[0]) ||
        !IsCanonicalAbsolutePath(registryPath)) {
        WriteLog(
            "Manager stock-controller registry rejected: its environment path is not a canonical absolute path.");
        return StockControllerRegistryState::Invalid;
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
            "Manager stock-controller registry rejected: the supplied file could not be opened (error %lu).",
            GetLastError());
        WriteLog(message);
        return StockControllerRegistryState::Invalid;
    }

    LARGE_INTEGER fileSize = {};
    if (!GetFileSizeEx(file, &fileSize) || fileSize.QuadPart < 0 ||
        static_cast<unsigned long long>(fileSize.QuadPart) >
            MajestyStockControllers::kMaximumRegistryBytes) {
        WriteLog(
            "Manager stock-controller registry rejected: its file size is outside the supported bounds.");
        CloseHandle(file);
        return StockControllerRegistryState::Invalid;
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
                "Manager stock-controller registry rejected: its file could not be read completely.");
            CloseHandle(file);
            return StockControllerRegistryState::Invalid;
        }
        totalRead += readNow;
    }
    CloseHandle(file);

    MajestyStockControllers::Registry registry;
    std::string parseError;
    if (!MajestyStockControllers::ParseRegistry(
            bytes.data(), bytes.size(), &registry, &parseError)) {
        char message[384] = {};
        sprintf_s(
            message,
            "Manager stock-controller registry rejected before hook installation: %s.",
            parseError.c_str());
        WriteLog(message);
        return StockControllerRegistryState::Invalid;
    }
    g_stockControllerRegistry = std::move(registry);
    char message[192] = {};
    sprintf_s(
        message,
        "Loaded validated MMCR registry with %u stock-controller panels and %u total recipes.",
        static_cast<unsigned int>(g_stockControllerRegistry.panels.size() +
            g_stockControllerRegistry.rewardPanels.size() +
            g_stockControllerRegistry.occupantActionPanels.size() +
            g_stockControllerRegistry.buildingOpenToggles.size() +
            g_stockControllerRegistry.liveAgentLists.size()),
        static_cast<unsigned int>(
            g_stockControllerRegistry.meters.size() +
            g_stockControllerRegistry.researchRows.size() +
            g_stockControllerRegistry.upgradeGates.size() +
            g_stockControllerRegistry.timedRageActions.size() +
            g_stockControllerRegistry.rageCommandActions.size() +
            g_stockControllerRegistry.sovereignTargetActions.size() +
            g_stockControllerRegistry.rewardPanels.size() +
            g_stockControllerRegistry.occupantActionPanels.size() +
            g_stockControllerRegistry.hostileMonsterFlags.size() +
            g_stockControllerRegistry.buildingOpenToggles.size() +
            g_stockControllerRegistry.liveAgentLists.size()));
    WriteLog(message);
    return StockControllerRegistryState::Loaded;
}

bool PrepareStockControllerRuntimeRecords() {
    g_privateResearchDescriptors.clear();
    g_privateResearchDescriptors.reserve(
        g_stockControllerRegistry.researchRows.size());
    for (const auto& row : g_stockControllerRegistry.researchRows) {
        g_privateResearchDescriptors.push_back({&row, nullptr});
    }
    g_privateSpellDescriptors.clear();
    g_privateSpellDescriptors.reserve(
        g_stockControllerRegistry.timedRageActions.size() +
        g_stockControllerRegistry.rageCommandActions.size() +
        g_stockControllerRegistry.sovereignTargetActions.size() * 2);
    for (const auto& action : g_stockControllerRegistry.timedRageActions) {
        g_privateSpellDescriptors.push_back(
            {PrivateSpellDescriptorKind::TimedRage, &action, {}});
    }
    for (const auto& action : g_stockControllerRegistry.rageCommandActions) {
        g_privateSpellDescriptors.push_back(
            {PrivateSpellDescriptorKind::RageCommandVisual, &action, {}});
    }
    for (const auto& action : g_stockControllerRegistry.sovereignTargetActions) {
        g_privateSpellDescriptors.push_back(
            {PrivateSpellDescriptorKind::SovereignVisual, &action, {}});
        g_privateSpellDescriptors.push_back(
            {PrivateSpellDescriptorKind::SovereignTarget, &action, {}});
    }
    return g_privateResearchDescriptors.size() ==
            g_stockControllerRegistry.researchRows.size() &&
        g_privateSpellDescriptors.size() ==
            g_stockControllerRegistry.timedRageActions.size() +
            g_stockControllerRegistry.rageCommandActions.size() +
            g_stockControllerRegistry.sovereignTargetActions.size() * 2;
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
    if (id >= kFirstQuestOfferIntentId &&
        id - kFirstQuestOfferIntentId < g_questOfferPresentationCount) {
        return &g_questOfferPresentations[
            id - kFirstQuestOfferIntentId].detailView;
    }
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

bool ValidateStockControllerRecipeProfile() {
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

bool ValidatePrivateEnchantmentRowsProfile() {
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

bool ValidatePrivateRewardFlagProfile() {
    return MatchesProfileBytes(
               g_buildProfile->secondaryControllerResultRva,
               g_buildProfile->expectedResultSite,
               sizeof(g_buildProfile->expectedResultSite),
               "reward secondary-controller result") &&
        MatchesProfileBytes(
               g_buildProfile->dialogCreationRva,
               g_buildProfile->expectedCreationEntry,
               sizeof(g_buildProfile->expectedCreationEntry),
               "reward dialog creation") &&
        MatchesProfileBytes(
               g_buildProfile->dialogFactoryRva,
               g_buildProfile->expectedFactoryEntry,
               sizeof(g_buildProfile->expectedFactoryEntry),
               "reward dialog factory") &&
        MatchesProfileBytes(
               g_buildProfile->modeRegistryCompletionRva,
               g_buildProfile->expectedModeRegistryCompletion,
               sizeof(g_buildProfile->expectedModeRegistryCompletion),
               "Fl00 mode registry completion") &&
        MatchesProfileBytes(
               g_buildProfile->stockCaptureCallbackRva + 0xCF,
               g_buildProfile->expectedStockCallbackCreate,
               sizeof(g_buildProfile->expectedStockCallbackCreate),
               "Fl00 completion callback creation");
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
    if (!g_stockControllerRegistry.occupantActionPanels.empty() ||
        !g_stockControllerRegistry.liveAgentLists.empty()) {
        if (!ValidateOccupantPanelProfile()) return false;
    }
    if (!ValidateSelectedParentControllerProfiles()) return false;
    if (!g_stockControllerRegistry.liveAgentLists.empty() &&
        !ValidateQuestBoardProfile()) return false;
    // Preflight every site selected by MMCP before installing any hook from
    // those groups. Unselected specialized sites are deliberately untouched
    // and cannot reject an otherwise generic manager launch.
    if (HasRuntimeCapability(
            MajestyRuntimeCapabilities::kExpandedBuildingSlots) &&
        !ValidateCustomGuildFactoryFallback()) {
        return false;
    }
    if (!g_stockControllerRegistry.panels.empty() &&
        !ValidateStockControllerRecipeProfile()) {
        return false;
    }
    if (!g_stockControllerRegistry.rewardPanels.empty() &&
        !ValidatePrivateRewardFlagProfile()) {
        return false;
    }
    if (!g_runtimeFeatureRegistry.enchantmentRows.empty() &&
        !ValidatePrivateEnchantmentRowsProfile()) {
        return false;
    }
    if (!g_runtimeFeatureRegistry.nameGenerators.empty() &&
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
    // Literal AP22 quantity-binding dispatch at Beta2
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

unsigned char* NativePanelContext(std::uint32_t controller) {
    using GetPanelContext = void* (__thiscall*)(void*);
    if (controller == 0) {
        return nullptr;
    }
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    return static_cast<unsigned char*>(
        getPanelContext(reinterpret_cast<void*>(controller)));
}

unsigned char* ActivePanelContext() {
    // AP69/MX05 resolve their own native +0x28/+0x2C handle pair. Stock
    // OpenDialog may remove the parent after setting up a child in the same
    // sidebar slot. Never borrow the deleted parent or fall back to a different
    // building when the child's native handle no longer resolves.
    const auto child = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_childController, 0, 0));
    return NativePanelContext(child != 0 ? child : static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_parentController, 0, 0)));
}

int ReadPackedAttributeValue(
    void* context, std::uint32_t attributeId, std::uint32_t fallback);
void WritePackedAttributeValue(
    void* context, std::uint32_t attributeId, int value);

constexpr std::uint32_t kEmbassyActiveFlagAttributeId = 0x044D4541u;

void RefreshBuildingOpenToggle(std::uint32_t controller) {
    const auto* toggle = g_parentOpenToggleRecord;
    if (toggle == nullptr) return;
    auto* context = NativePanelContext(controller);
    if (context == nullptr) return;
    const bool open = ReadPackedAttributeValue(
        context, kEmbassyActiveFlagAttributeId, 0) != 0;
    // Literal MX22 presenter order: hide the inactive action, show the action
    // that changes the current state, then send its stock enable message 0xA.
    SetControllerControlVisible(controller, toggle->openCommandId, !open);
    SetControllerControlVisible(controller, toggle->closeCommandId, open);
    SendControllerMessage(
        controller,
        open ? toggle->closeCommandId : toggle->openCommandId,
        0x0Au,
        0u,
        0u);
}

bool HandleBuildingOpenToggle(
    void* controller, std::uint32_t command, int* result) {
    const auto* toggle = g_parentOpenToggleRecord;
    if (toggle == nullptr ||
        (command != toggle->openCommandId && command != toggle->closeCommandId)) {
        return false;
    }
    auto* context = NativePanelContext(
        reinterpret_cast<std::uint32_t>(controller));
    if (context == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "A building open-toggle command lost its stock panel context.");
    }
    // MX22 stores this durable state on the selected building. Do not submit
    // order 0x16: its GS_EmbassyRecruitOrder side effect belongs to Embassy.
    WritePackedAttributeValue(
        context,
        kEmbassyActiveFlagAttributeId,
        command == toggle->openCommandId ? 1 : 0);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
    *result = 0;
    return true;
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

BuildingActivitySnapshot CaptureBuildingActivity(void* context) {
    BuildingActivitySnapshot snapshot = {};
    snapshot.command = ReadPackedAttributeValue(
        context, kCurrentResearchAttributeId);
    snapshot.startedAt = ReadPackedAttributeValue(
        context, kResearchStartedAtAttributeId);
    snapshot.duration = ReadPackedAttributeValue(
        context, kResearchDurationAttributeId);
    return snapshot;
}

void RestoreBuildingActivity(
    void* context, const BuildingActivitySnapshot& snapshot) {
    WritePackedAttributeValue(
        context, kCurrentResearchAttributeId, snapshot.command);
    WritePackedAttributeValue(
        context, kResearchStartedAtAttributeId, snapshot.startedAt);
    WritePackedAttributeValue(
        context, kResearchDurationAttributeId, snapshot.duration);
}

void ClearBuildingActivity(void* context) {
    const BuildingActivitySnapshot empty = {};
    RestoreBuildingActivity(context, empty);
}

bool PrivateResearchIsActive() {
    return g_researchOwner.pending ||
        g_researchOwner.active;
}

bool PrivateResearchMatches(
    const void* context,
    const MajestyStockControllers::ResearchRowRecord* record) {
    return g_researchOwner.active &&
        g_researchOwner.context == context &&
        g_researchOwner.record == record;
}

int SelectedBuildingLevel(const void* context) {
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

const MajestyStockControllers::UpgradeGateRecord* ActiveUpgradeGate() {
    if (g_parentPanelRecord == nullptr) {
        return nullptr;
    }
    for (const auto& gate : g_stockControllerRegistry.upgradeGates) {
        if (gate.panelKey == g_parentPanelRecord->panelKey) {
            return &gate;
        }
    }
    return nullptr;
}

const PrivateResearchDescriptor* FindPrivateResearchDescriptor(
    const MajestyStockControllers::ResearchRowRecord* record) {
    for (const auto& item : g_privateResearchDescriptors) {
        if (item.record == record) {
            return &item;
        }
    }
    return nullptr;
}

bool UpgradeResearchComplete(void* context) {
    const auto* gate = ActiveUpgradeGate();
    if (gate == nullptr || context == nullptr) {
        return gate == nullptr;
    }
    const int level = SelectedBuildingLevel(context);
    for (const auto& requirement : gate->requirements) {
        if (static_cast<int>(requirement.buildingLevel) != level) {
            continue;
        }
        const MajestyStockControllers::ResearchRowRecord* row = nullptr;
        for (const auto& candidate : g_stockControllerRegistry.researchRows) {
            if (candidate.panelKey == gate->panelKey &&
                candidate.recipeKey == requirement.recipeKey) {
                row = &candidate;
                break;
            }
        }
        const auto* state = FindPrivateResearchDescriptor(row);
        const std::uint32_t* descriptor = state == nullptr
            ? nullptr : state->descriptor;
        if (descriptor == nullptr && row != nullptr &&
            g_resolveResearchDescriptorTrampoline != 0) {
            using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
                std::uint32_t);
            auto resolve = reinterpret_cast<ResolveResearchDescriptor>(
                g_resolveResearchDescriptorTrampoline);
            descriptor = resolve(row->completionTemplateControlId);
        }
        if (descriptor == nullptr || descriptor[4] == 0) {
            StopUnsafeManagerRuntimeLaunch(
                "An upgrade recipe could not resolve its declared stock AP99 completion template.");
        }
        return ReadPackedAttributeValue(context, descriptor[4], 0) != 0;
    }
    return true;
}

void ApplyUpgradeResearchGate(
    std::uint32_t controller, void* context) {
    const auto* gate = ActiveUpgradeGate();
    if (gate == nullptr || controller == 0 || context == nullptr ||
        UpgradeResearchComplete(context)) {
        return;
    }
    // AP17's stock presenter remains authoritative.  The resolved recipe
    // changes only which completed AP99 attribute gates the current tier.
    SendControllerMessage(
        controller, gate->upgradeControlId, 0x0A, 1, 0);
    SetControllerControlVisible(
        controller, gate->upgradePriceControlId, false);
}

void RefreshPrivateResearchRows(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    unsigned char* context = ActivePanelContext();
    if (panel == nullptr || context == nullptr) {
        return;
    }
    using RefreshSingleResearchRow = void (__cdecl*)(
        void*, void*, std::uint32_t);
    auto refreshSingleResearchRow = reinterpret_cast<RefreshSingleResearchRow>(
        g_imageBase + g_buildProfile->refreshSingleResearchRowRva);
    for (const auto& row : g_stockControllerRegistry.researchRows) {
        if (g_activePanelRecord != nullptr &&
            row.panelKey == g_activePanelRecord->panelKey) {
            refreshSingleResearchRow(panel, context, row.actionControlId);
        }
    }
}

void RefreshTimedRageRows(std::uint32_t controller) {
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
    auto refreshSingleSpellRow = reinterpret_cast<RefreshSingleSpellRow>(
        g_imageBase + g_buildProfile->refreshSingleSpellRowRva);
    for (const auto& action : g_stockControllerRegistry.timedRageActions) {
        if (g_activePanelRecord != nullptr &&
            action.panelKey == g_activePanelRecord->panelKey) {
            refreshSingleSpellRow(panel, player, action.actionControlId, 0);
        }
    }
}

int ResourceStock(const MajestyStockControllers::ResourceMeterRecord* meter) {
    unsigned char* context = ActivePanelContext();
    if (context == nullptr || meter == nullptr) {
        return 0;
    }
    const int value = ReadPackedAttributeValue(
        context, meter->attributeId, 0);
    return value < 0 ? 0 : value;
}

const MajestyStockControllers::ResourceMeterRecord* FindActiveMeter(
    const std::string& resourceKey) {
    if (g_activePanelRecord == nullptr) {
        return nullptr;
    }
    return g_stockControllerRegistry.FindMeter(
        g_activePanelRecord->panelKey, resourceKey);
}

void UpdateResourceMeters(std::uint32_t controller) {
    if (controller == 0) {
        return;
    }
    for (const auto& meter : g_stockControllerRegistry.meters) {
        if (g_activePanelRecord == nullptr ||
            meter.panelKey != g_activePanelRecord->panelKey) {
            continue;
        }
        const int stock = ResourceStock(&meter);
        SetControllerControlVisible(controller, meter.labelControlId, true);
        SetControllerControlVisible(controller, meter.countControlId, true);
        SetControllerControlInteger(controller, meter.bindingControlId, stock);
    }
}

bool CompletionTemplateIsComplete(
    const MajestyStockControllers::RageCommandActionRecord& action);

void RefreshPrivateActionRows(
    std::uint32_t controller, bool runStockPresenter) {
    if (controller == 0 || g_activePanelRecord == nullptr) {
        return;
    }
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    unsigned char* context = ActivePanelContext();
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
    for (const auto& action : g_stockControllerRegistry.rageCommandActions) {
        if (action.panelKey != g_activePanelRecord->panelKey) continue;
        if (runStockPresenter) {
            refreshSingleSpellRow(panel, player, action.actionControlId, 0);
        }
        const bool levelAvailable =
            SelectedBuildingLevel(context) >= static_cast<int>(action.requiredLevel);
        SetControllerControlVisible(controller, action.actionControlId, levelAvailable);
        SetControllerControlVisible(controller, action.iconControlId, levelAvailable);
        SetControllerControlVisible(controller, action.priceControlId, false);
        if (levelAvailable) {
            const bool unavailable =
                ResourceStock(FindActiveMeter(action.resourceKey)) <
                    static_cast<int>(action.resourceCost) ||
                CompletionTemplateIsComplete(action) ||
                InterlockedCompareExchange(&g_pendingRageHandle, 0, 0) != 0;
            SendControllerMessage(
                controller, action.actionControlId, 0x0A,
                unavailable ? 1 : 0, 0);
        }
    }
    for (const auto& action : g_stockControllerRegistry.sovereignTargetActions) {
        if (action.panelKey != g_activePanelRecord->panelKey) continue;
        if (runStockPresenter) {
            refreshSingleSpellRow(panel, player, action.visualControlId, 0);
        }
        const bool levelAvailable =
            SelectedBuildingLevel(context) >= static_cast<int>(action.requiredLevel);
        SetControllerControlVisible(controller, action.visualControlId, levelAvailable);
        SetControllerControlVisible(controller, action.iconControlId, levelAvailable);
        SetControllerControlVisible(controller, action.priceControlId, false);
        if (levelAvailable) {
            const bool unavailable =
                ResourceStock(FindActiveMeter(action.resourceKey)) <
                    static_cast<int>(action.resourceCost);
            SendControllerMessage(
                controller, action.visualControlId, 0x0A,
                unavailable ? 1 : 0, 0);
        }
    }
}

void UpdateResearchPresentations(std::uint32_t controller) {
    if (!g_stockResearchRouteReady || controller == 0) {
        return;
    }
    unsigned char* context = ActivePanelContext();
    if (context == nullptr) {
        return;
    }
    for (const auto& row : g_stockControllerRegistry.researchRows) {
        if (g_activePanelRecord == nullptr ||
            row.panelKey != g_activePanelRecord->panelKey) continue;
        const bool active = PrivateResearchMatches(context, &row);
        if (active) {
            SetControllerControlVisible(controller, row.actionControlId, false);
            SetControllerControlVisible(controller, row.priceControlId, false);
            SetControllerControlVisible(controller, row.activeDisplayControlId, true);
            SetControllerControlVisible(controller, row.progressControlId, true);
            const DWORD now = SimulationClock();
            const DWORD elapsed = now > g_researchOwner.startedAt
                ? now - g_researchOwner.startedAt : 0;
            std::uint32_t progress[4] = {
                7, elapsed, 0, g_researchOwner.duration};
            SendControllerMessage(
                controller, row.progressControlId, 0x29, 0,
                reinterpret_cast<std::uint32_t>(progress));
            SendControllerMessage(
                controller, row.progressControlId, 0x08, 0, 0);
        } else {
            SetControllerControlVisible(controller, row.progressControlId, false);
            SetControllerControlVisible(controller, row.activeDisplayControlId, false);
            if (PrivateResearchIsActive()) {
                SendControllerMessage(
                    controller, row.actionControlId, 0x0A, 1, 0);
            }
        }
    }
}

void* StockCurrentPlayerAgent() {
    // AP24 constructor 0x004B1620 obtains the player's agent from the panel
    // context's +0x80 player slot, and refresh 0x004B1340 reads packed
    // attribute APB\x07 through 0x005B9FD0. Reproduce that exact read so timed actions
    // and Rage share Majesty's native Palace-owned exclusion state.
    using GetUiManager = void* (__cdecl*)();
    using GetPlayerAgent = void* (__thiscall*)(void*, std::uint32_t);
    auto* context = ActivePanelContext();
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

bool CompletionTemplateIsComplete(
    const MajestyStockControllers::RageCommandActionRecord& action) {
    void* playerAgent = StockCurrentPlayerAgent();
    if (playerAgent == nullptr) {
        return false;
    }
    if (g_resolveResearchDescriptorTrampoline == 0) {
        StopUnsafeManagerRuntimeLaunch(
            "A Rage controller recipe reached its completion gate without the validated AP99 resolver.");
    }
    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolve = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    const auto* descriptor = resolve(
        action.completionTemplateResearchControlId);
    if (descriptor == nullptr || descriptor[4] == 0) {
        StopUnsafeManagerRuntimeLaunch(
            "A Rage controller recipe could not resolve its declared AP99 completion template.");
    }
    return ReadPackedAttributeValue(playerAgent, descriptor[4], 0) != 0;
}

int StockCurrentPlayerGold() {
    // AP24 click handler 0x004B2A60 obtains the UI manager, resolves its
    // current player, and invokes that player's vtable +0x20 data reader with
    // APP (Gold) before it deducts or submits Rage. Reproduce the same read at
    // the private boundary; GPL remains the payment/effect owner.
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

void UpdateSecondaryPanelPresentation(std::uint32_t controller) {
    if (controller == 0 ||
        controller != static_cast<std::uint32_t>(
            InterlockedCompareExchange(&g_childController, 0, 0))) {
        return;
    }
    unsigned char* context = ActivePanelContext();
    if (context == nullptr) {
        return;
    }
    UpdateResearchPresentations(controller);
    UpdateResourceMeters(controller);
    RefreshPrivateActionRows(controller, false);
    const DWORD now = SimulationClock();
    for (const auto& action : g_stockControllerRegistry.timedRageActions) {
        if (g_activePanelRecord == nullptr ||
            action.panelKey != g_activePanelRecord->panelKey) continue;
        const bool levelAvailable =
            SelectedBuildingLevel(context) >= static_cast<int>(action.requiredLevel);
        DWORD elapsed = now - g_timedRageStartedAt;
        bool active = InterlockedCompareExchange(
            &g_timedRageActive, 0, 0) != 0 &&
            g_activeTimedRageAction == &action;
        if (active && elapsed >= action.durationMs) {
            InterlockedExchange(&g_timedRageActive, 0);
            g_activeTimedRageAction = nullptr;
            active = false;
            elapsed = 0;
        }
        if (active && levelAvailable) {
            SetControllerControlVisible(controller, action.actionControlId, false);
            SetControllerControlVisible(controller, action.iconControlId, true);
            SetControllerControlVisible(controller, action.priceControlId, false);
            SetControllerControlVisible(controller, action.activeDisplayControlId, true);
            SetControllerControlVisible(controller, action.progressControlId, true);
            std::uint32_t progress[4] = {7, elapsed, 0, action.durationMs};
            SendControllerMessage(
                controller, action.progressControlId, 0x29, 0,
                reinterpret_cast<std::uint32_t>(progress));
            SendControllerMessage(
                controller, action.progressControlId, 0x08, 0, 0);
        } else {
            SetControllerControlVisible(controller, action.actionControlId, levelAvailable);
            SetControllerControlVisible(controller, action.iconControlId, levelAvailable);
            SetControllerControlVisible(controller, action.priceControlId, levelAvailable);
            SetControllerControlVisible(controller, action.activeDisplayControlId, false);
            SetControllerControlVisible(controller, action.progressControlId, false);
            const auto* meter = FindActiveMeter(action.resourceKey);
            if (StockRageOfKrolmCount() != 0 ||
                ResourceStock(meter) < static_cast<int>(action.resourceCost) ||
                InterlockedCompareExchange(&g_pendingRageHandle, 0, 0) != 0) {
                SendControllerMessage(
                    controller, action.actionControlId, 0x0A, 1, 0);
            }
        }
    }
}

bool CaptureSubmittedResearch(
    const BuildingActivitySnapshot& activityToRestore) {
    if (!g_researchOwner.pending ||
        g_researchOwner.context == nullptr) {
        return false;
    }
    const BuildingActivitySnapshot submitted =
        CaptureBuildingActivity(g_researchOwner.context);
    if (submitted.command !=
            static_cast<int>(g_researchOwner.record->actionControlId) ||
        submitted.duration <= 0) {
        return false;
    }

    RestoreBuildingActivity(
        g_researchOwner.context, activityToRestore);
    g_researchOwner.startedAt =
        static_cast<DWORD>(submitted.startedAt);
    g_researchOwner.duration =
        static_cast<DWORD>(submitted.duration);
    g_researchOwner.pending = false;
    g_researchOwner.active = true;

    char trace[192] = {};
    sprintf_s(
        trace,
        "Captured queued private research 0x%08X tuple %u/%u and restored AP10 activity.",
        g_researchOwner.record->actionControlId,
        g_researchOwner.startedAt,
        g_researchOwner.duration);
    WriteLog(trace);
    return true;
}

void StageResearchForStockCompletion() {
    unsigned char* context = g_researchOwner.context;
    WritePackedAttributeValue(
        context,
        kCurrentResearchAttributeId,
        static_cast<int>(g_researchOwner.record->actionControlId));
    WritePackedAttributeValue(
        context,
        kResearchStartedAtAttributeId,
        static_cast<int>(g_researchOwner.startedAt));
    WritePackedAttributeValue(
        context,
        kResearchDurationAttributeId,
        static_cast<int>(g_researchOwner.duration));
}

void __cdecl ResearchCompletionBridge(
    std::uint32_t commandOwner,
    void* context,
    std::uint32_t eventRecord,
    std::uint32_t eventArgument,
    std::uint32_t eventType) {
    const bool privateResearchCompletion =
        eventType == 2 &&
        g_researchOwner.active &&
        g_researchOwner.context == context;
    if (!privateResearchCompletion) {
        g_stockResearchCompletion(
            commandOwner, context, eventRecord, eventArgument, eventType);
        return;
    }

    // Stock event 0x2009 is the authoritative Blacksmith completion boundary.
    // The private owner keeps AP10 recruitment in the building's packed tuple,
    // so publish AP99's captured tuple only for this literal stock callback.
    // This avoids predicting the event from elapsed time and preserves the
    // original descriptor lookup, attribute write, alert, and cleanup order.
    const BuildingActivitySnapshot liveActivity =
        CaptureBuildingActivity(context);
    StageResearchForStockCompletion();

    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveResearchDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    const std::uint32_t recipe = g_researchOwner.record->actionControlId;
    const auto* state = FindPrivateResearchDescriptor(g_researchOwner.record);
    const auto* expectedDescriptor = state == nullptr
        ? nullptr : state->descriptor;
    if (resolveResearchDescriptor(recipe) != expectedDescriptor) {
        RestoreBuildingActivity(context, liveActivity);
        StopUnsafeManagerRuntimeLaunch(
            "Private research completion found that AP99 lost its manager descriptor registration.");
    }

    InterlockedExchange(&g_researchCompletionStaged, 1);
    g_stockResearchCompletion(
        commandOwner, context, eventRecord, eventArgument, eventType);
    const BuildingActivitySnapshot stockResult =
        CaptureBuildingActivity(context);
    const bool completed = stockResult.command != static_cast<int>(recipe);
    RestoreBuildingActivity(context, liveActivity);
    if (!completed) {
        InterlockedExchange(&g_researchCompletionStaged, 0);
        WriteLog(
            "Stock event 0x2009 returned without retiring private research.");
        return;
    }

    g_researchOwner = {};
    InterlockedExchange(&g_researchCompletedThisUpdate, 1);
    char trace[128] = {};
    sprintf_s(
        trace,
        "Observed native event 0x2009 complete private research 0x%08X.",
        recipe);
    WriteLog(trace);
}

void __fastcall GameUpdateRefreshBridge(void* gameState, void*) {
    // This call site is Majesty's stock state-3 update dispatch. Run the
    // original update first, exactly as the unmodified main loop does, then
    // refresh the live secondary row on that same main/UI thread. The private
    // research owner also advances here so it uses the stock
    // simulation clock and never introduces a timer or worker thread.
    BuildingActivitySnapshot activityBeforeUpdate = {};
    const bool researchSubmissionPending =
        g_researchOwner.pending &&
        g_researchOwner.context != nullptr;
    if (researchSubmissionPending) {
        activityBeforeUpdate = CaptureBuildingActivity(
            g_researchOwner.context);
    }

    g_stockGameUpdate(gameState);
    if (researchSubmissionPending &&
        CaptureSubmittedResearch(activityBeforeUpdate) &&
        InterlockedCompareExchange(&g_secondaryPanelActive, 0, 0) != 0) {
        const auto controller = static_cast<std::uint32_t>(
            InterlockedCompareExchange(&g_childController, 0, 0));
        RefreshPrivateResearchRows(controller);
    }
    if (InterlockedExchange(
            &g_researchCompletedThisUpdate, 0) != 0) {
        if (InterlockedCompareExchange(&g_secondaryPanelActive, 0, 0) != 0) {
            const auto controller = static_cast<std::uint32_t>(
                InterlockedCompareExchange(&g_childController, 0, 0));
            RefreshPrivateResearchRows(controller);
        }
        InterlockedExchange(&g_researchCompletionStaged, 0);
        // Event 0x2009 has already completed and refreshed the private rows in
        // this update. Resume ordinary AP69 presentation on the next update.
        return;
    }
    if (InterlockedCompareExchange(&g_secondaryPanelActive, 0, 0) == 0) {
        return;
    }
    const auto controller = static_cast<std::uint32_t>(
        InterlockedCompareExchange(&g_childController, 0, 0));
    UpdateSecondaryPanelPresentation(controller);
}

bool InstallGameUpdateRefreshBridge() {
    auto* callSite = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->gameUpdateCallRva);
    if (std::memcmp(
            callSite,
            g_buildProfile->expectedGameUpdateCall,
            sizeof(g_buildProfile->expectedGameUpdateCall)) != 0) {
        WriteLog(
            "Secondary-panel refresh bridge refused: stock game-update call bytes are unknown.");
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
            "Secondary-panel refresh bridge failed: VirtualProtect rejected the call site.");
        return false;
    }
    std::memcpy(callSite, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), callSite, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(callSite, sizeof(patch), oldProtection, &ignored);
    WriteLog(
        "Installed controller-recipe refresh bridge on Majesty's stock state-3 update dispatch.");
    return true;
}

std::uint32_t SelectedBuildingAgent() {
    unsigned char* context = ActivePanelContext();
    return context == nullptr
        ? 0u : *reinterpret_cast<std::uint32_t*>(context + 0x70);
}

bool SubmitPrivateRageCommand(const char* callbackSymbol) {
    unsigned char* context = ActivePanelContext();
    const std::uint32_t building = SelectedBuildingAgent();
    if (context == nullptr || building == 0 || callbackSymbol == nullptr) {
        WriteLog(
            "Controller recipe could not submit its stock Rage command because the selected building context is unavailable.");
        return false;
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
    // Stock AP24 carries both metadata words from this panel context in Rage
    // command 1. Preserve that command packet exactly.
    CommandMetadata metadata = {};
    getCommandMetadata(context, &metadata);
    InterlockedExchange(&g_pendingRageHandle, static_cast<LONG>(building));
    submitBuildingCommand(
        kRageOfKrolmCommandId,
        building,
        metadata.first,
        metadata.second);
    WriteLog("Submitted a controller recipe through stock Rage command metadata.");
    return true;
}

int HandleTimedRageAction(
    std::uint32_t controller,
    const MajestyStockControllers::TimedRageActionRecord& action) {
    if (InterlockedCompareExchange(&g_timedRageActive, 0, 0) != 0 ||
        StockRageOfKrolmCount() != 0 ||
        InterlockedCompareExchange(&g_pendingRageHandle, 0, 0) != 0 ||
        ResourceStock(FindActiveMeter(action.resourceKey)) <
            static_cast<int>(action.resourceCost)) {
        UpdateSecondaryPanelPresentation(controller);
        WriteLog("Stock AP24 ownership or resource gating rejected a timed controller action.");
        return 0;
    }
    const int currentGold = StockCurrentPlayerGold();
    if (currentGold < static_cast<int>(action.goldCost)) {
        WriteLog("Stock AP24 affordability gating rejected a timed controller action.");
        return 0;
    }
    g_pendingTimedRageAction = &action;
    g_pendingRageCommandAction = nullptr;
    if (!SubmitPrivateRageCommand(action.callbackSymbol.c_str())) {
        g_pendingTimedRageAction = nullptr;
        InterlockedExchange(&g_pendingRageHandle, 0);
        return 0;
    }
    g_activeTimedRageAction = &action;
    g_timedRageStartedAt = SimulationClock();
    InterlockedExchange(&g_timedRageActive, 1);
    UpdateSecondaryPanelPresentation(controller);
    return 0;
}

int BeginPrivateResearch(
    std::uint32_t controller,
    const MajestyStockControllers::ResearchRowRecord& row) {
    if (!g_stockResearchRouteReady) {
        WriteLog("Private research refused: the stock AP99 route was not validated.");
        return 0;
    }
    unsigned char* context = ActivePanelContext();
    if (context == nullptr) {
        WriteLog("Private research had no selected parent context.");
        return 0;
    }
    const auto commandOwner = *reinterpret_cast<std::uint32_t*>(context + 0x94);
    if (commandOwner == 0 ||
        *reinterpret_cast<std::uint32_t*>(context + 0x70) == 0) {
        WriteLog("Private research had no native command owner or selected building.");
        return 0;
    }
    if (PrivateResearchIsActive()) {
        UpdateSecondaryPanelPresentation(controller);
        WriteLog("Private research rejected: the stock-shaped singleton owner is already active.");
        return 0;
    }

    // AP10 recruitment and stock AP99 research both use APB, / APB8 /
    // APB\r as their one building-activity tuple. Preserve AP10's tuple, expose
    // an empty activity only for native validation/submission, capture the
    // exact research tuple stock produces, then restore AP10.
    // Payment, level/completion checks, duration selection, and command
    // construction therefore remain native while ownership is separated.
    const BuildingActivitySnapshot liveActivity =
        CaptureBuildingActivity(context);
    ClearBuildingActivity(context);

    using CanSubmitResearch = bool (__thiscall*)(void*, std::uint32_t);
    auto canSubmitResearch = reinterpret_cast<CanSubmitResearch>(
        g_imageBase + g_buildProfile->canSubmitResearchRva);
    if (!canSubmitResearch(
            reinterpret_cast<void*>(controller), row.actionControlId)) {
        RestoreBuildingActivity(context, liveActivity);
        RefreshPrivateResearchRows(controller);
        WriteLog("Stock eligibility gating rejected private research.");
        return 0;
    }

    using SubmitResearchCommand = void (__cdecl*)(
        std::uint32_t, void*, std::uint32_t);
    auto submitResearchCommand = reinterpret_cast<SubmitResearchCommand>(
        g_imageBase + g_buildProfile->submitResearchCommandRva);
    g_researchOwner.context = context;
    g_researchOwner.record = &row;
    g_researchOwner.startedAt = 0;
    g_researchOwner.duration = 0;
    g_researchOwner.pending = true;
    g_researchOwner.active = false;
    submitResearchCommand(commandOwner, context, row.actionControlId);

    // Networked building commands normally apply on the next stock game
    // update, not inside SubmitResearchCommand. Handle the synchronous shape
    // if present; otherwise restore AP10 now and let GameUpdateRefreshBridge
    // capture the queued tuple on the exact update where stock installs it.
    const bool capturedSynchronously =
        CaptureSubmittedResearch(liveActivity);
    if (!capturedSynchronously) {
        RestoreBuildingActivity(context, liveActivity);
    }

    RefreshPrivateResearchRows(controller);
    UpdateSecondaryPanelPresentation(controller);
    WriteLog(capturedSynchronously
        ? "Submitted private research through AP99 and captured its stock tuple synchronously."
        : "Submitted private research through AP99; its queued stock tuple remains pending.");
    return 0;
}

int HandleRageCommandAction(
    std::uint32_t controller,
    const MajestyStockControllers::RageCommandActionRecord& action) {
    unsigned char* context = ActivePanelContext();
    if (context == nullptr ||
        SelectedBuildingLevel(context) < static_cast<int>(action.requiredLevel) ||
        ResourceStock(FindActiveMeter(action.resourceKey)) <
            static_cast<int>(action.resourceCost) ||
        CompletionTemplateIsComplete(action)) {
        RefreshPrivateActionRows(controller, false);
        WriteLog("Stock-shaped resource, level, or completion gating rejected a Rage controller action.");
        return 0;
    }
    if (InterlockedCompareExchange(&g_pendingRageHandle, 0, 0) != 0) {
        WriteLog("A Rage controller action was rejected while the singleton Rage command is pending.");
        return 0;
    }
    g_pendingTimedRageAction = nullptr;
    g_pendingRageCommandAction = &action;
    if (!SubmitPrivateRageCommand(action.callbackSymbol.c_str())) {
        g_pendingRageCommandAction = nullptr;
        InterlockedExchange(&g_pendingRageHandle, 0);
    }
    UpdateSecondaryPanelPresentation(controller);
    return 0;
}

int HandleSovereignTargetAction(
    std::uint32_t controller,
    const MajestyStockControllers::SovereignTargetActionRecord& action) {
    unsigned char* context = ActivePanelContext();
    if (context == nullptr ||
        SelectedBuildingLevel(context) < static_cast<int>(action.requiredLevel) ||
        ResourceStock(FindActiveMeter(action.resourceKey)) <
            static_cast<int>(action.resourceCost)) {
        RefreshPrivateActionRows(controller, false);
        WriteLog("Stock-shaped resource or level gating rejected a sovereign target action.");
        return 0;
    }
    const std::uint32_t building = SelectedBuildingAgent();
    if (building == 0) {
        WriteLog("Sovereign target action had no selected building agent.");
        return 0;
    }
    // Preserve AP69's stock target lifecycle. Publish the selected building
    // first and the immutable action record last; the latter is the commit
    // hook's ownership sentinel.
    InterlockedExchange(&g_pendingSovereignBuilding, static_cast<LONG>(building));
    g_pendingSovereignAction = &action;
    // AP69's stock slot-3 handler accepts only 0x1131..0x114C, then calls this
    // exact cdecl helper.  Invoke that same helper with the private descriptor
    // identity; calling the vtable with 0x2A20/0x2A21 would fall through to the
    // unrelated base-controller handler and never enter target mode.
    using BeginSovereignTarget = void (__cdecl*)(std::uint32_t);
    auto beginSovereignTarget = reinterpret_cast<BeginSovereignTarget>(
        g_imageBase + g_buildProfile->sovereignSpellClickRva);
    beginSovereignTarget(action.privateControlId);
    return 0;
}

// 0x004A7F40 constructs a stock five-dword research descriptor:
// duration, required building level, base research price, GMTX name, and
// completion attribute. Clone that descriptor under a
// private command key and change only the explicitly private gameplay price.
// Every stock consumer can then run unchanged while completion remains
// distinguishable from its template by descriptor identity.
const std::uint32_t* ResolvePrivateResearchDescriptor(
    PrivateResearchDescriptor* state) {
    if (state == nullptr || state->record == nullptr) {
        return nullptr;
    }
    if (state->descriptor != nullptr) {
        return state->descriptor;
    }
    if (g_resolveResearchDescriptorTrampoline == 0) {
        return nullptr;
    }
    using ResolveResearchDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveResearchDescriptor>(
        g_resolveResearchDescriptorTrampoline);
    const auto* templateDescriptor = resolveStockDescriptor(
        state->record->descriptorTemplateControlId);
    const auto* completionDescriptor = resolveStockDescriptor(
        state->record->completionTemplateControlId);
    if (templateDescriptor == nullptr || completionDescriptor == nullptr ||
        completionDescriptor[4] == 0) {
        WriteLog(
            "Private AP99 descriptor resolution failed: a declared stock template is unavailable.");
        return nullptr;
    }
    // AP99 allocates every five-dword descriptor through Majesty's operator
    // new immediately before registry insertion. The registry owns and frees
    // the allocation when the quest is unloaded; mirror that exact lifetime.
    using StockOperatorNew = void* (__cdecl*)(std::size_t);
    auto stockOperatorNew = reinterpret_cast<StockOperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    state->descriptor = static_cast<std::uint32_t*>(
        stockOperatorNew(kResearchDescriptorSize));
    if (state->descriptor == nullptr) {
        WriteLog("Private AP99 descriptor allocation returned null.");
        return nullptr;
    }
    std::memcpy(
        state->descriptor, templateDescriptor, kResearchDescriptorSize);
    state->descriptor[1] = state->record->requiredLevel;
    state->descriptor[2] = state->record->price;
    state->descriptor[4] = completionDescriptor[4];
    return state->descriptor;
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
    bool allRegistered = true;
    bool allAbsent = true;
    for (const auto& state : g_privateResearchDescriptors) {
        const auto* registered = resolveResearchDescriptor(
            state.record->actionControlId);
        allRegistered = allRegistered && registered != nullptr &&
            registered == state.descriptor;
        allAbsent = allAbsent && registered == nullptr;
    }
    if (allRegistered) return true;
    if (!allAbsent) {
        WriteLog(
            "Private AP99 registration failed: the stock registry contains a mixed or occupied descriptor set.");
        return false;
    }

    // All-null is the exact boundary at which AP99 rebuilt the registry for a
    // newly loaded quest and freed the preceding stock-owned descriptors.
    // Retire every borrowed identity before allocating replacements.
    for (auto& state : g_privateResearchDescriptors) {
        state.descriptor = nullptr;
    }
    for (auto& state : g_privateResearchDescriptors) {
        if (ResolvePrivateResearchDescriptor(&state) == nullptr) {
            return false;
        }
    }

    // AP99's stock descriptor construction at 0x004A83E0 inserts every
    // Blacksmith research recipe into this map with 0x004A8030, and every
    // later consumer, including completion at 0x004E0430, resolves through
    // the same map. Majesty clears and rebuilds this registry when a quest is
    // loaded without unloading this DLL. Re-resolve the private keys on every
    // secondary setup and create new stock-owned clones after that rebuild has
    // removed and freed the previous ones. Presentation, submission, and
    // completion therefore receive one stable identity for the current quest
    // while stock retains its normal teardown ownership.
    using FindOrInsert = void** (__thiscall*)(void*, const std::uint32_t*);
    auto findOrInsert = reinterpret_cast<FindOrInsert>(
        g_researchDescriptorRegistryFindOrInsert);
    for (const auto& state : g_privateResearchDescriptors) {
        const std::uint32_t key = state.record->actionControlId;
        void** slot = findOrInsert(
            reinterpret_cast<void*>(g_researchDescriptorRegistryMap), &key);
        if (slot == nullptr ||
            (*slot != nullptr && *slot != state.descriptor)) {
            WriteLog(
                "Private AP99 registration failed: the stock registry returned an occupied descriptor slot.");
            return false;
        }
        *slot = state.descriptor;
    }
    for (const auto& state : g_privateResearchDescriptors) {
        if (resolveResearchDescriptor(state.record->actionControlId) !=
                state.descriptor) {
            WriteLog(
                "Private AP99 registration failed: an inserted descriptor could not be resolved.");
            return false;
        }
    }
    const bool registryWasPreviouslyObserved =
        g_privateResearchDescriptorsRegistered;
    g_privateResearchDescriptorsRegistered = true;
    WriteLog(registryWasPreviouslyObserved
        ? "Re-registered private research descriptors after AP99 rebuilt its stock registry."
        : "Registered private research descriptors through AP99's stock registry.");
    return true;
}

bool InstallPrivateResearchDescriptorRegistry() {
    auto* entry = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->resolveResearchDescriptorRva);
    if (std::memcmp(
            entry,
            g_buildProfile->expectedResolveResearchDescriptorEntry,
            sizeof(g_buildProfile->expectedResolveResearchDescriptorEntry)) != 0) {
        WriteLog(
            "Private research descriptors refused: stock AP99 resolver bytes are unknown.");
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
            "Private research descriptors refused: AP99 registry insertion changed.");
        return false;
    }
    g_resolveResearchDescriptorTrampoline =
        reinterpret_cast<std::uintptr_t>(entry);
    g_researchDescriptorRegistryMap = registryMap;
    g_researchDescriptorRegistryFindOrInsert = findOrInsert;
    WriteLog(
        "Validated AP99's stock research descriptor registry for private registration.");
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
    // callback pointer for the scoped AP10/AP99 ownership handoff.
    if (dispatchSlot[-1] != 0x00002009u ||
        dispatchSlot[0] != stockCompletion ||
        dispatchSlot[1] != 0x0000200Bu) {
        WriteLog(
            "Private research completion bridge refused: stock event 0x2009 dispatch changed.");
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
            "Private research completion bridge failed: event 0x2009 dispatch is not writable.");
        return false;
    }
    dispatchSlot[0] = reinterpret_cast<std::uint32_t>(&ResearchCompletionBridge);
    DWORD ignored = 0;
    VirtualProtect(
        dispatchSlot, sizeof(*dispatchSlot), oldProtection, &ignored);
    WriteLog(
        "Installed the scoped private-research bridge on stock event 0x2009 completion.");
    return true;
}

const MajestyStockControllers::SecondaryPanelRecord* PanelForSpellRecord(
    const PrivateSpellDescriptor& state) {
    switch (state.kind) {
    case PrivateSpellDescriptorKind::TimedRage:
        return g_stockControllerRegistry.FindPanelByKey(
            static_cast<const MajestyStockControllers::TimedRageActionRecord*>(
                state.record)->panelKey);
    case PrivateSpellDescriptorKind::RageCommandVisual:
        return g_stockControllerRegistry.FindPanelByKey(
            static_cast<const MajestyStockControllers::RageCommandActionRecord*>(
                state.record)->panelKey);
    case PrivateSpellDescriptorKind::SovereignVisual:
    case PrivateSpellDescriptorKind::SovereignTarget:
        return g_stockControllerRegistry.FindPanelByKey(
            static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                state.record)->panelKey);
    }
    return nullptr;
}

const std::uint32_t* BuildPrivateSpellDescriptor(
    PrivateSpellDescriptor* state) {
    if (state == nullptr || state->record == nullptr ||
        g_resolveSpellDescriptorTrampoline == 0) {
        return nullptr;
    }
    if (state->descriptor[1] != 0) return state->descriptor;
    const auto* panel = PanelForSpellRecord(*state);
    if (panel == nullptr) return nullptr;
    using ResolveSpellDescriptor = const std::uint32_t* (__cdecl*)(
        std::uint32_t);
    auto resolveStockDescriptor = reinterpret_cast<ResolveSpellDescriptor>(
        g_resolveSpellDescriptorTrampoline);
    const std::uint32_t* source = nullptr;
    switch (state->kind) {
    case PrivateSpellDescriptorKind::TimedRage: {
        const auto& action =
            *static_cast<const MajestyStockControllers::TimedRageActionRecord*>(
                state->record);
        source = resolveStockDescriptor(action.descriptorTemplateControlId);
        const auto* priceTemplate = resolveStockDescriptor(
            action.levelPriceTemplateControlId);
        if (source == nullptr || priceTemplate == nullptr ||
            priceTemplate[3] != action.requiredLevel ||
            priceTemplate[4] != action.goldCost) {
            WriteLog(
                "Timed AP24 descriptor failed: its declared stock templates do not match the recipe values.");
            return nullptr;
        }
        std::memcpy(state->descriptor, source, 5 * sizeof(std::uint32_t));
        state->descriptor[0] = panel->buildingFamilyId;
        state->descriptor[1] = panel->childDialogId;
        state->descriptor[3] = action.requiredLevel;
        state->descriptor[4] = action.goldCost;
        break;
    }
    case PrivateSpellDescriptorKind::RageCommandVisual: {
        const auto& action =
            *static_cast<const MajestyStockControllers::RageCommandActionRecord*>(
                state->record);
        source = resolveStockDescriptor(action.visualTemplateControlId);
        if (source == nullptr || source[3] != action.requiredLevel) {
            WriteLog(
                "Rage action descriptor failed: its declared stock visual template does not match the recipe level.");
            return nullptr;
        }
        std::memcpy(state->descriptor, source, 5 * sizeof(std::uint32_t));
        state->descriptor[0] = panel->buildingFamilyId;
        state->descriptor[1] = panel->childDialogId;
        state->descriptor[3] = action.requiredLevel;
        state->descriptor[4] = 0;
        break;
    }
    case PrivateSpellDescriptorKind::SovereignVisual: {
        const auto& action =
            *static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                state->record);
        source = resolveStockDescriptor(action.visualTemplateControlId);
        if (source == nullptr) {
            WriteLog("Sovereign visual descriptor stock template is unavailable.");
            return nullptr;
        }
        std::memcpy(state->descriptor, source, 5 * sizeof(std::uint32_t));
        state->descriptor[0] = panel->buildingFamilyId;
        state->descriptor[1] = panel->childDialogId;
        state->descriptor[4] = 0;
        break;
    }
    case PrivateSpellDescriptorKind::SovereignTarget: {
        const auto& action =
            *static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                state->record);
        source = resolveStockDescriptor(action.targetTemplateControlId);
        if (source == nullptr || source[2] != action.stockTargetMode) {
            WriteLog(
                "Sovereign target descriptor failed: its declared stock target mode does not match the template.");
            return nullptr;
        }
        std::memcpy(state->descriptor, source, 5 * sizeof(std::uint32_t));
        state->descriptor[0] = panel->buildingFamilyId;
        state->descriptor[1] = panel->childDialogId;
        state->descriptor[2] = action.stockTargetMode;
        state->descriptor[3] = 1;
        state->descriptor[4] = 0;
        break;
    }
    }
    return state->descriptor;
}

extern "C" const std::uint32_t* __stdcall ResolvePrivateSpellDescriptor(
    std::uint32_t controlId) {
    if (g_activePanelRecord == nullptr) return nullptr;
    for (auto& state : g_privateSpellDescriptors) {
        const auto* panel = PanelForSpellRecord(state);
        if (panel != g_activePanelRecord) continue;
        bool matches = false;
        switch (state.kind) {
        case PrivateSpellDescriptorKind::TimedRage:
            matches = static_cast<const MajestyStockControllers::TimedRageActionRecord*>(
                state.record)->actionControlId == controlId;
            break;
        case PrivateSpellDescriptorKind::RageCommandVisual:
            matches = static_cast<const MajestyStockControllers::RageCommandActionRecord*>(
                state.record)->actionControlId == controlId;
            break;
        case PrivateSpellDescriptorKind::SovereignVisual:
            matches = static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                state.record)->visualControlId == controlId;
            break;
        case PrivateSpellDescriptorKind::SovereignTarget:
            matches = static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                state.record)->privateControlId == controlId;
            break;
        }
        if (!matches) continue;
        const std::uint32_t* descriptor = BuildPrivateSpellDescriptor(&state);
        if (descriptor == nullptr) {
            StopUnsafeManagerRuntimeLaunch(
                "A matched controller recipe could not resolve its declared stock spell template.");
        }
        if (state.kind == PrivateSpellDescriptorKind::SovereignVisual) {
            const auto& action =
                *static_cast<const MajestyStockControllers::SovereignTargetActionRecord*>(
                    state.record);
            unsigned char* context = ActivePanelContext();
            const bool levelMet = context != nullptr &&
                SelectedBuildingLevel(context) >=
                    static_cast<int>(action.requiredLevel);
            state.descriptor[3] = levelMet ? 0u : action.requiredLevel;
        }
        return descriptor;
    }
    return nullptr;
}

__declspec(naked) void ResolveSpellDescriptorHook() {
    __asm {
        cmp dword ptr [g_secondaryPanelActive], 1
        jne stock_resolver
        push dword ptr [esp + 4]
        call ResolvePrivateSpellDescriptor
        test eax, eax
        jz stock_resolver
        ret

    stock_resolver:
        jmp dword ptr [g_resolveSpellDescriptorTrampoline]
    }
}

bool InstallPrivateSpellDescriptorResolver() {
    auto* entry = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->resolveSpellDescriptorRva);
    if (std::memcmp(
            entry,
            g_buildProfile->expectedResolveSpellDescriptorEntry,
            sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry)) != 0) {
        WriteLog(
            "Private spell descriptors refused: stock resolver bytes are unknown.");
        return false;
    }
    auto* trampoline = reinterpret_cast<unsigned char*>(VirtualAlloc(
        nullptr,
        sizeof(g_buildProfile->expectedResolveSpellDescriptorEntry) + 5,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        WriteLog("Private spell descriptor trampoline allocation was rejected.");
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
            "Private spell descriptor resolver was not writable.");
        return false;
    }
    std::memcpy(entry, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(entry, sizeof(patch), oldProtection, &ignored);
    WriteLog("Installed the scoped stock AP69 descriptor resolver.");
    return true;
}

extern "C" std::uint32_t __stdcall ResolvePendingSovereignCursor(
    std::uint32_t mode, std::uint32_t stockOrdinal) {
    const auto* action = g_pendingSovereignAction;
    return action != nullptr && action->stockTargetMode == mode
        ? action->cursorOrdinal : stockOrdinal;
}

// Preserve the stock target transition literally and change only the cursor
// ordinal while the exact immutable controller recipe owns the session.
__declspec(naked) void SovereignCursorTransitionHook() {
    __asm {
        mov edx, dword ptr [esi]
        mov edx, dword ptr [edx + 48h]
        mov dword ptr [esi + 3Ch], eax
        mov dword ptr [esi + 40h], ebx
        mov dword ptr [esi + 38h], ebx
        mov eax, dword ptr [edi + 4]
        push eax
        push dword ptr [edi]
        call ResolvePendingSovereignCursor
        mov edx, dword ptr [esi]
        mov edx, dword ptr [edx + 48h]
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
    const auto* action = g_pendingSovereignAction;
    const auto building = static_cast<std::uint32_t>(InterlockedCompareExchange(
        &g_pendingSovereignBuilding, 0, 0));
    if (action != nullptr && building != 0 &&
        mode == action->stockTargetMode) {
        const auto* meter = g_stockControllerRegistry.FindMeter(
            action->panelKey, action->resourceKey);
        if (ResourceStock(meter) < static_cast<int>(action->resourceCost)) {
            // Stock temple spells still submit their current target packet
            // when the player cannot afford another cast. Their sovereign
            // executor rejects that packet at its native gold-affordability
            // branch, presents the stock failure feedback, and leaves the
            // repeat-cast target lifecycle intact. Preserve the stock mode and
            // use an unreachable cost only as the private resource predicate's
            // input to that exact downstream branch.
            cost = kStockUnaffordableGoldCost;
            WriteLog("Submitted a depleted private target through the stock unaffordable-spell route.");
        } else {
            mode = action->privateMode;
            target = building;
            cost = 0;
            WriteLog("Committed a private controller action through its stock sovereign target packet.");
        }
    }
    using SubmitCommand = void (__cdecl*)(
        std::uint32_t, std::uint32_t, std::uint32_t,
        std::uint32_t, std::uint32_t, std::uint32_t);
    auto submit = reinterpret_cast<SubmitCommand>(
        g_imageBase + g_buildProfile->sovereignSubmitCommandRva);
    submit(mode, player, x, y, target, cost);
}

extern "C" std::uint32_t __stdcall ResolvePrivateSovereignExecutorMode(
    std::uint32_t mode) {
    const auto* action =
        g_stockControllerRegistry.FindSovereignByPrivateMode(mode);
    if (action == nullptr) return mode;
    InterlockedExchange(
        &g_executingSovereignUnit,
        static_cast<LONG>(action->privateUnitId));
    return action->stockExecutorMode;
}

extern "C" std::uint32_t __stdcall ResolvePrivateSovereignUnit(
    std::uint32_t stockUnit) {
    const auto privateUnit = static_cast<std::uint32_t>(InterlockedExchange(
        &g_executingSovereignUnit, 0));
    return privateUnit == 0 ? stockUnit : privateUnit;
}

__declspec(naked) void PublicSovereignExecutorHook() {
    __asm {
        push dword ptr [esp + 4]
        call ResolvePrivateSovereignExecutorMode
        mov dword ptr [esp + 4], eax
        push -1
        push 006FA007h
        jmp dword ptr [g_sovereignExecutorResume]
    }
}

__declspec(naked) void Beta2SovereignExecutorHook() {
    __asm {
        push dword ptr [esp + 4]
        call ResolvePrivateSovereignExecutorMode
        mov dword ptr [esp + 4], eax
        push -1
        push 0070F5D7h
        jmp dword ptr [g_sovereignExecutorResume]
    }
}

__declspec(naked) void PublicSovereignConstructionHook() {
    __asm {
        push eax
        call ResolvePrivateSovereignUnit
        mov ecx, dword ptr [esp + 1Ch]
        mov ebx, eax
        jmp dword ptr [g_sovereignConstructionResume]
    }
}

__declspec(naked) void Beta2SovereignConstructionHook() {
    __asm {
        push eax
        call ResolvePrivateSovereignUnit
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
    WriteLog("Installed the private sovereign target, executor, and cursor route.");
    return true;
}

// Stock completion at 0x004DFE20 resolves the descriptor, applies its
// completion attribute, formats GMTX 0xBC ("Research Complete") with its name,
// posts the green alert, and clears the activity attributes. At 0x004DFFC7 EDI
// is the resolved name pointer. Keep that exact call and replace only EDI when
// EBX is one of the private descriptor clones.

extern "C" const char* __stdcall ResolvePrivateResearchCompletionText(
    const std::uint32_t* descriptor) {
    for (const auto& state : g_privateResearchDescriptors) {
        if (state.descriptor == descriptor) {
            return state.record->completionText.c_str();
        }
    }
    return nullptr;
}

__declspec(naked) void ResearchCompletionNamePushHook() {
    __asm {
        pushfd
        pushad
        push ebx
        call ResolvePrivateResearchCompletionText
        mov dword ptr [g_privateResearchCompletionText], eax
        popad
        popfd
        cmp dword ptr [g_privateResearchCompletionText], 0
        je stock_name
        push dword ptr [g_privateResearchCompletionText]
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
            "Private research completion text refused: stock completion bytes are unknown.");
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
            "Private research completion text failed: the stock site is not writable.");
        return false;
    }
    std::memcpy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(patch), oldProtection, &ignored);
    WriteLog(
        "Installed scoped private text substitution in the stock research-completion alert.");
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
        WriteLog("Private research refused: Majesty's stock AP99 bytes are unknown.");
        return false;
    }
    WriteLog("Validated AP99 native research refresh and command route.");
    return true;
}

__declspec(naked) void RageCommandDispatchHook() {
    __asm {
        mov ecx, dword ptr [ebp + 0Ch]
        cmp ecx, dword ptr [g_pendingRageHandle]
        jne stock_dispatch
        mov dword ptr [g_privateRageDispatch], 1

    stock_dispatch:
        push ecx
        mov ecx, edi
        jmp dword ptr [g_rageCommandDispatchResume]
    }
}

extern "C" void __cdecl SelectPrivateRageCallback() {
    g_privateRageCallback = nullptr;
    if (g_pendingTimedRageAction != nullptr) {
        g_privateRageCallback =
            g_pendingTimedRageAction->callbackSymbol.c_str();
        g_pendingTimedRageAction = nullptr;
    } else if (g_pendingRageCommandAction != nullptr) {
        g_privateRageCallback =
            g_pendingRageCommandAction->callbackSymbol.c_str();
        g_pendingRageCommandAction = nullptr;
    }
    if (g_privateRageCallback == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "A matched private Rage command lost its immutable controller recipe before GPL dispatch.");
    }
    WriteLog("Matched an exact controller-recipe Rage command handle.");
}

__declspec(naked) void RagePrivateBranchHook() {
    __asm {
        cmp dword ptr [g_privateRageDispatch], 1
        je private_recipe
        jmp stock_rage

    private_recipe:
        mov dword ptr [g_privateRageDispatch], 0
        mov dword ptr [g_pendingRageHandle], 0
        pushfd
        pushad
        call SelectPrivateRageCallback
        popad
        popfd
        cmp dword ptr [g_privateRageCallback], 0
        je stock_rage
        push dword ptr [g_privateRageCallback]
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

void __fastcall SecondaryPanelControllerSetup(void* controller, void*) {
    g_stockAp69Setup(controller);
    if (g_activePanelRecord == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "A captured secondary controller has no resolved MMCR panel owner.");
    }
    if (!RegisterPrivateResearchDescriptors()) {
        StopUnsafeManagerRuntimeLaunch(
            "Private AP99 descriptors could not be registered at the stock secondary-panel setup boundary.");
    }
    for (auto& state : g_privateSpellDescriptors) {
        if (PanelForSpellRecord(state) == g_activePanelRecord &&
            BuildPrivateSpellDescriptor(&state) == nullptr) {
            StopUnsafeManagerRuntimeLaunch(
                "A declared stock spell template could not be cloned at the AP69 setup boundary.");
        }
    }
    const auto value = reinterpret_cast<std::uint32_t>(controller);
    RefreshPrivateActionRows(value, true);
    RefreshTimedRageRows(value);
    RefreshPrivateResearchRows(value);
    UpdateSecondaryPanelPresentation(value);
}

int ReturnToPrivateParent(void* controller, std::uint32_t parentDialogId) {
    // Literal AP69 Back branch: obtain this child's building, hide its stream,
    // create the parent (id, context, 0, 0), return 1 for stock removal of the
    // initiating child. Only the parent dialog ID is private. No cached parent
    // pointer or creation-wide AP10 redirection is involved.
    using GetUiManager = void* (__cdecl*)();
    using HidePanel = void (__thiscall*)(void*);
    using CreateDialog = std::uint32_t (__thiscall*)(
        void*, std::uint32_t, void*, std::uint32_t, std::uint32_t);
    void* manager = reinterpret_cast<GetUiManager>(
        g_imageBase + g_buildProfile->uiManagerRva)();
    void* context = NativePanelContext(reinterpret_cast<std::uint32_t>(controller));
    if (context == nullptr) return 0;
    void* panel = *reinterpret_cast<void**>(static_cast<unsigned char*>(controller) + 0x24);
    auto** table = *reinterpret_cast<void***>(panel);
    reinterpret_cast<HidePanel>(table[0x14 / sizeof(void*)])(panel);
    reinterpret_cast<CreateDialog>(g_imageBase + g_buildProfile->dialogCreationRva)(
        manager, parentDialogId, context, 0, 0);
    return 1;
}

int __fastcall SecondaryPanelControllerControl(
    void* controller, void*, std::uint32_t controlId) {
    const auto value = reinterpret_cast<std::uint32_t>(controller);
    if (g_activePanelRecord != nullptr) {
        if (controlId == 0x1F4D) {
            return ReturnToPrivateParent(controller, g_activePanelRecord->parentDialogId);
        }
        for (const auto& action : g_stockControllerRegistry.timedRageActions) {
            if (action.panelKey == g_activePanelRecord->panelKey &&
                action.actionControlId == controlId) {
                return HandleTimedRageAction(value, action);
            }
        }
        for (const auto& row : g_stockControllerRegistry.researchRows) {
            if (row.panelKey == g_activePanelRecord->panelKey &&
                row.actionControlId == controlId) {
                return BeginPrivateResearch(value, row);
            }
        }
        for (const auto& action : g_stockControllerRegistry.rageCommandActions) {
            if (action.panelKey == g_activePanelRecord->panelKey &&
                action.actionControlId == controlId) {
                return HandleRageCommandAction(value, action);
            }
        }
        for (const auto& action : g_stockControllerRegistry.sovereignTargetActions) {
            if (action.panelKey == g_activePanelRecord->panelKey &&
                action.visualControlId == controlId) {
                return HandleSovereignTargetAction(value, action);
            }
        }
    }
    return g_stockAp69Control(controller, controlId);
}

void __fastcall SecondaryPanelControllerEvent(
    void* controller,
    void*,
    std::uint32_t argument1,
    std::uint32_t argument2,
    std::uint32_t argument3,
    std::uint32_t argument4) {
    if (InterlockedCompareExchange(
            &g_researchCompletionStaged, 0, 0) != 0) {
        // This controller inherits AP69 only for its stable streamed-panel
        // lifecycle. A stock AP17 research completion never enters AP69's
        // event renderer. Preserve that class boundary during the one staged
        // completion update; the post-update AP99 refresh below the bridge
        // restores the completed private research rows immediately afterward.
        return;
    }
    g_stockAp69Event(controller, argument1, argument2, argument3, argument4);
    UpdateSecondaryPanelPresentation(
        reinterpret_cast<std::uint32_t>(controller));
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
        const auto value = reinterpret_cast<std::uint32_t>(controller);
        RefreshTimedRageRows(value);
        RefreshPrivateResearchRows(value);
        RefreshPrivateActionRows(value, true);
    }
}

void ClearSecondaryPanelControllerOwnedState() {
    g_renderedDataRecordRevision = -1;
    g_activeOccupantPanel = nullptr;
    g_activeQuestBoard = nullptr;
    g_activeQuestBoardFaulted = false;
    g_activeQuestRevision = -1;
    g_requestedQuestRevision = -1;
    g_questBoardPopulationRequested = false;
    for (std::size_t index = 0; index < kMaximumQuestOffers; ++index) {
        g_questOfferPresentations[index].agent = nullptr;
        g_questOfferPresentations[index].recordKey = 0;
        g_questOfferPresentations[index].name.clear();
        g_questOfferPresentations[index].detail.clear();
        g_questOfferPresentations[index].summaryTemplate.clear();
        g_questOfferPresentations[index].summaryView = {};
        g_questOfferPresentations[index].detailView = {};
    }
    g_questOfferPresentationCount = 0;
    g_paintingQuestOffer = nullptr;
    g_suppressQuestStatusIconsForCurrentRow = false;
    InterlockedExchange(&g_secondaryPanelHandle, 0);
    InterlockedExchange(&g_secondaryPanelActive, 0);
    InterlockedExchange(&g_captureChildController, 0);
    g_pendingSovereignAction = nullptr;
    InterlockedExchange(&g_pendingSovereignBuilding, 0);
    g_activePanelRecord = nullptr;
    g_activeRewardPanelRecord = nullptr;
    g_activeRewardFlagState = nullptr;
}

void __cdecl SecondaryPanelControllerDestroyed(void*, void*) {
    // The generic registry has already cleared g_childController after
    // proving this is still the exact captured instance. Invalidate only state
    // owned by that private child dialog; the live parent remains valid when
    // Majesty performs an ordinary secondary-panel transition.
    ClearSecondaryPanelControllerOwnedState();
    WriteLog(
        "Invalidated manager-owned secondary-controller state at Majesty's stock teardown boundary.");
}

bool InstallSecondaryPanelControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockAp69Setup == nullptr) {
        std::memcpy(
            g_childControllerVtable,
            stockVtable,
            sizeof(g_childControllerVtable));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_childControllerVtable,
                stockVtable,
                kAp69VtableEntries,
                &g_childController,
                &SecondaryPanelControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private secondary controller because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockAp69Setup = reinterpret_cast<ControllerSetup>(stockVtable[1]);
        g_stockAp69Control = reinterpret_cast<ControllerControl>(stockVtable[3]);
        g_stockAp69Event = reinterpret_cast<ControllerEvent>(stockVtable[8]);
        g_childControllerVtable[1] = reinterpret_cast<void*>(&SecondaryPanelControllerSetup);
        g_childControllerVtable[3] = reinterpret_cast<void*>(&SecondaryPanelControllerControl);
        g_childControllerVtable[8] = reinterpret_cast<void*>(&SecondaryPanelControllerEvent);
    }
    *objectVtable = g_childControllerVtable;
    InterlockedExchange(
        &g_childController, static_cast<LONG>(controller));
    UpdateSecondaryPanelPresentation(controller);
    return true;
}

int __fastcall ParentPanelControllerControl(
    void* controller, void*, std::uint32_t controlId) {
    int openResult = 0;
    if (HandleBuildingOpenToggle(controller, controlId, &openResult)) return openResult;
    if (OpenOccupantPanel(controller, controlId, &openResult)) return openResult;
    if (OpenQuestBoardPanel(controller, controlId, &openResult)) return openResult;
    const auto* gate = ActiveUpgradeGate();
    if (gate != nullptr && controlId == gate->upgradeControlId) {
        using GetPanelContext = void* (__thiscall*)(void*);
        auto getPanelContext = reinterpret_cast<GetPanelContext>(
            g_imageBase + g_buildProfile->getPanelContextRva);
        void* context = getPanelContext(controller);
        if (!UpgradeResearchComplete(context)) {
            ApplyUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            WriteLog(
                "Rejected a parent upgrade through its declared stock research prerequisite.");
            return 0;
        }
    }
    if (g_parentPanelRecord != nullptr &&
        controlId == g_parentPanelRecord->openCommandId) {
        if (InterlockedCompareExchange(&g_secondaryPanelActive, 0, 0) == 1) {
            // AP10 translates visual control 0x1F44 into command 0x1F49. Consume
            // that command before stock closes the primary panel and opens AP69.
            WriteLog("Ignored a repeated secondary-panel command with AP10's stock no-action result.");
            return 0;
        }
        // Arm on AP10's actual secondary-panel command, not when the parent
        // panel opens. Stock APd1 guild-member navigation may legitimately
        // occur between parent-panel creations; it must not own or cancel this
        // one-command handoff.
        InterlockedExchange(&g_secondaryPanelArmed, 1);
        WriteLog("Armed a manager secondary mapping from its AP10 command.");
        return g_stockParentControl(controller, controlId);
    }
    const int result = g_stockParentControl(controller, controlId);
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    ApplyUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), getPanelContext(controller));
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
    return result;
}

void __fastcall ParentPanelControllerSetup(void* controller, void*) {
    g_stockParentSetup(controller);
    if (g_parentPanelRecord == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "A captured parent controller has no resolved MMCR panel owner.");
    }

    // The stock dialog-creation lifecycle does not finish at the factory
    // result. It inserts and lays out the returned controller, then invokes
    // vtable slot 1 as the final setup presenter. AP17 applies its Guardhouse
    // prerequisite at this boundary. Run the same disabled-control/hidden-
    // price presentation only after AP10 has finished publishing its normal
    // upgrade row, changing solely the resolved prerequisite attribute.
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    void* context = getPanelContext(controller);
    ApplyUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), context);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}

void __fastcall ParentPanelControllerActivity(void* controller, void*) {
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    auto* context = static_cast<unsigned char*>(getPanelContext(controller));
    if (context != nullptr) {
        if (InterlockedCompareExchange(
                &g_researchCompletionStaged, 0, 0) != 0) {
            // AP17 never invokes AP10's guild-activity renderer during its
            // stock research completion update. CurrentResearch is cleared
            // partway through that update, and an upgrade may replace the
            // live panel context. This vtable exists only on the resolved parent, so preserve
            // the stock class boundary for every private parent activity pass across
            // the complete staged lifecycle.
            ApplyUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            return;
        }
        using ReadPackedAttribute = int (__thiscall*)(
            void*, std::uint32_t, std::uint32_t);
        auto readPackedAttribute = reinterpret_cast<ReadPackedAttribute>(
            g_imageBase + g_buildProfile->readPackedAttributeRva);
        const int currentResearch = readPackedAttribute(
            context, kCurrentResearchAttributeId, 0);
        const auto* privateResearch =
            g_stockControllerRegistry.FindResearchByCommand(
                static_cast<std::uint32_t>(currentResearch));
        if (privateResearch != nullptr && g_parentPanelRecord != nullptr &&
            privateResearch->panelKey == g_parentPanelRecord->panelKey) {
            // AP17 does not run AP10's guild-activity renderer while its
            // native research command owns CurrentResearch. Preserve that
            // stock class boundary for the combined private/AP99 surface.
            ApplyUpgradeResearchGate(
                reinterpret_cast<std::uint32_t>(controller), context);
            return;
        }
    }
    g_stockParentActivity(controller);
    ApplyUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), context);
}

void __fastcall ParentPanelControllerEvent(
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
    g_stockParentEvent(
        controller, argument1, argument2, argument3, argument4);
    using GetPanelContext = void* (__thiscall*)(void*);
    auto getPanelContext = reinterpret_cast<GetPanelContext>(
        g_imageBase + g_buildProfile->getPanelContextRva);
    ApplyUpgradeResearchGate(
        reinterpret_cast<std::uint32_t>(controller), getPanelContext(controller));
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}

void __cdecl ParentPanelControllerDestroyed(void*, void*) {
    g_parentOccupantPanel = nullptr;
    g_parentQuestBoard = nullptr;
    // Stock may destroy only this parent after opening a child in the primary
    // slot. The child owns its own native building handle and private mapping;
    // only its exact-instance destructor may invalidate that live UI state.
    InterlockedExchange(&g_captureParentController, 0);
    InterlockedExchange(&g_secondaryPanelArmed, 0);
    InterlockedExchange(&g_ap10ControllerContext, 0);
    g_parentPanelRecord = nullptr;
    g_parentRewardPanelRecord = nullptr;
    g_parentOpenToggleRecord = nullptr;
    WriteLog(
        "Invalidated manager-owned parent-controller state at Majesty's stock teardown boundary.");
}

bool InstallParentPanelControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockParentControl == nullptr) {
        const auto* catalogRecord =
            MajestyStockBuildingControllers::Find(kAp10DialogId);
        const auto* catalogProfile = MajestyStockBuildingControllers::Profile(
            catalogRecord, g_buildProfile != &kPublicBuildProfile);
        if (catalogProfile == nullptr ||
            catalogProfile->entryCount != kAp10VtableEntries ||
            stockVtable != reinterpret_cast<void**>(
                g_imageBase + catalogProfile->vtableRva)) {
            WriteLog(
                "Refused the private AP10 parent because it is not the cataloged stock class.");
            return false;
        }
        std::memcpy(
            g_parentControllerVtable,
            stockVtable,
            sizeof(g_parentControllerVtable));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_parentControllerVtable,
                stockVtable,
                kAp10VtableEntries,
                &g_parentController,
                &ParentPanelControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private parent controller because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockParentSetup =
            reinterpret_cast<ControllerSetup>(stockVtable[1]);
        g_stockParentControl =
            reinterpret_cast<ControllerControl>(stockVtable[3]);
        g_stockParentEvent =
            reinterpret_cast<ControllerEvent>(stockVtable[8]);
        g_stockParentActivity =
            reinterpret_cast<ControllerActivity>(stockVtable[13]);
        g_parentControllerVtable[1] =
            reinterpret_cast<void*>(&ParentPanelControllerSetup);
        g_parentControllerVtable[3] =
            reinterpret_cast<void*>(&ParentPanelControllerControl);
        g_parentControllerVtable[8] =
            reinterpret_cast<void*>(&ParentPanelControllerEvent);
        g_parentControllerVtable[13] =
            reinterpret_cast<void*>(&ParentPanelControllerActivity);
    }
    *objectVtable = g_parentControllerVtable;
    return true;
}

RewardFlagRuntimeState* FindRewardStateByPanel(const std::string& panelKey) {
    for (auto& state : g_rewardFlagStates) {
        if (state.record != nullptr && state.record->panelKey == panelKey) return &state;
    }
    return nullptr;
}

RewardFlagRuntimeState* FindRewardStateByPrivateMode(
    std::uint32_t privateMode) {
    for (auto& state : g_rewardFlagStates) {
        if (state.record != nullptr &&
            state.record->privateMode == privateMode) return &state;
    }
    return nullptr;
}

RewardFlagRuntimeState* FindRewardStateByModeObject(void* modeObject) {
    // The registry owns the 0x20-byte immutable Fl00-shaped descriptor, but
    // its validator/completion callbacks receive Majesty's larger live
    // placement context (the selected target is at +0x60).  They are not the
    // same allocation.  Preserve the direct check as a defensive convenience,
    // then resolve through the same selected-mode manager used by stock AP41.
    for (auto& state : g_rewardFlagStates) {
        if (state.modeObject == modeObject) return &state;
    }
    if (g_imageBase == 0 || g_buildProfile == nullptr) return nullptr;
    void* owner = *reinterpret_cast<void**>(
        g_imageBase + g_buildProfile->flagModeOwnerRva);
    if (owner == nullptr) return nullptr;
    using GetManager = void* (__thiscall*)(void*);
    using GetSelected = std::uint32_t (__thiscall*)(void*);
    auto manager = reinterpret_cast<GetManager>(
        g_imageBase + g_buildProfile->getFlagModeManagerRva)(owner);
    if (manager == nullptr) return nullptr;
    const auto selected = reinterpret_cast<GetSelected>(
        g_imageBase + g_buildProfile->getSelectedFlagModeRva)(manager);
    return FindRewardStateByPrivateMode(selected);
}

void* FindRegisteredRewardMode(std::uint32_t privateMode) {
    using GetRegistry = void* (__cdecl*)();
    using FindMode = void* (__thiscall*)(void*, std::uint32_t);
    auto getRegistry = reinterpret_cast<GetRegistry>(
        g_imageBase + g_buildProfile->getFlagModeRegistryRva);
    void* registry = getRegistry();
    if (registry == nullptr) return nullptr;
    auto** vtable = *reinterpret_cast<void***>(registry);
    auto find = reinterpret_cast<FindMode>(vtable[24]);
    return find(registry, privateMode);
}

void SwapPrivateRewardAmount(RewardFlagRuntimeState* state) {
    if (state == nullptr) return;
    auto* stockAmount = reinterpret_cast<int*>(
        g_imageBase + g_buildProfile->attackRewardAmountRva);
    const int privateAmount = state->rewardAmount;
    state->rewardAmount = *stockAmount;
    *stockAmount = privateAmount;
}

void PostRewardUnavailableAlert(const RewardFlagRuntimeState* state) {
    if (state == nullptr || state->record == nullptr ||
        !state->record->hasAvailabilityGate) return;
    void* owner = *reinterpret_cast<void**>(
        g_imageBase + g_buildProfile->systemAlertOwnerRva);
    using PrepareAlert = void (__thiscall*)(void*, int, std::uint32_t, int);
    using PostLiteralAlert = void (__cdecl*)(const char*, int, int);
    auto prepare = reinterpret_cast<PrepareAlert>(
        g_imageBase + g_buildProfile->prepareSystemAlertRva);
    auto post = reinterpret_cast<PostLiteralAlert>(
        g_imageBase + g_buildProfile->postLiteralSystemAlertRva);
    prepare(owner, 1, 0x8000FF00u, 255);
    post(state->record->unavailableAlertText.c_str(), -1, 1);
}

bool RewardAvailabilityIsOpen(const RewardFlagRuntimeState* state) {
    if (state == nullptr || state->record == nullptr) return false;
    if (!state->record->hasAvailabilityGate) return true;
    if (state->selectedBuilding == nullptr) return false;
    using ReadPackedAttribute = int (__thiscall*)(
        void*, std::uint32_t, std::uint32_t);
    auto read = reinterpret_cast<ReadPackedAttribute>(
        g_imageBase + g_buildProfile->readPackedAttributeRva);
    return read(
        state->selectedBuilding,
        state->record->availabilityAttributeId,
        0) != 0;
}

bool RewardTargetIsLegal(
    const RewardFlagRuntimeState* state, void* target) {
    if (state == nullptr || state->record == nullptr || target == nullptr) return false;
    using DisplayClassifier = int (__cdecl*)(void*);
    auto classify = reinterpret_cast<DisplayClassifier>(
        g_imageBase + g_buildProfile->displayClassifierRva);
    if (classify(target) != 4) return false;
    auto** vtable = *reinterpret_cast<void***>(target);
    using GetPlayerNumber = int (__thiscall*)(void*);
    auto getPlayer = reinterpret_cast<GetPlayerNumber>(vtable[7]);
    if (getPlayer(target) != 7) return false;
    using FindRelation = void* (__thiscall*)(void*, std::uint32_t, int);
    auto findRelation = reinterpret_cast<FindRelation>(
        g_imageBase + g_buildProfile->findAttachedRelationRva);
    return findRelation(
        static_cast<unsigned char*>(target) + 0xA4,
        state->record->privateFlagId,
        1) == nullptr;
}

int __cdecl PrivateRewardTargetValidator(void* modeObject) {
    using StockValidator = int (__cdecl*)(void*);
    auto stock = reinterpret_cast<StockValidator>(
        g_imageBase + g_buildProfile->stockCaptureValidatorRva);
    auto* state = FindRewardStateByModeObject(modeObject);
    const int stockResult = stock(modeObject);
    void* target = modeObject == nullptr
        ? nullptr
        : *reinterpret_cast<void**>(
              static_cast<unsigned char*>(modeObject) + 0x60);
    if (stockResult != 0) {
        if (state == nullptr || state->lastValidationTarget != target ||
            state->lastStockValidationResult != stockResult) {
            char trace[224] = {};
            std::snprintf(
                trace,
                sizeof(trace),
                "Private reward hover validator preserved stock result %d for mode object 0x%08lX.",
                stockResult,
                static_cast<unsigned long>(
                    reinterpret_cast<std::uintptr_t>(modeObject)));
            WriteLog(trace);
        }
        if (state != nullptr) {
            state->lastValidationTarget = target;
            state->lastStockValidationResult = stockResult;
            state->lastPrivateValidationResult = stockResult;
        }
        return stockResult;
    }
    if (!RewardAvailabilityIsOpen(state)) {
        if (state == nullptr || state->lastValidationTarget != target ||
            state->lastStockValidationResult != 0 ||
            state->lastPrivateValidationResult != 1) {
            WriteLog(
                "Private reward hover validator rejected a target because its declared availability gate is closed.");
        }
        if (state != nullptr) {
            state->lastValidationTarget = target;
            state->lastStockValidationResult = 0;
            state->lastPrivateValidationResult = 1;
        }
        return 1;
    }
    const bool legal = RewardTargetIsLegal(state, target);
    if (state == nullptr || state->lastValidationTarget != target ||
        state->lastStockValidationResult != 0 ||
        state->lastPrivateValidationResult != (legal ? 0 : 1)) {
        char trace[256] = {};
        std::snprintf(
            trace,
            sizeof(trace),
            "Private reward hover validator resolved mode 0x%08lX, target 0x%08lX: %s.",
            state == nullptr || state->record == nullptr
                ? 0ul
                : static_cast<unsigned long>(state->record->privateMode),
            static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(target)),
            legal ? "legal hostile-monster target" : "rejected private target");
        WriteLog(trace);
    }
    if (state != nullptr) {
        state->lastValidationTarget = target;
        state->lastStockValidationResult = 0;
        state->lastPrivateValidationResult = legal ? 0 : 1;
    }
    return legal ? 0 : 1;
}

void* __cdecl PrivateRewardCompletionTargetCheck(
    void* modeObject, void* picker) {
    using StockTargetCheck = void* (__cdecl*)(void*, void*);
    auto stock = reinterpret_cast<StockTargetCheck>(
        g_imageBase + g_buildProfile->stockFlagTargetCheckRva);
    void* target = stock(modeObject, picker);
    if (target == nullptr) {
        WriteLog(
            "Private reward completion preserved the stock target check's null result.");
        return nullptr;
    }
    auto* state = FindRewardStateByModeObject(modeObject);
    if (!RewardAvailabilityIsOpen(state)) {
        PostRewardUnavailableAlert(state);
        return nullptr;
    }
    const bool legal = RewardTargetIsLegal(state, target);
    WriteLog(
        legal
            ? "Private reward completion accepted the stock-selected hostile monster."
            : "Private reward completion rejected the stock-selected target at its independent authorization boundary.");
    return legal ? target : nullptr;
}

std::uintptr_t __fastcall RewardPanelActivation(void* controller, void*) {
    auto* state = g_activeRewardFlagState;
    SwapPrivateRewardAmount(state);
    const auto result = g_stockRewardPanelActivation(controller);
    SwapPrivateRewardAmount(state);
    return result;
}

std::uintptr_t __fastcall RewardPanelRefresh(
    void* controller, void*, std::uint32_t a1, std::uint32_t a2,
    std::uint32_t a3, std::uint32_t a4) {
    auto* state = g_activeRewardFlagState;
    SwapPrivateRewardAmount(state);
    const auto result = g_stockRewardPanelRefresh(controller, a1, a2, a3, a4);
    SwapPrivateRewardAmount(state);
    return result;
}

void SetPrivateRewardMode(RewardFlagRuntimeState* state) {
    if (state == nullptr || state->record == nullptr) return;
    void* owner = *reinterpret_cast<void**>(
        g_imageBase + g_buildProfile->flagModeOwnerRva);
    using SetMode = void (__thiscall*)(void*, std::uint32_t, int);
    auto setMode = reinterpret_cast<SetMode>(
        g_imageBase + g_buildProfile->setFlagModeRva);
    setMode(owner, state->record->privateMode, state->rewardAmount);

    // Read back the same stock manager state used by AP41's +/- re-arm path.
    // Apart from providing a focused runtime trace, this proves that an
    // authored private FourCC resolved to its own registered placement mode
    // rather than leaving a previous mod's cursor active.
    using GetManager = void* (__thiscall*)(void*);
    using GetSelected = std::uint32_t (__thiscall*)(void*);
    auto manager = reinterpret_cast<GetManager>(
        g_imageBase + g_buildProfile->getFlagModeManagerRva)(owner);
    const auto selected = manager == nullptr ? 0u :
        reinterpret_cast<GetSelected>(
            g_imageBase + g_buildProfile->getSelectedFlagModeRva)(manager);
    void* registered = FindRegisteredRewardMode(state->record->privateMode);
    const auto registeredCursor = registered == nullptr
        ? 0u
        : *reinterpret_cast<const std::uint32_t*>(
              static_cast<const unsigned char*>(registered) + 4);
    char trace[256] = {};
    std::snprintf(
        trace,
        sizeof(trace),
        "Armed private reward mode 0x%08lX with cursor %lu; stock manager selected 0x%08lX and registry returned 0x%08lX/cursor %lu.",
        static_cast<unsigned long>(state->record->privateMode),
        static_cast<unsigned long>(state->record->cursorOrdinal),
        static_cast<unsigned long>(selected),
        static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(registered)),
        static_cast<unsigned long>(registeredCursor));
    WriteLog(trace);
}

int __fastcall RewardPanelControl(
    void* controller, void*, std::uint32_t controlId) {
    auto* state = g_activeRewardFlagState;
    if (state == nullptr || state->record == nullptr) {
        return g_stockRewardPanelControl(controller, controlId);
    }
    if (controlId == 10 || controlId == 11) {
        SwapPrivateRewardAmount(state);
        const int result = g_stockRewardPanelControl(controller, controlId);
        SwapPrivateRewardAmount(state);
        void* owner = *reinterpret_cast<void**>(
            g_imageBase + g_buildProfile->flagModeOwnerRva);
        using GetManager = void* (__thiscall*)(void*);
        using GetSelected = std::uint32_t (__thiscall*)(void*);
        auto manager = reinterpret_cast<GetManager>(
            g_imageBase + g_buildProfile->getFlagModeManagerRva)(owner);
        const auto selected = reinterpret_cast<GetSelected>(
            g_imageBase + g_buildProfile->getSelectedFlagModeRva)(manager);
        if (selected == state->record->privateMode) SetPrivateRewardMode(state);
        return result;
    }
    if (controlId != 5002) {
        return g_stockRewardPanelControl(controller, controlId);
    }
    using GetSelectedAgent = void* (__thiscall*)(void*);
    state->selectedBuilding = reinterpret_cast<GetSelectedAgent>(
        g_imageBase + g_buildProfile->selectedAgentRva)(controller);
    if (!RewardAvailabilityIsOpen(state)) {
        PostRewardUnavailableAlert(state);
        return 0;
    }
    SetPrivateRewardMode(state);
    return 0;
}

int __fastcall RewardParentControl(
    void* controller, void*, std::uint32_t controlId) {
    int openResult = 0;
    if (HandleBuildingOpenToggle(controller, controlId, &openResult)) return openResult;
    if (OpenOccupantPanel(controller, controlId, &openResult)) return openResult;
    if (OpenQuestBoardPanel(controller, controlId, &openResult)) return openResult;
    const auto* panel = g_parentRewardPanelRecord;
    if (panel == nullptr || controlId != panel->openCommandId) {
        return g_stockRewardParentControl(controller, controlId);
    }
    using OpenDialog = int (__thiscall*)(void*, std::uint32_t, std::uint32_t);
    auto open = reinterpret_cast<OpenDialog>(
        g_imageBase + g_buildProfile->openDialogRva);
    return open(controller, panel->childDialogId, 0);
}

void __fastcall RewardParentSetup(void* controller, void*) {
    g_stockRewardParentSetup(controller);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}

void __fastcall RewardParentEvent(
    void* controller, void*, std::uint32_t a1, std::uint32_t a2,
    std::uint32_t a3, std::uint32_t a4) {
    g_stockRewardParentEvent(controller, a1, a2, a3, a4);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}

bool InstallRewardParentControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockRewardParentControl == nullptr) {
        const auto* catalogRecord =
            MajestyStockBuildingControllers::Find(kMx09DialogId);
        const auto* catalogProfile = MajestyStockBuildingControllers::Profile(
            catalogRecord, g_buildProfile != &kPublicBuildProfile);
        if (catalogProfile == nullptr ||
            catalogProfile->entryCount > kAp10VtableEntries ||
            stockVtable != reinterpret_cast<void**>(
                g_imageBase + catalogProfile->vtableRva)) {
            WriteLog(
                "Refused the private reward parent because it is not the cataloged stock MX09 class.");
            return false;
        }
        std::memcpy(
            g_rewardParentVtable,
            stockVtable,
            catalogProfile->entryCount * sizeof(void*));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_rewardParentVtable,
                stockVtable,
                catalogProfile->entryCount,
                &g_parentController,
                &ParentPanelControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private reward parent because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockRewardParentControl =
            reinterpret_cast<RewardControllerControl>(stockVtable[3]);
        g_stockRewardParentSetup =
            reinterpret_cast<RewardControllerSetup>(stockVtable[1]);
        g_stockRewardParentEvent =
            reinterpret_cast<RewardControllerEvent>(stockVtable[8]);
        g_rewardParentVtable[1] = reinterpret_cast<void*>(&RewardParentSetup);
        g_rewardParentVtable[3] = reinterpret_cast<void*>(&RewardParentControl);
        g_rewardParentVtable[8] = reinterpret_cast<void*>(&RewardParentEvent);
    }
    *objectVtable = g_rewardParentVtable;
    return true;
}

// MX04 -> MX05: only private routing and callback symbols differ from stock.
// The native 0x15 command retains its building ID, selected-agent ID, quoted
// price, simulation queue, affordability check, debit, and GPL invocation.
// Its private command ID survives UI teardown; no pending UI owner is borrowed
// by the later simulation dispatch.
struct OccupantBuildProfile {
    std::uintptr_t costStringCall;
    std::uintptr_t submitCall;
    std::uintptr_t actionStringCall;
    std::uintptr_t commandDispatch;
    std::uintptr_t stringConstructor;
    std::uintptr_t postSubmitControlCall;
    std::uintptr_t generalControlCall;
    std::uintptr_t postSubmitControlHandler;
    std::uintptr_t selectionFocusJumpTableEntry;
    std::uintptr_t selectionFocusBranch;
    std::uintptr_t actionFocusJumpTableEntry;
    std::uintptr_t actionFocusBranch;
    std::uintptr_t childVtable;
};
constexpr OccupantBuildProfile kPublicOccupants = {
    0x000BBDDD, 0x000BC14F, 0x000C55F1, 0x000C4DA0, 0x00227A80,
    0x000BC15A, 0x000BC171, 0x00098170,
    0x00098338, 0x000981A9, 0x00098340, 0x000981E8, 0x0033EAC4,
};
constexpr OccupantBuildProfile kBeta2Occupants = {
    0x000BC81D, 0x000BCB8F, 0x000C6031, 0x000C57E0, 0x0023A220,
    0x000BCB9A, 0x000BCBB1, 0x000995A0,
    0x000997EC, 0x000995D9, 0x000997F4, 0x00099618, 0x003577AC,
};
const OccupantBuildProfile& OccupantProfile() {
    return g_buildProfile == &kPublicBuildProfile ? kPublicOccupants : kBeta2Occupants;
}

// The stock MX05 cost evaluator constructs one GPL call object, adds the
// selected agent, executes it, reads one scalar result, and destroys the call
// object. Live-agent-list presentation uses that literal evaluator lifecycle and
// only adds the already-supported integer argument for its bounded row queries.
struct QuestBoardBuildProfile {
    std::uintptr_t evaluatorHelper;
    std::uintptr_t evaluatorConstructor;
    std::uintptr_t addAgent;
    std::uintptr_t addInteger;
    std::uintptr_t execute;
    std::uintptr_t scalarResult;
    std::uintptr_t liveAgentResolver;
    std::uintptr_t resultAt;
    std::uintptr_t evaluatorDestructor;
    std::uintptr_t stringDestructor;
    std::uintptr_t parentVtable;
    std::uintptr_t rowNameFormatterCall;
    std::uintptr_t rowNameFormatter;
    std::uintptr_t rowIntentAttributeCall;
    std::uintptr_t rowSummaryD8Call;
    std::uintptr_t rowSummaryD9Call;
    std::uintptr_t rowSummaryDACall;
    std::uintptr_t rowSummaryDBCall;
    std::uintptr_t rowSummaryTextResolver;
    std::uintptr_t rowStatusFirstBlock;
    std::uintptr_t rowStatusSecondBlock;
    std::uintptr_t rowStatusFirstDrawCall;
    std::uintptr_t rowStatusSecondDrawCall;
    std::uintptr_t rowStatusDraw;
    std::uintptr_t childControl;
    std::uintptr_t childRefresh;
    std::uintptr_t sharedListRefresh;
};
constexpr QuestBoardBuildProfile kPublicQuestBoard = {
    0x000BBDB0, 0x00163680, 0x00162C40, 0x00162C60,
    0x001637C0, 0x00163520, 0x00158B20, 0x0002DDF0,
    0x00163760, 0x00227C30, 0x0033D37C,
    0x00098485, 0x000422F0, 0x0009873D,
    0x000988A9, 0x0009886F, 0x0009863A, 0x00098609, 0x00024020,
    0x00098916, 0x000989F0, 0x000989EB, 0x00098A8C, 0x00272850,
    0x000BC0C0, 0x000BC1D0, 0x00097E20,
};
constexpr QuestBoardBuildProfile kBeta2QuestBoard = {
    0x000BC7F0, 0x001797B0, 0x00178D70, 0x00178D90,
    0x001798F0, 0x00179650, 0x0016EC60, 0x0002ED50,
    0x00179890, 0x0023A3D0, 0x00356054,
    0x00098AB5, 0x00043200, 0x00098D6D,
    0x00098ED9, 0x00098E9F, 0x00098C6A, 0x00098C39, 0x00024FF0,
    0x00098F46, 0x00099020, 0x0009901B, 0x000990BC, 0x00287CB0,
    0x000BCB00, 0x000BCC10, 0x00098640,
};
const QuestBoardBuildProfile& QuestBoardProfile() {
    return g_buildProfile == &kPublicBuildProfile
        ? kPublicQuestBoard : kBeta2QuestBoard;
}

bool ValidateSelectedParentControllerProfiles() {
    std::vector<std::uint32_t> selected;
    if (!g_stockControllerRegistry.panels.empty()) {
        selected.push_back(kAp10DialogId);
    }
    if (!g_stockControllerRegistry.rewardPanels.empty()) {
        selected.push_back(kMx09DialogId);
    }
    for (const auto& panel : g_stockControllerRegistry.occupantActionPanels) {
        selected.push_back(panel.parentControllerBase);
    }
    for (const auto& panel : g_stockControllerRegistry.liveAgentLists) {
        selected.push_back(panel.parentControllerBase);
    }
    for (const auto& toggle : g_stockControllerRegistry.buildingOpenToggles) {
        selected.push_back(toggle.parentControllerBase);
    }
    std::sort(selected.begin(), selected.end());
    selected.erase(std::unique(selected.begin(), selected.end()), selected.end());

    const bool beta2 = g_buildProfile != &kPublicBuildProfile;
    for (const auto controllerId : selected) {
        const auto* record = MajestyStockBuildingControllers::Find(controllerId);
        const auto* profile = MajestyStockBuildingControllers::Profile(record, beta2);
        if (profile == nullptr || profile->entryCount <= 8 ||
            profile->entryCount > kAp10VtableEntries) {
            WriteLog(
                "Manager parent controller catalog is missing a safe stock class boundary.");
            return false;
        }
        auto** table = reinterpret_cast<void**>(
            g_imageBase + profile->vtableRva);
        const std::uintptr_t expected[] = {
            profile->destructorRva,
            profile->setupRva,
            profile->controlRva,
            profile->eventRva,
        };
        const std::size_t slots[] = {0, 1, 3, 8};
        for (std::size_t index = 0; index < 4; ++index) {
            if (reinterpret_cast<std::uintptr_t>(table[slots[index]]) !=
                    g_imageBase + expected[index]) {
                char message[224] = {};
                std::snprintf(
                    message,
                    sizeof(message),
                    "Runtime profile %s rejected stock parent 0x%08lX: vtable slot %lu differs from the audited class.",
                    g_buildProfile->id,
                    static_cast<unsigned long>(controllerId),
                    static_cast<unsigned long>(slots[index]));
                WriteLog(message);
                return false;
            }
        }
    }
    return true;
}

// GplType's stock runtime tags are part of the evaluator ABI.  Never invoke a
// typed value virtual until the returned object carries the matching tag: the
// base implementation reports a fatal GPL type error rather than coercing it.
//
// The public list contract deliberately returns each row agent's numeric
// ATTRIB_AgentID as GPL integer type 1. That avoids relying on unsupported
// external marshalling of a GPL agent result. The Manager rebuilds only the
// stock-shaped reference fields required by Majesty's pinned resolver, which
// validates the ID and recovers the live unit.
constexpr std::uint32_t kGplIntegerResultType = 1;

bool ValidateQuestBoardProfile() {
    const auto& profile = QuestBoardProfile();
    const unsigned char helperEntry[] = {0x6A, 0xFF, 0x68};
    const unsigned char addIntegerEntry[] = {0x83, 0xC1, 0x08, 0xE9};
    const unsigned char liveAgentResolverEntry[] = {
        0x56, 0x8B, 0xF1, 0x8B, 0x46, 0x08, 0x50, 0xE8,
    };
    const unsigned char liveAgentResolverLookup[] = {0x8B, 0xC8, 0xE8};
    const unsigned char liveAgentResolverFields[] = {
        0x89, 0x46, 0x0C, 0x5E, 0x85, 0xC0, 0x74, 0x0D,
        0x80, 0x78, 0x38, 0x00, 0x75, 0x07, 0x8B, 0xC8, 0xE9,
    };
    const unsigned char liveAgentResolverNull[] = {0x33, 0xC0, 0xC3};
    const unsigned char statusObjectEntry[] = {
        0x68, 0x49, 0x4E, 0x42, 0x62,
    };
    const unsigned char firstStatusBranch[] = {0x0F, 0x84};
    const unsigned char apb10[] = {0x68, 0x41, 0x50, 0x42, 0x10};
    const unsigned char apb11[] = {0x68, 0x41, 0x50, 0x42, 0x11};
    const unsigned char apb14[] = {0x68, 0x41, 0x50, 0x42, 0x14};
    const unsigned char apb15[] = {0x68, 0x41, 0x50, 0x42, 0x15};
    const unsigned char status40B[] = {0x68, 0x0B, 0x04, 0x00, 0x00};
    const unsigned char status40C[] = {0x68, 0x0C, 0x04, 0x00, 0x00};
    const unsigned char status40D[] = {0x68, 0x0D, 0x04, 0x00, 0x00};
    const unsigned char status40E[] = {0x68, 0x0E, 0x04, 0x00, 0x00};
    auto** childVtable = reinterpret_cast<void**>(
        g_imageBase + OccupantProfile().childVtable);
    const auto populationAddress = reinterpret_cast<std::uintptr_t>(
        childVtable[11]);
    const bool populationInImage =
        populationAddress != 0 && populationAddress >= g_imageBase && populationAddress <
            g_imageBase + 0x00400000u &&
        populationAddress <= static_cast<std::uintptr_t>(-1) - 0xE4u;
    const auto* population = populationInImage
        ? reinterpret_cast<const unsigned char*>(populationAddress)
        : nullptr;
    const auto eraseTarget = RelativeCallTarget(
        population == nullptr ? nullptr : population + 0x3F);
    const auto insertTarget = RelativeCallTarget(
        population == nullptr ? nullptr : population + 0xDF);
    const auto* firstStatus = reinterpret_cast<const unsigned char*>(
        g_imageBase + profile.rowStatusFirstBlock);
    std::int32_t secondStatusRelative = 0;
    std::memcpy(
        &secondStatusRelative, firstStatus + 0x3B,
        sizeof(secondStatusRelative));
    const std::uintptr_t secondStatusTarget =
        g_imageBase + profile.rowStatusFirstBlock + 0x3Fu +
        secondStatusRelative;
    const bool mx05ListShape = populationInImage &&
        reinterpret_cast<std::uintptr_t>(childVtable[3]) ==
            g_imageBase + profile.childControl &&
        reinterpret_cast<std::uintptr_t>(childVtable[14]) >= g_imageBase &&
        reinterpret_cast<std::uintptr_t>(childVtable[14]) <
            g_imageBase + 0x00400000u &&
        reinterpret_cast<std::uintptr_t>(childVtable[14]) ==
            g_imageBase + profile.childRefresh &&
        eraseTarget >= g_imageBase && eraseTarget < g_imageBase + 0x00400000u &&
        insertTarget >= g_imageBase && insertTarget < g_imageBase + 0x00400000u;
    return ValidateOccupantPanelProfile() &&
        ValidatePrivateIntentTextProfile() &&
        mx05ListShape &&
        MatchesProfileBytes(
            profile.evaluatorHelper, helperEntry, sizeof(helperEntry),
            "MX05 GPL scalar evaluator") &&
        OccupantCallMatches(
            profile.evaluatorHelper + 0x2D, OccupantProfile().stringConstructor) &&
        OccupantCallMatches(
            profile.evaluatorHelper + 0x43, profile.evaluatorConstructor) &&
        OccupantCallMatches(
            profile.evaluatorHelper + 0x51, profile.stringDestructor) &&
        OccupantCallMatches(profile.evaluatorHelper + 0x5F, profile.addAgent) &&
        OccupantCallMatches(profile.evaluatorHelper + 0x68, profile.execute) &&
        OccupantCallMatches(
            profile.evaluatorHelper + 0x71, profile.scalarResult) &&
        OccupantCallMatches(profile.scalarResult + 0x05, profile.resultAt) &&
        OccupantCallMatches(
            profile.evaluatorHelper + 0x84, profile.evaluatorDestructor) &&
        MatchesProfileBytes(
            profile.addInteger, addIntegerEntry, sizeof(addIntegerEntry),
            "GPL integer argument adapter") &&
        MatchesProfileBytes(
            profile.liveAgentResolver, liveAgentResolverEntry,
            sizeof(liveAgentResolverEntry), "GPL live-agent resolver") &&
        MatchesProfileBytes(
            profile.liveAgentResolver + 0x0C, liveAgentResolverLookup,
            sizeof(liveAgentResolverLookup), "GPL live-agent registry lookup") &&
        MatchesProfileBytes(
            profile.liveAgentResolver + 0x13, liveAgentResolverFields,
            sizeof(liveAgentResolverFields), "GPL live-agent reference fields") &&
        MatchesProfileBytes(
            profile.liveAgentResolver + 0x28, liveAgentResolverNull,
            sizeof(liveAgentResolverNull), "GPL live-agent null result") &&
        OccupantCallMatches(
            profile.rowNameFormatterCall, profile.rowNameFormatter) &&
        OccupantCallMatches(
            profile.rowIntentAttributeCall,
            g_buildProfile->readPackedAttributeRva) &&
        QuestSummaryCallMatches(
            profile.rowSummaryD8Call, profile.rowSummaryTextResolver, 0xD8u) &&
        QuestSummaryCallMatches(
            profile.rowSummaryD9Call, profile.rowSummaryTextResolver, 0xD9u) &&
        QuestSummaryCallMatches(
            profile.rowSummaryDACall, profile.rowSummaryTextResolver, 0xDAu) &&
        QuestSummaryCallMatches(
            profile.rowSummaryDBCall, profile.rowSummaryTextResolver, 0xDBu) &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock, statusObjectEntry,
            sizeof(statusObjectEntry), "MX05 status-icon object construction") &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x39, firstStatusBranch,
            sizeof(firstStatusBranch), "MX05 first status-icon branch") &&
        secondStatusTarget == g_imageBase + profile.rowStatusSecondBlock &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x40, apb10, sizeof(apb10),
            "MX05 APB10 status lookup") &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x50, status40B, sizeof(status40B),
            "MX05 status resource 0x40B") &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x65, apb11, sizeof(apb11),
            "MX05 APB11 status lookup") &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x7C, status40C, sizeof(status40C),
            "MX05 status resource 0x40C") &&
        MatchesProfileBytes(
            profile.rowStatusFirstBlock + 0x88, status40B, sizeof(status40B),
            "MX05 status resource 0x40B fallback") &&
        MatchesProfileBytes(
            profile.rowStatusSecondBlock + 0x03, apb14, sizeof(apb14),
            "MX05 APB14 status lookup") &&
        MatchesProfileBytes(
            profile.rowStatusSecondBlock + 0x13, status40D, sizeof(status40D),
            "MX05 status resource 0x40D") &&
        MatchesProfileBytes(
            profile.rowStatusSecondBlock + 0x28, apb15, sizeof(apb15),
            "MX05 APB15 status lookup") &&
        MatchesProfileBytes(
            profile.rowStatusSecondBlock + 0x3F, status40E, sizeof(status40E),
            "MX05 status resource 0x40E") &&
        MatchesProfileBytes(
            profile.rowStatusSecondBlock + 0x4B, status40D, sizeof(status40D),
            "MX05 status resource 0x40D fallback") &&
        OccupantCallMatches(
            profile.rowStatusFirstDrawCall, profile.rowStatusDraw) &&
        OccupantCallMatches(
            profile.rowStatusSecondDrawCall, profile.rowStatusDraw) &&
        OccupantCallMatches(
            profile.childRefresh + 0x03, profile.sharedListRefresh);
}

bool EvaluateQuestBoardScalar(
    const char* symbol,
    void* agent,
    bool hasInteger,
    int integerValue,
    std::uint32_t* result,
    bool trace) {
    if (symbol == nullptr || agent == nullptr || result == nullptr) {
        if (trace) WriteLog("Live-agent-list callback status=invalid-input.");
        return false;
    }
    *result = 0;
    const auto& profile = QuestBoardProfile();
    std::uint32_t nativeString[3] = {};
    __declspec(align(4)) unsigned char evaluator[0x40] = {};
    using ConstructString = void* (__thiscall*)(void*, const char*);
    using DestroyString = void (__thiscall*)(void*);
    using ConstructEvaluator = void* (__thiscall*)(void*, const void*);
    using AddAgent = void (__thiscall*)(void*, void*);
    using AddInteger = void (__thiscall*)(void*, int);
    using Execute = void (__thiscall*)(void*);
    using ResultAt = void** (__thiscall*)(void*, std::uint32_t);
    using ScalarResult = std::uint32_t (__thiscall*)(void*);
    using DestroyEvaluator = void (__thiscall*)(void*);
    reinterpret_cast<ConstructString>(
        g_imageBase + OccupantProfile().stringConstructor)(nativeString, symbol);
    reinterpret_cast<ConstructEvaluator>(
        g_imageBase + profile.evaluatorConstructor)(evaluator, nativeString);
    reinterpret_cast<DestroyString>(
        g_imageBase + profile.stringDestructor)(nativeString);
    const std::uint32_t resolutionToken =
        *reinterpret_cast<const std::uint32_t*>(evaluator + 4);
    const bool traceResult = trace;
    if (traceResult) {
        char message[320] = {};
        std::snprintf(
            message, sizeof(message),
            "Live-agent-list callback resolve: symbol=%s owner=0x%08lX integer=%d has_integer=%u token=0x%08lX resolved=%u.",
            symbol,
            static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(agent)),
            integerValue, hasInteger ? 1u : 0u,
            static_cast<unsigned long>(resolutionToken),
            resolutionToken != 0 ? 1u : 0u);
        WriteLog(message);
    }
    if (resolutionToken == 0) {
        reinterpret_cast<DestroyEvaluator>(
            g_imageBase + profile.evaluatorDestructor)(evaluator);
        return false;
    }
    reinterpret_cast<AddAgent>(g_imageBase + profile.addAgent)(evaluator, agent);
    if (hasInteger) {
        reinterpret_cast<AddInteger>(
            g_imageBase + profile.addInteger)(evaluator, integerValue);
    }
    reinterpret_cast<Execute>(g_imageBase + profile.execute)(evaluator);
    void** entry = reinterpret_cast<ResultAt>(
        g_imageBase + profile.resultAt)(evaluator + 0x24, 0);
    void* value = entry == nullptr ? nullptr : *entry;
    const std::uint32_t type = value == nullptr ? 0xFFFFFFFFu :
        *reinterpret_cast<const std::uint32_t*>(
            static_cast<const unsigned char*>(value) + 4);
    const bool valid = type == kGplIntegerResultType;
    if (valid) {
        *result = reinterpret_cast<ScalarResult>(
            g_imageBase + profile.scalarResult)(evaluator);
    }
    if (traceResult) {
        char message[256] = {};
        std::snprintf(
            message, sizeof(message),
            "Live-agent-list callback complete: symbol=%s invoked=1 type=0x%08lX valid=%u result=0x%08lX (%lu).",
            symbol, static_cast<unsigned long>(type), valid ? 1u : 0u,
            static_cast<unsigned long>(*result),
            static_cast<unsigned long>(*result));
        WriteLog(message);
    }
    reinterpret_cast<DestroyEvaluator>(
        g_imageBase + profile.evaluatorDestructor)(evaluator);
    return valid;
}
using QuestBoardScalarEvaluator = bool (*)(
    const char*, void*, bool, int, std::uint32_t*, bool);
QuestBoardScalarEvaluator g_questBoardScalarEvaluator =
    &EvaluateQuestBoardScalar;

void* ResolveQuestBoardAgentNumber(std::uint32_t agentNumber) {
    if (agentNumber == 0 || agentNumber == 0xFFFFFFFFu) return nullptr;
    // Stock GplAgentRef is 16 bytes: vtable/type are not read by the proven
    // resolver method; +8 is the agent number and +0C is its disposable cache.
    // ValidateQuestBoardProfile pins that method's complete field-access shape
    // before this adapter can be installed.
    __declspec(align(4)) unsigned char reference[0x10] = {};
    *reinterpret_cast<std::uint32_t*>(reference + 8) = agentNumber;
    using ResolveAgent = void* (__thiscall*)(void*);
    return reinterpret_cast<ResolveAgent>(
        g_imageBase + QuestBoardProfile().liveAgentResolver)(reference);
}
using QuestBoardAgentNumberResolver = void* (*)(std::uint32_t);
QuestBoardAgentNumberResolver g_questBoardAgentNumberResolver =
    &ResolveQuestBoardAgentNumber;

using BuildingCommandDispatch = void (__cdecl*)(std::uint32_t, std::uint32_t,
                                               std::uint32_t, std::uint32_t);
BuildingCommandDispatch g_stockOccupantDispatch = nullptr;

bool OccupantCallMatches(std::uintptr_t callRva, std::uintptr_t targetRva) {
    const auto* code = reinterpret_cast<const unsigned char*>(g_imageBase + callRva);
    std::int32_t relative = 0;
    std::memcpy(&relative, code + 1, 4);
    return code[0] == 0xE8 && callRva + 5 + relative == targetRva;
}
bool ValidateOccupantPanelProfile() {
    const auto& profile = OccupantProfile();
    const unsigned char entry[] = {0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8};
    const unsigned char sharedControlCall[] = {0x55, 0x8B, 0xCE, 0xE8};
    const unsigned char selectionFocusEntry[] = {
        0x8B, 0x4E, 0x24, 0x8B, 0x01, 0x8B,
        0x50, 0x68, 0x6A, 0x00, 0x6A, 0x00,
    };
    const unsigned char actionFocusEntry[] = {
        0x8B, 0x17, 0x8B, 0x82, 0xB8, 0x00,
        0x00, 0x00, 0x8B, 0xCF, 0xFF, 0xD0,
    };
    const unsigned char selectedAgentWrite[] = {
        0x89, 0x78, 0x48, 0x57, 0x57, 0xE8,
    };
    std::uint32_t selectionFocusJumpTarget = 0;
    std::memcpy(
        &selectionFocusJumpTarget,
        reinterpret_cast<const void*>(
            g_imageBase + profile.selectionFocusJumpTableEntry),
        sizeof(selectionFocusJumpTarget));
    std::uint32_t actionFocusJumpTarget = 0;
    std::memcpy(
        &actionFocusJumpTarget,
        reinterpret_cast<const void*>(
            g_imageBase + profile.actionFocusJumpTableEntry),
        sizeof(actionFocusJumpTarget));
    const bool customHandoffPolicyRequested = std::any_of(
        g_stockControllerRegistry.liveAgentLists.begin(),
        g_stockControllerRegistry.liveAgentLists.end(),
        [](const QuestBoard& panel) {
            return panel.stayOnPanelAfterAction ||
                !panel.focusSelectedRowOnClick ||
                panel.actionUsesParent;
        });
    const bool sharedControlShape = !customHandoffPolicyRequested || (
        MatchesProfileBytes(
            profile.postSubmitControlCall - 3, sharedControlCall,
            sizeof(sharedControlCall), "MX05 post-submit control handoff") &&
        OccupantCallMatches(
            profile.postSubmitControlCall,
            profile.postSubmitControlHandler) &&
        MatchesProfileBytes(
            profile.generalControlCall - 3, sharedControlCall,
            sizeof(sharedControlCall), "MX05 general control handoff") &&
        OccupantCallMatches(
            profile.generalControlCall,
            profile.postSubmitControlHandler) &&
        selectionFocusJumpTarget == static_cast<std::uint32_t>(
            g_imageBase + profile.selectionFocusBranch) &&
        MatchesProfileBytes(
            profile.selectionFocusBranch, selectionFocusEntry,
            sizeof(selectionFocusEntry), "MX05 selected-row focus branch") &&
        actionFocusJumpTarget == static_cast<std::uint32_t>(
            g_imageBase + profile.actionFocusBranch) &&
        MatchesProfileBytes(
            profile.actionFocusBranch, actionFocusEntry,
            sizeof(actionFocusEntry), "MX05 action focus branch") &&
        OccupantCallMatches(
            profile.postSubmitControlHandler + 0xEB,
            g_buildProfile->uiManagerRva) &&
        MatchesProfileBytes(
            profile.postSubmitControlHandler + 0xF0,
            selectedAgentWrite, sizeof(selectedAgentWrite),
            "MX05 selected-agent focus write") &&
        OccupantCallMatches(
            profile.postSubmitControlHandler + 0xF5,
            g_buildProfile->uiManagerRva));
    return MatchesProfileBytes(profile.commandDispatch, entry, sizeof(entry), "MX05 command dispatch") &&
        OccupantCallMatches(profile.costStringCall, profile.stringConstructor) &&
        OccupantCallMatches(profile.actionStringCall, profile.stringConstructor) &&
        OccupantCallMatches(profile.submitCall, g_buildProfile->submitBuildingCommandRva) &&
        sharedControlShape &&
        MatchesProfileBytes(g_buildProfile->secondaryControllerResultRva,
            g_buildProfile->expectedResultSite, sizeof(g_buildProfile->expectedResultSite), "MX05 controller result") &&
        MatchesProfileBytes(g_buildProfile->dialogCreationRva,
            g_buildProfile->expectedCreationEntry, sizeof(g_buildProfile->expectedCreationEntry), "MX05 dialog creation") &&
        MatchesProfileBytes(g_buildProfile->dialogFactoryRva,
            g_buildProfile->expectedFactoryEntry, sizeof(g_buildProfile->expectedFactoryEntry), "MX05 dialog factory");
}
void* OccupantString(void* destination, const char* symbol) {
    using Construct = void* (__thiscall*)(void*, const char*);
    return reinterpret_cast<Construct>(g_imageBase + OccupantProfile().stringConstructor)(destination, symbol);
}
bool SetControllerControlText(
    std::uint32_t controller,
    std::uint32_t controlId,
    const char* text) {
    if (controller == 0 || text == nullptr) return false;
    void* panel = *reinterpret_cast<void**>(controller + 0x24);
    if (panel == nullptr) return false;
    auto** vtable = *reinterpret_cast<void***>(panel);
    if (vtable == nullptr || vtable[0x50 / sizeof(void*)] == nullptr) {
        return false;
    }
    std::uint32_t nativeString[3] = {};
    OccupantString(nativeString, text);
    using SetControlText = void (__thiscall*)(
        void*, std::uint32_t, const void*);
    reinterpret_cast<SetControlText>(vtable[0x50 / sizeof(void*)])(
        panel, controlId, nativeString);
    using DestroyString = void (__thiscall*)(void*);
    reinterpret_cast<DestroyString>(
        g_imageBase + QuestBoardProfile().stringDestructor)(nativeString);
    return true;
}
void* __fastcall OccupantCostString(void* destination, void*, const char* stockSymbol) {
    const char* symbol = stockSymbol;
    if (g_activeOccupantPanel != nullptr) {
        symbol = g_activeOccupantPanel->costCallbackSymbol.c_str();
    } else if (g_activeQuestBoard != nullptr) {
        symbol = g_activeQuestBoard->actionCostCallbackSymbol.c_str();
    }
    return OccupantString(destination, symbol);
}
void* __fastcall OccupantActionString(void* destination, void*, const char* stockSymbol) {
    const char* symbol = stockSymbol;
    if (g_executingOccupantPanel != nullptr) {
        symbol = g_executingOccupantPanel->actionCallbackSymbol.c_str();
    } else if (g_executingQuestBoard != nullptr) {
        symbol = g_executingQuestBoard->actionCallbackSymbol.c_str();
    }
    return OccupantString(destination, symbol);
}
void __cdecl SubmitOccupantAction(std::uint32_t command, std::uint32_t building,
                                 std::uint32_t agent, std::uint32_t price) {
    const QuestBoard* submittedList = nullptr;
    if (command == 0x15) {
        if (g_activeOccupantPanel != nullptr) {
            command = g_activeOccupantPanel->actionCommandId;
        } else if (g_activeQuestBoard != nullptr) {
            command = g_activeQuestBoard->actionCommandId;
            submittedList = g_activeQuestBoard;
        }
    }
    if (submittedList != nullptr) {
        char trace[256] = {};
        std::snprintf(trace, sizeof(trace),
            "List action submitted: command=0x%08lX parent_id=0x%08lX callback=%s.",
            static_cast<unsigned long>(command), static_cast<unsigned long>(building),
            submittedList->actionCallbackSymbol.c_str());
        WriteLog(trace);
    }
    reinterpret_cast<BuildingCommandDispatch>(
        g_imageBase + g_buildProfile->submitBuildingCommandRva)(command, building, agent, price);
}
void __cdecl DispatchOccupantAction(std::uint32_t command, std::uint32_t building,
                                   std::uint32_t agent, std::uint32_t price) {
    const auto* record = g_stockControllerRegistry.FindOccupantPanelByCommand(command);
    const auto* quest = g_stockControllerRegistry.FindLiveAgentListByCommand(command);
    const auto* previous = g_executingOccupantPanel;
    const auto* previousQuest = g_executingQuestBoard;
    ULONGLONG actionStarted = 0;
    if (quest != nullptr) {
        char trace[256] = {};
        std::snprintf(trace, sizeof(trace),
            "List action dispatch: command=0x%08lX parent_id=0x%08lX callback=%s.",
            static_cast<unsigned long>(command), static_cast<unsigned long>(building),
            quest->actionCallbackSymbol.c_str());
        WriteLog(trace);
        actionStarted = GetTickCount64();
    }
    g_executingOccupantPanel = record;
    g_executingQuestBoard = quest;
    g_stockOccupantDispatch(
        record == nullptr && quest == nullptr ? command : 0x15,
        building, agent, price);
    g_executingOccupantPanel = previous;
    g_executingQuestBoard = previousQuest;
    const ULONGLONG actionFinished = quest == nullptr ? 0 : GetTickCount64();
    // Stock's GPL evaluator has completed and released its call object here.
    // Package-owned records need not change the native Occupants relation, so
    // they may emit no XSCX event. Observe the completed action's revision now,
    // through the same stock list refresh used by an event, not a paint poll.
    if (quest != nullptr) {
        RefreshQuestBoardAfterAction(quest, building);
        const ULONGLONG presentationFinished = GetTickCount64();
        char trace[224] = {};
        std::snprintf(trace, sizeof(trace),
            "List action complete: command=0x%08lX parent_id=0x%08lX callback_ms=%llu presentation_ms=%llu.",
            static_cast<unsigned long>(command), static_cast<unsigned long>(building),
            actionFinished-actionStarted, presentationFinished-actionFinished);
        WriteLog(trace);
    }
}
int __fastcall LiveAgentListControlHandoff(
    void* controller, void*, std::uint32_t controlId) {
    const auto* board = g_activeQuestBoard;
    if (board != nullptr && IsLiveQuestBoardController(controller, board)) {
        if (controlId == 0x138Bu && board->stayOnPanelAfterAction) {
            // Stock MX05 has already queued command 0x15 before reaching this
            // call. Returning the stock non-transition result skips its world
            // selection transfer without closing or replacing the child list.
            return 0;
        }
        if (controlId == 0x1388u && !board->focusSelectedRowOnClick) {
            // MX05 has already accepted the row click and refreshed its list
            // state before this shared handoff. Skip only the stock transfer
            // of world/tracking focus to that row's agent.
            return 0;
        }
    }
    return g_stockQuestBoardSharedControl(controller, controlId);
}
bool WriteOccupantBranch(std::uintptr_t address, void* target, unsigned char opcode,
                         std::size_t size = 5) {
    unsigned char patch[6] = {opcode, 0, 0, 0, 0, 0x90};
    const auto relative = static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(target) - address - 5);
    std::memcpy(patch + 1, &relative, 4);
    DWORD previous = 0, ignored = 0;
    auto* destination = reinterpret_cast<void*>(address);
    if (!VirtualProtect(destination, size, PAGE_EXECUTE_READWRITE, &previous)) return false;
    std::memcpy(destination, patch, size);
    FlushInstructionCache(GetCurrentProcess(), destination, size);
    return VirtualProtect(destination, size, previous, &ignored) != 0;
}
bool InstallOccupantPanelRoute() {
    if (!ValidateOccupantPanelProfile()) return false;
    const auto& profile = OccupantProfile();
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 11, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) return false;
    std::memcpy(trampoline, reinterpret_cast<void*>(g_imageBase + profile.commandDispatch), 6);
    if (!WriteOccupantBranch(reinterpret_cast<std::uintptr_t>(trampoline + 6),
            reinterpret_cast<void*>(g_imageBase + profile.commandDispatch + 6), 0xE9)) return false;
    FlushInstructionCache(GetCurrentProcess(), trampoline, 11);
    g_stockOccupantDispatch = reinterpret_cast<BuildingCommandDispatch>(trampoline);
    const bool customHandoffPolicyRequested = std::any_of(
        g_stockControllerRegistry.liveAgentLists.begin(),
        g_stockControllerRegistry.liveAgentLists.end(),
        [](const QuestBoard& panel) {
            return panel.stayOnPanelAfterAction ||
                !panel.focusSelectedRowOnClick;
        });
    if (customHandoffPolicyRequested) {
        g_stockQuestBoardSharedControl =
            reinterpret_cast<ControllerControl>(
                g_imageBase + profile.postSubmitControlHandler);
        if (!WriteOccupantBranch(
                g_imageBase + profile.postSubmitControlCall,
                reinterpret_cast<void*>(&LiveAgentListControlHandoff),
                0xE8) ||
            !WriteOccupantBranch(
                g_imageBase + profile.generalControlCall,
                reinterpret_cast<void*>(&LiveAgentListControlHandoff),
                0xE8)) return false;
    }
    return WriteOccupantBranch(g_imageBase + profile.costStringCall, reinterpret_cast<void*>(&OccupantCostString), 0xE8) &&
        WriteOccupantBranch(g_imageBase + profile.actionStringCall, reinterpret_cast<void*>(&OccupantActionString), 0xE8) &&
        WriteOccupantBranch(g_imageBase + profile.submitCall, reinterpret_cast<void*>(&SubmitOccupantAction), 0xE8) &&
        WriteOccupantBranch(g_imageBase + profile.commandDispatch, reinterpret_cast<void*>(&DispatchOccupantAction), 0xE9, 6);
}
bool OpenOccupantPanel(void* controller, std::uint32_t command, int* result) {
    if (g_parentOccupantPanel == nullptr) return false;
    for (const auto& panel : g_stockControllerRegistry.occupantActionPanels) {
        if (panel.parentDialogId != g_parentOccupantPanel->parentDialogId || panel.openCommandId != command) continue;
        using Open = int (__thiscall*)(void*, std::uint32_t, std::uint32_t);
        *result = reinterpret_cast<Open>(g_imageBase + g_buildProfile->openDialogRva)(controller, panel.childDialogId, 0);
        return true;
    }
    return false;
}

bool OpenQuestBoardPanel(void* controller, std::uint32_t command, int* result) {
    if (g_parentQuestBoard == nullptr) return false;
    for (const auto& panel : g_stockControllerRegistry.liveAgentLists) {
        if (panel.parentDialogId != g_parentQuestBoard->parentDialogId ||
            panel.openCommandId != command) continue;
        using Open = int (__thiscall*)(void*, std::uint32_t, std::uint32_t);
        *result = reinterpret_cast<Open>(
            g_imageBase + g_buildProfile->openDialogRva)(
                controller, panel.childDialogId, 0);
        return true;
    }
    return false;
}

bool QueryQuestBoard(
    const char* symbol,
    void* parent,
    std::uint32_t row,
    std::uint32_t* result,
    bool trace = false) {
    return g_questBoardScalarEvaluator(
        symbol, parent, row != 0, static_cast<int>(row), result, trace);
}

bool QueryQuestBoardAgent(
    const char* symbol,
    void* parent,
    std::uint32_t row,
    void** result,
    bool trace = false) {
    if (row == 0 || result == nullptr) return false;
    *result = nullptr;
    std::uint32_t agentNumber = 0;
    if (!QueryQuestBoard(symbol, parent, row, &agentNumber, trace)) return false;
    *result = g_questBoardAgentNumberResolver(agentNumber);
    if (trace) {
        char message[256] = {};
        std::snprintf(
            message, sizeof(message),
            "Live-agent-list row ID resolved: symbol=%s row=%lu agent_number=0x%08lX result=0x%08lX.",
            symbol, static_cast<unsigned long>(row),
            static_cast<unsigned long>(agentNumber),
            static_cast<unsigned long>(
                reinterpret_cast<std::uintptr_t>(*result)));
        WriteLog(message);
    }
    return *result != nullptr;
}

const QuestOfferPresentation* FindQuestOfferPresentation(void* agent) {
    for (std::size_t index = 0;
         index < g_questOfferPresentationCount; ++index) {
        if (g_questOfferPresentations[index].agent == agent) {
            return &g_questOfferPresentations[index];
        }
    }
    return nullptr;
}

using StockQuestRowNameFormatter = void* (__cdecl*)(
    MajestyStringView*, void*, int);
using StockQuestRowAttributeReader = int (__thiscall*)(
    void*, std::uint32_t, std::uint32_t);
using StockQuestRowSummaryText = const MajestyStringView* (__thiscall*)(
    void*, std::uint32_t);
using StockQuestRowStatusIconDraw = void (__thiscall*)(
    void*, const void*, std::uint32_t);
StockQuestRowNameFormatter g_stockQuestRowNameFormatter = nullptr;
StockQuestRowAttributeReader g_stockQuestRowAttributeReader = nullptr;
StockQuestRowSummaryText g_stockQuestRowSummaryText = nullptr;
StockQuestRowStatusIconDraw g_stockQuestRowStatusIconDraw = nullptr;

void* __cdecl QuestBoardRowNameFormatter(
    MajestyStringView* destination,
    void* agent,
    int stockStyle) {
    // This marker is scoped to the one synchronous invocation of the stock row
    // painter. Every row begins here, so an unmatched row also clears any
    // presentation retained by the preceding row.
    g_paintingQuestOffer = nullptr;
    g_suppressQuestStatusIconsForCurrentRow = false;
    const QuestOfferPresentation* presentation =
        g_activeQuestBoard == nullptr
            ? nullptr : FindQuestOfferPresentation(agent);
    if (presentation == nullptr || destination == nullptr) {
        return g_stockQuestRowNameFormatter(destination, agent, stockStyle);
    }
    void* result = g_stockQuestRowNameFormatter(destination, agent, stockStyle);
    g_paintingQuestOffer = presentation;
    g_suppressQuestStatusIconsForCurrentRow = true;
    if (presentation->name.empty()) return result;
    if (g_privateIntentStringAssign == nullptr) return result;
    const auto length = static_cast<std::uint32_t>(
        presentation->name.size());
    const MajestyStringView view = {
        presentation->name.c_str(), length, length,
    };
    // Stock constructs and owns the caller's output string inside the row-name
    // formatter before writing its text. Preserve that exact lifecycle first;
    // assigning directly into the caller's unconstructed stack object can make
    // the stock assignment routine free an arbitrary pointer.
    return g_privateIntentStringAssign(destination, &view);
}

bool IsQuestBoardBuildingSummary(std::uint32_t textId) {
    return textId >= 0xD8u && textId <= 0xDBu;
}

const MajestyStringView* __fastcall QuestBoardRowSummaryText(
    void* stockTextOwner,
    void*,
    std::uint32_t textId) {
    const QuestOfferPresentation* presentation = g_paintingQuestOffer;
    g_paintingQuestOffer = nullptr;
    if (g_activeQuestBoard != nullptr && presentation != nullptr &&
        presentation >= g_questOfferPresentations &&
        presentation < g_questOfferPresentations + g_questOfferPresentationCount &&
        IsQuestBoardBuildingSummary(textId) &&
        presentation->summaryView.data != nullptr &&
        presentation->summaryView.length != 0) {
        // The stock caller immediately formats and draws this returned text.
        // The backing string remains owned by the immutable populated offer
        // record for the full child-panel lifetime, well beyond that draw.
        return &presentation->summaryView;
    }
    return g_stockQuestRowSummaryText(stockTextOwner, textId);
}

void __fastcall QuestBoardFirstStatusIconDraw(
    void* painter,
    void*,
    const void* rectangle,
    std::uint32_t style) {
    if (g_suppressQuestStatusIconsForCurrentRow) return;
    g_stockQuestRowStatusIconDraw(painter, rectangle, style);
}

void __fastcall QuestBoardSecondStatusIconDraw(
    void* painter,
    void*,
    const void* rectangle,
    std::uint32_t style) {
    const bool suppress = g_suppressQuestStatusIconsForCurrentRow;
    // Stock always reaches its second status block, even when the first block
    // is skipped. This is the exact end of one row's suppression lifetime.
    g_suppressQuestStatusIconsForCurrentRow = false;
    if (suppress) return;
    g_stockQuestRowStatusIconDraw(painter, rectangle, style);
}

bool QuestSummaryCallMatches(
    std::uintptr_t callRva,
    std::uintptr_t targetRva,
    std::uint32_t expectedTextId) {
    if (!OccupantCallMatches(callRva, targetRva) || callRva < 5) return false;
    const auto* push = reinterpret_cast<const unsigned char*>(
        g_imageBase + callRva - 5);
    std::uint32_t textId = 0;
    std::memcpy(&textId, push + 1, sizeof(textId));
    return push[0] == 0x68 && textId == expectedTextId;
}

int __fastcall QuestBoardRowIntentAttribute(
    void* agent,
    void*,
    std::uint32_t attribute,
    std::uint32_t fallback) {
    if (g_activeQuestBoard != nullptr &&
        attribute == 0x1E565041u) {
        for (std::size_t index = 0;
             index < g_questOfferPresentationCount; ++index) {
            if (g_questOfferPresentations[index].agent == agent &&
                g_questOfferPresentations[index].detailView.data != nullptr &&
                g_questOfferPresentations[index].detailView.length != 0) {
                return static_cast<int>(
                    kFirstQuestOfferIntentId + index);
            }
        }
    }
    return g_stockQuestRowAttributeReader(agent, attribute, fallback);
}

bool InstallQuestBoardRowPresentation() {
    const auto& profile = QuestBoardProfile();
    if (!OccupantCallMatches(
            profile.rowNameFormatterCall, profile.rowNameFormatter) ||
        !OccupantCallMatches(
            profile.rowIntentAttributeCall,
            g_buildProfile->readPackedAttributeRva) ||
        g_privateIntentStringAssign == nullptr) {
        WriteLog(
            "Private live-agent-list presentation refused: stock MX05 painter sites changed.");
        return false;
    }
    g_stockQuestRowNameFormatter =
        reinterpret_cast<StockQuestRowNameFormatter>(
            g_imageBase + profile.rowNameFormatter);
    g_stockQuestRowAttributeReader =
        reinterpret_cast<StockQuestRowAttributeReader>(
            g_imageBase + g_buildProfile->readPackedAttributeRva);
    g_stockQuestRowSummaryText =
        reinterpret_cast<StockQuestRowSummaryText>(
            g_imageBase + profile.rowSummaryTextResolver);
    g_stockQuestRowStatusIconDraw =
        reinterpret_cast<StockQuestRowStatusIconDraw>(
            g_imageBase + profile.rowStatusDraw);
    return WriteOccupantBranch(
               g_imageBase + profile.rowNameFormatterCall,
               reinterpret_cast<void*>(&QuestBoardRowNameFormatter), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowIntentAttributeCall,
               reinterpret_cast<void*>(&QuestBoardRowIntentAttribute), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowSummaryD8Call,
               reinterpret_cast<void*>(&QuestBoardRowSummaryText), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowSummaryD9Call,
               reinterpret_cast<void*>(&QuestBoardRowSummaryText), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowSummaryDACall,
               reinterpret_cast<void*>(&QuestBoardRowSummaryText), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowSummaryDBCall,
               reinterpret_cast<void*>(&QuestBoardRowSummaryText), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowStatusFirstDrawCall,
               reinterpret_cast<void*>(&QuestBoardFirstStatusIconDraw), 0xE8) &&
        WriteOccupantBranch(
               g_imageBase + profile.rowStatusSecondDrawCall,
               reinterpret_cast<void*>(&QuestBoardSecondStatusIconDraw), 0xE8);
}

bool IsLiveQuestBoardController(
    const void* controller,
    const QuestBoard* expectedBoard) {
    return controller != nullptr && expectedBoard != nullptr &&
        InterlockedCompareExchange(&g_childController, 0, 0) ==
            static_cast<LONG>(reinterpret_cast<std::uintptr_t>(controller)) &&
        g_activeQuestBoard == expectedBoard;
}

using QuestVectorErase = void* (__thiscall*)(
    void*, void*, void*, std::uint32_t*, void*, std::uint32_t*);
using QuestVectorInsert = void* (__thiscall*)(
    void*, void*, void*, std::uint32_t*, std::uint32_t*);
ControllerSetup g_stockQuestBoardPopulate = nullptr;
ControllerSetup g_stockQuestBoardRefresh = nullptr;
ControllerSetup g_stockQuestBoardSharedRefresh = nullptr;
QuestVectorErase g_stockQuestVectorErase = nullptr;
QuestVectorInsert g_stockQuestVectorInsert = nullptr;

std::uintptr_t RelativeCallTarget(const unsigned char* call) {
    if (call == nullptr || call[0] != 0xE8) return 0;
    std::int32_t relative = 0;
    std::memcpy(&relative, call + 1, sizeof(relative));
    return reinterpret_cast<std::uintptr_t>(call) + 5 + relative;
}

bool ReplaceQuestListVector(
    std::uint32_t controller,
    const std::uint32_t* agents,
    std::size_t count) {
    if (controller == 0 || agents == nullptr ||
        count > kMaximumQuestOffers ||
        g_stockQuestVectorErase == nullptr ||
        g_stockQuestVectorInsert == nullptr) return false;
    auto* vector = reinterpret_cast<unsigned char*>(controller) + 0x34;
    void* owner = *reinterpret_cast<void**>(vector);
    auto* position = *reinterpret_cast<std::uint32_t**>(vector + 0x0C);
    auto* boundary = *reinterpret_cast<std::uint32_t**>(vector + 0x10);
    std::uint32_t iteratorResult[2] = {};
    // Literal MX05 population first erases [begin,end) through the list
    // vector's own helper. Live-agent lists use that exact operation rather than
    // overwriting private container fields or borrowing an Occupants relation.
    g_stockQuestVectorErase(
        vector, iteratorResult, owner, position, owner, boundary);
    for (std::size_t index = 0; index < count; ++index) {
        owner = *reinterpret_cast<void**>(vector);
        position = *reinterpret_cast<std::uint32_t**>(vector + 0x0C);
        std::uint32_t agent = agents[index];
        iteratorResult[0] = iteratorResult[1] = 0;
        // This is the same native insertion helper used by MX05's slot-11
        // population virtual for every member of relation index 2.
        g_stockQuestVectorInsert(
            vector, iteratorResult, owner, position, &agent);
    }
    return true;
}

bool AppendQuestSummaryLiteral(
    std::string* destination,
    const char* text,
    std::size_t length) {
    if (destination == nullptr || text == nullptr) {
        return false;
    }
    for (std::size_t index = 0; index < length; ++index) {
        const char value = text[index];
        if (value == '%') destination->push_back('%');
        destination->push_back(value);
    }
    return true;
}

void ClearQuestBoardPresentation(std::uint32_t controller) {
    std::uint32_t unused = 0;
    if (controller != 0) {
        ReplaceQuestListVector(controller, &unused, 0);
    }
    for (std::size_t index = 0; index < kMaximumQuestOffers; ++index) {
        g_questOfferPresentations[index] = {};
    }
    g_paintingQuestOffer = nullptr;
    g_suppressQuestStatusIconsForCurrentRow = false;
    g_questOfferPresentationCount = 0;
    g_activeQuestRevision = -1;
    g_requestedQuestRevision = -1;
    g_questBoardPopulationRequested = false;
}

void FaultQuestBoardPresentation(
    std::uint32_t controller,
    const char* reason) {
    WriteLog(reason);
    ClearQuestBoardPresentation(controller);
    // Keep the captured stock MX05 controller and its native Back/selection
    // lifecycle intact. Only the package-fed rows are disabled for this child
    // instance; opening a new instance gets a fresh validation attempt.
    g_activeQuestBoardFaulted = true;
}

void __fastcall QuestBoardPopulate(void* controller, void*) {
    const auto* board = g_activeQuestBoard;
    if (!IsLiveQuestBoardController(controller, board)) {
        if (g_stockQuestBoardPopulate != nullptr)
            g_stockQuestBoardPopulate(controller);
        return;
    }
    const auto value = reinterpret_cast<std::uint32_t>(controller);
    if (g_activeQuestBoardFaulted) return;
    // Stock MX05 invokes slot 11 from its high-frequency slot-14 painter.
    // Package GPL must not be polled from that paint loop.  Populate only on
    // first open or after the event/command boundary explicitly requests a
    // new package revision.
    if (g_activeQuestRevision != -1 &&
        !g_questBoardPopulationRequested) return;
    auto* parent = NativePanelContext(value);
    if (parent == nullptr) {
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: stock MX05 lost its native parent context.");
        return;
    }
    const std::uint32_t parentId =
        *reinterpret_cast<const std::uint32_t*>(parent + 0x70);
    std::uint32_t revision = 0;
    if (g_questBoardPopulationRequested && g_requestedQuestRevision >= 0) {
        revision = static_cast<std::uint32_t>(g_requestedQuestRevision);
    } else if (!QueryQuestBoard(
                   board->revisionCallbackSymbol.c_str(), parent, 0,
                   &revision, false)) {
        QueryQuestBoard(
            board->revisionCallbackSymbol.c_str(), parent, 0, &revision, true);
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: the package revision callback could not be evaluated.");
        return;
    }
    if (revision > 0x7FFFFFFFu) {
        FaultQuestBoardPresentation(value, "List rows disabled: revision must be a nonnegative signed integer.");
        return;
    }
    g_questBoardPopulationRequested = false;
    g_requestedQuestRevision = -1;
    char contextTrace[256] = {};
    std::snprintf(
        contextTrace, sizeof(contextTrace),
        "Live-agent-list population: controller=0x%08lX parent=0x%08lX parent_id=0x%08lX revision=%lu.",
        static_cast<unsigned long>(value),
        static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(parent)),
        static_cast<unsigned long>(parentId),
        static_cast<unsigned long>(revision));
    WriteLog(contextTrace);
    std::uint32_t agents[kMaximumQuestOffers] = {};
    QuestOfferPresentation presentations[kMaximumQuestOffers] = {};
    std::uint32_t offerCount = 0;
    if (!QueryQuestBoard(
            board->rowCountCallbackSymbol.c_str(), parent, 0,
            &offerCount, false)) {
        QueryQuestBoard(
            board->rowCountCallbackSymbol.c_str(), parent, 0,
            &offerCount, true);
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: the row-count callback did not return an integer.");
        return;
    }
    if (offerCount > kMaximumQuestOffers) {
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: the row count exceeded the bounded 64-row contract.");
        return;
    }
    const std::size_t count = static_cast<std::size_t>(offerCount);
    const auto privateText = [](std::uint32_t intentId) {
        return intentId == 0 ? nullptr : FindPrivateIntentText(intentId);
    };
    const MajestyStringView* titleView = privateText(board->rowTitleIntentId);
    const MajestyStringView* textView = privateText(board->rowTextIntentId);
    const MajestyStringView* suffixView =
        privateText(board->rowValueSuffixIntentId);
    const auto invalidText = [](const MajestyStringView* view) {
        return view != nullptr &&
            (view->data == nullptr || view->length == 0 || view->length > 96);
    };
    if ((board->rowTitleIntentId != 0 && titleView == nullptr) ||
        (board->rowTextIntentId != 0 && textView == nullptr) ||
        (board->hasRowValue && suffixView == nullptr) ||
        invalidText(titleView) || invalidText(textView) || invalidText(suffixView)) {
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: manager-owned presentation text is missing or invalid.");
        return;
    }
    for (const auto& variant : board->rowVariants) {
        const MajestyStringView* variantTitle =
            privateText(variant.rowTitleIntentId);
        const MajestyStringView* variantText =
            privateText(variant.rowTextIntentId);
        if ((variant.rowTitleIntentId != 0 && variantTitle == nullptr) ||
            (variant.rowTextIntentId != 0 && variantText == nullptr) ||
            invalidText(variantTitle) || invalidText(variantText)) {
            FaultQuestBoardPresentation(
                value,
                "Live-agent-list rows disabled: manager-owned variant text is missing or invalid.");
            return;
        }
    }
    for (std::size_t index = 0; index < count; ++index) {
        const std::uint32_t row = static_cast<std::uint32_t>(index + 1);
        void* rowAgent = nullptr;
        std::uint32_t recordKey = 0;
        if (board->dataRecordRows) {
            if (!QueryQuestBoard(board->rowAgentIdCallbackSymbol.c_str(), parent, row,
                                 &recordKey, false) || recordKey == 0 || recordKey > 0x7FFFFFFFu) {
                FaultQuestBoardPresentation(value, "Data-record list disabled: row keys must be positive signed integers.");
                return;
            }
        } else if (!QueryQuestBoardAgent(
                board->rowAgentIdCallbackSymbol.c_str(), parent, row,
                &rowAgent, false)) {
            QueryQuestBoardAgent(
                board->rowAgentIdCallbackSymbol.c_str(), parent, row,
                &rowAgent, true);
            FaultQuestBoardPresentation(
                value,
                "Live-agent-list rows disabled: a row-agent-ID callback did not resolve to a live agent.");
            return;
        }
        for (std::size_t prior = 0; prior < index; ++prior) {
            if (board->dataRecordRows ? presentations[prior].recordKey == recordKey
                                      : presentations[prior].agent == rowAgent) {
                FaultQuestBoardPresentation(
                    value,
                    "List rows disabled: every row must return a distinct identity.");
                return;
            }
        }
        const MajestyStringView* rowTitleView = titleView;
        const MajestyStringView* rowTextView = textView;
        if (board->hasRowVariants) {
            std::uint32_t selectedVariant = 0;
            if (!QueryQuestBoard(
                    board->rowVariantCallbackSymbol.c_str(), parent, row,
                    &selectedVariant, false) || selectedVariant == 0 ||
                selectedVariant > board->rowVariants.size()) {
                QueryQuestBoard(
                    board->rowVariantCallbackSymbol.c_str(), parent, row,
                    &selectedVariant, true);
                FaultQuestBoardPresentation(
                    value,
                    "Live-agent-list rows disabled: a row-variant callback did not select a declared variant.");
                return;
            }
            const auto& variant = board->rowVariants[selectedVariant - 1];
            rowTitleView = privateText(variant.rowTitleIntentId);
            rowTextView = privateText(variant.rowTextIntentId);
        }
        auto& presentation = presentations[index];
        presentation.agent = rowAgent;
        presentation.recordKey = recordKey;
        if (rowTitleView != nullptr) {
            presentation.name.assign(rowTitleView->data, rowTitleView->length);
        }
        if (rowTextView != nullptr) {
            presentation.detail.assign(rowTextView->data, rowTextView->length);
        }
        presentation.summaryTemplate.assign("\x01" "FFFFFF%s");
        if (rowTextView != nullptr || board->hasRowValue) {
            presentation.summaryTemplate += "\n\x01" "A550AA";
        }
        if (rowTextView != nullptr && !AppendQuestSummaryLiteral(
                &presentation.summaryTemplate,
                rowTextView->data,
                rowTextView->length)) {
            FaultQuestBoardPresentation(
                value,
                "Live-agent-list rows disabled: its row text could not be formatted.");
            return;
        }
        if (board->hasRowValue) {
            std::uint32_t rowValue = 0;
            if (!QueryQuestBoard(
                    board->rowValueCallbackSymbol.c_str(), parent, row,
                    &rowValue, false) || rowValue > 0x7FFFFFFFu) {
                QueryQuestBoard(
                    board->rowValueCallbackSymbol.c_str(), parent, row,
                    &rowValue, true);
                FaultQuestBoardPresentation(
                    value,
                    "Live-agent-list rows disabled: a row-value callback did not return a bounded integer.");
                return;
            }
            char valueText[32] = {};
            std::snprintf(
                valueText, sizeof(valueText), "%lu",
                static_cast<unsigned long>(rowValue));
            if (!presentation.detail.empty()) presentation.detail += "\n";
            presentation.detail += valueText;
            presentation.detail.append(suffixView->data, suffixView->length);
            if (rowTextView != nullptr) presentation.summaryTemplate += "\n";
            presentation.summaryTemplate += "\x01" "FFFF00";
            presentation.summaryTemplate += valueText;
            if (!AppendQuestSummaryLiteral(
                    &presentation.summaryTemplate,
                    suffixView->data,
                    suffixView->length)) {
                FaultQuestBoardPresentation(
                    value,
                    "Live-agent-list rows disabled: its value suffix could not be formatted.");
                return;
            }
        }
        if (presentation.detail.size() > 208 ||
            presentation.summaryTemplate.size() > 320) {
            FaultQuestBoardPresentation(
                value,
                "Live-agent-list rows disabled: a row exceeded the supported display-text bound.");
            return;
        }
        agents[index] = static_cast<std::uint32_t>(
            reinterpret_cast<std::uintptr_t>(rowAgent));
    }
    if (!ReplaceQuestListVector(value, agents, board->dataRecordRows ? 0 : count)) {
        FaultQuestBoardPresentation(
            value,
            "Live-agent-list rows disabled: stock MX05 rejected the replacement agent vector.");
        return;
    }
    for (std::size_t index = 0; index < kMaximumQuestOffers; ++index) {
        g_questOfferPresentations[index] = {};
    }
    g_questOfferPresentationCount = count;
    for (std::size_t index = 0; index < count; ++index) {
        g_questOfferPresentations[index].agent = presentations[index].agent;
        g_questOfferPresentations[index].recordKey = presentations[index].recordKey;
        g_questOfferPresentations[index].name =
            std::move(presentations[index].name);
        g_questOfferPresentations[index].detail =
            std::move(presentations[index].detail);
        g_questOfferPresentations[index].summaryTemplate =
            std::move(presentations[index].summaryTemplate);
        const auto detailLength = static_cast<std::uint32_t>(
            g_questOfferPresentations[index].detail.size());
        if (detailLength != 0) {
            g_questOfferPresentations[index].detailView = {
                g_questOfferPresentations[index].detail.c_str(),
                detailLength, detailLength,
            };
        }
        const auto summaryLength = static_cast<std::uint32_t>(
            g_questOfferPresentations[index].summaryTemplate.size());
        g_questOfferPresentations[index].summaryView = {
            g_questOfferPresentations[index].summaryTemplate.c_str(),
            summaryLength, summaryLength,
        };
    }
    g_activeQuestRevision = static_cast<int>(revision);
    char resultTrace[192] = {};
    std::snprintf(
        resultTrace, sizeof(resultTrace),
        "Live-agent-list population complete: revision=%lu row_count=%lu.",
        static_cast<unsigned long>(revision),
        static_cast<unsigned long>(count));
    WriteLog(resultTrace);
}

ControllerEvent g_stockQuestBoardEvent = nullptr;

void RefreshChangedQuestBoardRevision(void* controller, const QuestBoard* board) {
    if (!IsLiveQuestBoardController(controller, board) ||
        g_activeQuestBoardFaulted) return;

    // Package lists are not stored in Majesty's relation index 2, so their
    // revision cannot emit XSCX. Observe the bounded revision value at a stock
    // event or completed-action boundary, but do not touch any control unless it
    // actually changes. A change is translated into the same slot-14 refresh
    // MX05 performs for XSCX; unchanged high-frequency events are read-only.
    auto* parent = NativePanelContext(
        reinterpret_cast<std::uint32_t>(controller));
    std::uint32_t revision = 0;
    if (parent == nullptr || !QueryQuestBoard(
            board->revisionCallbackSymbol.c_str(), parent, 0, &revision, false)) {
        QueryQuestBoard(
            board->revisionCallbackSymbol.c_str(), parent, 0, &revision, true);
        FaultQuestBoardPresentation(
            reinterpret_cast<std::uint32_t>(controller),
            "Live-agent-list rows disabled: the package revision callback failed at a stock MX05 lifecycle boundary.");
        return;
    }
    if (g_activeQuestRevision == static_cast<int>(revision)) return;
    char revisionTrace[176] = {};
    std::snprintf(
        revisionTrace, sizeof(revisionTrace),
        "Live-agent-list revision changed: previous=%d current=%lu; invoking stock MX05 refresh.",
        g_activeQuestRevision, static_cast<unsigned long>(revision));
    WriteLog(revisionTrace);
    if (g_stockQuestBoardRefresh == nullptr ||
        (board->actionUsesParent &&
         g_stockQuestBoardSharedRefresh == nullptr)) {
        StopUnsafeManagerRuntimeLaunch(
            "A live-agent-list controller lost MX05's native refresh virtual.");
    }
    g_requestedQuestRevision = static_cast<int>(revision);
    g_questBoardPopulationRequested = true;
    // Literal MX05 event dispatch: invoke its live slot 14. The installed
    // private wrapper retains the package's chosen list/presentation policy.
    reinterpret_cast<ControllerSetup>((*static_cast<void***>(controller))[14])(controller);
}

void RefreshQuestBoardAfterAction(const QuestBoard* board, std::uint32_t building) {
    // The action may have closed/replaced the UI or destroyed its parent.
    // Resolve only the currently live controller after dispatch, and require
    // its native parent handle to match this command before reading any GPL.
    auto* controller = reinterpret_cast<void*>(
        static_cast<std::uintptr_t>(InterlockedCompareExchange(&g_childController, 0, 0)));
    if (!IsLiveQuestBoardController(controller, board) || g_activeQuestBoardFaulted) return;
    auto* parent = NativePanelContext(reinterpret_cast<std::uint32_t>(controller));
    if (parent == nullptr || building == 0 ||
        *reinterpret_cast<const std::uint32_t*>(parent + 0x70) != building) return;
    RefreshChangedQuestBoardRevision(controller, board);
}

void __fastcall QuestBoardEvent(
    void* controller, void*, std::uint32_t a1, std::uint32_t a2,
    std::uint32_t a3, std::uint32_t a4) {
    const auto* board = g_activeQuestBoard;
    g_stockQuestBoardEvent(controller, a1, a2, a3, a4);
    if (a3 == 0x09435358u) {
        // XSCX already dispatched stock slot 14; do not refresh it twice.
        return;
    }
    RefreshChangedQuestBoardRevision(controller, board);
}

bool QueryQuestBoardParentActionCost(
    void* controller,
    const QuestBoard* board,
    std::uint32_t* cost,
    bool trace) {
    if (!IsLiveQuestBoardController(controller, board) ||
        !board->actionUsesParent || cost == nullptr) {
        return false;
    }
    auto* parent = NativePanelContext(
        reinterpret_cast<std::uint32_t>(controller));
    return parent != nullptr && QueryQuestBoard(
        board->actionCostCallbackSymbol.c_str(), parent, 0, cost, trace) &&
        *cost <= 0x7FFFFFFFu;
}

bool PresentQuestBoardParentActionStock(
    std::uint32_t controller,
    std::uint32_t cost,
    bool affordable) {
    SendControllerMessage(
        controller, 0x138Bu, 0x0Au, affordable ? 0u : 1u, 0u);
    char price[24] = {};
    std::snprintf(
        price, sizeof(price), "%lu", static_cast<unsigned long>(cost));
    return SetControllerControlText(controller, 0x1F46u, price);
}
using QuestBoardParentActionPresenter = bool (*)(
    std::uint32_t, std::uint32_t, bool);
QuestBoardParentActionPresenter g_questBoardParentActionPresenter =
    &PresentQuestBoardParentActionStock;

void RefreshQuestBoardParentAction(void* controller) {
    const auto* board = g_activeQuestBoard;
    if (board == nullptr || !board->actionUsesParent ||
        g_activeQuestBoardFaulted) {
        return;
    }
    std::uint32_t cost = 0;
    if (!QueryQuestBoardParentActionCost(controller, board, &cost, false)) {
        QueryQuestBoardParentActionCost(controller, board, &cost, true);
        FaultQuestBoardPresentation(
            reinterpret_cast<std::uint32_t>(controller),
            "Live-agent-list parent action disabled: its action-cost callback did not return a bounded integer.");
        return;
    }
    const int gold = StockCurrentPlayerGold();
    if (!g_questBoardParentActionPresenter(
            reinterpret_cast<std::uint32_t>(controller),
            cost,
            gold >= 0 && static_cast<std::uint32_t>(gold) >= cost)) {
        FaultQuestBoardPresentation(
            reinterpret_cast<std::uint32_t>(controller),
            "Live-agent-list parent action disabled: MX05 rejected its stock price presentation.");
    }
}

int __fastcall QuestBoardControl(
    void* controller, void*, std::uint32_t controlId) {
    const auto* board = g_activeQuestBoard;
    if (board != nullptr && board->dataRecordRows && IsLiveQuestBoardController(controller, board)) {
        // MX05's row-click branch calls its Unit-based cost evaluator before
        // the common focus handoff. Never enter it for data rows. Likewise its
        // detail/tabs/selection-transfer commands are native Unit operations.
        if (controlId == 0x1388u || (controlId >= 0x138Cu && controlId <= 0x138Fu) ||
            controlId == 0x1F40u || controlId == 0x1F41u) return 0;
        if (controlId == 0x138Bu && g_activeQuestBoardFaulted) return 0;
    }
    if (controlId != 0x138Bu || board == nullptr ||
        !board->actionUsesParent || g_activeQuestBoardFaulted ||
        !IsLiveQuestBoardController(controller, board)) {
        return g_stockQuestBoardControl(controller, controlId);
    }
    auto* parent = NativePanelContext(
        reinterpret_cast<std::uint32_t>(controller));
    std::uint32_t cost = 0;
    if (parent == nullptr || !QueryQuestBoardParentActionCost(
            controller, board, &cost, false)) {
        QueryQuestBoardParentActionCost(controller, board, &cost, true);
        FaultQuestBoardPresentation(
            reinterpret_cast<std::uint32_t>(controller),
            "Live-agent-list parent action refused: its parent or cost callback is invalid.");
        return 0;
    }
    const int gold = StockCurrentPlayerGold();
    if (gold < 0 || static_cast<std::uint32_t>(gold) < cost) {
        RefreshQuestBoardParentAction(controller);
        return 0;
    }
    const std::uint32_t parentHandle =
        *reinterpret_cast<const std::uint32_t*>(parent + 0x70);
    if (parentHandle == 0) {
        FaultQuestBoardPresentation(
            reinterpret_cast<std::uint32_t>(controller),
            "Live-agent-list parent action refused: its stock parent handle is unavailable.");
        return 0;
    }
    // This is MX05's existing four-word paid-action packet. The package's
    // declared parent action uses the live parent building for both handles;
    // queued validation, debit, callback routing, event refresh, and cleanup
    // remain in the unchanged stock 0x15 executor lifecycle.
    SubmitOccupantAction(
        0x15u, parentHandle, parentHandle, cost);
    if (g_questOfferPresentationCount == 0 ||
        board->stayOnPanelAfterAction) {
        // An empty list has no valid stock world-focus target. The existing
        // non-transition result keeps the child alive for revision refresh.
        return 0;
    }
    return g_stockQuestBoardSharedControl(controller, controlId);
}

bool RefreshDataRecordListStock(void* controller) {
    const auto value = reinterpret_cast<std::uint32_t>(controller);
    void* panel = *reinterpret_cast<void**>(value + 0x24);
    if (panel == nullptr) return false;
    void* dialog = *reinterpret_cast<void**>(static_cast<unsigned char*>(panel)+4);
    if (dialog == nullptr) return false;
    using Find = void* (__thiscall*)(void*, std::uint32_t);
    void* list = reinterpret_cast<Find>(g_imageBase +
        (g_buildProfile == &kPublicBuildProfile ? 0x002524C0 : 0x00267920))(dialog, 0x1388u);
    if (list == nullptr) return false;
    const auto nativeVtable = g_imageBase +
        (g_buildProfile == &kPublicBuildProfile ? 0x0034F76C : 0x00369844);
    if (*reinterpret_cast<std::uintptr_t*>(list) != nativeVtable) return false;
    // Literal CYDialogListboxItem message dispatch. Clear only MX05's
    // Unit-specific callback; its native text painter, scrollbar, mouse and
    // keyboard selection, owned strings, and destruction stay stock.
    SendControllerMessage(value, 0x1388u, 7u, 0u, 0u);
    QuestBoardPopulate(controller, nullptr);
    const int revision = g_activeQuestBoardFaulted ? -2 : g_activeQuestRevision;
    if (g_renderedDataRecordRevision == revision) return true;
    auto send = [list](std::uint32_t message, std::uint32_t first, std::uint32_t second) {
        using Message = std::uint32_t (__thiscall*)(void*, std::uint32_t, std::uint32_t, std::uint32_t);
        return reinterpret_cast<Message>((*static_cast<void***>(list))[0x9C/4])(list, message, first, second);
    };
    const auto oldCount = send(0x18u, 0, 0);
    if (oldCount > kMaximumQuestOffers) return false;
    const auto selected = send(0x22u, 0, 0);
    const auto top = *reinterpret_cast<std::uint32_t*>(static_cast<unsigned char*>(list)+0x64);
    std::uint32_t selectedKey = 0, topKey = 0;
    if (selected < oldCount) send(0x37u, selected, reinterpret_cast<std::uint32_t>(&selectedKey));
    if (top < oldCount) send(0x37u, top, reinterpret_cast<std::uint32_t>(&topKey));
    for (std::uint32_t i = 0; i < oldCount; ++i) send(0x27u, 0, 0);
    if (send(0x18u, 0, 0) != 0) return false;
    // Shared MX05 refresh uses 40 pixels for its detailed non-monster row
    // (public 0x97F49 / beta2 0x98769), not three compact 16-pixel rows.
    // Keep that stock pitch for title/detail/value, with no icon column.
    *reinterpret_cast<int*>(static_cast<unsigned char*>(list)+0x50) = kDataRecordListRowHeight;
    *reinterpret_cast<int*>(static_cast<unsigned char*>(list)+0x58) = 0;
    int selectedIndex = -1, topIndex = 0;
    const auto count = g_activeQuestBoardFaulted ? 0 : g_questOfferPresentationCount;
    for (std::size_t i = 0; i < count; ++i) {
        const auto& row = g_questOfferPresentations[i];
        using Insert = int (__thiscall*)(void*, std::uint32_t, int, int);
        const int index = reinterpret_cast<Insert>((*static_cast<void***>(panel))[0x34/4])(
            panel, 0x1388u, -1, 0);
        if (index < 0 || static_cast<std::size_t>(index) >= kMaximumQuestOffers) return false;
        char text[512] = {};
        std::snprintf(text, sizeof(text), row.summaryTemplate.c_str(), row.name.c_str());
        std::uint32_t nativeString[3] = {};
        using Construct = void* (__thiscall*)(void*, const char*);
        using Destroy = void (__thiscall*)(void*);
        reinterpret_cast<Construct>(g_imageBase+OccupantProfile().stringConstructor)(nativeString, text);
        send(0x60u, index, reinterpret_cast<std::uint32_t>(nativeString));
        reinterpret_cast<Destroy>(g_imageBase+QuestBoardProfile().stringDestructor)(nativeString);
        send(0x25u, index, row.recordKey);
        if (row.recordKey == selectedKey) selectedIndex = index;
        if (row.recordKey == topKey) topIndex = index;
    }
    send(0x1Bu, static_cast<std::uint32_t>(selectedIndex), 0);
    send(0x21u, static_cast<std::uint32_t>(topIndex), 1);
    using Link = void (__thiscall*)(void*, std::uint32_t, std::uint32_t, int, int);
    reinterpret_cast<Link>((*static_cast<void***>(panel))[0x28/4])(panel, 0x1392u, 0x1388u, 1, 0);
    g_renderedDataRecordRevision = revision;
    return true;
}

void __fastcall QuestBoardRefresh(void* controller, void*) {
    const auto* board = g_activeQuestBoard;
    if (board != nullptr && board->dataRecordRows && IsLiveQuestBoardController(controller, board)) {
        if (!RefreshDataRecordListStock(controller)) {
            FaultQuestBoardPresentation(reinterpret_cast<std::uint32_t>(controller),
                "Data-record list disabled: the native text-list operation failed.");
        }
    } else if (board != nullptr && board->actionUsesParent &&
        IsLiveQuestBoardController(controller, board)) {
        // Stock MX05 slot 14 is exactly a shared list refresh followed by its
        // selected-row cost presenter. Parent-scoped actions must not expose
        // a transient row to the package callback, so preserve the first
        // stock half and replace only the incompatible selected-row quote.
        g_stockQuestBoardSharedRefresh(controller);
    } else {
        g_stockQuestBoardRefresh(controller);
    }
    RefreshQuestBoardParentAction(controller);
}

ControllerSetup g_stockQuestBoardSetup = nullptr;
void __fastcall QuestBoardSetup(void* controller, void*) {
    g_stockQuestBoardSetup(controller);
    const auto* board = g_activeQuestBoard;
    if (board != nullptr && board->dataRecordRows && IsLiveQuestBoardController(controller, board)) {
        const auto value = reinterpret_cast<std::uint32_t>(controller);
        // Shared stock setup hides the bottom action when its Unit vector is
        // empty. Independent records deliberately leave that vector empty;
        // the parent-scoped action does not require a selected row.
        SetControllerControlVisible(value, 0x138Bu, true);
        RefreshQuestBoardParentAction(controller);
    }
}

bool InstallQuestBoardChildVtable(std::uint32_t controller) {
    static void* table[15] = {};
    auto*** object = reinterpret_cast<void***>(controller);
    auto** stock = reinterpret_cast<void**>(
        g_imageBase + OccupantProfile().childVtable);
    if (*object != stock) return false;
    if (table[0] == nullptr) {
        std::memcpy(table, stock, sizeof(table));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                table, stock, 15, &g_childController,
                &SecondaryPanelControllerDestroyed, nullptr)) return false;
        g_stockQuestBoardEvent =
            reinterpret_cast<ControllerEvent>(stock[8]);
        g_stockQuestBoardSetup = reinterpret_cast<ControllerSetup>(stock[1]);
        g_stockQuestBoardControl =
            reinterpret_cast<ControllerControl>(stock[3]);
        g_stockQuestBoardPopulate =
            reinterpret_cast<ControllerSetup>(stock[11]);
        g_stockQuestBoardRefresh =
            reinterpret_cast<ControllerSetup>(stock[14]);
        g_stockQuestBoardSharedRefresh = reinterpret_cast<ControllerSetup>(
            g_imageBase + QuestBoardProfile().sharedListRefresh);
        const auto* population =
            reinterpret_cast<const unsigned char*>(stock[11]);
        const auto eraseTarget = RelativeCallTarget(population + 0x3F);
        const auto insertTarget = RelativeCallTarget(population + 0xDF);
        if (eraseTarget < g_imageBase ||
            eraseTarget >= g_imageBase + 0x00400000u ||
            insertTarget < g_imageBase ||
            insertTarget >= g_imageBase + 0x00400000u) return false;
        g_stockQuestVectorErase =
            reinterpret_cast<QuestVectorErase>(eraseTarget);
        g_stockQuestVectorInsert =
            reinterpret_cast<QuestVectorInsert>(insertTarget);
        table[1] = reinterpret_cast<void*>(&QuestBoardSetup);
        table[3] = reinterpret_cast<void*>(&QuestBoardControl);
        table[8] = reinterpret_cast<void*>(&QuestBoardEvent);
        table[11] = reinterpret_cast<void*>(&QuestBoardPopulate);
        table[14] = reinterpret_cast<void*>(&QuestBoardRefresh);
    }
    *object = table;
    InterlockedExchange(&g_childController, static_cast<LONG>(controller));
    g_renderedDataRecordRevision = -1;
    return true;
}

struct OccupantParentClass {
    void* table[kAp10VtableEntries];
    void** stock;
    std::size_t entryCount;
};
std::vector<OccupantParentClass*> g_occupantParentClasses;
OccupantParentClass* FindOccupantParentClass(void* controller) {
    auto** table = *static_cast<void***>(controller);
    for (auto* entry : g_occupantParentClasses) {
        if (entry->table == table) return entry;
    }
    return nullptr;
}
void __fastcall OccupantParentSetup(void* controller, void*) {
    auto* entry = FindOccupantParentClass(controller);
    if (entry == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "Private generic parent lost its stock setup class.");
    }
    reinterpret_cast<ControllerSetup>(entry->stock[1])(controller);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}
int __fastcall OccupantParentControl(void* controller, void*, std::uint32_t command) {
    int openResult = 0;
    if (HandleBuildingOpenToggle(controller, command, &openResult)) return openResult;
    if (OpenOccupantPanel(controller, command, &openResult)) return openResult;
    if (OpenQuestBoardPanel(controller, command, &openResult)) return openResult;
    auto* entry = FindOccupantParentClass(controller);
    if (entry != nullptr) {
        const int result = reinterpret_cast<ControllerControl>(
            entry->stock[3])(controller, command);
        RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
        return result;
    }
    StopUnsafeManagerRuntimeLaunch("Private occupant parent lost its stock controller class.");
}
void __fastcall OccupantParentEvent(
    void* controller, void*, std::uint32_t a1, std::uint32_t a2,
    std::uint32_t a3, std::uint32_t a4) {
    auto* entry = FindOccupantParentClass(controller);
    if (entry == nullptr) {
        StopUnsafeManagerRuntimeLaunch(
            "Private generic parent lost its stock event class.");
    }
    reinterpret_cast<ControllerEvent>(entry->stock[8])(
        controller, a1, a2, a3, a4);
    RefreshBuildingOpenToggle(reinterpret_cast<std::uint32_t>(controller));
}
bool InstallOccupantParentVtable(std::uint32_t controller) {
    auto*** object = reinterpret_cast<void***>(controller);
    for (const auto* entry : g_occupantParentClasses) {
        if (entry->stock == *object) { *object = const_cast<void**>(entry->table); return true; }
    }
    auto* entry = new OccupantParentClass();
    entry->stock = *object;
    const std::uint32_t declaredBase = g_parentQuestBoard != nullptr
        ? g_parentQuestBoard->parentControllerBase
        : g_parentOccupantPanel != nullptr
            ? g_parentOccupantPanel->parentControllerBase
            : g_parentOpenToggleRecord != nullptr
                ? g_parentOpenToggleRecord->parentControllerBase
                : 0;
    const auto* catalogRecord =
        MajestyStockBuildingControllers::Find(declaredBase);
    const auto* catalogProfile = MajestyStockBuildingControllers::Profile(
        catalogRecord, g_buildProfile != &kPublicBuildProfile);
    if (catalogProfile == nullptr ||
        catalogProfile->entryCount > kAp10VtableEntries ||
        entry->stock != reinterpret_cast<void**>(
            g_imageBase + catalogProfile->vtableRva)) {
        delete entry;
        return false;
    }
    entry->entryCount = catalogProfile->entryCount;
    std::memcpy(
        entry->table, entry->stock, entry->entryCount * sizeof(void*));
    if (!MajestyControllerLifecycle::RegisterManagedVtable(entry->table, entry->stock,
            entry->entryCount, &g_parentController,
            &ParentPanelControllerDestroyed, nullptr)) {
        delete entry;
        return false;
    }
    entry->table[1] = reinterpret_cast<void*>(&OccupantParentSetup);
    entry->table[3] = reinterpret_cast<void*>(&OccupantParentControl);
    entry->table[8] = reinterpret_cast<void*>(&OccupantParentEvent);
    g_occupantParentClasses.push_back(entry);
    *object = entry->table;
    return true;
}
bool InstallOccupantChildVtable(std::uint32_t controller) {
    // Exactly 15 entries, ending at MX05's shared list refresh slot +0x38.
    // All setup, selection, drawing, events, Back, and vector cleanup are native.
    static void* table[15] = {};
    auto*** object = reinterpret_cast<void***>(controller);
    auto** stock = reinterpret_cast<void**>(g_imageBase + OccupantProfile().childVtable);
    if (*object != stock) return false;
    if (table[0] == nullptr) {
        std::memcpy(table, stock, sizeof(table));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(table, stock, 15,
                &g_childController, &SecondaryPanelControllerDestroyed, nullptr)) return false;
    }
    *object = table;
    InterlockedExchange(&g_childController, static_cast<LONG>(controller));
    return true;
}

bool InstallRewardPanelControllerVtable(std::uint32_t controller) {
    auto*** objectVtable = reinterpret_cast<void***>(controller);
    auto** stockVtable = *objectVtable;
    if (g_stockRewardPanelActivation == nullptr) {
        std::memcpy(g_rewardPanelVtable, stockVtable, sizeof(g_rewardPanelVtable));
        if (!MajestyControllerLifecycle::RegisterManagedVtable(
                g_rewardPanelVtable,
                stockVtable,
                kAp69VtableEntries,
                &g_childController,
                &SecondaryPanelControllerDestroyed,
                nullptr)) {
            WriteLog(
                "Refused the private reward panel because its stock destructor could not be registered safely.");
            return false;
        }
        g_stockRewardPanelActivation =
            reinterpret_cast<RewardControllerActivation>(stockVtable[1]);
        g_stockRewardPanelControl =
            reinterpret_cast<RewardControllerControl>(stockVtable[3]);
        g_stockRewardPanelRefresh =
            reinterpret_cast<RewardControllerRefresh>(stockVtable[8]);
        g_rewardPanelVtable[1] = reinterpret_cast<void*>(&RewardPanelActivation);
        g_rewardPanelVtable[3] = reinterpret_cast<void*>(&RewardPanelControl);
        g_rewardPanelVtable[8] = reinterpret_cast<void*>(&RewardPanelRefresh);
    }
    *objectVtable = g_rewardPanelVtable;
    InterlockedExchange(&g_childController, static_cast<LONG>(controller));
    return true;
}

bool PrepareRewardFlagRuntimeRecords() {
    g_rewardFlagStates.clear();
    g_rewardFlagStates.reserve(g_stockControllerRegistry.hostileMonsterFlags.size());
    constexpr std::size_t kCallbackBytes = 0x1D2;
    constexpr std::size_t kTargetCallOffset = 0xAC;
    constexpr std::size_t kPrototypePointerOffset = 0xD1;
    constexpr std::size_t kCallOffsets[] = {
        0x12, 0x19, 0x4F, 0x66, 0x90, 0x9A, 0xAC, 0xBE,
        0xCA, 0xD5, 0x117, 0x143, 0x163, 0x17C, 0x189, 0x196,
    };
    auto* source = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->stockCaptureCallbackRva);
    if (std::memcmp(
            source + 0xCF,
            g_buildProfile->expectedStockCallbackCreate,
            sizeof(g_buildProfile->expectedStockCallbackCreate)) != 0) {
        WriteLog("Private reward callback refused: stock Fl00 completion bytes changed.");
        return false;
    }
    for (const auto& record : g_stockControllerRegistry.hostileMonsterFlags) {
        auto* callback = reinterpret_cast<unsigned char*>(VirtualAlloc(
            nullptr, kCallbackBytes, MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE));
        if (callback == nullptr) return false;
        std::memcpy(callback, source, kCallbackBytes);
        for (const auto offset : kCallOffsets) {
            if (callback[offset] != 0xE8) return false;
            std::int32_t originalRelative = 0;
            std::memcpy(&originalRelative, source + offset + 1, sizeof(originalRelative));
            const auto originalTarget = reinterpret_cast<std::uintptr_t>(source) +
                offset + 5 + originalRelative;
            const auto target = offset == kTargetCallOffset
                ? reinterpret_cast<std::uintptr_t>(&PrivateRewardCompletionTargetCheck)
                : originalTarget;
            const auto relocated = static_cast<std::int32_t>(
                target - (reinterpret_cast<std::uintptr_t>(callback) + offset + 5));
            std::memcpy(callback + offset + 1, &relocated, sizeof(relocated));
        }
        const auto prototype = reinterpret_cast<std::uintptr_t>(
            record.flagPrototypeName.c_str());
        std::memcpy(
            callback + kPrototypePointerOffset,
            &prototype,
            sizeof(std::uint32_t));
        FlushInstructionCache(GetCurrentProcess(), callback, kCallbackBytes);
        g_rewardFlagStates.push_back(
            {&record, nullptr, callback, nullptr, -1, nullptr, -999, -999});
    }
    return g_rewardFlagStates.size() ==
        g_stockControllerRegistry.hostileMonsterFlags.size();
}

extern "C" void __stdcall RegisterPrivateRewardFlagModes() {
    using OperatorNew = void* (__cdecl*)(std::size_t);
    using FlagModeConstructor = void* (__thiscall*)(
        void*, std::uint32_t, int, int, int, void*, void*, int, int);
    using GetRegistry = void* (__cdecl*)();
    using InsertMode = void (__thiscall*)(void*, void*);
    auto allocate = reinterpret_cast<OperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    auto construct = reinterpret_cast<FlagModeConstructor>(
        g_imageBase + g_buildProfile->flagModeConstructorRva);
    auto getRegistry = reinterpret_cast<GetRegistry>(
        g_imageBase + g_buildProfile->getFlagModeRegistryRva);
    for (auto& state : g_rewardFlagStates) {
        // The stock Fl00 registration allocates exactly 0x20 bytes. The old
        // standalone patch's unrelated 0x22 stack-state marker was once
        // mistaken for this size; keep the manager clone literal here.
        void* mode = allocate(0x20);
        if (mode == nullptr) {
            StopUnsafeManagerRuntimeLaunch(
                "Private reward flag mode allocation failed at stock registry completion.");
        }
        void* constructed = construct(
            mode,
            state.record->privateMode,
            static_cast<int>(state.record->cursorOrdinal),
            2,
            1,
            reinterpret_cast<void*>(&PrivateRewardTargetValidator),
            state.completionCallback,
            0,
            0);
        if (constructed != mode) {
            StopUnsafeManagerRuntimeLaunch(
                "Private reward flag mode did not preserve the stock constructor identity.");
        }
        state.modeObject = mode;
        void* registry = getRegistry();
        auto** vtable = *reinterpret_cast<void***>(registry);
        auto insert = reinterpret_cast<InsertMode>(vtable[25]);
        insert(registry, state.modeObject);

        void* registered = FindRegisteredRewardMode(state.record->privateMode);
        if (registered != state.modeObject) {
            StopUnsafeManagerRuntimeLaunch(
                "Private reward mode registry did not return the exact stock-constructed object after insertion.");
        }
        const auto registeredCursor =
            *reinterpret_cast<const std::uint32_t*>(
                static_cast<const unsigned char*>(registered) + 4);
        if (registeredCursor != state.record->cursorOrdinal) {
            StopUnsafeManagerRuntimeLaunch(
                "Private reward mode registry changed the declared CUR1 selector after insertion.");
        }

        char trace[256] = {};
        std::snprintf(
            trace,
            sizeof(trace),
            "Registered private reward mode 0x%08lX with CUR1 selector %lu through the stock Fl00 registry lifecycle.",
            static_cast<unsigned long>(state.record->privateMode),
            static_cast<unsigned long>(state.record->cursorOrdinal));
        WriteLog(trace);
    }
}

__declspec(naked) void RewardModeRegistryHook() {
    __asm {
        pushfd
        pushad
        call RegisterPrivateRewardFlagModes
        popad
        popfd
        mov ecx, dword ptr [esp + 10h]
        mov dword ptr fs:[0], ecx
        jmp dword ptr [g_modeRegistryResume]
    }
}

bool InstallPrivateRewardFlagModeRegistry() {
    auto* site = reinterpret_cast<unsigned char*>(
        g_imageBase + g_buildProfile->modeRegistryCompletionRva);
    if (std::memcmp(
            site,
            g_buildProfile->expectedModeRegistryCompletion,
            sizeof(g_buildProfile->expectedModeRegistryCompletion)) != 0) {
        WriteLog("Private reward mode registry refused: stock completion bytes changed.");
        return false;
    }
    g_modeRegistryResume = g_imageBase + g_buildProfile->modeRegistryResumeRva;
    unsigned char patch[11] = {0xE9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90};
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&RewardModeRegistryHook) -
        (reinterpret_cast<std::uintptr_t>(site) + 5));
    std::memcpy(patch + 1, &relative, sizeof(relative));
    DWORD oldProtection = 0;
    if (!VirtualProtect(site, sizeof(patch), PAGE_EXECUTE_READWRITE, &oldProtection)) {
        return false;
    }
    std::memcpy(site, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), site, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(site, sizeof(patch), oldProtection, &ignored);
    LogInstalledProfileSite(
        "private stock Fl00 mode registry", g_buildProfile->modeRegistryCompletionRva);
    return true;
}

extern "C" void __stdcall CaptureSecondaryController(
    std::uint32_t controller,
    std::uint32_t creationHandle) {
    if (controller == 0) {
        if (InterlockedExchange(&g_captureParentController, 0) == 1) {
            StopUnsafeManagerRuntimeLaunch(
                "A resolved parent dialog returned no stock controller at its creation boundary.");
        }
        if (InterlockedExchange(&g_captureChildController, 0) == 1) {
            ClearSecondaryPanelControllerOwnedState();
            StopUnsafeManagerRuntimeLaunch(
                "A resolved secondary dialog returned no stock controller at its creation boundary.");
        }
        return;
    }
    if (InterlockedExchange(&g_captureParentController, 0) == 1) {
        InterlockedExchange(&g_parentController, static_cast<LONG>(controller));
        const bool installed = g_parentRewardPanelRecord != nullptr
            ? InstallRewardParentControllerVtable(controller)
            : g_parentPanelRecord != nullptr
                ? InstallParentPanelControllerVtable(controller)
                : InstallOccupantParentVtable(controller);
        if (!installed) {
            InterlockedCompareExchange(
                &g_parentController, 0, static_cast<LONG>(controller));
            StopUnsafeManagerRuntimeLaunch(
                "A resolved parent controller could not install its stock-lifecycle vtable clone.");
        }
        // The factory result hook runs after the stock controller's initial
        // setup presenter. The proven MX22 toggle can be initialized here
        // because it reads only native building state. Package GPL callbacks
        // are deferred to the installed stock AP08 event lifecycle, after the
        // controller has been inserted and is live.
        RefreshBuildingOpenToggle(controller);
        WriteLog(
            "Captured a manager parent and installed its declared stock-class command guard.");
        return;
    }
    if (InterlockedExchange(&g_captureChildController, 0) == 1) {
        InterlockedExchange(
            &g_secondaryPanelHandle, static_cast<LONG>(creationHandle));
        const bool installed = g_activeQuestBoard != nullptr
            ? InstallQuestBoardChildVtable(controller)
            : g_activeOccupantPanel != nullptr
            ? InstallOccupantChildVtable(controller)
            : g_activeRewardPanelRecord != nullptr
            ? InstallRewardPanelControllerVtable(controller)
            : InstallSecondaryPanelControllerVtable(controller);
        if (!installed) {
            ClearSecondaryPanelControllerOwnedState();
            StopUnsafeManagerRuntimeLaunch(
                "A resolved secondary controller could not install its stock-lifecycle vtable clone.");
        }
        WriteLog("Captured a manager secondary controller and installed its scoped vtable.");
    }
}

void DismissSecondaryPanel() {
    const auto handle = static_cast<std::uint32_t>(
        InterlockedExchange(&g_secondaryPanelHandle, 0));
    InterlockedExchange(&g_childController, 0);
    ClearSecondaryPanelControllerOwnedState();
    g_activeRewardPanelRecord = nullptr;
    g_activeRewardFlagState = nullptr;
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
        WriteLog("Dismissed the manager secondary panel through Majesty's native dialog-removal API.");
    }
}

LRESULT CALLBACK RuntimeWindowProcedure(
    HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    const LRESULT result = CallWindowProcA(
        g_originalWindowProcedure, window, message, wParam, lParam);
    if (message == WM_RBUTTONDOWN && static_cast<short>(LOWORD(lParam)) >= kSidebarWidth) {
        g_pendingSovereignAction = nullptr;
        InterlockedExchange(&g_pendingSovereignBuilding, 0);
        DismissSecondaryPanel();
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
    if (g_stockControllerRegistry.FindLiveAgentListByChild(requested) != nullptr) {
        *idAddress = kMx05DialogId;
        LogDialogFactoryRequest(
            idAddress, requested,
            " Mapped private live-agent list to stock MX05.");
        return;
    }
    const auto* questParent =
        g_stockControllerRegistry.FindLiveAgentListByParent(requested);
    if (questParent != nullptr) {
        *idAddress = questParent->parentControllerBase;
        LogDialogFactoryRequest(
            idAddress, requested,
            " Preserved declared stock live-agent-list parent controller.");
        return;
    }
    if (g_stockControllerRegistry.FindOccupantPanelByChild(requested) != nullptr) {
        *idAddress = kMx05DialogId;
        LogDialogFactoryRequest(idAddress, requested, " Mapped private occupant panel to stock MX05.");
        return;
    }
    const auto* occupantParent = g_stockControllerRegistry.FindOccupantPanelByParent(requested);
    if (occupantParent != nullptr) {
        *idAddress = occupantParent->parentControllerBase;
        LogDialogFactoryRequest(idAddress, requested, " Preserved declared stock occupant-parent controller.");
        return;
    }
    const auto* toggleParent =
        g_stockControllerRegistry.FindBuildingOpenToggleByParent(requested);
    if (toggleParent != nullptr) {
        *idAddress = toggleParent->parentControllerBase;
        LogDialogFactoryRequest(
            idAddress, requested,
            " Preserved declared stock building-toggle parent controller.");
        return;
    }
    const auto* requestedRewardParent =
        g_stockControllerRegistry.FindRewardPanelByParentDialog(requested);
    if (requestedRewardParent != nullptr) {
        *idAddress = kMx09DialogId;
        LogDialogFactoryRequest(
            idAddress,
            requested,
            " Mapped a resolved reward parent dialog to stock MX09.");
        return;
    }
    const auto* requestedRewardChild =
        g_stockControllerRegistry.FindRewardPanelByChildDialog(requested);
    if (requestedRewardChild != nullptr) {
        *idAddress = kAp41DialogId;
        LogDialogFactoryRequest(
            idAddress,
            requested,
            " Mapped a resolved reward child dialog to stock AP41.");
        return;
    }
    const auto* requestedChild =
        g_stockControllerRegistry.FindPanelByChildDialog(requested);
    if (requestedChild != nullptr) {
        *idAddress = kAp69DialogId;
        LogDialogFactoryRequest(
            idAddress,
            requested,
            " Mapped a resolved child dialog to the stock AP69 controller class.");
        return;
    }
    if (requested == kAp10DialogId && idAddress[2] != 0) {
        InterlockedExchange(
            &g_ap10ControllerContext, static_cast<LONG>(idAddress[2]));
        InterlockedExchange(&g_secondaryPanelArmed, 0);
        LogDialogFactoryRequest(
            idAddress, requested, " Captured AP10 controller context.");
        return;
    }
    if (g_stockControllerRegistry.FindPanelByParentDialog(requested) != nullptr ||
        g_stockControllerRegistry.FindRewardPanelByParentDialog(requested) != nullptr ||
        g_stockControllerRegistry.FindLiveAgentListByParent(requested) != nullptr ||
        g_stockControllerRegistry.FindBuildingOpenToggleByParent(requested) != nullptr) {
        LogDialogFactoryRequest(idAddress, requested);
        return;
    }
    if (requested == 0 && InterlockedCompareExchange(&g_secondaryPanelArmed, 0, 1) == 1) {
        const auto parentContext = idAddress[2] != 0
            ? idAddress[2]
            : reinterpret_cast<std::uint32_t>(NativePanelContext(
                  static_cast<std::uint32_t>(InterlockedCompareExchange(
                      &g_parentController, 0, 0))));
        if (parentContext == 0 || g_parentPanelRecord == nullptr) {
            LogDialogFactoryRequest(
                idAddress, requested,
                " Resolved parent context unavailable; left request unmapped.");
            return;
        }
        *idAddress = kAp69DialogId;
        idAddress[2] = parentContext;
        LogDialogFactoryRequest(
            idAddress, requested,
            " Translated the armed secondary request to AP69 with its parent context.");
        return;
    }
    if (InterlockedExchange(&g_secondaryPanelArmed, 0) == 1) {
        LogDialogFactoryRequest(
            idAddress, requested, " Disarmed the secondary mapping on an intervening request.");
        return;
    }
    LogDialogFactoryRequest(idAddress, requested);
}

extern "C" void __stdcall ResolveDialogCreationRequest(std::uint32_t* arguments) {
    std::uint32_t requested = arguments[0];
    char trace[224] = {};
    sprintf_s(
        trace,
        "Dialog creation entry: id=0x%08X context=0x%08X owner=0x%08X arg4=0x%08X.",
        arguments[0], arguments[1], arguments[2], arguments[3]);
    WriteLog(trace);

    // Privatize only the armed AP10 opener's request. The stock opener already
    // owns the correct building context and the keep/remove-parent decision.
    const bool armed = InterlockedExchange(&g_secondaryPanelArmed, 0) == 1;
    if (requested == 0 && armed && g_parentPanelRecord != nullptr) {
        void* context = arguments[1] != 0
            ? reinterpret_cast<void*>(arguments[1])
            : NativePanelContext(static_cast<std::uint32_t>(
                  InterlockedCompareExchange(&g_parentController, 0, 0)));
        if (context != nullptr) {
            requested = arguments[0] = g_parentPanelRecord->childDialogId;
            arguments[1] = reinterpret_cast<std::uint32_t>(context);
            WriteLog("Creation entry translated a parent command to its resolved child dialog.");
        }
    }

    const auto* requestedChild = g_stockControllerRegistry.FindPanelByChildDialog(requested);
    const auto* rewardChild = g_stockControllerRegistry.FindRewardPanelByChildDialog(requested);
    const auto* occupantChild = g_stockControllerRegistry.FindOccupantPanelByChild(requested);
    const auto* questChild = g_stockControllerRegistry.FindLiveAgentListByChild(requested);
    if (requestedChild != nullptr || rewardChild != nullptr ||
        occupantChild != nullptr || questChild != nullptr) {
        // A new private child takes the tracked child slot. An older child's
        // delayed destructor cannot clear this new mapping (exact-instance
        // lifecycle guard). The parent slot is independent.
        InterlockedExchange(&g_childController, 0);
        ClearSecondaryPanelControllerOwnedState();
        g_activePanelRecord = requestedChild;
        g_activeRewardPanelRecord = rewardChild;
        g_activeRewardFlagState = rewardChild == nullptr
            ? nullptr : FindRewardStateByPanel(rewardChild->panelKey);
        g_activeOccupantPanel = occupantChild;
        g_activeQuestBoard = questChild;
        g_activeQuestBoardFaulted = false;
        g_activeQuestRevision = -1;
        g_requestedQuestRevision = -1;
        g_questBoardPopulationRequested = false;
        InterlockedExchange(&g_secondaryPanelActive, 1);
        InterlockedExchange(&g_captureChildController, 1);
        return;
    }

    const auto* requestedParent = g_stockControllerRegistry.FindPanelByParentDialog(requested);
    const auto* rewardParent = g_stockControllerRegistry.FindRewardPanelByParentDialog(requested);
    const auto* occupantParent = g_stockControllerRegistry.FindOccupantPanelByParent(requested);
    const auto* questParent = g_stockControllerRegistry.FindLiveAgentListByParent(requested);
    const auto* toggleParent =
        g_stockControllerRegistry.FindBuildingOpenToggleByParent(requested);
    if (requestedParent != nullptr || rewardParent != nullptr ||
        occupantParent != nullptr || questParent != nullptr ||
        toggleParent != nullptr) {
        // Only a parent creation changes parent recipes. AP91 Visitors, member
        // lists, and auxiliary notices must not erase a surviving parent's
        // occupant/reward/research openers.
        g_parentPanelRecord = requestedParent;
        g_parentRewardPanelRecord = rewardParent;
        g_parentOccupantPanel = occupantParent;
        g_parentQuestBoard = questParent;
        g_parentOpenToggleRecord = toggleParent;
        InterlockedExchange(&g_captureParentController, 1);
        WriteLog("Creation entry captured a resolved parent dialog.");
        return;
    }

    if (requested == kAp10DialogId && arguments[1] != 0) {
        InterlockedExchange(&g_ap10ControllerContext, static_cast<LONG>(arguments[1]));
        WriteLog("Creation entry captured AP10 context before setup-object construction.");
    }
    // A creation request is not destruction evidence: native layout may leave
    // another panel alive. Stock removal callbacks retire its mapping only when
    // that exact controller is actually removed. AP69 Back is handled at its
    // own command boundary, never by rewriting unrelated AP10 requests.
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
// Preserve that entire switch and row builder: manager-validated private
// overlays alias the existing XR01 row, then substitute their validated text
// at XR01's unchanged stock string-assignment call.
extern "C" void __stdcall SelectPrivateEnchantmentRow(
    std::uint32_t overlayId) {
    g_privateEnchantmentRowString = nullptr;
    const auto* row =
        g_runtimeFeatureRegistry.FindEnchantmentRow(overlayId);
    if (row == nullptr || g_runtimeFeatureRegistry.enchantmentRows.empty()) {
        return;
    }
    const std::size_t index = static_cast<std::size_t>(
        row - g_runtimeFeatureRegistry.enchantmentRows.data());
    if (index < g_runtimeEnchantmentViews.size()) {
        g_privateEnchantmentRowString = &g_runtimeEnchantmentViews[index];
    }
}

__declspec(naked) void HeroEnchantmentsSwitchHook() {
    __asm {
        mov dword ptr [g_privateEnchantmentRowString], 0
        pushfd
        pushad
        push eax
        call SelectPrivateEnchantmentRow
        popad
        popfd
        cmp dword ptr [g_privateEnchantmentRowString], 0
        je replay_stock_compare
        mov eax, 31305258h
    replay_stock_compare:
        cmp eax, 32425243h
        jmp dword ptr [g_heroEnchantmentsSwitchResume]
    }
}

__declspec(naked) void PrivateEnchantmentRowStringHook() {
    __asm {
        mov eax, dword ptr [g_privateEnchantmentRowString]
        test eax, eax
        jz stock_string
        mov dword ptr [esp + 4], eax
    stock_string:
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
    char message[192] = {};
    sprintf_s(
        message,
        "Installed scoped AP78 presenter for %u manager-validated enchantment rows.",
        static_cast<unsigned int>(
            g_runtimeFeatureRegistry.enchantmentRows.size()));
    WriteLog(message);
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

bool RegisterPrivateStockNameGenerator(
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
        return false;
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
        return false;
    }

    std::uint32_t privateKey = generatorId;
    void** privateSlot = findOrInsert(map, &privateKey);
    if (privateSlot == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: the stock map returned no value slot.");
        return false;
    }
    if (*privateSlot != nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "refused: another generator already owns that ID.");
        return false;
    }

    using StockOperatorNew = void* (__cdecl*)(std::size_t);
    auto stockOperatorNew = reinterpret_cast<StockOperatorNew>(
        g_imageBase + g_buildProfile->stockOperatorNewRva);
    auto* wrapper = static_cast<void**>(stockOperatorNew(8));
    if (wrapper == nullptr) {
        WritePrivateNameGeneratorLog(
            generatorLabel,
            "failed: the stock allocator returned null.");
        return false;
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
        return false;
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
    return true;
}

extern "C" void __stdcall RegisterRequestedPrivateNameGenerators(
    void* registry,
    void* resourceManager) {
    for (const auto& record : g_runtimeFeatureRegistry.nameGenerators) {
        char generatorLabel[5] = {
            static_cast<char>(record.generatorId & 0xFFu),
            static_cast<char>((record.generatorId >> 8) & 0xFFu),
            static_cast<char>((record.generatorId >> 16) & 0xFFu),
            static_cast<char>((record.generatorId >> 24) & 0xFFu),
            '\0'};
        if (!RegisterPrivateStockNameGenerator(
            registry,
            resourceManager,
            record.generatorId,
            record.namePartIds[0],
            record.namePartIds[1],
            record.namePartIds[2],
            record.namePartIds[3],
            generatorLabel)) {
            StopUnsafeManagerRuntimeLaunch(
                "A requested private name generator could not be registered at the stock registry-completion boundary.");
        }
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
        "pre-insertion manager secondary-controller hook",
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
    const RuntimeFeatureRegistryState runtimeFeatures =
        LoadRuntimeFeatureRegistry();
    if (runtimeFeatures != RuntimeFeatureRegistryState::Loaded) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the manager-owned runtime feature registry is missing or invalid.");
    }
    const StockControllerRegistryState controllerRecipes =
        LoadStockControllerRegistry();
    if (controllerRecipes != StockControllerRegistryState::Loaded) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the manager-owned stock-controller registry is missing or invalid.");
    }
    const bool managerLaunch = true;
    const bool privateActivityText = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kPrivateActivityText);
    const bool privateQuestRows =
        !g_stockControllerRegistry.liveAgentLists.empty();
    const bool privateIntentResolver =
        privateActivityText || privateQuestRows;
    const bool freestyleCam = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kFreestyleCamRebind);
    const bool expandedBuildingSlots = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kExpandedBuildingSlots);
    const bool privateNameGenerators =
        !g_runtimeFeatureRegistry.nameGenerators.empty();
    const bool stockControllerRecipes =
        !g_stockControllerRegistry.panels.empty() ||
        !g_stockControllerRegistry.occupantActionPanels.empty() ||
        !g_stockControllerRegistry.rewardPanels.empty() ||
        !g_stockControllerRegistry.buildingOpenToggles.empty() ||
        !g_stockControllerRegistry.liveAgentLists.empty();
    const bool ap10Ap69ControllerRecipes =
        !g_stockControllerRegistry.panels.empty();
    const bool privateRewardFlagRecipes =
        !g_stockControllerRegistry.rewardPanels.empty();
    if (!PrepareStockControllerRuntimeRecords()) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: controller runtime records could not be prepared.");
    }
    const bool requestedStockControllerRecipes = HasRuntimeCapability(
        MajestyRuntimeCapabilities::kGenericControllerRecipes);
    const bool privateEnchantmentRows =
        !g_runtimeFeatureRegistry.enchantmentRows.empty();
    const bool requestedNameGeneratorHook =
        HasRuntimeCapability(
            MajestyRuntimeCapabilities::kGenericNameGenerator);
    const bool requestedEnchantmentRowHook =
        HasRuntimeCapability(
            MajestyRuntimeCapabilities::kGenericEnchantmentRow);
    if (requestedNameGeneratorHook != privateNameGenerators ||
        HasRuntimeCapability(MajestyRuntimeCapabilities::kMapFogQuery) != g_runtimeFeatureRegistry.mapFogQuery ||
        HasRuntimeCapability(MajestyRuntimeCapabilities::kMovementQuery) != g_runtimeFeatureRegistry.movementQuery ||
        requestedEnchantmentRowHook != privateEnchantmentRows ||
        requestedStockControllerRecipes != stockControllerRecipes) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: MMCP hook selection and manager-owned runtime registries disagree.");
    }

    if (!SelectMajestyBuildProfile() || !ValidateMajestyBuildProfile()) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: the executable does not match every declared runtime capability profile.");
    }
    if (privateRewardFlagRecipes && !PrepareRewardFlagRuntimeRecords()) {
        StopUnsafeManagerRuntimeLaunch(
            "Terminating manager launch before Majesty resumes: private reward flag callbacks could not be prepared from stock Fl00.");
    }
    if (g_runtimeFeatureRegistry.mapFogQuery || g_runtimeFeatureRegistry.movementQuery) {
        RequireManagerRuntimeInstall(
            InstallMapQueryRuntime(g_imageBase, g_buildProfile == &kPublicBuildProfile,
                g_runtimeFeatureRegistry.mapFogQuery, g_runtimeFeatureRegistry.movementQuery),
            managerLaunch, "The stock GPL read-only query registration boundary did not match its profile.");
    }

    if (privateActivityText) {
        const PrivateIntentRegistryState intentRegistry =
            LoadPrivateIntentRegistry();
        if (intentRegistry != PrivateIntentRegistryState::Loaded) {
            StopUnsafeManagerRuntimeLaunch(
                "Terminating manager launch before Majesty resumes: private activity text was declared without a valid non-empty intent registry.");
        }
    }
    if (privateIntentResolver) {
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

    if (privateIntentResolver) {
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
    if (privateNameGenerators) {
        RequireManagerRuntimeInstall(
            InstallPrivateNameGenerators(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private name registry could not be installed.");
    }

    if (ap10Ap69ControllerRecipes) {
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            ValidateStockResearchRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the stock research route did not match the selected executable profile.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallPrivateResearchDescriptorRegistry(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: private research descriptor registration could not be installed.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallResearchCompletionBridge(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the stock research-completion bridge could not be installed.");
        g_stockResearchRouteReady = RequireManagerRuntimeInstall(
            InstallResearchCompletionNameClone(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private research-completion name clone could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateSpellDescriptorResolver(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private spell descriptor resolver could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateSovereignSpellRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private sovereign route could not be installed.");
        RequireManagerRuntimeInstall(
            InstallPrivateRageRoute(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the private Rage command route could not be installed.");
        RequireManagerRuntimeInstall(
            InstallGameUpdateRefreshBridge(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: the game-update refresh bridge could not be installed.");
    }
    if (stockControllerRecipes) {
        if (!g_stockControllerRegistry.occupantActionPanels.empty() ||
            !g_stockControllerRegistry.liveAgentLists.empty()) {
            RequireManagerRuntimeInstall(InstallOccupantPanelRoute(), managerLaunch,
                "Terminating manager launch: stock occupant action route could not be installed.");
        }
        if (privateQuestRows) {
            RequireManagerRuntimeInstall(
                InstallQuestBoardRowPresentation(), managerLaunch,
                "Terminating manager launch: stock quest-row presentation route could not be installed.");
        }
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
    }
    if (privateRewardFlagRecipes) {
        RequireManagerRuntimeInstall(
            InstallPrivateRewardFlagModeRegistry(),
            managerLaunch,
            "Terminating manager launch before Majesty resumes: private Fl00 modes could not be registered.");
    }
    if (privateEnchantmentRows) {
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
    if (stockControllerRecipes) {
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
