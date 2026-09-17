# Generic MX05 live-agent list lifecycle

For independent rows without a native world object, use the separate
[data-record list feature](stock-data-record-list-and-map-query.md). Its keys
are not live-agent IDs and must not be passed to the feature described here.

`stock.mx05-live-agent-list-panel.v1` lets a package populate Majesty's stock
MX05 list with zero to 64 distinct live agents. It is not quest-specific: the
parent may use any cataloged stock primary-building controller with its
matching stock panel template.

The ownership boundary is deliberately small:

- the parent controller owns opening, events, and teardown;
- MX05 owns the list, scrollbar, selection, native bottom action, price,
  affordability, queued payment, and Back;
- package GPL chooses the live agents, reports a revision, computes an optional
  per-row value, and performs the declared row- or parent-scoped action;
- the Manager supplies only bounded row presentation and callback routing.

The Manager does not create fake row objects, add controls, resize the list,
poll from the painter, or replace MX05 selection and action handling.

## Package contract

```json
{
  "type": "stock.mx05-live-agent-list-panel.v1",
  "panel_key": "available-orders",
  "parent_building": "YourNamespacedBuilding",
  "source_dialog_id": "LP01",
  "open_command_id": 29001,
  "row_count_callback_symbol": "YourMod_Row_Count",
  "row_agent_id_callback_symbol": "YourMod_Row_Agent_Id",
  "revision_callback_symbol": "YourMod_Row_Revision",
  "row_title_text": null,
  "row_text": null,
  "row_variant_callback_symbol": "YourMod_Row_Variant",
  "row_variants": [
    {"title_text": "Delivery", "row_text": "Deliver this order"},
    {"title_text": "Escort", "row_text": "Protect this traveler"}
  ],
  "row_value_callback_symbol": "YourMod_Row_Reward",
  "row_value_suffix_text": " Gold",
  "action_cost_callback_symbol": "YourMod_Action_Cost",
  "action_callback_symbol": "YourMod_Action_After_Debit",
  "stay_on_panel_after_action": true,
  "focus_selected_row_on_click": false,
  "action_agent_scope": "parent"
}
```

The callbacks must exist exactly once in included GPL:

```text
Function YourMod_Row_Count (agent Parent) is integer
Function YourMod_Row_Agent_Id (agent Parent, integer Row) is integer
Function YourMod_Row_Revision (agent Parent) is integer
Function YourMod_Row_Variant (agent Parent, integer Row) is integer
Function YourMod_Row_Reward (agent Parent, integer Row) is integer
Function YourMod_Action_Cost (agent ActionAgent) is integer
Function YourMod_Action_After_Debit (agent ActionAgent) is boolean
```

Rows are one-based. `Row_Count` may return `0` through `64`.
`Row_Agent_Id` must return the stock `ATTRIB_AgentID` of a different, non-null
live game agent for every reported row. A typical callback selects its row
agent from package-owned state and ends with:

```text
return $GetAttribute(RowAgent, #ATTRIB_AgentID);
```

Those agents must remain live while the panel is open. The Manager resolves
each returned ID through Majesty's validated stock live-agent lookup before it
is inserted into MX05. By default, MX05 passes the selected row's live agent to
both action callbacks. The optional `action_agent_scope` field accepts
`"selected-row"` (the default) or `"parent"`. Parent scope makes the native
bottom action panel-global: both callbacks receive the durable parent building
regardless of row selection, and the action remains available when the list is
empty. This avoids binding a list-wide action such as Refresh to a row that may
disappear before its queued command executes. The cost callback is a
side-effect-free gold quote; the action callback runs through stock queued
payment and must not deduct that gold again.

`row_title_text` and `row_text` are optional bounded Windows-1252 strings for
packages that want the same presentation on every row. A null title preserves
each row agent's ordinary stock name. Existing packages may omit the variant
fields entirely.

