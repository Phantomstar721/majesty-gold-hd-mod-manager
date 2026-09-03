# Native panel ownership and navigation

Custom panel recipes support both Majesty sidebar layouts: a subpanel beneath
its building panel, or a subpanel replacing the building panel. Mod authors do
not need alternate artwork, resolution-specific configuration, or a separate
recipe for these layouts. This applies to the supported research/action,
reward, and occupant panel families.

## Stock reference

The reference is Majesty's existing AP10 → AP69 and MX04 → MX05 dialog lifecycle,
not an alternate layout engine. Addresses below are independently verified RVAs.

| Native mechanism | Public 1.5.2.24 | Beta2 1.5.2.28 |
| --- | --- | --- |
| Open child and decide whether to retain parent | `0xB03F0` | `0xB0CE0` |
| Create and setup-present controller | `0x25910` | `0x268E0` |
| Resolve controller's own building handle | `0x67540` | `0x68780` |
| Layout container selection/fallback | `0xAF150` | `0xAFA40` |
| Dispatch control and consume removal result | `0x25B20` | `0x26AF0` |
| Remove dialog through scalar-deleting destructor | `0x25880` | `0x26850` |
| AP69 command handler, including Back | `0xAE6F0` | `0xAEFE0` |

1. The native opener resolves the initiating controller's building and creates
   the child. The factory result is captured before the final setup virtual.
2. Native layout selects its container. If the secondary container (`0xFA0`)
   is unavailable, it falls back to the primary (`0x7D5`) and records layout
   classification zero. This remains entirely Majesty's decision.
3. The opener returns Majesty's keep/remove result. Native command dispatch
   consumes a nonzero result by removing the initiating panel. A surviving child
   still has its own native handle pair at controller offsets `+0x28/+0x2C`.
4. Native controls resolve that handle when reading building attributes,
   calculating eligibility, submitting commands, and refreshing the UI. Parent
   removal does not remove the building or cancel simulation-owned research.
5. AP69 Back obtains its own building, hides its streamed panel through virtual
   `+0x14`, creates the parent with `(dialog_id, context, 0, 0)`, and returns one
   for native removal of the initiating child. The private implementation changes
   only the parent dialog ID. AP41/MX05 keep their native Back implementations.
6. Every managed vtable retains the native deleting-destructor boundary.
   Exact-instance checks prevent a delayed old destructor from invalidating a
   newly captured controller. Child teardown owns child records and UI targeting
   state; parent teardown owns parent records and opener state.

## Manager integration

- Parent and child MMCR recipes are independent. Closing one panel does not
  invalidate the other unless Majesty actually removes both controllers.
- Attribute/action helpers resolve the live child's native context first.
  A failed child handle lookup must not fall back to some other live parent.
- Reward and occupant openers preserve the native integer return value, just
  like the AP10 opener. Returning zero unconditionally would suppress the stock
  single-panel cleanup.
- A new private child takes the tracked child slot. Creation of unrelated stock
  dialogs is not evidence that an existing panel was destroyed; its registered
  destructor remains the authoritative removal boundary.
- Only a recognized parent creation changes parent recipe mappings. Stock
  Visitors/member lists and notifications must not erase a surviving parent's
  custom commands. This includes parents declaring multiple recipe families.
- AP69 Back is scoped to its actual Back control. An unrelated AP10 creation
  must never be redirected to the previously selected custom building.
- No raw parent building pointer is retained to keep a child functional after
  parent destruction. No resolution check, timer, polling, or mod identity is
  used to select lifecycle behavior.

## Validation

`tests/Test-PanelLifecycleRuntime.ps1` compiles the actual runtime and managed
destructor dispatcher with native-call stubs. Coverage includes single/stacked
lifetimes, native research submission and eligibility, independent context
resolution, Back ordering, mixed reward/occupant parents after stock Visitors,
unrelated dialogs, and delayed teardown. Simulation queue state survives UI
closure; native eligibility still decides whether research is submitted.

`tests/test_panel_lifecycle_profiles.py` checks the stock code listed above in
both executables. Set `MAJESTY_PUBLIC_EXE` and `MAJESTY_BETA2_EXE` to local
references when running the Python test suite.

The manual validation matrix is the same save/mod selection at 1024×768 and a
stacked-panel resolution, checking action submission, Back/reopen, Visitors,
building switches, and save/reload. The native-call tests do not replace those
in-game checks.
