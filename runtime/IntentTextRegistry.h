#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace MajestyIntentText {

constexpr std::uint32_t kRegistryVersion = 1;
constexpr std::uint32_t kFirstPrivateIntentId = 0x60000000u;
constexpr std::uint32_t kLastPrivateIntentId = 0x6FFFFFFFu;
constexpr std::uint32_t kMaximumRecordCount = 65536u;
constexpr std::uint32_t kMaximumTextBytes = 16384u;
constexpr std::size_t kMaximumRegistryBytes = 16u * 1024u * 1024u;

struct RegistryRecord {
    std::uint32_t id;
    std::string text;
};

bool IsPrivateIntentId(std::uint32_t id);

// Parses the manager-owned, deterministic MMTX v1 wire format. The parser is
// deliberately independent of Win32 file I/O so malformed input can be tested
// without loading the injected runtime.
bool ParseRegistry(
    const unsigned char* bytes,
    std::size_t size,
    std::vector<RegistryRecord>* records,
    std::string* error);

}  // namespace MajestyIntentText
