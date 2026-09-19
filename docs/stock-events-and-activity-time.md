# Shared gameplay events and accumulated activity time

These opt-in schema-v3 features provide shared stock event notifications and
consumer-defined, sampled activity duration. Neither facility owns quest AI,
eligibility policy, rewards, inventory effects, or building controllers.

## Stock ownership and the approved extension

The event facility composes observers into the stock GPL owners, not a UI,
inventory diff, world scan, or replacement AI. Only selected declarations add
callbacks. All subscribers run in deterministic mod-ID/feature-key order;
observers must return promptly and must not delete, retask, or recursively
invoke the observed stock owner. GPL callbacks are not a sandbox.

The activity ledger is the user-approved extension where no exact stock
mechanism exists: one shared stock-scheduled callback checks registered
activities once per simulation second. Conditions are consumer-owned, read-only,
bounded boolean queries. There is no inferred meaning for a custom activity.
The Manager owns identity, saved progress, pause/resume, removal and terminal
callback dispatch. No per-unit scheduler, fake world unit or marker effector is
created. Unselected features perform no work; an empty ledger sleeps.

The scheduling clone is `Rules/Quests_3.gpl:Day_Counter`: retrieve the existing
`GplAIRoot`, keep progress on its GPL attributes, and run a function-valued root
attribute through stock `NewThread`. That quest schedules `VictoryCondition2`
at 60000 milliseconds; the shared sampler uses its own reserved function slot
at 1000 milliseconds. It never replaces a stock root function slot. The stock
`KillThread` lifecycle removes the shared schedule once the ledger is empty;
terminal dispatch finishes before it may stop its own thread.

The SDK **GPL Reference**, pages 2, 4-5, 10, 33, and 38, specifies heterogeneous
one-dimensional lists, dynamic GPL attributes, one-based `ListMember`, and the
approximate, frame-budgeted `NewThread` interval. The executable's beta2 type
registration at `0x56BF13..0x56BF30` registers `FUNCTION` as intrinsic type 8;
the attribute type is `function`, not a guessed alias. Saved data lives on the
stock GPL root and stock scheduler, never in a process-local native ledger.
No new native clock query or timing hook is installed.

### Potion consumption

`GPLMx/TaskModules/Subtasks/mx_heal_self.gpl`: both `heal_self` and
`heal_self_fleeing` apply the healing effect and heal, then decrement
`ATTRIB_NumHealingPotions`. Observe immediately after that decrement, inside
the existing positive-inventory branch. Non-potion healing is unchanged.

`GPLMx/TaskModules/Subtasks/mx_Spells.gpl`: the six Bazaar effect functions
reject dead casters, apply their stock effects, delete the appropriate carried
item and forget its spell. Observe after the complete effect function; its
dead-caster return bypasses the observer. Effector duration and end callbacks
continue to own restoration. Stable identities are `healing_potion`,
`speed_tonic`, `strength_potion`, `shapeshift_potion`, `regeneration_elixer`,
`invisibility_brew` and `fire_balm`. The stock spelling `elixer` is intentional.
Purchase, effector expiration and non-consumable enchantments are not events.

### Actual reward-flag credit

`GPLMx/DecisionTrees/Modules/mx_check_rewards.gpl` owns Explore success and
both Attack success paths. Their death/cancellation functions are not success
notifications by themselves; Attack's target-death callback also contains a
guarded success branch. Preserve Attack's `gavereward` guard and assignment order.
`GPLMx/mx_Monster_Deaths.gpl` owns the actual stock distribution routines,
including Ranger range, same-player Explore policy, and invisible/camouflaged
recipients. Privately clone those distribution functions for the three flag
success calls and observe their actual recipients after `give_gold`; never
replace ordinary monster loot. Notification reports the stock per-recipient
share, including a zero share after integer division, not a recomputed reward.
The flag is borrowed context and may disappear immediately after dispatch.

### Attack-flag completion before payout

