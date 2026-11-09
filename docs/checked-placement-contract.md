# Guarded stock-cast checked placement v1

Available in Manager 0.3.11 as an optional, guarded provider.
The chain now selects explicit default Steam/beta2/GOG profiles. Startup checks
reviewed observer, cast, action and image bodies; individual installers also
guard their write sites. Query, relocation and state profiles are independently
checked across all three executables. A guarded completed-world
construction route now exists separately from saved-game admission; neither
route bypasses current world/catalog or effective-package checks.
See [release integration evidence](release-0.3.11-integration.md). The historical
checkpoints below distinguish offline evidence from consumer gameplay acceptance.

## Declaration and native procedures

### Learned, isolated actions (v3)

The installed October 12 consumer is bound by the guild's
`dist/local-test-receipt.json`; its definition SHA256 is
`c242d118f7235666827452a2e7f61b1fb2fc34d64826048c6eef022da6b66b31`.
Source-only Manager admission with the installed spell-policy provider and
owned AP78 spell icon is recorded in `local/learned-placement-installed-admission.log`.
This does not prepare a profile or establish live learning/arrival acceptance.

`stock.checked-placement.v3` retains all v2 fields, including `arrival_action`,
and adds an explicit integer `required_level` (1..1000). The authored departure
must retain the v2 Teleport clone except for `Game/SpellType value="None"` and
`Game/CharacterLevel` equal to that declared level. SpellRank, ValidationScript,
TimeoutDuration0, release, effector and arrival structure remain unchanged.
V1/v2 do not acquire these exceptions. MMPL3 adds the declared level after the
existing arrival image identity; older runtimes reject the new version.

The stock named None category maps to zero and is skipped by ordinary
GetBestSpell list1..4 selection before validation/rank. Evidence:
`majesty-gold-hd-research/docs/action-spelltype-schema-20261012.md` and its
linked three-profile JSON. This does not block explicit named action calls or
an explicit List_None request. The native checked provider still binds Engine
identity/script/flags and dispatches through its existing DoAction bridge; it
does not select by Game/SpellType or call CastSpell. No new gameplay hook is
introduced by the metadata contract.

V3 does not teach the action or invent eligibility. The owning GPL must call
stock idempotent LearnSpell at its established learning-eligibility boundary,
and retain all current casting checks and successful-arrival cooldown. Use the
existing AP78 `kind=spell` declaration on the owned Action for its name/icon,
not a fake passive on a stock hero. Save/load and in-game acceptance remain
consumer lifecycle checks; metadata acceptance alone is not completion proof.

October 12 integration checkpoint: the owning guild's
`private/dawnfall-learned-v1/WitchHunterFourSkills` was admitted read-only against
installed stock and shared spell-policy source without writing a merged profile.
Its definition SHA256 at inspection was
`2d2247404e345a790109ed96ce054deb15d9c8f112b8bee1f8b14b7c5ad84aff`.
This is a receipt, not a future byte-identity admission requirement. Local test
Manager build receipt: `local/learned-placement-manager-build.log`. Actual
learning, level/building transitions, AP78 visibility, save/load and casting
remain in-game acceptance work. Breach's separate acquisition/icon repair is
not resolved by this build.

Schema3 `runtime_features` entry (all fields required):

```json
{
  "type": "stock.checked-placement.v1",
  "feature_key": "dawnfall",
  "api_prefix": "WHP_Dawnfall",
  "actor": "Solarus",
  "action": "WHP_DawnfallCast",
  "release_callback_symbol": "WHP_DawnfallRelease",
  "movement_callback_symbol": "WHP_DawnfallCommit",
  "maximum_range": 600
}
```

The names are examples, not inserted into the consumer. One binding is supported.
This feature requires `stock.attack-projectile-observation.v1` in the same
composition; it reuses that service's loaded-BCD and world identity checks.
`manager.checked-placement.v1` is derived only after effective-output validation.

Range accepts 1..2097120 pixels. The upper bound is twice the maximum supported
map side (65535 tiles ×16 pixels), covering every supported map diagonal.
The default remains 600. A map-wide declaration does not scan the map: landing
candidates still come only from the chosen target's bounded exterior perimeter.
Squared-distance arithmetic remains 64-bit, and target identity, landing fit,
path, cancellation, and cast ownership checks remain unchanged on all profiles.
Caller capability strings alone cannot select its hooks.

All four exports are native GPL procedures with an integer output reference as
argument0. They are not return-valued GPL functions:

