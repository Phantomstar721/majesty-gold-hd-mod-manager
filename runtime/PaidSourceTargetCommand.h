#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace MajestyPaidSourceTarget {
// Independently tagged extension. Neither the stock 03F1 record nor Manager v2
// changes length or assigns a new meaning to its seven existing words.
constexpr std::uint16_t CommandTag = 0x7F31;
constexpr std::size_t PayloadSize = 32;
// Toolbar origin is a separate version/tag, never a reinterpretation of v3.
constexpr std::uint16_t ToolbarCommandTag = 0x7F32;
constexpr std::size_t ToolbarPayloadSize = 36;
struct Record {
    std::uint32_t mode{}, context{}, player{}, x{}, y{}, target{}, gold{}, source{};
    std::uint32_t toolbarControl{};
};
using Payload = std::array<unsigned char, PayloadSize>;
using ToolbarPayload = std::array<unsigned char, ToolbarPayloadSize>;
bool Encode(const Record&, Payload&);
bool EncodeToolbar(const Record&, ToolbarPayload&);
// A failed decode clears its output; no previous queued identity survives.
bool Decode(std::uint16_t tag, const void* bytes, std::size_t length, Record&);
}
