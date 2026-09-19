# Kingdom research and conditional earned rewards: stock boundary audit

Status: **implemented for local beta2 testing; in-game acceptance still required**.
The [test-build author contract](kingdom-research-contract.md) describes the
declaration and literal panel resources. This audit
identifies why the existing building-research recipe cannot safely promise a
kingdom-owned, saved purchase or a general earned-income multiplier. A custom
extension was explicitly approved by the user through the owning content task
on 2026-09-18. That approval covers saved kingdom research, controller integration
and fractional earned-reward accounting, not a watcher or arbitrary Gold hook.

## Requested generic behavior

A package-defined research purchase is made once per owner, persists after the
researching building is lost, and remains recorded across save/load. Its benefit
is available only while that owner has a living, completed building of the
declared family and required level. Multiple buildings neither stack the benefit
nor permit duplicate/concurrent purchases. A percentage modifier applies once to
eligible heroes' actual gold and XP earnings, preserving payer costs and stock
XP level processing. Repeated small awards retain fractional bonus credit.

This is not a timed combat effector and has no Rage/Krolm lifecycle.

## Examined references

- Installed beta2 MajestyHD.exe 1.5.2.28, PE timestamp `0x5A8A11D5`;
  addresses below are preferred VAs at image base `0x00400000`.
- Stock `SDK/OriginalQuests/GPLMx`, especially
  `TaskModules/Subtasks/mx_give_exp.gpl`, `mx_Monster_Deaths.gpl`,
  `mx_LowLevel.gpl`, and the stock callers of `give_gold`.
- Manager `stock_controller_features.py`, `stock_controller_registry.py`,
  `runtime/MajestyModManagerRuntime.cpp`, and the documented AP52 recruitment
  and AP10/AP69 research contracts.

No live game or selected merged profile was modified for this audit.

## Stock research: reuse points and ownership mismatch

1. **Descriptor construction/ownership.** AP99 owns a registry of five-dword
   descriptors: duration, minimum building level, price, name, completion
   attribute. Its resolver is `0x004A8FD0`. The Manager's
   `ResolvePrivateResearchDescriptor` allocates using Majesty's allocator and
   copies an existing descriptor. It replaces level/price and copies the
   completion attribute from `completion_template_control_id`. The registry
   owns descriptor cleanup; the Manager re-registers after the registry is
   reconstructed. This privatizes a command, **not its completion storage**.
2. **UI dispatch/payment submission.** AP99 click handler `0x004A94C0` resolves
   the building context, checks affordability through `0x004A9430`, and submits
   through `0x004C36A0`. That function constructs a `0x3ED` queued command
   (`0x004C33B0`) and hands it to the existing command queue. This is a useful
   reuse boundary, but does not establish a kingdom-wide purchase reservation.
   The complete queued debit and saved order boundary are traced in the
   follow-up section below.
3. **Timing/context.** Stock research uses the building's `CurrentResearch`
   (`0x2C425041`), start time (`0x38425041`) and duration (`0x0D425041`).
   The current AP10 coexistence adapter captures this tuple in one process-global
   `ResearchOwner`, restores the building's recruitment tuple, and temporarily
   restores the research tuple at stock completion. That pointer-based singleton
   is not a serialized per-kingdom research ledger, nor a general AP52 ownership
   contract. Do not extend this singleton into a claimed saved kingdom purchase.
4. **Completion.** Native event `0x2009` reaches `0x004E0430`. At
   `0x004E0466..0x004E048F`, it reads CurrentResearch from the supplied building,
   resolves the descriptor and calls that **same building's** attribute setter
   with descriptor word 4 and value 1. It does not write an owner's research
   record. Following the native announcement/UI work, `0x004E0640..0x004E0664`
   clears CurrentResearch and duration on that building.
5. **Refresh.** The existing adapter invokes native row refresh
   `0x004A9160`/`0x004A93D0` and observes the native completion callback. Its
   supported parent/child class path is AP10/AP69. AP52's current recruitment
   child retains the literal AP52 allocation and 17-slot vtable; simply attaching
   AP99 controls or changing the feature validator is not proof of valid dispatch
   or activity ownership on that controller.
6. **Persistence/cancellation limit.** The observed completion belongs to an
   individual building. The current feature contains no independently saved
   owner completion/reservation record and no fractional-reward state. This
   audit does not certify save/load, building destruction or cancellation for a
   new combined controller. Those are required work, not implicit guarantees
   from reusing AP99 widgets.

In particular, selecting an unused stock completion template or borrowing an
existing package's template does not solve the ownership mismatch. No existing
`stock.ap99-research-row.v1` field expresses the requested saved owner state.

## Earned rewards: use the stock scripted settlement boundary

