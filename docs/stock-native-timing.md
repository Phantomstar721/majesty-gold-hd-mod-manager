# Native timing boundary

An opt-in schema-v3 service, implemented for the public and beta2 executables.
It shares the existing native GPL registration boundary with map/movement
queries. It does not modify CastSpell, PerformAction or CreateEffector.

## Package declaration and API

```json
{
  "type": "stock.native-timing.v1",
  "spell_ids": ["Za01"],
  "effector_ids": ["Ze01"]
}
```

These are existing Description resource IDs, not native addresses or requested
patches. Each declared spell must be exactly one package-owned Action/Standard
Description with `Game/Flags` containing `IsSpell` and an explicit
`TimeoutDuration` from 0 through 2147483647 milliseconds. Each effector must be
exactly one package-owned Unit/Overlay Description. The Manager rejects missing,
wrong-kind, duplicate and cross-package ownership claims, ambiguous names or
duplicate timing fields. Lists may be empty for
clock and read-only base-period queries; each family permits at most 1024 IDs across selected packages.
Generated packages re-prove this evidence before launch.

Do not supply GPL stub definitions. The native functions return GPL integers:

| Call | Result |
| --- | --- |
| `$MM_SimulationTime()` | Current stock simulation DWORD, carried as a signed GPL integer bit pattern. Negative timestamps are valid after the high bit is set. |
| `$MM_SimulationElapsed(integer Started)` | Unsigned elapsed simulation milliseconds since a timestamp from the same game, saturated at 2147483647. Handles DWORD wrap; use this instead of signed GPL subtraction. |
| `$MM_UnitMovementBasePeriod(agent Subject)` | Raw base period in simulation milliseconds of the unit's currently selected stock linear movement attachment. |
| `$MM_ActionBasePeriod(string ActionName)` | Raw `Engine/Rate` **max** period in simulation milliseconds of a named, loaded Action/Standard description. |
| `$MM_EffectorRemaining(agent Subject, string EffectorName)` | Remaining simulation milliseconds, saturated at 2147483647; 0 when absent or the timeout has elapsed; -2 when an existing effect has no active expiring order. |
| `$MM_CommitSpellCooldown(agent Caster, string ActionName)` | 1 after updating an existing learned spell; 0 when the caster has not learned it. |

Resource arguments use the Description's **Name**, as stock GPL does. The loaded
description for effector/cooldown operations must resolve to a declared ID. The effector function is registered
only if an effector is declared; the cooldown function only if a spell is
declared. Both return -1 for invalid/missing handles or names, -3 for unsupported
native layouts/data, and -4 for an undeclared resource. Consumers must treat
negative results as unavailable, not as elapsed/expired time.

### Read-only base periods

Both base-period functions are available with an empty-list timing declaration.
They may read stock or modded loaded descriptions and require no ownership claim
in `spell_ids`. This does **not** grant cooldown-write access to those resources.
They return nonnegative raw milliseconds, `-1` for a missing/deleted subject or
unknown/empty action name, and `-3` for unsupported native description/method
layouts or negative period data. Zero is a valid unconfigured base value;
consumers needing a meaningful reference must reject results <= 0. There is no
invented fallback or class-specific reference table in the Manager.

These reads exclude attribute modifiers, quantum rounding and the stock minimum
interval clamp. They are not the Q16 travel-rate queries, current animation
duration, wall time, a queued order's remaining time, or `Game/TimeoutDuration`
spell cooldown. A movement attachment change or loaded action replacement is
visible at the next query. The action getter takes **only a name**, because stock
stores this base on each action description, not on the recipient unit.

`ATTRIB_MovementRateModifier` and `ATTRIB_ActionRateModifier` add fixed
millisecond deltas before native rounding/clamping. One delta derived from one
reference action cannot provide the same percentage change to every action.
Reference selection, percentage-to-delta calculation, eligibility, stacking and
applying/reversing that delta belong to the mod's existing stock effector
lifecycle. These APIs do not choose Attack_Action/Cast_Action, watch actions,
retime orders, or recompute modifiers on refresh. A package using a fixed
reference should describe the benefit as approximate, not universally exact.

Call commit **once from a successful stock action-completion callback**, after
the consumer's own alive/eligibility checks. It copies the currently loaded
spell's timeout and current clock into its existing learned-spell node. It does
not teach a spell, waive level/availability checks, perform an action, charge
resources, alter effects, or detect success on the consumer's behalf. Calling it
again restarts that native cooldown, just as another stock cast would. An
interrupted/cancelled action must never invoke it. The package retains stock
PerformAction and its completion/cancellation callbacks; this API is not an
alternative action scheduler. Continue using stock IsSpellAvailable to decide
whether to begin an action.

Remaining time is a snapshot, not permission to remove an effect. Zero may mean
its stock cleanup is queued but has not run yet. The native effect order,
CreateEffector's refresh rules, DeleteEffector, and the original end callback
remain authoritative. Requery on the next use; never retain native pointers or
mirror effector ownership in GPL markers. An indefinite effect is not expired.

