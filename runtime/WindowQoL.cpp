#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include "WindowQoL.h"
#include "WindowQoLProfiles.h"

// Used by Python preflight to reject a stale runtime before enabling either row.
extern "C" __declspec(dllexport) const char* MajestyWindowQoLAbi() { return "WindowQoL ABI 1"; }

namespace WindowQoL {
namespace {
const WindowQoLProfiles::Profile* profile = nullptr;
std::uintptr_t image = 0;
WNDPROC original = nullptr;
void (*logger)(const char*) = nullptr;
bool requested = true, closing = false, owned = false, conflictLogged = false;
bool focused = false, minimized = false;
HWND current = nullptr;
ATOM hotkey = 0;
RECT lastRect = {};
int lastMode = -1;

// Test builds replace this table; no fixture calls the real desktop APIs.
struct Api {
    decltype(&GetForegroundWindow) foreground;
    decltype(&GetWindowThreadProcessId) process;
    decltype(&IsWindow) valid;
    decltype(&IsIconic) iconic;
    decltype(&IsWindowVisible) visible;
    decltype(&GetClientRect) client;
    decltype(&ClientToScreen) screen;
    decltype(&ClipCursor) clip;
    decltype(&GetClipCursor) getClip;
    decltype(&RegisterHotKey) registerKey;
    decltype(&UnregisterHotKey) unregisterKey;
    decltype(&GlobalAddAtomA) addAtom;
    decltype(&GlobalDeleteAtom) deleteAtom;
    decltype(&VirtualProtect) protect;
} api = {GetForegroundWindow, GetWindowThreadProcessId, IsWindow, IsIconic, IsWindowVisible,
         GetClientRect, ClientToScreen, ClipCursor, GetClipCursor,
         RegisterHotKey, UnregisterHotKey, GlobalAddAtomA, GlobalDeleteAtom, VirtualProtect};

int Fullscreen() { return *reinterpret_cast<volatile int*>(image + profile->gameFullscreenRva); }
HWND MainWindow() { return *reinterpret_cast<HWND volatile*>(image + profile->mainWindowRva); }
bool Main(HWND window) {
    DWORD pid = 0;
    return window && window == MainWindow() && api.valid(window) &&
        api.process(window, &pid) && pid == GetCurrentProcessId();
}
void Log(const char* text) { if (logger) logger(text); }
void FreeSteamCursor() {
    if (!owned) return;
    RECT actual = {};
    // Do not release a different clip installed by another owner.
    if (api.getClip(&actual) && EqualRect(&actual, &lastRect)) api.clip(nullptr);
    owned = false;
}
void RemoveShortcut() {
    if (!hotkey) return;
    api.unregisterKey(current, hotkey);
    api.deleteAtom(hotkey);
    hotkey = 0;
}
bool Active() {
    return current && !closing && !minimized && focused && Main(current) &&
        api.foreground() == current && api.visible(current) && !api.iconic(current) && Fullscreen() == 0;
}
int EffectiveGogMode() {
    const int stock = *reinterpret_cast<volatile int*>(image + profile->gogModeRva);
    // Stock remains the sole cursor owner. Never alter its saved mode/getter.
    if (Fullscreen() != 0) return stock;
    return Active() && hotkey && requested ? 2 : 0;
}
// Replace just Apply's original MOV EAX,[mode]. Preserve every other register
// and flags as that MOV does. The original routine owns the actual ClipCursor.
__declspec(naked) void EffectiveGogModeThunk() {
    __asm {
        pushfd
        push ecx
        push edx
        call EffectiveGogMode
        pop edx
        pop ecx
        popfd
        ret
    }
}
void ApplyCursor() {
    if (profile->gogClipRva) {
        reinterpret_cast<void(__cdecl*)()>(image + profile->gogClipRva)();
    } else if (Active() && hotkey && requested) {
        RECT rect = {};
        if (api.client(current, &rect) && rect.right > rect.left && rect.bottom > rect.top &&
            api.screen(current, reinterpret_cast<POINT*>(&rect.left)) &&
            api.screen(current, reinterpret_cast<POINT*>(&rect.right))) {
            if (!owned || !EqualRect(&rect, &lastRect)) {
                if (api.clip(&rect)) { lastRect = rect; owned = true; }
                else FreeSteamCursor();
            }
        } else FreeSteamCursor();
    } else FreeSteamCursor();
}
void Reconcile() {
    const int mode = Fullscreen();
    // Stock fullscreen focus policy must remain authoritative, including GOG.
    if (mode != 0) {
        RemoveShortcut();
        FreeSteamCursor();
        if (profile->gogClipRva && lastMode == 0) ApplyCursor();
        lastMode = mode;
        return;
    }
    if (Active()) {
        if (!hotkey) {
            const ATOM id = api.addAtom("Majesty.ModManager.CursorToggle");
            if (id && api.registerKey(current, id, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_F11)) {
                hotkey = id;
            } else {
                if (id) api.deleteAtom(id);
                if (!conflictLogged) {
                    Log("Window QoL: Ctrl+Shift+F11 is unavailable; cursor confinement is disabled for this focus session.");
                    conflictLogged = true;
                }
            }
        }
    } else RemoveShortcut();
    ApplyCursor();
    lastMode = mode;
}
LRESULT CALLBACK Procedure(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    if (window != current && !Main(window)) return original(window, message, wparam, lparam);
    const bool first = current != window;
    if (first) {
        RemoveShortcut();
        FreeSteamCursor();
        current = window;
        closing = false;
        focused = api.foreground() == window;
        minimized = api.iconic(window) != FALSE;
    }
    if (message == WM_HOTKEY && hotkey && wparam == hotkey) {
        if (Active()) { requested = !requested; ApplyCursor(); }
        return 0;
    }
    bool update = first;
    switch (message) {
    case WM_ACTIVATE: focused = LOWORD(wparam) != WA_INACTIVE; minimized = HIWORD(wparam) != 0; update = true; break;
    case WM_ACTIVATEAPP: focused = wparam != 0; update = true; break;
    case WM_SETFOCUS: focused = true; update = true; break;
    case WM_KILLFOCUS: focused = false; update = true; break;
    case WM_SIZE: minimized = wparam == SIZE_MINIMIZED; update = true; break;
    case WM_WINDOWPOSCHANGED: case WM_DISPLAYCHANGE: case WM_DPICHANGED: case WM_SHOWWINDOW: update = true; break;
    case WM_DESTROY: case WM_NCDESTROY: closing = true; update = true; break;
    case WM_ENDSESSION: if (wparam) { closing = true; update = true; } break;
    default: break;
    }
    // Release before a native focus/minimize/destruction handler runs. GOG's
    // native reapply sees the same effective mode and cannot recapture it.
    if (update && (!focused || minimized || closing)) Reconcile();
    const LRESULT result = original(window, message, wparam, lparam);
    if (update || lastMode != Fullscreen()) Reconcile();
    // Native destruction can synchronously create/focus the replacement HWND.
    // Do not discard the new window's hotkey/clip owner when the old call returns.
    if (message == WM_NCDESTROY && current == window) current = nullptr;
    return result;
}
std::uint32_t Fnv(const unsigned char* bytes, unsigned size) {
    std::uint32_t hash = 2166136261u;
    for (unsigned n = 0; n < size; ++n) hash = (hash ^ bytes[n]) * 16777619u;
    return hash;
}
struct Patch { unsigned char* at; unsigned size; unsigned char bytes[17]; DWORD protect; };
bool Commit(Patch* patches, unsigned count) {
    // Acquire every range before the first write. Overlapping page permissions
    // are restored in reverse order, including a failed acquisition.
    unsigned acquired = 0;
    for (; acquired < count; ++acquired) {
        auto& p = patches[acquired];
        if (!api.protect(p.at, p.size, PAGE_EXECUTE_READWRITE, &p.protect)) break;
    }
    if (acquired == count) {
        for (unsigned i = 0; i < count; ++i) std::memcpy(patches[i].at, patches[i].bytes, patches[i].size);
        FlushInstructionCache(GetCurrentProcess(), nullptr, 0);
    }
    const bool changed = acquired == count;
    while (acquired) {
        auto& p = patches[--acquired]; DWORD ignored = 0;
        api.protect(p.at, p.size, p.protect, &ignored);
    }
    return changed;
}
}

bool Install(std::uintptr_t base, MajestyBuildId build, bool borderless, bool confinement, void (*log)(const char*)) {
    if (!borderless && !confinement) return true;
    if (base != 0x400000) return false;
    const WindowQoLProfiles::Profile* selected = nullptr;
    for (const auto& row : WindowQoLProfiles::profiles) if (row.build == build) selected = &row;
    if (!selected) return false;
    const auto& p = *selected;
    auto* creation = reinterpret_cast<unsigned char*>(base + p.creationRva);
    if (Fnv(creation, 1080) != p.creationFnv ||
        std::memcmp(reinterpret_cast<void*>(base + p.windowedPreferenceGuardRva), p.preferenceGuard, 19) ||
        std::memcmp(reinterpret_cast<void*>(base + p.mainWindowGuardRva), p.windowGuard, 12) ||
        (p.gogClipRva && Fnv(reinterpret_cast<unsigned char*>(base + p.gogClipRva), 109) != p.gogClipFnv)) return false;
    Patch patches[4] = {}; unsigned count = 0;
    if (borderless) {
        auto& patch = patches[count++]; patch.at = creation + 467; patch.size = 17;
        const unsigned char head[] = {0xC7,0x84,0x24,0xB4,0,0,0,2,0,0,0,0xE9};
        std::memcpy(patch.bytes, head, sizeof(head));
        const auto delta = static_cast<std::int32_t>((creation + 419) - (patch.at + 16));
        std::memcpy(patch.bytes + 12, &delta, 4); patch.bytes[16] = 0x90;
    }
    if (confinement) {
        for (unsigned offset : {140u,265u}) {
            auto& patch = patches[count++]; patch.at = creation + offset; patch.size = 4;
            const auto address = reinterpret_cast<std::uintptr_t>(&Procedure);
            std::memcpy(patch.bytes, &address, 4);
        }
        if (p.gogClipRva) {
            auto& patch = patches[count++]; patch.at = reinterpret_cast<unsigned char*>(base + p.gogClipRva); patch.size = 5;
            patch.bytes[0] = 0xE8;
            const auto delta = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&EffectiveGogModeThunk) - reinterpret_cast<std::uintptr_t>(patch.at + 5));
            std::memcpy(patch.bytes + 1, &delta, 4);
        }
    }
    profile = selected; image = base; original = reinterpret_cast<WNDPROC>(base + p.procedureRva); logger = log;
    if (!Commit(patches, count)) { profile = nullptr; return false; }
    Log("Window QoL installed: stock window modes; cursor shortcut Ctrl+Shift+F11 (windowed/focused only).");
    return true;
}
}
