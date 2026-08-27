# CAM Manager proof of concept and mod contract

## Outcome

The proof of concept consumes completed Haunt and Alchemist packages without
editing either source repository and emits three validated local profiles:

- `local/poc/final-outputs/haunt-only`
- `local/poc/final-outputs/alchemist-only`
- `local/poc/final-outputs/combined`

Each output is one complete Majesty mod: a top-level MMXML manifest, seven
composed CAM providers, one merged Description document, a compiled BCD, the
compiler-ready GPL/DAT source project, a v1 `mod-definition.json`, and a
fingerprinted `CAM-MERGE-REPORT.json`. The original selected mods must be
disabled while a generated profile is active so their global providers are not
loaded twice. Every generated profile receives a deterministic manager UUID
that is distinct from each selected Workshop UUID, including one-mod profiles.

All three generated profiles use manager-safe custom dialog IDs. Haunt is
migrated from its current standalone `AP07` package to `CGPH`; Alchemist remains
`CGAL`/`CGBR`. This deliberately makes Expanded Building Slots a runtime
prerequisite for every proof profile.

## What a manager-ready Workshop mod must contain

A mod that participates in repeatable composition must be a complete,
independently usable content package. It must ship:

1. Exactly one top-level `.mmxml` with a stable UUID, display metadata, and
   ordered `Dataset`/`Load` directives. Every declared path must be relative,
   remain inside the package, and name an existing file.
2. Every CAM, Description XML, custom art asset, and audio payload used by the
   mod. The manager consumes the finished Workshop package; it must not need
   the author's source repository or unshipped raw assets.
3. A nonempty compiled BCD plus the complete GPL and DAT sources used to build
   it. A compiled-only BCD is acceptable only when it has no semantic collision;
   once two packages define the same function, expression, or data block,
   source is required to resolve and recompile it safely.
4. Complete effective whole-table resources where Majesty requires them, such
   as `BDEP`, `UNTN`, `ACTN`, `QITM`, `AITX`, and `HPTX`. The manager recovers
   each mod's intent by diffing those tables against the installed stock common
   ancestor.
5. Namespaced XML IDs, FourCCs, GPL symbols, IMAG/DSND/WAVE keys, and a unique
   `CGxx` building DialogID. A custom guild supplies matching `SMNU` and `STRT`
   resources and retains the exact stock controller lifecycle declared by its
   controller profile.
6. A v1 `mod-definition.json` whose `mod_id` matches the MMXML UUID and whose
   building records declare `local_name`, `dialog_id`, `controller_base`, and
   `panel_resource_template`.

Numeric private inventory IDs need one additional lifecycle declaration in a
future metadata version: whether each item may be spawned into the world when
its owner dies. Majesty reports every numeric `INVx` key as droppable, so a
unit Description attribute such as `CanDropItem=0` does not control this path.
The POC currently accepts an explicit composition-profile list and extends the
stock `Hero_Drop_Quest_Items` exclusion condition. It fails closed if that
function is not stock-shaped or if a requested exclusion is not a defined GPL
expression. SDK named inventory items do not use this numeric `INVx` path and
must not be added to the condition. The current Alchemist reagent is a named
item (`"AlchemistReagent"`), so the combined profile declares no numeric
death-drop exclusion; the original source packages remain unchanged.

The current completed Workshop packages do not yet include that sidecar. This
POC therefore supplies read-only caller-owned definitions under `profiles/poc`.
Future manager-ready uploads should include the same metadata in their own
package.

## Content that cannot live only in a Workshop mod

There are two separate external dependency classes.

### Player-time runtime

`CGxx` dialogs require Majesty Gold HD: Expanded Building Slots. For the
Alchemist feature set, the player must use its DLL launcher, which starts
Majesty suspended, injects the runtime, and resumes the game. Launching the
Alchemist package directly from ordinary Steam bypasses the CGBR and related
hooks. The current runtime supports the public 1.5.2.24 and beta2 1.5.2.28
executables and refuses unknown fingerprints. Generated CAM profiles also
declare `freestyle-cam-rebind.v1`; this capability repairs the stale IMAG
generation lifecycle through the injected runtime and is undergoing the
Haunt-first Freestyle validation matrix.

The generic reusable capability is intentionally narrow: stock-shaped custom
guild recruit, upgrade, hero-list, and destroy behavior. The following are
Alchemist-specific capabilities, not functionality the CAM manager may infer
for an arbitrary mod:

- the CGBR Brewing secondary controller;
- private AP78 weapon-oil rows;
- the private NM18/HN69-HN72 name generator.

A future metadata version needs a versioned runtime-capability registry before
other mods may request new secondary controls, effect presenters, or name
generators. Until then, unknown runtime behavior fails closed.

### Generation-time tooling

Generating a profile requires this CAM manager utility, an installed Majesty
game as the immutable `Data`/`DataMX` common ancestor, the Majesty SDK source
corpus, and `SDK/Gplbcc.exe`. These are generation inputs, not files that a
generated player profile needs at runtime. RGSeditor is needed to publish or
update a Workshop item, but not to test a generated local profile.

