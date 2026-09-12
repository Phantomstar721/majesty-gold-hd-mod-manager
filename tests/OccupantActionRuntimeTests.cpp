// Exercise the actual x86 runtime route, not a second model of it. No game
// process is opened and DllMain is not invoked by this console test.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cassert>

namespace {
std::uint32_t g_seen[4] = {};
const OccupantPanel* g_seenOwner = nullptr;
const QuestBoard* g_seenQuestOwner = nullptr;
const char* g_seenQuestCallback = nullptr;
void __cdecl RecordCommand(std::uint32_t command, std::uint32_t building,
                           std::uint32_t agent, std::uint32_t price) {
    g_seen[0] = command; g_seen[1] = building; g_seen[2] = agent; g_seen[3] = price;
    g_seenOwner = g_executingOccupantPanel;
    g_seenQuestOwner = g_executingQuestBoard;
    g_seenQuestCallback = g_executingQuestBoard == nullptr
        ? nullptr : g_executingQuestBoard->refreshCallbackSymbol.c_str();
}
void __cdecl NestedCommand(std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t) {
    const auto* outer = g_executingOccupantPanel;
    g_stockOccupantDispatch = &RecordCommand;
    DispatchOccupantAction(0x10001, 99, 88, 77);
    assert(g_seenOwner == &g_stockControllerRegistry.occupantActionPanels[1]);
    assert(g_executingOccupantPanel == outer);
}
const char* g_seenSymbol = nullptr;
void* __fastcall RecordString(void* destination, void*, const char* symbol) {
    g_seenSymbol = symbol;
    return destination;
}
}

