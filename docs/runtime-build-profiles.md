# Runtime executable profiles

The Majesty Mod Manager native runtime supports two explicit 32-bit Steam
Majesty executables.
It selects the profile from the loaded PE timestamp, then validates every hook
site before modifying the process. An unknown timestamp or mismatched byte
guard stops installation before any hook is written.

| Profile | Version | PE timestamp | Pristine SHA-256 |
|---|---:|---:|---|
| `public-1.5.2.24` | 1.5.2.24 | `0x5897B72F` | `AA9BE61DC095773CCC5C08B9E5729A30EE856258249371C5189CE52FB675DB00` |
| `beta2-1.5.2.28` | 1.5.2.28 | `0x5A8A11D5` | `99848B5DB16CC3EA540D7E909CB24966AD9F3CD15D302CDE47AAB3BA81E3167E` |

The optional Mod Manager activity-text hook has its own conditional profile
guard. Its stock lifecycle, resolver RVAs, exact bytes, registry protocol, and
fixture test are documented in
[private-intent-text-runtime.md](private-intent-text-runtime.md). No registry
means this resolver is neither validated nor modified.

Every optional runtime group is selected by the validated MMCP v1 manifest,
not by a package ID or by the mere presence of a data file. The manager derives
the canonical `stock.name-generator.v1`,
`stock.ap78-enchantment-row.v1`, and `stock.controller-recipes.v1` selections
from its generated MMFR/MMCR contents. The selected public/beta2 byte guards are
still checked before the corresponding generic group writes a hook. See
[runtime-capability-manifest.md](runtime-capability-manifest.md) for the wire
formats, failure behavior, exact capability-to-hook map, and bounded registry
ownership rules.

Legacy Alchemist and expanded-Haunt capability strings are accepted only while
reading schema-v1/v2 package definitions. The manager translates them into
generic feature records before composition; generated MMCP does not select a
package-specific native branch.

Executable patch utilities may change the installed file's hash while retaining
the stock timestamp. This is allowed only when every runtime code fingerprint
still matches its selected pristine profile.

## Stock-equivalent address map

These are independently matched stock routines and state, not a calculated
offset conversion.

| Stock lifecycle site | Public RVA | beta2 RVA |
|---|---:|---:|
| Dialog controller result | `0x0002594A` | `0x0002691A` |
| Dialog creation | `0x00025910` | `0x000268E0` |
| Dialog factory | `0x0010AC00` | `0x0011B150` |
| Unknown-dialog fallback | `0x0010C03F` | `0x0011C58F` |
| Shared AP07/AP10 guild allocation | `0x0010BE9C` | `0x0011C3EC` |
| UI manager | `0x00025D00` | `0x00026CD0` |
| Remove dialog | `0x00025880` | `0x00026850` |
| Panel context | `0x00067540` | `0x00068780` |
| Command metadata | `0x001C2060` | `0x001D7240` |
| Player agent | `0x00029580` | `0x0002B150` |
| Packed attribute read | `0x001B9FD0` | `0x001CEF70` |
| Building command submission | `0x000C4CF0` | `0x000C5730` |
| MX22 open/close command handler | `0x000B9540` | `0x000B9F80` |
| MX22 open/close presenter | `0x000B95A0` | `0x000B9FE0` |
| Rage command dispatch | `0x000C4FE1` | `0x000C5A21` |
| Rage private GPL branch | `0x000B1269` | `0x000B1B59` |
| Rage GPL construction continuation | `0x000B12C9` | `0x000B1BB9` |
| Simulation clock | `0x003C5454` | `0x003E3FDC` |
| State-3 update call | `0x0002526D` | `0x0002623D` |
| Game update | `0x00026650` | `0x000278A0` |
| Stream control lookup | `0x002524C0` | `0x00267920` |
| Research rows refresh | `0x000A8AE0` | `0x000A93D0` |
| Single research row refresh | `0x000A8870` | `0x000A9160` |
| Research eligibility | `0x000A8B40` | `0x000A9430` |
| Research command submission | `0x000C2C60` | `0x000C36A0` |
| Research completion | `0x000DFE20` | `0x000E0430` |
| Research descriptor resolver | `0x000A86E0` | `0x000A8FD0` |
| Spell descriptor resolver | `0x000AE3B0` | `0x000AECA0` |
| Single spell row refresh | `0x000AE4D0` | `0x000AEDC0` |
| Sovereign target manager | `0x0005E5D0` | `0x0005F600` |
| Sovereign cursor transition | `0x0005EE25` | `0x0005FE55` |
| Current player | `0x00024A00` | `0x000259D0` |
| Research completion name push | `0x000DFFC7` | `0x000E05D7` |
| AP78 Enchantments switch | `0x000A39A0` | `0x000A4280` |
| AP78 XR01 row string call | `0x000A3A08` | `0x000A42E8` |
| Stock string assignment | `0x00228350` | `0x0023AAF0` |
| Name-registry completion | `0x0011090E` | `0x00120E5E` |
| Stock operator new | `0x002D8F7E` | `0x002EE542` |
| Name-generator factory | `0x0010C070` | `0x0011C5C0` |
| Name-generator constructor | `0x0010AB70` | `0x0011B0C0` |
| Name-registry map insertion | `0x0010FB70` | `0x001200C0` |