The producer audit narrows gold integration to the existing scripted
`mx_Monster_Deaths.gpl::give_gold` boundary. A case-insensitive check of stock
GPLMx confirms these routes; there is no need to introduce a native `GiveGold`
or positive-attribute hook for these producers:

| Producer | Final settlement route |
| --- | --- |
| Monster/lair loot and attack bounties | `dropgoldinradius` splits the original pool, then calls `give_gold` per recipient |
| Explore bounties | `dropgoldinradius_sameplayer` preserves its owner filter, splits, then calls `give_gold` |
| Destroyed-building loot | Stock death routes call `dropgoldinradius` or `dropgoldeveryone`, each settling via `give_gold` |
| Chest opening | `Open_Chest` clears the chest gold and deletes the chest before `Give_Gold` |
| Rogue theft | `Steal` debits the target before `Give_Gold` |
| Elf marketplace/inn performances | Stock completion routines pay through `Give_Gold` |
| Off-map quests, Fairgrounds and gambling wins | Stock completion routines pay through `give_gold`/`Give_Gold` |

Gold modification belongs inside the existing positive-amount branch, before
both the `got_gold` display and carried-Gold write, exactly once per recipient.
Preserve the stock display/write/log order. Do not adjust the original pool,
the payer debit, a deferred entitlement, or each stage of a job. Deferred jobs
must settle through this helper only when their original ledger is paid.

`give_gold` also serves `mx_collect_tax.gpl`, `mx_Monster_Steal.gpl` and
`mx_Auto_Revenue.gpl`. Require the recipient's stock `subtype == Hero` **and**
that recipient owner's active research; pass all other recipients through
unchanged. Do not whitelist stock hero titles: that would exclude custom heroes.
Stock loot code already uses this Hero-subtype classification.

`mx_LowLevel.gpl::Transfer_Gold` debits one agent and credits another via ordinary
Gold adjustments. `Spend_Gold` spends stored gold before carried gold and credits
the building's taxed share using the same attribute operation. The resulting
positive write has no built-in parameter saying "new earnings" versus "transfer".
A universal positive-Gold hook cannot infer that distinction safely.

Custom jobs that settle genuine earnings through stock `give_gold` can share
this same guarded integration. Jobs that write Gold directly cannot be promised
automatic coverage; their authors must use the declared settlement boundary.
Conversely, mods must not route refunds/transfers through this earnings helper
and expect the reward modifier to recover their unstated intent. The verified
stock boundary removes the need to intercept each known producer separately;
it does not eliminate the saved research/eligibility and fractional-accounting
requirements below.

## XP and rounding

`TaskModules/Subtasks/mx_give_exp.gpl::give_exp` first divides the integer award
by current hero level, adds it to accumulated XP, then runs the existing
level-up loop, callbacks/effectors, voice and stat updates before writing the
remaining XP. `advance_to_level` is a separate direct-level operation and must
not become an earned-XP bonus path.

No percentage modifier or fractional bonus carry exists in that examined stock
helper. A 15% bonus rounded independently on each 1-point reward becomes zero
forever. Retaining those fractions requires additional persistent bookkeeping
with explicit recipient/owner, lifetime and save rules. Its interaction with
the stock level divisor must be specified; changing the divisor's existing
rounding would be a separate gameplay change.

## Approved extension and remaining validation

No exact stock mechanism satisfying the **combined** owner-persistent purchase,
conditional building availability and classified fractional earnings behavior
was identified. The AP99 purchase presentation and command/completion lifecycle
remain the reference for the parts they actually supply; they are insufficient
as a literal clone for the additional state and reward semantics.

The approved extension covers:

- Namespaced, saved owner research state and duplicate-purchase protection,
  independent of the originating building.
- AP52-compatible research dispatch and activity ownership while preserving its
  recruitment and low-resolution panel lifecycle.
- An explicit earned-reward boundary with persistent fractional bonus accounting
  and building eligibility, without a background watcher, replacement controller,
  or blanket Gold-write interception.

The new `manager.kingdom-research.v1` test-build contract is separate from the
existing building-owned research row. It supplies a saved owner ledger and
literal primary-panel resource group. Package authors bind the declaration and
resources, not custom payment, reward or native-hook code. Purchase, completion,
cancellation, ownership changes, building loss and save/load still require
in-game acceptance; the static audit and compiler checks are not that evidence.

## Follow-up native trace for the approved implementation

- Queued research reaches order-processor virtual entry `0x00758E1C`, whose
  stock target is `0x004E02F0`. The routine rejects an existing `(1, 0x4005)`
  order, resolves the descriptor and obtains the building owner's player record.
  It applies the stock price calculation, checks/debits treasury attribute
  `0x00505041`, records expenditure at player `+0x164`, writes the building's
  command/start/duration, then schedules callback `0x2009`, order `0x4005`.
  A private pre-dispatch gate can reject duplicate purchases before this debit;
  the stock routine must remain the sole debit/scheduling owner.
