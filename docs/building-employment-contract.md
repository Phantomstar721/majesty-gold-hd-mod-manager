# Building employment — integrated contract

Production parser, destination-specific source generation, MMCR v23 paired
dispatch and native primary-panel/queued-research gates are integrated. Public,
pristine beta2 and GOG have separate guarded command and read-side lookup profiles.
The historical checkpoints below describe the implementation sequence; this
opening status supersedes their former pending-integration statements.

Employment v1 gates private AP69 research-panel openers, not arbitrary controls.
Hire becomes disabled and Research enabled on confirmed arrival; optional
stock Visitors8021 replaces Hire visually when included in gated_control_ids
(see [stock Visitors contract](employment-stock-visitors.md)). Ordinary
visitors, upgrades and already-running research retain their stock lifecycle.
Roster refresh uses the existing stock event boundaries with a read-only revision
checksum, not a timer. The current roster is bounded to 64 eligible heroes.
No native gameplay/save-load acceptance or deployment is claimed.

The undeployed consumer is `../majesty-gold-hd-custom-guild-witch-hunter/private/crucible-hire-candidate-v1/WitchHunterFourSkills`.
`scripts/check_employment_candidate.py` checks its receipt, all declared controller
admission, employment selector resources, paired registry, and isolated generated GPL for
both datasets without composing a profile. Hire31300, Research8009, WSHR/WSPN,
`MM_WHP_CrucibleHire_Admit` and paired action bridge
`MM_Action_a63b958b9245e9625ab5230c` are the observed bindings.
The initially suspected Chapterhouse AP07/AP10 mismatch was a diagnostic-input
error: the isolated check omitted its paid-action declaration. Supplying all
controller features admits the existing paid-only Guild alias contract without
changing the candidate. Owner evidence is in the candidate parent's
`chapter-controller-admission.json`. These checks do not create or certify a
complete merged profile, which remains the user's Prepare operation.

The native build is at `artifacts/runtime`; it has not replaced the deployed
Manager. Native presentation fixtures exercise locked/unlocked transitions in
both directions, while queued-research fixtures cover rejected new actions and
unaffected completion of existing research. Deployment and a user-run Prepare
are the next steps before in-game Hire/arrival/cancellation/save-load acceptance.

## Package-owned inputs

```json
{
  "type": "stock.building-employment.v1",
  "feature_key": "forge.hire",
  "api_prefix": "ForgeHire",
  "parent_building": "Forge",
  "source_dialog_id": "FH01",
  "open_command_id": 8100,
  "gated_control_ids": [8009],
  "hero_titles": ["Ranger"],
  "minimum_level": 8,
  "eligibility_callback_symbol": "ForgeEligible",
  "cleanup_callback_symbol": "ForgeCleanup",
  "visitor_callback_symbol": "ForgeVisited"
}
```

Callbacks: `Eligible(agent Hero, agent Building) is boolean`,
`Cleanup(agent Hero, agent Building)` with no result, and the unchanged ordinary
`Visited(agent Hero)` function. Eligibility must be read-only. Cleanup retires
package-owned effects/claims; it must not delete, kill, rehome or start new tasks
for the hero. Manager completion owns membership/removal. These match the owner
callbacks already supplied; no signature adaptation is required.

Parent building identity is the shared declared building across its tiers. The
owner supplies a private MX05-shaped SMNU/STRT selector, exact stock geometry
and controls documented in stock-quest-board-panel.md. Preserve ordinary hero
icon/name/level rows. Label both bottom-action string references **Select**.
The primary Hire control must have a unique ID, separate from Research.
Never gate stock upgrade 0x1F47 or navigation. No custom art is required by this
interface. Runtime admission requires the paired-capable Manager build.

## Preserved stock boundaries

- `GPL/Building_Births.gpl::check_strays` and expansion equivalent enumerate
  heroes over the whole kingdom with `ListObjects` and `insideOtherUnits`.
  Queries additionally check live Type, HP, exact owner, title and minimum level.
  Presentation does not create attributes or reserve a hero.
- MX05 queues `(command, building handle, selected hero handle, quoted price)`.
  Hiring is free; the current one-agent action ABI is insufficient. Selection
  and execution must carry both identities, independent of the open panel.
- `use_building` owns travel, Hide, confirmed InsideBuilding, Occupants insertion
  and Visited_Script dispatch. The existing visitor remains the fallback for
  ordinary shoppers. Entry, not distance or selection, authorizes completion.
- `Mausoleum.gpl` calls CancelGuildMembership. `Unit_Dismissed` explicitly removes
  GPL Home.Members. Do not call dismissal wholesale: it exits and flees.
- `flee_map` supplies the nondeath removal order: quest-item handling,
  Waiting_to_die, KillThread(ActiveScript), DeleteGamePiece. Owner cleanup and
  explicit membership/occupant handling must be settled before removal.

Missing unlock state means locked, including older saves. Never synthesize a
past hire. Already-running research must complete normally; gates admit only
new actions. A saved building boolean is sufficient for the final unlock;
do not introduce a per-frame controller or native-pointer persistence.

## Acceptance boundaries

1. Paired dispatch preserves stock queued actor validation/payment and delivers
   building and selected hero to the callback on Public, beta2 and GOG.
