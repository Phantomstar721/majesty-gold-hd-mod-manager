#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstring>
#include <cstdio>

#include "ControllerLifecycleRegistry.h"

namespace {

struct FakeController {
    void** vtable;
};

int g_stockDestructorCalls = 0;
std::uint32_t g_lastDeleteFlags = 0;

void* __fastcall FakeStockDestructor(
    void* controller,
    void*,
    std::uint32_t deleteFlags) {
    ++g_stockDestructorCalls;
    g_lastDeleteFlags = deleteFlags;
    return controller;
}

void __cdecl CountCleanup(void*, void* context) {
    ++*static_cast<int*>(context);
}

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "FAILED: %s\n", message);
        return false;
    }
    return true;
}

using DeleteController = void* (__thiscall*)(void*, std::uint32_t);

}  // namespace

int main() {
    bool passed = true;
    void* stockVtable[3] = {
        reinterpret_cast<void*>(&FakeStockDestructor),
        reinterpret_cast<void*>(0x1010),
        reinterpret_cast<void*>(0x2020)};
    void* managedVtable[3] = {};
    std::memcpy(managedVtable, stockVtable, sizeof(managedVtable));
    volatile LONG liveController = 0;
    int cleanupCalls = 0;

    passed &= Expect(
        MajestyControllerLifecycle::RegisterManagedVtable(
            managedVtable,
            stockVtable,
            3,
            &liveController,
            &CountCleanup,
            &cleanupCalls),
        "first managed vtable registration succeeds");
    passed &= Expect(
        managedVtable[0] != stockVtable[0],
        "only the stock destructor entry is wrapped");
    passed &= Expect(
        managedVtable[1] == stockVtable[1] && managedVtable[2] == stockVtable[2],
        "non-destructor entries remain stock-identical");
    passed &= Expect(
        MajestyControllerLifecycle::RegisterManagedVtable(
            managedVtable,
            stockVtable,
            3,
            &liveController,
            &CountCleanup,
            &cleanupCalls),
        "identical registration is idempotent");

    FakeController first = {managedVtable};
    liveController = static_cast<LONG>(reinterpret_cast<std::uintptr_t>(&first));
    auto destroy = reinterpret_cast<DeleteController>(managedVtable[0]);
    void* result = destroy(&first, 0xA5);
    passed &= Expect(result == &first, "stock destructor return value is preserved");
    passed &= Expect(g_stockDestructorCalls == 1, "stock destructor runs exactly once");
    passed &= Expect(g_lastDeleteFlags == 0xA5, "stock delete flags are preserved");
    passed &= Expect(cleanupCalls == 1, "current controller cleanup runs once");
    passed &= Expect(liveController == 0, "current controller slot is invalidated");

    FakeController stale = {managedVtable};
    FakeController replacement = {managedVtable};
    liveController = static_cast<LONG>(
        reinterpret_cast<std::uintptr_t>(&replacement));
    destroy(&stale, 0x01);
    passed &= Expect(
        cleanupCalls == 1,
        "delayed destruction of an older controller does not clean replacement state");
    passed &= Expect(
        liveController == static_cast<LONG>(
            reinterpret_cast<std::uintptr_t>(&replacement)),
        "delayed destruction preserves the replacement controller pointer");
    destroy(&replacement, 0x02);
    passed &= Expect(cleanupCalls == 2, "replacement cleanup runs at its own teardown");
    passed &= Expect(g_stockDestructorCalls == 3, "every teardown still reaches stock");

    void* secondManagedVtable[2] = {
        stockVtable[0], reinterpret_cast<void*>(0x3030)};
    volatile LONG secondLiveController = 0;
    int secondCleanupCalls = 0;
    passed &= Expect(
        MajestyControllerLifecycle::RegisterManagedVtable(
            secondManagedVtable,
            stockVtable,
            2,
            &secondLiveController,
            &CountCleanup,
            &secondCleanupCalls),
        "an independent controller type can register dynamically");
    FakeController second = {secondManagedVtable};
    secondLiveController = static_cast<LONG>(
        reinterpret_cast<std::uintptr_t>(&second));
    reinterpret_cast<DeleteController>(secondManagedVtable[0])(&second, 0x04);
    passed &= Expect(
        secondCleanupCalls == 1 && cleanupCalls == 2,
        "independent controller types invalidate only their own state");

    if (!passed) {
        return 1;
    }
    std::puts("Controller lifecycle registry tests passed.");
    return 0;
}
