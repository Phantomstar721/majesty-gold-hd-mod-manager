// Included inside the existing runtime owner, after profile/image globals.
PanelEngineModules::State g_panelEngineModules;
bool InitializePanelEngineModules() {
#if defined(CAM_PANEL_ENGINE_SUPPORT)
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
        g_imageBase + reinterpret_cast<const IMAGE_DOS_HEADER*>(g_imageBase)->e_lfanew);
    const auto* sections = IMAGE_FIRST_SECTION(nt);
    bool seen[2] = {};
    for (unsigned i=0; i<nt->FileHeader.NumberOfSections; ++i) {
        unsigned service=0;
        if (!std::memcmp(sections[i].Name,".weng\0\0\0",8)) service=1;
        if (!std::memcmp(sections[i].Name,".sfun\0\0\0",8)) service=2;
        if (!service) continue;
        if (seen[service-1]) return false;
        seen[service-1]=true;
        const auto rva=sections[i].VirtualAddress;
        const auto size=sections[i].Misc.VirtualSize;
        if (rva>=nt->OptionalHeader.SizeOfImage || size>nt->OptionalHeader.SizeOfImage-rva ||
            !(sections[i].Characteristics & IMAGE_SCN_MEM_EXECUTE)) return false;
        const auto* bytes=reinterpret_cast<const unsigned char*>(g_imageBase+rva);
        if (!PanelEngineModules::ValidDescriptor(bytes,size,service,
                static_cast<unsigned>(g_buildProfile->buildId))) return false;
        const auto& d=*reinterpret_cast<const PanelEngineModules::Descriptor*>(bytes);
        if (d.hook>nt->OptionalHeader.SizeOfImage-5) return false;
        const auto* hook=reinterpret_cast<const unsigned char*>(g_imageBase+d.hook);
        if (std::memcmp(hook,d.active?d.patched:d.original,5)) return false;
        std::int32_t relative=0;
        std::memcpy(&relative,d.patched+1,4);
        if (static_cast<std::int64_t>(d.hook)+5+relative!=
                static_cast<std::int64_t>(rva)+256+d.entry) return false;
        if (!d.active) continue;
        if (service==1) {
            g_panelEngineModules.windowEngine=true;
            if (d.revision==2) {
                std::uint32_t bind=0;
                std::memcpy(&bind,bytes+160,4);
                g_panelEngineModules.bindHandoff=reinterpret_cast<PanelEngineHandoff::Bind>(g_imageBase+rva+256+bind);
            }
            g_panelEngineModules.ownsView=reinterpret_cast<PanelEngineModules::Probe>(
                g_imageBase+rva+256+d.ownsView);
            g_panelEngineModules.ownsController=reinterpret_cast<PanelEngineModules::Probe>(
                g_imageBase+rva+256+d.ownsController);
        } else g_panelEngineModules.scriptFunctions=true;
    }
#endif
    return true;
}
