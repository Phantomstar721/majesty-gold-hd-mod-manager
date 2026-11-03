#if defined(CAM_COMPACT_TOOLBAR_DIAGNOSTIC)
#include "CompactToolbarDiagnostic.h"
MajestyCompactDiagnostic::Budget g_compactBudget;
void* g_compactTable[9]{};
volatile LONG g_compactController=0;
ControllerSetup g_compactStockSetup=nullptr;
ControllerEvent g_compactStockEvent=nullptr;
bool g_compactRejected=false;
bool g_compactTableRegistered=false;
bool g_compactSetupReady=false;
unsigned g_compactGeneration=0;

void CompactDiagnosticStop(const char* reason,void* controller,ULONGLONG now) {
    if(!g_compactBudget.Stop())return;
    char text[256]{};
    sprintf_s(text,"CompactToolbar/v2 STOP reason=%s elapsed_ms=%llu records=%u controller=%p",
        reason,now-g_compactBudget.start,g_compactBudget.records,controller);
    WriteLog(text);
}
void __cdecl CompactDiagnosticDestroyed(void* controller,void*) {
    g_compactSetupReady=false;
    const auto now=GetTickCount64();
    if(g_compactBudget.Expired(now)) { CompactDiagnosticStop("time-limit",controller,now);return; }
    if(!g_compactBudget.Event(now,0))return;
    char text[256]{};
    sprintf_s(text,"CompactToolbar/v2 DETACHED elapsed_ms=%llu controller=%p generation=%u deadline_unchanged=1",
        now-g_compactBudget.start,controller,g_compactGeneration);
    WriteLog(text);
    if(g_compactBudget.records==255)CompactDiagnosticStop("record-limit-inconclusive",controller,now);
}
void __fastcall CompactDiagnosticSetup(void* controller,void*) {
    g_compactStockSetup(controller);
    if(static_cast<LONG>(reinterpret_cast<std::uintptr_t>(controller))!=g_compactController)return;
    const auto now=GetTickCount64();
    if(g_compactSetupReady)return;
    g_compactSetupReady=true;
    if(g_compactBudget.Expired(now)) { CompactDiagnosticStop("time-limit",controller,now);return; }
    const bool first=g_compactBudget.Arm(now);
    if(!first&&!g_compactBudget.Event(now,0))return;
    char text[256]{};
    sprintf_s(text,"CompactToolbar/v2 %s profile=%s controller=%p generation=%u elapsed_ms=%llu limit_ms=120000 limit_records=256 clocks=excluded",
        first?"ARMED":"ATTACHED",g_buildProfile->id,controller,g_compactGeneration,now-g_compactBudget.start);
    WriteLog(text);
    if(g_compactBudget.records==255)CompactDiagnosticStop("record-limit-inconclusive",controller,now);
}
void __fastcall CompactDiagnosticEvent(void* controller,void*,unsigned source,
    unsigned category,unsigned attribute,unsigned payload) {
    // Preserve the complete native handler, including its clock handling.
    g_compactStockEvent(controller,source,category,attribute,payload);
    if(static_cast<LONG>(reinterpret_cast<std::uintptr_t>(controller))!=g_compactController)return;
    if(!g_compactSetupReady||g_compactBudget.stopped)return;
    const auto now=GetTickCount64();
    if(g_compactBudget.Expired(now)) {
        CompactDiagnosticStop("time-limit",controller,now);return;
    }
    if(!g_compactBudget.Event(now,attribute))return;
    char text[320]{};
    sprintf_s(text,"CompactToolbar/v2 EVENT elapsed_ms=%llu profile=%s controller=%p source=%08X category=%08X attribute=%08X payload=%08X delivered=1 forwarded=1 stock_refresh=%u",
        now-g_compactBudget.start,g_buildProfile->id,controller,source,category,attribute,payload,
        (attribute==0x02435358||attribute==0x09425041)?1u:0u);
    WriteLog(text);
    if(g_compactBudget.records==255)CompactDiagnosticStop("record-limit-inconclusive",controller,now);
}
void CaptureCompactDiagnostic(std::uint32_t controller) {
    if(!controller||g_compactBudget.stopped||g_compactRejected)return;
    const auto index=static_cast<unsigned>(g_buildProfile->buildId);
    if(index>=3)return;
    const auto& p=MajestyCompactDiagnostic::profiles[index];
    auto*** object=reinterpret_cast<void***>(controller);
    auto** stock=*object;
    if(reinterpret_cast<std::uintptr_t>(stock)!=g_imageBase+p.table)return;
    if(g_compactBudget.Expired(GetTickCount64())) {
        CompactDiagnosticStop("time-limit",reinterpret_cast<void*>(controller),GetTickCount64());return;
    }
    for(unsigned i=0;i<9;++i)if(reinterpret_cast<std::uintptr_t>(stock[i])!=g_imageBase+p.slots[i]) {
        g_compactRejected=true;
        WriteLog("CompactToolbar/v2 NOT-ARMED reason=table-guard");return;
    }
    if(MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(stock[1]),0x89)!=p.setupHash ||
       MajestyCompactDiagnostic::Hash(reinterpret_cast<unsigned char*>(stock[8]),0x43)!=p.eventHash) {
        g_compactRejected=true;
        WriteLog("CompactToolbar/v2 NOT-ARMED reason=code-guard");return;
    }
    if(!g_compactTableRegistered) {
      std::memcpy(g_compactTable,stock,sizeof(g_compactTable));
      if(!MajestyControllerLifecycle::RegisterManagedVtable(g_compactTable,stock,9,
        &g_compactController,&CompactDiagnosticDestroyed,nullptr)) {
        g_compactRejected=true;
        WriteLog("CompactToolbar/v2 NOT-ARMED reason=lifecycle-registration");return;
      }
      g_compactStockSetup=reinterpret_cast<ControllerSetup>(stock[1]);
      g_compactStockEvent=reinterpret_cast<ControllerEvent>(stock[8]);
      g_compactTable[1]=reinterpret_cast<void*>(&CompactDiagnosticSetup);
      g_compactTable[8]=reinterpret_cast<void*>(&CompactDiagnosticEvent);
      g_compactTableRegistered=true;
    }
    g_compactSetupReady=false;
    ++g_compactGeneration;
    g_compactController=static_cast<LONG>(controller);
    *object=g_compactTable;
}
#endif
