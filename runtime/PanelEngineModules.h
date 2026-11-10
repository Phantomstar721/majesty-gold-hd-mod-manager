// Manager-owned alpha module ABI. Read once before native entrypoint resumes.
#pragma once
#include <cstdint>
#include <cstring>
namespace PanelEngineModules {
#pragma pack(push, 1)
struct Descriptor {
    char magic[8];
    std::uint32_t schema, service, branch, revision, headerSize, blobSize;
    std::uint32_t entry, ownsView, ownsController, hook, active, ownership;
    unsigned char original[5], patched[5], padding[2];
    unsigned char source[32], digest[32];
    std::uint32_t blobChecksum, oldFile, oldImage, oldCode, oldCount, oldChecksum;
};
#pragma pack(pop)
static_assert(sizeof(Descriptor) == 156, "Native module ABI changed");
inline std::uint32_t Checksum(const unsigned char* bytes, std::uint32_t size) {
    std::uint32_t result = 2166136261u;
    for (std::uint32_t i=0; i<size; ++i) result = (result ^ bytes[i])*16777619u;
    return result;
}
using Probe = int (__cdecl*)(void*);
struct State {
    Probe ownsView = nullptr, ownsController = nullptr;
    bool windowEngine = false, scriptFunctions = false;
};
// No vtable cloning or instance registry here. Both probes borrow the engine's
// own loaded-view/class registry; the engine retains its stock teardown owner.
inline bool ValidDescriptor(const unsigned char* data, std::uint32_t available,
                            std::uint32_t service, std::uint32_t branch) {
    if (available < 256) return false;
    const auto& d = *reinterpret_cast<const Descriptor*>(data);
    std::uint32_t checksum = 0;
    std::memcpy(&checksum, data+sizeof(d), 4);
    if (std::memcmp(d.magic,"MMENG001",8) || d.schema!=1 || d.service!=service ||
        d.branch!=branch || d.revision!=1 || d.headerSize!=256 || d.ownership!=1 ||
        d.active>1 || !d.blobSize || d.blobSize>available-256 ||
        d.entry>=d.blobSize || checksum!=Checksum(data,sizeof(d))) return false;
    for (unsigned i=sizeof(d)+4; i<256; ++i) if (data[i]) return false;
    if (service==1 && (d.ownsView>=d.blobSize || d.ownsController>=d.blobSize)) return false;
    static const unsigned char sources[2][32] = {
        {0xd6,0x04,0x9b,0x80,0x21,0x57,0x52,0x41,0x02,0x76,0x77,0xdb,0x2d,0xf4,0x41,0xcd,0xb5,0x0b,0xd0,0x03,0x87,0x35,0xc3,0xfd,0xa6,0x05,0x8b,0x70,0xd1,0xa4,0x0b,0x9b},
        {0x1c,0x34,0x2d,0x54,0xee,0xd8,0x16,0xf5,0xe8,0x5b,0xdd,0xa3,0x26,0x78,0x6d,0x91,0xcd,0x82,0xde,0xa0,0xe9,0x89,0xca,0xab,0x56,0x11,0x3e,0x09,0xeb,0x1e,0xba,0x6b}
    };
    static const std::uint32_t hooks[2][3]={{153925,157973,154533},{1674988,1760924,1757676}};
    static const unsigned char original[2][3][5]={
        {{0xe8,0xb6,0x52,0x0e,0},{0xe8,0x36,0x48,0x0f,0},{0xe8,0xb6,0x74,0x0e,0}},
        {{0xe9,0x6f,0xb1,0xe9,0xff},{0xe9,0xcf,0x70,0xe8,0xff},{0xe9,0x9f,0x7c,0xe8,0xff}}
    };
    if (!service || service>2 || branch>2 || d.hook!=hooks[service-1][branch] ||
        std::memcmp(d.source,sources[service-1],32) ||
        std::memcmp(d.original,original[service-1][branch],5)) return false;
    const unsigned char opcode=service==1?0xe8:0xe9;
    return d.original[0]==opcode && d.patched[0]==opcode &&
        Checksum(data+256,d.blobSize)==d.blobChecksum;
}
}
