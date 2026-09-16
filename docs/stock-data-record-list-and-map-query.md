# Data-record lists and bounded map queries

These independent schema-v3 features contain no quest, guild, payout, travel,
or target-selection policy. They can be used separately. The existing
`stock.mx05-live-agent-list-panel.v1` is unchanged.

## Read-only map queries

Declare `{"type": "stock.map-fog-query.v1"}` in `runtime_features`.
This enables the following shared native GPL functions:

```text
$MM_MapFog(integer Player, coordinate Point) is integer
$MM_MapNextFrontier(integer Player, coordinate Origin,
                    integer Cursor, integer Budget, coordinate Result) is integer
```

`MM_MapFog` returns `-1` for invalid input/no active map, `0` for unexplored,
or `1` for explored. This is the same persistent explored bit tested by stock
`GetNearestHiddenCoord`, **not** current line of sight. Player is a zero-based
stock player-bit index (0..31). Coordinates use GPL map units: one tile is 32
units. Bounds are `[0, GetBoardExtents().X)` and `[0, GetBoardExtents().Y)`.

`MM_MapNextFrontier` finds an unexplored tile with an explored cardinal
neighbour, reading Majesty's existing tile array. Initialize `Cursor` to zero;
it is an **in/out integer variable** counting examined tiles, not results.
Keep Player and Origin fixed for one traversal. Scanning follows stock
`GetNearestHiddenCoord`'s expanding rectangles: start with the 2-by-2 rectangle
from Origin's tile through the tile one step right/down, then grow all four
sides by one tile. Within each rectangle, the order is top left-to-right,
right top-to-bottom, bottom right-to-left, then left bottom-to-top. This is
one of stock's four orientations, fixed without consuming game randomness.
Out-of-bounds and already-visited clamped-edge cells are omitted. Returned
coordinates are tile centers; a traversal never yields the same tile twice.
This is stock rectangle-near ordering, not global Euclidean-distance sorting.

The return status is:

| Value | Meaning |
| --- | --- |
| -1 | Invalid arguments or unavailable map; outputs unchanged |
| 0 | Work budget exhausted; more tiles remain |
| 1 | Found a frontier; Result updated, Cursor advanced |
| 2 | All tiles visited; no unvisited candidate remains |

Budget must be 1..256. One unit examines one tile and at most four neighbours:
at most `5 * Budget` mask reads, with early exit on the first candidate.
Resuming seeks the cursor's rectangle with at most 26 arithmetic comparisons,
without rereading previous tiles or walking through every previous rectangle.
Each visited tile then needs at most eight segment checks to locate it, including
on thin maps or near a map edge. Work is bounded independently of map area.
There is no hidden exhaustive native search, pathfinding, randomness, cache,
thread, or work between calls. Result remains unchanged unless status is 1.
A completed traversal may have yielded candidates earlier; completion does
not invalidate them. Neither status 0 nor absence of frontier proves the map
fully explored (a wholly unexplored map has no explored/unexplored boundary).
The caller owns any overall attempt limit, sampling, reachability checks, and
reset on generation/load; do not persist a cursor across different maps.

Native registration follows the stock GPL function-registration lifecycle,
after stock functions and before package bytecode resolution. No map pointer
is retained across calls or serialized. When the feature is absent, its
registration hook is not installed.

## Independent list records

Declare a `stock.mx05-data-record-list-panel.v1` feature. It uses the same
private MX05-shaped panel and building declaration as the live-agent list, but
replaces `row_agent_id_callback_symbol` with `row_key_callback_symbol`:

```json
{
  "type": "stock.mx05-data-record-list-panel.v1",
  "panel_key": "notices",
  "parent_building": "library",
  "source_dialog_id": "PN01",
  "open_command_id": 16641,
  "row_count_callback_symbol": "Notice_Count",
  "row_key_callback_symbol": "Notice_Key",
  "revision_callback_symbol": "Notice_Revision",
  "row_title_text": "Survey destination",
  "row_text": "Visit the marked coordinate",
  "row_value_callback_symbol": "Notice_Reward",
  "row_value_suffix_text": " Gold",
  "action_cost_callback_symbol": "Notice_RefreshCost",
  "action_callback_symbol": "Notice_Refresh",
  "stay_on_panel_after_action": true,
  "focus_selected_row_on_click": false,
  "action_agent_scope": "parent"
}
```

