// The actual x86 runtime and destructor dispatcher, with native call boundaries
// stubbed. No game process, window, package, or save file is opened.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cassert>
#include <cstdio>

namespace {
struct Stream { void** table; };
struct Controller {
    void** table;
    unsigned char padding[0x20];
    Stream* stream;
    unsigned char* context;
    unsigned char listPadding[8];
    void* listOwner;
    unsigned char listVectorPadding[8];
    std::uint32_t* listBegin;
    std::uint32_t* listEnd;
};
static_assert(offsetof(Controller, stream) == 0x24, "native stream offset");
static_assert(offsetof(Controller, listOwner) == 0x34, "MX05 list vector offset");
unsigned char contextA[0xA0] = {}, contextB[0xA0] = {};
void* contextTable[74] = {};
void* streamTable[27] = {};
void* playerTable[9] = {};
struct PlayerRecord { void** table; } playerRecord = {playerTable};
void* nativeTable[17] = {};
void* parentTable[17] = {};
void* childTable[17] = {};
Stream stream = {streamTable};
Controller parent = {parentTable, {}, &stream, contextA};
Controller child = {childTable, {}, &stream, contextA};
Controller replacementParent = {parentTable, {}, &stream, contextB};
Controller replacementChild = {childTable, {}, &stream, contextB};
MajestyBuildProfile profile = kBeta2BuildProfile;
DWORD clockValue = 100;
void* seenContext = nullptr;
std::uint32_t seenCommand = 0, seenDialog = 0;
std::uint32_t seenBuilding = 0, seenAgent = 0, seenPrice = 0;
int fallbackCount = 0, submitCount = 0, refreshCount = 0, openCount = 0;
int openResult = 0, deleteCount = 0, hideCount = 0;
int packedValue = 0;
int playerGold = 1000;
int setIntegerCount = 0, questEventCount = 0, questNativeRefreshCount = 0;
int parentEventCount = 0;
int questQueryCount = 0, questRowQueryCount = 0, questTextQueryCount = 0;
int selectedQuestIndex = -1;
std::uint32_t questRevision = 7;
bool questCanRefresh = true;
bool questAgentValid = true;
std::uint32_t questAgents[4] = {101, 202, 303, 0};
std::uint32_t questVectorStorage[8] = {};
std::uint32_t lastMessageControl = 0, lastMessage = 0;
std::uint32_t lastVisibleControl = 0, lastVisibleValue = 0;
std::uint32_t visibleControls[16] = {};
std::uint32_t visibleValues[16] = {};
std::size_t visibleControlCount = 0;
bool affordable = true;
bool reenterParentEventOnSet = false;
int stockQuestNameCount = 0, stockQuestAttributeCount = 0;
void* __fastcall Context(void* object, void*) {
    return static_cast<Controller*>(object)->context;
}
void* __cdecl Manager() { return reinterpret_cast<void*>(1); }
void* __fastcall Player(void*, void*) { return &playerRecord; }
int __fastcall PlayerValue(void*, void*, std::uint32_t field) {
    assert(field == kPlayerGoldDataId);
    return playerGold;
}
void* __fastcall PlayerAgent(void*, void*, std::uint32_t player) {
    assert(player == 7);
    return contextA;
}
int __fastcall ReadAttribute(void*, void*, std::uint32_t attribute, std::uint32_t) {
    if (attribute == kEmbassyActiveFlagAttributeId) return packedValue;
    assert(
        attribute == kCurrentResearchAttributeId ||
        attribute == kResearchStartedAtAttributeId ||
        attribute == kResearchDurationAttributeId);
    return 0;
}
void __fastcall WriteAttribute(void*, void*, std::uint32_t attribute, int value) {
    if (attribute == kEmbassyActiveFlagAttributeId) {
        packedValue = value;
        return;
    }
    assert(
        attribute == kCurrentResearchAttributeId ||
        attribute == kResearchStartedAtAttributeId ||
        attribute == kResearchDurationAttributeId);
}
std::uint32_t __fastcall Send(void*, void*, std::uint32_t control, std::uint32_t message,
                             std::uint32_t, std::uint32_t) {
    lastMessageControl = control; lastMessage = message;
    if (control == kMx05SelectionControlId && message == 0x22u) {
        return static_cast<std::uint32_t>(selectedQuestIndex);
    }
    return 0;
}
void __fastcall SetInteger(
    void*, void*, std::uint32_t, int, std::uint32_t) {
    ++setIntegerCount;
    if (reenterParentEventOnSet) {
        reenterParentEventOnSet = false;
        OccupantParentEvent(&parent, nullptr, 1, 2, 0x06425041u, 4);
    }
}
void __fastcall Visible(void*, void*, std::uint32_t control, std::uint32_t value) {
    if (visibleControlCount < 16) {
        visibleControls[visibleControlCount] = control;
        visibleValues[visibleControlCount++] = value;
    }
    lastVisibleControl = control; lastVisibleValue = value;
}
void __fastcall Hide(void*, void*) { ++hideCount; }
void __cdecl Refresh(void*, void* context, std::uint32_t command) {
    ++refreshCount; seenContext = context; seenCommand = command;
}
bool __fastcall Eligible(void* object, void*, std::uint32_t command) {
    seenContext = Context(object, nullptr); seenCommand = command;
    return affordable;
}
void __cdecl Submit(std::uint32_t owner, void* context, std::uint32_t command) {
    assert(owner == 456); ++submitCount; seenContext = context; seenCommand = command;
}
void __cdecl SubmitBuilding(
    std::uint32_t command, std::uint32_t building,
    std::uint32_t agent, std::uint32_t price) {
    ++submitCount;
    seenCommand = command;
    seenBuilding = building;
    seenAgent = agent;
    seenPrice = price;
}
int __fastcall Fallback(void*, void*, std::uint32_t) { ++fallbackCount; return 23; }
void __fastcall NativeParentEvent(
    void*, void*, std::uint32_t, std::uint32_t,
    std::uint32_t, std::uint32_t) {
    ++parentEventCount;
}
bool QuestScalar(
    const char* symbol, void* owner, bool hasInteger, int integerValue,
    std::uint32_t* result, bool) {
    assert(owner == contextA && result != nullptr);
    ++questQueryCount;
    if (std::strcmp(symbol, "Quest_Revision") == 0) {
        assert(!hasInteger);
        *result = questRevision;
    } else if (std::strcmp(symbol, "Quest_RefreshCost") == 0) {
        assert(!hasInteger);
        *result = 25;
    } else if (std::strcmp(symbol, "Quest_Reward") == 0) {
        assert(hasInteger && integerValue >= 1 && integerValue <= 4);
        *result = static_cast<std::uint32_t>(integerValue * 100);
    } else {
        assert(false);
    }
    return true;
}
bool QuestBoolean(
    const char* symbol, void* owner, bool* result, bool) {
    assert(std::strcmp(symbol, "Quest_CanRefresh") == 0);
    assert(owner == contextA && result != nullptr);
    ++questQueryCount;
    *result = questCanRefresh;
    return true;
}
bool QuestAgent(
    const char* symbol, void* owner, int row, void** result, bool) {
    assert(std::strcmp(symbol, "Quest_At") == 0);
    assert(owner == contextA && result != nullptr && row >= 1 && row <= 4);
    ++questRowQueryCount;
    if (!questAgentValid) return false;
    *result = reinterpret_cast<void*>(questAgents[row - 1]);
    return true;
}
bool QuestString(
    const char* symbol, void* owner, int row, std::string* result, bool) {
    assert(owner == contextA && result != nullptr && row >= 1 && row <= 4);
    ++questTextQueryCount;
    if (std::strcmp(symbol, "Quest_Name") == 0) {
        *result = "Quest " + std::to_string(row);
    } else if (std::strcmp(symbol, "Quest_Goal") == 0) {
        *result = "Complete objective " + std::to_string(row);
    } else {
        assert(false);
    }
    return true;
}
MajestyStringView* __fastcall AssignQuestText(
    MajestyStringView* destination, void*, const MajestyStringView* source) {
    *destination = *source;
    return destination;
}
void* __cdecl StockQuestName(
    MajestyStringView* destination, void*, int) {
    ++stockQuestNameCount;
    return destination;
}
int __fastcall StockQuestAttribute(
    void*, void*, std::uint32_t, std::uint32_t) {
    ++stockQuestAttributeCount;
    return 91;
}
void* __fastcall EraseQuestVector(
    void* vector, void*, void*, void*, std::uint32_t*, void*, std::uint32_t*) {
    auto* bytes = static_cast<unsigned char*>(vector);
    *reinterpret_cast<std::uint32_t**>(bytes + 0x0C) = questVectorStorage;
    *reinterpret_cast<std::uint32_t**>(bytes + 0x10) =
        questVectorStorage + sizeof(questVectorStorage) / sizeof(questVectorStorage[0]);
    return nullptr;
}
void* __fastcall InsertQuestVector(
    void* vector, void*, void*, void*, std::uint32_t*, std::uint32_t* agent) {
    auto* bytes = static_cast<unsigned char*>(vector);
    auto** position = reinterpret_cast<std::uint32_t**>(bytes + 0x0C);
    **position = *agent;
    ++*position;
    return nullptr;
}
void __fastcall NativeQuestRefresh(void* controller, void*) {
    ++questNativeRefreshCount;
    QuestBoardPopulate(controller, nullptr);
}
int __fastcall NativeQuestControl(void*, void*, std::uint32_t) { return 17; }
void __fastcall NativeQuestEvent(
    void* controller, void*, std::uint32_t, std::uint32_t,
    std::uint32_t eventId, std::uint32_t) {
    ++questEventCount;
    if (eventId == 0x09435358u) QuestBoardRefresh(controller, nullptr);
}
void* __fastcall Delete(void* object, void*, std::uint32_t flags) {
    assert(flags == 1); ++deleteCount; return object;
}
int __fastcall Open(void* object, void*, std::uint32_t dialog, std::uint32_t context) {
    assert(object == &parent && context == 0);
    ++openCount; seenDialog = dialog;
    std::uint32_t args[] = {dialog, reinterpret_cast<std::uint32_t>(contextA), 0, 0};
    ResolveDialogCreationRequest(args);
    return openResult;
}
std::uint32_t __fastcall Create(void* manager, void*, std::uint32_t dialog,
                               void* context, std::uint32_t owner, std::uint32_t flags) {
    assert(manager == reinterpret_cast<void*>(1));
    assert(hideCount == 1 && owner == 0 && flags == 0);
    seenDialog = dialog; seenContext = context;
    std::uint32_t args[] = {dialog, reinterpret_cast<std::uint32_t>(context), owner, flags};
    ResolveDialogCreationRequest(args);
    return 123;
}
void Destroy(Controller& object) {
    reinterpret_cast<MajestyControllerLifecycle::StockControllerDestructor>(object.table[0])(&object, 1);
}
void Reset() {
    ClearSecondaryPanelControllerOwnedState();
    g_parentController = g_childController = 0;
    g_captureParentController = g_secondaryPanelArmed = 0;
    g_parentPanelRecord = nullptr;
    g_parentRewardPanelRecord = nullptr;
    g_parentOpenToggleRecord = nullptr;
    g_parentOccupantPanel = nullptr;
    g_parentQuestBoard = nullptr;
    g_activeQuestRefreshCost = -1;
    g_activeQuestRefreshEnabled = -1;
    g_researchOwner = {};
    parent.context = child.context = contextA;
    replacementParent.context = replacementChild.context = contextB;
    fallbackCount = submitCount = refreshCount = openCount = hideCount = 0;
    seenContext = nullptr; seenDialog = seenCommand = 0;
    seenBuilding = seenAgent = seenPrice = 0;
    affordable = true;
    reenterParentEventOnSet = false;
    packedValue = 0; lastMessageControl = lastMessage = 0;
    playerGold = 1000; setIntegerCount = 0;
    questEventCount = questNativeRefreshCount = 0;
    selectedQuestIndex = -1;
    parentEventCount = 0;
    questQueryCount = questRowQueryCount = questTextQueryCount = 0;
    questRevision = 7;
    questCanRefresh = true;
    questAgentValid = true;
    stockQuestNameCount = stockQuestAttributeCount = 0;
    questAgents[0] = 101; questAgents[1] = 202;
    questAgents[2] = 303; questAgents[3] = 0;
    std::memset(questVectorStorage, 0, sizeof(questVectorStorage));
    child.listOwner = &child;
    child.listBegin = questVectorStorage;
    child.listEnd = questVectorStorage +
        sizeof(questVectorStorage) / sizeof(questVectorStorage[0]);
    g_questBoardScalarEvaluator = &QuestScalar;
    g_questBoardBooleanEvaluator = &QuestBoolean;
    g_questBoardAgentEvaluator = &QuestAgent;
    g_questBoardStringEvaluator = &QuestString;
    g_stockQuestVectorErase =
        reinterpret_cast<QuestVectorErase>(&EraseQuestVector);
    g_stockQuestVectorInsert =
        reinterpret_cast<QuestVectorInsert>(&InsertQuestVector);
    g_stockQuestBoardRefresh =
        reinterpret_cast<ControllerSetup>(&NativeQuestRefresh);
    g_stockQuestBoardEvent =
        reinterpret_cast<ControllerEvent>(&NativeQuestEvent);
    lastVisibleControl = lastVisibleValue = 0;
    std::memset(visibleControls, 0, sizeof(visibleControls));
    visibleControlCount = 0;
}
void ResearchPair() {
    Reset();
    g_parentController = reinterpret_cast<LONG>(&parent);
    g_childController = reinterpret_cast<LONG>(&child);
    g_parentPanelRecord = g_activePanelRecord = &g_stockControllerRegistry.panels[0];
    g_secondaryPanelActive = 1;
}
void Initialize() {
    g_imageBase = 0; g_buildProfile = &profile;
    profile.getPanelContextRva = reinterpret_cast<std::uintptr_t>(&Context);
    profile.uiManagerRva = reinterpret_cast<std::uintptr_t>(&Manager);
    profile.getCurrentPlayerRva = reinterpret_cast<std::uintptr_t>(&Player);
    profile.getPlayerAgentRva = reinterpret_cast<std::uintptr_t>(&PlayerAgent);
    profile.readPackedAttributeRva = reinterpret_cast<std::uintptr_t>(&ReadAttribute);
    profile.refreshSingleResearchRowRva = reinterpret_cast<std::uintptr_t>(&Refresh);
    profile.canSubmitResearchRva = reinterpret_cast<std::uintptr_t>(&Eligible);
    profile.submitResearchCommandRva = reinterpret_cast<std::uintptr_t>(&Submit);
    profile.submitBuildingCommandRva =
        reinterpret_cast<std::uintptr_t>(&SubmitBuilding);
    profile.simulationClockRva = reinterpret_cast<std::uintptr_t>(&clockValue);
    profile.openDialogRva = reinterpret_cast<std::uintptr_t>(&Open);
    profile.dialogCreationRva = reinterpret_cast<std::uintptr_t>(&Create);
    contextTable[0x124 / 4] = reinterpret_cast<void*>(&WriteAttribute);
    for (auto* context : {contextA, contextB}) {
        *reinterpret_cast<void***>(context) = contextTable;
        *reinterpret_cast<std::uint32_t*>(context + 0x70) = 123;
        *reinterpret_cast<std::uint32_t*>(context + 0x80) = 7;
        *reinterpret_cast<std::uint32_t*>(context + 0x94) = 456;
    }
    streamTable[0x68 / 4] = reinterpret_cast<void*>(&Send);
    streamTable[0x5C / 4] = reinterpret_cast<void*>(&SetInteger);
    streamTable[0x20 / 4] = reinterpret_cast<void*>(&Visible);
    streamTable[0x14 / 4] = reinterpret_cast<void*>(&Hide);
    nativeTable[0] = reinterpret_cast<void*>(&Delete);
    nativeTable[3] = reinterpret_cast<void*>(&Fallback);
    nativeTable[8] = reinterpret_cast<void*>(&NativeParentEvent);
    playerTable[0x20 / 4] = reinterpret_cast<void*>(&PlayerValue);
    assert(MajestyControllerLifecycle::RegisterManagedVtable(parentTable, nativeTable,
        17, &g_parentController, &ParentPanelControllerDestroyed, nullptr));
    assert(MajestyControllerLifecycle::RegisterManagedVtable(childTable, nativeTable,
        11, &g_childController, &SecondaryPanelControllerDestroyed, nullptr));
    g_stockAp69Control = reinterpret_cast<ControllerControl>(&Fallback);
    g_stockRewardParentControl = reinterpret_cast<RewardControllerControl>(&Fallback);
    g_stockResearchRouteReady = true;
    g_stockControllerRegistry.panels = {{"example", 0x30303042, 0x30303050, 0x30304241, 0x1f49}};
    MajestyStockControllers::ResearchRowRecord row = {};
    row.panelKey = "example"; row.recipeKey = "generic-research"; row.actionControlId = 0x6000;
    g_stockControllerRegistry.researchRows = {row};
    g_stockControllerRegistry.rewardPanels = {{"beacon", 0x31303042, 0x31303050, 0x4100}};
    g_stockControllerRegistry.occupantActionPanels = {
        {"clinic", 0x31303042, 0x32303050, 0x4101, 0x10000, "Clinic_Cost", "Clinic_Action", kMx09DialogId}};
    g_stockControllerRegistry.buildingOpenToggles = {
        {"rentals", 0x31303042, 0x5D01, 0x5D02, kMx09DialogId}};
}
}

