// Included after GogStandardMods.inl. See docs/gog-workshop-quests.md.
constexpr wchar_t kGogQuestManifestsEnvironment[] = L"MAJESTY_MOD_MANAGER_QUEST_MANIFESTS";
std::vector<GogStandardMod> g_gogWorkshopQuests;
using StockQuestDirectoryScan = void (__thiscall*)(void*, const MajestyStringView*, unsigned, const void*);
using StockQuestManifestLoad = bool (__thiscall*)(void*, const MajestyStringView*, const void*);
using StockQuestGuidKey = unsigned (__cdecl*)(const GUID*);
using StockQuestLookup = void* (__thiscall*)(void*, unsigned);
StockQuestDirectoryScan g_stockQuestDirectoryScan = nullptr;
StockQuestManifestLoad g_stockQuestManifestLoad = nullptr;
StockQuestGuidKey g_stockQuestGuidKey = nullptr;
StockQuestLookup g_stockQuestLookup = nullptr;

__declspec(noreturn) void StopGogQuestLaunch(const char* reason) {
    WriteLog(reason);
    MessageBoxW(nullptr,
        L"Majesty Mod Manager could not load the downloaded quests for GOG. "
        L"Rescan in the Manager and launch again. Review MajestyBuildingRuntime.log "
        L"beside the runtime DLL if the problem continues.",
        L"Majesty Mod Manager", MB_OK | MB_ICONERROR);
    TerminateProcess(GetCurrentProcess(), 0x4D4D5154u);
    ExitProcess(0x4D4D5154u);
}

bool RegisterGogWorkshopQuests(void* owner, const void* options) {
    // The stock manager and XML loader own all quest records and resources.
    // Lookup uses Majesty's GUID-to-key routine, then checks the full GUID so
    // a colliding native key cannot silently select a different quest.
    std::vector<GUID> ids(g_gogWorkshopQuests.size());
    std::vector<unsigned> keys(ids.size());
    for (std::size_t i = 0; i < ids.size(); ++i) {
        if (!g_stockModGuidParse(g_gogWorkshopQuests[i].id.c_str(), &ids[i])) return false;
        keys[i] = g_stockQuestGuidKey(&ids[i]);
    }
    std::vector<std::string> loaded;
    for (std::size_t i = 0; i < ids.size(); ++i) {
        if (g_stockQuestLookup(owner, keys[i])) continue;
        const auto& quest = g_gogWorkshopQuests[i];
        if (std::any_of(loaded.begin(), loaded.end(), [&](const std::string& path) {
                return _stricmp(path.c_str(), quest.manifest.c_str()) == 0;
            })) continue;
        MajestyStringView path{};
        g_stockModStringConstruct(&path, quest.manifest.c_str());
        const bool registered = g_stockQuestManifestLoad(owner, &path, options);
        g_stockModStringDestroy(&path);
        if (!registered) {
            WriteLog(("GOG quest manifest could not be registered: " + quest.manifest).c_str());
            return false;
        }
        loaded.push_back(quest.manifest);
    }
    for (std::size_t i = 0; i < ids.size(); ++i) {
        const auto* record = static_cast<const unsigned char*>(g_stockQuestLookup(owner, keys[i]));
        if (!record || std::memcmp(record + 4, &ids[i], sizeof(GUID)) != 0) {
            WriteLog(("GOG quest is absent or its native key conflicts: " + g_gogWorkshopQuests[i].id +
                " at " + g_gogWorkshopQuests[i].manifest).c_str());
            return false;
        }
    }
    WriteLog("GOG downloaded quests are registered in the stock quest manager.");
    return true;
}

void __fastcall GogQuestDirectoryScan(void* owner, void*, const MajestyStringView* directory,
    unsigned recursive, const void* options) {
    g_stockQuestDirectoryScan(owner, directory, recursive, options);
    if (!RegisterGogWorkshopQuests(owner, options))
        StopGogQuestLaunch("GOG downloaded quest registration failed at the stock startup boundary.");
}

bool ValidateGogQuestProfile() {
    return g_buildProfile && g_buildProfile->buildId == MajestyBuildId::Gog &&
        MajestyGogAudit::Validate(g_imageBase, MajestyGogAudit::kWorkshopQuests,
            sizeof(MajestyGogAudit::kWorkshopQuests) / sizeof(MajestyGogAudit::kWorkshopQuests[0])) &&
        RelativeCallTarget(reinterpret_cast<const unsigned char*>(g_imageBase + 0xEFCE0)) == g_imageBase + 0x119650;
}

bool InstallGogWorkshopQuests() {
    SetLastError(ERROR_SUCCESS);
    const DWORD length = GetEnvironmentVariableW(kGogQuestManifestsEnvironment, nullptr, 0);
    if (!length) return GetLastError() == ERROR_ENVVAR_NOT_FOUND;
    if (length > kMaximumStandardManifestCharacters + 1 || !ValidateGogQuestProfile()) return false;
    std::vector<wchar_t> value(length);
    if (GetEnvironmentVariableW(kGogQuestManifestsEnvironment, value.data(), length) != length - 1 ||
        !ParseGogStandardMods(value.data(), g_gogWorkshopQuests, L".mqxml",
            kMaximumStandardManifestCharacters / 38)) return false;
    g_stockQuestDirectoryScan = reinterpret_cast<StockQuestDirectoryScan>(g_imageBase + 0x119650);
    g_stockQuestManifestLoad = reinterpret_cast<StockQuestManifestLoad>(g_imageBase + 0x1195A0);
    g_stockQuestGuidKey = reinterpret_cast<StockQuestGuidKey>(g_imageBase + 0x136B10);
    g_stockQuestLookup = reinterpret_cast<StockQuestLookup>(g_imageBase + 0x117F60);
    g_stockModGuidParse = reinterpret_cast<StockModGuidParse>(g_imageBase + 0x286530);
    g_stockModStringConstruct = reinterpret_cast<StockModStringConstruct>(g_imageBase + 0x23C370);
    g_stockModStringDestroy = reinterpret_cast<StockModStringDestroy>(g_imageBase + 0x23C520);
    auto* site = reinterpret_cast<unsigned char*>(g_imageBase + 0xEFCE0);
    DWORD previous = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &previous)) return false;
    const auto relative = static_cast<std::int32_t>(
        reinterpret_cast<std::uintptr_t>(&GogQuestDirectoryScan) - reinterpret_cast<std::uintptr_t>(site) - 5);
    std::memcpy(site + 1, &relative, sizeof(relative));
    const bool flushed = FlushInstructionCache(GetCurrentProcess(), site, 5) != FALSE;
    DWORD ignored = 0;
    const bool restored = VirtualProtect(site, 5, previous, &ignored) != FALSE;
    WriteLog("Installed GOG quest registration after the stock local quest scan.");
    return flushed && restored;
}