`attack-flag-completed` observes `attack_flag_poll` and
`Attack_flag_death_callback` in `GPLMx/DecisionTrees/Modules/mx_check_rewards.gpl`.
The stock birth function starts its existing `activeScript` polling thread,
sets `gavereward` false, and may change the flag owner's team. Both completion
paths resolve `target` from the flag's native TargetID and require
`gavereward != TRUE` plus `IsDead(target)`. Notify **inside that branch,
immediately before** `playsound(ThisAgent, "completed_reward", "begin")`.

The poll path sets `gavereward` true before distribution, deletes the flag,
and returns. The target-death callback distributes first, then sets
`gavereward` true, runs `check_revert_teams`, and returns; it does not delete
the flag at that point. These differing orders remain literal. Flag removal
still resets its heroes' tasks and reverts teams through stock `attack_flag_death`.
The Manager adds no scheduling, cleanup, reward state or UI refresh.

This is completion of the stock flag's objective, not proof of a gold transfer,
a particular killer, or a custom capture outcome. It runs even with no eligible
recipient, a share rounded to zero, or a zero-valued flag. Consumers requiring a
positive bounty must inspect the flag's `ATTRIB_RewardCost` themselves. Both
arguments are borrowed references: the target is already dead, and the flag
may be deleted after the callback. Record bounded evidence promptly, before
stock team reversion; do not delete agents, yield, change `gavereward`, trigger
the same stock owner recursively, or replace a mod's authoritative death/capture
confirmation. The existing stock guard owns duplicate suppression.

`reward-flag-paid` may be selected alongside this event. Both observers are
composed into each attack owner: completion runs first, while per-recipient
credit remains after the native `give_gold` call. No observer replaces another.
With no subscribers, no completion call or extra stock source input is added.

### Combat and exploration XP awards

`combat-experience-awarded` observes only the hero branch of
`GPLMx/TaskModules/Subtasks/mx_make_attack.gpl:attack_end`. Stock attack and spell
resolution compute `exp_given`, then the hero branch applies
`max(1, ExperienceLevel / combat_exp_div)` before calling `give_exp`.
The familiar-to-leader award in the same function remains untouched.

`exploration-experience-awarded` observes only
`GPLMx/TaskModules/Characters/mx_Travel_to.gpl:travel_to_exp`, inside its existing
successful `has_arrived(ThisAgent, false)` branch. Failed arrival, danger checks,
healing and travel continuations do not emit an event. This is stock arrival
credit for exploration/patrol, not credit for every newly revealed tile.

Both callbacks have the signature `(agent Recipient, integer Base)` with no
return value. A synchronous generated wrapper captures the original `give_exp`
argument once, calls the original `give_exp` first, then notifies subscribers
when Base is positive. Base is **before give_exp's recipient-level divisor and
any earned-reward bonus**, but after the combat caller's own divisor. It is not
the final XP credited. A zero amount after the recipient-level divisor may
therefore still produce an event with a positive Base. Level-up side effects
finish before notification, without recomputing Base at the new level.

Example declaration:

```json
{
  "type": "stock.gameplay-event-observer.v1",
  "feature_key": "support-combat-xp",
  "event": "combat-experience-awarded",
  "callback_symbol": "Example_CombatAward"
}
```

A consumer can award a fraction of Base to its eligible follower through normal
`give_exp`; that recipient's own divisor and selected research bonus run once.
The Manager does not find followers, choose a percentage, deduct leader XP or
award anything itself. Calling `give_exp` from the observer does not emit these
events: there is no broad interceptor. Songs, quests, training, tournaments,
item collection, familiar awards and direct XP writes remain outside them.
Observers must not call `attack_end` or `travel_to_exp` recursively.

The implementation changes only the two proved call identities. Their complete
stock bodies, predicates, payment/division order and callbacks remain intact;
an incompatible rewrite fails with the owning function named. There is no new
timer, saved state, native hook, per-frame query or cleanup lifecycle. With no
subscribers there are no generated wrappers or additional stock source inputs.

### Caravan delivery

