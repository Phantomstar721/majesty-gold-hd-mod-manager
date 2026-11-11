// Included in the pinned, privately compiled Window Engine module only.
static PanelEngineHandoff::Callbacks g_mmHandoff = {};
extern "C" int __cdecl MMWE_BindHandoff(const PanelEngineHandoff::Callbacks* value) {
    if (!value || value->size != sizeof(*value) || value->revision != 1 ||
        !value->capture || !value->describe || !value->wrapped) return 0;
    if (g_mmHandoff.capture && (g_mmHandoff.capture != value->capture ||
        g_mmHandoff.describe != value->describe || g_mmHandoff.wrapped != value->wrapped)) return 0;
    g_mmHandoff = *value;
    return 1;
}
static int MMWE_ManagedTable(void** table, unsigned* count, void** locator) {
    return g_mmHandoff.describe && g_mmHandoff.describe(table, count, locator);
}
static void MMWE_Capture(void* ctrl, void* view, void* unit) {
    if (g_mmHandoff.capture) g_mmHandoff.capture(ctrl, view, unit);
}
static int MMWE_Wrapped(void* ctrl) {
    auto* c = class_of(ctrl);
    if (!c) return 0;
    if (!g_mmHandoff.wrapped) return 1;
    return g_mmHandoff.wrapped(ctrl, c->orig, *(void***)ctrl);
}
