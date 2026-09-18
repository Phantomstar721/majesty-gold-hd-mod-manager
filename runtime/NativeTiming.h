#pragma once
#include <cstdint>
#include <limits>

namespace MajestyNativeTiming {
constexpr int kInvalid = -1;
constexpr int kNoExpiry = -2;
constexpr int kUnsupported = -3;
constexpr int kUndeclared = -4;

// Literal unsigned subtraction used by the native order and spell predicates.
// Saturate the positive return value to GPL's signed integer range, not the
// underlying native clock or saved state.
inline int Elapsed(std::uint32_t now, std::uint32_t started) {
    const auto elapsed = now-started;
    const auto maximum = static_cast<std::uint32_t>(std::numeric_limits<int>::max());
    return static_cast<int>(elapsed > maximum ? maximum : elapsed);
}
inline int Remaining(std::uint32_t now, std::uint32_t started,
                     std::uint32_t duration, std::uint32_t flags) {
    if (flags & 1u) return kNoExpiry;
    const auto elapsed = now-started;
    return elapsed >= duration ? 0 : Elapsed(duration, elapsed);
}
}
