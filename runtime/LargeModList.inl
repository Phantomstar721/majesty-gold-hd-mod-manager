#include "LargeModList.h"
bool InstallLargeModList() {
    using namespace LargeModList;
    const auto index = static_cast<unsigned>(g_buildProfile->buildId);
    if (index >= 3) return false;
    const auto& p = profiles[index];
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
        g_imageBase + reinterpret_cast<const IMAGE_DOS_HEADER*>(g_imageBase)->e_lfanew);
    const auto* sections = IMAGE_FIRST_SECTION(nt);
    unsigned char* section = nullptr;
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (std::memcmp(sections[i].Name, ".mpst", 6) == 0) {
            if (sections[i].Misc.VirtualSize < 0x700) return false;
            section = reinterpret_cast<unsigned char*>(g_imageBase + sections[i].VirtualAddress);
        }
    }
    if (!section) return false;
    unsigned char expected[sizeof(payload)];
    std::memcpy(expected, payload, sizeof(payload));
    auto put = [](unsigned char* data, unsigned offset, unsigned value) {
        std::memcpy(data+offset, &value, 4);
    };
    for (const auto& m : moves) {
        unsigned replacement = m.original;
        const unsigned imports[] = {0x735430,0x735434,0x735444,0x73544C,0x7C1E30,0x7C1E38,0x7C1E4C,0x7C1DFC};
        for (unsigned i=0;i<8;++i) if (replacement == imports[i]) replacement = p[i+4];
        if (m.original == 0x80E180) replacement = reinterpret_cast<unsigned>(section+0x600);
        if (m.original == 0x80E1F0) replacement = reinterpret_cast<unsigned>(section+0x1F0);
        if (m.original == 0x80E200) replacement = reinterpret_cast<unsigned>(section+0x200);
        if (index != 0) {
            if (m.original == 0x7BD900) replacement = reinterpret_cast<unsigned>(section+0x700);
            if (m.original >= 0x7BDD00 && m.original < 0x7BDD30)
                replacement = reinterpret_cast<unsigned>(section+0xB00) + m.original-0x7BDD00;
        }
        put(expected, m.offset, replacement);
    }
    const unsigned offsets[] = {8,0x1E8,0x1F6};
    for (unsigned i=0;i<3;++i)
        put(expected, offsets[i]+1, p[i] - (reinterpret_cast<unsigned>(section+0x300)+offsets[i]+5));
    put(expected, sizeof(payload)-8, p[3]);
    auto* code = section+0x300;
    if (std::memcmp(code,expected,sizeof(expected))) return false;
    unsigned char expanded[sizeof(payload)];
    std::memcpy(expanded,expected,sizeof(expanded));
    for (const auto& m : moves) {
        if (m.original == 0x7BD900) put(expanded,m.offset,reinterpret_cast<unsigned>(arena));
        if (m.original >= 0x7BDD00 && m.original < 0x7BDD30)
            put(expanded,m.offset,reinterpret_cast<unsigned>(arena+kCapacity)+m.original-0x7BDD00);
    }
    // Same synchronous fread/parser/list/commit routine with a larger owned arena.
    put(expanded,48,kCapacity-1);
    DWORD previous,ignored;
    if (!VirtualProtect(code,sizeof(expanded),PAGE_EXECUTE_READWRITE,&previous)) return false;
    std::memcpy(code,expanded,sizeof(expanded));
    const bool flushed = FlushInstructionCache(GetCurrentProcess(),code,sizeof(expanded)) != FALSE;
    return VirtualProtect(code,sizeof(expanded),previous,&ignored) && flushed;
}
