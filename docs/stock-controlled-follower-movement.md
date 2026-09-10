# Stock controlled-follower movement lifecycle

`stock.controlled-follower-speed-sync.v1` is a source-composed extension of
Majesty's existing controlled-monster lifecycle. It does not add a DLL hook,
timer, watcher, or replacement follower AI.

## Stock ownership

Installed `GPLMx/TaskModules/Subtasks/mx_Control_Monster.gpl` owns the control
transition. `Control_Monster` rejects a dead target, increments the leader's
follower count, installs `fake_wander`, creates the infinite Charm effector,
assigns `Controlled_Monster` and `Controlled_Monster_Death`, records the leader,
and transfers player ownership.

Installed
`GPLMx/TaskModules/Characters/Monsters/mx_Controlled_Monster.gpl` owns both
cleanup exits. `Controlled_Monster_Death` decrements the valid leader's follower
count before `Monster_Gravestone`. `leader_dead` detects an invalid leader,
switches to the stock delayed `fake_stop` reversion, removes the Charm effector,
and ultimately reaches `Reset_Controlled` through `Stop_Being_Controlled`.

Stock `Speed_Monster` proves the paired attribute operation: a negative
`ATTRIB_MovementRateModifier` adjustment increases movement rate, and the exact
positive inverse removes it.

## Manager composition

For each declaration the manager:

1. validates one package-owned `(agent Leader, agent Follower) is boolean`
   eligibility callback;
2. generates four deterministic 16-character private effector names from the
   package UUID and feature key, one for each possible positive difference in
   Majesty's bounded Speed 1–5 tiers;
3. after stock `Control_Monster` transfers player ownership, verifies both
   stock Speed values are 1–5 and applies one declared movement step for each
   tier by which the follower trails the leader, only when the corresponding
   marker is absent and the callback returns TRUE;
4. before stock death or leader-loss cleanup, checks all four markers, applies
   the exact inverse once for every step actually present, and deletes those
   markers; and
5. retains every original stock statement and its order.

The markers make cleanup exact and idempotent. The composer registers every
generated marker as a private Overlay Description by cloning stock
`vines_icon`'s persistent, manually checked/deleted, non-isometric lifecycle
shape. This ensures `CreateEffector`, `CheckEffector`, and `DeleteEffector`
always resolve a real effect type; packages do not provide these internal
resources. Independent declarations use independent markers, so their
adjustments may stack without one feature removing another's value. The composer requires the complete recognized stock
setup, ownership-transfer, gravestone, and Charm-cleanup anchors. It refuses a
changed lifecycle rather than guessing where to insert code.
