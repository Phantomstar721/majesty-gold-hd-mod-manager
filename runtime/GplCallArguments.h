#pragma once
#include <cstddef>

namespace MajestyGplCall {
// Return-value functions and stock scheduled callbacks address raw frame slots.
inline bool FrameSlot(unsigned index, std::size_t slots, unsigned& slot) {
    if (index >= slots) return false;
    slot = index;
    return true;
}
// Stock call38 supplies [implicit result, written argument 0, argument 1, ...].
// A procedure's explicit out parameter is still a written argument, not slot0.
// Raw scheduled-frame consumers must not use this translation.
inline bool ExplicitSlot(unsigned argument, std::size_t slots, unsigned& slot) {
    if (slots == 0 || argument >= slots - 1) return false;
    slot = argument + 1;
    return true;
}
}
