# Mod Manager runtime registries

MMCR v18 adds optional child DialogID/opener fields to private recruitment
records; inline-only recruitment stays v17. The child retains AP52's native
17-slot class and uses stock secondary-container layout and Back ownership.
See [private AP52 recruitment](stock-ap52-private-recruitment.md).
The [private hero source recipes](private-hero-integration.md) emit GPL only;
they add no runtime hook or registry record.

The injected runtime does not infer native behavior from package names, mod
UUIDs, or the presence of individual CAM resources. For every launch, the Mod
Manager generates three deterministic files:

- `DataMX/majesty_mod_manager_capabilities.bin` (`MMCP`) selects the runtime
  hook groups needed by the composed package.
- `DataMX/majesty_mod_manager_features.bin` (`MMFR`) supplies the validated
  private name-generator and AP78-row records, optional query flags and declared
  resources for native timing services.
- `DataMX/majesty_mod_manager_controllers.bin` (`MMCR`) supplies the validated,
  manager-resolved recipes for the supported stock controller lifecycles.

Their absolute paths are published through
`MAJESTY_MOD_MANAGER_CAPABILITIES`, `MAJESTY_MOD_MANAGER_FEATURES`, and
`MAJESTY_MOD_MANAGER_CONTROLLERS`, respectively. The manager writes empty,
valid MMFR and MMCR files when no data-driven feature needs them, so every
manager launch has one unambiguous registry set.

The launcher starts Majesty suspended and releases it only after the DLL has
validated all three files, checked that MMCP agrees exactly with the non-empty
MMFR/MMCR sections, validated the selected public or beta2 executable profile,
installed only the selected hook groups, and signaled the existing ready event.
A missing file, relative or non-canonical path, malformed record, unsupported
capability, registry mismatch, executable-profile mismatch, or failed required
install terminates the suspended process before a game can load. Injecting the
DLL without the MMCP environment variable is not a Mod Manager launch and
installs no optional hook.

## MMCP v1

All integers are little-endian.

```text
4 bytes  magic "MMCP"
u32      schema version (1)
u32      capability count (0..64)
repeat count times:
  u32    capability byte length (1..128)
  bytes  lowercase ASCII capability name
```

Names use the same dotted, lowercase segments accepted by manager package
definitions. Records must be strictly increasing by their raw ASCII bytes, so
duplicates are invalid. The parser rejects trailing bytes and files larger than
64 KiB. It also rejects a well-formed capability it does not support; an older
DLL therefore cannot silently run a package that needs a newer hook.

### Canonical generated capabilities

| Capability | Runtime behavior and required data |
|---|---|
| `expanded-building-slots.cg-prefix` | Installs the stock unknown-dialog fallback used for manager-allocated internal building dialog IDs. |
| `freestyle-cam-rebind.v1` | Installs only the generic Freestyle CAM lifecycle repair. |
| `private-activity-text-registry.v1` | Requires a valid, non-empty MMTX file and installs only the shared stock activity-text resolver extension. |
| `generic-visitor-lists.v1` | Accepted marker for the external CAM data patch; installs no executable hook. |
| `stock.name-generator.v1` | Requires at least one validated MMFR name-generator record and installs the shared stock registry-completion extension. |
| `stock.ap78-enchantment-row.v1` | Requires at least one validated MMFR AP78 row and installs the shared scoped AP78 presenter extension. |
| `stock.controller-recipes.v1` | Requires at least one resolved MMCR recipe and installs only the stock-controller hook groups selected by those records. |
| `stock.map-fog-query.v1` | Requires the MMFR map-query flag and registers read-only, bounded native GPL map queries. |
| `stock.movement-query.v1` | Requires the MMFR movement-query flag and registers read-only native unit/description locomotion queries. |
| `manager.overlay-movement-scale.v1` | Beta2-only: requires MMFR v8 overlay percentages; scales one native linear-order step while the overlay is attached, preserving stock timing and lifecycle. |
| `stock.native-timing.v1` | Requires MMFR v3 timing selection and registers the stock clock, read-only movement/action base periods, declared effector-time queries and learned-spell cooldown commits. |
| `stock.equipment.v1` | Local beta2-only trial: requires MMFR v4 equipment records and extends stock enum/name/icon tables. No purchase, combat, save, or timer hooks. |
| `manager.kingdom-research.v1` | Local beta2-only trial: requires MMFR v5/v6 research records, saved GPL owner state, and a private AP52 parent. Uses the stock queued purchase/order/completion lifecycle and declared earned-reward boundaries; optionally reconciles private active effects at native lifecycle events. |

The manager derives these data-driven capability names from the generated
registries. A package cannot enable one merely by copying the capability string
into its definition. Conversely, a non-empty corresponding registry without
its generic capability is rejected before any hook is installed.

Schema-v1/v2 package definitions can still contain the historical aliases
`alchemist.cgbrewing-secondary-controller`,
`alchemist.ap78-private-oil-rows`, `alchemist.nm18-name-generator`, and
`phantom.nm19-name-generator`. Those are package-input compatibility aliases,
not package-specific runtime branches. The manager translates them into the
same generic records described below and emits only the canonical generic MMCP
capabilities. New packages describe typed runtime features instead of using
these aliases.

