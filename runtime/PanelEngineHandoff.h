#pragma once
// Private x86 module handshake, not a GPL/authoring API. The existing controller
// remains the action owner; the Window Engine remains the outer presenter.
namespace PanelEngineHandoff {
struct Callbacks {
    unsigned size, revision;
    void (__cdecl* capture)(void* controller, void* view, void* unit);
    int (__cdecl* describe)(void** managed, unsigned* count, void** locator);
    int (__cdecl* wrapped)(void* controller, void** managed, void** presenter);
};
using Bind = int (__cdecl*)(const Callbacks*);
}
