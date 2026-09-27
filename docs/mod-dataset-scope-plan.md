# Dataset-aware generated output

Status: implemented in source, pending in-game acceptance. Applies to Steam
public, Steam beta2 and GOG through their existing native Mod loader. No runtime
dispatcher or additional executable hooks are used.

## Recommendation in plain terms

Keep one managed output folder and one logical Manager selection. Store shared
content once. When a script genuinely needs different versions for original and
expansion quests, put those small differences into native, separately identified
Mod records scoped to the appropriate quest type. Majesty already chooses which
records to load. Do not create a copy of the original Standard mod.

Use the existing `Any` generated record for common output, plus a `Majesty` record
and/or `MajestyExpansion` record only when that scope needs a patch. A profile
with no scoped differences retains the existing single-record layout. At most
three generated records are needed, independent of the number of source mods.

This is the smallest change to the current shared runtime/artwork/profile model.
It is not free: conditional records consume additional active IDs and require
extra compilation/loading only when emitted. They do not add gameplay polling,
per-unit state or per-action dispatch.

## Native evidence and lifecycle

Addresses are RVAs at image base `0x400000`; executable identities are recorded
in the [initial audit](standard-script-provider-review.md).

| Boundary | Steam beta2 | Steam public | GOG |
| --- | --- | --- | --- |
| Iterate every Mod in one manifest | `13A1C0` | `125900` | `139760` |
| Register each Mod | `139FF0` | `125730` | `139590` |
| First Dataset/base reader | `0FA050` | `0F7EA0` | `0FA6B0` |
| Source-resource reader, Dataset-zero lookup | `0FF1A9` | `0FCFF9` | `0FF939` |
| First type call in active resource filter | `13A8E0` | `126020` | `139BE0` |
| Save-context Mod-ID/name collector | `139990` | `1250D0` | `138F30` |
| Collector call from save path | `04F4B9` | `04E519` | `04F3D9` |

1. Native manifest registration iterates Mod index zero, one, etc., registering
   each distinct GUID. Each record retains its XML document and resolves paths
   relative to the same package. The loop/increment and registration call were
   inspected independently in all three executables.
2. Active Mod order is separate from manifest registration. The Manager must
   explicitly restore Standard IDs first, then common generated output, then the
   scoped patch IDs. XML order alone is not sufficient.
3. Quest resource collection walks the active list and includes each record only
   for matching type or `Any`. Each Mod's reader uses its first Dataset. Do not
   implement this as sibling Datasets under a single Mod GUID.
4. The save-path collector also filters by requested type or `Any`, then copies
   the native 16-byte GUID and display name. The caller supplies the quest type
   from its state (`+0xA4`) and a save-context list. The same structure was traced
   on all three builds. Opposite-scope records therefore are not collected by
   this path just because their IDs are in the active list.
5. Use native ownership and teardown. The existing documented
   [GOG registration lifecycle](gog-standard-mods.md) covers XML retention, native
   installed/active lists, and resource teardown. No additional live object,
   callback, watcher, cancellation handler or cleanup hook is required by files
   containing ordinary Mod records.

These are static findings. They do not establish save compatibility for changed
gameplay or replace base/expansion transition and save/load playtests.

## Composition algorithm

1. Preserve each selected input's native scope and load order. Treat `Any` as
   eligible in both views; do not infer scope from folder names or mod identity.
2. Reuse one parsed/input-proof snapshot. Evaluate only the affected script
   composition for the original-game and expansion views. Native fallbacks use
   each view's actual stock and eligible Standard definitions. Comparisons of
   authored Merge edits, including reconciliation with source-backed Standards,
   retain the existing full-SDK common source ancestry (including helper proofs);
   a destination dataset is not their source ancestor. Changing that ancestor
   falsely treats shared expansion ancestry as
   competing mod insertions. Comparison ancestors are not emitted as defaults.
   Both loaders reuse the same stock snapshot. Do not rerun CAM,
   artwork allocation, whole-package inventory or compiler proof for each view.
3. Run the same callback/discovery/validation pipeline for both script results.
   Already-native, unchanged definitions remain in their original mod.
4. Put equal, valid-in-both patches in common output. Put differing definitions
   in their scoped output only. Check dependency availability in each effective
   view: equality of a caller's text alone does not prove that its dependencies
   are common. Generated functions, expressions, DAT bindings and callbacks must
   not reference an unavailable opposite-scope definition.
5. Compile only nonempty outputs. Share common CAM, descriptions, runtime
   registries and other unchanged files. Do not generate a second full profile
   or duplicate the original Standard assets.
6. Package records, file hashes, IDs, scope and order together in the existing
   atomic publication/report/sentinel transaction. Prune obsolete scoped files
   as part of replacing that owned bundle, not through global folder searches.