For different static presentation per row, set both common text fields to null,
supply `row_variant_callback_symbol`, and declare one through 64 `row_variants`.
Every variant contains exactly `title_text` and `row_text`; either may be null,
but not both. The integer callback receives `(Parent, Row)` and returns the
one-based variant index. The Manager resolves every declared string through its
private literal-text registry before launch. GPL never returns strings. A zero
or out-of-range variant result clears and faults only that private list.

The optional value is enabled by supplying both `row_value_callback_symbol` and
`row_value_suffix_text`; set both to null to omit it. When present, the value is
displayed on its own reward line below the selected row text. At least one of
common text, row variants, or value must be customized.

`stay_on_panel_after_action` is optional and defaults to `false`. Stock MX05
normally transfers world selection from the parent building to the selected
row agent after a successful bottom action. Set this field to `true` when the
action should leave the current child list open instead. The policy runs only
after stock has queued the paid action: it does not change the selected row,
the quoted/debited cost, command packet, GPL callback, revision, or refresh.
Lists that omit the field and all ordinary occupant-action panels retain the
complete stock focus behavior.

`focus_selected_row_on_click` is independently optional and defaults to `true`.
Set it to `false` when the list uses a live agent only as stable row identity
and clicking the row should not move Majesty's world or tracking-panel focus to
that agent. MX05 still accepts the row selection and refreshes the list's
selection, text, action, and cost state; only the final stock focus transfer is
skipped. This is useful for abstract rows such as jobs, orders, or quests, but
the contract is not quest- or building-specific.

This contract intentionally uses live agents as row identity. It gives stock
MX05 a real object for selection and queued action dispatch, and avoids a
Manager-owned synthetic-row lifecycle.

## Required child resources

The package owns one MX05-shaped `SMNU`/`STRT` child pair. Its SMNU must retain
stock MX05's exact record count, positions, sizes, and these native rectangles:

| Control | Purpose | Rectangle |
|---:|---|---:|
| `0x1388` | list | `(10,55,164,160)` |
| `0x138B` | one bottom action | `(51,219,103,21)` |
| `0x138C` | action coin | `(33,219,16,17)` |
| `0x1392` | scrollbar | `(174,51,25,167)` |
| `0x1F46` | action price | `(115,222,39,16)` |

The two STRT indices referenced by action `0x138B` must contain the same
non-empty label. The label is package-defined; it is not required to say
Refresh. Obsolete generated controls `0x7102`, `0x7103`, and `0x7104` are
rejected. The Manager assigns the final child-dialog and queued-action IDs.

## Stock population and presentation

MX05 slot 11 clears the vector at controller offset `0x34` and inserts row
agents through two stock vector helpers. The Manager invokes those helpers in
the same order. Slots 8 and 11 provide the revision-gated population. The
slot-3 and slot-14 wrappers delegate directly to stock unless a declared list
policy applies. Stay-on-panel and row-focus policies affect only MX05's shared
control handoff. Parent-scoped actions run slot 14's unchanged shared-list
refresh half, skip only its incompatible selected-row cost tail, and then quote
and present the bottom action against the parent. Slot 3 submits MX05's same
four-word paid command with the parent building as both durable building and
action-agent handles. Selected-row scope never enters that branch.
A retained post-action child and a row click without world focus both return
MX05's stock non-transition result (`0`).

For each reported row, the Manager evaluates `Row_Agent_Id(Parent, Row)`,
requires an integer result, resolves that number through Majesty's stock
`GplAgentRef` live-agent lookup, rejects missing/dead or duplicate results, and
inserts the resolved agent pointer. It then builds immutable bounded
presentation records keyed by those exact pointers. Unmatched agents always
use stock presentation.

When variants are enabled, the Manager evaluates the integer variant callback
once for each row during that same revision-gated population pass and copies
the selected pre-resolved title/detail into the immutable presentation record.
The painter never invokes package GPL.

The shared row painter still calls Majesty's stock name formatter first so the
destination string has its normal construction and ownership. If the feature
has no custom title, that stock name is left unchanged. Optional detail and
value presentation is exposed through the stock intention and building-summary
paths only for a matched row.

