#pragma once
#include "GogVisitorCompatibility.h"
#include <cstddef>
#include <cstdint>

// Fixed GOG 1.5.2.28 ranges from docs/gog-runtime-audit.json.
// Only the selected capability reads these bounded ranges; no search is used.
namespace MajestyGogAudit {
struct Range { std::uintptr_t rva; std::size_t size; std::uint32_t hash;
    std::size_t skipOffset; std::size_t skipSize; };
constexpr Range kCore[] = {
    {0x0010D060, 5201, 0x85251067u, 5183, 18}, // dialog factory
    {0x00096B90, 314, 0xD552D538u, 0, 0}, // guild construction
};
constexpr Range kFreestyle[] = {
    {0x002868A0, 219, 0x0CF3E84Au, 0, 0}, // freestyle 0x2873b0
    {0x00286980, 141, 0x3F2E5B1Eu, 0, 0}, // freestyle 0x287490
    {0x00287210, 156, 0xDAFECCEBu, 0, 0}, // freestyle 0x287d20
    {0x00286DA0, 1021, 0x3C610043u, 0, 0}, // freestyle 0x2878b0
    {0x00271150, 98, 0xCDB25CE3u, 0, 0}, // freestyle 0x271c60
    {0x00283AE0, 164, 0x9AEA04D2u, 0, 0}, // freestyle 0x2845f0
    {0x00281060, 93, 0x85D993A6u, 0, 0}, // freestyle 0x281b70
    {0x0025B2A0, 11, 0x6D5135AAu, 0, 0}, // freestyle 0x25bdb0
    {0x002D2970, 141, 0xCCB33E20u, 0, 0}, // freestyle 0x2d3480
    {0x0023B1A0, 604, 0x85F3EFFFu, 0, 0}, // freestyle 0x246430
};
constexpr Range kNames[] = {
    {0x00112650, 1857, 0x6F36E33Bu, 0, 0}, // name registry
    {0x0010E4D0, 177, 0x9875D48Eu, 0, 0}, // name factory
    {0x0010CFD0, 131, 0x32971D7Cu, 0, 0}, // name construction
    {0x00111FD0, 169, 0x24E80563u, 0, 0}, // name insertion
    {0x0010E700, 46, 0xBBE9C79Bu, 0, 0}, // name wrapper destruction
};
constexpr Range kIntent[] = {
    {0x0010ADE0, 67, 0x0BE57809u, 0, 0}, // intent resolver
    {0x00174330, 9, 0xA5E6C345u, 0, 0}, // intent provider
    {0x0023CC40, 145, 0x4B93B085u, 0, 0}, // stock string assignment
};
constexpr Range kEnchantments[] = {
    {0x0023CC40, 145, 0x4B93B085u, 0, 0}, // stock string assignment
    {0x000A41B0, 3832, 0xB0D8F7C2u, 0, 0}, // enchantment rows
};
constexpr Range kRegistration[] = {
    {0x00174330, 9, 0xA5E6C345u, 0, 0}, // intent provider
    {0x001AD1E0, 17, 0x795F0874u, 0, 0}, // registration dispatch
    {0x001D4F40, 4398, 0x60B3E5C0u, 0, 0}, // registration functions
    {0x00180FF0, 305, 0x8CF1E2EAu, 0, 0}, // registration insert
    {0x0023C370, 69, 0x22529BDFu, 0, 0}, // registration string construction
    {0x0002EC20, 105, 0x355CD831u, 0, 0}, // registration argument accessor
    {0x0023C520, 33, 0x788DA9A2u, 0, 0}, // registration string destruction
};
constexpr Range kMap[] = {
    {0x001D0C80, 81, 0xEF65C4B2u, 0, 0}, // map extents
    {0x001D2F20, 505, 0xA0716919u, 0, 0}, // map hidden coordinate
    {0x001D2CD0, 582, 0xB1A065C5u, 0, 0}, // map path cost
    {0x001D7420, 1828, 0xD1F8F619u, 0, 0}, // map rectangle search
};
constexpr Range kMovement[] = {
    {0x000329E0, 318, 0x5AC7F07Cu, 0, 0}, // movement change type
    {0x0016DF60, 43, 0x480F562Eu, 0, 0}, // movement resolve live unit
    {0x001C2350, 150, 0x62F86517u, 0, 0}, // movement find description
    {0x001CE3E0, 10, 0x5387E78Du, 0, 0}, // movement base interval
    {0x00048810, 73, 0x04B028CCu, 0, 0}, // movement effective interval
    {0x001CE300, 62, 0xA26C6346u, 0, 0}, // movement attachment selection
    {0x001CE2C0, 33, 0x0CDE635Bu, 0, 0}, // movement packed attribute
    {0x001E23B0, 179, 0x73C75413u, 0, 0}, // movement step
    {0x002175C0, 149, 0xCD704C98u, 0, 0}, // movement construction
    {0x00217AF0, 107, 0xC6DA8250u, 0, 0}, // movement derived data
};
constexpr Range kTiming[] = {
    {0x000310B0, 469, 0x00E4936Eu, 0, 0}, // timing cast spell
    {0x00030E80, 555, 0xB6B78D81u, 0, 0}, // timing spell availability
    {0x001D3BF0, 230, 0x2A5D947Du, 0, 0}, // timing check effector
    {0x001DDB00, 21, 0x3AF7B250u, 0, 0}, // timing effector getter
    {0x001DE360, 41, 0xA6554E28u, 0, 0}, // timing order getter
    {0x00221D50, 35, 0xD90B5557u, 0, 0}, // timing refresh effector
    {0x002114B0, 26, 0xABA3F551u, 0, 0}, // timing expiry predicate
    {0x001CE270, 13, 0x4DC446E1u, 0, 0}, // timing base action period
    {0x000488B0, 145, 0x5F8159A1u, 0, 0}, // timing effective action period
    {0x001C3EE0, 141, 0x31F183F5u, 0, 0}, // timing action construction
    {0x001C41C0, 366, 0x0DD44E4Cu, 0, 0}, // timing action XML loading
    {0x001C4110, 174, 0xE6856D6Eu, 0, 0}, // timing action binary loading
    {0x0004D030, 634, 0x1C028BC0u, 0, 0}, // timing vehicle serialization
    {0x0004D480, 97, 0x0F36A6BFu, 0, 0}, // timing vehicle destruction
    {0x0004D560, 106, 0xAF519597u, 0, 0}, // timing vehicle construction
    {0x00221D20, 39, 0xFF576D57u, 0, 0}, // timing expiry order installation
    {0x00221CF0, 43, 0x417FF1F9u, 0, 0}, // timing expiry callback
    {0x00221BA0, 327, 0x379BA80Au, 0, 0}, // timing effector cleanup
    {0x00210C00, 115, 0x81900F80u, 0, 0}, // timing order save
    {0x00210B70, 138, 0x0C018C2Au, 0, 0}, // timing order load
    {0x001DDB90, 406, 0x165F73D5u, 0, 0}, // timing add effector
    {0x001D3960, 547, 0x8D1BDD2Bu, 0, 0}, // timing create effector
    {0x001D3B90, 92, 0xDAB1365Du, 0, 0}, // timing delete effector
    {0x001C23F0, 165, 0x2CD6F0D3u, 0, 0}, // timing find unit description
};
inline bool Validate(std::uintptr_t base, const Range* ranges, std::size_t count) {
    if (base != 0x00400000) return false;
    for (std::size_t r = 0; r < count; ++r) {
        const auto& range = ranges[r];
        bool visitorOverlap = false;
        for (const auto& site : kVisitorSites)
            visitorOverlap = visitorOverlap || (range.rva < site.rva + site.size &&
                range.rva + range.size > site.rva);
        if (visitorOverlap && !ValidateVisitorOverlay(base)) return false;
        const auto* bytes = reinterpret_cast<const unsigned char*>(base + range.rva);
        std::uint32_t hash = 2166136261u;
        for (std::size_t i = 0; i < range.size; ++i) {
            const bool skip = i >= range.skipOffset && i < range.skipOffset + range.skipSize;
            const auto value = visitorOverlap ? StockVisitorByte(range.rva + i, bytes[i]) : bytes[i];
            hash = (hash ^ (skip ? 0u : value)) * 16777619u;
        }
        if (hash != range.hash) return false;
    }
    return true;
}
} // namespace MajestyGogAudit