The first consumer is Standard GPL preservation. Scope metadata and output
packaging should be resource-neutral, but this is not authorization to invent
automatic merges for every artwork/description namespace now. A future scoped
resource must have its own native composition evidence before it is emitted.

## Manager changes required

- Keep the existing common GUID derivation. Derive scoped identities
  deterministically from the logical profile and scope; track which source mods
  they represent. Never use another mod's GUID or rewrite save IDs to bypass a
  mismatch. Content fingerprints still decide when a rebuild is required.
- Extend generated-output validation/report/readback to support a bundle of
  records. Today these paths require one Mod and an `Any` Dataset.
- Launch/remember the complete ordered ID bundle. Expand remembered generated
  IDs back to the user's choices, and exclude every generated record from input
  discovery using the owned bundle metadata.
- Keep one runtime registry set. This change is native data loading, not separate
  runtimes per scope. Validate its references against both effective views.
- Account for the current **26 active-ID persistence limit** before Prepare and
  Launch. Optional scoped records count toward it. Do not silently drop an ID
  or expand the runtime restore hook as an unrelated workaround.
- Native Majesty's selector may display additional generated records; the
  Manager can group them logically but should not promise stock UI hiding.

Preserving the common GUID avoids needless identity churn, but is not a promise
that an old save is compatible with altered script state. New saves require the
applicable scoped ID. Removing a patch record or changing selections must report
that honestly rather than retaining dummy records to trick missing-mod checks.

## Alternatives considered

- **Extra Dataset siblings under one Mod:** the native readers use Dataset zero;
  not a supported conditional dispatch mechanism.
- **Flatten all scripts into Any:** leaks scoped behavior into other quests.
- **Two full generated profiles:** can use stock scopes, but duplicates full
  composition work and complicates the current single shared runtime/art model.
  Two scoped records referencing common files are viable and save one active ID
  compared with three records; they replace the existing common identity/layout.
  For this repository, preserving the common record and emitting only necessary
  deltas is the smaller migration. Revisit only if the ID limit becomes material.
- **Select a profile before launching:** insufficient because the player can
  change quest type in the same game session.
- **A custom runtime scope dispatcher:** adds executable-specific hooks and
  ownership that ordinary native Mod filtering already supplies. Not justified.

## Acceptance before deployment

Exercise all three builds with base -> expansion -> base transitions in one
session, a save/reload for each, unchanged and changed Standard order, both scoped
providers together, and no scoped provider selected. Confirm active order, exact
saved required IDs, callback presence, absence of opposite-scope behavior, and
native resource cleanup. Include a near-limit active-ID selection, interrupted
publication, old generated bundle recognition and removal of a now-empty delta.
Measure cold/warm Prepare separately, including additional compiler launches.

No claim of complete scoped-output support should be made before those checks.

## Implementation notes, 2026-09-27

`prepare_gpl_bundle` reuses the captured Standard source/proof inputs and one
stock dataset-symbol snapshot. With no Standard GPL input it retains the original
single-composition path. With native script inputs it composes the two effective
GPL views, using original stock bodies wherever they exist for original quests.
Base-absent expansion helpers required by Manager features still use the existing
explicit dependency closure. Expansion views do not import already-loaded stock
helpers redundantly. Common definitions must occur identically in both complete
views; missing definitions are not filled from the opposite view. Known
opposite-scope native references, including callback assignments, are rejected.

The original Healer and Monk decision trees omit Bazaar. Their callback gap is
the same pair of stock decisions between which expansion inserts Bazaar. The
original reset/death helpers also omit expansion's StopMoving/DeleteAllEffectors
calls. Their literal stock bodies are recognized separately and preserved.
Native additions between cleanup and death dispatch are retained; the dispatch
must remain a unique top-level branch after cleanup in the expansion form.

Generated schema-5 ownership includes the complete active-ID list. Readback
checks record order/scope/identity, scope-owned paths, every output hash, and
runtime evidence against each common-plus-scoped source view. Schema-4
single-record output remains readable. Saved selection expansion and the startup
cache carry all generated IDs. The guaranteed minimum ID count is checked during
selection; exact delta count is checked before compilation/publication so a
near-limit selection is not rejected merely because it *might* need two patches.
Launch retains its independent 26-ID guard.

The source checks include literal installed potion and hero-tree source fixtures,
separate compilation of emitted script parts, dependency isolation, no-difference
and one-sided outputs, multi-record readback, altered IDs/paths/files, launch order,
selection restoration and empty common script output. These are not a live
base/expansion transition or save/load result. The normal owned-directory atomic
replacement remains the publication mechanism; optional deltas disappear with
their replaced bundle rather than being retained as dummy save dependencies.
