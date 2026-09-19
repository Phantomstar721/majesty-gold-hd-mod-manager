# Attached-overlay movement scaling

This opt-in extension is for percentages smaller than Majesty's movement-clock
rounding can represent. It is approved as a distance adapter, not a replacement
clock, pathfinder, order controller or effect lifecycle. Initially it supports
only the audited Steam beta2 1.5.2.28 executable.

Declare a private overlay in schema-3 `runtime_features`:

```json
{"type":"manager.overlay-movement-scale.v1","overlay_id":"ZE01","percent":115}
```

The overlay must be one package-owned, added `Unit/Overlay` Description; claiming
a stock unit or another package's overlay is rejected. Percent is an integer
1–1000; 100 leaves distance unchanged. There is no GPL setter or replacement
timer. Attach and remove the overlay with ordinary stock effectors. Existing
movement-period adjustments are independent: remove any old period adjustment
from **new** casts if it would otherwise double-apply the intended speed change.
Migrating existing saved effects remains the author’s responsibility.

Distinct active overlays add their bonuses: two 115% declarations give 130%,
not 132.25%. Repeated attachments of the same overlay count once, following
stock `GetEffector` presence semantics. Combined slowing effects have a 1%
minimum. These rules apply only to this opt-in feature, not stock modifiers.

## Stock lifecycle and exact boundary

Addresses below are beta2 VAs (image base `0x400000`).

- The linear DMOV engine (vtable `0x764310`) supplies period at `+0C` and
  distance at `+10`. Unit `+54` owns the selected descriptor binding, whose
  `+14` points to that engine. The ordinary interval getter `0x4488F0` combines
  the base period and packed modifier, then rounds to the simulation quantum.
  With quantum 50, periods 70 and 61 both become 50. Changing that period by
  a percentage therefore cannot give a consistent small speed bonus.
- Stock `0x5E3060` converts the distance to signed Q16 map units (divide by 32),
  accounts for sub-quantum periods, and applies the `0x4000` order flag's
  15/32-coordinate step cap. Native order construction (`0x5E3329`, and derived
  construction at `0x60E765`) caches this **base** step at order `+48`.
- Linear order execution `0x5E3120` obtains the native unit, computes direction
  and remaining distance, and lazily computes the same base step if absent.
  It compares distance/step at `0x5E31D2`, multiplies the direction through
  `0x5E2910` at `0x5E31EA`, and checks continued movement at `0x5E3286`.
  One adapter at the first read computes the scaled step into the consumed
  unit-argument stack slot (`ESP+2C`; the unit is already preserved in EBP).
  Stock itself reuses this slot for lazy step output before `0x5E31CC`, and
  never needs its old argument value afterward. Redirecting EBX to this local
  value lets all three unchanged native reads use the same step. The cached
  base step is never overwritten. Applying or removing an overlay therefore
  affects the next update even on an already-running native order. Nothing
  re-queries the unit after movement callbacks, which could change its lifetime.
- The unchanged native order virtual `+20` moves the unit; the order manager
  callback `+44` and the existing distance comparison determine continuation.
  Stock retains destination clipping, collision/path handling, flag-specific
  rounding, rescheduling with the existing period, arrival and retirement
  (`+4C`). No retained order pointer is read after retirement.
- Stock `GetEffector` (`0x5DE7B0`) queries category 1 in the unit's attached
  container at `+A4`, through `0x5BC6E0`. Its native iterator (`0x5BBE60`) skips
  inactive/deleted attachment records (flag bit 1) and matches the overlay's
  Description ID (`unit+7C`). The adapter borrows that query's result only as
  a boolean, never stores an effector pointer, and counts each declared ID once.
  Native creation, expiry callback, cancellation, deletion and save restoration
  continue to own the entire effect lifetime; no watcher or extra save state
  is introduced. UI rows continue following those same native attachments.

The distance calculation uses widened integer arithmetic and retains positive
Q16 resolution, overflow bounds and the stock order's step cap. No matching
overlay means exact unchanged stock values. With no declarations, none of the
movement execution sites are patched. When selected, work is limited to stock
overlay lookups when a linear order consumes a step or a caller requests a rate;
there are no global scans, timers or idle callbacks.

`MM_UnitMovementRate(unit, 1)`, when the separate movement-query feature is
declared, includes this distance scaling before rate division. Mode 0 and the
unit-type query remain unscaled reference values. Reported rates are nominal;
short destinations, collision, turning and native per-order caps still affect
actual travel. Action/attack speed is not changed by this feature.

MMFR v8 adds flag bit 6 and a final count plus sorted `{overlay FourCC, percent}`
u32 records, maximum 256. Older records retain their layout (including the v6
research effect field). MMCP enables the adapter only when this list is nonempty.
Python and native parsers reject malformed, duplicate or out-of-order data;
installation separately checks the full native functions before patching.
