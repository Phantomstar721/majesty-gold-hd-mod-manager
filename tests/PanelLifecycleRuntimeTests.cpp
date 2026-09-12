// The actual x86 runtime and destructor dispatcher, with native call boundaries
// stubbed. No game process, window, package, or save file is opened.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cassert>
#include <cstdio>

namespace {
struct StreamedDialog { void** table; };
struct Stream { void** table; StreamedDialog* streamedDialog; };
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
unsigned char contextC[0xA0] = {}, contextD[0xA0] = {};
void* contextTable[74] = {};
void* streamTable[27] = {};
void* playerTable[9] = {};
struct PlayerRecord { void** table; } playerRecord = {playerTable};
void* nativeTable[17] = {};
void* parentTable[17] = {};
void* childTable[17] = {};
void* streamedDialogTable[1] = {};
StreamedDialog streamedDialog = {streamedDialogTable};
Stream stream = {streamTable, &streamedDialog};
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
int questNativeSetupCount = 0;
int parentEventCount = 0;
int questQueryCount = 0, questOfferCountQueryCount = 0;
int questRevisionQueryCount = 0, questAgentQueryCount = 0;
int questVariantQueryCount = 0;
int selectedQuestIndex = -1;
std::uint32_t questRevision = 7;
std::uint32_t questOfferCount = 3;
std::uint32_t questVariantSelections[3] = {1, 2, 1};
std::uint32_t resolvedQuestAgentNumber = 0;
std::uint32_t questVectorStorage[68] = {};
std::uint32_t lastMessageControl = 0, lastMessage = 0;
std::uint32_t lastVisibleControl = 0, lastVisibleValue = 0;
std::uint32_t visibleControls[16] = {};
std::uint32_t visibleValues[16] = {};
std::size_t visibleControlCount = 0;
bool affordable = true;
bool reenterParentEventOnSet = false;
int stockQuestNameCount = 0, stockQuestAttributeCount = 0;
int stockQuestSummaryCount = 0;
int stockQuestStatusIconDrawCount = 0;
bool stockQuestDestinationConstructed = false;
MajestyStringView* expectedQuestDestination = nullptr;
void* expectedQuestSummaryOwner = nullptr;
std::uint32_t expectedQuestSummaryTextId = 0;
void* lastQuestStatusPainter = nullptr;
const void* lastQuestStatusRectangle = nullptr;
std::uint32_t lastQuestStatusStyle = 0;
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
    if (control == 0x1388u && message == 0x22u) {
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
        ++questRevisionQueryCount;
        *result = questRevision;
    } else if (std::strcmp(symbol, "Quest_Count") == 0) {
        assert(!hasInteger);
        ++questOfferCountQueryCount;
        *result = questOfferCount;
    } else if (std::strcmp(symbol, "Quest_Reward") == 0) {
        assert(hasInteger && integerValue >= 1 && integerValue <= 64);
        *result = static_cast<std::uint32_t>(integerValue * 100);
    } else if (std::strcmp(symbol, "Quest_Variant") == 0) {
        assert(hasInteger && integerValue >= 1 && integerValue <= 3);
        ++questVariantQueryCount;
        *result = questVariantSelections[integerValue - 1];
    } else if (std::strcmp(symbol, "Quest_Agent_Id") == 0) {
        assert(hasInteger && integerValue >= 1 &&
               integerValue <= static_cast<int>(questOfferCount));
        ++questAgentQueryCount;
        *result = 0x1000u + static_cast<std::uint32_t>(integerValue);
    } else {
        assert(false);
    }
    return true;
}
void* ResolveQuestAgentNumber(std::uint32_t agentNumber) {
    resolvedQuestAgentNumber = agentNumber;
    void* rows[] = {contextA, contextB, contextC, contextD};
    if (agentNumber >= 0x1001u && agentNumber <= 0x1004u) {
        return rows[agentNumber - 0x1001u];
    }
    return nullptr;
}
MajestyStringView* __fastcall AssignQuestText(
    MajestyStringView* destination, void*, const MajestyStringView* source) {
    assert(destination == expectedQuestDestination);
    assert(stockQuestDestinationConstructed);
    *destination = *source;
    return destination;
}
void* __cdecl StockQuestName(
    MajestyStringView* destination, void*, int) {
    ++stockQuestNameCount;
    assert(destination == expectedQuestDestination);
    destination->data = nullptr;
    destination->capacityFlags = 0;
    destination->length = 0;
    stockQuestDestinationConstructed = true;
    return destination;
}
int __fastcall StockQuestAttribute(
    void*, void*, std::uint32_t, std::uint32_t) {
    ++stockQuestAttributeCount;
    return 91;
}
const MajestyStringView* __fastcall StockQuestSummary(
    void* owner, void*, std::uint32_t textId) {
    static const char text[] = "stock building summary";
    static const MajestyStringView view = {
        text, static_cast<std::uint32_t>(sizeof(text) - 1),
        static_cast<std::uint32_t>(sizeof(text) - 1),
    };
    ++stockQuestSummaryCount;
    assert(owner == expectedQuestSummaryOwner);
    assert(textId == expectedQuestSummaryTextId);
    return &view;
}
void __fastcall StockQuestStatusIconDraw(
    void* painter, void*, const void* rectangle, std::uint32_t style) {
    ++stockQuestStatusIconDrawCount;
    lastQuestStatusPainter = painter;
    lastQuestStatusRectangle = rectangle;
    lastQuestStatusStyle = style;
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
void __fastcall NativeQuestSetup(void* controller, void*) {
    ++questNativeSetupCount;
    // Model an MX05 slot 1 that was already entered before Manager vtable
    // installation: its later slot-14 call still resolves through the
    // controller's newly installed table.
    auto** table = *reinterpret_cast<void***>(controller);
    reinterpret_cast<ControllerSetup>(table[14])(controller);
}
void __fastcall NativeQuestEvent(
    void* controller, void*, std::uint32_t, std::uint32_t,
    std::uint32_t eventId, std::uint32_t) {
    ++questEventCount;
    if (eventId == 0x09435358u) {
        auto** table = *reinterpret_cast<void***>(controller);
        reinterpret_cast<ControllerSetup>(table[14])(controller);
    }
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
    questEventCount = questNativeRefreshCount = questNativeSetupCount = 0;
    selectedQuestIndex = -1;
    parentEventCount = 0;
    questQueryCount = questOfferCountQueryCount = 0;
    questRevisionQueryCount = questAgentQueryCount = questVariantQueryCount = 0;
    questRevision = 7;
    questOfferCount = 3;
    questVariantSelections[0] = 1;
    questVariantSelections[1] = 2;
    questVariantSelections[2] = 1;
    resolvedQuestAgentNumber = 0;
    stockQuestNameCount = stockQuestAttributeCount = stockQuestSummaryCount = 0;
    stockQuestStatusIconDrawCount = 0;
    stockQuestDestinationConstructed = false;
    expectedQuestDestination = nullptr;
    lastQuestStatusPainter = nullptr;
    lastQuestStatusRectangle = nullptr;
    lastQuestStatusStyle = 0;
    std::memset(questVectorStorage, 0, sizeof(questVectorStorage));
    child.listOwner = &child;
    child.listBegin = questVectorStorage;
    child.listEnd = questVectorStorage +
        sizeof(questVectorStorage) / sizeof(questVectorStorage[0]);
    g_questBoardScalarEvaluator = &QuestScalar;
    g_questBoardAgentNumberResolver = &ResolveQuestAgentNumber;
    g_privateIntentRecords = {
        {0x68000001u, "Complete 100% objective"},
        {0x68000002u, " Gold"},
        {0x68000003u, "Delivery"},
        {0x68000004u, "Deliver goods"},
        {0x68000005u, "Escort"},
        {0x68000006u, "Protect a traveler"},
    };
    g_privateIntentViews.clear();
    for (const auto& record : g_privateIntentRecords) {
        const auto length = static_cast<std::uint32_t>(record.text.size());
        g_privateIntentViews.push_back(
            {record.text.c_str(), length, length});
    }
    g_stockQuestVectorErase =
        reinterpret_cast<QuestVectorErase>(&EraseQuestVector);
    g_stockQuestVectorInsert =
        reinterpret_cast<QuestVectorInsert>(&InsertQuestVector);
    g_stockQuestBoardRefresh =
        reinterpret_cast<ControllerSetup>(&NativeQuestRefresh);
    g_stockQuestBoardEvent =
        reinterpret_cast<ControllerEvent>(&NativeQuestEvent);
    g_stockQuestRowStatusIconDraw =
        reinterpret_cast<StockQuestRowStatusIconDraw>(
            &StockQuestStatusIconDraw);
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
    nativeTable[14] = reinterpret_cast<void*>(&NativeQuestRefresh);
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

    // 13. An occupant-action recipe may use AP08 without becoming a quest-board
    // recipe. AP08 is a distinct 13-entry parent class; derive that boundary
    // from the occupant record and leave the package-owned MX05 child native.
    Reset();
    MajestyStockControllers::OccupantActionPanelRecord ap08Occupant = *occupant;
    ap08Occupant.panelKey = "dispatch";
    ap08Occupant.parentDialogId = 0x31304741;
    ap08Occupant.childDialogId = 0x31305044;
    ap08Occupant.openCommandId = 0x7101;
    ap08Occupant.parentControllerBase = kAp08DialogId;
    g_parentOccupantPanel = &ap08Occupant;
    auto* ap08Image = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 0x00400000u, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(ap08Image != nullptr);
    g_imageBase = reinterpret_cast<std::uintptr_t>(ap08Image);
    auto** ap08StockTable = reinterpret_cast<void**>(
        ap08Image + kBeta2QuestBoard.parentVtable);
    ap08StockTable[0] = reinterpret_cast<void*>(&Delete);
    ap08StockTable[1] = reinterpret_cast<void*>(&Fallback);
    ap08StockTable[3] = reinterpret_cast<void*>(&Fallback);
    ap08StockTable[8] = reinterpret_cast<void*>(&NativeParentEvent);
    ap08StockTable[12] = ap08StockTable;
    parent.table = ap08StockTable;
    profile.getPanelContextRva =
        reinterpret_cast<std::uintptr_t>(&Context) - g_imageBase;
    profile.uiManagerRva =
        reinterpret_cast<std::uintptr_t>(&Manager) - g_imageBase;
    profile.getCurrentPlayerRva =
        reinterpret_cast<std::uintptr_t>(&Player) - g_imageBase;
    profile.submitBuildingCommandRva =
        reinterpret_cast<std::uintptr_t>(&SubmitBuilding) - g_imageBase;
    assert(ValidateAp08ParentProfile());
    g_captureParentController = 1;
    CaptureSecondaryController(reinterpret_cast<std::uint32_t>(&parent), 0);
    auto* questAp08Clone = FindOccupantParentClass(&parent);
    assert(questAp08Clone != nullptr &&
           questAp08Clone->stock == ap08StockTable);
    assert(questAp08Clone->entryCount == kAp08VtableEntries);
    assert(g_parentQuestBoard == nullptr && g_parentOccupantPanel == &ap08Occupant);
    assert(questQueryCount == 0 && setIntegerCount == 0 && visibleControlCount == 0);
    OccupantParentEvent(&parent, nullptr, 1, 2, 3, 4);
    assert(parentEventCount == 1 && questQueryCount == 0);
    assert(OccupantParentControl(&parent, nullptr, 0x7102) == 23);
    assert(fallbackCount == 1 && submitCount == 0);
    Destroy(parent);
    assert(g_parentOccupantPanel == nullptr && g_parentController == 0);

    // 14. The live-agent-list recipe retains the exact AP08 parent boundary
    // while the package-owned MX05 child keeps one native bottom action.
    Reset();
    MajestyStockControllers::LiveAgentListRecord quest = {};
    quest.panelKey = "agent-list";
    quest.parentDialogId = 0x31304741;
    quest.childDialogId = 0x31304251;
    quest.openCommandId = 0x7101;
    quest.actionCommandId = 0x20000;
    quest.rowCountCallbackSymbol = "Quest_Count";
    quest.rowAgentIdCallbackSymbol = "Quest_Agent_Id";
    quest.revisionCallbackSymbol = "Quest_Revision";
    quest.rowTitleIntentId = 0;
    quest.rowTextIntentId = 0x68000001u;
    quest.hasRowValue = true;
    quest.rowValueCallbackSymbol = "Quest_Reward";
    quest.rowValueSuffixIntentId = 0x68000002u;
    quest.actionCostCallbackSymbol = "Quest_RefreshCost";
    quest.actionCallbackSymbol = "Quest_Refresh";
    quest.parentControllerBase = 0x38305041;
    g_stockControllerRegistry.liveAgentLists = {quest};
    g_parentQuestBoard = &g_stockControllerRegistry.liveAgentLists[0];
    parent.table = ap08StockTable;
    g_captureParentController = 1;
    CaptureSecondaryController(reinterpret_cast<std::uint32_t>(&parent), 0);
    auto* ap08Clone = FindOccupantParentClass(&parent);
    assert(ap08Clone != nullptr && ap08Clone->stock == ap08StockTable);
    assert(ap08Clone->entryCount == kAp08VtableEntries);
    // Controller capture is installation only. It must not execute package GPL
    // or write private controls before Majesty inserts the controller.
    assert(parentEventCount == 0 && questQueryCount == 0);
    assert(setIntegerCount == 0 && visibleControlCount == 0);

    // AP08 remains a stock parent with only the child opener. Refresh is not
    // presented, queried, or dispatched from the primary building panel.
    OccupantParentEvent(&parent, nullptr, 1, 2, 3, 4);
    assert(parentEventCount == 1 && questQueryCount == 0 &&
           setIntegerCount == 0 && lastMessageControl == 0);
    OccupantParentEvent(&parent, nullptr, 1, 2, 0x06425041u, 4);
    assert(parentEventCount == 2 && questQueryCount == 0);
    assert(setIntegerCount == 0 && visibleControlCount == 0);
    assert(OccupantParentControl(&parent, nullptr, 0x7102) == 23);
    assert(fallbackCount == 1 && submitCount == 0);
    Destroy(parent);
    assert(g_parentQuestBoard == nullptr && g_parentController == 0);
    assert(VirtualFree(ap08Image, 0, MEM_RELEASE));

    // Restore the direct native seams after the synthetic image-base proof.
    g_imageBase = 0;
    profile.getPanelContextRva = reinterpret_cast<std::uintptr_t>(&Context);
    profile.uiManagerRva = reinterpret_cast<std::uintptr_t>(&Manager);
    profile.getCurrentPlayerRva = reinterpret_cast<std::uintptr_t>(&Player);
    profile.submitBuildingCommandRva =
        reinterpret_cast<std::uintptr_t>(&SubmitBuilding);

    // 15. If stock MX05 slot 1 was already entered before the Manager installs
    // its clone, its later stock slot-14 call reaches the gated slot-11 package
    // population. Slots 3, 10, and 14 remain byte-for-byte stock.
    g_activeQuestBoard = &g_stockControllerRegistry.liveAgentLists[0];
    g_childController = reinterpret_cast<LONG>(&child);
    g_stockQuestBoardRefresh =
        reinterpret_cast<ControllerSetup>(&NativeQuestRefresh);
    visibleControlCount = setIntegerCount = 0;
    lastMessageControl = lastMessage = 0;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    child.table = nativeTable;
    nativeTable[1] = reinterpret_cast<void*>(&NativeQuestSetup);
    const auto alreadyEnteredSetup =
        reinterpret_cast<ControllerSetup>(nativeTable[1]);
    child.table = childTable;
    childTable[8] = reinterpret_cast<void*>(&QuestBoardEvent);
    childTable[11] = reinterpret_cast<void*>(&QuestBoardPopulate);
    childTable[14] = reinterpret_cast<void*>(&NativeQuestRefresh);
    alreadyEnteredSetup(&child);
    assert(questNativeSetupCount == 1 && questNativeRefreshCount == 1);
    assert(g_activeQuestRevision == 7 && questOfferCountQueryCount == 1);
    assert(questRevisionQueryCount == 1);
    assert(visibleControlCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);

    // 16. One package population supplies multiple distinct live agents to
    // MX05's native vector. Selection, scrolling, and the bottom action remain
    // stock while optional static text and per-row values are Manager-owned.
    g_activeQuestRevision = -1;
    assert(kGplIntegerResultType == 1);
    g_questBoardAgentNumberResolver = &ResolveQuestAgentNumber;
    void* decodedAgent = nullptr;
    assert(QueryQuestBoardAgent(
        "Quest_Agent_Id", contextA, 2, &decodedAgent));
    assert(decodedAgent == contextB && resolvedQuestAgentNumber == 0x1002u);
    questQueryCount = questAgentQueryCount = 0;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    questAgentQueryCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(g_activeQuestRevision == 7 && questOfferCountQueryCount == 1);
    assert(questAgentQueryCount == 3 && g_questOfferPresentationCount == 3);
    assert(g_questOfferPresentations[0].agent == contextA);
    assert(g_questOfferPresentations[1].agent == contextB);
    assert(g_questOfferPresentations[2].agent == contextC);
    assert(g_questOfferPresentations[0].name.empty());
    assert(g_questOfferPresentations[1].name.empty());
    assert(g_questOfferPresentations[2].name.empty());
    assert(g_questOfferPresentations[0].detail ==
           "Complete 100% objective\n100 Gold");
    assert(g_questOfferPresentations[1].detail ==
           "Complete 100% objective\n200 Gold");
    assert(g_questOfferPresentations[2].detail ==
           "Complete 100% objective\n300 Gold");
    const char expectedSummaryTemplate[] =
        "\x01" "FFFFFF%s\n\x01"
        "A550AAComplete 100%% objective\n\x01" "FFFF00100 Gold";
    assert(g_questOfferPresentations[0].summaryTemplate == expectedSummaryTemplate);
    g_privateIntentStringAssign =
        reinterpret_cast<StockStringAssign>(&AssignQuestText);
    g_stockQuestRowNameFormatter = &StockQuestName;
    g_stockQuestRowAttributeReader =
        reinterpret_cast<StockQuestRowAttributeReader>(&StockQuestAttribute);
    g_stockQuestRowSummaryText =
        reinterpret_cast<StockQuestRowSummaryText>(&StockQuestSummary);
    MajestyStringView rowName = {
        reinterpret_cast<const char*>(0xDEADBEEFu),
        0xCCCCCCCCu,
        0xDDDDDDDDu,
    };
    expectedQuestDestination = &rowName;
    QuestBoardRowNameFormatter(&rowName, contextA, 0);
    assert(rowName.data == nullptr && rowName.length == 0 &&
           stockQuestNameCount == 1 && stockQuestDestinationConstructed);
    const MajestyStringView* stablePrivateSummary = nullptr;
    for (const std::uint32_t textId : {0xD8u, 0xD9u, 0xDAu, 0xDBu}) {
        if (textId != 0xD8u) {
            rowName = {
                reinterpret_cast<const char*>(0xDEADBEEFu),
                0xCCCCCCCCu,
                0xDDDDDDDDu,
            };
            stockQuestDestinationConstructed = false;
            QuestBoardRowNameFormatter(&rowName, contextA, 0);
            assert(stockQuestDestinationConstructed);
        }
        const int stockSummaryBefore = stockQuestSummaryCount;
        const MajestyStringView* summary = QuestBoardRowSummaryText(
            reinterpret_cast<void*>(0x12345678u), nullptr, textId);
        assert(summary == &g_questOfferPresentations[0].summaryView);
        assert(summary->length == sizeof(expectedSummaryTemplate) - 1);
        assert(std::memcmp(
                   summary->data, expectedSummaryTemplate,
                   sizeof(expectedSummaryTemplate) - 1) == 0);
        assert(summary->data[0] == 1 && summary->data[1] == 'F');
        assert((reinterpret_cast<const unsigned char*>(summary)[7] & 1u) == 0);
        char renderedSummary[128] = {};
        sprintf_s(
            renderedSummary, sizeof(renderedSummary), summary->data,
            "Quest 1", 901, 902, 903);
        const char expectedRenderedSummary[] =
            "\x01" "FFFFFFQuest 1\n\x01"
            "A550AAComplete 100% objective\n\x01" "FFFF00100 Gold";
        assert(std::strcmp(renderedSummary, expectedRenderedSummary) == 0);
        assert(stockQuestSummaryCount == stockSummaryBefore);
        const int statusDrawsBefore = stockQuestStatusIconDrawCount;
        void* statusPainter = reinterpret_cast<void*>(0x11223344u);
        const void* statusRectangle = reinterpret_cast<void*>(0x55667788u);
        QuestBoardFirstStatusIconDraw(
            statusPainter, nullptr, statusRectangle, 2);
        QuestBoardSecondStatusIconDraw(
            statusPainter, nullptr, statusRectangle, 3);
        assert(stockQuestStatusIconDrawCount == statusDrawsBefore);
        assert(!g_suppressQuestStatusIconsForCurrentRow);
        if (stablePrivateSummary == nullptr) stablePrivateSummary = summary;
        assert(stablePrivateSummary->data ==
               g_questOfferPresentations[0].summaryTemplate.c_str());
    }
    // The private marker is consumed by exactly one summary call. A second
    // formatting request falls through with the stock owner and GMTX ID
    // unchanged, while the previously returned private storage remains live.
    expectedQuestSummaryOwner = reinterpret_cast<void*>(0x12345678u);
    expectedQuestSummaryTextId = 0xD8u;
    const MajestyStringView* stockSummary = QuestBoardRowSummaryText(
        expectedQuestSummaryOwner, nullptr, expectedQuestSummaryTextId);
    assert(stockSummary->length == 22 &&
           std::memcmp(stockSummary->data, "stock building summary", 22) == 0);
    assert(stockQuestSummaryCount == 1);
    assert(stablePrivateSummary->data ==
           g_questOfferPresentations[0].summaryTemplate.c_str());
    MajestyStringView fallbackName = {
        reinterpret_cast<const char*>(0xBAADF00Du),
        0xAAAAAAAAu,
        0xBBBBBBBBu,
    };
    expectedQuestDestination = &fallbackName;
    stockQuestDestinationConstructed = false;
    assert(QuestBoardRowNameFormatter(
               &fallbackName, reinterpret_cast<void*>(999), 0) ==
           &fallbackName);
    assert(stockQuestNameCount == 5 && stockQuestDestinationConstructed);
    QuestBoardFirstStatusIconDraw(
        reinterpret_cast<void*>(0x11223344u), nullptr,
        reinterpret_cast<void*>(0x55667788u), 2);
    QuestBoardSecondStatusIconDraw(
        reinterpret_cast<void*>(0x11223344u), nullptr,
        reinterpret_cast<void*>(0x55667788u), 3);
    assert(stockQuestStatusIconDrawCount == 2);
    assert(lastQuestStatusPainter == reinterpret_cast<void*>(0x11223344u));
    assert(lastQuestStatusRectangle == reinterpret_cast<void*>(0x55667788u));
    assert(lastQuestStatusStyle == 3);
    expectedQuestSummaryOwner = reinterpret_cast<void*>(0x87654321u);
    expectedQuestSummaryTextId = 0xDBu;
    stockSummary = QuestBoardRowSummaryText(
        expectedQuestSummaryOwner, nullptr, expectedQuestSummaryTextId);
    assert(stockSummary->length == 22 &&
           std::memcmp(stockSummary->data, "stock building summary", 22) == 0);
    assert(stockQuestSummaryCount == 2);
    const int rowIntent = QuestBoardRowIntentAttribute(
        contextA, nullptr, 0x1E565041u, 0);
    assert(rowIntent == static_cast<int>(kFirstQuestOfferIntentId));
    const MajestyStringView* rowDetail = FindPrivateIntentText(rowIntent);
    const char expectedDetail[] = "Complete 100% objective\n100 Gold";
    assert(rowDetail != nullptr &&
           rowDetail->length == sizeof(expectedDetail) - 1 &&
           std::memcmp(
               rowDetail->data, expectedDetail,
               sizeof(expectedDetail) - 1) == 0);
    assert(QuestBoardRowIntentAttribute(
        contextB, nullptr, 0x1E565041u, 0) ==
        static_cast<int>(kFirstQuestOfferIntentId + 1));
    assert(QuestBoardRowIntentAttribute(
        reinterpret_cast<void*>(999), nullptr, 0x1E565041u, 0) == 91);
    assert(stockQuestAttributeCount == 1);
    assert(child.listBegin == questVectorStorage + 3);
    assert(questVectorStorage[0] ==
           reinterpret_cast<std::uint32_t>(contextA));
    assert(questVectorStorage[1] ==
           reinterpret_cast<std::uint32_t>(contextB));
    assert(questVectorStorage[2] ==
           reinterpret_cast<std::uint32_t>(contextC));

    // The value/reward column is optional for the same multi-row lifecycle.
    // Omitting it performs no value callback and leaves each row's ordinary
    // title/detail/action behavior intact.
    auto& activeList = g_stockControllerRegistry.liveAgentLists[0];
    activeList.hasRowValue = false;
    activeList.rowValueCallbackSymbol.clear();
    activeList.rowValueSuffixIntentId = 0;
    g_activeQuestRevision = -1;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    questAgentQueryCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(questQueryCount == 5 && questAgentQueryCount == 3);
    assert(g_questOfferPresentationCount == 3);
    assert(g_questOfferPresentations[0].detail == "Complete 100% objective");
    assert(g_questOfferPresentations[1].detail == "Complete 100% objective");
    const char expectedTextOnlySummary[] =
        "\x01" "FFFFFF%s\n\x01" "A550AAComplete 100%% objective";
    assert(g_questOfferPresentations[0].summaryTemplate ==
           expectedTextOnlySummary);

    activeList.hasRowValue = true;
    activeList.rowValueCallbackSymbol = "Quest_Reward";
    activeList.rowValueSuffixIntentId = 0x68000002u;
    g_activeQuestRevision = -1;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    questAgentQueryCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(questQueryCount == 8 && questAgentQueryCount == 3);
    assert(g_questOfferPresentations[0].detail ==
           "Complete 100% objective\n100 Gold");

    // Package-declared static variants select bounded title/detail text with
    // the same integer scalar evaluator already used by row values. Row
    // identity, selection, action routing, and stock MX05 ownership do not
    // change.
    activeList.rowTextIntentId = 0;
    activeList.hasRowVariants = true;
    activeList.rowVariantCallbackSymbol = "Quest_Variant";
    activeList.rowVariants = {
        {0x68000003u, 0x68000004u},
        {0x68000005u, 0x68000006u},
    };
    g_activeQuestRevision = -1;
    g_activeQuestBoardFaulted = false;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    questAgentQueryCount = questVariantQueryCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(!g_activeQuestBoardFaulted && questVariantQueryCount == 3);
    assert(questQueryCount == 11 && questAgentQueryCount == 3);
    assert(g_questOfferPresentations[0].name == "Delivery");
    assert(g_questOfferPresentations[1].name == "Escort");
    assert(g_questOfferPresentations[2].name == "Delivery");
    assert(g_questOfferPresentations[0].detail == "Deliver goods\n100 Gold");
    assert(g_questOfferPresentations[1].detail ==
           "Protect a traveler\n200 Gold");

    // A non-one-based or out-of-range result faults only this private list and
    // clears its borrowed rows.
    questVariantSelections[1] = 3;
    g_activeQuestRevision = -1;
    g_activeQuestBoardFaulted = false;
    questQueryCount = questVariantQueryCount = 0;
    QuestBoardPopulate(&child, nullptr);
    assert(g_activeQuestBoardFaulted && g_questOfferPresentationCount == 0);
    assert(child.listBegin == questVectorStorage);

    // Restore the ordinary single static presentation for the remaining
    // stock-painter and revision lifecycle checks.
    questVariantSelections[1] = 2;
    activeList.hasRowVariants = false;
    activeList.rowVariantCallbackSymbol.clear();
    activeList.rowVariants.clear();
    activeList.rowTextIntentId = 0x68000001u;
    g_activeQuestRevision = -1;
    g_activeQuestBoardFaulted = false;
    QuestBoardPopulate(&child, nullptr);
    assert(!g_activeQuestBoardFaulted && g_questOfferPresentationCount == 3);
    assert(g_questOfferPresentations[0].summaryTemplate == expectedSummaryTemplate);

    // Stock slot 14 can run at paint cadence without polling package GPL or
    // producing any Manager-owned UI write.
    questNativeRefreshCount = 0;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    visibleControlCount = setIntegerCount = 0;
    lastMessageControl = lastMessage = 0;
    for (int index = 0; index < 300; ++index) {
        reinterpret_cast<ControllerSetup>(child.table[14])(&child);
        MajestyStringView paintName = {
            reinterpret_cast<const char*>(0xDEADBEEFu),
            0xCCCCCCCCu,
            0xDDDDDDDDu,
        };
        expectedQuestDestination = &paintName;
        stockQuestDestinationConstructed = false;
        QuestBoardRowNameFormatter(&paintName, contextA, 0);
        const MajestyStringView* paintSummary = QuestBoardRowSummaryText(
            reinterpret_cast<void*>(0x12345678u), nullptr, 0xD8u);
        assert(stockQuestDestinationConstructed);
        assert(paintSummary == &g_questOfferPresentations[0].summaryView);
        assert(std::memcmp(
                   paintSummary->data, expectedSummaryTemplate,
                   sizeof(expectedSummaryTemplate) - 1) == 0);
        QuestBoardFirstStatusIconDraw(
            reinterpret_cast<void*>(0x11223344u), nullptr,
            reinterpret_cast<void*>(0x55667788u), 2);
        QuestBoardSecondStatusIconDraw(
            reinterpret_cast<void*>(0x11223344u), nullptr,
            reinterpret_cast<void*>(0x55667788u), 3);
    }
    assert(questNativeRefreshCount == 300 && questQueryCount == 0);
    assert(stockQuestSummaryCount == 2);
    assert(stockQuestStatusIconDrawCount == 2);
    assert(visibleControlCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);

    // 17. Unchanged non-XSCX events perform one bounded revision query and no
    // list refresh or synthetic presentation.
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    questEventCount = questNativeRefreshCount = 0;
    QuestBoardEvent(&child, nullptr, 1, 2, 3, 4);
    assert(questEventCount == 1 && questQueryCount == 1 &&
           questRevisionQueryCount == 1);
    assert(questNativeRefreshCount == 0 && visibleControlCount == 0);

    // 18. A changed package revision is translated into exactly one stock
    // slot-14 refresh, whose gated slot-11 population retains native ownership.
    questRevision = 8;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    QuestBoardEvent(&child, nullptr, 1, 2, 3, 4);
    assert(questNativeRefreshCount == 1 && questOfferCountQueryCount == 1);
    assert(questRevisionQueryCount == 1 && g_activeQuestRevision == 8);
    assert(visibleControlCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);

    // 19. XSCX remains wholly stock: one native slot-14 refresh per event and
    // no extra callback, UI write, or second refresh from the Manager.
    questNativeRefreshCount = 0;
    questQueryCount = questOfferCountQueryCount = questRevisionQueryCount = 0;
    for (int index = 0; index < 3; ++index) {
        QuestBoardEvent(&child, nullptr, 1, 2, 0x09435358u, 4);
    }
    assert(questNativeRefreshCount == 3 && questQueryCount == 0);
    assert(visibleControlCount == 0 && setIntegerCount == 0 &&
           lastMessageControl == 0);

    // 20. A package count above the bounded multi-row contract is contained to
    // the private rows. The live MX05 controller remains usable and its vector
    // is cleared instead of terminating Majesty.
    g_activeQuestRevision = -1;
    g_activeQuestBoardFaulted = false;
    questOfferCount = 65;
    QuestBoardPopulate(&child, nullptr);
    assert(g_activeQuestBoardFaulted);
    assert(g_questOfferPresentationCount == 0);
    assert(child.listBegin == questVectorStorage);

    std::puts("Panel lifecycle x86 tests passed: single/stacked, research, Back, visitors, reward, occupant, multi-row MX05 live-agent list, revision gating, first-open building toggle, stale teardown.");
}
