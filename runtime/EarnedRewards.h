#pragma once
#include <cstdint>
#include <limits>

namespace MajestyEarnedRewards {
// GPL integer binary arithmetic converts through Q22.10, including comparisons.
// Keep reward math native; the saved carry and stock settlement still own state.
inline int CapAdd(int base, int bonus) {
    if (base <= 0 || bonus <= 0) return base;
    const auto sum = std::int64_t(base) + bonus;
    return sum > (std::numeric_limits<int>::max)() ?
        (std::numeric_limits<int>::max)() : static_cast<int>(sum);
}
inline int Bonus(int base, int percent, int& carry) {
    if (base <= 0 || percent <= 0 || percent > 100 || carry < 0 || carry >= 100)
        return 0;
    const auto hundredths = std::int64_t(base) * percent + carry;
    carry = static_cast<int>(hundredths % 100);
    return static_cast<int>(hundredths / 100);
}
}
