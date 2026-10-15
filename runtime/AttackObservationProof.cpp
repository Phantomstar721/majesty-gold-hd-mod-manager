#include "AttackObservationProof.h"
#include "AttackObservationBaseline.h"
#include <algorithm>
#include <cstring>
#include <set>

namespace MajestyAttackObservation {
int PackageProof::Find(const unsigned char* digest) const {
    if (digest) for (std::size_t i=0;i<digests.size();++i)
        if (!std::memcmp(digests[i].data(),digest,32)) return static_cast<int>(i);
    // The shipped SDK archives carry different debug-source records.
    // Their instructions, signatures and DAT records match the retail bundle.
    // Admit only these reviewed byte identities, and only against that complete
    // retail bundle; a path or filename never grants stock ownership.
    static const char* retail[]={
        "024e1b872e4b21d79677bca811ebb11a09a4434049c03d2c2f9d758fa04ee58f",
        "a5f4f612406506316e2b409b35f4e7014dbca4291143f8c888f040d5c15f6f91",
        "461f47f4e8ec83301be81f524013b1603a8251ca86a7f2ce13ddc192ebb49494",
        "0467f3cc06c676bdf7e77dece17673c2a651da66450b7dd3eb5acde066e26513",
        "3922797215f49906962b92dcd5411f707a9b0d7db31b0b9bc77e945d11353b7c",
        "308294eb59e05d620dde6b4f2691d8c312d10f7fd4dab76b3dfecd0cbc1b987f"};
    static const char* sdk[]={
        "7d258dfc4067f2a1376c12950a1148d50a4678a3e6f88fe2e2885445931b7a27",
        retail[1],
        "178e57097f67daf7d8c443b6078c2b66e8e9ff5f71359669ff640a0d8a3fceb5",
        "3269972da9b7b9ec42281d52d9c05c2c4c4dfc1a42832dff56e29dac47f540f9",
        "195e05881df63ed67bc618a2e646d012db68df74212cd2df6cbd4e4ebb3e5026",
        "19bca1c34d15fb22606d8232bbd7981c2c1c6ba1591bf61ccb0259db05aec4bf"};
    static const char* originalSdk[]={
        "715707fb88e75303c5991e80d0ce86528df9f48efb8c7b4860d28dd9239a36ea",
        retail[1],
        "b6bf02a542b12e4d890ce81e358ec2af39aec9c62a994420cab0d31e3059fec9",
        "bf5f79ffc0231dfcba319b057853b594763aad1daae6517043fa0f6003c8d78c",
        sdk[4],
        "8b572cfd429007ffd3f50eb11dbec5b39c2baa7bcbf640c565c0fc100a6bc9f7"};
    const auto matches=[](const unsigned char* bytes,const char* hex) {
        const auto digit=[](char c){return c<='9'?c-'0':c-'a'+10;};
        for(unsigned j=0;j<32;++j)
            if(bytes[j]!=(digit(hex[2*j])*16+digit(hex[2*j+1])))return false;
        return true;
    };
    if(!digest || digests.size()<6)return -1;
    bool publicBundle=true,originalBundle=true;
    for(unsigned i=0;i<6;++i) {
        publicBundle &= matches(digests[i].data(),retail[i]);
        originalBundle &= !std::memcmp(digests[i].data(),kBaselineDigests[i],32);
    }
    if(!publicBundle&&!originalBundle)return -1;
    for(unsigned i=0;i<6;++i)
        if(matches(digest,publicBundle?sdk[i]:originalSdk[i]))return static_cast<int>(i);
    return -1;
}
bool ParsePackageProof(const unsigned char* bytes,std::size_t size,PackageProof& output) {
    output={};
    if (!bytes || size<12 || size>1048576 || std::memcmp(bytes,"MMOB",4)) return false;
    std::size_t cursor=4;
    auto word=[&](std::uint32_t& v) {
        if (cursor+4>size) return false;
        v=bytes[cursor] | (std::uint32_t(bytes[cursor+1])<<8) |
          (std::uint32_t(bytes[cursor+2])<<16) | (std::uint32_t(bytes[cursor+3])<<24);
        cursor+=4; return true;
    };
    std::uint32_t version=0,count=0;
    if (!word(version) || (version!=3 && version!=4 && version!=7 && version!=8) || !word(count) || count<((version%2==0)?9u:7u) || count>256) return false;
    const auto baseVersion=(version-1)%4+1;
    PackageProof result;
    result.scoped=baseVersion==2||baseVersion==4;
    std::string* fields[]={&result.featureKey,&result.apiPrefix,&result.actor,&result.action,&result.projectile,&result.releaseCallback};
    for (unsigned field=0;field<(baseVersion<3?6u:0u);++field) {
        std::uint32_t length=0;
        if (!word(length) || !length || length>64 || cursor+length>size || (field==1 && length>46)) return false;
        const std::string text(reinterpret_cast<const char*>(bytes+cursor),length);
        const auto letter=[](unsigned char c) { return (c>='A'&&c<='Z') || (c>='a'&&c<='z'); };
        if (!letter(text[0]) && (field==0 || text[0]!='_')) return false;
        for (unsigned char c:text)
            if (!letter(c) && !(c>='0'&&c<='9') && c!='_' && !(field==0 && (c=='-' || c=='.'))) return false;
        if (text.size()>=3 && (text[0]=='M'||text[0]=='m') && (text[1]=='M'||text[1]=='m') && text[2]=='_') return false;
        *fields[field]=text;cursor+=length;
    }
    const char* suffixes[]={"AttackSettled","ReleaseId","ImpactId","BeginShotSnapshot","ShotPending","EndShotSnapshot","PayloadFull","ShotRetired"};
    auto lower=[](std::string text) { for (char& c:text) if (c>='A'&&c<='Z') c+=32;return text; };
    for (const char* suffix:suffixes)
        if (lower(result.releaseCallback)==lower(result.apiPrefix+"_"+suffix)) return false;
    if (size-cursor<count*32u) return false;
    std::set<std::array<unsigned char,32>> seen;
    for (unsigned i=0;i<count;++i) {
        std::array<unsigned char,32> digest{};
        std::memcpy(digest.data(),bytes+cursor,32);cursor+=32;
        if (!seen.insert(digest).second) return false;
        result.digests.push_back(digest);
    }
    if(version>4) {
        unsigned total=0;
        if(!word(total)||!total||total>4096)return false;
        std::string previous;
        for(unsigned i=0;i<total;++i) {
            unsigned length=0;
            if(!word(length)||!length||length>128||cursor+length>size)return false;
            std::string name(reinterpret_cast<const char*>(bytes+cursor),length);cursor+=length;
            for(unsigned j=0;j<length;++j) {
                const char c=name[j];
                if(!((c>='a'&&c<='z')||c=='_'||(j>(name[0]=='#'?1u:0u)&&c>='0'&&c<='9')||(j==0&&c=='#')))return false;
            }
            if(name=="#"||(!previous.empty()&&name<=previous))return false;
            previous=name;result.protectedNames.insert(name);
        }
    }
    if(cursor!=size)return false;
    output=std::move(result);return true;
}
bool LoadProof::Begin(int index) {
    // -2 is assigned only by the bounded non-overlap parser, never for an
    // unreadable, opaque or conflicting archive (-1).
    if (fault_ || (index<0&&index!=-2) || index>=256 || stack_.size()>=32) { fault_=true;return false; }
    if ((index==0||index==5) && stack_.empty() && completed_>=6) {
        started_=completed_=finished_=0;
    }
    if (index>=0 && index<(scoped_?9:7)) {
        const unsigned bit=1u<<index;
        if ((started_&bit) || (index>=6 && (completed_!=6 || !stack_.empty())) ||
            (index>=7 && (started_&((1u<<7)|(1u<<8))))) {
            fault_=true;return false;
        }
        started_|=bit;
    }
    stack_.push_back(index);return true;
}
bool LoadProof::Complete(int index,bool success) {
    if (fault_ || !success || stack_.empty() || stack_.back()!=index) { fault_=true;return false; }
    stack_.pop_back();
    if (index>=0 && index<6) {
        static constexpr int order[]={5,4,3,2,1,0};
        if (completed_>=6 || order[completed_]!=index) { fault_=true;return false; }
        ++completed_;
    } else if (index>=6 && index<(scoped_?9:7)) {
        finished_|=1u<<index;
    }
    return true;
}
}
