#pragma once
#include <array>
#include <cstdint>
namespace MajestyCheckedPlacement {
// Fixed process lifetime budget: no eviction, resets, allocation or actor scans.
struct DiagnosticBudget {
    struct Entry { unsigned actor{}; std::uint64_t reasons{}; };
    std::array<Entry,8> entries{};
    unsigned emitted{};
    bool Take(unsigned actor,unsigned reason) {
        if(!actor||reason>=64||emitted>=96)return false;
        for(auto& entry:entries) {
            if(entry.actor && entry.actor!=actor)continue;
            const auto bit=std::uint64_t{1}<<reason;
            if(entry.reasons&bit)return false;
            entry.actor=actor;entry.reasons|=bit;++emitted;return true;
        }
        return false;
    }
};
}
