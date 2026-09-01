# Private hero name generators

## Stock lifecycle

Majesty's name-generator manager constructs a map of 17 stock entries during
startup. Each entry is an eight-byte heap object containing the common stock
wrapper vtable and a pointer to a 0x40-byte generator. The generator receives
four explicit `HN` text-resource FourCCs plus the game's resource manager.

The stock sequence for every entry is:

1. Allocate the eight-byte wrapper through Majesty's imported operator new.
2. Put the common stock wrapper vtable in word zero.
3. Obtain the stock name-generator factory.
4. Construct the generator with four ordered `HN` IDs and the resource manager.
5. Put the resulting generator pointer in wrapper word one.
6. Find or insert the `NM` key in the manager's existing map.
7. Store the wrapper in the returned value slot.

`NM01` uses `HN01` through `HN04`, `NM02` uses `HN05` through `HN08`, and so on.
Most classes use the first two tables and leave the final two empty. Warriors
use three tables, allowing the `Sir` prefix, a given name, and an ending. The
last stock entry is `NM17`, which belongs to Inns and uses `BN01` through
`BN04`. There is no unused stock `NM` entry.

After inserting `NM17`, the constructor sets the manager-ready word at offset
`+0x24` to one. The private hook runs immediately before that assignment, when
the same registry pointer and resource-manager pointer are still live. It loops
over every manager-validated name-generator record in the immutable MMFR file
and repeats the literal stock construction sequence for each record. The hook
then replays the displaced ready assignment exactly.

An MMFR name record contains one private printable `NM` FourCC and four ordered,
distinct printable `HN` FourCCs. Records are deterministic and strictly sorted.
The manager rejects stock `NM01` through `NM17`, conflicting ownership, missing
package-owned `HN` resources, and a Description that does not select the
declared generator. The native parser independently enforces the wire bounds
before the hook is eligible for installation. See
[runtime-capability-manifest.md](runtime-capability-manifest.md) for the MMFR
format and limits.

There is no package-name or generator-specific runtime branch. Any validated
private `NM` record within the registry bounds follows the same stock lifecycle.
The current packages are useful compatibility examples:

| Package input | Generated MMFR record |
|---|---|
| Legacy Alchemist alias | `NM18` with `HN69`, `HN70`, `HN71`, `HN72` |
| Legacy expanded-Haunt alias | `NM19` with `HN73`, `HN74`, `HN75`, `HN76` |

The Alchemist package supplies 43 approved given names in `HN69`, 43 approved
space-prefixed surnames or epithets in `HN70`, and empty `HN71` and `HN72`
tables. No Cultist or other stock name table is replaced.

The expanded Phantoms Haunt package supplies its approved given names in
`HN73`, its space-prefixed surnames and epithets in `HN74`, and empty `HN75`
and `HN76` tables. Its Phantom description selects `NM19`, leaving the stock
Priestess `NM11` generator and its Original/Expansion `HN41`-`HN44` resources
unchanged.

Those fixed IDs are translations for existing schema-v1/v2 packages only. New
schema-v3 packages declare their own typed `stock.name-generator.v1` record;
the manager proves and composes it into MMFR, then derives the generic
`stock.name-generator.v1` MMCP hook selection. Legacy alias strings never select
a separate Alchemist or Phantom implementation inside the runtime.

## Dual executable trace

All addresses are RVAs from the image base and are independently guarded.

| Site | Public 1.5.2.24 | Beta2 1.5.2.28 | Guard |
|---|---:|---:|---|
| Registry completion hook | `0x0011090E` | `0x00120E5E` | `8B44241C895824` |
| Imported operator new | `0x002D8F7E` | `0x002EE542` | `FF2540537300` / `FF2580E47400` |
| Generator factory | `0x0010C070` | `0x0011C5C0` | `6AFF684E0E7000` / `6AFF68EE907100` |
| Generator constructor | `0x0010AB70` | `0x0011B0C0` | `6AFF68FB0A7000` / `6AFF689B8D7100` |
| Registry find-or-insert | `0x0010FB70` | `0x001200C0` | `8B54240483EC1053` |

The completion hook preserves all registers and flags, calls the private
registration helper, replays the displaced manager-ready assignment exactly,
and resumes at the next stock instruction. The helper copies the already-live
`NM17` wrapper vtable instead of embedding a private object layout. A missing
stock entry, an existing private owner, an allocation failure, or a constructor
failure is logged and never overwrites another generator.

## Constraints

- Both supported executable profiles must pass every byte guard before any
  runtime modification.
- The extension must remain inside the stock registry lifecycle. Do not replace
  it with a custom randomizer, post-birth renamer, polling thread, or per-hero
  watcher.
- `NM01` through `NM17` remain stock-owned. Every other selected `NM` key must
  be unique and have one non-conflicting four-table definition.
- Each selected generator's four package-owned `HN` resources must be present
  before its custom hero is born.
- The generated MMFR and canonical generic MMCP capability must agree exactly;
  either side without the other stops the manager launch before Majesty resumes.