| Suffix after api_prefix | Arguments after output | Output |
| --- | --- | --- |
| `_Ready` | agent Caster | 1 supported loaded actor/map/footprint; 0 unavailable |
| `_Boundary` | agent Caster, agent Target, integer Phase | 1 admitted; 0 refused/unknown |
| `_Begin` | agent Caster, agent Target | 1 stock cast attempt started; 0 before dispatch, with no gameplay side effects |
| `_Commit` | agent Caster, agent Target | 1 coordinate write authorized and stock relocation returned; 0 refused; -1 effective provider unavailable |

Phase0 admits empty channels or the exact stock movement classes on channels0/1;
channel2 must remain empty and a pending provider cast is rejected. The bounded
reader checks only this actor's stacks, owner, count and bidirectional links.
Unknown/action/animation orders are refused. It does not use the global weapon
settlement query: already-fired projectiles are not modified by spell submission.
Stock CastSpell forwards to the same PerformAction dispatcher on all three
profiles; that dispatcher owns ordinary movement/action ordering. No manual
StopMoving, task reset or custom cancellation is inserted. Phase1 requires the
particular observed stock movement callback and captured actor/target lifetimes.
The phase argument alone cannot create authority. Gameplay eligibility, distance
policy, mark/Breach ownership, cooldown and follow-up Attack_Object stay in GPL.

`Begin` returning1 means a started attempt, including one synchronously cancelled
by stock callbacks. It never spends cooldown or promises eventual movement.
False occurs before the native DoAction bridge. `Commit` can perform stock
cancellation before a final refusal, but 0 never authorizes a coordinate write.
Only output1 may spend the consumer cooldown. No coordinates or reusable tokens
are exposed.

## Required consumer source

The owning consumer task must add its declaration, a private stock WRd1 action,
release function and wrapper calls, then compose that new source revision.
Do not reuse v6 compatibility hashes as approval of a modified consumer BCD.
The current v7 stub and decision tree were not edited here.

Clone the effective stock `teleport`/WRd1 Description literally. Change only
ID, Name, Description, Engine/Script GPLFunction, and Game/TimeoutDuration to0.
The native direct-action route does not call learned-spell cooldown accounting.
Keep Cast/Stand images, ordinary spell flags, effector duration1200 and the other
stock fields. The release function must match `release_source(feature)` in
`src/majesty_cam/checked_placement.py`, which emits:

```gpl
function WHP_DawnfallRelease(agent thisagent, agent target)
declare
    integer theTimePeriod;
begin
    theTimePeriod = $GetSpellAttribute("WHP_DawnfallCast", "effector_duration");
    $createeffector(thisagent, "teleport_effector", theTimePeriod);
    thisagent's "teleportScript" = $WHP_DawnfallCommit;
    $RunThread(thisagent's "teleportScript", theTimePeriod / 2, thisagent, target);
end
```

This retains Teleport_Effect's effector, saved function value, half-period
RunThread and stock cancellation/restoration ownership. The approved difference
is passing the captured target, replacing Teleport_DoMove's current-target lookup.
The effector name may also refer to an owned private clone of the effective
stock `teleport_effector` overlay. Only ID/Name/Description and the stock
`NotVisibleInISOView` rendering flag may differ. The effective clone must match
the owner's XML; timing, callback order, sound, attachment and other fields
remain unchanged. This generic option does not change the native wire format.

2026-10-14 regression: a consumer switched to such a hidden clone, but the
release-token comparison still required the literal stock overlay name.
Catalog preflight did not exercise that later validator. Tests now cover the
actual installed source in both dataset views and reject altered lifecycle or
overlay fields. Research context: graph f2644580d33ad98703361cd8fc88c825068161ef,
spell.teleport_short decoded fields (game_files_data_action_cam/DACT[11]/ARa1)
do not establish callback semantics; shared-map and
teleport-eligibility-chain-source-20261011 retain that limitation. Primary
comparison uses SDK Data/M_Overlays.xml and GPL/TaskModules/Subtasks/Spells.gpl,
plus the existing release contract above. No new native behavior is inferred.

The stock hero prototype already declares `function teleportScript`.
The movement callback is package-owned, takes `(agent, agent)`, rechecks consumer
policy, then calls the `_Commit` procedure. It must not schedule a second timer.
Native cast authorizations are never restored from saved IDs; restored callback
invocations without a fresh observed cast decline.

## Provenance and native boundaries

