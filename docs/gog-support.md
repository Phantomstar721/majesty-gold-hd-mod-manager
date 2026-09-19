# GOG compatibility

The Manager supports the audited GOG 1.5.2.28 executable alongside Steam.
The GOG trial's installation switching, merged-package launch and selected
Standard Workshop mods have received user-reported gameplay acceptance.

## Executable identity and current availability

The supported target is GOG Gold HD 1.5.2.28, timestamp `0x5BBB8DB8`,
SHA-256 `65C6DD32C3D873C2E320BDAA2DE1B00488AF85B44573FD0FD82F79A2FFD37792`.
It is distinct from Steam beta2 despite the identical version string. The old
1.5.1.2 executable is not supported. Python detection and native selection
validate the four stock PE sections; helper sections may be appended.

GOG support includes:

- Remember Active Mods and Generic Visitor Lists, including guarded restore.
- Core launch and the existing custom-building factory fallback.
- Selected Standard mods from already-downloaded Workshop packages, registered
  through GOG's stock manifest loader during Manager launch. See
  [the discovery and ownership audit](gog-standard-mods.md).
- The existing Freestyle IMAG acquisition, assignment, and release repair.
- Private name generators, activity text, and AP78 enchantment rows.
- The existing GPL map, movement-rate, and native timing interfaces.
- Stock controller recipes, including private recruitment, occupant and live-agent
  lists, reward panels, secondary panels, and their existing research actions.

Experimental equipment and saved kingdom-research integration are not part of
this change or the current release. Their GOG lifecycles remain unaudited.
Manager preflight identifies unsupported capabilities, and native preflight
rejects them before installing any hook.
The Steam public and beta2 profiles retain their prior capabilities. Optional
Steam executable utilities are marked unavailable on GOG without spawning their
installers. The shared intro-video preference remains available.

GOG has no Steam Workshop subscription/download or quest-discovery path. This
integration registers selected, already-downloaded Standard mod manifests at
stock startup. Quest packages must be in the local Quests folder. Local and
Steam/GOG installations share the normal Documents/My Games/MajestyHD folders.

## Audited stock lifecycles

`gog-runtime-audit.json` records complete compared function bodies, their exact
hashes, every relocated operand, and explicit instruction differences. Address
candidates alone were not promoted to hooks. The Steam comparison fixture was
an owned copy of the installed beta2 executable with canonical utility restorers
applied; it is **not** claimed to have the pristine Steam file hash. Audited
reference ranges are pinned separately. GOG's full pristine hash was verified.

The core factory maps beta2 `0x11B150` to GOG `0x10D060`. Its unknown-ID
epilogue is `0x10E49F`; the unchanged AP07/AP10 allocation block is `0x10E2FC`.
It allocates the same 0x34-byte controller and enters constructor `0x96BA0`,
which installs vtable `0x354F94`. Constructor arguments, FourCC ownership,
stock setup/dispatch, and deleting-destructor lifetime stay native. Only the
existing reserved-prefix fallback is applied. The original epilogue or the
exact existing fallback is required. A bounded full-body guard also checks the
factory (normalizing only that epilogue) and constructor before installation.

Remember Active Mods uses startup/menu call `0x772C0 -> 0x139240` and Mods OK
call `0x138BE9 -> 0x1393A0`. The helper preserves both displaced stock calls.
The stock installed-list sentinel is VA `0x7E0C34`; the Active-list owner and
sentinel are `0x7E0C3C` and `0x7E0C50`, with dirty flag `0x7E0C00`. The existing
insert/commit pair is `0x136190` / `0x136240`, resolved from the actual stock
restore-handler calls rather than a duplicate-template byte match. The five
CRT imports are `fprintf=0x74D414`, `fopen=0x74D458`, `fread=0x74D45C`,
`fclose=0x74D46C`, and `sscanf=0x74D47C` (VAs). The existing private scratch
arena and parsing layout are retained. Stock owns list construction, ordering,
duplicate prevention, apply/refresh, and node deletion. Cancel does not reach
the save call. Files close synchronously, and wrappers restore registers before
return. See the preserved helper lifecycle in `helpers/README.md`.

