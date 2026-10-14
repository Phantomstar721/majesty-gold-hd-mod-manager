#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

namespace MajestyAttackObservation {
enum class AttachmentRoute { None, Saved, Created };
struct WorldAttachmentProfile {
    std::uint32_t savedReturn, createdReturn, builder, builderHash, callerHash;
    std::uint32_t attach, attachHash, serviceSlot;
    std::uint32_t creationReturn2, creationHash2, creationReturn3, creationHash3;
    AttachmentRoute Classify(std::uintptr_t caller, unsigned mode,
                             std::uint32_t world, int loadStatus,
                             std::uint32_t loadedWorld) const {
        if (!world) return AttachmentRoute::None;
        if (caller==savedReturn && (mode==0 || mode==3) &&
            loadStatus==0 && loadedWorld==world) return AttachmentRoute::Saved;
        // These guarded callers pass the completed builder's returned world,
        // not a saved-game loader output. Nonnull and actual mode0 are required
        // here even for the caller that supplies mode through a register.
        if ((caller==createdReturn || caller==creationReturn2 || caller==creationReturn3) && mode==0)
            return AttachmentRoute::Created;
        return AttachmentRoute::None;
    }
};
inline const WorldAttachmentProfile* WorldAttachmentFor(MajestyBuildId build) {
    static const WorldAttachmentProfile publicBuild{0x4252C1,0x4946FF,0x4E96D0,0x1F4711A8,0xC4C47D10,0x424CC0,0xFCA525E8,0x20,0x46F019,0x3DD1EEC5,0x48C85A,0x3B0B9F98};
    static const WorldAttachmentProfile betaBuild{0x426291,0x494EAF,0x4E9C90,0x441781EE,0x23E2DADB,0x425C90,0x520C36EC,0x1C,0x47031A,0xA04C5C45,0x48BAA6,0x96C109A5};
    static const WorldAttachmentProfile gogBuild{0x425521,0x49545F,0x4EA3D0,0x9EE854B3,0x751F5191,0x424F20,0xF0A90751,0x1C,0x47027D,0xA92A0EB2,0x48BE6B,0x83D1B35A};
    switch (build) {
        case MajestyBuildId::SteamPublic:return &publicBuild;
        case MajestyBuildId::SteamBeta2:return &betaBuild;
        case MajestyBuildId::Gog:return &gogBuild;
    }
    return nullptr;
}
}
