# Standard script providers — unshipped design draft

This work is not packaged for testing and is not release-ready. The defects in the
[initial review](standard-script-provider-review.md) have been corrected in source
as described in its follow-up. Scoped GPL composition can be evaluated separately,
but publication still produces one `Any` Mod; a differing base/expansion script
now reports the exact conflicting symbol instead of flattening it. See the
[scoped-output recommendation](mod-dataset-scope-plan.md) for the remaining design.

## Generic source registration

A Standard mod remains independently enabled and classified as Standard. Its
normal `.mmxml` GPL `Target` and ordered `Source` children register the editable
source. No dummy CAM, per-behavior replacement table, or conversion to Merge is
required. This path uses explicit manifest sources, not recursive project-file
discovery. The older loader's project-recovery option is not used by the new
selection/Prepare integration.

An optional matching `mod-definition.json` can declare
`stock.hero-quest-participant.v1` for private hero trees. Replacements of stock
trees need no participant declaration. Other Standard-side runtime declarations
are not silently accepted by this source-only integration.

The selected Standard order determines the effective native definition. Only
definitions touched by the generated profile participate in reconciliation:

- A generated stock fallback yields to the native replacement without emitting
  an unnecessary duplicate.
- Independent edits combine through the existing instruction merger.
- Competing edits report the provider and function instead of selecting stock.
- Unrelated Standard scripts, descriptions, artwork and other assets stay native.

For overlapping inputs, the installed compiler must reproduce the declared BCD.
A filename-only compiler probe identifies diagnostic filename positions. Only
those proven fields and their exact envelope-size adjustment are normalized;
instruction bytes, operands, strings and line numbers are not discarded. A
compiled-only provider is not rejected merely for being selected. If composition
needs a definition it may own, missing source evidence is reported as unknown
ownership, not a confirmed conflict. A later known native winner can make earlier
opaque input irrelevant. Proofs and parsed inputs use bounded process-local caches
invalidated by declared inputs and compiler identity. Nothing polls during play.

Standard source/target/declaration identities and selected order participate in
the prepared-plan fingerprint and are rechecked before publication. Checkbox and
conflict-winner updates refresh the provider snapshot without rerunning Merge
preflight. Selection snapshotting does not parse GPL or run the compiler.

Authored script changes are reconciled before generated callbacks and subsequent
discovery/auditing. Those operations receive effective native fallback functions;
the actual result undergoes final checks and unused native copies are pruned.
Dataset dependency closure does not re-import stock over a proven native helper.

## Remaining dataset boundary

Do not flatten `MajestyExpansion` scripts into the generated `Any` profile.
Do not assume extra Dataset siblings are selected by the game. Static inspection
of beta2's mod type reader at VA `0x4FA050` and source-resource enumerator at
`0x4FF140` shows index-zero Dataset reads (`0x4FA084` / `0x4FF1A9`), not a proven
conditional multi-Dataset dispatch. The experimental sibling-output path was
removed before packaging.

The recommended design is one managed output bundle with shared content and
optional native scoped patch records, not a copied Standard mod or a runtime
dispatcher. The recommendation and static all-version evidence are recorded in
the scope plan. Publishing those records is not implemented or playtested yet.
