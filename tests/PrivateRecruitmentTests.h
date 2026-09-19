// Included by the x86 runtime harness; never attaches to a game process.
#include <fstream>
#include <iterator>
namespace {
void VerifyPrivateRecruitmentProfile(const char* environment, bool beta) {
    char path[32768] = {};
    if (!GetEnvironmentVariableA(environment, path, sizeof(path))) return;
    std::ifstream file(path, std::ios::binary);
    assert(file.good());
    const std::vector<unsigned char> raw((std::istreambuf_iterator<char>(file)),
                                         std::istreambuf_iterator<char>());
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(raw.data());
    const auto* pe = reinterpret_cast<const IMAGE_NT_HEADERS*>(raw.data() + dos->e_lfanew);
    std::vector<unsigned char> image(pe->OptionalHeader.SizeOfImage);
    const auto* sections = IMAGE_FIRST_SECTION(pe);
    for (unsigned i = 0; i < pe->FileHeader.NumberOfSections; ++i) {
        std::memcpy(image.data()+sections[i].VirtualAddress,
                    raw.data()+sections[i].PointerToRawData, sections[i].SizeOfRawData);
    }
    using namespace MajestyPrivateRecruitment;
    const auto base = reinterpret_cast<std::uintptr_t>(image.data());
    assert(Validate(base, beta ? MajestyBuildId::SteamBeta2 : MajestyBuildId::SteamPublic));
    const auto* profile = beta ? kBeta : kPublic;
    image[profile[0].rva + 10] ^= 1;
    assert(!Validate(base, beta ? MajestyBuildId::SteamBeta2 : MajestyBuildId::SteamPublic));
    image[profile[0].rva + 10] ^= 1;
    Presenters privateRows;
    assert(privateRows.Initialize(base, beta ? MajestyBuildId::SteamBeta2 : MajestyBuildId::SteamPublic, 0x7301));
    for (unsigned index = 0; index < 9; ++index) {
        const auto which = index < 3 ? 0u : index < 6 ? 1u : index-4;
        const auto choice = index < 6 ? index % 3 : 0;
        const auto& code = profile[which];
        const void* copies[] = {privateRows.recruit[0], privateRows.recruit[1], privateRows.recruit[2],
            privateRows.tooltip[0], privateRows.tooltip[1], privateRows.tooltip[2],
            privateRows.count, privateRows.setup, privateRows.event};
        const auto* copy = static_cast<const unsigned char*>(copies[index]);
        std::vector<unsigned char> expected(image.begin()+code.rva, image.begin()+code.rva+code.size);
        for (std::size_t branchIndex = 0; branchIndex < code.branchCount; ++branchIndex) {
            const auto& branch = code.branches[branchIndex];
            const auto replacement = choice == 0 ? Replacement<0>(branch.role) :
                                     choice == 1 ? Replacement<1>(branch.role) : Replacement<2>(branch.role);
            const auto target = replacement ? replacement : base + branch.targetRva;
            const auto relative = static_cast<std::int32_t>(target - (reinterpret_cast<std::uintptr_t>(copy) + branch.offset + 5));
            std::memcpy(expected.data()+branch.offset+1, &relative, 4);
        }
        const std::uint32_t commands[] = {0x1F48, 0x1389, 0x1388};
        const std::uint32_t prices[] = {0x1752, 0x1F51, 0x7301};
        for (std::size_t controlIndex = 0; controlIndex < code.controlCount; ++controlIndex) {
            const auto& control = code.controls[controlIndex];
            const auto value = control.id == 0x1F48 ? commands[choice] : prices[choice];
            std::memcpy(expected.data()+control.offset, &value, 4);
        }
        assert(std::memcmp(copy, expected.data(), code.size) == 0);
    }
    assert(Validate(base, beta ? MajestyBuildId::SteamBeta2 : MajestyBuildId::SteamPublic)); // stock source remained untouched
}
unsigned recruitIndexSeen = 99;
void* recruitControllerSeen = nullptr;
void* recruitTextSeen = nullptr;
std::uint32_t __cdecl TestProduced(void* unit, unsigned index) {
    recruitControllerSeen = unit; recruitIndexSeen = index; return 0x12345678u;
}
void __fastcall TestName(void* controller, void*, unsigned index, void* text) {
    recruitControllerSeen = controller; recruitIndexSeen = index; recruitTextSeen = text;
}
bool __fastcall TestQuote(void* controller, void*, unsigned index, int* price) {
    recruitControllerSeen = controller; recruitIndexSeen = index; *price = 500 + index; return true;
}
bool __fastcall TestAffordable(void* controller, void*, unsigned index) {
    recruitControllerSeen = controller; recruitIndexSeen = index; return index == 2;
}
void __fastcall TestTooltip(void* controller, void*, void* text, unsigned index) {
    recruitControllerSeen = controller; recruitIndexSeen = index; recruitTextSeen = text;
}
void RunPrivateRecruitmentTests() {
    using namespace MajestyPrivateRecruitment;
    const auto savedBase = imageBase;
    const auto* savedHelpers = helpers;
    VerifyPrivateRecruitmentProfile("MAJESTY_PUBLIC_EXE", false);
    VerifyPrivateRecruitmentProfile("MAJESTY_BETA2_EXE", true);
    const std::uint32_t stubs[] = {
        reinterpret_cast<std::uint32_t>(&TestProduced), reinterpret_cast<std::uint32_t>(&TestName),
        reinterpret_cast<std::uint32_t>(&TestQuote), reinterpret_cast<std::uint32_t>(&TestAffordable),
        reinterpret_cast<std::uint32_t>(&TestTooltip), 0, 0};
    imageBase = 0; helpers = stubs;
    auto* unit = reinterpret_cast<void*>(0x1234);
    auto* text = reinterpret_cast<void*>(0x5678);
    assert(Produced<2>(unit, 0) == 0x12345678u && recruitIndexSeen == 2 && recruitControllerSeen == unit);
    Name<1>(unit, nullptr, 0, text);
    assert(recruitIndexSeen == 1 && recruitTextSeen == text);
    int quote = 0;
    assert(Quote<2>(unit, nullptr, 0, &quote) && quote == 502 && recruitIndexSeen == 2);
    assert(Affordable<2>(unit, nullptr, 0));
    TooltipPrice<1>(unit, nullptr, text, 0);
    assert(recruitIndexSeen == 1 && recruitTextSeen == text);
    std::uint32_t first = 0xDEADBEEF, second = 0xDEADBEEF;
    ThreeCounts(unit, nullptr, &first, &second);
    assert(first == 1 && second == 1);

    // Exercise executable cloning/control remapping and W^X without executing
    // any game code: mov eax, stock-command; ret becomes a private command.
    const unsigned char source[] = {0xB8, 0x48, 0x1F, 0, 0, 0xC3};
    const Control control[] = {{1, 0x1F48u}};
    Code code = {0, sizeof(source), 0, nullptr, 0, nullptr, 0, control, 1};
    imageBase = reinterpret_cast<std::uintptr_t>(source);
    auto* copy = Clone<0>(code, 0x7302u, 0);
    assert(copy != nullptr);
    using Read = unsigned (__cdecl*)();
    assert(reinterpret_cast<Read>(copy)() == 0x7302u);
    assert(source[1] == 0x48 && source[2] == 0x1F);
    MEMORY_BASIC_INFORMATION memory = {};
    assert(VirtualQuery(copy, &memory, sizeof(memory)) && memory.Protect == PAGE_EXECUTE_READ);
    VirtualFree(copy, 0, MEM_RELEASE);
    imageBase = savedBase; helpers = savedHelpers;

    // Private selection creates the AP52 controller; unrelated stock AP52
    // remains unmapped. Global recipe ownership is retired at stock teardown.
    g_stockControllerRegistry.privateRecruitments = {{"test", 0x4E505A5Au, 0x7301u}};
    std::uint32_t args[] = {0, 0x4E505A5Au, 0, 0};
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == 0x32355041u);
    args[1] = 0x32355041u;
    ResolveDialogFactoryRequest(args + 1);
    assert(args[1] == 0x32355041u);
    std::uint32_t creation[] = {0x4E505A5Au, 0, 0, 0};
    ResolveDialogCreationRequest(creation);
    assert(g_parentRecruitment == &g_stockControllerRegistry.privateRecruitments[0]);
    ParentPanelControllerDestroyed(nullptr, nullptr);
    assert(g_parentRecruitment == nullptr);
    g_stockControllerRegistry.privateRecruitments.clear();
}
}