- Recruitment uses order `0x4002`, callback `0x2006`, but shares the building's
  start/duration tuple. `0x0044E000` already rejects a positive pending duration.
  Private research must reciprocally reject a busy duration at execution, not
  merely disable its UI. This serializes recruitment/research through stock
  activity state; no process-global captured tuple is appropriate here.
- Shared AP52 recruit presenter `0x00496AF0` reads the pending duration and,
  when nonzero, treats attribute `0x0E425041` as a produced unit description.
  A research duration cannot be passed to that recruitment-only path. Its
  private presentation adapter must handle the declared research activity
  explicitly while preserving the stock presenter otherwise.
- Stock order save `0x006118B0` writes duration, type, owner/start fields,
  flags and callback payload; read `0x00611820` restores the same versioned
  fields and payload. Keep the original scheduled order in those structures.
  Added completion/fraction state uses saved GPL attributes, not pointers
  in a DLL or an external save sidecar.

## Implemented boundary and safety checks

- A private-command gate wraps the stock queued executor. It reserves the
  original paying player in saved `GplAIRoot` attributes, then invokes the
  original sole debit/scheduling owner. Submission failure releases that
  reservation; the extension neither debits nor refunds gold.
- Native completion reason 2 runs stock first, then records the original payer's
  purchase and refreshes the live primary row. The descriptor's private
  completion attribute is only a display mirror, not purchase ownership.
- Stock AP99 ignores cancellation reason 1. For the declared private command
  only, the adapter releases the saved reservation and clears CurrentResearch,
  then duration, through the ordinary native setters. The existing order manager
  retains destruction/cleanup. No replacement timer or order is created.
- Eligibility is resolved against the native three-byte building family,
  required stage, FirstStageBuilt and CurrentStageBuilt. A DAT title alone does
  not prove completion. Building queries use the declared GPL title as a filter,
  then revalidate the native family and completion state.
- Only positive borrowed-building cache entries are retained; each is checked
  again when an award settles. Saved per-hero fractions preserve small awards.
  There is no per-frame update, background scan or per-unit watcher.
- The beta2 profile validates full audited executor/completion/get-order/raw-set
  function bytes and the existing scalar GPL-call ABI before installing hooks.
  The research gate and generated GPL service are absent when unselected.

## Reward arithmetic correction (2026-09-19)

The first generated `MM_KR_CapAdd` incorrectly assumed ordinary signed 32-bit
GPL expression arithmetic. This was a Manager service bug, including when the
research was unpurchased or the recipient ineligible: a zero bonus still passed
through the faulty overflow check.

The installed beta2 executable establishes the actual behavior:

- `GplInteger` vtable `0x0076034C`, operator dispatcher `0x0059A860`.
- Integer storage accessor `0x0059A710` and scalar getter `0x0059A730` retain
  the full signed integer. Assignment uses the scalar getter.
- Conversion accessor `0x0059A850` shifts left by 10. Integer binary addition
  (`0x0059AB78`) and subtraction (`0x0059ABD2`) convert both operands through
  this fixed-point representation, then arithmetic-shift the result right 10.
- Greater-than (`0x0059AA95`) also compares converted operands. Consequently
  `2147483647 - 5` evaluates to `-6`, and `0 > -6` incorrectly selects the
  saturation branch. Returning the literal then retains `2147483647`.

The isolated stock-compiler fixture confirms the literal is encoded as an
integer, not a floating-point parsing error. Executable-byte regression checks
pin the traced operator instructions; x86 callback tests exercise the replacement
through GPL-shaped integer argument and in/out-storage slots.

`MM_KR_CapAdd` and fractional `MM_KR_AwardBonus` now register as native helpers
only alongside selected kingdom research. They compute in 64-bit intermediates,
bound the result to signed integer storage, and return zero additional reward
for nonpositive bases or invalid bonus inputs. Generated GPL retains eligibility,
the saved per-hero carry, and the original gold/XP settlement boundaries. It no
longer performs large-value comparison, multiplication or overflow arithmetic.

This does not change Majesty's global expression evaluator, stock XP divisor,
level-up processing or existing numerical limits outside this service. Nor does
it reconstruct gold/XP already corrupted in a saved game. Acceptance should use
a fresh game or a save from before the faulty reward service ran.

## Optional active-effector event adapter (2026-09-19)

The user approved this narrowly scoped native adapter after the audit established
that a one-shot spell cast cannot by itself cover later construction and owner
changes. Research/readiness state remains authoritative. No additional scheduler,
polling loop, marker agent, saved native pointer or sidecar ledger is introduced.

