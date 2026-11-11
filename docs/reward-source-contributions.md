# Declared reward-selection contributions

2026-11-10. Human design approval: "Yes, implement declared reward contributions".
This is source composition, not a runtime service or a new bounty implementation.

Add optional `source_contributions` to schema2/3 component metadata. It is separate
from `runtime_features`, does not change Standard/Merge classification or Dataset,
and is inactive in standalone/Classic gameplay. The standalone compiled mod still
supplies its normal complete `check_rewards` function.

```json
{
  "source_contributions": [{
    "type": "stock.reward-selection.v1",
    "feature_key": "guild.reward-policy",
    "callbacks": {
      "flag_eligible": "Guild_FlagEligible",
      "flag_priority": "Guild_FlagPrioritized"
    },
    "priority_multiplier": 2
  }]
}
```

| Optional phase | Exact GPL signature/result | Meaning |
| --- | --- | --- |
| flag_eligible | (agent Hero, agent Flag) is boolean | False vetoes the flag; bonuses/priority cannot undo it. |
| attack_distance | (agent Hero, agent Target) is integer | Positive alternate travel distance, <=0 declines. Cached once per provider/distinct valid nonself attack target per invocation; least positive distance wins, stock floor100 remains. |
| target_evaluation | (agent Hero, agent Target, integer StockValue, integer TravelValue) is integer | Modify the one stock target_eval result. TravelValue is this provider's cached distance, otherwise0. Overlapping replacements need a preferred provider. |
| flag_incentive | (agent Hero, agent Flag, agent Target, integer Score, integer TravelValue) is integer | Add this bonus after stock penalties for a valid attack candidate; the provider owns further eligibility. |
| flag_priority | (agent Hero, agent Flag) is boolean | Apply the declared positive integer priority_multiplier after incentives. |
| extra_candidates | (agent Hero) is list | Ordered list of possible extra lair targets, evaluated after flags. |
| extra_eligible | (agent Hero, agent Target) is boolean | Eligibility for that extra target; retain effect expiry/hostility and other provider rules. |
| extra_score | (agent Hero, agent Target, integer TravelValue) is integer | Extra candidate score; strict ties keep the earlier stock flag/provider candidate. |

Callbacks are package-owned, uniquely named, synchronous read-only queries.
Signatures/source ownership do not prove purity; this is an author contract, not
an inferred property of arbitrary GPL. No callback may re-enter check_rewards,
pay gold, create flags, retask units or mutate the selection ledger. No continuous
observer, all-unit/order scan or new timer belongs in this contract.

The three extra callbacks must be declared together with
`"extra_dispatch": "stock.raid_lair"` and an explicit
`"suppress_player_attack_flags": true`, false, or `"eligible"`. Dispatch accepts valid, live,
nonself lairs and literally clones stock raid_lair's Attack_object / Target /
Intent_Raiding handoff. Existing visible positive own-player attack flags suppress
an extra candidate in legacy `true` mode, even if a separate membership policy
vetoes that flag. Opt-in `"eligible"` mode suppresses only flags admitted by all
declared flag-eligibility predicates for this hero. Those predicates run once
in the original flag pass; extra targets reuse its admitted-flag list. Thus a
nonmember may pursue an independently eligible extra target without enrolling
in or collecting the restricted flag. Admitted ordinary flags retain stock
dispatch and suppress duplicate extra pursuit of that same target. `false`
disables suppression. There is no flag parent, heroes-list append, payout or debit for extras.
The stock no_attack argument suppresses these attack candidates but retains the
original guard dispatch. Stock flag dispatch/payout code is unchanged.

Contributions run in stable (mod UUID, feature_key) order within a phase, with
eligibility before incentives and priority. Integer operations are not reassociated.
Native overflow/query/payout semantics are not newly proved by source composition.

## Standalone source and conflict handling

`reward_contributions.render(stock_check_rewards, ((owner_uuid, contribution), ...),
stock_raid_lair)` emits the standalone selector from the destination stock source.
Keep that emitted GPL in the author's source/project and compile the ordinary
standalone package normally. This pure helper does not build a Manager profile.
Owner UUID braces/case are normalized by the helper. Parameter and bound-local
spellings/comments/formatting may differ; the complete current bound-local AST must
match that package's declared expansion for its edits to combine automatically.
Unaccounted edits remain normal preferred-mod conflicts. Choosing one provider
retains its exact complete authored function; no losing contribution is reinserted.
No whole-source hash pin or mod-specific symbol rule is used.

Native Standard source proof and Dataset scope remain authoritative. Declare only
the phases the package owns, and provide matching source for the loaded compiled
function and helpers. Source metadata alone cannot certify an opaque BCD.

## Existing consumer migration

The guild flag owner supplies flag_eligible (unmarked=True; marked uses its existing
home/title/kingdom membership rules) and flag_priority (its mark predicate for
every marked title, including guard), with multiplier2. Keep its original Flag_Score helper and payout uses
unchanged or make them call the same helpers with identical standalone results.

The travel/incentive owner supplies attack_distance, target_evaluation,
flag_incentive and the three extra callbacks. Reuse current reachability and
scoring; target_evaluation receives the already-computed stock value instead of
calling target_eval again. TravelValue>0 replaces a duplicated reachability query.
Keep existing Breach expiry, one500-gold cast debit, declared player-flag suppression,
Dawnfall range/cooldown and saved state. No actual bounty is created.

Primary evidence: KG f2644580d33ad98703361cd8fc88c825068161ef,
script_function.check_rewards and mechanic.heroai; research shared-map and
reward-selection-source-pair-20261012.md; installed Base/MX check_rewards and
raid_lair GPL. Existing native restrictions/qualifications remain unchanged.