2. Verify the integrated private stock travel continuation and saved-function
   restoration in game. Stock `reset_tasks` clears Target/ActiveScript/BackScript
   but **does not clear TaskName**; no label authorizes hiring.
3. Apply disabled presentation after stock refresh AND reject gated commands;
   disabled controls alone do not cancel pending dispatch. Do not affect upgrade.
4. Output/registry/source validation and three-version fixtures are connected;
   live acceptance remains separate from static evidence.

No in-game acceptance has been performed for this feature.

## Current integration checkpoint

The owner selected WSHR for the selector and 31300 for Hire; Research remains
8009. The supplied eligibility/cleanup functions and existing visitor were
checked together against the callback contract. The standalone generated queries
compile with the installed SDK compiler; this is not a merged profile build or
a native lifecycle verification. The MX05 limit remains 64 rows; pagination or
an explicit overflow presentation policy is still needed before promising an
unbounded kingdom roster.

The bounded queued-argument research request is recorded at
`../majesty-gold-hd-research/docs/intake/20261006-133752-manager-employment-paired-command.md`.
The first delivery failed with a tool path-deserialization error. The human
subsequently corrected routing to `01a107ce-7a27-79f0-975d-5e85dd46ad97` (local).
The same intake was delivered on October 6 at 17:19:59 UTC; acceptance does not
establish completion. Preserve that intake's historical failed-send record.

The owner's resource-only candidate is
`../majesty-gold-hd-custom-guild-witch-hunter/private/crucible-hire-resources-v1/hire-panel-resources.cam`,
SHA256 `2f32657161ed7dcedbda48e67518462f6f25dee6fe1e2d57098a3481dfae250f`.
It was independently read with the Manager CAM parser and checked by the existing
`_validate_mx05_live_agent_list_panel` stock validator. WSHR retains the native
selector shape; WSPN contains Hire31300 and Research8009. Removing only the added
Hire record reproduces the baseline WSPN records exactly. Hire geometry is
(7,162,93,26). `validate_panel_resources` exposes this same reusable validation
for development inputs without composing a profile. This verifies authored
resources, not runtime registry allocation or queued gameplay admission.

## Source lifecycle checkpoint

`lifecycle_source` now emits Select, Arrive and primary-command Admit functions.
It privately clones the destination dataset's `use_building`, `travel_to`,
`has_arrived` and `gettargetrange`. Only function identities/references and the
private visited continuation change. The range helper's exact comparison with
`use_building` must be privatized too, or building entry would use attack range.
The public functions and ordinary building Visited_Script are not replaced.

Select rechecks eligibility, exits an existing building against the old Target,
stops movement and resets tasks before assigning the new Target and private
continuation. The normal engine tasks own that destination; no per-hero custom
attribute, saved native pointer, polling timer or extra RunThread is added.
Normal cancellation through Reset_Tasks removes both private continuations.
Arbitrary other scripts modifying Target without honoring stock task ownership
are not treated as a verified cancellation mechanism.

Arrive requires the private ActiveScript/BackScript pair, a live target, actual
InsideBuilding and Occupants membership, then rechecks eligibility. A concurrent
completed hire causes the extra arrival to exit without consumption. Owner cleanup,
GPL/native membership removal and quest-item handling precede the stock
Waiting_to_die/KillThread/DeleteGamePiece ending. The saved unlock is set before
Occupants removal so its normal relation notification sees the completed state.

Admit constrains only the declared Hire and research-opener IDs, leaving upgrade
and all unrelated IDs to stock. It is connected to native input, queued research
admission and primary presentation; existing research is not changed.
Tests execute the emitted admission/entry code with
explicit stock API fixtures and compare the travel clone against both SDK source
datasets. Both isolated GPL variants compile. These are source/fixture checks,
not proof of native save/load or UI refresh acceptance.

## Paired native adapter checkpoint

The finalized research is `../majesty-gold-hd-research/docs/employment-pair-20261006.md`.
Its exact-image windows are retained in tests/fixtures/employment-command-profiles.json.
The three installed/fixture images and AddSubject/Execute ABI sites are checked
by tests/test_employment_command_profiles.py without launching the game.

runtime/PairedOccupantAction.h implements nested execution scope, ordered
Building/Hero append, null/rejected-building execution suppression, one execution
per matching evaluator, legacy single-argument passthrough, and a zero-price packet
gate. Its x86 fastcall shims preserve the original thiscall/RET4 argument boundary.
tests/Test-PairedOccupantAction.ps1 runs the standalone native adapter fixture,
source lifecycle fixtures and the mandatory three-image evidence checks.

Registry v23 admission, guarded hook installation, source generation, stock-event
roster refresh and native primary-panel gating are now integrated.
`handle-absence-20261006.md` supplies the additional read-side evidence: exact
category getter/service checks precede lookup, and an ordinary absent key returns
null. No generation-safe actor lifetime, exception recovery or native gameplay
acceptance is claimed.
# Optional travel activity text

Declarations may provide `travel_text` (nonempty Windows-1252, at most96 bytes,
no NUL), e.g. `Going to the workshop`. The Manager allocates it through the
existing private literal MMTX registry and emits stock `SpecifyIntent` after
assigning the selected hero's private travel functions. TaskName stays empty;
travel, interruption, cancellation and arrival ownership do not change. Omit
the field to retain existing behavior. No package-owned runtime ID is accepted.
