#include "ControllerLifecycleRegistry.h"

namespace MajestyControllerLifecycle {
namespace {

struct Registration {
    void** managedVtable;
    StockControllerDestructor stockDestructor;
    volatile LONG* liveController;
    ControllerCleanup cleanup;
    void* cleanupContext;
    Registration* next;
};

Registration* volatile g_registrations = nullptr;
volatile LONG g_registrationLock = 0;

class RegistrationLock {
public:
    RegistrationLock() {
        while (InterlockedCompareExchange(&g_registrationLock, 1, 0) != 0) {
            SwitchToThread();
        }
    }

    ~RegistrationLock() {
        InterlockedExchange(&g_registrationLock, 0);
    }

    RegistrationLock(const RegistrationLock&) = delete;
    RegistrationLock& operator=(const RegistrationLock&) = delete;
};

Registration* FindRegistration(void** managedVtable) {
    auto* registration = static_cast<Registration*>(
        InterlockedCompareExchangePointer(
            reinterpret_cast<PVOID volatile*>(&g_registrations),
            nullptr,
            nullptr));
    while (registration != nullptr) {
        if (registration->managedVtable == managedVtable) {
            return registration;
        }
        registration = registration->next;
    }
    return nullptr;
}

void* __fastcall ManagedControllerDestructor(
    void* controller,
    void*,
    std::uint32_t deleteFlags) {
    if (controller == nullptr) {
        return nullptr;
    }

    auto** managedVtable = *reinterpret_cast<void***>(controller);
    Registration* registration = FindRegistration(managedVtable);
    if (registration == nullptr || registration->stockDestructor == nullptr) {
        // This dispatcher is installed only after its immutable registration
        // is published. Reaching it without that record indicates external
        // vtable corruption; do not guess a destructor target.
        return controller;
    }

    const LONG controllerValue = static_cast<LONG>(
        reinterpret_cast<std::uintptr_t>(controller));
    const bool owned = InterlockedCompareExchange(
        registration->liveController, 0, controllerValue) == controllerValue;
    if (owned && registration->cleanup != nullptr) {
        registration->cleanup(controller, registration->cleanupContext);
    }

    // Preserve Majesty's scalar-deleting-destructor flags and return value.
    return registration->stockDestructor(controller, deleteFlags);
}

}  // namespace

bool RegisterManagedVtable(
    void** managedVtable,
    void** stockVtable,
    std::size_t vtableEntries,
    volatile LONG* liveController,
    ControllerCleanup cleanup,
    void* cleanupContext) {
    if (managedVtable == nullptr || stockVtable == nullptr ||
        managedVtable == stockVtable || vtableEntries == 0 ||
        stockVtable[0] == nullptr || liveController == nullptr) {
        return false;
    }

    RegistrationLock lock;
    Registration* existing = FindRegistration(managedVtable);
    if (existing != nullptr) {
        return existing->stockDestructor ==
                reinterpret_cast<StockControllerDestructor>(stockVtable[0]) &&
            existing->liveController == liveController &&
            existing->cleanup == cleanup &&
            existing->cleanupContext == cleanupContext;
    }

    auto* registration = static_cast<Registration*>(HeapAlloc(
        GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(Registration)));
    if (registration == nullptr) {
        return false;
    }

    registration->managedVtable = managedVtable;
    registration->stockDestructor =
        reinterpret_cast<StockControllerDestructor>(stockVtable[0]);
    registration->liveController = liveController;
    registration->cleanup = cleanup;
    registration->cleanupContext = cleanupContext;
    registration->next = g_registrations;
    MemoryBarrier();
    InterlockedExchangePointer(
        reinterpret_cast<PVOID volatile*>(&g_registrations), registration);

    managedVtable[0] = reinterpret_cast<void*>(&ManagedControllerDestructor);
    return true;
}

}  // namespace MajestyControllerLifecycle
