#include "CheckedPlacementProof.h"
#include "CheckedPlacement.h"
#include <cstring>
namespace MajestyCheckedPlacement {
namespace {
bool Name(const unsigned char* bytes,std::size_t size,std::size_t& pos,std::string& out) {
    std::uint32_t length{};if(pos+4>size)return false;std::memcpy(&length,bytes+pos,4);pos+=4;
    if(!length||length>64||pos+length>size)return false;
    out.assign(reinterpret_cast<const char*>(bytes+pos),length);pos+=length;
    for(std::size_t i=0;i<out.size();++i) {
        const unsigned char c=out[i];const bool letter=(c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='_';
        if(!letter&&(!i||c<'0'||c>'9'))return false;
    }
    return _strnicmp(out.c_str(),"MM_",3)!=0;
}
}
bool ParsePlacementProof(const unsigned char* bytes,std::size_t size,PlacementProof& out) {
    out={};if(!bytes||size<44||size>512||std::memcmp(bytes,"MMPL",4))return false;
    std::uint32_t version{},range{};std::memcpy(&version,bytes+4,4);std::memcpy(&range,bytes+8,4);
    if((version!=1&&version!=2&&version!=3)||!range||range>MaximumRange)return false;
    PlacementProof next;std::size_t pos=44;
    if(!Name(bytes,size,pos,next.key)||!Name(bytes,size,pos,next.prefix)||!Name(bytes,size,pos,next.actor)||!Name(bytes,size,pos,next.action)||
        !Name(bytes,size,pos,next.release)||!Name(bytes,size,pos,next.callback)||
        (version>=2&&!Name(bytes,size,pos,next.arrival))||next.prefix.size()>46)return false;
    if(version>=2) {
        if(pos+(version==3?8:4)!=size)return false;
        std::memcpy(&next.imageId,bytes+pos,4);pos+=4;
        if(!next.imageId)return false;
    }
    if(version==3) {
        std::memcpy(&next.requiredLevel,bytes+pos,4);pos+=4;
        if(!next.requiredLevel||next.requiredLevel>1000)return false;
    }
    if(pos!=size)return false;
    if(version>=2&&!_stricmp(next.action.c_str(),next.arrival.c_str()))return false;
    const std::string names[]={next.prefix+"_Ready",next.prefix+"_Boundary",next.prefix+"_Begin",next.prefix+"_Commit",next.release,next.callback};
    for(unsigned i=0;i<6;++i)for(unsigned j=0;j<i;++j)if(!_stricmp(names[i].c_str(),names[j].c_str()))return false;
    next.range=static_cast<int>(range);std::memcpy(next.observerDigest.data(),bytes+12,32);out=std::move(next);return true;
}
}
