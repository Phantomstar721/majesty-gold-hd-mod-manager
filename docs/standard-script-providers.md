# Standard script providers

Selected Standard mods keep their native load order and provide their own
scripts when the Manager integrates shared features. Generated output uses
common `Any` content plus optional native original/expansion script patches.
See the [scoped-output design](mod-dataset-scope-plan.md) for scope and
validation details. Individual mod combinations still need in-game testing.

## Generic source registration

Standard script overlap checks compare GPL/DAT tokens, ignoring comments,
formatting and identifier case. Quoted values, operators and instruction order
remain significant. Identical instructions do not require a load-order winner.
This check reuses the cached scan; it does not compile scripts or add selection-time
file reads. XML description comparisons remain unchanged.

The conflict preview reuses this inventory and the same native Standard ordering
routine used by Prepare. It reports last providers per definition across all
selected Standards, separately for the original and expansion datasets. It does
not merge scripts or apply a new precedence policy. Unknown effects retain an
explicit fallback label; routine labels never claim particular damage formulas.
Literal numeric expressions are recorded while tokenizing, without evaluating
expressions or rereading files. Original/expansion scope follows the stock first
Dataset rule, consistently across the three supported executable profiles.
The preview cannot prove hidden compiled behavior or predict later generated
Merge adjustments. A cyclic order has no reported final provider, and unresolved
multi-mod choices are shown as provisional instead of silently resolved.

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

### Shared declarations for Standard variants

When one package ships multiple Standard Mod components with the same private
hero trees, its schema-v3 `mod-definition.json` may use `mod_ids` **instead of**
`mod_id`:

```json
{
  "schema_version": 3,
  "mod_ids": [
    "{11111111-1111-1111-1111-111111111111}",
    "{22222222-2222-2222-2222-222222222222}"
  ],
  "internal_name": "SharedHeroDeclarations",
  "display_name": "Shared hero declarations",
  "custom_buildings": [],
  "runtime_features": [
    {
      "type": "stock.hero-quest-participant.v1",
      "feature_key": "support-hero-quests",
      "hero_script": "Private_Support_Tree",
      "stock_hero_script": "mx_healer"
    }
  ]
}
```

Replace the example IDs with each covered component's manifest Mod ID. List each
UUID once; letter case and surrounding braces do not distinguish IDs. Add one
feature record per private hero tree. All listed variants share those records.

Only the selected component's native sources and compiled target are used. The
list does not enable other variants, borrow their trees, or change load order.
Each selected component must itself supply the declared trees and retain the
verified stock decision points. A selected ID missing from the list produces an
explicit error rather than silently losing quest participation.

This shared form is limited to Standard schema-v3 hero-participant declarations
with empty `custom_buildings`. It does not apply to Merge definitions. Existing
single-`mod_id` definitions remain supported. No automatic tree discovery or
additional in-game processing is introduced. The same source-only behavior
applies to all supported Steam and GOG executable profiles.

## Native script ownership

The selected Standard order determines the effective native definition. Only
definitions touched by the generated profile participate in reconciliation:

- A generated stock fallback yields to the native replacement without emitting
  an unnecessary duplicate.
- Independent edits combine through the existing instruction merger.
- Competing edits join the consolidated script review instead of selecting stock.
- Unrelated Standard scripts, descriptions, artwork and other assets stay native.

For overlapping inputs, the installed compiler must reproduce the declared BCD.
A filename-only compiler probe identifies diagnostic filename positions. Only
those proven fields and their exact envelope-size adjustment are normalized;
instruction bytes, operands, strings and line numbers are not discarded. A
compiled-only provider is indexed from its native declaration tables during
composition, using the already captured BCD bytes. Functions, expressions,
prototypes and DAT records are distinguished from references to other scripts.
Unrelated compiled-only files remain native without source registration. A real
overlap names the exact provider, target and definition requiring matching source;
it does not claim the two behaviors are irreconcilable. Unsupported or damaged
tables remain explicitly unknown. A later native winner can make earlier opaque
input irrelevant, including separate GPL targets within one package. Only a
winning source-backed target needs compiler proof. See the
[all-version BCD trace](stock-bcd-ownership.md).
Proofs and parsed inputs use bounded process-local caches
invalidated by declared inputs and compiler identity. Nothing polls during play.
Source parsing is lazy per winning compiled block. Known base/expansion
availability uses those same compiled definition indexes, including source-less
native inputs; unrelated source cannot create or erase runtime ownership.

Standard source/target/declaration identities and selected order participate in
the prepared-plan fingerprint and are rechecked before publication. Checkbox and
conflict-winner updates refresh the provider snapshot without rerunning Merge
preflight. Selection snapshotting does not parse GPL or run the compiler.

Authored script changes are reconciled before generated callbacks and subsequent
discovery/auditing. Those operations receive effective native fallback functions;
the actual result undergoes final checks and unused native copies are pruned.
Dataset dependency closure does not re-import stock over a proven native helper.
Authored Standard/Merge comparisons share the same SDK source ancestry used by
the instruction merger, while native defaults continue to use the destination
dataset's stock. Ordered, short-circuit decision checks can combine an explicit
priority change with independently anchored edits; competing orders and uncertain
anchors remain conflicts. See [decision-chain reconciliation](stock-decision-chain-merge.md).
Equivalent `else` and fall-through layouts after a proven unconditional return
also compare consistently, without suppressing real removal-versus-edit conflicts.

Automatic reconciliation compares a Merge result with the effective Standard
owner. If that cannot be combined safely, the choice names the actual authored
mods, never a synthetic "Combined Merge mods" entry. One preference per mod pair
applies to every unresolved overlap in original and expansion quests. A preferred
mod supplies its conflicting definition; independently compatible contributions
from other mods are then retained through the existing merger. Safe results
elsewhere remain combined. Authored compatibility definitions retain their real
participant provenance at this boundary instead of being replaced by the original
unresolved sources. Selected-owner rules expose only their accepted winner.
An indivisible multi-mod compatibility definition must win or lose consistently
against an outside mod; preferences cannot silently split it apart.
Source/bytecode mismatch and missing ownership
evidence are not selectable overrides. Generated callbacks, scope checks,
compilation and final validation run after decisions. See
[script conflict review](script-conflict-review.md).

## Native dataset boundary

Do not flatten `MajestyExpansion` scripts into the generated `Any` profile.
Do not assume extra Dataset siblings are selected by the game. Static inspection
of beta2's mod type reader at VA `0x4FA050` and source-resource enumerator at
`0x4FF140` shows index-zero Dataset reads (`0x4FA084` / `0x4FF1A9`), not a proven
conditional multi-Dataset dispatch. The experimental sibling-output path was
removed before packaging.

The implementation uses one managed output bundle with shared content and
optional native scoped patch records, not a copied Standard mod or a runtime
dispatcher. Static all-version evidence is recorded in the scope plan. Generated
records share artwork, descriptions and runtime registries. Native selection may
show the script patches individually; the Manager groups them as one prepared
selection and activates Standard IDs, common output, then scoped patches.
No base/expansion transition or save/load playtest is claimed yet.
