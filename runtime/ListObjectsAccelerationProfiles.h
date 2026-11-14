#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

// Stock $ListObjects boundary, one row per audited executable. Each row is
// produced and checked by scripts/audit_listobjects_acceleration.py from the
// pristine executable; see docs/listobjects-acceleration.md. Every helper and
// global the accelerated filter uses is decoded at install time from the
// hash-verified stock filter and property-lookup bodies, so a row holds only
// the two function RVAs and the FNV-1a hashes of the guarded bodies.
namespace ListObjectsAccelerationProfiles {
struct Profile {
    MajestyBuildId build;
    std::uint32_t listObjects, filter;
    std::uint32_t listObjectsHash, filterHash, getPropertyHash, pushBackHash,
        resolveAgentHash, attributeLookupHash;
};

constexpr Profile kProfiles[] = {
    {MajestyBuildId::SteamPublic, 0x39050, 0x38D70,
        0xF98E8B9A, 0xDD6CFAEA, 0x87381384, 0x2E7ECBE4, 0x0BE4E1D3, 0x831E74FA},
    {MajestyBuildId::SteamBeta2, 0x39F60, 0x39C80,
        0x59E8EA25, 0x47263EA4, 0x4CA3B34C, 0x397A71F6, 0xFB4D3B73, 0xFC558268},
    {MajestyBuildId::Gog, 0x39E80, 0x39BA0,
        0x5658D174, 0xD15F4A84, 0x89A15D4E, 0x941CD4DA, 0xFB4D3B73, 0x38FCFDEE},
};

// Guarded body sizes and decode offsets: the instruction layout is identical
// on every audited build (the audit script checks the opcode in front of each
// operand).
constexpr std::uint32_t kListObjectsSize = 0x674;  // code before the modifier jump table
constexpr std::uint32_t kFilterSize = 0x2D1;       // the whole callback, through its RET
constexpr std::uint32_t kGetPropertySize = 0xA3;
constexpr std::uint32_t kPushBackSize = 0x32;
constexpr std::uint32_t kResolveAgentSize = 0x8;
constexpr std::uint32_t kAttributeLookupSize = 0x65;
constexpr std::uint32_t kPushSite = 0x432;  // PUSH <filter> between PUSH 0, PUSH 0 and CALL EAX

namespace FilterOperand {
constexpr std::uint32_t Inside = 0x37, Anchor = 0x44, PointGiven = 0x52, Point = 0x5A,
    UnitPosition = 0x68, RectDistance = 0x70, AnchorDistance = 0x78, RangeLimit = 0x81,
    PlayerFilter = 0x94, TeamFilter = 0xCE, TeamTable = 0xDE, TeamOf = 0xE3,
    ComponentFind = 0x142, AgentRefCtor = 0x154, TypeKey = 0x161, GetProperty = 0x16A,
    TypeString = 0x170, StricmpImport = 0x177, CheckKey = 0x19E, CheckString = 0x1A8,
    AttributeCount = 0x1DD, AttributeIds = 0x1E8, UnitAttribute = 0x1F2,
    AttributeValues = 0x1F9, GplManager = 0x209, ValueNew = 0x213, AgentRefDtor = 0x248,
    Results = 0x266, PushBack = 0x273, FirstOnly = 0x279;
}
namespace GetPropertyOperand {
constexpr std::uint32_t GplManager = 0x2B, ResolveAgent = 0x32, AttributeLookup = 0x4B;
}
}  // namespace ListObjectsAccelerationProfiles