The simulation clock follows the game's pause and speed and is not wall time.
Store a timestamp using ordinary saved GPL state if it must survive a save;
never reuse timestamps from a different game. The Manager keeps no per-unit
timing ledger. Existing stock order/spell state remains serialized by Majesty.

## Stock lifecycle traced before implementation

Addresses are executable VAs (public / beta2).

- GPL `CastSpell` (`430280 / 4311E0`) resolves the agent using the nonthrowing
  stock resolver (`558B20 / 56EC60`), looks up the named action in the loaded
  action catalog (`7C545C / 7E3FE4`), and finds that action's existing learned
  spell node. VehicleRec owns this list at `+168`, its sentinel at `+17C`, and
  its count at `+180`. Each node has next/previous links, action ID at `+08`,
  last cast time at `+0C`, timeout at `+10`, and an availability byte at `+14`.
- `LearnSpell` creates a node only when absent, initializing its native timing;
  `CastSpell` never creates one. At `430410 / 431370`, casting reads the action's
  Game `+0C` timeout and writes node `+10`, then writes the stock simulation
  clock (`7C5454 / 7E3FDC`) into node `+0C`. Only then does it invoke native
  `PerformAction` (`5BEC30 / 5D3E10`). Consequently cancellation does not undo
  the already-written cooldown. A completion-only consumer must use its stock
  action completion callback, not call CastSpell and attempt to undo it later.
- `IsSpellAvailable` (`430050 / 430FB0`) retains required-level checks and
  compares unsigned `now - last_cast >= timeout`. Completion-time commit must
  copy the two stock writes, without changing availability, teaching a spell,
  starting an action, clearing orders, or accepting a caller-provided duration.
- VehicleRec's native save path (`44C39A / 44D2AA` and following) serializes
  list count, action ID, last cast and timeout; its load path restores those
  values. Destruction frees the same list. No Manager-owned per-unit state is
  necessary. Both builds use the stock VehicleRec layout; other native classes
  must be rejected before accessing the list.
- `CheckEffector` (`5BF6C0 / 5D48A0`) obtains the named unit description and
  resolves the subject anew. Its native query finds a matching effector in the
  subject's existing attachment container. Getter virtual `+140`
  (`5C95D0 / 5DE7B0`) returns that same borrowed object instead of a boolean.
- Native `CreateEffector` (`5BF430 / 5D4610`) owns construction, attachment and
  starting presentation. Add-effector (`5C9660 / 5DE840`) refreshes an existing
  non-projectile effect only when its stock expiry order exists. The refresh
  helper (`60D6C0 / 622A00`) obtains order `(1, 9)` via virtual `+180`
  (`5C9E30 / 5DF010`) and updates order `+08` start time and `+0C` duration.
  A duration query must only borrow these values, never invoke that helper.
- The native expiry predicate (`5FCE20 / 612160`) uses unsigned elapsed time
  against those fields, honoring order flag `+18 & 1` (no expiry). The native
  scheduler invokes completion and removal; `6229D0` in beta2 installs the
  effect order with callback ID `100D`. Its registered callback `6229A0` goes
  through `622850` for normal completion/cleanup. Explicit DeleteEffector also
  routes through this stock order or cleanup path. No custom callback owns it.
- Native order save/load (`6118B0 / 611820` in beta2) serializes/restores duration,
  start time, type, flags and callback data. A query retains no object pointers
  between calls and therefore adds no cancellation or save migration lifecycle.
- Movement base getter (`5BA0F0 / 5CF090`) reads the selected borrowed DMOV at
  unit `+54`, then descriptor Engine `+14`, then period `+0C`. Construction,
  attachment replacement, movement scheduling and cleanup remain as traced in
  [the movement query contract](stock-movement-query.md). The new period read
  validates the same linear engine and stock unit interval method, but does not
  invoke scheduling or attribute evaluation.
- Action/Standard engine construction (`5AFBF0 / 5C4B90`) initializes the period
  fields to zero; the engine vtable is `74754C / 7614AC`. The stock XML loader
  (`5AFED0 / 5C4E70`) loads `Rate` min into Engine `+24` and max into `+28`.
  In beta2, `5C4F92..5C4FA0` passes these exact fields to the native range reader.
  Binary loading (`5AFE20 / 5C4DC0`) restores the same field at `+28`. Catalog
  ownership and engine destruction remain with Majesty; queries borrow them.
- Action base getter (`5B9F80 / 5CEF20`) takes an explicit action description,
  reads Engine `+14 -> +28`, and does not use a unit. Gameplay period getter
  (`447AC0 / 4489D0`) invokes it, adds the unit's `0x32565041` action modifier,
  rounds to simulation quantum and clamps to at least 1. Movement does the same
  with `0x22565041`. The new getters copy only the base reads, leaving native
  action dispatch, completion/cancellation, animation, orders and UI untouched.

Queries and commits execute synchronously on the calling GPL simulation thread.
No selected consumer means no installed interface; a selected but unused
interface has no per-frame or periodic work.
