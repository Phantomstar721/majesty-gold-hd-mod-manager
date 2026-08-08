# Majesty Script Merger Review

Reviewed Workshop item `3772146427`, **Majesty Script Merger v1.0**, from the
local Steam Workshop installation. The item includes its executable, CLI, full
C# source, and a README. It does not include an explicit software license, so
its implementation should be treated as research material unless its author
grants permission to reuse code.

## What it actually does

This is a genuine semantic script merger rather than a file concatenator. It:

- discovers Workshop, local-mod, and local-quest manifests;
- indexes GPL functions, GPL expressions, named DAT blocks, and XML
  `Description` entries by semantic name or ID;
- builds a vanilla comparison corpus from both SDK rulesets;
- performs line-based three-way merges against vanilla;
- folds any number of mods in a user-specified load order;
- presents overlapping regions for manual resolution;
- emits a load-last local patch without modifying source mods; and
- compiles the generated GPL with `Gplbcc.exe`, checking the output because the
  compiler can return success even when compilation failed.

Its quest support is deliberately report-only because a normal load-last mod
cannot override a quest's own bindings reliably.

## Patterns worth adopting

1. Compare semantic records, not source filenames. Mod authors organize files
   differently, but function names and description IDs express actual runtime
   ownership.
2. Use the SDK data as the common ancestor. This separates two independent
   stock edits from a genuine same-line conflict.
3. Fold mods in explicit load order and retain a manual conflict editor.
4. Generate a separate local output package. Never mutate Workshop content.
5. Validate the generated semantic item and run the real compiler before
   presenting a merge as successful.
6. Offer both a GUI workflow and a reproducible CLI/report surface.

## What it does not solve

- CAM archives are only reported. Their sections, entries, tables, palettes,
  image references, dialog resources, and sound resources are not merged.
- Multiple `<Strings>` tables are reported as last-one-wins rather than merged.
- It does not allocate or rewrite colliding four-character resource IDs.
- It has no custom-building declaration or controller registry.
- It asks the user to reproduce the game's load order manually instead of
  reading and managing an active profile.
- Compiled-only BCD mods cannot be text-merged.
- A line-clean merge can still contain a semantic conflict elsewhere; its own
  README correctly warns about this.
- Generated patch UUIDs are random on every emission. Our manager needs stable
  profile and package identities so regeneration does not appear as a new mod
  or destabilize persisted mappings.
- Output is written directly into the destination folder rather than built and
  validated in staging before an atomic replacement.

## Relationship to the planned manager

The proposed application is a superset rather than a duplicate:

```text
Installed/selected mods
        |
        +-- GPL/DAT/XML semantic merge
        +-- CAM entry and whole-table merge
        +-- resource namespace allocation + reference rewriting
        +-- custom-building controller declarations
        +-- dependency/conflict/profile resolution
        |
        v
Validated generated mod package + controller registry
        |
        v
Runtime DLL dispatches allocated building IDs to requested stock controllers
```

The Script Merger is strong evidence that the GPL/DAT/XML portion is tractable
and that a load-last generated patch is a practical delivery model. We should
either interoperate with it or ask its author about collaboration/licensing
before considering direct source reuse.