A passive MMXML "utility mod" cannot merge other active mods from inside the
game: registries such as BDEP and whole STRT tables have already resolved to a
single effective provider by then. The practical reusable product is therefore
an external tool, even if its installer/download is distributed through the
Workshop:

`selected Workshop packages -> external generator -> one validated local mod`

The Haunt-only Freestyle proof deliberately does not require Alchemist inputs:

```powershell
.\scripts\Build-Haunt-Freestyle-Poc.ps1
```

## Merge rules implemented in the POC

The composer accepts an ordered sequence of any number of packages and applies
stock-relative N-way rules:

- named CAM registries are unioned by their native four-byte key;
- BDEP is merged by case-sensitive building ID;
- UNTN, ACTN, and HPTX are merged by embedded ID;
- QITM and AITX are merged by positional index;
- XML is indexed by case-sensitive `(type, ID)`;
- GPL functions/expressions and DAT blocks are indexed case-insensitively;
- identical co-owned changes are accepted;
- divergent semantic changes require an explicit resolution;
- explicitly declared non-droppable numeric inventory IDs are added to the
  stock hero-death exclusion condition before its `CanDropInventoryItem` and
  `SpawnUnit` path;
- TILE and SPLT collisions use deterministic allocation and only typed IMAG or
  TILE-palette reference rewriting. Typed building IMAG coverage includes the
  stock set-208 terminal TILE field after the direction records;
- unknown manifest directives, CAM sections, IMAG layouts, direct references,
  and unsupported dataset shapes fail instead of being dropped or guessed.

For the combined proof, Alchemist is intentionally the first art owner, so its
requested main TILE positions stay fixed. With the current committed inputs,
the complete typed Haunt run `17173-17929` is relocated to `17815-18571`; its
interface TILE `2624` is relocated to `2982`. Both mods' SPLT change at `560`
is byte-identical and Alchemist's `854` is unique, so palettes need no
relocation.

The two real GPL conflicts are `Random_Hero_Type` and `spell_extra_value`.
Their explicit resolutions come from the existing Alchemist compatibility
source, which preserves both heroes and the Haunt's conditional Paladin rule.

The generated profile includes the required stock-derived effective whole
tables. Unchanged TILE records remain empty fall-through entries, but SPLT is
different: the working stock-shaped packages materialize its complete effective
palette prefix, and custom externally-paletted TILE records render incorrectly
if those palette records are empty. The manager therefore copies the locally
installed stock SPLT prefix, applies resolved mod palette changes, preserves
the stock positional-section flags, and validates every emitted TILE-to-SPLT
reference. Reports fingerprint the stock files used as the common ancestor and
record that this local materialization occurred. Combined outputs include
packaged custom assets from both selected mods; republishing another author's
assets or locally materialized stock content still requires the relevant
permissions, so generated profiles remain local by default.

## Building and testing

The checked-in convenience command is:

```powershell
.\scripts\Build-Haunt-Alchemist-Poc.ps1
```

The builder refuses an existing profile destination and leaves source packages
untouched. Every output is reparsed, each CAM is round-tripped, positional
section flags and external palette closure are checked, all Description keys
and GPL sources are reparsed, and `Gplbcc.exe` must produce a nonempty BCD. The
JSON report records input, stock, and output SHA-256 fingerprints plus all
allocations and conflict resolutions.

For a live test, copy exactly one generated profile directory into
`Documents\My Games\MajestyHD\Mods`, disable the original Haunt and Alchemist
items, enable only the generated profile, and launch through Expanded Building
Slots. Test one normal Original quest and one Northern Expansion quest for each
profile. Freestyle testing requires the runtime capability declared in the
generated report and must use the injected launcher.

Minimum live checks:

| Profile | Checks |
| --- | --- |
| Haunt-only | Palace gate, construct/recruit/upgrade, reopen and save/reload, Phantom art/audio/spells, Paladin lifecycle, stock AP07/Elf panel still correct. |
| Alchemist-only | All three levels, recruit with NM18 names, CGAL/CGBR reopen, Oil/Phial/Vigor behavior, AP78 rows, Embassy/Outpost behavior, stock AP10/Fervus still correct. |
| Combined | Both build entries, repeatedly alternate CGPH/CGAL/CGBR, recruit both heroes, verify both art/audio sets and both BDEP rules, exercise the resolved Embassy/Outpost/Paladin flow, kill an Alchemist carrying one or more Monster Reagents and verify the game remains responsive, save/reload. |

## Current scope limits

- Dataset bases other than `Any`, multiple behavioral variants, and quest-mod
  binding are not yet composed.
- Freestyle custom-CAM loading is experimental under
  `freestyle-cam-rebind.v1`; only completed profile/build combinations from the
  live matrix may be described as supported.
- v1 metadata cannot declare arbitrary runtime hooks.
- A novel positional reference shape must first be traced to a stock mechanism
  and added as a typed parser; blind byte scanning is prohibited.
- Divergent GPL/XML/table changes without an explicit resolution stop the
  build.
