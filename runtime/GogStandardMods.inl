// Included inside the runtime's anonymous namespace. See docs/gog-standard-mods.md.
constexpr wchar_t kGogStandardManifestsEnvironment[] = L"MAJESTY_MOD_MANAGER_STANDARD_MANIFESTS";
constexpr std::size_t kMaximumStandardManifestCharacters = 30000;
constexpr std::size_t kMaximumStandardMods = 26;
struct GogStandardMod {
    std::string id;
    std::string manifest;
};
std::vector<GogStandardMod> g_gogStandardMods;
using StockModDirectoryScan = void (__cdecl*)(const MajestyStringView*, unsigned, const void*);
using StockModManifestLoad = bool (__cdecl*)(const MajestyStringView*, const void*);
using StockModGuidParse = bool (__cdecl*)(const char*, GUID*);
using StockModLookup = void* (__cdecl*)(const GUID*);
using StockModStringConstruct = MajestyStringView* (__thiscall*)(MajestyStringView*, const char*);
using StockModStringDestroy = void (__thiscall*)(MajestyStringView*);
StockModDirectoryScan g_stockModDirectoryScan = nullptr;
StockModManifestLoad g_stockModManifestLoad = nullptr;
StockModGuidParse g_stockModGuidParse = nullptr;
StockModLookup g_stockModLookup = nullptr;
StockModStringConstruct g_stockModStringConstruct = nullptr;
StockModStringDestroy g_stockModStringDestroy = nullptr;

__declspec(noreturn) void StopGogStandardModLaunch(const char* reason) {
    WriteLog(reason);
    MessageBoxW(nullptr,
        L"Majesty Mod Manager could not load the selected Standard mods for GOG. "
        L"Rescan the installed mods in the Manager and launch again. If this continues, "
        L"review MajestyBuildingRuntime.log beside the runtime DLL for the missing mod or loader check.",
        L"Majesty Mod Manager", MB_OK | MB_ICONERROR);
    TerminateProcess(GetCurrentProcess(), 0x4D4D5458u);
    ExitProcess(0x4D4D5458u);
}

bool StockModNarrowPath(const std::wstring& path, std::string& output) {
    // The stock filesystem takes ANSI strings. Never silently substitute a
    // Unicode filename. A real short path is safe because it retains the same
    // file and manifest-relative directory; otherwise report the limitation.
    const auto convert = [&](const std::wstring& value) {
        const int count = WideCharToMultiByte(CP_ACP, 0, value.c_str(), -1, nullptr, 0, nullptr, nullptr);
        if (count <= 1 || count > MAX_PATH) return false;
        std::vector<char> narrow(count);
        if (!WideCharToMultiByte(CP_ACP, 0, value.c_str(), -1, narrow.data(), count, nullptr, nullptr)) return false;
        std::vector<wchar_t> restored(value.size() + 1);
        if (!MultiByteToWideChar(CP_ACP, 0, narrow.data(), -1, restored.data(),
                static_cast<int>(restored.size())) || value != restored.data()) return false;
        output.assign(narrow.data());
        return true;
    };
    if (convert(path)) return true;
    const DWORD length = GetShortPathNameW(path.c_str(), nullptr, 0);
    if (length == 0 || length > 32768) return false;
    std::vector<wchar_t> shortPath(length);
    const DWORD copied = GetShortPathNameW(path.c_str(), shortPath.data(), length);
    return copied != 0 && copied < length && convert(shortPath.data());
}

bool ParseGogStandardMods(const std::wstring& value, std::vector<GogStandardMod>& output,
    const wchar_t* extension = L".mmxml", std::size_t maximum = kMaximumStandardMods) {
    output.clear();
    if (value.empty() || value.size() > kMaximumStandardManifestCharacters) return false;
    std::vector<GogStandardMod> parsed;
    std::size_t start = 0;
    while (start < value.size()) {
        const auto end = value.find(L'\n', start);
        const auto row = value.substr(start, end == std::wstring::npos ? end : end - start);
        if (parsed.size() >= maximum || row.size() < 38 || row[36] != L'\t') return false;
        GogStandardMod mod;
        for (std::size_t i = 0; i < 36; ++i) {
            const auto c = row[i];
            const bool hyphen = i == 8 || i == 13 || i == 18 || i == 23;
            if (hyphen ? c != L'-' : !((c >= L'0' && c <= L'9') || (c >= L'A' && c <= L'F'))) return false;
            mod.id += static_cast<char>(c);
        }
        const auto path = row.substr(37);
        for (const auto c : path) if (c < 32 || c == L'"' || c == L'|' || c == L'*' || c == L'?') return false;
        const bool drive = path.size() > 3 &&
            ((path[0] >= L'A' && path[0] <= L'Z') || (path[0] >= L'a' && path[0] <= L'z')) &&
            path[1] == L':' && (path[2] == L'\\' || path[2] == L'/');
        const bool unc = path.size() > 4 && path[0] == L'\\' && path[1] == L'\\' && path[2] != L'.';
        if ((!drive && !unc) || path.size() < 6 || _wcsicmp(path.c_str() + path.size() - 6, extension) != 0) return false;
        const DWORD attributes = GetFileAttributesW(path.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY) ||
            !StockModNarrowPath(path, mod.manifest)) {
            WriteLog(("GOG Standard manifest is missing or its path cannot be represented by the stock filesystem: " + mod.id).c_str());
            return false;
        }
        for (const auto& previous : parsed) if (previous.id == mod.id) return false;
        parsed.push_back(std::move(mod));
        if (end == std::wstring::npos) break;
        start = end + 1;
        if (start == value.size()) return false;
    }
    output = std::move(parsed);
    return true;
}

