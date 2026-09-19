#pragma once
#include <cassert>

namespace StandardModTests {
std::vector<std::string> events;
std::vector<unsigned> installed;
const void* expectedOptions = nullptr;
const MajestyStringView* expectedDirectory = nullptr;
bool loadSucceeds = true;
bool omitSecondVariant = false;
unsigned scannedRecursion = 0;

void __cdecl Scan(const MajestyStringView* directory, unsigned recursive, const void* options) {
    assert(directory == expectedDirectory && options == expectedOptions);
    scannedRecursion = recursive;
    events.push_back("scan");
}
bool __cdecl Parse(const char* text, GUID* id) {
    *id = {};
    id->Data1 = text[0] - '0';
    return id->Data1 >= 1 && id->Data1 <= 3;
}
void* __cdecl Lookup(const GUID* id) {
    return std::find(installed.begin(), installed.end(), id->Data1) != installed.end() ? &installed : nullptr;
}
MajestyStringView* __fastcall Construct(MajestyStringView* value, void*, const char* text) {
    events.push_back("construct");
    const auto length = std::strlen(text);
    auto* copy = new char[length + 1];
    std::memcpy(copy, text, length + 1);
    value->data = copy;
    value->length = static_cast<std::uint32_t>(length);
    return value;
}
void __fastcall Destroy(MajestyStringView* value, void*) {
    events.push_back("destroy");
    delete[] value->data;
    value->data = nullptr;
}
bool __cdecl Load(const MajestyStringView* value, const void* options) {
    assert(options == expectedOptions);
    const std::string path(value->data, value->length);
    events.push_back(path);
    if (!loadSucceeds) return false;
    if (path == "variants.mmxml") {
        installed.push_back(1);
        if (!omitSecondVariant) installed.push_back(2);
    } else if (path == "other.mmxml") installed.push_back(3);
    return true;
}

void Run() {
    g_stockModDirectoryScan = &Scan;
    g_stockModManifestLoad = &Load;
    g_stockModGuidParse = &Parse;
    g_stockModLookup = &Lookup;
    g_stockModStringConstruct = reinterpret_cast<StockModStringConstruct>(&Construct);
    g_stockModStringDestroy = reinterpret_cast<StockModStringDestroy>(&Destroy);
    g_gogStandardMods = {{"1", "variants.mmxml"}, {"2", "variants.mmxml"}, {"3", "other.mmxml"}};
    unsigned options[] = {0x12345678, 0xABCDEF01};
    MajestyStringView directory{};
    expectedOptions = options;
    expectedDirectory = &directory;
    GogStandardModDirectoryScan(&directory, 0x101, options);
    assert(scannedRecursion == 0x101);
    assert((events == std::vector<std::string>{"scan", "construct", "variants.mmxml", "destroy",
        "construct", "other.mmxml", "destroy"}));
    assert((installed == std::vector<unsigned>{1, 2, 3}));
    assert(options[0] == 0x12345678 && options[1] == 0xABCDEF01);

    // Existing installed records survive a repeated startup boundary without
    // duplicate registration. Stock teardown makes the next boundary reload.
    events.clear();
    GogStandardModDirectoryScan(&directory, 0, options);
    assert((events == std::vector<std::string>{"scan"}));
    installed.clear();
    events.clear();
    assert(RegisterGogStandardMods(options));
    assert(events.size() == 6);
    installed = {3}; // a record the original local directory scan supplied
    events.clear();
    assert(RegisterGogStandardMods(options));
    assert((events == std::vector<std::string>{"construct", "variants.mmxml", "destroy"}));

    installed.clear();
    events.clear();
    loadSucceeds = false;
    assert(!RegisterGogStandardMods(options));
    assert((events == std::vector<std::string>{"construct", "variants.mmxml", "destroy"}));
    loadSucceeds = true;
    omitSecondVariant = true;
    events.clear();
    assert(!RegisterGogStandardMods(options));
    assert(std::count(events.begin(), events.end(), "variants.mmxml") == 1);
    omitSecondVariant = false;

    wchar_t tempDirectory[MAX_PATH] = {}, tempFile[MAX_PATH] = {};
    assert(GetTempPathW(MAX_PATH, tempDirectory));
    assert(GetTempFileNameW(tempDirectory, L"mms", 0, tempFile));
    const std::wstring manifest = std::wstring(tempFile) + L".mmxml";
    assert(MoveFileW(tempFile, manifest.c_str()));
    const std::wstring id = L"12345678-ABCD-EFAB-1234-123456789ABC";
    const std::wstring row = id + L"\t" + manifest;
    std::vector<GogStandardMod> parsed;
    assert(ParseGogStandardMods(row, parsed) && parsed.size() == 1);
    assert(parsed[0].id == "12345678-ABCD-EFAB-1234-123456789ABC");
    assert(GetFileAttributesA(parsed[0].manifest.c_str()) != INVALID_FILE_ATTRIBUTES);
    // Optional launch data never adds a hook to Steam. With no data, no game
    // image is needed at all; no stock code is read or called.
    SetEnvironmentVariableW(kGogStandardManifestsEnvironment, nullptr);
    g_buildProfile = nullptr;
    assert(InstallGogStandardMods());
    g_buildProfile = &kBeta2BuildProfile;
    assert(SetEnvironmentVariableW(kGogStandardManifestsEnvironment, row.c_str()));
    assert(!InstallGogStandardMods());
    assert(SetEnvironmentVariableW(kGogStandardManifestsEnvironment, nullptr));
    std::wstring tooMany;
    for (unsigned i = 0; i < 27; ++i) {
        wchar_t prefix[9] = {};
        swprintf_s(prefix, L"%08X", i);
        if (!tooMany.empty()) tooMany += L'\n';
        tooMany += std::wstring(prefix) + id.substr(8) + L"\t" + manifest;
    }
    assert(!ParseGogStandardMods(tooMany, parsed));
    assert(parsed.empty());
    for (const auto& invalid : std::vector<std::wstring>{L"", row + L"\n", row + L"\n" + row,
            id + L"\trelative.mmxml", id + L"\t" + manifest + L"\t", L"x" + row.substr(1),
            std::wstring(30001, L'A'), id + L"\t" + manifest + L".missing"}) {
        assert(!ParseGogStandardMods(invalid, parsed));
        assert(parsed.empty());
    }
    assert(DeleteFileW(manifest.c_str()));
    assert(!ParseGogStandardMods(row, parsed));
    g_gogStandardMods.clear();
}
} // namespace StandardModTests