### Stock references and lifecycle

- `M_Overlays.xml/super_charge_effector` supplies the literal directionless,
  nonblocking root-attached Overlay, menu 11, StackPriority 0 and mouse-transparent
  flags. Its own artwork is privatized, and the requested silent variant uses
  DefaultSound 0. The validator compares the complete descriptor shape, not
  merely a few favorable flags.
- `DoWizTowerEnchant` uses `CreateEffector(unit, name, 1, "Infinite")`; the
  associated cancellation uses `DeleteEffector`. The adapter copies that
  attached-effector ownership, not the tower's unrelated active-script thread.
  Super Charge's one-shot building query is the reference for completion fanout.
- `ListObjects` predicate `0x439C80` explicitly excludes the originating native
  unit (`0x439CC2..0x439CCA`). A research completion originates from a building,
  unlike the stock spell caster, so the fanout must reconcile that building
  explicitly before querying the others. The 2026-09-19 paused capture had a
  completed level-3 building, payer 0 in the saved completion ledger, and no
  attached overlays; it was the only qualifying building and the query skipped
  itself. The generated callback now applies the same owner-checked, idempotent
  visual operation to its origin, then retains the stock query for other units.
- Native creation `0x005DE840` resolves the Description, creates the native
  child and attaches it through `0x005BE330` to the parent's `+0xA4` container
  (`0x005DE908..0x005DE912`). The stock Check/GetEffector paths
  `0x005DE790/0x005DE7B0` query this same container by description ID.
- `BuildingReachedMaxHP` in `mx_Building_Births.gpl` upgrades the GPL attributes
  first, then writes HP, CurrentStageBuilt and FirstStageBuilt, in that order.
  Native building setter `0x00449950` stores and dispatches stock notifications
  before returning. The adapter wraps its BuildingRec vtable slot
  `0x007531E8` and reconciles only the two readiness attributes, after stock.
  `0x0043AF70` clears CurrentStageBuilt when starting an upgrade, so a qualifying
  stage number alone cannot keep an effect active while under construction.
- Native `SetUnitPlayerNumber` calls the owner virtual at `0x00433030`.
  BuildingRec slot `0x007530E4` points to `0x005CF320`, which commits `unit+0x80`
  and performs its stock notification before returning. The adapter runs after
  that original method, only when ownership actually changed. Construction
  previews, retired units and unfinished first-stage objects cannot call GPL.
- Building destruction `0x00448400` reaches the common retirement path
  `0x005CF4D0`. It marks the unit retired, releases its GPL binding through
  `0x005CF6C0`, and calls virtual `+0x1DC`: `0x005CF2D0` forwards the owned
  `+0xA4` container to `0x005BDD90`. The Manager does not call a freed agent or
  add another death/cleanup owner.

### Save-load boundary

The container's `ConvertToPointers` routine is **not** a safe reconciliation
hook: stock also calls it during saving after temporary ID conversion. The
actual container read (`0x005BE0B0`, called by `0x005EA320`) is still too early
to run arbitrary scripts against the whole restored world.

The selected boundary is the existing state-2 initialization call at
`0x00426234 -> 0x0042AAB0`. State dispatch `0x004261F0`, table entry
`0x004262C8`, identifies this separately from the state-3 simulation update.
Native loaded-world installation (`0x00425C90`) schedules state 2 after installing
the world. Initialization conditionally calls `0x0042A540` / `InitializeGpl` for
a **new** game; the saved-game branch retains restored GPL state instead.
Both branches join at `0x0042ACA8`, finalize the native worlds, then request
state 3 at `0x0042ACCC..0x0042ACD4`.

The adapter calls this original initializer first and reconciles afterwards.
It borrows the same category-zero building collection and traversal used by
`0x0042A6BD..0x0042A799`: root `0x007E3FD4 -> +4`, world `+0x8C`, stock lookup
`0x005B9030(catalog, 0, 0)`, list sentinel `+0x20`, node next `+0`, unit `+0x0C`.
Only declared families invoke their generated callback. No references persist
after this one pass. Existing correct effects are kept; missing effects are
created and ineligible effects removed through the stock operations.

### Boundary checks and remaining acceptance

Before hook installation the native profile validates the full readiness/owner
setter bytes, building-list lookup, initialization join, original vtable entries
and state-2 call target. Effect-free v5 records do not select these extra sites.
Python/native MMFR v6 readers reject malformed names, truncation and v6 records
with no selected visual. Offline x86 fixtures exercise stock-first readiness and
ownership adapters, preview/death/foreign-family exclusion and the sentinel list
walk; a stock-compiler fixture covers the generated effector/completion GPL.
These checks are not a substitute for the purchase/rebuild/transfer/save-load
acceptance sequence in the live game, which remains pending for this adapter.
