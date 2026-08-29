# Majesty Mod Manager merge-mod contract

## Scope

This contract applies only to packages shown in **Merge**. Standard `.mmxml`
mods remain independent Active Mod selections; `.mqxml` quests are chosen
through Majesty's stock quest browser rather than the Active Mods list. Source
quests are catalog-only and are never rewritten or duplicated. The current catalog
classification is syntactic: a Mod manifest containing a `CAM` directive is
Merge, while a Mod manifest with no `CAM` directive is Standard. GPL/DAT- or
Descriptions-only mods are not yet routed through the semantic composer, so a
Standard label is not proof that such a package cannot conflict. Semantic
classification of those packages is a target, not current behavior.

The current contract is deliberately fail-closed. It describes what the
composer can prove safe today, not every package that Majesty can load by
ordinary last-writer-wins rules.

This document separates enforced prototype gates from authoring obligations.
The manager fails closed on structures and declarations it can inspect; it
cannot infer an undeclared runtime hook or an unannounced visitor-atlas
dependency.

## Required package shape

A merge-ready package must be complete and independently loadable. The manager
must be able to consume the installed package without its authoring repository.
It must contain all of the following:

1. Exactly one top-level `.mmxml` manifest with a stable UUID and nonempty
   display name. Every load path is package-relative, stays inside the package,
   names an existing file, and appears only once.
2. Only the currently supported manifest load directives: `CAM`,
   `Descriptions`, and `GPL` (`Target` plus ordered `Source` children). Every
   composed dataset has `base="Any"`. Dataset variants and unknown directives
   are not silently flattened.
3. At least one readable CAM and one GPL load. Each GPL target is nonempty and
   each load has at least one declared `.gpl` or `.dat` Source. Authors must
   ship every source needed to reconstruct the compiled project; current
   preflight verifies presence and the build recompiles it, but cannot
   independently prove that an omitted source never existed.
4. Every Description document, CAM archive, art file, and audio payload used by
   the mod. A generated package must not retain a runtime path back into a
   Workshop folder or private source tree.
5. A generic package supplies a matching top-level version-2
   `mod-definition.json`. Version 1 remains readable for legacy packages. A
   trusted UUID-keyed manager compatibility adapter may instead supply an
   external definition or a complete audited replacement package; that
   substitution is reported and never overwrites the installed source.

The current replacement preflight is stricter still: it requires a complete
BDEP provider, exactly one main TILE/IMAG provider and one interface TILE/IMAG
provider, an IMAG reference table in every TILE archive, and at least one
declared custom building whose dialog ID matches `CG[A-Z0-9]{2}`.

The only CAM section types currently accepted are `SMNU`, `STRT`, `DATA`,
`IMAG`, `TILE`, `SPLT`, `DSND`, and `WAVE`. Within `DATA`, the current composer
accepts only `BDEP`. Any additional section or resource kind needs a typed,
stock-traced parser before it can join this contract.

## `mod-definition.json` v2

Version 2 has an exact field set; additional fields are rejected rather than
ignored:

```json
{
  "schema_version": 2,
  "mod_id": "{stable-package-uuid}",
  "internal_name": "NamespacedInternalName",
  "display_name": "Player-facing name",
  "custom_buildings": [
    {
      "local_name": "NamespacedBuildingDescriptionID",
      "dialog_id": "CGxx",
      "controller_base": "APxx",
      "panel_resource_template": "APxx"
    }
  ],
  "runtime_capabilities": []
}
```

Each `local_name` and `dialog_id` is unique within the definition. A custom
building uses a unique manager-safe `CGxx` dialog ID, supplies matching `SMNU`
and `STRT` resources, and declares the stock controller and panel template it
literally follows. The controller's construction, dispatch, state ownership,
callbacks, cleanup, cancellation, and UI refresh lifecycle must be traced to
that stock base. `controller_base` is not permission to replace that lifecycle
with a custom watcher, timer, or hook.

`runtime_capabilities` is a list of lowercase, dotted launcher-feature
identifiers the package needs. Each dot-separated segment starts and ends with
a letter or digit and may contain hyphens; new contracts should use a `.vN`
suffix when revisions will not be backward-compatible. Unknown features make
the mod red and nonselectable. This list is package-owned, so adding a
conforming mod does not require adding its UUID to the manager. Version 1 omits
the field and remains readable for legacy compatibility adapters.