int main() {
    g_stockControllerRegistry.occupantActionPanels = {
        {"stable", 0x31303042, 0x31303050, 0x4101, 0x10000, "Stable_Cost", "Stable_Action", 0x30315041},
        {"clinic", 0x32303042, 0x32303050, 0x4102, 0x10001, "Clinic_Cost", "Clinic_Action", 0x3930584D},
        {"dispatch", 0x31304741, 0x31305044, 0x4103, 0x10002, "Dispatch_Cost", "Dispatch_Action", 0x38305041},
    };
    MajestyStockControllers::QuestBoardRecord quest = {};
    quest.panelKey = "missions";
    quest.parentDialogId = 0x31304741;
    quest.childDialogId = 0x31304251;
    quest.openCommandId = 0x7101;
    quest.actionCommandId = 0x20000;
    quest.offerCountCallbackSymbol = "Quest_Count";
    quest.offerNameIntentId = 0x68000001;
    quest.offerGoalIntentId = 0x68000002;
    quest.offerRewardCallbackSymbol = "Quest_Reward";
    quest.refreshCallbackSymbol = "Quest_Refresh";
    quest.parentControllerBase = 0x38305041;
    g_stockControllerRegistry.questBoards = {quest};
    const auto* stable = &g_stockControllerRegistry.occupantActionPanels[0];
    const auto* clinic = &g_stockControllerRegistry.occupantActionPanels[1];
    const auto* dispatch = &g_stockControllerRegistry.occupantActionPanels[2];
    g_stockOccupantDispatch = &RecordCommand;
    // An already queued clinic action executes correctly with no UI open.
    g_activeOccupantPanel = nullptr;
    DispatchOccupantAction(0x10001, 10, 20, 300);
    assert(g_seenOwner == clinic && g_seen[0] == 21);
    assert(g_seen[1] == 10 && g_seen[2] == 20 && g_seen[3] == 300);
    assert(g_executingOccupantPanel == nullptr);
    // The quest board's one native bottom action uses the same exact MX05
    // queue/debit executor and retains its durable agent and quoted price.
    const auto* missions = &g_stockControllerRegistry.questBoards[0];
    DispatchOccupantAction(0x20000, 30, 40, 0);
    assert(g_seenQuestOwner == missions && g_seen[0] == 21);
    assert(g_seen[1] == 30 && g_seen[2] == 40 && g_seen[3] == 0);
    assert(std::strcmp(g_seenQuestCallback, "Quest_Refresh") == 0);
    assert(g_executingQuestBoard == nullptr);
    // Changing panel cannot change a queued command's owner.
    g_activeOccupantPanel = stable;
    DispatchOccupantAction(0x10001, 10, 20, 300);
    assert(g_seenOwner == clinic);
    // Stock Mausoleum and unrelated stock commands never take private symbols.
    DispatchOccupantAction(21, 11, 22, 2000);
    assert(g_seenOwner == nullptr && g_seen[0] == 21);
    DispatchOccupantAction(1, 1, 2, 3);
    assert(g_seenOwner == nullptr && g_seen[0] == 1);
    // Command callback context is strictly call-scoped, including nesting.
    g_stockOccupantDispatch = &NestedCommand;
    DispatchOccupantAction(0x10000, 10, 20, 300);
    assert(g_executingOccupantPanel == nullptr);
    // Actual submission keeps the complete stock packet and privatizes only
    // its command discriminator, never the selected-agent handle or price.
    MajestyBuildProfile profile = kBeta2BuildProfile;
    profile.submitBuildingCommandRva = 0;
    g_buildProfile = &profile;
    g_imageBase = reinterpret_cast<std::uintptr_t>(&RecordCommand);
    SubmitOccupantAction(21, 0x12345678, 0x87654321, 0x4567);
    assert(g_seen[0] == 0x10000 && g_seen[1] == 0x12345678 &&
           g_seen[2] == 0x87654321 && g_seen[3] == 0x4567);
    g_activeOccupantPanel = nullptr;
    SubmitOccupantAction(21, 1, 2, 3);
    assert(g_seen[0] == 21);
    g_imageBase = reinterpret_cast<std::uintptr_t>(&RecordString) - kBeta2Occupants.stringConstructor;
    assert(OccupantCostString(reinterpret_cast<void*>(1), nullptr, "Stock_Cost") == reinterpret_cast<void*>(1));
    assert(std::strcmp(g_seenSymbol, "Stock_Cost") == 0);
    g_activeOccupantPanel = stable;
    OccupantCostString(nullptr, nullptr, "Stock_Cost");
    assert(std::strcmp(g_seenSymbol, "Stable_Cost") == 0);
    g_executingOccupantPanel = clinic;
    OccupantActionString(nullptr, nullptr, "Stock_Action");
    assert(std::strcmp(g_seenSymbol, "Clinic_Action") == 0);
    g_executingOccupantPanel = nullptr;
    OccupantActionString(nullptr, nullptr, "Stock_Action");
    assert(std::strcmp(g_seenSymbol, "Stock_Action") == 0);
    // Factory dispatch retains each parent's declared stock class and aliases
    // only the private child. Provide a caller slot for normal diagnostic logs.
    std::uint32_t args[6] = {0, clinic->parentDialogId, 0, 0, 0, 0};
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == kMx09DialogId);
    args[1] = stable->childDialogId;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == kMx05DialogId);
    args[1] = dispatch->parentDialogId;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == kAp08DialogId);
    args[1] = dispatch->childDialogId;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == kMx05DialogId);
    args[1] = missions->parentDialogId;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == 0x38305041);
    args[1] = missions->childDialogId;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == kMx05DialogId);
    // Creation requests alone do not prove destruction. Both notices and
    // stock Visitors/list requests preserve live mappings until stock teardown.
    std::uint32_t creation[] = {0x36335041, 0, 0, 0}; // AP36 notice
    g_activeOccupantPanel = stable;
    g_secondaryPanelActive = 1;
    ResolveDialogCreationRequest(creation);
    assert(g_activeOccupantPanel == stable);
    creation[0] = kMx05DialogId;
    creation[1] = 123;
    ResolveDialogCreationRequest(creation);
    assert(g_activeOccupantPanel == stable && g_secondaryPanelActive == 1);
    creation[0] = clinic->childDialogId;
    ResolveDialogCreationRequest(creation);
    assert(g_activeOccupantPanel == clinic && g_captureChildController == 1);
    ClearSecondaryPanelControllerOwnedState();
    assert(g_activeOccupantPanel == nullptr && g_activeQuestBoard == nullptr &&
           g_captureChildController == 0);
    std::puts("Occupant and quest-board x86 routing tests passed.");
    return 0;
}