Generic Visitor Lists uses the complete stock painter at `0x98F40`. The gate,
icon dispatch, and threat call are `0x991B5`, `0x98FF8`, and `0x992B1`. The
image resolver, classifier, and attribute getter are `0xBC0E0`, `0x10AE70`,
and `0x1CE2C0`. Hero and monster continuations are `0x99001` / `0x9905D`.
List construction, row insertion, selection, draw ordering, and descriptor
destruction remain stock. GOG's stock stream-message dispatch is at vtable
`+0x74`, compared with Steam's `+0x68`; that instruction is left unchanged.
The existing IX92/IX94 resource requirements and display-only threat bands
remain exactly those of the helper. No new UI or gameplay policy is introduced.

Freestyle uses the same complete IMAG bodies and seven-argument resource-manager
acquisition described in `freestyle-cam-runtime.md`. The singleton load is
`0x23B3B1`, its slot is `0x3E7638`, and the audited acquisition/assignment/
teardown bodies are listed in the JSON. AddRef, Release, store ordering, nested
acquisition, stock frame/grid use, and menu reconstruction remain unchanged.
The GOG named-retention diagnostic is deliberately unavailable. Production
hooks retain their existing byte guards and rollback behavior, plus bounded
GOG body fingerprints before installation.

Private names register at `0x112D6E`, immediately before the existing ready
assignment. The stock map remains at registry `+4`, wrappers remain eight bytes,
and generator construction retains its four ordered HN IDs plus resource owner.
GOG's bootstrap obtains that owner from `+0x160` instead of `+0x158`; stock
already loads EBP before the hook captures it. The hook therefore needs no new
field access. Factory `0x10E4D0`, constructor `0x10CFD0`, insertion `0x111FD0`,
and imported operator new `0x2EDA2C` were resolved from the actual call chain.
The wrapper vtable is copied from the live stock NM17 entry; stock teardown
continues to delete the generator and wrapper.
The complete deleting wrapper at `0x10E700` is included in the body audit.

Activity text uses resolver `0x10ADE0`, provider `0x174330`, and stock 12-byte
string assignment `0x23CC40`. Unknown IDs retain the original resolver path.
AP78's entire row routine has three stock stream-slot changes (`+0x68` to
`+0x74`); its unchanged native code handles them. The private switch at
`0xA4830` and string call at `0xA4898` retain the existing synchronous alias and
string-view contract. Effect iteration, row ownership, refresh, cancellation,
and cleanup remain with AP78 and stock effects. Neither feature adds a timer,
watcher, polling loop, or controller.

The GPL registration boundary is `0x1AD1E7 -> 0x1D4F40`. It retains the complete
stock registration body first, then calls the existing Manager registration
adapter. The 12-byte string constructor/destructor are `0x23C370` / `0x23C520`,
the engine provider is `0x174330`, function insertion is `0x180FF0`, and argument
access is `0x2EC20`. The destructor was resolved from the actual registration
call because two independently owned template bodies otherwise look identical.
Registration flags, argument boxing, synchronous return, and temporary string
destruction remain unchanged.

Map extents, hidden-coordinate lookup, PathCost, and rectangle traversal are
`0x1D0C80`, `0x1D2F20`, `0x1D2CD0`, and `0x1D7450`; the world slot is
`0x3E426C`. Complete body comparison preserves the stock map/tile field layout
and rectangle ordering. The existing PathCost optional-unit adapter changes
only the call at wrapper `+0x81`; native explicit-unit validation, average-unit
branch, pathfinding, and evaluator cleanup remain stock.

Movement's fresh live-unit resolver is `0x16DF60`, description lookup is
`0x1C2350`, and the loaded description and quantum owners are `0x3E4124` /
`0x3E40F0`. The base/effective interval bodies (`0x1CE3E0` / `0x48810`), attachment
selection, step (`0x1E23B0`), and DMOV constructor/derived data (`0x2175E0` /
`0x217AF0`) retain their complete stock instruction shapes. Constructor vtable
`0x3631D0` and the derived-data slot are checked explicitly. No unit pointer is
retained across calls.

