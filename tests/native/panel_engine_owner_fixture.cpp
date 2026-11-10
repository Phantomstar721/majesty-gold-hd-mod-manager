// The SDK translation unit precedes this file in the generated fixture. Every
// native game function macro is redirected to a local test pointer. No game
// process, mapped address, native module installation or UI is used.
#include "../../runtime/PanelEngineAgentClient.h"
extern "C" __declspec(dllimport) void __stdcall ExitProcess(unsigned);

static void* stockVtable[VT_COPY_SLOTS + 1];
static int MMWE_VtableLength(void** table) { return table==stockVtable+1 ? 17 : 0; }
static void* viewVtable[32];
static void* tableVtable[4];
static unsigned char viewBytes[8], dialogBytes[0x110], controllerBytes[OWN_SIZE];
static unsigned char tableBytes[16];
static const char* rowText[8];
static const char* returnedString;
static int stockCalls, initCalls, commandCalls, notifyCalls, eventCalls;
static int hideCalls, deleteCalls, deleteFlags, openCalls, nativeOpenResult;
static u32 lastId, lastCommand, lastPanel;
static void* lastUnit;
static int token;
static int tallEnables, tallDisables, tallMode;
static unsigned char firstTall[OWN_SIZE], secondTall[OWN_SIZE];
static unsigned char borrowedAgent[0x39];
static int unitResolutionCalls;

static void require(int value, unsigned line) { if (!value) ExitProcess(line); }
#define REQUIRE(value) require((value), __LINE__)
static void setPointer(void* into, int offset, void* value) { *(void**)((char*)into + offset) = value; }
static void* __fastcall strings(void*, void*, int index) {
    returnedString = rowText[index];
    return &returnedString;
}
static void __fastcall hidden(void*, void*, u32 control, int show) {
    REQUIRE(control == 10 && show == 0); ++hideCalls;
}
static void __fastcall initialize(void*, void*) { ++initCalls; }
static int __fastcall command(void*, void*, u32 control) { ++commandCalls; lastCommand = control; return 9; }
static void __fastcall notify(void*, void*, u32, u32, u32, u32) { ++notifyCalls; }
static void __fastcall event(void*, void*, u32, u32, u32, u32) { ++eventCalls; }
static void* __fastcall destroy(void*, void*, int flags) { ++deleteCalls; deleteFlags = flags; return &token; }
static void* __fastcall unit(void*, void*) { return &token; }
static void* __fastcall associatedUnit(void* actor, void*) {
    REQUIRE(actor == borrowedAgent); ++unitResolutionCalls; return &token;
}
static int __fastcall openPanel(void*, void*, u32 id, void* target) {
    ++openCalls; lastPanel = id; lastUnit = target; return nativeOpenResult;
}
static void* __cdecl game() { return &token; }
static void __fastcall frameTall(void*, void*, int on) {
    tallMode = on;
    if (on) ++tallEnables; else ++tallDisables;
}
static u32 __fastcall windowId(void*, void*, void* target) { REQUIRE(target == &token); return 0x314d5446; }
static void* __fastcall factory(void*, void*, u32 id, void* view, void* unit, int extra) {
    ++stockCalls; lastId = id;
    REQUIRE(view == viewBytes && unit == &token && extra == 23);
    return id == 0x32504146 ? controllerBytes : 0;
}
static void* __cdecl allocate(u32 size) { REQUIRE(size == OWN_SIZE); return controllerBytes; }
static void* __fastcall construct(void* self, void*, void* view, void* target) {
    REQUIRE(self == controllerBytes && view == viewBytes && target == &token);
    setPointer(self, 0, stockVtable + 1); setPointer(self, 0x24, view);
    return self;
}