The normalized instruction windows around each pair match the same stock
lifecycle. The simulation-clock mapping is additionally confirmed in each
build's state-3 update: the clock is read, advanced from the same simulation
delta, overflow-reset, published, and passed into the same downstream update
calls in identical order.

Steam replaces the executable when switching branches, which removes the
on-disk custom-building fallback even though the CAM and DLL remain installed.
Authors do not reserve a `CG` dialog ID: schema-v3 composition infers each
package-local dialog and allocates a collision-free internal ID. The current
internal allocation uses the manager's `CG` namespace. The injected runtime
therefore verifies the selected build's exact stock unknown-dialog epilogue and
reapplies the already-proven `CG`-prefix branch in memory. It preserves the
manager-resolved FourCC and constructor arguments, then enters that build's
unchanged AP07/AP10 allocation block. An executable that already contains the
exact file-based patch is accepted unchanged; any other bytes fail closed
before dependent hooks are installed.

## AP78 private Enchantments rows

The hero Enchantments list is AP78's hard-coded overlay-FourCC switch, not a
generic `Menu=11` presenter. The manager writes every proved package-owned
overlay/text pair to MMFR and derives one shared
`stock.ap78-enchantment-row.v1` hook selection. The runtime fingerprints and
patches only the first comparison in AP78's stock switch and XR01's existing
string-assignment call. When the current overlay matches any validated MMFR
record, it is synchronously aliased to XR01 for one row build and that record's
text is substituted immediately before the unchanged stock string assignment.
All other overlays execute the original comparison unchanged.

The string-assignment call consumes Majesty's 12-byte narrow-string object,
not a raw `char*`; the runtime builds immutable views over the validated
Windows-1252 strings with the stock data/capacity/length layout. A raw C string
violates this call contract and can crash AP78.

The hook adds no list, timer, watcher, effect ownership, or replacement
controller. AP78 continues to own active-effect iteration, formatting, row
append, refresh, and teardown. Both executable profiles fingerprint the switch,
call site, and stock assignment function before either AP78 site is modified.
AP78's unchanged row builder paints every supported enchantment from the stock
`IX93` interface atlas rather than the overlay Description's `ImageIDBase`.
When any private AP78 row is present, composition therefore carries the exact
effective-stock `IX93` IMAG record and its referenced TILEs; a selected package
cannot replace that fixed stock layout.
The legacy Alchemist alias is translated by the manager into the `ALo1`,
`ALo2`, and `ALo3` MMFR examples; those IDs and texts are not hard-coded as a
separate runtime path.