## MMFR v1-v8

MMFR is an immutable, data-only registry. It cannot carry a DLL, path, RVA,
patch byte, callback, or instruction.

```text
4 bytes  magic "MMFR"
u32      schema version (1)
u32      name-generator count (0..256)
u32      AP78-row count (0..1024)

repeat name-generator count times:
  u32    private NM FourCC
  u32    first HN FourCC
  u32    second HN FourCC
  u32    third HN FourCC
  u32    fourth HN FourCC

repeat AP78-row count times:
  u32    overlay FourCC
  u32    display-text byte length (1..512)
  bytes  non-NUL Windows-1252 display text
```

Each section is strictly increasing by its primary FourCC. Name-generator IDs
must start with `NM`, may not claim stock `NM01` through `NM17`, and must refer
to four distinct printable `HN` FourCCs outside stock `HN01` through `HN68`.
Overlay IDs may be any printable FourCC that the composed package owns as a
package-added Description rather than a stock override. The file is limited to
1 MiB and rejects
duplicates, undefined Windows-1252 bytes, truncation, trailing data, and
conflicting declarations. The manager additionally proves the corresponding
package-owned Description and text/overlay resources before it emits a record.

Arbitrary validated records within these bounds share the same two stock hook
groups. The runtime does not contain an `NM18`, `NM19`, Alchemist, Phantom, or
specific-overlay branch.

Version 2 adds one little-endian `u32` flags field immediately after the two
section counts, before any records. Bit 0 enables `stock.map-fog-query.v1`;
bit 1 enables `stock.movement-query.v1`. All other bits must be zero.
The writer retains v1 unless either native query feature is
requested. See [data-record lists and bounded map queries](stock-data-record-list-and-map-query.md)
for the GPL function signatures, input bounds, and explicit continuation status.
See [movement-rate queries](stock-movement-query.md) for normal/effective live
unit rates, named-description rates, and failure values. Both features share one
stock GPL registration adapter; movement-only use does not enable map queries
or modify stock PathCost.

MMFR v3 is emitted only for `stock.native-timing.v1`. It retains the v2 layout,
requires flag bit 2, and appends two resource families after the AP78 rows:
`u32 spell_count`, that many `u32` action FourCCs, then `u32 effector_count`
and that many overlay FourCCs. Each family is strictly numerically increasing,
unique and limited to 1024 printable FourCCs. Empty families select clock and
read-only base-period support. Bits above 2, missing bit 2 in v3, truncation and trailing bytes fail
closed. V1/v2 output is unchanged when timing is unselected. The native timing
interface shares the same single GPL registration adapter; it adds no scheduler
or background work. See [native timing](stock-native-timing.md).

MMFR v4 is emitted only when private equipment is selected. It adds required
flag bit 3 and permits bits 0–3. Timing families remain present only when bit 2
is set. After all prior records/families, it appends `u32 equipment_count`
(1–256), followed by three `u32` fields per record: stable equipment identity
(0x800000–0xFFFFFF), slot (0 weapon, 1 armor), and printable name-table FourCC.
Records are strictly increasing by identity. The icon set uses that same
identity within stock INBw/INBa; the enum name is `MME_` plus six uppercase hex
digits. No file paths or callbacks are supplied. Readers reject invalid slots,
duplicate identities, missing bit 3, truncation, and trailing data. V1–v3
output is unchanged without equipment. See the [trial contract](stock-equipment-contract.md)
and [native audit](stock-custom-equipment-audit.md) for stock ownership and
remaining in-game validation.

MMFR v5 is emitted only when saved kingdom research is selected. It requires
flag bit 4 and permits bits 0–4. Timing and equipment sections remain present
only when their respective flags are set. After the prior selected sections,
v5 appends `u32 research_count` (1–32), followed by these records:

```text
16 bytes stable identity derived from package UUID and feature key
u32      printable three-byte native building family (high byte zero)
u32      private action control ID
u32      audited stock descriptor template control ID
u32      private completion display attribute
u32      required completed level (1–3)
u32      price (1–1,000,000)
u32      earned-gold bonus percent (0–100)
u32      earned-XP bonus percent (0–100)
u32      progress control ID
u32      active-display control ID
u32      completion-text byte length (1–96)
bytes    non-NUL Windows-1252 completion text
```

The fixed record prefix is 60 bytes. Identities are strictly increasing;
identities, action IDs, completion attributes and building families must each
be unique. At least one percentage must be nonzero. The native parser rejects
invalid fields, missing bit 4, empty final sections, truncation and trailing
bytes. The Manager additionally proves the owned Description/DAT/prototype
chain and literal panel group. V1–v4 output is unchanged without this feature.

