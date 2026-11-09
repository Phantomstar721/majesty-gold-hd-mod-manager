namespace MessageChecks {
using Word=std::uint32_t;
template<class T> Word Address(T p){return static_cast<Word>(reinterpret_cast<std::uintptr_t>(p));}
Word world[2]{}, runtime[2]{}, global=0, catalog[1]{}, unit[3][32]{};
Word catalogTable[13]{}, alternateTable[13]{};
bool missingCatalog=false;
bool enumerating=false;
int scans=0, submissions=0, setups=0, forwards=0, destroys=0, reads=0, releases=0, preparations=0;
Word constructedMenu[16]{};
void __cdecl Prepare(Word value){assert(value==0);++preparations;}
void* __fastcall Catalog(void* w,void*,Word kind){assert(w==world&&kind==3);return missingCatalog?nullptr:catalog;}
int __fastcall Enumerate(void* c,void*,int (__cdecl* visit)(void*,void*,void*),void* a,void* b){
    assert(c==catalog);++scans;enumerating=true;
    for(auto& u:unit)if(visit(u,a,b))break;
    enumerating=false;return 0;
}
void* __fastcall Resolve(void* w,void*,Word id){assert(w==world);return id==1?unit[0]:nullptr;}
void __cdecl Submit(void* w,void* u,Word arg){
    assert(!enumerating&&w==world&&u==unit[0]&&arg==0);++submissions;
}
void __fastcall Setup(void*,void*){++setups;}
int __fastcall Command(void*,void*,Word id){assert(id==9005||id==0x7F01);++forwards;return 17;}
bool __fastcall Hover(void*,void*,Word id,Word a,Word b){assert(id==0x7F01&&a==2&&b==3);++forwards;return true;}
void* __fastcall Destroy(void* p,void*,Word flags){assert(flags==0);++destroys;return p;}
void* resourceTable[17]{};
void** resource=resourceTable;
HGLOBAL streamHandle=nullptr;
void* __cdecl Manager(){return &resource;}
void* __fastcall Acquire(void*,void*,void*,Word type,Word key,Word a,Word b,void* c,Word d){
    assert(type==0x554E4D53&&key==0x4B4D5041&&!a&&!b&&!c&&!d);return streamHandle;
}
void __fastcall Release(void*,void*,void* handle,Word arg){
    assert(handle==streamHandle&&!arg);++releases;
    assert((GlobalFlags(streamHandle)&GMEM_LOCKCOUNT)==0);GlobalFree(streamHandle);streamHandle=nullptr;
}
void* __fastcall Read(void*,void*,Word** reader,void* context,Word key,Word mode,Word flags){
    assert(!context&&key==0x4B4D5041&&mode==1&&flags==2&&preparations==1);
    assert(reader[0]==reader[1]);++reads;
    std::vector<Word> words(reader[0],reader[0]+100); // stream has sufficient padding
    std::vector<MajestyMessageFlagHud::Record> records;std::size_t end=0;
    assert(MajestyMessageFlagHud::Parse(words,records,end));
    unsigned privateCount=0;
    for(auto& r:records)if(auto* id=r.Find(6))
        if(words[id->value]==0x7F20||words[id->value]==0x7F21)++privateCount;
    assert(privateCount==2);return constructedMenu;
}
void* __fastcall Original(void*,void*,void*,Word key,Word mode,Word flags){assert(key==123&&mode==3&&flags==4);++forwards;return constructedMenu;}
int creationCalls=0;
void __cdecl Create(){++creationCalls;}
void Run(){
    using namespace MessageFlagControls;
    auto p=profiles[0];
    runtime[1]=Address(world);global=Address(runtime);
    p.worldGlobal=Address(&global);p.catalog=Address(&Catalog);p.enumerate=Address(&Enumerate);
    p.resolve=Address(&Resolve);p.commandFactory=Address(&Submit);
    p.allTable=Address(catalogTable);catalog[0]=p.allTable;
    MessageFlagControls::profile=&p;
    stockAllUnitsTable=Address(alternateTable);
    auto savedGlobal=global;global=0;assert(!Clear());global=savedGlobal;
    missingCatalog=true;assert(!Clear());missingCatalog=false;
    catalog[0]=123;assert(!Clear());catalog[0]=p.allTable;
    assert(scans==0&&submissions==0);
    unit[0][0x6C/4]=0x4647534D;unit[0][0x70/4]=1;
    unit[1][0x6C/4]=0x4647534D;unit[1][0x70/4]=2;unit[1][0x74/4]=4;
    unit[2][0x6C/4]=0x30306C46;unit[2][0x70/4]=3; // player reward flag
    void* table[9]{};
    table[0]=reinterpret_cast<void*>(&Destroy);table[1]=reinterpret_cast<void*>(&Setup);
    table[2]=reinterpret_cast<void*>(&Hover);table[3]=reinterpret_cast<void*>(&Command);
    p.table=Address(table);for(unsigned i=0;i<9;++i)p.slots[i]=Address(table[i]);
    MessageFlagControls::profile=&p;installed=true;suppressed=0;
    Controller first={table,{},nullptr,nullptr},second={table,{},nullptr,nullptr};
    assert(Capture(Address(&first)));assert(scans==0);
    MessageFlagControls::Setup(&first,nullptr);assert(setups==1&&scans==0);
    assert(MessageFlagControls::Command(&first,nullptr,9005)==17);
    assert(MessageFlagControls::Command(&first,nullptr,0x7F01)==17);
    assert(MessageFlagControls::Hover(&first,nullptr,0x7F01,2,3));
    assert(CreateDirectoryW(L"artifacts",nullptr)||GetLastError()==ERROR_ALREADY_EXISTS);
    assert(CreateDirectoryW(L"artifacts\\panel-lifecycle-tests",nullptr)||GetLastError()==ERROR_ALREADY_EXISTS);
    preferencePath=L"artifacts\\panel-lifecycle-tests\\message-controls-test.dat";
    DeleteFileW(preferencePath.c_str());assert(Preference(false));assert(!suppressed);
    MessageFlagControls::Command(&first,nullptr,0x7F20);
    assert(suppressed&&scans==1&&submissions==1);
    suppressed=0;assert(Preference(false));assert(suppressed);
    catalog[0]=stockAllUnitsTable; // actual stock AllUnitsList, not only GE_AllUnitsList
    MessageFlagControls::Command(&first,nullptr,0x7F21);
    assert(suppressed&&scans==2&&submissions==2);
    catalog[0]=p.allTable;
    MessageFlagControls::Command(&first,nullptr,0x7F20);
    assert(!suppressed&&scans==2);
    assert(Capture(Address(&second)));
    using Destructor=void* (__thiscall*)(void*,Word);
    reinterpret_cast<Destructor>(first.table[0])(&first,0);
    assert(controller==static_cast<LONG>(Address(&second)));
    MessageFlagControls::Command(&first,nullptr,0x7F21);assert(scans==2);
    reinterpret_cast<Destructor>(second.table[0])(&second,0);
    assert(controller==0&&destroys==2);
    auto good=preferencePath;preferencePath=L"?:\\invalid\\preference";
    assert(!Preference(true,true));preferencePath=good;DeleteFileW(good.c_str());
    std::vector<Word> words={1000,0xFFFFFFFF,0,6,2004,2,0,0,500,21,42,0,0,500,21,0xFFFFFFFF,
        0,6,9005,2,504,0,71,21,12,0x7A444E49,13,1014,0xFFFFFFFF,0xFFFFFFFF};
    words.resize(200,0);
    streamHandle=GlobalAlloc(GMEM_MOVEABLE,words.size()*4);
    auto* bytes=GlobalLock(streamHandle);std::memcpy(bytes,words.data(),words.size()*4);GlobalUnlock(streamHandle);
    Construction c{Address(&Prepare),Address(&Read)};construction=&c;
    p.getter=Address(&Manager);resourceTable[14]=reinterpret_cast<void*>(&Acquire);
    resourceTable[16]=reinterpret_cast<void*>(&Release);
    void* menuTable[3]={nullptr,nullptr,reinterpret_cast<void*>(&Read)};void** menu=menuTable;
    assert(ReadHud(&menu,nullptr,nullptr,0x4B4D5041,1,2)==constructedMenu);
    assert(constructedMenu[0x2C/4]==0x4B4D5041);assert(reads==1&&releases==1);
    originalLoad=reinterpret_cast<Load>(&Original);
    assert(ReadHud(&menu,nullptr,nullptr,123,3,4)==constructedMenu);assert(reads==1&&releases==1&&forwards==4);
    creationResume=reinterpret_cast<void*>(&Create);
    suppressed=1;CreationGate();assert(creationCalls==0);
    suppressed=0;CreationGate();assert(creationCalls==1);
    installed=false;MessageFlagControls::profile=nullptr;preferencePath.clear();
    assert(!Install()); // test image has no supported game base; no patch is attempted
}
}
