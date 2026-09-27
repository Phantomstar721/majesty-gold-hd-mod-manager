# Shared spell policies

These opt-in schema-3 declarations use stock GPL callback ABIs on default Steam
1.5.2.24, Steam beta2 1.5.2.28 and GOG 1.5.2.28. Policy guards are source
composition; persistent caster attribution additionally requires the guarded
native extension below. Neither adds polling or timers. Gameplay eligibility
and damage values belong to the provider, not the Manager.

## Central discovery (no consumer edits required)

A provider can declare `stock.spell-policy-discovery.v1`, with `feature_key`
and these seven arrays of action or callback names:

- `suppression_exempt_actions`
- `suppression_special_actions`
- `already_guarded_direct_callbacks`
- `physical_projectile_callbacks`
- `area_or_periodic_projectile_callbacks`
- `other_exempt_projectile_callbacks`
- `direct_projectile_callbacks`

The Manager resolves XML/GPL bindings against that provider-owned policy.
Unknown or contradictory classifications and mixed-use impact callbacks produce
explicit errors rather than guesses. Consuming mods need no new declarations.
Per-action validation wrappers preserve original validation (or stock allowed
validation when absent). GPL cast wrappers preserve the original payload;
native/projectile action bindings remain native. Whole-impact guards prevent
secondary effects leaking through an intercepted hit. The explicit consumer
declarations below are optional alternatives, not prerequisites for discovery.

## Provider

```json
{
  "type": "stock.spell-policy-provider.v1",
  "feature_key": "projectile-blocking",
  "policy": "block-direct-projectile",
  "callback_symbol": "Example_BlockProjectile"
}
```

`Example_BlockProjectile(agent Source, agent Target) is boolean` returns true
only when it has consumed/intercepted that impact. The provider owns its eligibility,
hit resolution, charge consumption, feedback and attack-completion behavior.
It must not call the guarded impact again. The Manager calls providers in stable
callback-name order and stops on the first true result: one impact cannot consume
two providers. Register the provider once, not once per consuming spell.

For suppression use `policy: "suppress-special-spell"` and a callback with
`(agent Caster, string SpellName) is boolean`. True means suppress. This predicate
must be **read-only/idempotent**, since validation and execution both query it.
It receives only actions explicitly registered as special spells.

## Optional explicit direct-projectile consumer

```json
{
  "type": "stock.direct-projectile-impact.v1",
  "feature_key": "ice-projectile-impact",
  "callback_symbol": "Example_ProjectileHit"
}
```

The callback must be package-owned `(agent Source, agent Target)` with no return
value. It must be the complete **single-target direct-projectile impact entry**,
not a shared damage helper, area victim callback or periodic tick. Registering
the latter is a false declaration; the Manager cannot infer gameplay intent from
a two-agent signature. All paths sharing that callback must have the same direct
projectile classification. Separate mixed-use callbacks in the owning package.

When a blocking provider is selected, composition inserts one early-return guard
immediately after `begin`, before **any** original payload instruction. Damage,
chill and other secondary effects are skipped together. Everything after the guard
remains literal. No blanket interception is added to `spell_attack`, `damage`,
area damage or damage-over-time. Without a provider the original body is untouched.

## Optional explicit suppressible special-spell consumer

```json
{
  "type": "stock.special-spell.v1",
  "feature_key": "special-spell",
  "action_name": "example_special",
  "validation_callback_symbol": "Example_Check",
  "cast_callback_symbol": "Example_Cast"
}
```

The package must own the named Action XML, with these exact bindings:

* `Game/ValidationScript value="Example_Check"`: owned `(agent Caster) is integer`.
* `Engine/Script type="0" cProc="0" GPLFunction="Example_Cast"`: owned
  `(agent Caster, agent Target)` with no return value.

An action without a validation function must first supply an owned stock-shaped
validator returning 1. Sharing either callback between multiple action identities
is rejected; give each action a small named entry that calls its shared helper.

With a suppression provider, composition guards the validator (return 0), the
cast callback (return), and the stock `Cast(agent,string,agent,string)` entry
(return before experience, sound and native cast submission). The existing Cast
body and all private payloads remain unchanged after their guards. Execution is
checked again because suppression can change after selection. Already-created
projectiles/effects are not cancelled. Raw calls to private effect helpers that
bypass these entries remain the author's responsibility; route spell execution
through the declared boundary instead of duplicating gameplay effects.

Without a provider no wrappers or Cast override are emitted. In explicit-only
mode unregistered actions remain unaffected; discovery instead requires explicit
classification of discovered spells. Provider-only selection emits no service.

## Validation and scope

