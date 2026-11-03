# Owned effect sequencing: isolated implementation

Manager 0.3.11 includes this tested sequence core and the guarded placement
provider. This document retains the original core-design evidence; it does not
claim that the core alone is a renderer. See [release integration](release-0.3.11-integration.md).


Current authority/status, 2026-10-04: the user has since approved full actor
lifecycle research and requires all three executable versions. Historical
actor-scope exclusions and the modified-beta2-only scope below are superseded,
not current restrictions or release exceptions. The isolated core is still not
a native renderer. See [current lifecycle evidence](dawnfall-fade-lifecycle.md)
for the verified draw boundary and remaining arrival-action ownership gap.

The authorized new Manager component is implemented in `runtime/EffectSequence.h`
and `.cpp`. It is an authored presentation scheduler, not a reconstruction of
actor internals. No production capability, native hook or V28 caller enables it.

## Implemented behavior

An observed release starts steady departure at a captured source anchor. Only a
successful checked-placement notification can start arrival at the actual resulting
position. The core never requests movement, stores a reserved destination or
changes the existing 600ms movement callback. A missing commit expires departure
after the stock 1200ms release lifetime.

Arrival uses a 500ms quadratic diagonal from offset (-160,-240) to ground (0,0),
eight trail samples spanning 280ms, 200ms of impact and 200ms of fade. These are
authored presentation values for a placeholder review, not stock timing claims.
The frame output supplies geometry and phase; it does not yet render art.

Each frame replaces the complete previous visual batch. Identity is keyed by
actor ID, lifetime and world generation; duplicates, absent/dead/inside actors,
clock reversal and expiry remove visuals. Cancellation/removal clears the
matching sequence. Placement is consumed once. World/load reset clears all
transient visuals and does not recycle tickets. No native actor appearance or
combat state is modified, so reset requires no actor restoration operation.
There is no damage, stun, invulnerability, attack callback or audio event to replay.
The core deliberately does not serialize a sequence or resume it after load.

Capacity is bounded at 128 active owners. Timing is bounded and arithmetic uses
64-bit intermediates. Readiness requires the existing exact-profile placement
adapter and a validated replaceable-world-frame renderer. The profile enum is an
internal adapter input, not user/package authorization; only the existing exact
executable gate may select its modified-beta2 value. No current production code
supplies renderer readiness, so no executable profile advertises this capability.

`scripts/Test-EffectSequence.ps1` compiles and executes the actual new C++ core
in isolation. Fixtures cover acceleration, trail placement, phase boundaries,
duplicate placement, missing commit, cancellation before/after arrival, death,
identity reuse, reset, clock reversal, lag, capacity and unavailable capabilities.
They establish authored code behavior only, not native rendering or save acceptance.

## Alternatives grounded in existing source

1. **Private actor actions:** would still need same-actor action handoff/recovery.
   This component does not use them or investigate their excluded internals.
2. **An effector attached directly to the caster:** stock `CreateEffector` and
   Rage's completion script provide an existing owner. They do not establish an
   independent fixed-ground anchor while the caster continues moving. This is
   insufficient evidence for the requested landing image.
3. **Stock meteor projectiles:** `Meteor_Storm_Active` targets enemies and its hit
   callback applies damage. That sequence is not an approved cosmetic adapter.
4. **A private non-damaging spell unit:** concrete SDK candidate, authored under
   `artifacts/dawnfall-v2-engineering/spell-unit-candidate`. Stock
   `Meteor_Storm_Hit` uses `CreateSpellUnit(caster, description, caster)`;
   `Farseeing_unit_created` gives that unit a `SetSpellUnitTimeout`, and
   `Farseeing_active` is empty. The candidate preserves the meteor spell-unit
   descriptor shape, replaces the birth function with timeout-only code, and
   supplies an empty active script. It does not copy Farseeing's sight range,
   meteor damage or periodic threads. Its DFV1 image is intentionally unresolved;
   there is no installable package or production call.

The fourth alternative is a genuinely permitted source/API integration route.
Using existing SDK creation functions does not require researching their factory
internals. It may render an entire baked arrival animation with native timeout
ownership instead of a new per-frame renderer. Current source does not establish
that the unit remains fixed after caster movement, animation phase persistence,
or cancellation semantics. Those are explicit acceptance questions for the
documented SDK route, not permission to reconstruct excluded implementation.

## Smallest remaining interfaces and visual difference

For the native sequence core, the missing interface is a **Manager-owned,
replaceable batch of cosmetic world-anchored images**, driven by a game clock and
current identity samples. It must discard drawings on reset without actor calls.
No callable per-frame renderer with that contract is exposed by the inspected
Manager source. It cannot simply be declared available. The SDK spell-unit
candidate is a possible adapter for a baked timeline; equivalence to replacement
and immediate cancellation is unproved and must not be asserted.

## Owning-thread continuation, 2026-10-04

`scripts/Test-EffectSequence.ps1 -ExportSamples` now compiles and runs the actual
sample exporter as well as the isolated core. Its `samples.json` is input to
`tests/test_effect_sequence_art.py`, using explicit installed stock CAM and sample
paths. The checks cover the 81 stream-major references, exact signed offsets,
hidden unused trail streams, invalid phases/ranges, changed stock envelopes and
strict numeric schema types. No art was installed or new pixel artwork generated.

The source-only spell-unit and FadeOut/FadeIn probes were missing GPL `declare`
sections; these were repaired and checked with the stock compiler. The probe BCD
in `local/witch-public-api-probes-20261004` is diagnostic output, not a playable
quest or approved production caller.

The placement dependency is still guarded to the audited modified-beta2 image:
`CheckedPlacementRuntime.cpp` directly calls that build's native addresses and
uses `AuditedBeta2Startup`. Changing a profile enum cannot port it. This is a
separate remaining implementation requirement before any three-version release.
The SDK Wendigo blink precedent schedules FadeIn after a deferred movement call;
it does not establish the complete cancellation/load/death recovery contract
required for this authored arrival sequence. No visibility-changing runtime
integration is enabled by the compiler or artwork checks.

Both independent-effect alternatives leave the Solarii visible and ordinary
combat under native control. They can aim to show the complete meteor/trail/impact
alongside the actor, but they do **not** guarantee disappearance/reveal or defer
the first attack until impact. This is a material visible difference requiring
review, not a completed implementation of literal transformation. The new core
solves sequence state and geometry without hidden actor-state assumptions; the
adapter and this visual interpretation remain the dependencies for a playtest.

Source references are the local stock SDK `GPL/TaskModules/Subtasks/Spells.gpl`,
`GPL/Spell_Data.dat`, `Data/M_Characters.xml`, `Data/M_Overlays.xml`,
`Data/M_Projectiles.xml` and `Data/M_ParticleSystems.xml`, plus existing
`docs/checked-placement-contract.md`. No binary research was used for this work.
