# `$ListObjects` acceleration

An always-on runtime change with no package declaration. Stock `$ListObjects`
hands one per-unit filter callback to each candidate collection it walks. The
runtime replaces only that callback with an exact re-implementation that reaches
the same decision with less work. Results, their order, script errors and every
side effect stay those of stock Majesty. An executable without an audited
profile, or with any difference in the guarded stock bytes, keeps the stock
callback.

Profiles exist for default Steam 1.5.2.24 and Steam beta2 1.5.2.28. GOG 1.5.2.28
has no profile yet and keeps the stock callback until a row produced by
`scripts/audit_listobjects_acceleration.py` is added.

## Why native code

`$ListObjects` is a GPL built-in. Scripts can only call it, and its cost is spent
inside the native callback, once per unit of every walked collection on every
call. In GPL profiler captures of saves with many AI-driven units it is the
largest single self-time entry. CAM resources, GPL and the existing Manager
features cannot change how the built-in evaluates a unit.

## Stock lifecycle traced before implementation

Addresses are executable VAs (public / beta2). Both builds contain the same
instruction sequence; only address operands differ.

- `$ListObjects` (`439050 / 439F60`) parses its arguments into fixed `.data`
  search state: anchor, type string, range, player and team filters, the
  title/subtype key and comparand, attribute id/value pairs, an optional point,
  and the inside-units and first-match-only flags. A positive range `r` becomes
  the squared limit `(r/16)²` (integer division), zero means touching footprints
  only, and a negative range means no limit. Because the state is global, the
  built-in is not re-entrant. It runs synchronously on the GPL thread.
- It collects matches in a static result vector (`7C10A8 / 7DFB60`) while it
  walks the candidate collections: by default the anchor kingdom's visible-unit
  list, or, with the hidden-map modifier, the building, vehicle and reward-flag
  lists. Each walk is the collection's virtual `+30` ForEach, called at
  `439482 / 43A392` as `PUSH 0; PUSH 0; PUSH <filter>; CALL EAX`. That operand
  is the only reference to the filter in either executable.
- The filter (`438D70 / 439C80`, cdecl `int(unit, 0, 0)`) tests, in order:
  1. an indoor unit (host id at `+84`) is skipped unless the inside-units flag
     is set;
  2. the anchor itself is skipped;
  3. the squared footprint gap to the anchor (`436390 / 4372A0`), or to the
     point (position `5C1BC0 / 5D6DA0`, rectangle distance `5C1CC0 / 5D6EA0`),
     is computed for every remaining unit and compared with a non-negative
     limit;
  4. the player filter (player id at `+80`);
  5. the team filter: the anchor's and the unit's teams through
     `50A8B0 / 51AE00`, the unit's player through virtual `+1C`;
  6. the unit's `'AE'` agent component (`42D570 / 42E7B0`); none rejects;
  7. an agent reference is built (`558620 / 56E760`), and the property getter
     (`5587C0 / 56E900`) reads the GPL type through the attribute lookup
     (`5616A0 / 5777D0`). The getter resolves the agent again
     (`55E8E0 / 574A20`) and raises a script error for a missing or deleted
     agent (`+38`); the attribute lookup raises one for a missing attribute.
     This lookup also happens when no type string was given; a given type is
     compared with `_stricmp`;
  8. with both a title/subtype key and comparand, a second getter call and
     `_stricmp`;
  9. the attribute pairs, last pair first (`5B9FD0 / 5CEF70`), by exact
     integer equality.

  A match creates a GPL agent value (`558480 / 56E5C0`, kind 5), sets it from a
  new agent reference and pushes `{distance, component, value}` through
  `438CF0 / 439C00`. With first-match-only the callback then returns 1, which
  stops the walk. Every other path returns 0.
- After the walks the records are sorted by distance, then by component
  address. The output list is cleared and refilled, and the match count is
  returned. First-match-only keeps the first match in collection order.
- Agent references are destroyed inside the callback. Apart from the output
  list and the GPL values it holds, nothing outlives the call: the next call
  rewrites the search globals and the result vector. There is no callback,
  cancellation path, saved state or UI refresh.

## The hand-over site and the accelerated callback

The only write is the four-byte operand of that `PUSH <filter>`. It is replaced
during DLL initialization by `ListObjectsAcceleration::Install`, after the build
profile is selected. The accelerated callback has the stock signature and return
contract, reads the same `.data` state and calls the same stock helpers. It
evaluates the same conjunction in a cheaper order:

| Stock | Accelerated |
| --- | --- |
| Distance for every unit, before the player filter | Player filter first. Distance only when the limit is not negative (still before any type lookup), or for a match as the record's sort key |
| Agent resolved by the reference constructor, then again by each property-getter call | Agent resolved once. Type and title are read through the same stock attribute lookup the getter calls |
| `'AE'` component found up to three times per match | Found once and reused for the record |