## Manager-generated stock controller recipes

Controller-backed package features are composed into the immutable MMCR file
at `DataMX/majesty_mod_manager_controllers.bin`, whose absolute path is supplied
through `MAJESTY_MOD_MANAGER_CONTROLLERS`. The manager resolves all package-
local parent/child dialogs and owner-qualifies logical panel keys before writing
MMCR. The native runtime never reads package JSON and never chooses behavior by
mod UUID, display name, or authored dialog prefix.

One generic `stock.controller-recipes.v1` MMCP selection installs the already-
traced stock hook set for every validated MMCR alternative. The supported
records reuse AP10/AP69 secondary-panel ownership, AP22 packed-resource
presentation, AP99 research, AP17 upgrade gating, AP24 Rage command/timed
action, and AP69 sovereign targeting. Resource keys, recipe/action keys,
controls, templates, prices, requirements, FourCCs, and GPL callback symbols
come from the validated registry rather than an Alchemist-specific branch.

These records do not create a parallel controller engine. They route one active
alternative through the corresponding serialized stock state: one AP10/AP69
parent-child panel chain, one AP99 research owner, one pending Rage handoff, one
active timed-Rage UI owner, and one sovereign-target session. A registry can
hold multiple packages and alternatives, but simultaneous ownership beyond
those stock boundaries is not supported or claimed. Exact controller
destruction, dialog replacement, command completion/cancellation, GPL effector
cleanup, and quest/resource teardown remain authoritative.

The following reagent-focused trace records why the first compatibility recipe
is safe. It documents the legacy Alchemist values now translated by the manager
into generic MMCR records; it is an example, not the identity or limit of the
runtime mechanism.

## Legacy Alchemist recipe: private reagent spell targeting

Alchemical Tempest clones Lunord Wind Storm's `Sp29` descriptor and complete
global ground-target lifecycle. Philosopher's Stone clones Fervus Vines'
`Sp23` descriptor and complete global enemy-target lifecycle. Neither target
mode calls the Wizard Guild range validator or installs Lightning Storm's
range-overlay callbacks.

Majesty's target validator recognizes a fixed stock mode list, so both actions
retain their stock temple modes through target acquisition and cancellation.
The scoped cursor-transition clone reproduces the original 23-byte transition
in order and changes only cursor ordinal 29 or 24 to private ordinal 38 or 39
while the matching Laboratory action is pending. The stock cursor presenter
still performs the actual render and refresh. At command submission, the
pending stock mode is changed to `AlT1` or `AlS1`, the selected Laboratory is
stored as owner, and the temple gold cost becomes zero. The existing private
executor then reuses Lightning Storm's spell-unit construction only after
targeting has finished, so it cannot impose Wizard range or cursor behavior.

Stock temple spells submit the current target packet even when the player does
not have enough gold for another cast. The sovereign executor compares the
player's gold with the packet cost, enters its native insufficient-gold branch,
presents the stock failure feedback, and returns before command construction.
It does not cancel or replace the active target mode. The private Reagent check
clones that lifecycle exactly: when fewer than ten Reagents remain, it preserves
the stock Wind Storm or Vines target packet and supplies an unreachable positive
cost to the stock affordability branch. The pending private cursor state also
remains intact. When Reagents are available, submission converts the mode and
owner to the private action exactly as before. No synthetic target mode, custom
cleanup, watcher, or cancellation path is used.

The Brewing Reagents display follows stock AP22 Hero Items rather than trying
to rewrite a nested Rage label. AP22 renders each item quantity in a separate
top-level numeric control. CGBR clones the Healing Potion quantity control,
changing only its private visible ID, embedded numeric binding ID, rectangle,
string bindings, art FourCC, and value source. AP22's helper at Beta2
`0x004A3480..0x004A34D5` calculates the item quantity and dispatches it through
panel virtual `+0x5C` as `(binding ID, integer value, 0)`. The visible field ID
is not the update target. The runtime uses that exact numeric dispatch for the
private Reagent binding. AP78's dynamic enchantment-list owners `0x221A` and
`0x221B` are unrelated and are deliberately not serialized into CGBR.