Timing preserves CastSpell's two writes at `0x310B0`, IsSpellAvailable at
`0x30E80`, and clock `0x3E4274`. VehicleRec's destructor resolves its table to
`0x353194`; its learned-spell list at `+0x168` and save/load fields are unchanged.
The effector getter/order accessor are `0x1DDB00` / `0x1DE360`. Their actual vtable
slots, refresh helper (`0x221D50`), expiry (`0x2114B0`), order installation
(`0x221D20`), callback (`0x221CF0`), cleanup (`0x221BA0`), and serialization are
included in the audit. Action construction/loading and base/effective period
bodies preserve the existing `Rate.max` contract. GOG uses these same stock
owners and callbacks; the Manager keeps no additional timing state.

## Installation switching and packaging

Discovery checks GOG product `1423481910` under the normal 32/64-bit registry
views and common GOG paths. A saved executable choice still takes precedence.
The game, QOL services, prepared-package cache, and plan are rebound together.
When multiple supported installations are detected, a dropdown shows the store
and executable version, retains the selected installation, and rescans on a
change. Browse remains available for other locations. Switching is disabled
while a scan, preparation, or launch is running. Paths distinguish duplicate
copies of the same build; a rejected choice restores the previous selection.
Selection validation and the following scan run on the existing background
worker, with immediate progress and disabled actions while the switch runs.
The switch defers package planning to the scan instead of inventorying the old
catalog and immediately discarding that work for a second plan.
Installation discovery is also completed there before updating the dropdown.
If the new installation cannot be scanned, actions from the old snapshot remain
disabled until a successful scan.
Each successful installation switch repeats the required-helper onboarding
check after the scan. Missing requirements open Quality of Life, clear any
search filter, and appear at the top of the list. Ordinary rescans do not repeat
the prompt. Installed requirements follow optional helpers in the list.
Required helpers retain their individual Remove buttons. Removal uses their
normal restore scripts and immediately refreshes the required-helper state;
Prepare and Launch remain unavailable until the player reinstalls them. The
Remove Optional bulk action continues to remove only optional helpers.
Helper inspection caches retain separate results for up to eight installation
paths. Returning to an unchanged installation, including after restarting the
Manager, refreshes preferences directly and starts no PowerShell dry-runs.
Executable and relevant UI-data metadata, canonical script/dependency contents,
and status-interpretation settings still invalidate that installation's result.
The initial inspection and checks after changed evidence still run the canonical
read-only scripts; a failed inspection is retried on the next scan.
PE discovery reads only the header and file length rather than the whole EXE.
Plan fingerprints include the selected installation path and executable profile;
metadata invalidation includes the EXE. Byte-identical CAM inputs alone cannot
make a build prepared for the other installation appear current.
The full source recheck uses the same installation identity and refreshes cached
package hashes. Applying a helper without changing the executable profile or
composition inputs does not falsely invalidate the plan; changed package files,
stock inputs, or installation identity still do.

Both stores share redirected `Documents/My Games/MajestyHD`, including Mods,
Quests, and saves, as well as the existing remembered Active list. There is no
new per-store save directory. The user remains responsible for Rescan/Prepare.

Required helper source is owned under `helpers/`; packaging uses these copies
for both launch helpers and the complete QOL-suite view. Canonical sibling
repositories remain references. The standalone output is:

`dist/Majesty Mod Manager/Majesty Mod Manager.exe`

## Verification and acceptance

`scripts/audit_gog_runtime.py --gog <pristine-GOG-exe> --beta2 <reference-exe>`
verifies every pinned audit range without modifying either source.
It also verifies every production bounded body fingerprint against those ranges.
`tests/Test-GogHelpers.ps1 -Executable <exe-paths>` tests both install orders,
idempotency, non-last-section restore, and exact byte round trips on owned
copies. Its preference-directory override keeps test preference output local.
The Python GOG tests cover identity, safe availability, installation switching,
helper ownership, and shared redirected Documents. Native build and existing
runtime tests cover compilation and retained contracts.
`Test-DualRuntimeProfiles.ps1 -AllowModifiedReferences` is used only for the
owned, non-pristine Steam fixtures: it retains every site guard and identity
check but deliberately omits the whole-file pristine-hash assertion. The default
mode still requires pristine hashes.

