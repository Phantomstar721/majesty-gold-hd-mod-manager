#pragma once
#include <cstdint>
#include <limits>

namespace MajestyMovement {
constexpr int kInvalid = -1;
constexpr int kUnsupported = -2;
constexpr int kInvalidData = -3;

// Literal GSUnit movement interval rounding, with widened intermediates so
// malformed mod data fails instead of overflowing or dividing by zero.
inline int NormalInterval(int interval, int quantum) {
    if (quantum <= 0) return kInvalidData;
    std::int64_t value = interval;
    if (value >= quantum) {
        if (value + quantum / 2 > std::numeric_limits<int>::max()) return kInvalidData;
        value = ((value + quantum / 2) / quantum) * quantum;
    }
    if (value > std::numeric_limits<int>::max()) return kInvalidData;
    return value > 1 ? static_cast<int>(value) : 1;
}

inline int Rate(int distance, int interval) {
    // Stock converts distance<<16 with signed 32-bit Q16 division by 32.
    // Decline values that stock could not represent before that conversion.
    if (distance < 0 || distance > 32767 || interval <= 0) return kInvalidData;
    return static_cast<int>((static_cast<std::int64_t>(distance) << 11) / interval);
}
}  // namespace MajestyMovement
