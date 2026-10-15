#include "PaidSourceTargetCommand.h"
#include <climits>

namespace MajestyPaidSourceTarget {
namespace {
bool Valid(const Record& r) {
    // Full native identities, never a selected pointer or an index-only handle.
    return r.mode && r.player < 8 && r.source && r.source <= 0x1FFFFF &&
        r.target && r.target <= 0x1FFFFF && r.gold <= INT_MAX;
}
void Store(unsigned char* p, std::uint32_t v) {
    for(unsigned i=0;i<4;++i) p[i]=static_cast<unsigned char>(v>>(8*i));
}
std::uint32_t Load(const unsigned char* p) {
    std::uint32_t v{};for(unsigned i=0;i<4;++i)v|=std::uint32_t(p[i])<<(8*i);return v;
}
}
bool Encode(const Record& r, Payload& out) {
    out.fill(0);if(!Valid(r)||r.toolbarControl)return false;
    const std::uint32_t values[]={r.mode,r.context,r.player,r.x,r.y,r.target,r.gold,r.source};
    for(unsigned i=0;i<8;++i)Store(out.data()+4*i,values[i]);return true;
}
bool EncodeToolbar(const Record& r,ToolbarPayload& out) {
    out.fill(0);
    if(!Valid(r)||!r.toolbarControl||r.toolbarControl>65535)return false;
    Record base=r;base.toolbarControl=0;
    Payload prefix;
    if(!Encode(base,prefix))return false;
    for(std::size_t i=0;i<prefix.size();++i)out[i]=prefix[i];
    Store(out.data()+PayloadSize,r.toolbarControl);
    return true;
}
bool Decode(std::uint16_t tag,const void* bytes,std::size_t length,Record& out) {
    out={};if(!bytes)return false;
    const bool toolbar=tag==ToolbarCommandTag;
    if((!toolbar&&tag!=CommandTag)||length!=(toolbar?ToolbarPayloadSize:PayloadSize))return false;
    const auto* p=static_cast<const unsigned char*>(bytes);
    Record r{Load(p),Load(p+4),Load(p+8),Load(p+12),Load(p+16),Load(p+20),Load(p+24),Load(p+28)};
    if(toolbar) {
        r.toolbarControl=Load(p+PayloadSize);
        if(!r.toolbarControl||r.toolbarControl>65535)return false;
    }
    if(!Valid(r))return false;out=r;return true;
}
}