Automated checks are static or use isolated files. The user has confirmed GOG
installation selection, improved switching responsiveness, merged-package
launch and selected Standard mods working in-game. This does not establish
exhaustive acceptance for every feature. Regression coverage should still
include remembered Active-list restoration across restarts, visitor rendering,
repeated Random/named Freestyle games, private names/text/enchantment rows,
panel switching, recruitment, research completion, list selection and
sovereign-target cancel/commit with compatible content.

## Controller recipe stock lifecycle

`gog-controller-audit.json` pins factory-resolved constructors, complete vtables,
and every method for the 24 parent classes. `gog-recipe-audit.json` adds AP69's
complete secondary class, the stream adapter, MX05 child/list lifecycle,
research descriptors and completion, reward mode, and sovereign targeting.
The native profile uses explicit GOG addresses and bounded body guards. It adds
no per-frame discovery or additional timers.

Creation at `0x25B70` reaches the native factory `0x10D060`; setup and input keep
the stock argument order, controller `+0x24` stream, `+0x28` context and class
ownership. AP69's `0xAD5B0` constructor selects vtable `0x355F10`. Back hides the
child using stream virtual `+0x14`, opens its own parent, and returns the native
removal result. Native deleting destructors and the existing exact-instance
cleanup registry retain ownership during parent/child replacement.

GOG's controller-facing stream moves text `+0x50 -> +0x54`, caption
`+0x54 -> +0x58`, selection `+0x58 -> +0x5C`, integer `+0x5C -> +0x60`, and
message `+0x68 -> +0x74`. Hide, visibility, linked controls and list insertion
retain their slots. Only the three runtime adapters needing changed slots use
the new profile fields. Literal private recruitment clones come from GOG's own
five stock functions and seven helpers, retaining their callbacks and shared
building queue. Stock costs, progress, completion, and cleanup are unchanged.

Research uses its native descriptor map, queued command and `0x2009` completion
dispatch. Its registry owns private descriptor allocations and frees/rebuilds
them at quest teardown/loading. The completion bridge preserves native state
writes, presentation and the post-update refresh. GOG's state-3 call at
`0x254CD` invokes its entire unchanged update `0x26BF0`: advance the simulation
clock, dispatch both world queues, run state/world updates, then refresh player
UI. The manager resumes its existing private refresh at that return boundary.
The complete GOG update is audited independently because its Steam networking
and diagnostic branches differ. Sovereign targeting retains native cursor,
cancel, commit, executor and spell construction order; its executor's SEH
literal is GOG-specific.

The required visitor helper overlaps MX05's stock renderer. Runtime validation
accepts either all original sites or the exact `.mgvl` section, complete helper
payload, and all three matching patches. Only after that check are those bytes
normalized to stock for the enclosing body fingerprint. Other renderer changes,
partial installations and altered helper payloads still fail.

MX05's shared control handler (`0x99B50`, 616 bytes) is covered by the complete
recipe-body audit. Its row-focus branch at `0x99B89` uses the GOG stream-message
slot `+0x74`; the narrow handoff guard uses that profiled slot rather than Steam's
`+0x68`. The `0x1388` selection query, native focus dispatch, `0x138B` action
handoff, selected-agent write and subsequent panel open/refresh retain the
documented stock ordering and ownership. No handler bytes or lifecycle change.

`Test-GogRuntimeProfiles.ps1 -Executable <fixture-paths>` maps fixture bytes as
non-executable data and exercises the production site checks, full body guards,
all parent class guards, recruitment metadata and mutation rejection. All eight
combinations of list handoff policies exercise the conditional focus guards;
Steam-slot substitution and changed jump-table targets are rejected. Optional
`-RegistryRoot <directory>` reads copied MMCP/MMCR/MMFR binaries and checks the
complete selected launch profile with its actual records. It does
not load game code or prepare Manager content. Reference copies restored by the
owned helper scripts reproduce the pinned pristine GOG SHA-256.
