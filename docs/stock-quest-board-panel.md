# AP08/MX05 quest-list lifecycle

`stock.ap08-mx05-quest-list-panel.v1` lets an AP08-shaped custom building show
package-owned quest agents through Majesty's existing MX05 visitor list. It is
a bounded stock-lifecycle recipe, not a generic UI or scripting engine.

- AP08 owns the primary quest-building setup, commands, events, and teardown.
- MX05 owns the child list, visitor row drawing, selection, scrollbar,
  selected-agent price, affordability, queued building command, and Back.
- The package owns quest creation, durable quest agents, availability,
  rejection, completion, and rewards.

The Manager changes only the list population source, two presentation inputs
inside MX05's existing row painter, and the GPL callbacks used for the selected
action. It does not construct fixed rows or periodically rewrite the panel.

## AP08 parent proof

The public executable constructs AP08 at `0x0049E1E0`, installs vtable
`0x0073D37C`, and returns a `0x38`-byte object from the dialog factory. Beta2
constructs it at `0x0049EAC0`, installs vtable `0x00756054`, and uses the same
object size. Both vtables contain exactly 13 executable entries; the next word
is `#gam` string data.

Slots 1, 3, and 8 are setup, command, and event handling. The Manager copies
the live 13-entry table, replaces only those routing slots plus the registered
destructor dispatcher, delegates unhandled work to the captured stock entries,
and retires state only when Majesty destroys that exact controller.

## MX05 child proof

The MX05 child vtable has 15 entries. On beta2 its relevant entries are:

- slot 1, `0x004BCBC0`: calls shared list setup;
- slot 3, `0x004BCB00`: handles list selection `0x1388`, selected action
  `0x138B`, and otherwise delegates;
- slot 8, `0x004BC7D0`: refreshes only for the stock `XSCX` list-change event;
- slot 11, `0x004BCD80`: clears and populates the native agent vector;
- slot 14, `0x004BCC10`: invokes the shared list refresh.

Public has the equivalent slot layout at vtable `0x0073EAC4`; beta2 uses
`0x007577AC`. Shared refresh preserves selection by agent handle and invokes
Majesty's stock visitor row callback and painter. The Manager supplies the
package's bounded offer title at the painter's stock name-format call and its
goal/reward text at the painter's stock activity-text lookup. The rest of the
painter, including icon, level, layout, scrollbar, and empty-list state,
remains stock.

The package must retain the native list and action/price chrome. Stock
SMNU/MX05 literally authors controls `0x1388`, `0x138B`, `0x138C`, `0x1392`,
`0x1F40`, `0x1F41`, `0x1F45`, `0x1F46`, and `0x1F4D`; additional controls used
by MX05 are created or resolved by code. The package child adds no private
controls and the AP08 parent authors only the child opener. At composition the
Manager shortens the native list and scrollbar by one stock row, moves the
unchanged selected-action/coin/price records up by 25 pixels, and clones those
three literal records at their original bottom coordinates for Refresh. The
Manager supplies the cloned control IDs and strings. A package-authored Refresh
row or AP54 parent workaround is rejected.

## Native population and refresh

MX05's population virtual clears the vector stored at controller offset `0x34`
and inserts every agent from relation index 2 through two native vector helpers.
The Manager calls those same helpers, in the same order, but obtains at most
four durable quest agents from the package's list-source callback. External GPL
returns a durable agent ID as type-1 integer even when the function is declared
`is agent`; the Manager extracts that scalar and passes a stock 16-byte
agent-handle shape to Majesty's exact ID-to-agent resolver. Native type-5 agent
values follow their existing stock virtual and the same resolver. Rows must be
contiguous: row 1 through the last offer return agents and every later row
returns `Null()`.

Stock setup calls slot 14, which reaches the overridden slot 11 and then the
shared list presenter. The Manager does not perform a second content pass.
After that presenter, the Manager applies one deliberately narrow visual rule
approved for Manager quest boards: when stock reports no selected row, controls
`0x138C` (coin) and `0x1F46` (price) are hidden; when a row is selected, both
are restored. Stock still owns list selection, action `0x138B`, price text,
affordability, command dispatch, and Back. The source package SMNU remains an
exact MX05 clone; only generated merged output receives the second action row.
Stock `XSCX` events follow the same route exactly once. Static disassembly shows
that MX05 compares the event ID, calls vtable slot 14 once when it is `XSCX`,
and immediately returns. Majesty may supply that stock event frequently; the
Manager neither emits it nor adds a second list refresh. After stock finishes,
it revalidates only the generated Refresh action.
Package list changes do not emit `XSCX`, so at other existing stock event
boundaries the Manager reads one side-effect-free revision value. An unchanged
revision produces no list write; a changed revision invokes stock slot 14 once
and then reapplies the selected-action and generated-Refresh presentation.
No timer, watcher, or replacement state machine is introduced.

