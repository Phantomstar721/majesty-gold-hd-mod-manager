#pragma once
#include <cstdint>
namespace MajestyCompactDiagnostic {
constexpr unsigned kClock=0x09435358;
struct Budget {
    bool started=false, stopped=false;
    std::uint64_t start=0;
    unsigned records=0;
    bool Arm(std::uint64_t now) {
        if(started)return false;
        started=true;start=now;records=1;return true;
    }
    bool Expired(std::uint64_t now) const { return started && now-start>=120000; }
    // Reserve the final record for an unambiguous terminal marker.
    bool Event(std::uint64_t now,unsigned attribute) {
        if(!started||stopped||Expired(now)||attribute==kClock||records>=255)return false;
        ++records;return true;
    }
    bool Stop() {
        if(!started||stopped)return false;
        stopped=true;++records;return true;
    }
};
struct Profile { unsigned table, slots[9], eventHash, setupHash; };
constexpr Profile profiles[]={
 {0x33eb04,{0xbc6c0,0xbcba0,0xbc720,0xbc770,0x53830,0x53840,0x53810,0x675a0,0xbcb50},0x9898c061,0x996359e3},
 {0x3577ec,{0xbd100,0xbd5e0,0xbd160,0xbd1b0,0x547b0,0x547c0,0x54790,0x687e0,0xbd590},0x0ce9dbe5,0x6990b9af},
 {0x356944,{0xbd700,0xbdbe0,0xbd760,0xbd7b0,0x546d0,0x546e0,0x546b0,0x68700,0xbdb90},0x06f607e5,0x170021dc}
};
inline unsigned Hash(const unsigned char* p,unsigned count) {
    unsigned hash=2166136261u;
    for(unsigned i=0;i<count;++i)hash=(hash^p[i])*16777619u;
    return hash;
}
}