`GPLMx/TaskModules/Characters/Henchmen/mx_caravan.gpl:Caravan_Go_Trade` owns
travel, destination replacement, cargo multiplication, transfer, scenario
callbacks and removal. Observe the successful branch before `henchman_dead`,
after the transfer/scenario work, using its existing `Target` and
`Gold_To_Give` locals. Return-home, missing market, destruction and removal
alone are not delivery. Callback consumers must copy needed context now.

### Completed Fairgrounds participation

`GPLMx/TaskModules/Buildings/mx_Fairgrounds.gpl:Enter_Tourney` sets
`ContestantInFair`, schedules the existing `ActiveScript` interval and selects
`Exit_Fair`. That timed continuation is the completion boundary. A private
continuation snapshots the event, rank and participant counter, runs stock
`Exit_Fair` literally, and then notifies eligible finishers. `Dump_Contestants`
still calls the original exit directly; cancellation and stat boosting are
not completion. Exclude a timed continuation while the grounds are cleaning
up or its contest has changed. Do not infer success merely from XP or exit.

## Package interface

Declarations reside in schema-v3 `runtime_features`.

```json
{
  "type": "stock.gameplay-event-observer.v1",
  "feature_key": "my-consumption-observer",
  "event": "potion-consumed",
  "callback_symbol": "MyMod_PotionConsumed"
}
```

| Event | Void callback arguments |
| --- | --- |
| `potion-consumed` | `agent Consumer, string PotionIdentity` |
| `combat-experience-awarded` | `agent Recipient, integer Base` |
| `exploration-experience-awarded` | `agent Recipient, integer Base` |
| `reward-flag-paid` | `agent Flag, agent Recipient, integer Share` |
| `attack-flag-completed` | `agent Flag, agent Target` |
| `caravan-delivered` | `agent Caravan, agent Destination, integer Cargo` |
| `tournament-completed` | `agent Participant, agent Fairgrounds, integer Event, integer Rank, integer Participants` |

```json
{
  "type": "stock.activity-duration.v1",
  "feature_key": "my-custom-activity",
  "api_prefix": "MyMod_Activity",
  "condition_callback_symbol": "MyMod_IsActive",
  "completion_callback_symbol": "MyMod_Completed",
  "cancellation_callback_symbol": "MyMod_Cancelled"
}
```

Condition: `(agent Owner, agent Subject, agent Context, integer Key) is boolean`.
Completion: the same arguments with no return value. Cancellation adds an
integer reason. Owner and subject are required live game agents, but are not
restricted to heroes or buildings. Context is an optional borrowed agent.
The consumer chooses a positive key unique within this feature and owner;
simultaneous features and owners do not share one activity slot. Generated
start/pause/resume/cancel/progress functions are namespaced by `api_prefix`;
colliding exports or package definitions must fail before composition.

Durations are qualifying sampled simulation milliseconds, not wall time (one
stock day is 60000). A registration earns up to 1000 milliseconds when its
condition is true at two consecutive enabled samples. Its first sample only
establishes eligibility: joining just before a shared tick never earns a full
second immediately. A false sample or explicit pause breaks that pair without
erasing accumulated time. Transitions can therefore undercount roughly one
sample interval. Stock script-budget delays can add slippage; this is not an
exact stopwatch or a guaranteed one-second wall-clock deadline. Pausing the
game stops the simulation scheduler; game speed follows the stock scheduler.
Conditions must not do world scans, pathfinding or mutate registrations.
Terminal callbacks may register/cancel other activities; remove the finished
record before calling one so it cannot complete twice. Cancellation is never
completion. Deleted owners/subjects are cancelled, and consumers must validate
borrowed agents in cancellation callbacks. Progress must be serialized through
stock GPL state; no process-local C++ activity ledger may pretend to survive a
save/load. Use the same prepared profile when resuming a save; changing or
removing its GPL definitions is not a save migration mechanism.

### Generated GPL API

For `api_prefix: "MyMod_Activity"`, all six functions return an integer:

