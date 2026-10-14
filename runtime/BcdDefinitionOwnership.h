#pragma once
#include <cstdint>
#include <cstddef>
#include <string>
#include <set>
#include <map>

// Port of majesty_cam.bcd.definition_keys: table framing only, no bytecode
// execution or heuristic string scan. Unreadable/unknown never means empty.
namespace MajestyBcdOwnership {
struct Reader {
    const unsigned char* data; std::size_t pos,end;
    bool Word(std::uint32_t& value) {
        if(pos>end || end-pos<4)return false;
        value=data[pos]|(std::uint32_t(data[pos+1])<<8)|
            (std::uint32_t(data[pos+2])<<16)|(std::uint32_t(data[pos+3])<<24);
        pos+=4;return true;
    }
    bool Block(std::uint32_t version,Reader& body) {
        const auto start=pos;std::uint32_t size=0,actual=0;
        if(!Word(size)||size<16||size>end-start||!Word(actual)||actual!=version)return false;
        const auto stop=start+size;
        Reader footer{data,stop-8,stop};std::uint32_t a=1,b=0;
        if(!footer.Word(a)||!footer.Word(b)||a||b!=0xffffffffu)return false;
        body={data,pos,stop-8};pos=stop;return true;
    }
    bool Name(bool expression,std::string& name) {
        name.clear();
        if(expression) { if(pos>=end||data[pos++]!='#')return false;name='#'; }
        bool first=true;
        while(pos<end) {
            unsigned char c=data[pos++];
            if(!c)return !first;
            if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='_'||(!first&&c>='0'&&c<='9')))return false;
            if(name.size()>=128)return false;
            name+=static_cast<char>(c);first=false;
        }
        return false;
    }
};
using Key=std::pair<unsigned,std::string>;
using Definitions=std::set<Key>;
inline std::string Lower(std::string name) {
    for(char& c:name)if(c>='A'&&c<='Z')c+=32;
    return name;
}
inline bool ReadDefinitions(const unsigned char* data,std::size_t size,Definitions& output) {
    output.clear();Definitions result;
    if(!data||size<4||size>64u*1024u*1024u)return false;
    Reader file{data,0,size},root{},instructions{},symbols{},records{};
    std::uint32_t length=0,error=1;
    if(!file.Word(length)||length!=size-4||!file.Block(0xffffffffu,root)||file.pos!=file.end||
       !root.Word(error)||error||!root.Block(0,instructions)||!root.Block(1,symbols))return false;
    for(unsigned kind=0;kind<3;++kind) {
        std::uint32_t count=0;
        if(!symbols.Word(count)||count>(symbols.end-symbols.pos)/17)return false;
        std::set<std::string> seen;
        for(unsigned i=0;i<count;++i) {
            std::string name;Reader body{};
            if(!symbols.Name(kind==2,name)||!seen.insert(name).second||
               !symbols.Block(1,body))return false;
            result.insert({kind,name});
        }
    }
    if(symbols.pos!=symbols.end||!root.Block(1,records))return false;
    std::uint32_t count=0;
    if(!records.Word(count)||count>(records.end-records.pos)/17)return false;
    std::set<std::string> seen;
    for(unsigned i=0;i<count;++i) {
        std::string name;Reader body{};
        if(!records.Name(false,name)||!seen.insert(Lower(name)).second||
           !records.Block(1,body))return false;
        result.insert({3,Lower(name)});
    }
    if(records.pos!=records.end||root.pos!=root.end)return false;
    output=std::move(result);return true;
}
inline bool NonOverlapping(const unsigned char* data,std::size_t size,
                           const std::set<std::string>& protectedNames) {
    Definitions definitions;
    if(protectedNames.empty()||!ReadDefinitions(data,size,definitions))return false;
    for(const auto& key:definitions)if(protectedNames.count(Lower(key.second)))return false;
    return true;
}

// A category1 reverse list is one publication batch, closed before postload.
// Namespace and exact symbol spelling are retained; never infer a winner from
// a filename or from an earlier batch whose catalogs may have been released.
class BatchOwnership {
    std::map<Key,bool> first_;
    bool generatedCompleted_{};
public:
    void Reset() { first_.clear(); generatedCompleted_=false; }
    // Caller must first establish the exact audited baseline digest. Unlike an
    // optional mod, that baseline may supply protected stock callbacks which
    // the generated package deliberately leaves unchanged.
    bool BaselineRetainsWinners(const Definitions& definitions,const std::set<std::string>& protectedNames) const {
        if(!generatedCompleted_ || protectedNames.empty())return false;
        for(const auto& key:definitions) {
            if(!protectedNames.count(Lower(key.second)))continue;
            for(const auto& entry:first_)
                if(entry.first.first==key.first && entry.first.second!=key.second &&
                   Lower(entry.first.second)==Lower(key.second))return false;
        }
        return true;
    }
    int ContinuationIndex(int index,bool categoryFile,bool ready,const Definitions& definitions,
                          const std::set<std::string>& protectedNames) const {
        return index>=0 && index<6 && categoryFile && ready &&
            BaselineRetainsWinners(definitions,protectedNames) ? -2 : index;
    }
    bool Admit(const Definitions& definitions,const std::set<std::string>& protectedNames,
               bool generated,bool baseline) const {
        for(const auto& key:definitions) {
            if(!protectedNames.count(Lower(key.second)))continue;
            const auto prior=first_.find(key);
            if(generated) {
                if(prior!=first_.end()&&!prior->second)return false;
                // Tape keys fold case, while symbol keys do not. A case-only
                // competing spelling cannot establish consistent ownership.
                for(const auto& entry:first_)
                    if(entry.first.first==key.first && entry.first.second!=key.second &&
                       Lower(entry.first.second)==Lower(key.second))return false;
            } else if(!baseline && (prior==first_.end()||!prior->second))return false;
        }
        return true;
    }
    void Complete(const Definitions& definitions,const std::set<std::string>& protectedNames,bool generated) {
        generatedCompleted_ |= generated;
        for(const auto& key:definitions)
            if(protectedNames.count(Lower(key.second)))first_.emplace(key,generated);
    }
};
}