extern "C" void __cdecl mainCRTStartup() {
    REQUIRE(!MajestyPanelEngine::ResolveLiveAgentUnit(0, associatedUnit));
    REQUIRE(!MajestyPanelEngine::ResolveLiveAgentUnit(borrowedAgent, 0));
    borrowedAgent[0x38] = 1;
    REQUIRE(!MajestyPanelEngine::ResolveLiveAgentUnit(borrowedAgent, associatedUnit));
    REQUIRE(unitResolutionCalls == 0);
    borrowedAgent[0x38] = 0;
    REQUIRE(MajestyPanelEngine::ResolveLiveAgentUnit(borrowedAgent, associatedUnit) == &token);
    REQUIRE(unitResolutionCalls == 1);
    fixture_GAME_FACTORY = factory; fixture_GET_UNIT = unit;
    fixture_OPEN_SUB = openPanel; fixture_GAME_OBJ = game; fixture_WINDOW_ID = windowId;
    fixture_GAME_NEW = allocate; fixture_STATS_CTOR = construct;
    fixture_FRAME_TALL = frameTall;
    stockVtable[1] = (void*)destroy;
    stockVtable[1 + SLOT_INIT] = (void*)initialize;
    stockVtable[1 + SLOT_ONCOMMAND] = (void*)command;
    stockVtable[1 + SLOT_NOTIFY] = (void*)notify;
    stockVtable[1 + SLOT_ONEVENT] = (void*)event;
    viewVtable[VIEW_SETVISIBLE / 4] = (void*)hidden;
    tableVtable[STRT_GETSTRING / 4] = (void*)strings;
    setPointer(viewBytes, 0, viewVtable); setPointer(viewBytes, 4, dialogBytes);
    setPointer(dialogBytes, 0x10c, tableBytes); setPointer(tableBytes, 0, tableVtable);
    construct(controllerBytes, 0, viewBytes, &token);
    rowText[0] = "Ordinary title"; *(int*)(tableBytes + 12) = 1;
    REQUIRE(!MMWE_OwnsView(viewBytes) && !MMWE_OwnsController(controllerBytes));
    REQUIRE(WE_Factory(0, 0, 0x32504146, viewBytes, &token, 23) == controllerBytes);
    REQUIRE(!MMWE_OwnsController(controllerBytes));
    REQUIRE(*(void***)controllerBytes == stockVtable + 1);

    rowText[0] = "WE|1|BASE|FAP2";
    rowText[1] = "WE|1|HIDE|10";
    rowText[2] = "WE|1|PANEL|20|NX02";
    rowText[3] = "WE|1|BACK|30";
    rowText[4] = "WE|1|DOES|40|50";
    *(int*)(tableBytes + 12) = 5;
    REQUIRE(MMWE_OwnsView(viewBytes));
    REQUIRE(WE_Factory(0, 0, 0x314d5446, viewBytes, &token, 23) == controllerBytes);
    REQUIRE(lastId == 0x32504146 && stockCalls == 3 && MMWE_OwnsController(controllerBytes));
    REQUIRE(!MMWE_OwnsController(0));
    void** vt = *(void***)controllerBytes;
    ((Init_t)vt[SLOT_INIT])(controllerBytes, 0);
    REQUIRE(initCalls == 1 && hideCalls == 1);
    nativeOpenResult = 1;
    REQUIRE(((OnCommand_t)vt[SLOT_ONCOMMAND])(controllerBytes, 0, 20) == 1);
    REQUIRE(lastPanel == 0x3230584e && !lastUnit && hideCalls == 1);
    nativeOpenResult = 0;
    REQUIRE(((OnCommand_t)vt[SLOT_ONCOMMAND])(controllerBytes, 0, 20) == 0);
    REQUIRE(hideCalls == 2);
    REQUIRE(((OnCommand_t)vt[SLOT_ONCOMMAND])(controllerBytes, 0, 30) == 1);
    REQUIRE(lastPanel == 0x314d5446 && !lastUnit && openCalls == 3);
    REQUIRE(((OnCommand_t)vt[SLOT_ONCOMMAND])(controllerBytes, 0, 40) == 9);
    REQUIRE(lastCommand == 50 && commandCalls == 1);
    REQUIRE(((OnCommand_t)vt[SLOT_ONCOMMAND])(controllerBytes, 0, 60) == 9);
    REQUIRE(lastCommand == 60 && commandCalls == 2);
    ((Notify_t)vt[SLOT_NOTIFY])(controllerBytes, 0, 1, 0, 2, 3);
    ((Notify_t)vt[SLOT_ONEVENT])(controllerBytes, 0, 1, 0, 2, 3);
    REQUIRE(notifyCalls == 1 && eventCalls == 1);
    REQUIRE(((Dtor_t)vt[0])(controllerBytes, 0, 7) == &token);
    REQUIRE(deleteCalls == 1 && deleteFlags == 7);

    // An own bare class uses the stock constructor once and is then wrapped.
    // This executes only the local fixture constructor, not native game code.
    rowText[0] = "WE|1|CLASS|bare";
    REQUIRE(WE_Factory(0, 0, 0x314d5446, viewBytes, &token, 23) == controllerBytes);
    REQUIRE(MMWE_OwnsController(controllerBytes));

    // Closing an older tall instance must not reset a newer tall panel's
    // frame. Use the SDK's existing reference count, not an extra registry.
    setPointer(firstTall, 0, stockVtable + 1); setPointer(firstTall, 0x24, viewBytes);
    setPointer(secondTall, 0, stockVtable + 1); setPointer(secondTall, 0x24, viewBytes);
    rowText[5] = "WE|1|TALL|1"; *(int*)(tableBytes + 12) = 6;
    REQUIRE(wrap(firstTall) && wrap(secondTall));
    REQUIRE(MMWE_OwnsController(firstTall) && MMWE_OwnsController(secondTall));
    void** first = *(void***)firstTall;
    void** second = *(void***)secondTall;
    ((Init_t)first[SLOT_INIT])(firstTall, 0);
    ((Init_t)second[SLOT_INIT])(secondTall, 0);
    REQUIRE(tallEnables == 1 && tallDisables == 0 && tallMode == 1 && g_tall_open == 2);
    REQUIRE(((Dtor_t)first[0])(firstTall, 0, 1) == &token);
    REQUIRE(tallDisables == 0 && tallMode == 1 && g_tall_open == 1);
    REQUIRE(((Dtor_t)second[0])(secondTall, 0, 1) == &token);
    REQUIRE(tallDisables == 1 && tallMode == 0 && g_tall_open == 0);
    // Unknown tables are refused before a copy and do not consume a class slot.
    void* unknownTable[VT_COPY_SLOTS+1] = {};
    setPointer(controllerBytes,0,unknownTable+1);
    const int beforeClasses=g_nclasses;
    REQUIRE(!wrap(controllerBytes));
    REQUIRE(g_nclasses==beforeClasses && *(void***)controllerBytes==unknownTable+1);
    ExitProcess(0);
}
