#pragma once

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstddef>
#include <cstdint>

namespace MajestyControllerLifecycle {

using StockControllerDestructor = void* (__thiscall*)(
    void* controller, std::uint32_t deleteFlags);
using ControllerCleanup = void (__cdecl*)(
    void* controller, void* cleanupContext);

// Register a manager-owned clone of a stock controller vtable. Slot zero is
// Majesty's scalar-deleting destructor for the streamed-panel controller
// classes used by the manager. The registry replaces only that slot and
// delegates every teardown to the captured stock function unchanged.
//
// liveController must point to the owner's currently captured controller.
// Cleanup runs only when the object being destroyed is still that exact
// instance. This prevents a delayed destructor for an older dialog from
// invalidating a newly created dialog that reuses the same managed vtable.
bool RegisterManagedVtable(
    void** managedVtable,
    void** stockVtable,
    std::size_t vtableEntries,
    volatile LONG* liveController,
    ControllerCleanup cleanup,
    void* cleanupContext);

// Internal presentation handoff. Only tables already registered by an existing
// Manager controller may be wrapped. An alias leaves the presenter's destructor
// intact, but lets its delegated Manager destructor find the same cleanup owner.
bool DescribeManagedVtable(void** table, std::size_t* entries, void*** stock);
bool RegisterPresenterAlias(void** presenter, void** managed);
void** CanonicalManagedVtable(void** table);

}  // namespace MajestyControllerLifecycle
