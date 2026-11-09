# Paired accuracy source integration review

The Manager now has a reusable offline source composer in
`src/majesty_cam/paired_accuracy.py`. It is not a registered runtime feature.
It accepts bounded private marker/helper symbols and both stock stat functions,
uses the existing structural merger, and preserves all unrelated instructions.
Original and Expansion output is recorded under `artifacts/paired-accuracy-integration`.

Unlike the supplied prototype, this composer compares the entire stock accuracy
branch: mode, attribute, cap/floor and +/-1 adjustment. A changed branch rejects.
It also checks the composed output and prevents another provider from replacing
the reserved Manager merge side. Missing/duplicate functions, symbol collisions
and partial up/down pairs reject. Independent edits outside the accuracy branches
still compose normally. The result explicitly has `runtime_ready=False`.

The source change gives both skills the existing stock increment/decrement once;
it does not append a second award to the active weapon. It retains the nested
HasAttribute check for the private marker. Source composition is not a ledger
transaction or a save/load integration.

## Review of the supplied persistence prototype

The prototype correctly distinguishes an owned contribution from a total-stat
snapshot and recognizes that capped gain followed by loss is not reversible.
Its `Host` supplies the missing decomposition by assumption. There is no native
projection implementation behind `atomic_replace_owned`.

Two concrete validation issues were reproduced without changing its repository:
`transition(-1, (60,65), (59,64), 0)` accepts level zero, although restore rejects
it; `transition(True, (60,65), (61,66), 2)` accepts a boolean direction. Contribution
and sequence integers also have no declared representable bound. That ledger has
not been adopted as a production saved-state implementation. The source prototype
also permits replacing its own `witch-dual` merge side and only pattern-matches
the beginning of an accuracy branch; the Manager composer closes those two
source-integration gaps.

## Current integration direction after handoff

The accepted direction is ordinary stock `AdjustAttribute` calls at the existing
gain/loss decision points. Loading a save must not replay those adjustments,
replace the actor's total stats, or reconstruct a separate contribution ledger.
The earlier owned-stat replacement proposal above is historical prototype review,
not a required adapter for this design.

The remaining verification is narrower: establish that the native accuracy
values and private identity survive save/load, and that no integration callback
awards them again. Exercise direct advancement, draining, alternating weapon
modes, cap/floor behavior, and unrelated training or temporary modifiers. Cover
both script datasets and all three supported executable profiles before enabling
the feature. Source composition alone does not establish that lifecycle.

Do not infer historical missing gains or retrofit old heroes from their current
level. Any retroactive migration requires a separate explicit policy. No new
persistence capability is enabled; the offline composer remains unregistered,
and frozen V28 remains unchanged.

## Owning-thread continuation, 2026-10-04

`compose_source` now emits a complete source file, preserving every unrelated
source span. The stock compiler exposed a missing `declare` in the proposed
helper; this is corrected. Complete-file regression coverage also prevents
joining one function's `end` to the next declaration.

Compiling the actual Expansion progression code exposed a shared lexer defect:
leading decimals such as stock `.9` were rendered as `. 9`. The structural merger
now preserves that numeric token, with a regression. This correction is included in Manager 0.3.11. The v0.3.9 checkpoint
below is historical evidence, not the current release boundary.

`scripts/verify_paired_accuracy_source.py` uses the installed stock compiler and
both GPL/GPLMx progression sources without preparing a profile. The current
Witch-marker output is in `local/witch-paired-source-20261004`, with source and
compiled hashes in `evidence.json`. The marker is the existing `WHP_Prototype`;
no consumer source, package or frozen snapshot was modified. These compiler
artifacts do not establish native save/load acceptance or enable a production
recipe. The public-interface diagnostic source was also corrected to include
required declarations and compiled separately under
`local/witch-public-api-probes-20261004`.