After MX05's native slot-14 refresh finishes, the child publishes the package's
Refresh quote into the Manager-generated price binding, presents the cloned
action/coin/price controls together, and uses the stock action-enable message.
Unchanged events do not rebuild the list. XSCX or a package revision change
follows MX05's existing slot-14 refresh and then revalidates the Refresh quote.
The AP08 parent never evaluates or dispatches Refresh.

## Selected action and Refresh dispatch

MX05 selection `0x1388` and selected action `0x138B` remain entirely stock.
The stock cost evaluator receives the selected quest agent. For a free Reject,
the package returns zero. Stock queues the selected agent handle, owner building
ID, and quoted price as command `0x15`; the Manager changes only that command's
discriminator to its allocated quest-action ID.

The MX05 child handles its Manager-generated Refresh control before delegating
unrelated controls to the stock handler. It validates the package gate and
quote, then queues the Guild as both the building and action agent. At
simulation dispatch, either immutable Manager
command ID selects the corresponding package callback and is translated back
to stock command `0x15`. The native executor still resolves the IDs, validates
and debits the quoted gold, and invokes GPL. Package callbacks must not debit
gold again.

Callback context is scoped to that native dispatch and restored after nested
calls. Back may destroy the child inside the delegated stock handler, so no
post-control panel access occurs.

## Author contract

The feature has ten package-owned GPL callbacks:

```text
Function YourMod_Offer_At (agent Guild, integer Row) is agent
Function YourMod_Offer_Revision (agent Guild) is integer
Function YourMod_Offer_Name (agent Guild, integer Row) is string
Function YourMod_Offer_Goal (agent Guild, integer Row) is string
Function YourMod_Offer_Reward (agent Guild, integer Row) is integer
Function YourMod_Reject_Cost (agent Offer) is integer
Function YourMod_Reject_Offer (agent Offer) is boolean
Function YourMod_Refresh_Cost (agent Guild) is integer
Function YourMod_Can_Refresh (agent Guild) is boolean
Function YourMod_Refresh_After_Debit (agent Guild) is boolean
```

The parent is a declared `AP08`/`AP08` custom building. Its SMNU contains only
the declared child opener. The child owns exactly one SMNU/STRT pair containing
the nine literal stock MX05 records and no package-specific controls. Refresh
control IDs and text are Manager-owned output and are not author fields. Dialog
IDs, commands, and callback symbols must remain unambiguous across the full
selection.

The Manager derives the count from `Offer_At`; there is no count callback,
per-row command, or per-row UI contract. For each non-null row, the three
presentation callbacks provide a bounded title, goal, and reward. They are
read only when the revision changes and are shown through MX05's existing
painter. Majesty's type-0 GPL `Null()` result is the normal end-of-list sentinel
and produces an empty or shorter native MX05 list; it is not a runtime error.
Native callers read external GPL boolean callbacks through Majesty's stock
scalar-result helper and branch on zero/nonzero; at that evaluator boundary the
result is type 1 even though the internal `GplBoolean` class is type 6. Integer
callbacks likewise require type 1 before the scalar helper is used. A mismatched
package callback is rejected without invoking a fatal base-class conversion.
Quest semantics remain package-owned.

MMCR v7 stores the two Manager-allocated commands and ten callbacks. MMCR v5's
fixed-row wire and v6's incomplete native rows are rejected so an obsolete
package/runtime combination cannot silently use an incompatible presenter.

Read-only profile tests verify both executable builds' scalar/string/agent
evaluator calls, AP08 vtable boundary, MX05 list virtuals, vector helper and
row-painter call sites, and stock event gate. Native x86 tests verify command
routing, vector replacement, private row text, revision gating, one-pass
refresh, and teardown without launching Majesty.