Callbacks retain the existing integer contract:

- Count and Revision: `(agent Parent) is integer`. Count is 0..64.
- Key, optional Value, optional Variant: `(agent Parent, integer Row) is integer`.
  Row is **one-based index, not record key**. All callbacks in a snapshot must
  read the same ordering and must not mutate gameplay state.
- Key: unique 1..2147483647 within that parent list. It is not resolved as a
  GPL agent, native Unit, world coordinate, or pointer. Preserve a record's key
  across reorderings/revisions; avoid recycling keys during the parent's life.
- Revision: nonnegative integer changed whenever contents/order/text/value
  change. The Manager rebuilds its snapshot on existing stock event boundaries,
  not a new polling timer, and does not query rows from the draw callback.
- Value: optional nonnegative signed integer. Set both value callback and
  suffix to null to omit it.
- Cost: `(agent Parent) is integer`, nonnegative signed integer.
- Action: `(agent Parent) is boolean`, called through the existing queued stock
  paid-action executor after its validation and debit.

`row_variant_callback_symbol` and `row_variants` have the live-list syntax;
variant indices are one-based. Use null static title/detail when supplying
variants. Every data row/variant needs an explicit title; no world name fallback
exists. Each title/detail/suffix is bounded to 96 Windows-1252 bytes; keep text
concise for the stock sidebar. The native text-only row reserves three lines.

No row action or world refocus is implied by selecting a record. Actions are
parent-scoped and stay on the child panel; contradictory policies are rejected.
The native list owns the text copies, integer item data, scrolling, highlight,
and destruction. Selection/top row are preserved by key on Refresh. The MX05
Unit vector remains empty; no fake unit or standalone GPL agent is inserted.

## State ownership and lifecycle

The package owns persistent records, coordinates, claimants, eligibility,
cancellation, and rewards in its normal saved GPL state. Existing parent-owned
attributes/collections are sufficient; **no new standalone-agent lifetime is
required by this interface**. It does not create/delete agents or claim to
validate their existence. A package choosing standalone GPL agents remains
responsible for their stock creation/save/load/deletion lifecycle.

The Manager owns only a bounded presentation snapshot. Opening constructs the
stock child with its live parent handle; callbacks populate the snapshot.
Revision changes replace native text rows, preserving selection by key.
Bad counts/keys/callbacks disable the list instance instead of interpreting data
as pointers. Closing, changing building, parent destruction, or native teardown
clears that transient snapshot through the existing controller destructor.
After load/reopen, callbacks reconstruct presentation from saved package data.
The Manager never serializes native pointers, creates offers, cancels accepted
work on Refresh, or pays a quest reward. Those policies stay in the package.

## Native reference

Public / beta2 stock authorities (image-relative addresses): GPL registration
call `198EE7 / 1ADE97`, map extents `1BC9C0 / 1D1930`, hidden-coordinate wrapper
`1BE9F0 / 1D3BD0`. World+88 is the map; map+38/+3C are usable dimensions,
+40 is padded stride, +54 is the 24-byte tile array, and tile+4 is the explored
player mask. No field is written by this feature.

The stock expanding search is at `1C2F20 / 1D8100`. Its first orientation's
four perimeter loops occupy offsets `+86..+163`; `+163..+1E6` grows and clamps
the bounds. The bounded query retains the first-visit order of those loops,
but does not repeat clamped edges, read padding, randomize orientation, or
apply stock's output-coordinate shift toward the origin. Its documented
frontier predicate and tile-center output remain unchanged. Exhaustion exits
immediately and leaves continuation in the caller-owned integer; no deferred
work or native search context survives the call.

MX05 shared refresh `97E20 / 98640` defines list clear/insert/text/item-data,
selection/top restoration, and scrollbar linkage. `CYDialogListboxItem`
vtables `34F76C / 369844` provide the native text painter instead of MX05's
Unit-specific painter. Parent payment uses the already traced stock command
0x15 lifecycle, and controller teardown uses the existing stock destructor
registry. MMFR v2 carries a map-query flag; MMCR v16 carries the record-row
mode. Old features still emit their prior wire versions.
