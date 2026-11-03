#include "../runtime/MessageFlagHudLayout.h"
#include <cassert>
#include <cstdio>
#include <io.h>
#include <fcntl.h>
using namespace MajestyMessageFlagHud;

int main() {
    _setmode(_fileno(stdin), _O_BINARY);
    std::vector<unsigned char> bytes;
    unsigned char buffer[4096];
    std::size_t count;
    while ((count=std::fread(buffer,1,sizeof(buffer),stdin)) != 0) {
        bytes.insert(bytes.end(),buffer,buffer+count);
        if(bytes.size()>MaximumStreamBytes)return 2;
    }
    std::vector<std::uint32_t> result;
    if(!Extend(bytes.data(),bytes.size(),result))return 3;
    std::vector<std::uint32_t> original(bytes.size()/4);
    std::memcpy(original.data(),bytes.data(),bytes.size());
    std::vector<Record> before,after;
    std::size_t a=0,b=0;
    assert(Parse(original,before,a)&&Parse(result,after,b));
    assert(after.size()==before.size()+2);
    for(std::size_t i=0;i<before.size();++i) {
        const auto& old=before[i];const auto& now=after[i];
        const auto* id=old.Find(6);
        assert(old.end-old.begin==now.end-now.begin);
        for(std::size_t j=0;j<old.end-old.begin;++j) {
            if(id&&original[id->value]==2004 &&
               (old.begin+j==old.Find(2)->value+2 || old.begin+j==old.Find(42)->value+2)) {
                assert(result[now.begin+j]<original[old.begin+j]);
            } else assert(result[now.begin+j]==original[old.begin+j]);
        }
    }
    for(unsigned i=0;i<2;++i) {
        const auto& row=after[before.size()+i];
        assert(result[row.Find(6)->value]==(i?ClearControl:ToggleControl));
        assert(!row.Find(5)&&!row.Find(258)&&!row.Find(266));
    }
    std::vector<std::uint32_t> rejected;
    assert(!Extend(reinterpret_cast<const unsigned char*>(result.data()),result.size()*4,rejected));
    assert(rejected.empty());
    assert(!Extend(bytes.data(),bytes.size()-1,rejected));
    assert(!Extend(nullptr,bytes.size(),rejected));
    for(std::size_t length=0;length<bytes.size();length+=4) {
        if(!Extend(bytes.data(),length,rejected))assert(rejected.empty());
        // Padding after the native terminator is not required by the reader.
        else assert(length >= (a+1)*4);
    }
    return 0;
}