Every helper that can raise a script error is called for exactly the units, with
exactly the arguments and in the same order as in stock. That means the type
lookup for every unit that reaches it, the title lookup only when both key and
comparand are set, and the attribute reads last pair first. A missing or deleted
agent, where the stock getter raises its error, is handed to the stock callback
for that unit, so the error and its message stay stock's own. A match runs the
stock value, reference and push_back calls in stock order with the same record.

The reordered tests are pure reads. The distance helpers' only side effect is a
lazy footprint-extent cache fill. A unit whose distance is skipped fills that
cache the next time anything asks for it, so skipping the distance of an
unlimited, non-matching unit changes no result.

## Guards

`runtime/ListObjectsAccelerationProfiles.h` holds one row per audited build: the
two function RVAs and the FNV-1a hashes of six stock bodies. The bodies are
`$ListObjects` (`0x674` bytes, up to its modifier jump table), the filter
(`0x2D1`, through its final `RET`), the property getter, the result push_back,
the agent resolver and the attribute lookup. `Install()`:

1. selects the row for the detected build, or refuses;
2. requires the `0x400000` image base, and checks that both functions lie in
   `.text` and match their hashes;
3. checks `PUSH 0; PUSH 0; PUSH <filter>; CALL EAX` at the hand-over site;
4. decodes the getter and push_back from the verified filter, and checks their
   hashes and that they share the filter's GPL-manager getter; it then decodes
   the resolver and attribute lookup from the verified getter and checks those
   hashes too;
5. decodes every other helper and global from fixed operand offsets of the
   verified filter, requires each call target to be in `.text` and each global
   in the image, and requires the bound `_stricmp` import;
6. writes the four-byte operand under `VirtualProtect` and flushes the
   instruction cache.

Any failure logs `ListObjects acceleration not installed (<reason>); stock
$ListObjects is unchanged.` to `MajestyBuildingRuntime.log` and writes nothing.
Success logs one line, and the callback logs once, after 4096 units, that it is
active. A second `Install()` refuses because the hashed `$ListObjects` body now
contains the new operand.

## Verification build

`scripts/Build-Runtime.ps1 -ListObjectsDifferential` defines
`MAJESTY_LISTOBJECTS_DIFFERENTIAL`. Its callback first evaluates the accelerated
decision without side effects. It then runs the stock callback, which alone
produces the result. For every unit it compares the decision, distance,
component, record count and return value. The first 64 disagreements are logged
with the search state. Totals of units, matches, delegated units and mismatches
are logged at 4096 units and every 2^20 units after that. An exception raised by
either evaluation is logged from an SEH filter and then propagates as it does in
stock. This build is for verification only and does more work than stock.

## Evidence

### Offline (native)

- `scripts/audit_listobjects_acceleration.py` finds both functions by signature,
  requiring exactly one match each. It checks the hand-over site and that the
  filter address occurs only once in the file, and decodes all 30 filter
  operands, checking the opcode bytes in front of each. It also checks the
  structural facts the callback relies on: the unit player and host offsets, the
  `'AE'` key, the virtual slots, the value kind, the deleted-agent flag and the
  result vector fields. It then prints each build's row.
- `tests/test_listobjects_acceleration_profiles.py` re-derives every row from
  its executable the way `Install()` does and compares it with the audit.
- `tests/ListObjectsAccelerationTests.cpp` (`Build-Runtime.ps1 -FeatureTests`)
  maps each executable at `0x400000`. It checks every refusal path and that a
  successful install changes only the four operand bytes. It then replaces the
  stock leaf helpers with recording fakes, and runs the stock filter's own bytes
  and the accelerated callback on synthetic units. The search states cover every
  combination of the inside flag, point or anchor distance, four ranges, player
  and team filters, type and title/subtype settings, zero to two attribute pairs
  and first-match-only. For each unit both callbacks must give the same return
  value, the same records and the same sequence of calls that can raise an error
  or have a side effect. For missing or deleted agents the fixture checks the
  hand-over to the stock callback. Each audited build gets 124,416 live-agent
  unit comparisons and 55,296 missing/deleted-agent checks. The fixture passes
  in both the release and the verification-build configuration.

### Live

Static verification is not gameplay acceptance. On 2026-11-12, Steam beta2 ran
the verification build for about seven minutes of a save with many units. It
recorded 1,319,108,608 unit evaluations and 1,694,359 matches, with 0 mismatches
and 0 exceptions, and every install guard passed on that executable. No
missing or deleted agent reached the filter in that session (0 delegated
units), so that path rests on the offline fixture. Default Steam has not been
run live, and GOG has no profile.

## Not changed

Argument parsing, the candidate collections and their walk order, the sort, the
output list and every error message stay stock. Each call still walks its whole
collection; a per-type candidate index would be a separate, larger change.

## Adding or refreshing a build

Run `python scripts/audit_listobjects_acceleration.py <MajestyHD.exe>` on the
pristine executable and paste the printed `C++:` row into
`runtime/ListObjectsAccelerationProfiles.h`. Then run the profile test and the
x86 fixture with all three executables.