`private-activity-text-registry.v1` is not package-owned. It is reserved and
derived by the composer only when automatic inspection actually detaches one
or more safe private AITX rows. A package or compatibility adapter that tries
to assert it directly is rejected. The generated profile is schema version 2
and records its complete effective capability set, including derived features,
so its definition, binary manifest, merge report, and runtime registry can be
cross-checked as one contract.

Schema version 1 is not accepted as a generic third-party Merge contract. It
cannot state package-owned runtime requirements, so the catalog marks an
unadapted v1 Merge mod red and nonselectable. Version 1 remains usable only
when a trusted manager compatibility profile supplies the missing definition,
capabilities, or complete audited replacement package.

## Stock-relative content requirements

Majesty treats several resources as complete effective tables rather than
independent rows. Whenever a mod changes one, its package must ship the complete
effective resource, preserving stock order, flags, padding, and unchanged
entries. The manager recovers the mod's intended delta by comparing it with the
installed stock game/SDK common ancestor.

The currently supported whole-table resources are:

- `BDEP`, keyed by case-sensitive building ID;
- `UNTN`, `ACTN`, and `HPTX`, keyed by their embedded IDs;
- `QITM` and `AITX`, keyed by positional index; and
- `TILE` and `SPLT`, keyed by positional index and interpreted together with
  their typed references.

Custom quests can load complete `AITX` or `QITM` tables after Active Mods and
therefore supersede Merge-mod text rows. The manager never modifies or copies
installed quests. For `AITX`, the manager automatically finds every
stock-relative changed row in each selected package, then searches that same
package's GPL/DAT sources for direct calls to Majesty's stock text consumers.
The text argument must resolve to the changed row through either an exact
decimal literal or an exact package/stock integer expression. Dynamic and
indirect-only uses fail closed, as does using a row-bound expression through an
unconfirmed non-resolver lifecycle. During Build, the manager restores/removes
the changed positional row, adds one synthetic GPL expression per source Mod
UUID and AITX row, rewrites only the proven stock-resolver argument sites to
that stable manager-owned ID, removes the now-unused exact expression only when
it was defined by that package, and emits
`Data/MMMIntentText.bin`. The launcher DLL resolves only IDs present in that
validated registry; every other ID follows Majesty's stock resolver. Thus
quest-local AITX remains untouched and can load normally. Multiple direct
symbol aliases for one row are supported and share its synthetic ID. A missing
or dynamic-only binding, unsupported indirect use, cross-owner ambiguity,
registry collision, or malformed registry makes the source mod red and
nonselectable.

Package-owned bound expressions are removed only after every use has been
proven and rewritten. Stock-supplied aliases are never removed. If another
selected package refers to an expression that would be removed—outside its own
independently proven private binding—the merge fails rather than breaking that
cross-package dependency. This also lets unrelated packages independently use
the same convenient source alias for different private rows without creating a
false GPL definition conflict.

Before generating a synthetic name, the manager checks every selected GPL/DAT
code reference plus the complete stock/selected expression environment. Any
preexisting use of that reserved `#MMM_AITX_*` name rejects the build instead
of capturing an unrelated symbol.

An explicit GPL conflict resolution has no package owner. Before accepting one,
the manager resolves every stock text-consumer argument against the complete
exact-integer expression environment from the installed stock definitions and
all selected packages. An alternative exact alias for a detached row is
rewritten to that row's synthetic expression; missing, compound, or ambiguous
expression evidence fails closed. This stricter pass applies only to explicit
resolution items and does not reinterpret another package's ordinary numeric
resolver arguments.

Automatic localization is limited structurally to appended rows or installed
stock rows carrying the stock blank-placeholder value (empty text or the stock
literal `empty`). Replacing meaningful stock AITX text may be an
intentional global relabeling, which source syntax cannot prove safe to
privatize, so that package is red and nonselectable. No row numbers are
hardcoded. The merge report records whether each accepted row was appended or
an existing stock placeholder, plus every source expression and generated expression.

Manager IDs are stable hashes of normalized source Mod UUID plus the original
AITX row index in the reserved positive range `0x60000000` through
`0x6FFFFFFF`. Selecting another Merge mod cannot renumber an existing row. The
binary registry is
strictly bounded and fingerprinted in both the manager sentinel and merge
report. This runtime path also covers non-panel consumers that use the common
stock AITX resolver, such as advisor flags and local chat messages. `QITM`
remains an unresolved limitation for legacy private numeric items. New
Merge-ready content should author custom carried items through Majesty's named
inventory-item path rather than adding numeric `QITM` rows. The current
Alchemist input still uses numeric Phoenix Phial ID 113, so this activity-text
fix alone does not make that item's detail text safe under every custom quest.
The manager does not silently migrate it because doing so would change the
native item panel and would not migrate items already stored in saved games.

