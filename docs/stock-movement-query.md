# Read-only movement-rate queries

Declare `{"type": "stock.movement-query.v1"}` in the package's schema-3
`runtime_features`. Do not add GPL stub definitions for these native functions.

| GPL function | Return type | Meaning |
| --- | --- | --- |
| `$MM_UnitMovementRate(agent Unit, integer Mode)` | integer | Mode 0: the unit's currently selected movement attachment, without attribute modifiers. Mode 1: the same attachment with the current stock movement-rate modifier and stock interval rounding. |
| `$MM_UnitTypeMovementRate(string UnitType)` | integer | Normal movement attachment (kind 1) of a named, loaded unit description, without an instance or attribute modifiers. Uses stock description-name lookup, e.g. `"Ranger"`. |

Rates are raw **Q16 map-coordinate units per simulation millisecond**: divide by
65536 for coordinate units/ms, or multiply by 1000/65536 for coordinate units/s.
Compare the returned integers directly; higher means faster. The coordinate
conversion is the engine's 32 source-distance units per map-coordinate unit.
Normal mode retains stock simulation-interval rounding; it removes the modifier,
not the engine's scheduling rules. No wall-time or position sampling is used.

These are locomotion rates, not instantaneous velocity. Standing still, turning,
blocked paths, collision avoidance, per-order step limits, and interruptions can
reduce observed travel without changing the returned rate. Mode 1 queries the
current modifier, not a historical snapshot of an already queued move order.
An explicit movement-attachment or unit-type change affects subsequent queries.

Returns: nonnegative rate on success (zero means no positive representable rate);
`-1` invalid/missing unit, unknown/empty description name, or invalid mode;
`-2` absent/unsupported movement description or non-stock interval override;
`-3` invalid/out-of-range movement data or unavailable simulation timing.
Call with the declared GPL argument types, as with stock native GPL functions.
Consumers requiring travel must reject all results <= 0; never substitute the
AI `ATTRIB_Speed` rating.

The description query reads Majesty's **loaded** description catalog, including
selected mods' replacements. It is not a second, pristine-vanilla catalog. It
does not require any instance of that unit to exist. Which reference types to
compare, which maximum to use, and eligibility/rechecking policy belong to the
consuming mod; the Manager has no hero/class speed table or following policy.

## Stock evidence and lifecycle

All addresses below are executable RVAs, public / beta2 respectively.

- `ChangeUnitType` (`031BB0 / 032B10`) supplies the stock argument ABI:
  argument-array accessor `02DDF0 / 02ED50`; virtual `+5C` obtains a GPL agent
  reference; `158B20 / 16EC60` resolves it without throwing for an absent unit.
  Resolution checks the script-agent deletion flag before obtaining its unit.
  This query uses a temporary reference so stock's disposable reference-cache
  write does not alter the caller's GPL reference.
- The same wrapper uses string virtual `+30` and description-name lookup
  `1AE060 / 1C3000` against the loaded unit-description registry at
  `3C5304 / 3E3E8C`. Lookup is read-only and retains native name matching.
- Unit construction/attachment selection stores a borrowed DMOV descriptor at
  unit `+54`. A unit-description engine stores eight movement bindings at
  `+D4`, each `{kind, resource ID, resolved descriptor pointer}` (12 bytes).
  The normal binding has kind 1. Supported DUNT engine subtypes are 1, 2, 3;
  supported DMOV subtype is 1 (the stock linear movement engine).
- DMOV construction resolves the resource first, then loads its PRIM values.
  The linear engine's `+0C` is the movement interval and `+10` the travel step.
  Derived-value initialization (`203460 / 2187A0`) converts distance by 32 and
  divides by the interval using signed Q16 arithmetic. Its vtable is
  `34A240 / 364310`. The query never constructs/clones a description or unit.
- The base interval getter (`1BA0F0 / 1CF090`) reads exactly
  `unit+54 -> descriptor+14 -> engine+0C`. The gameplay getter
  (`0479E0 / 0488F0`) adds packed attribute `0x22565041`
  (`ATTRIB_MovementRateModifier`), rounds intervals at or above the current
  simulation quantum to the nearest quantum, and clamps to at least 1.
  The simulation scheduler lives at `3C52D0 / 3E3E58`; its `+20` is the quantum.
- Stock move-step calculation (`1CDE80 / 1E3060`) reads that same attachment's
  step, performs the 32-unit conversion, and obtains the interval through unit
  virtual `+158`. Sub-quantum moves scale their step; ordinary intervals use
  the stock order scheduler. The queries report the corresponding rate, not
  order execution, pathfinding, or a replacement scheduler.

Installation validates both supported executable profiles before registering
the two functions at the stock GPL registration boundary. Map queries and these
queries share that one boundary. With neither feature selected, it is untouched;
with this feature selected but unused, there is no polling, timer, world scan,
unit tracking, or per-frame callback. Each call borrows already-owned native
objects and returns one integer. No gameplay state, attribute, order, resource,
save data, or callback lifecycle is changed; there is nothing to cancel or clean
up after the call. Stale/deleted handles are resolved afresh, never retained.
