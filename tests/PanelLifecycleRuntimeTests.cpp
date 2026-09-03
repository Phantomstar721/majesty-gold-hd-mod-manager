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
};
static_assert(offsetof(Controller, stream) == 0x24, "native stream offset");
unsigned char contextA[0xA0] = {}, contextB[0xA0] = {};
void* contextTable[74] = {};
void* streamTable[27] = {};
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
int fallbackCount = 0, submitCount = 0, refreshCount = 0, openCount = 0;
int openResult = 0, deleteCount = 0, hideCount = 0;
bool affordable = true;
void* __fastcall Context(void* object, void*) {
    return static_cast<Controller*>(object)->context;
}
void* __cdecl Manager() { return reinterpret_cast<void*>(1); }
void* __fastcall Player(void*, void*) { return reinterpret_cast<void*>(2); }
void* __fastcall PlayerAgent(void*, void*, std::uint32_t player) {
    assert(player == 7);
    return contextA;
}
int __fastcall ReadAttribute(void*, void*, std::uint32_t, std::uint32_t) { return 0; }
void __fastcall WriteAttribute(void*, void*, std::uint32_t, int) {}
std::uint32_t __fastcall Send(void*, void*, std::uint32_t, std::uint32_t,
                             std::uint32_t, std::uint32_t) { return 0; }
void __fastcall Visible(void*, void*, std::uint32_t, std::uint32_t) {}
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
int __fastcall Fallback(void*, void*, std::uint32_t) { ++fallbackCount; return 23; }
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
    g_parentOccupantPanel = nullptr;
    g_researchOwner = {};
    parent.context = child.context = contextA;
    replacementParent.context = replacementChild.context = contextB;
    fallbackCount = submitCount = refreshCount = openCount = hideCount = 0;
    seenContext = nullptr; seenDialog = seenCommand = 0;
    affordable = true;
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
    streamTable[0x20 / 4] = reinterpret_cast<void*>(&Visible);
    streamTable[0x14 / 4] = reinterpret_cast<void*>(&Hide);
    nativeTable[0] = reinterpret_cast<void*>(&Delete);
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
    std::puts("Panel lifecycle x86 tests passed: single/stacked, research, Back, visitors, reward, occupant, stale teardown.");
}
