# Mod Manager runtime registries

The injected runtime does not infer native behavior from package names, mod
UUIDs, or the presence of individual CAM resources. For every launch, the Mod
Manager generates three deterministic files:

- `DataMX/majesty_mod_manager_capabilities.bin` (`MMCP`) selects the runtime
  hook groups needed by the composed package.
- `DataMX/majesty_mod_manager_features.bin` (`MMFR`) supplies the validated
  private name-generator and AP78-row records consumed by those hook groups.
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

The manager derives the last three capability names from the generated
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

## MMFR v1

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

## MMCR v2-v4

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
12. MX05 live-agent-list panels with bounded static row variants (v12).

The writer retains canonical v2 when neither newer section is needed, uses v3
when occupant panels are present, and uses v4 when building toggles are
present. It uses v12 only when at least one live-agent list is present. A
newer-version header with an empty final section is noncanonical.

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
