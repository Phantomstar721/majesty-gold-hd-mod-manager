#pragma once
#include <cstdint>
#include <cstring>
#include <vector>
#include "MajestyBuildId.h"
// Same append-tolerant section identity as the existing Manager/QoL selector.
// This is only identity admission: every consumed native body is also guarded.
namespace MajestyFeatureImage {
struct Section { const char* name; unsigned size,rva,rawSize,rawOffset,flags; };
inline bool Matches(const std::vector<unsigned char>& bytes, MajestyBuildId build) {
    if(bytes.size()<0x400 || bytes[0]!='M' || bytes[1]!='Z')return false;
    auto u16=[&](unsigned p){unsigned short v;std::memcpy(&v,bytes.data()+p,2);return v;};
    auto u32=[&](unsigned p){unsigned v;std::memcpy(&v,bytes.data()+p,4);return v;};
    unsigned pe=u32(0x3c);
    if(pe>0x300 || u32(pe)!=0x4550 || u16(pe+4)!=0x14c || u16(pe+20)!=0xe0)return false;
    unsigned n=u16(pe+6), opt=pe+24, table=opt+0xe0;
    if(n<4 || table+n*40>0x400 || u16(opt)!=0x10b || u32(opt+28)!=0x400000 ||
       u32(opt+32)!=0x1000 || u32(opt+36)!=0x200 || u32(opt+60)!=0x400)return false;
    static const Section sections0[]={
        {".text",3358333u,4096u,3358720u,1024u,1610612768u},
        {".rdata",518284u,3362816u,518656u,3359744u,1073741888u},
        {".data",361068u,3883008u,51200u,3878400u,3221225536u},
        {".rsrc",3892u,4247552u,4096u,3929600u,1073741888u},
    };
    static const Section sections1[]={
        {".text",3457549u,4096u,3458048u,1024u,1610612768u},
        {".rdata",538972u,3465216u,539136u,3459072u,1073741888u},
        {".data",364020u,4005888u,53760u,3998208u,3221225536u},
        {".rsrc",3892u,4370432u,4096u,4051968u,1073741888u},
    };
    static const Section sections2[]={
        {".text",3456765u,4096u,3457024u,1024u,1610612768u},
        {".rdata",541688u,3461120u,541696u,3458048u,1073741888u},
        {".data",364684u,4005888u,54272u,3999744u,3221225536u},
        {".rsrc",3892u,4374528u,4096u,4054016u,1073741888u},
    };
    const Section* expected=nullptr; unsigned timestamp=0;
    switch(build) {
    case MajestyBuildId::SteamPublic:expected=sections0;timestamp=1486337839u;break;
    case MajestyBuildId::SteamBeta2:expected=sections1;timestamp=1518997973u;break;
    case MajestyBuildId::Gog:expected=sections2;timestamp=1539018168u;break;
    default:return false;
    }
    if(u32(pe+8)!=timestamp)return false;
    for(unsigned i=0;i<n;++i) {
        unsigned p=table+i*40, size=u32(p+16), offset=u32(p+20);
        if(size && (offset<0x400 || offset>bytes.size() || size>bytes.size()-offset))return false;
        if(i>=4)continue;
        const auto& e=expected[i];char name[8]{};std::memcpy(name,e.name,std::strlen(e.name));
        if(std::memcmp(bytes.data()+p,name,8)||u32(p+8)!=e.size||u32(p+12)!=e.rva||
           size!=e.rawSize||offset!=e.rawOffset||u32(p+36)!=e.flags)return false;
    }
    return true;
}
}
