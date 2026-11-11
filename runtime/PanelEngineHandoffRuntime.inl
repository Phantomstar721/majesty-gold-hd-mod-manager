// Uses only the existing declared controller recipes and lifecycle registry.
void __cdecl CapturePanelEngineActionOwner(void* ctrl, void* view, void* unit) {
    if (!g_captureParentController && !g_captureChildController) return;
    const auto value = reinterpret_cast<std::uint32_t>(ctrl);
    if (!ctrl || *reinterpret_cast<void**>(value + 0x24) != view ||
        NativePanelContext(value) != unit) {
        StopUnsafeManagerRuntimeLaunch("The panel presentation handoff lost its declared building context.");
        return;
    }
    CaptureSecondaryController(value, 0);
}
int __cdecl DescribePanelEngineActionOwner(void** managed, unsigned* count, void** locator) {
    std::size_t entries = 0;
    void** stock = nullptr;
    if (!count || !locator || !MajestyControllerLifecycle::DescribeManagedVtable(managed, &entries, &stock) ||
        entries < 9 || entries > 17) return 0;
    *count = static_cast<unsigned>(entries);
    *locator = stock[-1];
    return 1;
}
int __cdecl CompletePanelEngineHandoff(void*, void** managed, void** presenter) {
    std::size_t entries = 0;
    void** stock = nullptr;
    if (!MajestyControllerLifecycle::DescribeManagedVtable(managed, &entries, &stock)) return 1;
    if (MajestyControllerLifecycle::RegisterPresenterAlias(presenter, managed)) return 1;
    StopUnsafeManagerRuntimeLaunch("The panel presentation handoff could not retain its cleanup owner.");
    return 0;
}
bool BindPanelEngineActionOwners() {
    if (!g_panelEngineModules.bindHandoff) return true; // legacy native-only module
    const PanelEngineHandoff::Callbacks callbacks = {sizeof(callbacks), 1,
        &CapturePanelEngineActionOwner, &DescribePanelEngineActionOwner, &CompletePanelEngineHandoff};
    return g_panelEngineModules.bindHandoff(&callbacks) != 0;
}
