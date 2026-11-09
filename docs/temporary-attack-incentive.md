# Temporary attack incentive — source boundary

User direction, 2026-10-13: replace flag-backed casting with a separate temporary
attack incentive. Cast price remains 500. Player flags are independent. Do not
prepare or change the user's merged profile. The Manager update remains held.

## Payment and lifetime

Use the existing `stock.ap69-sovereign-target-action.v3` paid callback. The
guild owns its declaration and timed effector; Manager must not add a second
debit, reward creation, hidden RewardFlag, flag timeout, payout or refund.
Existing effector eligibility/expiry is the incentive lifetime source, not
a new polling task or separate timer. Ordinary stock flags may be placed,
increased, paid and removed independently before, during and after the spell.

## Stock reference and limits

Research `reward-selection-source-pair-20261012.md` identifies the base and
expansion `DecisionTrees/Modules/check_rewards.gpl` counterpart. The installed
SDK source confirms reward score is cost * greed modifier / max(distance,100).
Strict greater-than retains the first tie; the final score must exceed 1.
Attack eligibility honors `no_attack`, valid target, allegiance and crowding.
Stock flag dispatch also appends the hero to the flag's heroes list and sets
the hero's parent to that flag: neither operation belongs to a separate spell.

`Combat_wandering.gpl` demonstrates non-flag attack dispatch by assigning
`activescript = $Attack_object`, target, and intent. Its candidates are monsters
(or enemy heroes in its companion), not lairs. `target_eval.gpl` scores an
already supplied target; changing its return does not add lair candidates.
Consequently a target_eval-only bonus does not implement this requirement.

The replacement needs effect-eligible lair candidates and a scoring/selection
boundary that preserves ordinary reward handling, including a player flag on
the same target. It must not always preempt stock rewards merely by running
first. This is a source integration requirement, not proof of a native bounty
mechanism or a reason to change stock flag records.

The guild owner has the authorized source/candidate correction. Implement the
selection extension as ordinary GPL: no new native capability or Manager-only
declaration is needed. Manager uses its existing generic function merger and
player preference for actual overlap, not a guild-name-specific rewrite.

For a player attack flag on the same eligible target, add the incentive to
that existing candidate's score and retain its stock dispatch and payout.
For a separate spell-only candidate, compare against the same best score and
dispatch using the stock raid_lair assignments and `#Intent_Raiding`. Never
attach the hero to a synthetic flag. Equal scores retain the existing candidate.
The amount is a motivation weight, not gold stored in or paid by the effect.

## Acceptance still required

No flag vs existing player flag; cast price 500 in either case; independent
player increase/cancel/payout; expiry and recast; invalid/dead/changed-owner
targets; no_attack callers; target selection and player flag coexistence;
base/expansion source; all three runtime profiles. No live acceptance claimed.

## Source integration checkpoint

Candidate: sibling guild repository
`private/breach-temporary-incentive-gpl-v1/WitchHunterFourSkills`.
Its `verification.json` binds the source and compiled files; Manager independently
rechecked those hashes, loaded the ordinary paid v3 declaration, and confirmed
the package does not select the bounty service. Compiled `Data/WHP.bcd` includes
`check_rewards` and both incentive helpers. The generic function merger admits
the replacement against both installed stock base/expansion bodies; no merged
package was created. The existing paid route's production windows were checked
against the exact Public, beta2 and GOG fixtures. These are offline checks, not
gameplay acceptance or deployment.

Added regression coverage: ordinary paid action selection does not emit a
bounty helper, and actual paid runtime dispatch bypasses an installed/rejecting
bounty service while charging exactly 500 in both player-flag states.

Expiry removes the additional incentive for subsequent decisions. It does not
invent a task-cancellation loop to pull heroes out of an attack already begun.

Final receiving check: `merge_sources` against both base and expansion stock
accepts the candidate's check_rewards replacement and helpers. A competing
whole-function replacement produces a normal conflict. Supplying either side
as the explicit resolution retains that side's exact token stream, with no
incentive reinsertion after selection. Choosing another mod's replacement can
therefore remove the incentive's decision logic; that is intentional preferred-
mod behavior, not a feature-specific exception. Only in-memory semantic results
were evaluated; no profile/output package was prepared.