The current report and build plan fingerprint the complete stock composition
input set: the five stock CAMs used by the composer, `mx_defines.gpl`, both SDK
`OriginalQuests` Description XML directories (including membership), and the
`Gplbcc.exe` compiler. The manager reparses every selected package and rehashes
package, compatibility, and stock inputs after planning, then rechecks them
before, during, and immediately before publishing. Added, removed, changed, or
symlinked inputs fail closed. `MajestyHD.exe` is not part of the merge report;
executable compatibility is guarded separately by the QOL installers and
runtime launcher. A package based on an ancestor the manager cannot identify
is not safe to diff.

## Namespace and asset auditability

Private additions must be namespaced across every runtime namespace they use:
manifest UUID, internal and XML Description IDs, FourCC resource keys, GPL
functions/expressions, DAT blocks, dialog IDs, IMAG keys, `DSND`/`WAVE` keys,
and custom art or sound filenames. GPL and DAT names are compared
case-insensitively; Description keys are compared as case-sensitive
`(element-type, ID)` pairs.

`TILE`/`SPLT` collisions may be relocated only through known typed structures.
Every moved TILE must be reachable through an audited IMAG frame field, and
every moved palette reference must be a parsed TILE palette field. The package
must preserve complete positional tables and section flags, and its emitted
TILE-to-SPLT references must close over the generated palette table. Unknown
IMAG layouts, direct or untyped positional references, truncated tables, and
blind byte-pattern rewriting make the package nonselectable.

All custom payloads used by those records must be present and attributable to
the package. A local merge report records source ownership and hashes; it does
not grant permission to republish another author's assets or materialized stock
content.

## Runtime capabilities

Content that needs behavior outside stock CAM/GPL dispatch must declare a
stable, manager-recognized runtime capability. New or incompatible revisions
should use an explicit `.vN` suffix. A capability is accepted only
after its closest stock mechanism, supported executable fingerprints, hook
sites, ownership, cleanup, and coexistence with the other runtime/QOL patches
have been documented and validated. Unknown declared capabilities fail closed.

Version 2 owns these declarations in the package itself. Version 1 remains a
legacy building-only shape, so extra runtime requirements for a v1 package must
come from a trusted compatibility adapter. The manager cannot discover an
undeclared native hook merely from data files, so authors must declare those
features. Positional `AITX` text is different: its stock-relative row and
direct stock-resolver call sites are automatically discovered rather than
being recorded as package-specific rows in the manager or package definition.

Catalog preflight uses the same typed stock-relative AITX discovery as Build.
Missing or ambiguous bindings are displayed red and cannot be selected; Build
repeats the proof so a package changed after scanning cannot bypass it.

Every generated profile contains
`DataMX/majesty_mod_manager_capabilities.bin`. This is the deterministic MMCP
v1 launcher contract: `MMCP`, little-endian 32-bit version and record count,
then strictly bytewise-sorted records made of a 32-bit byte length and a
canonical lowercase ASCII dotted name. The decoder rejects duplicates,
truncation, trailing bytes, names over 128 bytes, more than 64 records, and
files over 64 KiB. The merge report and manager-owned sentinel both record its
relative path, SHA-256, and record count.

The manager passes the validated absolute path through
`MAJESTY_MOD_MANAGER_CAPABILITIES` on every launch. A Standard-only launch uses
an atomically written empty MMCP manifest, making absence of the environment
variable distinguishable from an intentional manager launch. A merged launch
uses the manifest inside the fingerprinted generated profile. Before launch,
the manager validates the exact generated file set and every SHA-256 recorded
by its sentinel, reparses the package graph and all emitted CAM resources, and
rejects any missing, changed, or additional generated file.

### Generic Visitor Lists

Generic Visitor Lists is a mandatory global launch prerequisite, not a CAM mod.
Setup stages its licensed guarded installer; scan dry-runs it; Launch
idempotently installs and verifies it, and stops if the installer is missing,
the executable is unsupported, or verification fails. `create_build_plan`
currently adds `generic-visitor-lists.v1` to every plan, so this is not a
per-mod opt-in and current compatibility rows need not declare it. The
prototype does not yet detect visitor-producing content or validate
IX92/IX94/TILE atlas closure. The following are therefore authoring
requirements for such content, not automated readiness checks:

