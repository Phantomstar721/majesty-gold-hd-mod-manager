#pragma once
#include <cstdint>
namespace MajestyNativeImpact {
// Literal stock absorption branch. Caller has already retained native ownership.
template<class Animation, class Removal>
void FinishAbsorbed(std::uint32_t projectile, Animation animation, Removal removal) {
    if(!animation(projectile,0x60u,0x1005u,0u,0u,0u))removal(projectile);
}
}