MMFR v6 is selected only when at least one research declares `active_effector`.
It retains v5 flags and appends `u32 name_length`, then that many ASCII bytes,
after **each** record's completion text. Zero means no effect for that record;
otherwise the name must match `[A-Za-z_][A-Za-z0-9_]{0,63}`. There must be at
least one nonempty name. Names refer to validated private Overlay descriptions,
not arbitrary script entry points. V5 remains the unchanged effect-free format.
The MMCP capability is derived from these validated records, never accepted as
an author-supplied hook request. See the [test-build contract](kingdom-research-contract.md)
and [stock audit](stock-kingdom-research-audit.md); live acceptance is pending.

MMFR v7 adds flag 32 and a final hero-information section. It is emitted only
when `stock.ap78-info-row.v1` rows are selected; older feature sets keep their
unchanged wire versions. Each of 1–1024 sorted rows contains eight `u32` values:
kind (1 spell, 2 enchantment, 3 passive), subject FourCC, unlock level, private
image FourCC, set ID, key length, label length and tooltip length. Key ASCII and
label/tooltip Windows-1252 bytes follow. Ordering is by kind, numeric FourCC and
key; spell/effect subjects are unique. The complete MMFR remains capped at 1 MiB.
Research records in v7 include the v6 optional effector length even when empty.
See the [AP78 stock lifecycle and author contract](stock-ap78-info-rows.md).

MMFR v8 adds flag 64 and a final movement-scale section after the other selected
sections: `u32 count` (1–256), then `{u32 overlay_id, u32 percent}` pairs sorted
strictly by numeric FourCC. Percent must be 1–1000. Research retains its v6/v7
effect-length field. V8 requires bit 6 and permits only bits 0–6; empty sections,
duplicates, malformed IDs and trailing data are rejected. Without movement
scaling the writer retains the older appropriate version. See the
[overlay movement contract and native lifecycle](stock-overlay-movement-scale.md).

## MMCR controller recipes

MMCR is likewise manager-owned and data-only. Its path is supplied through
`MAJESTY_MOD_MANAGER_CONTROLLERS`; package JSON is never parsed inside Majesty.
The manager first resolves package-local building and child-dialog identities,
then writes exact runtime identities and validated recipes into the binary
registry.

The base header contains magic `MMCR`, a schema version, and nine
little-endian section counts. Later canonical versions append their section
counts in this order:

1. AP10-owned/AP69-shaped secondary panels;
2. AP22 packed-resource meters;
3. AP99 research rows;
4. AP17 upgrade/research gates;
5. AP24 timed Rage actions;
6. AP24 one-shot Rage command actions;
7. AP69 sovereign-target actions;
8. MX09-owned/AP41-shaped reward panels; and
9. AP41/Fl00 hostile-monster reward actions;
10. MX04/MX05 occupant-action panels (v3); and
11. MX22 building open/closed toggles (v4); and
12. MX05 live-agent-list panels with bounded static row variants, an optional
    post-action stay-on-panel policy, and an optional row-click focus policy
    (v14), plus optional parent-scoped actions (v15), or independent data-record
    rows (v16); and
13. AP52 private three-choice recruitment presenters (v17).

The writer retains canonical v2 when neither newer section is needed, uses v3
when occupant panels are present, and uses v4 when building toggles are
present. It uses v14 when a live-agent list retains selected-row action scope;
a list that requests parent action scope uses v15. Independent data-record
lists use v16, which adds a boolean `u32` record-row flag after each list's
action-scope field. They require explicit titles, parent-scoped actions,
stay-on-panel behavior, and no world refocus; their keys never resolve as Units.
Private AP52 recruitment uses v17 with a thirteenth section count. Each record
stores its qualified panel key, resolved parent dialog ID and private third
price control ID. Hero choices, prices, capacity and upgrades are not duplicated
in MMCR; they remain in the native descriptions.
Other recipes retain their existing versions. A newer-version header with
an empty final section is noncanonical.

Records are deterministically sorted within their section and refer to an
existing panel through a manager-qualified `panel_key`. The parser validates
all cross-references, unique dialog/family/command/action/private-mode
ownership, non-overlapping panel control IDs, levels and numeric ranges,
printable FourCCs, callback-symbol syntax, and bounded non-NUL Windows-1252
text. Logical keys and callback symbols are at most 64 bytes; completion text
is at most 96 bytes; the complete registry is at most 512 KiB, with at most 32
panels and 256 records in total. Any truncation, trailing bytes, non-canonical
ordering, invalid reference, or ownership collision fails closed.

MMCR records are alternatives routed through Majesty's existing serialized
stock lifecycles. They do not create parallel controller systems. At runtime
there is one active AP10/AP69 parent-child panel chain, one active AP99 research
owner, one pending Rage command/action handoff, one active timed-Rage UI owner,
and one sovereign-target session. Dialog replacement, stock controller
destruction, command completion, cancellation, and quest/resource teardown
remain the boundaries that clear those states. The registry may contain many
validated alternatives, but it does not promise simultaneous ownership that
the corresponding stock mechanism does not support.

## Validation coverage

The standalone C++ parsers cover empty and populated canonical registries plus
unknown, unsorted, duplicate, conflicting, truncated, oversized, and
trailing-byte inputs. `Test-RuntimeBuild.ps1` additionally proves that optional
installers remain inside their generic MMCP/data guards, while the dual-profile
test validates every selected stock site for both supported executables.