- IMAG `IX92monster icons`;
- IMAG `IX94monstor icons n` (the stock misspelling); and
- the complete positional TILE table from the same
  `DataMX/mx_interfacedata.cam` ancestor, with its stock padding and order.

An augmented atlas preserves every stock mapping. A custom monster adds a
25x25 compatible frame and an entry whose four-character type ID exactly
matches its runtime unit Description ID. Shipping only the new atlas row or
icon is unsafe because it removes or invalidates stock mappings. These
resources belong in an `Any` interface-data provider because base quests do not
normally load the expansion atlases.

## Deterministic merge and conflicts

The manager composes the selected packages in an explicit, stable order and
compares semantic records with the stock ancestor:

- identical co-owned changes are accepted once;
- independent keyed additions are unioned;
- whole-table deltas are combined by their documented typed key;
- positional art collisions use deterministic allocation, with only audited
  references rewritten; and
- divergent changes are never resolved by implicit load order.

An overlap proceeds only when the relevant typed merger can prove it is
independent or an explicit resolution selects or supplies the complete intended
semantic result. Today, GPL/DAT conflicts may use an explicit selected-owner
resolution. Divergent Description, named CAM, and whole-table records must
merge cleanly or stop until an equally explicit typed resolution is added.
Unused, misspelled, or stale resolution rules also stop the build.

Explicit overlap resolutions currently come from checked-in compatibility
metadata: selected-owner rules or supplied complete GPL/DAT semantic
definitions. This is separate from custom-text binding, which is automatic and
UUID-agnostic. There is no interactive diff3/manual conflict editor. Any
unrecognized overlap aborts Build. If multiple simultaneously applicable rules
name the same semantic item, Build also stops; registry order never chooses a
winner. A requested item must appear exactly once in its resolution source.
Each supplied semantic resolution is scoped to the mods named by that
combination rule. A third selected mod may repeat one participant's exact
byte-identical definition, but a novel third-party variant remains an
unresolved conflict and stops the build.

The generated report records ordered inputs, stock and output hashes,
stock-relative deltas, allocations, conflicts, explicit resolutions, runtime
capabilities, compiled BCD size, and validation results. Identical ordered inputs
and profile identity produce the same generated UUID and allocations.

## Build, activation, and failure rules

Composition is read-only with respect to every source package. The manager
builds in a staging directory, recompiles GPL with the real SDK compiler,
reparses and round-trips every emitted archive, checks all typed references,
and only then publishes a separate local package through a recoverable
manager-owned staging/backup rename. The generated UUID
is deterministic and never reuses a selected source UUID, even for a one-mod
profile. Build-plan input identity uses the SHA-256 content of every selected
package file, external adapter definition, and compatibility resolution source
rather than timestamps. The manager recomputes that identity
before composition, after composition, and immediately before publication; a
Workshop update or source mutation at any of those boundaries discards staging
and requires Prepare again, so a registry cannot be published beside GPL built
from a different planned input set.

The fixed generated-profile directory is protected by one exclusive sibling
lock from build validation through publication, and from launch validation
until the launched game exits. A second Build or merged Launch fails safely
while that lock is held. Immediately before a merged launch, the manager also
revalidates the selected package, compatibility, stock, generated-profile, and
runtime inputs used by that launch. Standard-only launches do not take this
merged-profile lock.

While a generated profile is active:

- every source Mod represented inside the generated profile is omitted from the
  Active Mod GUID list;
- exactly the validated generated profile is enabled for that Merge set;
- selected Standard mods remain independent Active Mod GUIDs;
- source quests remain untouched and are chosen in the stock quest browser; and
- changing Merge selection or order makes the prior build stale and disables
  manager Launch.

The current Remember Active Mods bridge restores at most 26 Active Mod GUIDs.
The count is selected Standard mods plus one generated Merge-profile GUID when
Merge content is selected; source Merge GUIDs and quests do not count. Launch
fails closed above 26 until an arbitrary-length restore hook is bundled.

Source Workshop items remain installed and untouched. Any manager-owned
compatibility substitution is keyed by the source UUID, uses a complete
audited replacement input, and is disclosed in the report; it never overwrites
the original package.

Catalog and deep-preflight failures are shown red and nonselectable. Conflicts
discovered only during composition currently abort Build and appear as
build-failure diagnostics rather than a persistent red catalog row. In either
case no new partial package is published or projected into the Active Mods
file; any prior generated package remains stale and manager Launch stays
disabled.
