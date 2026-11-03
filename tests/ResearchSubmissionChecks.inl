// Literal GS_OrderProcessor +0x78 body, independently identical in all three profiles.
// Executes only in this fixture with order-allocation/publication doubles.
namespace ResearchSchedulerChecks {
unsigned order[16] = {}; unsigned created=0, published=0;
void* __fastcall Make(void*,void*,unsigned id) {assert(id==0x4005);++created;return order;}
bool __fastcall Publish(void*,void*,unsigned flag,void* value) {
    assert(flag==1 && value==order);++published;return false; // ignored native return
}
const unsigned char body[]={0x56,0x8B,0x74,0x24,0x08,0x32,0xC0,0x85,0xF6,0x74,0x37,0x8B,0x4C,0x24,0x14,0x8B,0x06,0x8B,0x90,0x88,0x01,0x00,0x00,0x51,0x8B,0xCE,0xFF,0xD2,0x8B,0x4C,0x24,0x0C,0x8B,0x54,0x24,0x10,0x83,0x48,0x18,0x02,0x89,0x48,0x14,0x89,0x50,0x2C,0x8B,0x16,0x8B,0x92,0x8C,0x01,0x00,0x00,0x50,0x8B,0x44,0x24,0x1C,0x50,0x8B,0xCE,0xFF,0xD2,0xB0,0x01,0x5E,0xC2,0x14,0x00};
void Run() {
    void* code=VirtualAlloc(nullptr,sizeof(body),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);assert(code);
    std::memcpy(code,body,sizeof(body));DWORD old=0;
    assert(VirtualProtect(code,sizeof(body),PAGE_EXECUTE_READ,&old));
    FlushInstructionCache(GetCurrentProcess(),code,sizeof(body));
    using Schedule=bool (__thiscall*)(void*,void*,unsigned,unsigned,unsigned,unsigned);
    auto schedule=reinterpret_cast<Schedule>(code);
    void* table[100]={};table[0x188/4]=reinterpret_cast<void*>(&Make);table[0x18C/4]=reinterpret_cast<void*>(&Publish);
    struct Unit{void** table;} unit={table};
    assert(!schedule(nullptr,nullptr,15000,0x2009,0x4005,1));assert(!created && !published);
    assert(schedule(nullptr,&unit,15000,0x2009,0x4005,1));
    assert(created==1 && published==1 && order[0x14/4]==15000 && order[0x2C/4]==0x2009 && order[0x18/4]==2);
    VirtualFree(code,0,MEM_RELEASE);
}
}
