#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
namespace MajestyCheckedPlacement {
struct PlacementProof {
    std::string key,prefix,actor,action,release,callback,arrival;
    int range{};
    std::uint32_t imageId{};
    std::uint32_t requiredLevel{};
    std::array<unsigned char,32> observerDigest{};
};
bool ParsePlacementProof(const unsigned char*,std::size_t,PlacementProof&);
}
