// Outcome handling on the existing guarded GS_OrderProcessor research dispatch.
using StockResearchExecution = bool (__thiscall*)(void*,void*,std::uint32_t);
const unsigned char kResearchSchedulerBody[] = {0x56,0x8B,0x74,0x24,0x08,0x32,0xC0,0x85,0xF6,0x74,0x37,0x8B,0x4C,0x24,0x14,0x8B,0x06,0x8B,0x90,0x88,0x01,0x00,0x00,0x51,0x8B,0xCE,0xFF,0xD2,0x8B,0x4C,0x24,0x0C,0x8B,0x54,0x24,0x10,0x83,0x48,0x18,0x02,0x89,0x48,0x14,0x89,0x50,0x2C,0x8B,0x16,0x8B,0x92,0x8C,0x01,0x00,0x00,0x50,0x8B,0x44,0x24,0x1C,0x50,0x8B,0xCE,0xFF,0xD2,0xB0,0x01,0x5E,0xC2,0x14,0x00};
bool ValidatePrivateResearchExecutionProfile() {
    if(g_stockControllerRegistry.researchRows.empty())return true;
    if(!g_buildProfile || !MajestyFeatureParity::Validate(g_imageBase,g_buildProfile->buildId,
        MajestyFeatureParity::Feature::Research))return false;
    // FeatureParity column order: beta2, public Steam, GOG.
    const std::uintptr_t scheduler[]={0xDD400u,0xDCDF0u,0xDDB40u};
    const int index=MajestyFeatureParity::Index(g_buildProfile->buildId);
    if(index<0 || g_imageBase!=0x400000)return false;
    const auto slot=ParityRva(ParitySite::ResearchSlot);
    return *reinterpret_cast<const std::uintptr_t*>(g_imageBase+slot)==g_imageBase+ParityRva(ParitySite::ResearchExecute) &&
        *reinterpret_cast<const std::uintptr_t*>(g_imageBase+slot-0x10)==g_imageBase+scheduler[index] &&
        std::memcmp(reinterpret_cast<const void*>(g_imageBase+scheduler[index]),kResearchSchedulerBody,sizeof(kResearchSchedulerBody))==0;
}
bool ExecutePrivateResearchWithOutcome(StockResearchExecution original,void* processor,void* unit,std::uint32_t command) {
    const auto* pending = g_researchOwner.pending &&
        g_researchOwner.context==unit && g_researchOwner.record &&
        g_researchOwner.record->actionControlId==command ? g_researchOwner.record : nullptr;
    const auto* row = g_stockControllerRegistry.FindResearchByCommand(command);
    const auto* state = row ? FindPrivateResearchDescriptor(row) : nullptr;
    const auto* panel = row ? g_stockControllerRegistry.FindPanelByKey(row->panelKey) : nullptr;
    // Repeat the stock shared-activity exclusion at execution, not just UI
    // submission: a recruitment command may have won the intervening queue.
    const bool eligible = !row || (unit && panel &&
        SecondaryPanelAllowed(unit, *panel) &&
        ((*reinterpret_cast<const std::uint32_t*>(static_cast<const unsigned char*>(unit)+0x7C) & 0xFFFFFFu) == (panel->buildingFamilyId & 0xFFFFFFu)) &&
        ReadPackedAttributeValue(unit,kResearchDurationAttributeId)==0 &&
        (row->startCallbackSymbol.empty() || !g_researchOrderPresent(unit)) &&
        state && state->descriptor && state->descriptor[4] &&
        (row->chargeMs ? QueuedActionStatus(*row,unit,0)==0 : ReadPackedAttributeValue(unit,state->descriptor[4])==0));
    const bool delayed = row && row->chargeMs;
    const bool reserved = eligible && delayed && QueuedActionStatus(*row,unit,1)==0;
    bool accepted=eligible && (!delayed || reserved) && original(processor,unit,command);
    if (reserved && accepted && !KingdomResearchHasStockOrder(unit,command)) accepted=false;
    if (reserved && !accepted) {
        QueuedActionStatus(*row,unit,3);
        // Stock's scheduling failure can follow tuple publication. No money
        // was charged (this contract requires zero price); retire only ours.
        if (ReadPackedAttributeValue(unit,kCurrentResearchAttributeId)==static_cast<int>(command)) {
            WritePackedAttributeValue(unit,kCurrentResearchAttributeId,0);
            WritePackedAttributeValue(unit,kResearchDurationAttributeId,0);
        }
    }
    if(!accepted && pending && g_researchOwner.pending &&
        g_researchOwner.context==unit && g_researchOwner.record==pending) {
        // The guarded executor's normal false paths precede payment and tuple
        // publication. Retire only this private reservation, as the existing
        // kingdom-research adapter does for its rejected reservation.
        g_researchOwner={};
        if(InterlockedCompareExchange(&g_secondaryPanelActive,0,0)!=0)
            RefreshPrivateResearchRows(static_cast<std::uint32_t>(InterlockedCompareExchange(&g_childController,0,0)));
        WriteLog("Stock research rejected the queued private request; released its pending reservation without payment or activity writes.");
    }
    return accepted;
}