| Function | Arguments | Result |
| --- | --- | --- |
| `MyMod_Activity_Start` | `agent Owner, agent Subject, agent Context, integer Key, integer Duration` | 1 created; 0 already registered (unchanged); -1 invalid live handles/key/duration; -2 capacity reached; -3 sampler busy |
| `MyMod_Activity_Pause` | `agent Owner, integer Key` | 1 present/paused; 0 absent; -3 busy |
| `MyMod_Activity_Resume` | `agent Owner, integer Key` | 1 present/enabled; 0 absent; -3 busy |
| `MyMod_Activity_Cancel` | `agent Owner, integer Key` | 1 removed and cancellation dispatched; 0 absent; -3 busy |
| `MyMod_Activity_Elapsed` | `agent Owner, integer Key` | accumulated qualifying milliseconds, or -1 absent |
| `MyMod_Activity_State` | `agent Owner, integer Key` | 0 absent; 1 last sample qualified; 2 enabled but waiting/not qualifying; 3 explicitly paused |

Do **not** interpret these return values as booleans: negative results are
errors, not success. Durations and keys are positive signed GPL integers.
The shared ledger supports 128 simultaneous registrations across all selected
mods, owners and activity types. Check the result of Start before marking a
consumer objective active. If another GPL thread receives -3 while the sampler
is processing its snapshot, retry from its next normal stock lifecycle call;
do not spin, create another timer, or silently mark the registration started.
Condition callbacks themselves are read-only and must not register/cancel work.

Cancellation reasons are 1 explicit cancellation, 2 owner lost/dead, 3 subject
lost/dead, and 4 supplied context lost/dead. Omitted context is `$NullAgent()`.
The parentheses are required: bare `$NullAgent` is a function reference, not
an agent. Stock `mx_LowLevel.gpl` uses the same `$NullAgent()` comparison.
An agent that is dying may remain a valid GPL reference; always validate before
accessing its game-unit properties. Death/invalid-handle cleanup occurs on the
next shared sample, including for manually paused records.

There is no completed-record cache. Both terminal paths remove the registration
before invoking its callback, and `_State` then returns 0. The consumer persists
any completed objective/reward state it needs. Starting the same owner/key
again from a completion callback intentionally creates a **new** registration.
Terminal decisions from a sample are committed before notifications begin;
cancelling an already-terminal record returns 0, not a second notification.

Example (the named callbacks must be defined exactly once in this package):

```gpl
function MyMod_IsActive(agent Owner, agent Subject, agent Context, integer Key) is boolean
declare
begin
    // Example only: a real mod checks its own saved activity and stock state.
    return ($IsMoving(Subject) == False);
end

function MyMod_Begin(agent Owner, agent Subject)
declare
    integer Result;
begin
    Result = $MyMod_Activity_Start(Owner, Subject, $NullAgent(), 1, 120000);
    // Only Result == 1 establishes a new two-stock-day registration.
end
```

Do not ship placeholder definitions for the generated six API functions.
The Manager emits them; collisions with authored definitions are rejected.
Use a separate completed callback and cancelled callback with the signatures
above. The reserved `MM_` GPL function/attribute namespace belongs to the Manager.

### Composition and validation boundaries

Observers at one event are additive and deterministic. The Manager preserves
straight-line callback preludes when the entire following stock body is
unchanged. Bazaar potion handlers may also retain conditional consume/forget/
return branches between the unchanged dead-caster guard and normal effects;
those branches receive the same consumption notification before returning.
The consumed item and forgotten spell must match the stock pair exactly.
These rules depend on code structure, not a mod ID or creature title. Other
changes to a protected success/cleanup boundary are rejected with its function
and source name, rather than silently replacing that mod's behavior.
Formatting/comments may differ; stock strings and statements may not.
Only requested stock owner files
are read and included in prepared-input fingerprints. Shared declarations also
appear under `shared_services` in the composition report.

The source-level sampler harness exercises emitted registration, qualification,
pause/resume, cancellation, death cleanup, capacity and reentrant callbacks.
The stock compiler separately checks the emitted service and event boundary
clones. Neither check substitutes for a consuming mod's in-game validation of
normal event effects, script-budget responsiveness, multiplayer, and save/load.
