# Majesty Gold HD CAM Merger

Tooling to make two or more Majesty Gold HD CAM mods work together, built on a
container layer that already unpacks and repacks CAM archives byte-for-byte.

The live Majesty install should stay a reference and test target. This repo keeps code,
synthetic test fixtures, and documentation only. Do not commit proprietary game assets.

## Status: working Haunt + Alchemist proof of concept

The container layer and the first real merge pipeline now work. The tool safely
ingests completed packages and v1 definitions, performs stock-relative N-way
table/XML/GPL merges, compiles one BCD, and relocates positional art only through
typed reference maps. It generates Haunt-only, Alchemist-only, and combined
profiles without editing either source mod.

See [the POC contract and test guide](docs/poc-mod-contract.md) for package
requirements, the external Expanded Building Slots/runtime boundary, current
scope limits, and the live test matrix.

## Why merging, and not a slot convention

An obvious alternative is to publish a slot registry and ask mod authors to
claim `TILE`/`SPLT` ranges. It was considered and rejected. A convention only
binds mods written afterwards by authors who find and follow it, which is not a
lever anyone in this community actually holds. Mods that already exist, and
mods by authors who never read this repo, still have to be reconciled.

So the tool has to take arbitrary mods as they are, report the clashes it finds,
and offer resolutions. Prevention is not available.

## Design: a three-way merge

The stock CAM is the common ancestor, so this is `base = stock`, plus one side
per mod, with the usual three-way semantics and the usual failure modes. Most
"conflicts" in practice are an artifact of the format forcing a mod to ship a
whole table when it meant to add a few rows; diffing each side against stock
recovers the intent mechanically.

| Conflict class | Why it happens | Automatable |
| --- | --- | --- |
| Disjoint entries (`PH*` vs `MK*`) | Different names, no real conflict | Yes, union |
| `BDEP` | Engine takes one complete table, does not merge tables | Yes, combine deltas against stock |
| `UNTN`, `ACTN`, `QITM`, `AITX`, `HPTX` | Whole tables, load order wins | Yes, same delta approach |
| `TILE` / `SPLT` | Global numeric slots, mods pick overlapping ones | Hard, needs renumbering and reference rewriting |
| `SMNU/AP07` and other recruit dialogs | Exe-keyed stock controller dispatch | Yes, with allocated IDs plus the runtime controller registry |
| Replaced stock GPL functions | Two mods rewrite the same behavior | Sometimes: vanilla-aware three-way merge plus manual resolution |

### The two that require higher-level support

A recruit-dialog clash is resource contention, not just a data conflict.
Runtime testing in the Expanded Building Slots project proved that a custom
dialog ID can retain its own CAM resources while using a stock controller and
without displacing the stock building. The production design therefore assigns
stable internal IDs during the merge and emits a registry mapping each ID to
the controller archetype declared by the mod author.

Overlapping GPL replacements are code merge conflicts. The reviewed Workshop
Majesty Script Merger demonstrates a useful vanilla-aware three-way approach:
merge non-overlapping edits automatically, validate and compile the result, and
present genuine overlap regions for an explicit user decision.

See [the local Majesty Script Merger review](docs/majesty-script-merger-review.md)
for the reusable concepts, limitations, and relationship to the planned
manager.

### The hazard in renumbering

Reassigning a `TILE` slot is only safe with a complete map of references to it,
and references are not all in one place. In the Phantoms Haunt work, cloning
AP10 under AP07 and searching for the old tile `466` missed frames that
referenced `474` and `495`, because raw-texture animation-set IDs were also
embedded inside the selected `SMNU`. Incomplete reference discovery silently
corrupts art rather than failing loudly, which is the worst failure shape for a
merge tool. Renumbering should be last, behind detection and the table merges.

## Suggested order of work

1. Detect. Unpack each mod, diff against stock, report additions and
   modifications per section, and flag overlaps. No semantic understanding of
   any record type required, and it answers the question authors actually ask.
2. Merge the whole-table types via deltas against stock.
3. Report the unmergeable classes with concrete resolution options.
4. Only then attempt `TILE`/`SPLT` renumbering, gated on a reference map that
   can be shown to be complete.

## Container layer (working today)

`0.2.0` captures the first in-game audio discovery pass. See
`docs/handoff-0.2.0.md` for the resume summary, confirmed findings, and next steps.

The container goals below are met and remain the foundation for the merge work:

- Inspect CAM archives without modifying them.
- Unpack CAM archives into an editable directory plus an order-preserving index.
- Repack directories back into valid CAM archives.

## Current Commands

```powershell
python -m majesty_cam.cli list path\to\archive.cam
python -m majesty_cam.cli verify path\to\archive.cam
python -m majesty_cam.cli unpack path\to\archive.cam local\unpacked
python -m majesty_cam.cli pack local\unpacked local\repacked.cam
python -m majesty_cam.cli poc-build --game-path "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD" --input-root local\poc\inputs --output-root local\poc\outputs
```

`unpack` requires a new or empty destination so files left by an older archive
cannot be mistaken for current output. To intentionally retain existing files,
pass `--allow-nonempty`; the tool warns that unrelated files will remain. It
never cleans a destination automatically.

For the checked-in Haunt/Alchemist fixture layout, the equivalent convenience
command is:

```powershell
.\scripts\Build-Haunt-Alchemist-Poc.ps1
```

Generated packages and proprietary inputs remain under ignored `local/` paths.
The public `compose_package(...)` API accepts an ordered sequence of any number
of packages; unresolved conflicts and unsupported binary shapes fail closed.

## Local Setup

Tests run directly from a fresh checkout without installing the package:

```powershell
python -m unittest discover -s tests
```

For an isolated editable install and the `majesty-cam` command:

```powershell
cd C:\Users\bterr\source\repos\majesty-gold-hd-cam-merger
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m unittest discover -s tests
```

## Local Game Data

Use `local/` for anything copied from the game install while testing. It is ignored by
git on purpose.

Useful paths on this machine:

- SDK: `C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK`
- SDK example CAMs: `C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Example\Data`

## Reference Repos

Use `reference-repos/` for shallow clones of public research/tooling repos. It is also
ignored by git so third-party code and game data are not accidentally bundled.