Preparation checks exact schema, callback signatures, single package ownership,
duplicate consumers/providers, generated-symbol collisions and XML bindings.
The generated `MM_BlockDirectProjectile` and `MM_SpecialSpellSuppressed` names
are reserved implementation details, not APIs for undeclared callers.
Composition failures remain explicit; the Manager does not guess a damage class
or overwrite conflicting functions. Policy guards do not themselves add damage.

## Stock lifecycle and original-caster audit (2026-09-26)

`GPL/TaskModules/Subtasks/Cast.gpl` and its `GPLMx` counterpart have the same
argument shape and sequence: calculate/grant experience, play sound, dispatch
`castspell`. Action XML owns validation and the two-agent engine callback.
The guards run at those boundaries without taking ownership of cooldowns,
animation, native action cleanup or cancellation. Immediate impact callbacks
receive caster and target; blocking occurs before entering their whole payload.

`Fire_Ball_Hit` calls `CreateSpellUnit(Caster, "fire_ball", Target)` and performs
its original direct hit through `spell_attack(Caster, Target, 30)`.
`fire_ball_unit_created` sets the native lifetime and runs `fire_ball_active`
synchronously; the latter applies splash via `player_spell_attack(Target,15,2)`.
The original caster is already absent from that callback. Other spell units may
repeat active callbacks; their lifetime remains owned by stock spell-unit timeout.

Read-only disassembly of `CreateSpellUnit` confirms the same complete instruction
structure in all three executables (only relocated addresses differ):

| Boundary (VA) | Default Steam | Steam beta2 | GOG |
| --- | --- | --- | --- |
| GPL CreateSpellUnit entry | `430A20` | `431980` | `431850` |
| Load source's player at +80 | `430B1D` | `431A7D` | `43194D` |
| Replace source register with new unit | `430B59` | `431AB9` | `431989` |
| Invoke two-agent birth callback | `430B88` | `431AE8` | `4319B8` |

The constructor receives source **player**, coordinates and descriptor, not source
unit identity. Birth receives new spell unit and target. `player_spell_attack`
explicitly calls `spelldamage(nullagent(),...)`; it is also used by genuine
sovereign spells. Reconstructing a hero from player, selection or nearest unit is
incorrect. A global last-caster variable fails for nested births and delayed ticks.

## Persistent caster identity

Declare `{"type":"stock.spell-origin.v1","feature_key":"spell-source"}` to
derive native capability `manager.spell-origin.v1`. A scoped construction source
bridges the audited native boundary above. After stock initialization and before
birth, the stock GPL evaluator records an `agentref` attribute using AddAttribute.
Child spell units inherit the same original hero, not a bonus snapshot. Stock
lifetime, callbacks and cleanup remain unchanged; sovereign command births are
not intercepted.

`MM_OriginalCaster(agent Subject) is agent` returns the saved valid hero, or
Subject itself when its subtype is Hero (including hidden heroes). Missing,
deleted, sovereign and nonhero origins return null. Existing effects created
before enabling this service have no recoverable origin.

The attribute uses Majesty's saved agent-reference mechanism, not a persistent
native pointer. Installation verifies complete function fingerprints, displaced
instructions, call targets and the stock evaluator lifecycle on all three builds.
Automated checks cover emitted GPL, reference graphs and nested birth ordering;
they do not emulate Majesty's save codec. In-game acceptance must include save
and reload with a living attributed effect, then source deletion.

## Source transport through target-only helpers

```json
{
  "type":"stock.source-context-dispatch.v1",
  "feature_key":"attributed-hit",
  "target_symbol":"player_spell_attack",
  "parameter_types":["agent","integer","integer"],
  "callback_symbol":"Example_AttributedHit"
}
```

The provider owns a void adapter with an extra leading argument:
`Example_AttributedHit(agent Source, agent Target, integer Damage, integer Minimum)`.
Direct and periodic resolvers can register separate adapters.

Composition traces native Action/projectile/spell-unit callbacks and spell DAT
active scripts. Only synchronous helper paths reaching a selected target get
private clones carrying Source. Original helpers and unrelated callers keep
their ABI. Adapter bodies are traversal barriers, preventing recursive dispatch
or duplicate bonus application. Resolved descriptions and DAT selections, not
losing conflict candidates, determine the native callback roots.

The adapter resolves `MM_OriginalCaster(Source)` and adds its bonus exactly once
in its damage resolver. Preserve the stock null attacker in target-only damage:
Source must be separate, otherwise hero Intelligence scaling would be added
incorrectly. The Manager itself changes no rolls, mitigation or damage values.
No global last-attacker, tick service, HP hook, or poison change is added.
Arbitrary asynchronous callbacks and victim-only effectors are not inferred as
source-bearing boundaries.
