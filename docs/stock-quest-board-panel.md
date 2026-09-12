# AP08/MX05 one-row quest-board lifecycle

`stock.ap08-mx05-quest-list-panel.v4` is the smallest proven package-fed
quest-board contract. It lets an AP08-shaped custom Guild present zero or one
package-owned offer through Majesty's existing MX05 list lifecycle. It is not
a generic multi-row UI or scripting engine.

- AP08 owns primary building setup, the child opener, events, and teardown.
- MX05 owns the child list, drawing, scrollbar, selection-dependent action,
  price, affordability, queued payment, and Back.
- The package owns offer availability, static row text, reward, Refresh cost,
  Refresh after-debit behavior, and all quest semantics.

The Manager changes only MX05's population source, resolves two bounded static
row strings through its private text registry, and routes the native action's
cost/action callback symbols. It does not add controls, resize the list, move
the stock action row, poll the package, or replace MX05's presentation.

## Stock boundaries

The public executable constructs AP08 at `0x0049E1E0`, installs vtable
`0x0073D37C`, and allocates a `0x38`-byte object. Beta2 constructs AP08 at
`0x0049EAC0`, installs vtable `0x00756054`, and uses the same object size. Both
tables contain exactly 13 executable entries. The Manager copies that exact
boundary, replaces only routing slots 1, 3, and 8 plus the registered
destructor dispatcher, and delegates all unrelated behavior to stock.

The MX05 child has 15 entries. On beta2 its relevant entries are:

- slot 1, `0x004BCBC0`: shared list setup;
- slot 3, `0x004BCB00`: list selection, action, and delegation;
- slot 8, `0x004BC7D0`: stock `XSCX` list-change handling;
- slot 11, `0x004BCD80`: native agent-vector population;
- slot 14, `0x004BCC10`: shared list refresh/paint.

Public uses the equivalent table at `0x0073EAC4`; beta2 uses `0x007577AC`.
The private clone wraps only slots 8 and 11. Slots 3, 10, and 14 remain the
exact stock entries.

The package's MX05-shaped SMNU must retain stock MX05's exact record count and
these exact native records and rectangles:

| Control | Purpose | Rectangle |
|---:|---|---:|
| `0x1388` | list | `(10,55,164,160)` |
| `0x138B` | one bottom action | `(51,219,103,21)` |
| `0x138C` | action coin | `(33,219,16,17)` |
| `0x1392` | scrollbar | `(174,51,25,167)` |
| `0x1F46` | action price | `(115,222,39,16)` |

The two STRT indices referenced by native action `0x138B` must both say
`REFRESH`. Obsolete generated controls `0x7102`, `0x7103`, and `0x7104` are
rejected. There is no second action row and no Manager-owned presentation.

## One-row population proof

MX05 slot 11 clears the vector at controller offset `0x34` and inserts agents
through its two native vector helpers. The Manager invokes those same helpers
in the same order. The package returns `0` or `1` from its integer offer-count
callback:

- `0` produces the ordinary empty MX05 list;
- `1` inserts the already-known live Guild panel context as the single row;
- a value above `1` faults only the private rows and clears the vector.

The static title and goal come from the feature record. The reward callback
receives `(Guild, 1)` when the count is one. Stock MX05 still owns icon, level,
layout, scrollbar, selection, empty-list behavior, action enablement, and
clearing selection.

The revision callback is side-effect free. An unchanged revision performs no
population work. A changed revision invokes the saved stock slot 14 once.
Stock `XSCX` events keep their original one-refresh path; the Manager does not
emit synthetic events or add a timer.

Because slot 14 is also a high-frequency paint/update path, its stock entry is
never replaced. Slot 11 returns before evaluating package GPL unless this is
the first open or a real revision change requested new population. Repeated
slot-14 passes perform zero package GPL calls and zero Manager UI writes.

## Refresh dispatch and cleanup

MX05 selection `0x1388`, native action `0x138B`, price control `0x1F46`,
affordability, and queued payment remain stock. While the private quest-board
child is active, the Manager substitutes only the Refresh cost and action
symbols and one allocated command discriminator. The stock queue retains the
Guild row agent, owner building ID, and quoted price. Dispatch translates the
private discriminator back through the stock building-command executor, then
invokes the package's after-debit Refresh callback. The package must not deduct
gold again.

Back and destruction remain stock. Callback context is scoped to the active
native dispatch and restored after nested calls.

## Author contract

The feature declares five package-owned GPL callbacks:

```text
Function YourMod_Offer_Count (agent Guild) is integer
Function YourMod_Offer_Revision (agent Guild) is integer
Function YourMod_Offer_Reward (agent Guild, integer Row) is integer
Function YourMod_Refresh_Cost (agent Guild) is integer
Function YourMod_Refresh_After_Debit (agent Guild) is boolean
```

The `runtime_features` record is:

```json
{
  "type": "stock.ap08-mx05-quest-list-panel.v4",
  "panel_key": "offers",
  "parent_building": "YourNamespacedGuild",
  "source_dialog_id": "QB01",
  "open_command_id": 29001,
  "offer_count_callback_symbol": "YourMod_Offer_Count",
  "revision_callback_symbol": "YourMod_Offer_Revision",
  "offer_name_text": "Royal Dispatch",
  "offer_goal_text": "Deliver orders to an allied building",
  "offer_reward_callback_symbol": "YourMod_Offer_Reward",
  "refresh_cost_callback_symbol": "YourMod_Refresh_Cost",
  "refresh_callback_symbol": "YourMod_Refresh_After_Debit"
}
```

The parent is a declared `AP08`/`AP08` custom building. Its SMNU contains the
child opener. The child owns exactly one stock-shaped MX05 SMNU/STRT pair with
the native action labeled Refresh. The Manager assigns the final child and
queued-action IDs.

Offer Count must return only integer `0` or `1`. The two text fields are
nonempty Windows-1252 strings of at most 96 bytes. The Manager assigns stable
private IDs and stores only those IDs in MMCR. Reward and Refresh cost return
nonnegative signed 32-bit values. MMCR v10 stores this contract. MMCR v9 is
rejected because it encoded the non-stock duplicate Refresh row. Earlier
quest-board wire versions remain obsolete.

Read-only profile tests verify both executable builds' scalar evaluator calls,
AP08 boundary, MX05 list virtuals, vector helpers, painter sites, and event
gate. Native x86 tests verify zero/one population, count rejection, revision
gating, one-pass refresh, command routing, teardown, and 300 consecutive stock
slot-14 updates with no package scalar evaluation or Manager UI writes.
