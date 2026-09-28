# Private stock-derived hero integration

These optional schema-v3 recipes are package-owned source composition. They
add no DLL hooks, runtime registry, polling, timers or replacement AI.

## Quest participation

Use one declaration per private tree:

Standard packages with multiple components can share these declarations through
an explicit `mod_ids` list in their definition file. See the
[shared Standard declaration example](standard-script-providers.md#shared-declarations-for-standard-variants).

```json
{
  "type": "stock.hero-quest-participant.v1",
  "feature_key": "support-quests",
  "hero_script": "Example_Support_Tree",
  "stock_hero_script": "mx_healer"
}
```

The analogue may be any of the 16 supported stock `mx_` hero trees. It selects
which `stock.hero-quest-lifecycle.v1` providers apply and which continuation
anchor to use. The private tree must be one package-owned `(agent ThisAgent)`
function, not a stock function under its original name.

Stock references are the installed SDK's `GPLMx/DecisionTrees/mx_*.gpl`,
`mx_LowLevel.gpl` and `mx_Hero_Deaths.gpl`. The lifecycle remains:

1. `Check_Nearby` declines, provider resume, then unchanged `Check_rewards`.
2. `Pursue_Entertainment` declines, then provider consideration. Healer/Monk
   instead continue after `Purchase_Bazaar(ThisAgent,70)` because their stock
   trees omit entertainment. Earlier private guards and later work stay intact.
3. Existing shared reset callbacks run before movement/target/task reset;
   death callbacks run after `DeleteAllEffectors`, before `IGDeathScript`.
   Participants do not duplicate those callbacks or create separate cleanup.

A TRUE provider callback short-circuits the remaining stock decision cascade.
Missing, duplicated or reordered anchors fail with the private tree's name.
These anchors are verified as parsed decision branches, not adjacent lines:
explicit `begin/end`, comments and source formatting do not change eligibility.
The nearby decision's false-result continuation must contain the rewards check
as its sole immediate child. Consideration must remain beneath that rewards
check on the same conditional path, not in a sibling, loop or `else` branch.
Callbacks guard the complete existing continuation; original instructions,
comments, enclosing branches and `else` ownership remain intact. The original
Healer/Monk continuation gaps use the same structural checks.
Reset and death anchors likewise use statement boundaries, not line breaks.
Reset callbacks precede the original entry sequence; death callbacks run before
the existing top-level death dispatch and after the original cleanup and any
intervening mod work. Conditional, missing, repeated or reversed cleanup anchors
are not treated as formatting differences. Original-game stock functions retain
their audited target-reset and death-dispatch boundaries without adding expansion
cleanup behavior.
Without a selected provider for that analogue, the tree remains unchanged and
has no dependency on any provider's symbols. Stock dispatch still owns timing;
there is no Manager per-tick scan.

## Renamed spell evaluation

Stock `GPLMx/DecisionTrees/Modules/mx_target_eval.gpl::spell_extra_value` sums
mode-1 `IsSpellAvailable` checks into a local `value` and returns it to combat
evaluation. Its stock spell-name checks do not recognize renamed clones.

```json
{
  "type": "stock.spell-evaluation-equivalent.v1",
  "feature_key": "private-note-evaluation",
  "private_spell": "Example_Arcane_Note",
  "stock_spell": "energy_blast",
  "hero_title": "Example_Caster"
}
```

The private Action and Character Description must belong to the declaring
package. `hero_title` is the Character's internal Description name, not its
localized display text. The installed stock helper supplies weight and mode;
authors do not repeat either. Any spell already in that helper can be an
analogue, including energy_blast (+10) and sun_scorch (+30).

The Manager first composes the shared helper, then adds the cloned availability
and value instruction scoped to that hero title before its final return.
Other mods' instructions remain intact. An unsupported stock clause, changed
signature/local, extra return or already-authored private spell clause fails
explicitly rather than guessing or double-counting. This remains a synchronous
stock calculation with no retained state, callback, cancellation or cleanup.
Spell casting and its effect lifecycle are unchanged.
