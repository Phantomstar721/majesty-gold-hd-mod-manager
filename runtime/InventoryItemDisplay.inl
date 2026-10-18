// AP22 real inventory rows. Stock still owns enumeration, refresh and cleanup.
std::uintptr_t g_inventoryItemResume = 0;

bool InventoryItemRowsSelected() {
    return std::any_of(g_runtimeFeatureRegistry.heroInfoRows.begin(),
        g_runtimeFeatureRegistry.heroInfoRows.end(), [](const HeroInfoRecord& row) { return row.kind == 5; });
}

std::uintptr_t InventoryItemBody() {
    if (!g_buildProfile) return 0;
    switch (g_buildProfile->buildId) {
    case MajestyBuildId::SteamPublic: return 0xA2E30;
    case MajestyBuildId::SteamBeta2: return 0xA3710;
    case MajestyBuildId::Gog: return 0xA3CC0;
    default: return 0;
    }
}

bool ValidateInventoryItemDisplay() {
    if (!InventoryItemRowsSelected()) return true;
    const auto rva = InventoryItemBody();
    if (!rva) return false;
    const auto index = MajestyFeatureParity::Index(g_buildProfile->buildId);
    const std::uint32_t hashes[] = {0xEC2A9E79u, 0xD550412Eu, 0x48455371u};
    auto hash = 2166136261u;
    const auto* bytes = reinterpret_cast<const unsigned char*>(g_imageBase+rva);
    for (unsigned i=0;i<0x1A1;++i) hash=(hash^bytes[i])*16777619u;
    if (index<0 || hash!=hashes[index]) return false;
    const std::uintptr_t appends[] = {0xB5040,0xB4750,0xB5640};
    bytes = reinterpret_cast<const unsigned char*>(g_imageBase+appends[index]);
    hash=2166136261u;
    for(unsigned i=0;i<0x1E;++i) hash=(hash^bytes[i])*16777619u;
    return hash==0xD64DAA54u;
}

void __stdcall DecorateInventoryItem(std::uint32_t controller, int index, unsigned key) {
    if (index < 0 || (key & 0xFFFFFFu) != 0x564E49u || (key >> 24) > 127) return;
    const auto* row = g_runtimeFeatureRegistry.FindHeroInfo(5, key >> 24);
    if (!row) return;
    auto label = HeroInfoString(row->displayText);
    auto tooltip = HeroInfoString(row->tooltipText);
    // Synchronous native copies; these views never become row-owned strings.
    SendControllerMessage(controller, 0x232D, 0x60, index, reinterpret_cast<unsigned>(&label));
    SendControllerMessage(controller, 0x232D, 0x62, index, reinterpret_cast<unsigned>(&tooltip));
    alignas(4) unsigned char image[0x6C] = {};
    g_heroImageCtor(image);
    g_heroImageType(image, 1);
    g_heroImageId(image, row->imageId);
    g_heroImageSet(image, row->imageSet);
    g_heroImageFrame(image, 0);
    *reinterpret_cast<std::uint32_t*>(image+0x1C)=0;
    g_heroImageFlags(image, 9);
    SendControllerMessage(controller, 0x232D, 0x24, index, reinterpret_cast<unsigned>(image));
    g_heroImageDtor(image);
}

__declspec(naked) void InventoryItemAppendHook() {
    __asm {
        // Replay the complete overwritten stock push/call first.
        push 232Dh
        call eax
        pushfd
        pushad
        push dword ptr [ebx+0Ch]
        push eax
        push esi
        call DecorateInventoryItem
        popad
        popfd
        jmp dword ptr [g_inventoryItemResume]
    }
}

bool InstallInventoryItemDisplay() {
    if (!InventoryItemRowsSelected()) return true;
    const auto body = InventoryItemBody();
    g_inventoryItemResume=g_imageBase+body+0x13F;
    return WriteOccupantBranch(g_imageBase+body+0x138,
        reinterpret_cast<void*>(&InventoryItemAppendHook),0xE9,7);
}