bool RegisterGogStandardMods(const void* stockOptions) {
    // All engine calls happen on the stock startup thread, after its normal
    // local scan. The XML document and Mod records remain owned by Majesty.
    std::vector<GUID> ids(g_gogStandardMods.size());
    for (std::size_t i = 0; i < ids.size(); ++i)
        if (!g_stockModGuidParse(g_gogStandardMods[i].id.c_str(), &ids[i])) return false;
    std::vector<std::string> loaded;
    for (std::size_t i = 0; i < ids.size(); ++i) {
        if (g_stockModLookup(&ids[i])) continue;
        const auto& mod = g_gogStandardMods[i];
        if (std::any_of(loaded.begin(), loaded.end(), [&](const std::string& path) {
                return _stricmp(path.c_str(), mod.manifest.c_str()) == 0;
            })) continue;
        MajestyStringView path{};
        g_stockModStringConstruct(&path, mod.manifest.c_str());
        const bool registered = g_stockModManifestLoad(&path, stockOptions);
        g_stockModStringDestroy(&path);
        if (!registered) {
            WriteLog(("GOG Standard manifest could not be registered: " + mod.manifest).c_str());
            return false;
        }
        loaded.push_back(mod.manifest);
    }
    for (std::size_t i = 0; i < ids.size(); ++i) {
        if (!g_stockModLookup(&ids[i])) {
            WriteLog(("GOG Standard mod is absent from its manifest: " + g_gogStandardMods[i].id +
                " at " + g_gogStandardMods[i].manifest).c_str());
            return false;
        }
    }
    WriteLog("GOG selected Standard mods are registered in the stock installed-mod list.");
    return true;
}

void __cdecl GogStandardModDirectoryScan(
    const MajestyStringView* directory, unsigned recursive, const void* stockOptions) {
    g_stockModDirectoryScan(directory, recursive, stockOptions);
    if (!RegisterGogStandardMods(stockOptions)) {
        StopGogStandardModLaunch(
            "GOG selected Standard mod registration failed. Rescan the selected Workshop packages before relaunching.");
    }
}

bool ValidateGogStandardModProfile() {
    return g_buildProfile != nullptr && g_buildProfile->buildId == MajestyBuildId::Gog &&
        MajestyGogAudit::Validate(g_imageBase, MajestyGogAudit::kStandardMods,
            sizeof(MajestyGogAudit::kStandardMods) / sizeof(MajestyGogAudit::kStandardMods[0])) &&
        RelativeCallTarget(reinterpret_cast<const unsigned char*>(g_imageBase + 0xEFD14)) == g_imageBase + 0x139890;
}

bool InstallGogStandardMods() {
    SetLastError(ERROR_SUCCESS);
    const DWORD length = GetEnvironmentVariableW(kGogStandardManifestsEnvironment, nullptr, 0);
    if (length == 0) return GetLastError() == ERROR_ENVVAR_NOT_FOUND;
    if (length > kMaximumStandardManifestCharacters + 1) return false;
    if (!ValidateGogStandardModProfile()) {
        WriteLog("GOG Standard manifest loader rejected: executable profile or audited stock loader bytes differ.");
        return false;
    }
    std::vector<wchar_t> value(length);
    if (GetEnvironmentVariableW(kGogStandardManifestsEnvironment, value.data(), length) != length - 1 ||
        !ParseGogStandardMods(value.data(), g_gogStandardMods)) return false;
    g_stockModDirectoryScan = reinterpret_cast<StockModDirectoryScan>(g_imageBase + 0x139890);
    g_stockModManifestLoad = reinterpret_cast<StockModManifestLoad>(g_imageBase + 0x1397E0);
    g_stockModGuidParse = reinterpret_cast<StockModGuidParse>(g_imageBase + 0x286530);
    g_stockModLookup = reinterpret_cast<StockModLookup>(g_imageBase + 0x138EA0);
    g_stockModStringConstruct = reinterpret_cast<StockModStringConstruct>(g_imageBase + 0x23C370);
    g_stockModStringDestroy = reinterpret_cast<StockModStringDestroy>(g_imageBase + 0x23C520);
    auto* site = reinterpret_cast<unsigned char*>(g_imageBase + 0xEFD14);
    DWORD previous = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &previous)) return false;
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&GogStandardModDirectoryScan) - reinterpret_cast<std::uintptr_t>(site) - 5);
    std::memcpy(site + 1, &relative, sizeof(relative));
    const bool flushed = FlushInstructionCache(GetCurrentProcess(), site, 5) != FALSE;
    DWORD ignored = 0;
    const bool restored = VirtualProtect(site, 5, previous, &ignored) != FALSE;
    WriteLog("Installed GOG Standard manifest registration at the stock startup directory scan.");
    return flushed && restored;
}
