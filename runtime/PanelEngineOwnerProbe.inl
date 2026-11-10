// Included after the pinned WE1 source by the isolated alpha module build.
// No new instance registry: the engine's existing class copies own teardown.
// Before construction only the view's actually loaded STRT is inspected.
// The Manager calls these only after verifying the versioned module image.
extern "C" int __cdecl MMWE_OwnsView(void* view) {
    void* table = 0;
    const int count = count_view_texts(view, &table);
    Line line;
    for (int index = 0; index < count; ++index)
        if (parse_line(text_at(table, index), &line)) return 1;
    return 0;
}

extern "C" int __cdecl MMWE_OwnsController(void* controller) {
    return controller && class_of(controller) ? 1 : 0;
}
