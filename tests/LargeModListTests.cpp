#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cassert>
#include <vector>
#include <fstream>
#include <iterator>
#include "../runtime/MajestyBuildId.h"
struct Profile { MajestyBuildId buildId; };
Profile profile{};
Profile* g_buildProfile=&profile;
std::uintptr_t g_imageBase=0;
#include "../runtime/LargeModList.inl"
extern "C" unsigned char GogFixtureBytes[0x500000];
FILE* input=nullptr;
unsigned commits=0;
void __cdecl Noop(void*,void*){}
void __cdecl Apply(){++commits;}
FILE* __cdecl Open(const char*,const char*) { std::rewind(input);return input; }
int __cdecl Close(FILE*){return 0;}
struct Node { Node *next,*prev;void* value; };
std::vector<Node*> allocated;
Node* __fastcall Insert(void*,void*,Node* next,Node* prev,void** value) {
    auto* n=new Node{next,prev,*value};allocated.push_back(n);return n;
}
void __fastcall Count(void*,void*,unsigned){}
void Jump(unsigned address,void* target) {
    auto* code=reinterpret_cast<unsigned char*>(address);
    code[0]=0xE9;
    const unsigned displacement=reinterpret_cast<unsigned>(target)-address-5;
    std::memcpy(code+1,&displacement,4);
}
int main(int argc,char** argv){
    assert(argc==4);
    void* image=GogFixtureBytes;
    DWORD old;
    assert(VirtualProtect(image,sizeof(GogFixtureBytes),PAGE_EXECUTE_READWRITE,&old));
    g_imageBase=reinterpret_cast<std::uintptr_t>(image);
    assert(g_imageBase==0x400000);
    for(unsigned index=0;index<3;++index){
        profile.buildId=static_cast<MajestyBuildId>(index);
        std::ifstream file(argv[index+1],std::ios::binary);
        std::vector<char> data((std::istreambuf_iterator<char>(file)),{});
        assert(!data.empty());
        auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(data.data());
        auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(data.data()+dos->e_lfanew);
        std::memcpy(image,data.data(),nt->OptionalHeader.SizeOfHeaders);
        auto* copyNt=reinterpret_cast<IMAGE_NT_HEADERS32*>(static_cast<char*>(image)+dos->e_lfanew);
        auto* sections=IMAGE_FIRST_SECTION(copyNt);
        auto& section=sections[copyNt->FileHeader.NumberOfSections++];
        std::memset(&section,0,sizeof(section));
        std::memcpy(section.Name,".mpst",6);section.VirtualAddress=0x480000;section.Misc.VirtualSize=0x1200;
        auto* sectionBytes=static_cast<unsigned char*>(image)+section.VirtualAddress;
        auto* code=sectionBytes+0x300;
        const auto& p=LargeModList::profiles[index];
        std::memcpy(code,LargeModList::payload,sizeof(LargeModList::payload));
        auto put=[](void* dest,unsigned value){std::memcpy(dest,&value,4);};
        unsigned imports[]={0x735430,0x735434,0x735444,0x73544C,0x7C1E30,0x7C1E38,0x7C1E4C,0x7C1DFC};
        for(const auto& m:LargeModList::moves){
            unsigned v=m.original;
            for(unsigned i=0;i<8;++i)if(m.original==imports[i])v=p[i+4];
            if(m.original==0x80E180)v=reinterpret_cast<unsigned>(sectionBytes+0x600);
            if(m.original==0x80E1F0)v=reinterpret_cast<unsigned>(sectionBytes+0x1F0);
            if(m.original==0x80E200)v=reinterpret_cast<unsigned>(sectionBytes+0x200);
            if(index && m.original==0x7BD900)v=reinterpret_cast<unsigned>(sectionBytes+0x700);
            if(index && m.original>=0x7BDD00 && m.original<0x7BDD30)
                v=reinterpret_cast<unsigned>(sectionBytes+0xB00)+m.original-0x7BDD00;
            put(code+m.offset,v);
        }
        unsigned offsets[]={8,0x1E8,0x1F6};
        for(unsigned i=0;i<3;++i)put(code+offsets[i]+1,p[i]-reinterpret_cast<unsigned>(code+offsets[i]+5));
        put(code+sizeof(LargeModList::payload)-8,p[3]);
        code[0]^=1;assert(!InstallLargeModList());code[0]^=1;
        assert(InstallLargeModList());
        Jump(p[0],reinterpret_cast<void*>(&Noop));
        Jump(p[1],reinterpret_cast<void*>(&Insert));
        Jump(p[2],reinterpret_cast<void*>(&Count));
        Jump(p[3],reinterpret_cast<void*>(&Apply));
        put(reinterpret_cast<void*>(p[4]),reinterpret_cast<unsigned>(&Open));
        put(reinterpret_cast<void*>(p[5]),reinterpret_cast<unsigned>(&std::fread));
        put(reinterpret_cast<void*>(p[6]),reinterpret_cast<unsigned>(&Close));
        put(reinterpret_cast<void*>(p[7]),reinterpret_cast<unsigned>(&std::sscanf));
        std::strcpy(reinterpret_cast<char*>(sectionBytes+0x600),"fixture");
        std::strcpy(reinterpret_cast<char*>(sectionBytes+0x1F0),"rb");
        std::strcpy(reinterpret_cast<char*>(sectionBytes+0x200),"%8x-%4x-%4x-%2x%2x-%2x%2x%2x%2x%2x%2x");
        Node installed{},active{};installed.next=installed.prev=&installed;active.next=active.prev=&active;
        std::vector<std::vector<unsigned char>> mods(100,std::vector<unsigned char>(20));
        std::vector<Node> nodes(100);
        input=std::tmpfile();assert(input);
        for(unsigned i=0;i<100;++i){
            const unsigned id=i+1;put(mods[i].data()+4,id);
            nodes[i]={&installed,installed.prev,mods[i].data()};installed.prev->next=&nodes[i];installed.prev=&nodes[i];
            std::fprintf(input,"%08X-0000-0000-0000-000000000000\r\n",id);
        }
        // Unknown IDs must be skipped, and repeated restore must stay idempotent.
        std::fprintf(input,"FFFFFFFF-0000-0000-0000-000000000000\r\n");
        put(reinterpret_cast<void*>(p[8]),reinterpret_cast<unsigned>(&installed));
        put(reinterpret_cast<void*>(p[10]),reinterpret_cast<unsigned>(&active));
        using Restore=void (__cdecl*)(void*,void*);
        for(unsigned repeat=0;repeat<2;++repeat){
            reinterpret_cast<Restore>(code)(nullptr,nullptr);
            unsigned count=0;
            for(auto* n=active.next;n!=&active;n=n->next){assert(count<100);assert(n->value==mods[count].data());++count;}
            assert(count==100);
        }
        std::fclose(input);
        for(auto* n:allocated)delete n;allocated.clear();
    }

    return 0;
}
