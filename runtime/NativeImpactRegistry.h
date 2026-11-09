#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
namespace MajestyNativeImpact {
struct Binding { std::uint32_t id{};std::string provider,projectile,script; };
struct Registry { std::array<unsigned char,32> proof{};std::vector<Binding> bindings; };
bool Parse(const unsigned char*,std::size_t,Registry&);
}