The Manager checks both effective dataset views, private action ownership, the
literal stock clone, release tokens, callback signatures and alias collisions.
The generated `DataMX/majesty_mod_manager_checked_placement.bin` (`MMPL` v1)
contains bounded names/range plus SHA256 of the actual generated MMOB proof.
That proof pins Any/Majesty/MajestyExpansion compiler outputs and guards loaded
BCD precedence. Optional and baseline BCDs cannot define these native aliases.
The native reader compares against the exact observer proof it parsed, not an
isolated consumer DLL/BCD hash.

Exact image SHA256:
`e15cf0d8b6150f1b60ae6dce9f7cafae920d231b5c7aeac1d2f4be9c2519030b`.
All following addresses are VAs in that image:

- Post-submit `5DF310` returns the order; the provider also requires it linked to
  the expected actor channel. Action processor `5DF7B0` supplies the exact
  action-to-animation transfer. Order fields contain action IDs, not pointers.
- Actual emission call `60C165 -> 5DAE90` and RunThread `5D3340` identify the
  released cast's idle function value and captured actor/target. Native timer
  call `5938C8 -> 590E40` brackets that exact invocation; nested unrelated
  callbacks cannot borrow authority. Function reset/destruction revoke it.
- Player/team, description change, HP death, removal, direct dead-bit writers,
  order retarget/clear, concrete retirement, load/restore and world teardown
  invalidate before native callbacks. The observer shares submit/unlink/retire
  hooks; a parallel unit factory or world lifecycle is not introduced.
- Loaded unit membership and descriptor membership are checked afresh. Only
  covered concrete unit vtables, living outside units, nonempty initialized
  native bitmap/rectangle footprints, a bounded map, hostile distinct teams,
  and the declared actor's actual normal ground/linear movement are admitted.
  Uninitialized shape caches decline; the provider does not fabricate shapes.
- `5DA530` completion-byte path query uses flags400 and the actual mover;
  `5E1C30` full-footprint placement uses flags800. `5DA580` must accept exactly
  the prechecked exterior seed. Full bounds/footprints apply to every candidate.
- Stock `5DEF20` cancels channels1,0,2. State/path/fit are repeated afterward.
  `5D7520 -> 5D7460` retains spatial notifications. A guarded six-byte window
  at `5D748F` repeats state/path/fit after +B8/+BC notifications, before stores
  beginning `5D7495`. Only the expected actor and concrete call frame may write;
  refused writes skip the stores and retain the native post-notifications at
  current coordinates for a still-owned actor. Retired/world-invalid actors
  use the native epilogue without another unit call. Registers, flags and FP/SSE
  state are preserved. Other/reentrant writes invalidate the pending attempt.

## Offline evidence

- `tests/CheckedPlacementTests.cpp`: placement, callback lifetime, reentry,
  identity/movement/footprint, invalidation and native-proof parser fixtures.
- `tests/test_checked_placement.py`: declaration, stock clone, effective callback,
  proof binding and derived-capability refusal cases.
- `tests/test_dawnfall_native_profiles.py`: exact instruction/call/ABI evidence.
- `artifacts/placement-composition/20261003T002048620580/verification.json`:
  real isolated three-dataset compiler/composition output with a provider fixture.
  Its input is a Manager-owned copy; it does not register the consumer AI tree.
- Logs: `artifacts/checked-placement-build.log`,
  `artifacts/checked-placement-python.log`, `artifacts/dawnfall-native-checks.log`,
  `artifacts/placement-observer-regression.log`.

The consumer v8 revision now uses this ABI, including the literal stock release
and Solarus tree integration. Four isolated actual v8 compositions are recorded
in `artifacts/dawnfall-v8-composition-verification.json` (alone, with Bards, with
Alchemist, and all three). Each validates the actual generated Any/Majesty/
MajestyExpansion BCD identities and the MMPL-to-MMOB digest binding; the native
proof parsers reopen each emitted proof. This remains offline evidence only.

The compatibility review found every v6 function unchanged and twelve added
functions; no compatibility component owns an added symbol. The registry pins
the complete v8 function set. `artifacts/v8-compatibility-review.json` records the
review and `artifacts/compatibility-before-v8.json` preserves the former pins.
V6/v7 consumer directories were read only and remain unchanged.

The aggregate regression receipt is `artifacts/provider-final-regression.log`.
The five previously reported issues are resolved: profile assertions explicitly
retain the approved exact-beta2 capability exceptions; expression analysis now
rejects both increment and decrement tokens; notification insertion preserves
the original source spacing; obsolete potion-effect restrictions were replaced
with exact effect-source preservation and real consume/forget/dead-guard refusal
assertions, consistent with the existing selected-effect contract. No failing
case was disabled. Native instruction/profile fixtures remain offline evidence.