## Implementation evidence and limits

The production source-review path handles declared Merge and Standard sources
together, respecting each Standard component's Dataset. The actual two consumer
candidates retain their standalone compiled/source proofs. Source-only fixtures
exercise Public, beta2 and GOG stock pairs and compile with the installed Steam
and GOG SDK compilers. Current receipts are private under
`local/reward-contributions/actual-candidates/receipt.json`; reproduce with
`scripts/verify_reward_contribution_candidates.py --merge-root <merge candidate>
--native-root <standard candidate> --work local/reward-contributions/<case>`.

The same fixture executes the actual adapters for missing/wrong/dead/foreign
membership, marked guard priority, raw player-flag suppression, repeated targets,
expired effects and ready/unready travel. World/native eligibility queries are
explicit doubles; this does not establish in-game movement, native integer
overflow, save/load or payout acceptance. Separate generic regressions retain
each preferred whole function exactly and reject real behavior edits despite
permitting harmless parameter/local renaming.

The current independent-incentive candidate uses `"eligible"` suppression:
membership-vetoed attack flags do not suppress its separate lair candidate.
The veto remains binding on flag dispatch, enrollment and payout. Ordinary
admitted attack flags retain stock dispatch; no duplicate incentive dispatch
is added. Legacy Boolean declarations preserve their previous raw-flag behavior.

Plan schema29 prevents reuse of an earlier prepared result with the same inputs
but older generated selector/activity logic. Source-development cache identities
include both generators; packaged cache identity remains the application itself.
No extra recursive scan or per-unit observer was added.

## Automatic terminal-factor inference

Manager 0.3.14 beta can also combine an unchanged Standard selector without
an author contribution declaration. This is a bounded source proof, not a
general guess about a function's effects. The complete caller must reduce to
the destination stock selector by removing exactly one conditional helper call
immediately before the original score debug/winner comparison. Parameter/local
renaming is allowed; other caller edits are not silently discarded.

The helper must take hero, flag and score, perform only score-independent
read-only guards or definitely assigned local aliases, and finish with the
original `score * positive_literal_factor` product. An explicit early zero
return is an eligibility veto. A zero numeric stock score is not a veto and can
still receive an independently declared incentive. The factor and marker are
evaluated once per original flag, before incentives and the original ordered
multiplication. The helper is cloned with its local agent/reference boundary
intact, its proven compiler-project constant resolved to its literal value, and
its final returned value changed to the factor. No division,
reassociated arithmetic, repeated predicate or copied global state is used.

Only the documented stock SDK queries HasAttribute(string,agent),
IsValidGamePiece(agent), and GetUnitPlayerNumber(agent) are admitted in this
proof grammar. The primary source is installed SDK `GPL Reference.pdf`,
pages5/27/28/32, SHA256
`41587f35790d332afebf8395189053125eec0c6b148cdc282e43f805d34750b6`.
The existence/required-read distinction additionally uses the already guarded
three-profile saved-attribute contract in `docs/saved-attribute-row-contract.md`.
These are bounded API/source contracts, not newly recovered complete native
query handlers. Any selected compiled GPL owner of a query name disqualifies
inference, including opaque or apparently identical replacements. The loaded
helper and multiplier must have unambiguous effective compiled ownership and
their original full project source must reproduce the loaded BCD.

The inference module recognizes no mod ID, author, private symbol or property
name. Unsupported shapes, side effects, unknown calls, score-dependent tests,
changed caller instructions and selected helper/constant/query overrides decline
the proof. They retain the normal whole-function preferred-mod path. Selecting
one complete authored body does not reinsert a losing inferred helper; a native
winner remains in its original Standard BCD instead of being duplicated.

Source evidence consulted: KG commit
`f2644580d33ad98703361cd8fc88c825068161ef`, nodes
`script_function.check_rewards`, `mechanic.heroai`,
`engine_function.hasattribute`, `engine_function.isvalidgamepiece`, and
`engine_function.getunitplayernumber`, retaining their evidence/source limits;
research shared-map checkpoint21449 and
`reward-selection-source-pair-20261012.md`; destination Base/MX stock selector
and raid_lair source; SDK reference above. No new native research or excluded
actor/callback/cleanup mapping was performed.

The actual frozen unchanged package and current declared consumer are checked
through production `merge_gpl_resources`, then isolated language compilation for
Public, beta2 and GOG. Private receipts are in
`local/reward-contributions/unchanged-alpha`; the checker binds all nine unchanged
candidate files, the declared consumer input set, current implementation, and
the three executable fixture identities. Reversed actual review candidates and
both exact whole-body fallbacks are included. Source-level behavior fixtures
use explicit world/query doubles; they do not prove native movement, payout,
integer-overflow behavior or save/load acceptance.

`scripts/Build-RewardFactorAlpha.ps1` packages the candidate under
`dist/reward-factor-alpha` using the existing alpha native payload unchanged.
It does not replace the beta or existing working alpha app. The candidate uses
the existing alpha settings/private game executable/output when the player
chooses to run it; the player performs Prepare. That alpha received player
acceptance for the reported combination. The same adapter is promoted to beta
0.3.14 with its plan fingerprint marker, while the newer Standard-only and XML
corrections are retained. No Manager profile is built by the offline gates.

The beta package also includes the validated shared activity-callback cleanup
correction, revision2 Window Engine presentation handoff and
completed-construction action gating needed by the accepted panels. The bounded
alpha panel-setup diagnostic remains compiled only for the alpha build flag.
Optional engine modules are still installed by the player, not by selecting a
mod or updating the application. Existing native-only revision1 content remains
supported; a managed-panel declaration requiring revision2 cannot be satisfied
by an older installed module.
