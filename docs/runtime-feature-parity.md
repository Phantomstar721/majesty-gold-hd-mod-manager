# Shared native feature parity

Profiles cover default Steam 1.5.2.24 (`5897B72F`), Steam beta2 1.5.2.28
(`5A8A11D5`), and GOG 1.5.2.28 (`5BBB8DB8`). Unknown identities and modified
required stock boundaries fail closed. All three profiles are required for new
shared features; a version-limited exception requires user approval.

## Equipment, information rows, movement and research

The 2026-09-25 port replaces the former beta2-only gates. The fixed addresses
and body hashes are in `runtime/FeatureParityProfiles.h`. Only selected features
validate/install adapters. There is no runtime signature scan, additional timer,
or per-unit cache. The movement hot path caches its engine identity at install.

Existing lifecycle audits remain the references:
[equipment](stock-custom-equipment-audit.md),
[information rows](stock-ap78-info-rows.md),
[movement](stock-overlay-movement-scale.md), and
[research](stock-kingdom-research-audit.md). Their beta2 VAs are reference
annotations, not cross-build addresses. Key **RVAs** are:

| Stock boundary | Default Steam | Steam beta2 | GOG |
| --- | --- | --- | --- |
| Equipment enum initialization | `20E80` | `21E40` | `210D0` |
| Equipment presenter constructor | `101720` | `1038D0` | `104060` |
| Learned-row refresh | `A3320` | `A3C00` | `A41B0` |
| Attached-effect refresh | `A3830` | `A4110` | `A46C0` |
| Selected live hero resolver | `67540` | `68780` | `686A0` |
| Linear movement execution | `1CDF40` | `1E3120` | `1E2470` |
| Attached-effector query | `1C95D0` | `1DE7B0` | `1DDB00` |
| Queued research executor | `DFCE0` | `E02F0` | `E0A30` |
| Research completion | `DFE20` | `E0430` | `E0B70` |
| Building readiness setter | `48A40` | `49950` | `49870` |
| Building collection lookup | `1A4080` | `1B9030` | `1B8380` |

### Equipment

The complete enum initializer, presenter constructor and destructor match
instruction structure after resolving address operands. Enum maps, strings,
name/icon insertion and resource acquisition are resolved from stock calls,
not inferred from a global offset. Presenter maps retain offsets 0/20/40/60;
the native destructor releases acquired name references. Only two construction
calls are wrapped. Shopping, ranks, combat, cloning, saved attribute maps and
native cleanup are unchanged.

### Information rows

Learned/effect refresh bodies match except for GOG's final stock virtual call
at refresh+49C/+89F: its slot is +74 rather than +68. That instruction is left
untouched. Hook offsets, register ownership, native 12-byte strings, row-message
+9C dispatch and 0x6C-byte image construction remain the same. Stock copies and
frees labels, tooltips and images; no borrowed row survives refresh. Call-site
verification separately identifies default Steam's selected-hero resolver.

### Movement

Complete step, execution, vector and effector-iteration bodies match across
builds. RTTI identifies `MovementDesc_Linear_Engine` vtables at `34A240`,
`364310`, `3631D0` (default/beta2/GOG); their four entries are pinned as data.
The six-byte hook at execute+B2 reads `[EBX]`, tests EAX and branches to +12A;
continuation is +B8. EBP owns the live unit, ESP+2C is the consumed argument
slot. One local step is scaled, not the cached order. Stock retains arrival,
pathfinding, clipping, callbacks, retirement and attached-overlay lifetime.
Bonuses remain additive; no matching overlay leaves stock values unchanged.

### Research and shared boundaries

Queued execution, completion, saved-attribute setter and order lookup match
across builds. The order virtual remains +180; original executor/readiness/owner
slots are independently checked. Existing per-build descriptor and queued-command
adapters retain pricing, payment, callbacks, cancellation, UI refresh and native
order destruction. Saved GPL state owns kingdom eligibility and completion.

Optional visual reconciliation uses the state-2/world-ready hook from the
[exploration audit](stock-exploration-attribution-audit.md). Default Steam's
join uses different scratch registers but finalizes the same world containers
before requesting state3. The complete stock initializer runs first. Building
collection lookup and sentinel/node layout match. Readiness and owner wrappers
retain stock ordering; exploration accepts the shared building-owner wrapper
on all supported builds. No additional scheduler or saved native pointer exists.

## Verification and remaining acceptance

Read-only checks cover actual executables: body hashes, globals, calls, virtual
slots and displaced instructions. `tests/test_feature_parity_profiles.py` uses
`MAJESTY_PUBLIC_EXE`, `MAJESTY_BETA2_EXE`, `MAJESTY_GOG_EXE` without launching or
modifying them. Existing x86 row, research-visual and movement fixtures exercise
the adapters (`Build-Runtime.ps1 -FeatureTests -ExplorationTests`). Capability
regressions check all derived shared features against supported identities and
reject unknown/malformed PE layouts.

Static verification is **not** native gameplay/save-file certification. Default
Steam and GOG still need in-game acceptance of equipment/panel display,
hover/refresh, overlapping speed effects and expiry, research purchase and
cancellation, upgrade/transfer, save/load, and return to menu. Use disposable
quests and user-prepared packages. This port did not rewrite a package or save.
