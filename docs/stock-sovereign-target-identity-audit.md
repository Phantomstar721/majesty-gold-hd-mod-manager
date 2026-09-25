# Sovereign action target and source identity

Read-only Steam beta2 1.5.2.28 trace, 2026-09-24. This records a confirmed
Manager defect and the boundary requiring a separately versioned extension;
the opt-in extension below is implemented in the test build, not yet playtested.

## Current Manager defect

`SubmitPrivateSovereignCommand(mode, player, x, y, target, cost)` receives the
stock clicked target. For an affordable private action it assigns the selected
building ID to `target`, switches to the private mode, and sets cost to zero.
Consequently the private spell's second birthscript argument is the building,
not the clicked creature. A consumer cannot recover the exact creature by
searching nearby units. Keeping only the creature instead would lose the exact
building that owns the private resource balance.

## Stock queue and execution

- Submit `0x4DA580` constructs a stock sovereign command through `0x4DA440` and
  queues it through `0x4D81F0` / `0x5A82B0`.
- Constructor stores seven words at `+8..+0x20` (mode, command context,
  player, X, Y, target, cost). Serialization `0x4DA500` copies those seven
  words to its 28-byte buffer. There is no spare second unit reference.
- Executor `0x4DA630` resolves the target at `0x4DA695..0x4DA6A3`, chooses the
  spell unit at `0x4DA6B3`, and checks player gold against packet cost at
  `0x4DA6CD`. Manager substitutes only the private unit selection and the
  executor mode today.
- The spell-unit branch `0x4DB2C5` constructs at the packet coordinates with
  the player ID. It runs stock initialization and invokes the birthscript at
  `0x4DB39A`, passing the new spell unit and the resolved packet target.
- Invoker `0x5DAD00` adds exactly those two agent arguments to the GPL evaluator
  (`0x5DAD5C..0x5DAD73`) and executes it (`0x5DAD7C`).

## Closest existing GPL mechanism

`CreateSpellUnit(Source, Name, Target)` registration `0x435C1A..0x435C49`
points to `0x431980`. It reads Source and Target separately, but retains only
Source's player (`[Source+0x80]` at `0x431A7D`) for creation. At `0x431AE8` it
calls the same two-agent birthscript invoker with the new spell unit and Target.
It does not pass Source as a third argument or save a source-building relation.
Simply switching to this GPL function therefore does not solve the ownership
requirement.

## Approved opt-in extension

A generic opt-in recipe must transport both exact IDs through the queued command
and deliver spell unit, source building, and clicked target to its callback.
Existing v1 callbacks must keep their current two-argument contract. Source
ownership must be resolved from the queued action, never the current selection;
stale/deleted source or target must fail without resource debit or retargeting.
Stock acquisition, cancellation, repeat cast, affordability feedback, unit
construction, and cleanup should remain in their existing order. The consumer
then removes nearest-unit reconstruction and applies its own policy to the
provided target. No watcher, nearby scan, or global last-click lookup is needed.

The user explicitly approved extending this private command/callback contract.
`stock.ap69-sovereign-target-action.v2` adds `callback_symbol`, a package-owned
void function `(agent Spell, agent SourceBuilding, agent ClickedTarget)`.
MMCR v20 records this opt-in and rejects missing/invalid callbacks. The final
composed function must retain that signature. All existing fields and control
evidence remain required; v1 stays binary- and behavior-compatible.

At submission, v2 keeps the clicked target and reserves the otherwise-zero
private gold-cost word for the source building ID. At executor entry it resolves
both IDs, validates source player/family/level and resource affordability, then
clears that word to zero **before any stock gold arithmetic**. Invalid sources
or missing targets cannot create a spell or debit resources. Insufficient
resources follow stock Sp23's unaffordable branch. Consumer target policy and
resource debit remain in its callback, allowing validation before debit.

The native executor wrapper retains the source only for the synchronous stock
execution, using a scoped frame restored on return/unwind. It does not consult
the live selection or retain a last-click pointer. The stock birth invocation
site passes the created spell and exact target to a wrapper which supplies the
third source argument through stock evaluator AddAgent calls. It bypasses the
unit's two-argument birth callback only for the matching v2 construction;
subsequent stock initialization/cleanup remains untouched. Do not separately
construct this v2 unit through a two-argument stock birth path while assigning
its birthscript to a three-argument function.

Additional audited boundaries (VA):

| Build | World pointer | Target lookup | Birth call | Stock birth invoker |
|---|---|---|---|---|
| Steam public | 0x7C544C | 0x5A15F0 | 0x4DAD8A | 0x5C5B20 |
| Steam beta2 | 0x7E3FD4 | 0x5B65A0 | 0x4DB39A | 0x5DAD00 |
| GOG | 0x7E426C | 0x5B58F0 | 0x4DBADA | 0x5DA050 |

Their call destinations, world load, and complete birth argument sequence are
pinned before installation and checked against the local executable fixtures.
V2 uses the existing audited evaluator constructor/AddAgent/execute/destructor
profile, with no return-value conversion. Native fixtures exercise queued
identity retention after selection/cursor changes, two different source
buildings, vanished entities, wrong player, depletion, and legacy commands.
Live spell use, cancellation, repeat casts, and multi-building play remain to
be verified in game.
