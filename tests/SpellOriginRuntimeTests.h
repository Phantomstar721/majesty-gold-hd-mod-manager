// Actual x86 creation wrapper/prologue and birth ABI with isolated stand-ins.
namespace SpellOriginTest {
struct Value { void** vtable; void* unit; };
struct Args { Value* value; void* spell; void* target; Args* nested; };
Args* current = nullptr;
unsigned records = 0, births = 0;
void** __fastcall Argument(void* data, void*, unsigned index) {
    assert(index == 1); return reinterpret_cast<void**>(&static_cast<Args*>(data)->value);
}
void* __fastcall Unwrap(void* value, void*) { return static_cast<Value*>(value)->unit; }
void* __fastcall Unit(void* value, void*) { return value; }
bool Record(void* spell, void* source) {
    assert(current && spell == current->spell && source == current->value->unit);
    ++records; return true;
}
void __fastcall StockBirth(void* callback, void*, void* spell, void* target) {
    assert(callback == current && spell == current->spell && target == current->target);
    assert(records == births+1); ++births;
    if (current->nested) {
        auto* saved = current;
        current = current->nested;
        SpellOrigin::Create(current);
        current = saved;
        assert(SpellOrigin::source == current->value->unit);
    }
}
void __cdecl StockCreate(Args* arguments) {
    assert(arguments == current && SpellOrigin::source == current->value->unit);
    SpellOrigin::Birth(arguments,nullptr,arguments->spell,arguments->target);
}
__declspec(naked) void Resume() {
    __asm {
        mov eax, [esp+38h]
        push eax
        call StockCreate
        add esp, 4
        pop ebp
        pop ebx
        add esp, 2Ch
        ret
    }
}
void Jump(unsigned char* site, const void* target) {
    site[0] = 0xE9;
    const auto displacement = static_cast<std::int32_t>(reinterpret_cast<std::uintptr_t>(target)
        - reinterpret_cast<std::uintptr_t>(site)-5);
    std::memcpy(site+1,&displacement,4);
}
void Run() {
    auto* image = static_cast<unsigned char*>(VirtualAlloc(nullptr,0x1000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(image);
    Jump(image+0x20,reinterpret_cast<void*>(&Argument));
    Jump(image+0x40,reinterpret_cast<void*>(&Unit));
    Jump(image+0x60,reinterpret_cast<void*>(&StockBirth));
    const auto base = g_imageBase;
    const auto* profile = SpellOrigin::profile;
    const auto resume = SpellOrigin::resume;
    const auto record = SpellOrigin::record;
    const MajestySpellOrigin::Profile fake{0,0x20,0x40,0x60,0};
    g_imageBase = reinterpret_cast<std::uintptr_t>(image);
    SpellOrigin::profile = &fake;
    SpellOrigin::resume = reinterpret_cast<std::uintptr_t>(&Resume);
    SpellOrigin::record = &Record;
    void* vtable[24]{};
    vtable[23] = reinterpret_cast<void*>(&Unwrap);
    Value a{vtable,reinterpret_cast<void*>(1)}, b{vtable,reinterpret_cast<void*>(2)};
    Args child{&b,reinterpret_cast<void*>(3),reinterpret_cast<void*>(4),nullptr};
    Args parent{&a,reinterpret_cast<void*>(5),reinterpret_cast<void*>(6),&child};
    current = &parent;
    assert(SpellOrigin::source == nullptr);
    SpellOrigin::Create(current);
    assert(records == 2 && births == 2 && SpellOrigin::source == nullptr);
    {
        SpellOrigin::Scope aScope(a.unit);
        try { SpellOrigin::Scope bScope(b.unit); throw 1; } catch (...) {}
        assert(SpellOrigin::source == a.unit);
    }
    assert(SpellOrigin::source == nullptr);
    SpellOrigin::profile = profile;
    SpellOrigin::resume = resume;
    SpellOrigin::record = record;
    g_imageBase = base;
    VirtualFree(image,0,MEM_RELEASE);
}
}