int main() {
    Initialize();
    // 1. Single-panel replacement: native deletion of ONLY the parent preserves
    // the child's mapping, command ownership, player lookup, and research path.
    ResearchPair();
    Destroy(parent);
    assert(g_parentController == 0 && g_parentPanelRecord == nullptr);
    assert(g_childController == reinterpret_cast<LONG>(&child));
    assert(g_activePanelRecord == &g_stockControllerRegistry.panels[0]);
    assert(ActivePanelContext() == contextA && StockCurrentPlayerAgent() == contextA);
    SecondaryPanelControllerControl(&child, nullptr, 0x6000);
    assert(submitCount == 1 && fallbackCount == 0 && seenContext == contextA);
    assert(seenCommand == 0x6000 && refreshCount > 0 && g_researchOwner.pending);
    // UI closure is not simulation cancellation.
    Destroy(child);
    assert(g_childController == 0 && g_activePanelRecord == nullptr);
    assert(g_researchOwner.pending && g_researchOwner.context == contextA);

    // 2. Stacked layout: deleting a child leaves the parent opener available.
    ResearchPair();
    Destroy(child);
    assert(g_parentController == reinterpret_cast<LONG>(&parent));
    assert(g_parentPanelRecord == &g_stockControllerRegistry.panels[0]);

    // 3. No parent borrowing: another parent's context must never replace an
    // unresolved child's building, even if that other controller is still live.
    ResearchPair();
    parent.context = contextB;
    assert(ActivePanelContext() == contextA);
    child.context = nullptr;
    assert(ActivePanelContext() == nullptr);
    assert(StockCurrentPlayerAgent() == nullptr);
    SecondaryPanelControllerControl(&child, nullptr, 0x6000);
    assert(submitCount == 0);

    // 4. Native affordability still controls research after single-panel swap.
    ResearchPair(); Destroy(parent); affordable = false;
    SecondaryPanelControllerControl(&child, nullptr, 0x6000);
    assert(submitCount == 0 && refreshCount == 1 && !g_researchOwner.pending);

    // 5. Back clones AP69's hide/create/return-1 sequence using the child's own
    // context and private parent ID. Delayed child teardown preserves new parent.
    ResearchPair(); Destroy(parent);
    assert(SecondaryPanelControllerControl(&child, nullptr, 0x1f4d) == 1);
    assert(hideCount == 1 && seenDialog == g_stockControllerRegistry.panels[0].parentDialogId);
    assert(seenContext == contextA && g_captureParentController == 1);
    g_parentController = reinterpret_cast<LONG>(&replacementParent); // native capture
    Destroy(child);
    assert(g_parentController == reinterpret_cast<LONG>(&replacementParent));
    assert(g_parentPanelRecord == &g_stockControllerRegistry.panels[0]);

    // 6. Foreign AP10 creation is not mistaken for Back. Notices and stock list
    // creations alone are not evidence that the current child was destroyed.
    ResearchPair();
    std::uint32_t args[] = {kAp10DialogId, reinterpret_cast<std::uint32_t>(contextB), 0, 0};
    ResolveDialogCreationRequest(args);
    assert(args[0] == kAp10DialogId && args[1] == reinterpret_cast<std::uint32_t>(contextB));
    assert(g_activePanelRecord != nullptr);
    args[0] = 0x36335041; args[1] = 0; // AP36
    ResolveDialogCreationRequest(args);
    assert(g_activePanelRecord != nullptr);

    // 7. Old destructors cannot erase newly captured controllers/records.
    ResearchPair();
    g_parentController = reinterpret_cast<LONG>(&replacementParent);
    g_childController = reinterpret_cast<LONG>(&replacementChild);
    Destroy(parent); Destroy(child);
    assert(g_parentController == reinterpret_cast<LONG>(&replacementParent));
    assert(g_childController == reinterpret_cast<LONG>(&replacementChild));
    assert(g_activePanelRecord != nullptr && ActivePanelContext() == contextB);
    Destroy(replacementParent); Destroy(replacementChild);
    assert(g_parentController == 0 && g_childController == 0 && g_activePanelRecord == nullptr);

    // 8. Shared reward+occupant parent -> stock Visitors -> custom opener.
    // Generic IDs and callback names, no Zoo or Tame special case.
    const auto* occupant = &g_stockControllerRegistry.occupantActionPanels[0];
    const auto* reward = &g_stockControllerRegistry.rewardPanels[0];
    for (int stockResult : {0, 1}) {
        Reset(); openResult = stockResult;
        args[0] = occupant->parentDialogId; args[1] = reinterpret_cast<std::uint32_t>(contextA);
        ResolveDialogCreationRequest(args);
        g_parentController = reinterpret_cast<LONG>(&parent);
        args[0] = 0x31395041; // AP91 stock Visitors
        ResolveDialogCreationRequest(args);
        assert(g_parentOccupantPanel == occupant && g_parentRewardPanelRecord == reward);
        assert(RewardParentControl(&parent, nullptr, occupant->openCommandId) == stockResult);
        assert(openCount == 1 && seenDialog == occupant->childDialogId && g_activeOccupantPanel == occupant);
        g_childController = reinterpret_cast<LONG>(&child); // native capture
        if (stockResult) Destroy(parent);
        assert(g_activeOccupantPanel == occupant);
        Destroy(child);
        assert(g_activeOccupantPanel == nullptr);
        if (!stockResult) assert(g_parentOccupantPanel == occupant);
    }

    // 9. Other parent wrappers also return the stock layout/removal decision.
    Reset(); openResult = 1; g_parentOccupantPanel = occupant;
    assert(ParentPanelControllerControl(&parent, nullptr, occupant->openCommandId) == 1);
    Reset(); g_parentOccupantPanel = occupant;
    assert(OccupantParentControl(&parent, nullptr, occupant->openCommandId) == 1);
    Reset(); g_parentRewardPanelRecord = reward;
    assert(RewardParentControl(&parent, nullptr, reward->openCommandId) == 1);
    assert(seenDialog == reward->childDialogId && g_activeRewardPanelRecord == reward);
    g_parentController = reinterpret_cast<LONG>(&parent);
    g_childController = reinterpret_cast<LONG>(&child);
    Destroy(parent);
    assert(g_activeRewardPanelRecord == reward);
    Destroy(child);
    assert(g_activeRewardPanelRecord == nullptr);

    // 10. Explicit private child creation can reopen without a surviving parent.
    Reset();
    args[0] = g_stockControllerRegistry.panels[0].childDialogId;
    args[1] = reinterpret_cast<std::uint32_t>(contextA);
    ResolveDialogCreationRequest(args);
    assert(g_activePanelRecord != nullptr && g_captureChildController == 1);

    // 11. MX22's paired-control state is cloned, but its Embassy order is not.
    Reset();
    g_parentOpenToggleRecord = &g_stockControllerRegistry.buildingOpenToggles[0];
    int toggleResult = 99;
    assert(HandleBuildingOpenToggle(&parent, 0x5D01, &toggleResult));
    assert(toggleResult == 0 && packedValue == 1 && submitCount == 0);
    assert(lastVisibleControl == 0x5D02 && lastVisibleValue == 1);
    assert(lastMessageControl == 0x5D02 && lastMessage == 0x0A);
    assert(HandleBuildingOpenToggle(&parent, 0x5D02, &toggleResult));
    assert(packedValue == 0 && lastVisibleControl == 0x5D02 && lastVisibleValue == 0);
    assert(lastMessageControl == 0x5D01 && lastMessage == 0x0A);
    assert(!HandleBuildingOpenToggle(&parent, 0x7777, &toggleResult));

    // 12. The native creation-result hook installs the combined parent vtable
    // after stock setup has already run.  Reward+occupant+toggle parents must
    // receive their first MX22 presentation immediately at that boundary.
    Reset();
    parent.table = nativeTable;
    g_stockRewardParentControl = nullptr;
    g_stockRewardParentSetup = nullptr;
    g_stockRewardParentEvent = nullptr;
    g_parentRewardPanelRecord = reward;
    g_parentOccupantPanel = occupant;
    g_parentOpenToggleRecord = &g_stockControllerRegistry.buildingOpenToggles[0];
    g_captureParentController = 1;
    CaptureSecondaryController(reinterpret_cast<std::uint32_t>(&parent), 0);
    assert(g_captureParentController == 0);
    assert(g_parentController == reinterpret_cast<LONG>(&parent));
    assert(g_parentRewardPanelRecord == reward && g_parentOccupantPanel == occupant);
    assert(lastVisibleControl == 0x5D02 && lastVisibleValue == 0);
    assert(lastMessageControl == 0x5D01 && lastMessage == 0x0A);

    // 13. AP08 is a distinct 13-entry parent class. The quest-board wrapper
    // copies exactly that live table and retains its stock destructor rather
    // than reading four AP10 entries from adjacent string data.
    Reset();
    MajestyStockControllers::QuestBoardRecord quest = {};
    quest.panelKey = "quest-board";
    quest.parentDialogId = 0x31304741;
    quest.childDialogId = 0x31304251;
    quest.openCommandId = 0x7101;
    quest.selectedActionCommandId = 0x20000;
    quest.refreshCommandId = 0x20001;
    quest.refreshControlId = 0x7102;
    quest.refreshPriceBindingId = 0x7103;
    quest.listSourceCallbackSymbol = "Quest_At";
    quest.revisionCallbackSymbol = "Quest_Revision";
    quest.offerNameCallbackSymbol = "Quest_Name";
    quest.offerGoalCallbackSymbol = "Quest_Goal";
    quest.offerRewardCallbackSymbol = "Quest_Reward";
    quest.selectedCostCallbackSymbol = "Quest_SelectedCost";
    quest.selectedActionCallbackSymbol = "Quest_Reject";
    quest.refreshCostCallbackSymbol = "Quest_RefreshCost";
    quest.canRefreshCallbackSymbol = "Quest_CanRefresh";
    quest.refreshCallbackSymbol = "Quest_Refresh";
    quest.parentControllerBase = 0x38305041;
    g_stockControllerRegistry.questBoards = {quest};
    g_parentQuestBoard = &g_stockControllerRegistry.questBoards[0];
    parent.table = nativeTable;
    g_imageBase = reinterpret_cast<std::uintptr_t>(nativeTable) -
        kBeta2QuestBoard.parentVtable;
    profile.getPanelContextRva =
        reinterpret_cast<std::uintptr_t>(&Context) - g_imageBase;
    profile.uiManagerRva =
        reinterpret_cast<std::uintptr_t>(&Manager) - g_imageBase;
    profile.getCurrentPlayerRva =
        reinterpret_cast<std::uintptr_t>(&Player) - g_imageBase;
    profile.submitBuildingCommandRva =
        reinterpret_cast<std::uintptr_t>(&SubmitBuilding) - g_imageBase;
    g_captureParentController = 1;
    CaptureSecondaryController(reinterpret_cast<std::uint32_t>(&parent), 0);
    auto* ap08Clone = FindOccupantParentClass(&parent);
    assert(ap08Clone != nullptr && ap08Clone->stock == nativeTable);
    assert(ap08Clone->entryCount == kAp08VtableEntries);
    // Controller capture is installation only. It must not execute package GPL
    // or write private controls before Majesty inserts the controller.
    assert(parentEventCount == 0 && questQueryCount == 0);
    assert(setIntegerCount == 0 && visibleControlCount == 0);
    assert(g_activeQuestRefreshCost == -1 &&
           g_activeQuestRefreshEnabled == -1);

    // AP08 remains a stock parent with only the child opener. Refresh is not
    // presented, queried, or dispatched from the primary building panel.
    OccupantParentEvent(&parent, nullptr, 1, 2, 3, 4);
    assert(parentEventCount == 1 && questQueryCount == 0 &&
           setIntegerCount == 0 && lastMessageControl == 0);
    OccupantParentEvent(&parent, nullptr, 1, 2, 0x06425041u, 4);
    assert(parentEventCount == 2 && questQueryCount == 0);
    assert(setIntegerCount == 0 && visibleControlCount == 0);
    assert(OccupantParentControl(
               &parent, nullptr, quest.refreshControlId) == 23);
    assert(fallbackCount == 1 && submitCount == 0);
    Destroy(parent);
    assert(g_parentQuestBoard == nullptr && g_parentController == 0);

    // Restore the direct native seams after the synthetic image-base proof.
    g_imageBase = 0;
    profile.getPanelContextRva = reinterpret_cast<std::uintptr_t>(&Context);
    profile.uiManagerRva = reinterpret_cast<std::uintptr_t>(&Manager);
    profile.getCurrentPlayerRva = reinterpret_cast<std::uintptr_t>(&Player);
    profile.submitBuildingCommandRva =
        reinterpret_cast<std::uintptr_t>(&SubmitBuilding);

    // 14. The custom population source replaces only MX05's native vector.
    // Count is derived from contiguous package agents; presentation remains a
    // separate post-stock-refresh boundary.
    g_activeQuestBoard = &g_stockControllerRegistry.questBoards[0];
    g_activeQuestRefreshCost = -1;
    g_activeQuestRefreshEnabled = -1;
    assert(IsQuestBoardAgentCompatibleResultType(kGplAgentResultType));
    assert(IsQuestBoardAgentCompatibleResultType(kGplNullResultType));
    assert(IsQuestBoardAgentCompatibleResultType(kGplIntegerResultType));
    assert(!IsQuestBoardAgentCompatibleResultType(kGplStringResultType));
    g_childController = reinterpret_cast<LONG>(&child);
    lastMessageControl = 0;
    visibleControlCount = 0;
    setIntegerCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(g_activeQuestRevision == 7 && questRowQueryCount == 4);
    assert(questTextQueryCount == 6 && g_questOfferPresentationCount == 3);
    assert(g_questOfferPresentations[1].name == "Quest 2");
    assert(g_questOfferPresentations[1].detail ==
           "Complete objective 2 (200 gold)");
    g_privateIntentStringAssign =
        reinterpret_cast<StockStringAssign>(&AssignQuestText);
    g_stockQuestRowNameFormatter = &StockQuestName;
    g_stockQuestRowAttributeReader =
        reinterpret_cast<StockQuestRowAttributeReader>(&StockQuestAttribute);
    MajestyStringView rowName = {};
    QuestBoardRowNameFormatter(
        &rowName, reinterpret_cast<void*>(202), 0);
    assert(rowName.length == 7 &&
           std::memcmp(rowName.data, "Quest 2", 7) == 0 &&
           stockQuestNameCount == 0);
    const int rowIntent = QuestBoardRowIntentAttribute(
        reinterpret_cast<void*>(202), nullptr, 0x1E565041u, 0);
    assert(rowIntent == static_cast<int>(kFirstQuestOfferIntentId + 1));
    const MajestyStringView* rowDetail = FindPrivateIntentText(rowIntent);
    assert(rowDetail != nullptr && rowDetail->length == 31 &&
           std::memcmp(
               rowDetail->data, "Complete objective 2 (200 gold)", 31) == 0);
    assert(QuestBoardRowIntentAttribute(
        reinterpret_cast<void*>(999), nullptr, 0x1E565041u, 0) == 91);
    assert(stockQuestAttributeCount == 1);
    assert(child.listBegin == questVectorStorage + 3);
    assert(questVectorStorage[0] == 101 && questVectorStorage[1] == 202 &&
           questVectorStorage[2] == 303);
    assert(visibleControlCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);

    // The native selected-action row moves up unchanged. The Manager-generated
    // second MX05 clone presents Refresh at the child's original bottom row.
    g_stockQuestBoardRefresh =
        reinterpret_cast<ControllerSetup>(&NativeQuestRefresh);
    g_stockQuestBoardControl =
        reinterpret_cast<ControllerControl>(&NativeQuestControl);
    visibleControlCount = 0;
    selectedQuestIndex = -1;
    QuestBoardRefresh(&child, nullptr);
    assert(questNativeRefreshCount == 1 && visibleControlCount == 5);
    assert(visibleControls[0] == kMx05SelectedActionCoinControlId &&
           visibleValues[0] == 0);
    assert(visibleControls[1] == kMx05SelectedActionPriceControlId &&
           visibleValues[1] == 0);
    assert(visibleControls[2] == quest.refreshControlId &&
           visibleValues[2] == 1);
    assert(visibleControls[3] == quest.refreshPriceBindingId &&
           visibleValues[3] == 1);
    assert(visibleControls[4] == kQuestRefreshCoinControlId &&
           visibleValues[4] == 1);
    assert(setIntegerCount == 1 && g_activeQuestRefreshCost == 25 &&
           g_activeQuestRefreshEnabled == 1);
    assert(lastMessageControl == quest.refreshControlId && lastMessage == 0x0Au);
    visibleControlCount = 0;
    selectedQuestIndex = 0;
    assert(QuestBoardControl(&child, nullptr, kMx05SelectionControlId) == 17);
    assert(visibleControlCount == 2);
    assert(visibleControls[0] == kMx05SelectedActionCoinControlId &&
           visibleValues[0] == 1);
    assert(visibleControls[1] == kMx05SelectedActionPriceControlId &&
           visibleValues[1] == 1);
    playerGold = 10;
    submitCount = 0;
    assert(QuestBoardControl(&child, nullptr, quest.refreshControlId) == 0);
    assert(submitCount == 0);
    playerGold = 1000;
    visibleControlCount = 0;
    assert(QuestBoardControl(&child, nullptr, quest.refreshControlId) == 0);
    assert(submitCount == 1 && seenCommand == quest.refreshCommandId);
    assert(seenBuilding == 123 && seenAgent == 123 && seenPrice == 25);
    assert(visibleControlCount == 3 &&
           visibleControls[2] == kQuestRefreshCoinControlId &&
           visibleValues[2] == 0 && g_activeQuestRefreshEnabled == 0);
    visibleControlCount = 0;
    assert(QuestBoardControl(&child, nullptr, 0x1F4Du) == 17);
    assert(visibleControlCount == 0);

    // 15. Unchanged high-frequency events are read-only: one revision query,
    // no list refresh and no synthetic panel write or message.
    questQueryCount = questRowQueryCount = questTextQueryCount = 0;
    questEventCount = questNativeRefreshCount = setIntegerCount = 0;
    lastMessageControl = 0;
    QuestBoardEvent(&child, nullptr, 1, 2, 3, 4);
    assert(questEventCount == 1 && questQueryCount == 1);
    assert(questNativeRefreshCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);
    QuestBoardRefresh(&child, nullptr);
    assert(questRowQueryCount == 0 && questTextQueryCount == 0);
    questNativeRefreshCount = 0;
    visibleControlCount = 0;

    // 16. A changed package revision is translated into one stock slot-14
    // refresh, whose slot-11 population keeps native list ownership. The
    // post-stock boundary updates the selected-action chrome and revalidates
    // the separate Manager-generated Refresh action.
    questRevision = 8;
    questQueryCount = questRowQueryCount = questTextQueryCount = 0;
    QuestBoardEvent(&child, nullptr, 1, 2, 3, 4);
    assert(questNativeRefreshCount == 1 && questRowQueryCount == 4);
    assert(g_activeQuestRevision == 8 && setIntegerCount == 0);
    assert(visibleControlCount == 2);
    assert(lastMessageControl == quest.refreshControlId && lastMessage == 0x0Au);

    // 17. Stock MX05 owns exactly one slot-14 refresh for every XSCX event.
    // Even if the engine supplies XSCX at a high cadence, the Manager adds no
    // second list refresh; it only revalidates the child Refresh action.
    questNativeRefreshCount = setIntegerCount = 0;
    visibleControlCount = 0;
    lastMessageControl = 0;
    for (int index = 0; index < 3; ++index) {
        QuestBoardEvent(&child, nullptr, 1, 2, 0x09435358u, 4);
    }
    assert(questNativeRefreshCount == 3 && setIntegerCount == 0);
    assert(visibleControlCount == 6);
    assert(lastMessageControl == quest.refreshControlId && lastMessage == 0x0Au);

    // 18. A mod callback that violates the declared stock-agent result
    // contract is contained to the private quest rows. The live MX05
    // controller remains usable and its vector is cleared instead of
    // terminating Majesty as though runtime installation had failed.
    g_activeQuestRevision = -1;
    g_activeQuestBoardFaulted = false;
    questAgentValid = false;
    QuestBoardPopulate(&child, nullptr);
    assert(g_activeQuestBoardFaulted);
    assert(g_questOfferPresentationCount == 0);
    assert(child.listBegin == questVectorStorage);

    std::puts("Panel lifecycle x86 tests passed: single/stacked, research, Back, visitors, reward, occupant, MX05 child Refresh and native quest list, revision gating, first-open building toggle, stale teardown.");
}