MX05's shared agent painter also has two building-only status-icon calls. For a
matched package row, the Manager suppresses only those two final draw calls so
unrelated repair/tax status art cannot appear beside a generic list entry. The
stock status objects are still constructed, populated, and destroyed in their
original order. An unmatched row takes both original draw calls unchanged.

The four stock building-summary branches use GMTX IDs `0xD8` through `0xDB`.
Public resolves them through RVA `0x00024020`; beta2 uses `0x00024FF0`. The
resolver returns a 12-byte `MajestyStringView`, not a wide character pointer.
Manager summaries therefore use a stable narrow Windows-1252 backing string and
preserve the view's narrow-encoding flag. Package `%` characters are doubled
before the unchanged stock printf-style formatter consumes the template.

## Revision and cleanup

The revision callback is side-effect free. First open requests one population.
An unchanged revision causes no vector rewrite. A changed revision invokes the
saved stock slot 14 once, which reaches the gated slot-11 population. Stock
`XSCX` keeps its original one-refresh path.

Because slot 14 also runs at paint cadence, it never evaluates row population,
identity, revision, variant, or value callbacks. Selected-row scope retains
stock's normal cost-callback cadence. Parent scope runs the same stock shared
list refresh but bypasses the selected-row cost presenter, then evaluates the
package cost callback exactly once against the parent. It performs no row
discovery or vector rewrite.

Invalid callback results, more than 64 rows, null or duplicate row agents, or
bad presentation data clear only the private list and fault that child
instance. They do not convert a package data error into a process-wide runtime
installation failure. Back and destruction remain stock and clear all borrowed
row references.

## Verified stock boundaries

### Optional hidden verbose toggle on data-record panels

For `stock.mx05-data-record-list-panel.v1` only, the package may move control
`0x138C` from `(33, 219, 16, 17)` to the stock offscreen-hide rectangle
`(1500, 1500, 16, 17)`. Retain its native record, ID, order and dimensions.
No additional feature field or runtime hook is required. The visible stock
rectangle is also accepted. Live-agent panels retain the exact stock rectangle;
all other geometry checks are unchanged, including action `0x138B` and price
`0x1F46`.

This is the verbose/short-list toggle, not a payment icon. Beta2 MX05 command
`0x4BCB00` delegates it to `0x4995A0`; the `0x138C` branch at `0x4996F5`
reads its checked state, calls `0x497910(1, checked)` and invokes list refresh
through virtual `+0x38`. Setup at `0x499510` initializes its checked state
from the stock list preference without repositioning it. Data-record mode
already consumes this Unit-specific command in `QuestBoardControl`. Keeping
the record offscreen preserves native construction and cleanup without adding
a useless player-facing control or changing Refresh payment behavior.

### Executable profiles

The Manager profiles both supported executable builds. AP08 uses the public
vtable at `0x0073D37C` and beta2 vtable at `0x00756054`, each with 13 entries.
MX05 uses public table `0x0073EAC4` and beta2 table `0x007577AC`, each with 15
entries. The live-agent resolver is public RVA `0x00158B20` and beta2 RVA
`0x0016EC60`. The row-ID callback must return stock GPL integer type 1. The
Manager validates the resolver's entry, registry lookup, cached-reference,
live/dead check, and null-return shapes before constructing the temporary
stock-shaped reference used to resolve that integer ID.

Read-only executable tests verify those profiles, GPL integer and agent-reference
types, the complete agent resolver shape, MX05 vector helpers, painter, summary,
both status-icon seams, the stock event gate, and both shared-control handoffs.
Native x86 tests verify
three simultaneous rows, distinct identity, optional text/value presentation,
matched-only status-icon suppression, stable string-view lifetime, percent
escaping, one-based static variant selection and bounds failure, revision
gating, queued selected-row dispatch, parent-scoped paid actions with and
without rows, independent child-retention and row-focus policies, 64-row
bounds, stock fallbacks, and repeated slot-14 painting without polling the
row-count, row-identity, revision, variant, or row-value callbacks.
