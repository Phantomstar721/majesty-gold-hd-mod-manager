#pragma once

namespace MajestyPanelEngine {
using AssociatedUnit = void* (__fastcall*)(void* agent, void* unusedEdx);

// The stock reference resolver rejects a null or deleted GPL agent before
// requesting its associated unit. The three-build client proof pins byte38.
// Input must be borrowed from the stock lookup during this synchronous call;
// this does not validate arbitrary pointers or certify actor lifetime.
inline void* ResolveLiveAgentUnit(void* agent, AssociatedUnit resolve) {
    if (!agent || !resolve || static_cast<const unsigned char*>(agent)[0x38])
        return nullptr;
    return resolve(agent, nullptr);
}
}
