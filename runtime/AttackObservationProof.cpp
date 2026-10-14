#include "AttackObservationProof.h"
#include <algorithm>
#include <cstring>
#include <set>

namespace MajestyAttackObservation {
int PackageProof::Find(const unsigned char* digest) const {
    if (digest) for (std::size_t i=0;i<digests.size();++i)
        if (!std::memcmp(digests[i].data(),digest,32)) return static_cast<int>(i);
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
