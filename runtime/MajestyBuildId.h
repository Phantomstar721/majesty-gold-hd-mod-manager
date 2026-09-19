#pragma once
#include <cstdint>

// Explicit executable identity. Never interpret an unknown build as beta2.
enum class MajestyBuildId : std::uint8_t { SteamPublic, SteamBeta2, Gog };
