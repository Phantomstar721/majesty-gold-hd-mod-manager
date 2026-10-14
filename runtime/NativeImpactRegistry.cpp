#include "NativeImpactRegistry.h"
#include <cstring>
#include <set>
#include <tuple>
bool MajestyNativeImpact::Parse(const unsigned char* data,std::size_t size,Registry& output) {
    output={};
    if(!data || size<44 || size>320*1024 || std::memcmp(data,"MMIP",4))return false;
    std::size_t position=4;
    auto word=[&](std::uint32_t& result) {
        if(position+4>size)return false;
        std::memcpy(&result,data+position,4);position+=4;return true;
    };
    std::uint32_t version{},count{};
    if(!word(version)||version!=1||!word(count)||!count||count>1024)return false;
    Registry result;std::memcpy(result.proof.data(),data+position,32);position+=32;
    auto name=[&](std::string& result,bool description=false) {
        std::uint32_t length{};
        if(!word(length)||!length||length>(description?128u:64u)||position+length>size)return false;
        result.assign(reinterpret_cast<const char*>(data+position),length);position+=length;
        for(unsigned i=0;i<length;++i) {
            const auto c=result[i];
            if(description) { if(c<0x20||c>0x7E)return false;continue; }
            if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||c=='_'||(i&&c>='0'&&c<='9')))return false;
        }
        return true;
    };
    using Key=std::tuple<std::string,std::string,std::uint32_t,std::string>;
    Key previous{};bool first=true;
    for(unsigned i=0;i<count;++i) {
        Binding row;
        if(!word(row.id)||!row.id||!name(row.provider)||!name(row.projectile,true)||!name(row.script))return false;
        Key key{row.provider,row.projectile,row.id,row.script};
        if(!first && !(previous<key))return false;
        previous=key;first=false;result.bindings.push_back(std::move(row));
    }
    if(position!=size)return false;
    output=std::move(result);return true;
}
