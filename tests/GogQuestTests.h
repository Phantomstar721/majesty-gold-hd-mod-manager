#pragma once
#include <map>

namespace QuestTests {
struct Record { unsigned vtable = 0; GUID id{}; };
std::map<unsigned, Record> records;
std::vector<std::string> events;
void* expectedOwner = &records;
const void* expectedOptions = nullptr;
bool failLoad = false;
bool failPack = false;
bool omitVariant = false;

void __fastcall Scan(void* owner, void*, const MajestyStringView* path, unsigned recursive, const void* options) {
    assert(owner == expectedOwner && path && recursive == 1 && options == expectedOptions);
    events.push_back("scan");
}
unsigned __cdecl Key(const GUID* id) { return id->Data1; }
void* __fastcall Lookup(void* owner, void*, unsigned key) {
    assert(owner == expectedOwner);
    const auto it = records.find(key);
    return it == records.end() ? nullptr : &it->second;
}
bool __fastcall Load(void* owner, void*, const MajestyStringView* path, const void* options) {
    assert(owner == expectedOwner && options == expectedOptions);
    const std::string file(path->data, path->length);
    events.push_back(file);
    if (failLoad || (failPack && file == "pack.mqxml")) return false;
    if (file == "pack.mqxml") {
        records[1].id.Data1 = 1;
        if (!omitVariant) records[2].id.Data1 = 2;
    } else records[3].id.Data1 = 3;
    return true;
}

void Run() {
    g_stockQuestDirectoryScan = reinterpret_cast<StockQuestDirectoryScan>(&Scan);
    g_stockQuestManifestLoad = reinterpret_cast<StockQuestManifestLoad>(&Load);
    g_stockQuestGuidKey = &Key;
    g_stockQuestLookup = reinterpret_cast<StockQuestLookup>(&Lookup);
    g_stockModGuidParse = &StandardModTests::Parse;
    g_stockModStringConstruct = reinterpret_cast<StockModStringConstruct>(&StandardModTests::Construct);
    g_stockModStringDestroy = reinterpret_cast<StockModStringDestroy>(&StandardModTests::Destroy);
    g_gogWorkshopQuests = {{"1", "pack.mqxml"}, {"2", "pack.mqxml"}, {"3", "other.mqxml"}};
    unsigned options[] = {0, 1};
    expectedOptions = options;
    MajestyStringView directory{};
    GogQuestDirectoryScan(expectedOwner, nullptr, &directory, 1, options);
    assert((events == std::vector<std::string>{"scan", "pack.mqxml", "other.mqxml"}));
    assert(records.size() == 3 && options[0] == 0 && options[1] == 1);
    events.clear();
    GogQuestDirectoryScan(expectedOwner, nullptr, &directory, 1, options);
    assert((events == std::vector<std::string>{"scan"}));
    records.clear(); // stock teardown, followed by another startup
    events.clear();
    assert(RegisterGogWorkshopQuests(expectedOwner, options));
    assert(events.size() == 2);
    records[1].id.Data2 = 99; // a colliding key is not the expected GUID
    records.erase(3);
    assert(!RegisterGogWorkshopQuests(expectedOwner, options));
    assert(records[1].id.Data2 == 99 && records.count(3) == 1);
    records.clear();
    events.clear();
    omitVariant = true;
    assert(!RegisterGogWorkshopQuests(expectedOwner, options));
    assert(std::count(events.begin(), events.end(), "pack.mqxml") == 1);
    assert(records.count(1) == 1 && records.count(3) == 1); // partial stock records retained
    omitVariant = false;
    records.clear();
    events.clear();
    failPack = true;
    // The actual startup wrapper must return, retaining the good quest.
    GogQuestDirectoryScan(expectedOwner, nullptr, &directory, 1, options);
    assert((events == std::vector<std::string>{"scan", "pack.mqxml", "other.mqxml"}));
    assert(records.size() == 1 && records.count(3) == 1);
    failPack = false;
    events.clear();
    GogQuestDirectoryScan(expectedOwner, nullptr, &directory, 1, options);
    assert(records.size() == 3); // repaired file retried at the next stock boundary
    records.clear();
    failLoad = true;
    StandardModTests::events.clear();
    assert(!RegisterGogWorkshopQuests(expectedOwner, options));
    assert((StandardModTests::events == std::vector<std::string>{"construct", "destroy", "construct", "destroy"}));
    failLoad = false;
    g_gogWorkshopQuests.clear();

    wchar_t directoryPath[MAX_PATH] = {}, temporary[MAX_PATH] = {};
    assert(GetTempPathW(MAX_PATH, directoryPath));
    assert(GetTempFileNameW(directoryPath, L"mmq", 0, temporary));
    const std::wstring manifest = std::wstring(temporary) + L".mqxml";
    assert(MoveFileW(temporary, manifest.c_str()));
    const std::wstring row = L"12345678-ABCD-EFAB-1234-123456789ABC\t" + manifest;
    std::vector<GogStandardMod> parsed;
    assert(ParseGogStandardMods(row, parsed, L".mqxml", 789));
    assert(!ParseGogStandardMods(row, parsed)); // quests never enter active mods
    assert(!ParseGogStandardMods(row + L"\n" + row, parsed, L".mqxml", 789));
    assert(SetEnvironmentVariableW(kGogQuestManifestsEnvironment, nullptr));
    g_buildProfile = nullptr;
    assert(InstallGogWorkshopQuests());
    g_buildProfile = &kBeta2BuildProfile;
    assert(SetEnvironmentVariableW(kGogQuestManifestsEnvironment, row.c_str()));
    assert(!InstallGogWorkshopQuests());
    assert(SetEnvironmentVariableW(kGogQuestManifestsEnvironment, nullptr));
    assert(DeleteFileW(manifest.c_str()));
    assert(!ParseGogStandardMods(row, parsed, L".mqxml", 789));
    assert(ParseGogStandardMods(row, parsed, L".mqxml", 789, true));
    assert(parsed.size() == 1 && parsed[0].manifest.empty());
    assert(!ParseGogStandardMods(row + L"\n" + row, parsed, L".mqxml", 789, true));
    assert(!ParseGogStandardMods(L"invalid", parsed, L".mqxml", 789, true));
}
} // namespace QuestTests
