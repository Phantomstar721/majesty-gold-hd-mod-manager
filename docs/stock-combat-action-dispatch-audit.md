# Weapon action selection and nested defeat callbacks

2026-09-20, supported Steam beta2. Read-only source/native audit; no action
adapter, runtime patch, merged profile, or live experiment was created.

## Proven boundaries

Stock `M_Actions.xml` A001/basic_attack selects ImageSet Attack, Rate max1100,
and Script make_attack. A different ImageSet must be selected before submitting
that action, not from make_attack after presentation has already started.
Stock `attack_end` in `mx_make_attack.gpl` only distributes hero/familiar XP.
It is not a notification that native animation/order cleanup has finished.

The Manager's `gameplay_events.py` combat-experience-awarded observer wraps the
hero XP award in that function. It is not a defeat or weapon-action selector.
The generic semantic composer merges function source; it does not automatically
intercept every PerformAction call in foreign functions.

One installed third-party combat source, Workshop73230/1965892371/GPL/
AI_Combat.gpl, performs weapon dispatch in attackLogic at line236:
`$performAction(thisAgent,(thisAgent's "attack_action"),target);`.
Changing only stock attack_object leaves that alternate path unchanged. Any
source-level selection change there must retain its preceding spell, range,
movement and kiting gates and evaluate selection only at actual weapon dispatch.
There is currently no existing Manager feature that supplies such a selector
across arbitrary foreign combat functions.

## Native PerformAction behavior

GPL dispatch resolves the action/units at `5D1990`; `5D1A42` invokes the unit's
virtual +F4 (`5DE3C0`). That path invokes order processor virtual +14
(`5DFA40`). It does not simply append an isolated visual effect:

- `5DFA69..5DFA98` invokes existing action cancellation/replacement paths.
- The default action path invokes unit virtual +1A4 (`5DF100`), which delegates
  to +1A8 and removes additional channel-1 order kinds7/6.
- `5DFAA7..5DFB10` constructs action order kind10 with its action/target and
  submits it through virtual +18C.
- `OrderAction::Process` (`5DF7B0`) later starts its presentation through
  `5DF740`; action animation has a separate order lifecycle (`5D0F60`).

Thus submitting a self-targeted action from inside a lethal-hit/death callback
reenters action ownership while the originating callback may still be on the
stack. It must not be described as a proven post-attack sequencing point.

## Unresolved, do not infer

This bounded audit has **not** proved whether the remaining cleanup of every
originating attack can overwrite/cancel the newly submitted action. It has not
identified an exact stock post-kill spellcast analogue guaranteeing this
ordering. Neither direct callback submission nor a timer/deferred callback is
approved by this evidence. A complete callback-to-cleanup trace for the selected
action path is still required before claiming safe Finale sequencing.

Stock resurrection callbacks do submit do_nothing, but they restore a dead
recipient and its scripts; they do not establish safety for interrupting the
live attacker's action from the victim's synchronous death callback.