## Private hero name generators

Majesty constructs the complete `NM01` through `NM17` registry before setting
its ready flag. The manager emits every proved private generator and its four
ordered `HN` tables to MMFR, then derives the generic
`stock.name-generator.v1` MMCP selection. At the exact stock completion
boundary the runtime iterates those validated records using the stock allocator,
factory, generator constructor, map insertion, and wrapper vtable. Stock
selection, fragment concatenation, ownership, and destruction remain unchanged.

The legacy Alchemist (`NM18`/`HN69`-`HN72`) and expanded-Haunt
(`NM19`/`HN73`-`HN76`) declarations are manager-side compatibility examples,
not fixed runtime branches. See
[private-name-generator.md](private-name-generator.md) for the complete generic
lifecycle trace and byte guards.

## Manager-owned controller teardown

Majesty destroys streamed-panel controllers through vtable slot zero, its
MSVC scalar-deleting destructor. On beta2, AP69 constructs with vtable
`0x00756DD8`; slot zero is `0x004AB8B0`. That function calls the complete base
controller destructor at `0x004AB430`, preserves the caller's delete flag, and
only then invokes stock operator delete when bit zero requests it. Beta2 AP10
constructs with vtable `0x00755E5C`; its slot zero at `0x00496770` performs its
complete derived/base teardown at `0x004955C0` and applies the same stock delete
flag afterward.

Private controller clones must therefore retain slot zero as their lifetime
boundary. `ControllerLifecycleRegistry` captures the live stock slot directly
from each constructed controller instead of adding another build-specific
address. It installs one shared dispatcher in the manager-owned vtable,
invalidates state only when the destroyed object still matches that owner's
exact live controller pointer, then calls the captured stock destructor with
its original flags. Parent and secondary controller types register
independently, and a delayed destructor for an older instance cannot clear a
replacement.

The active MMCR record, rather than a package identity, supplies the parent and
child routing ownership. Parent and child controllers have independent native
lifetimes. A parent destructor must not clear a surviving child's routing;
the child resolves its own building through Majesty's native controller handle.
Destructor callbacks clear only the exact controller state still owned by that
record; simulation-owned research and active effects remain under Majesty's
existing command and GPL lifecycles.
Any future stock-controller recipe must use this same registration boundary
rather than adding quest-name resets, polling, or feature-specific unload hooks.

Both stacked and single-panel layouts are supported without resolution-specific
branches or package metadata. See [panel lifecycle](panel-lifecycle.md) for the
stock placement, command-result, Back, and stock-list navigation contracts.

## Required validation

Run both tests whenever runtime code changes:

```powershell
.\tests\Test-RuntimeBuild.ps1
.\tests\Test-DualRuntimeProfiles.ps1 `
  -PublicExe <pristine-1.5.2.24-exe> `
  -Beta2Exe <pristine-1.5.2.28-exe>
```

`Test-DualRuntimeProfiles.ps1` verifies the known hashes, versions, PE
timestamps, hook bytes, and entry fingerprints for every mapped stock routine.
It can also validate an installed, utility-patched beta2 executable with
`-PatchedBeta2Exe` without requiring that modified file to retain a pristine
hash.

The integrated Freestyle CAM lifecycle has its own fixture-backed site test:

```powershell
.\tests\Test-FreestyleCamRuntimeProfiles.ps1 `
  -PublicExe <public-1.5.2.24-exe> `
  -Beta2Exe <beta2-1.5.2.28-exe>
```

That test validates the Random/shared use, named-construction use, frame/grid
uses, wrapper assignment/getter/teardown sites, and resource-manager singleton
load independently for both profiles. The traced lifecycle and live matrix are
documented in [freestyle-cam-runtime.md](freestyle-cam-runtime.md).
