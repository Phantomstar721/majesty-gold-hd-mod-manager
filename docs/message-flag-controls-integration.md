# Message-flag controls integration — 2026-10-31

Current status (2026-11-01): first playtest identified the wrong SMNU loader hook.
The corrected quest-construction loader is implemented and deployed to the
canonical local test Manager; source and packaged validation are complete. Typed declaration and minimal-package admission are
unchanged. The original build below did not render the new controls.
Exact build receipt: artifacts/message-controls-integration-receipt.json.
In-game acceptance is still pending the user's test. The older dated
investigation sections below are retained as history, not current blockers.
Authority: user-approved request relayed by mod owner
019ff0f4-feb7-7260-97cd-b51b72f3fe63. Manager owns runtime/schema/profile work;
the mod owner owns its package and ongoing dismissal research. No research-chat
handoff is authorized for this task. Existing intake
majesty-gold-hd-research/docs/intake/20261031-message-flag-controls-lifecycle.md
is reused as context, not resent.

## Evidence and supported reuse

Consulted Knowledge Graph README and nodes engine_function.messageflag and
engine_function.ismessageflagpresent at graph commit
f2644580d33ad98703361cd8fc88c825068161ef, research shared-map and the mod's
docs/message-flag-controls-plan.md and docs/research.md. Graph assertions are
qualified static claims against aa9be61d...5db00, not validated addresses for
the installed modified Public image. Relevant source citations:
reading_audit_20261002 /readings/27/fields/semantics.effect (creation),
builtin_native_effects_20260923 /readings/60/fields/semantics.effect (presence),
reading_audit_20261002 /readings/20/fields/semantics.failure (null-list hazard).
Presence lookup is not a safe bulk-clear contract.

Manager already ships a guarded six-byte restore utility at
payload/qol/utilities/Suppress All Message Flags/scripts/Restore-SuppressAllMessageFlags.ps1.
Its profile, tail and owned-byte guards should be reused for a future explicit
migration; no whole-backup restore is needed. Read-only -DryRun on the installed
Steam root identifies the legacy patch at file offset 0x48A90. Beta2 and pristine
GOG fixtures report stock creation bytes. Their owned offsets are 0x499A0 and
0x498C0 respectively. No executable was changed. This establishes existing
patch detection only, not safe runtime hooks or dismissal parity.

docs/gog-qol.md documents synchronous speed/zoom preference persistence as the
applicable precedent. It does not establish a message-HUD or save-load callback.
src/majesty_cam/compact_sovereign_toolbar.py requires an owned building secondary
panel and a paid target action; it cannot represent global UI-only message
controls without misusing ownership and payment contracts.

## Proposed typed surface (not admitted)

Reserve the conceptual capability stock.message-flag-controls.v1. A declaration
would request the two fixed stock-style commands, not supply native addresses,
callbacks, file paths, arbitrary flag kinds, custom timers or arbitrary code.
Manager owns control IDs, persistence identity and executable profiles. MSGF is
the only affected kind; reward flags are excluded by construction. Default OFF
and global-last-state-wins follow the supplied plan. The user's subsequent
"saved doesnt matter at all" removes save-owned state, serialization and
automatic restored-flag cleanup from scope. Persist only the global preference.
Do not ship a mod-definition using this proposed type: it is intentionally not
registered until its full lifecycle has evidence on all three versions.

## Exact native blockers

1. Safe snapshot/enumeration of current MSGF IDs and stock queued-dismiss command
   timing. Repeated first-entry lookup is unsafe if removal is deferred.
2. Dismissal completion: relation observers, UI and camera tracking cleanup;
   stale-ID and already-deleting handling. Calling virtual cleanup directly is
   not established as equivalent to dispatching the stock command.
3. No saved-world cleanup or attachment callback is required. This former
   blocker was removed by the user's explicit scope change on October 31.
4. Actual owning in-quest HUD controller, control construction, dispatch,
   refresh and teardown on each executable. Building/paid-toolbar ownership is
   not transferable evidence. Lower-right layout remains provisional.
5. Independent Public/beta2/GOG guards for all of those paths, not merely the
   already-known constructor entry. Creation gating alone cannot fulfill ON.

The mod owner supplies stock dismissal evidence for items 1/2. HUD work proceeds
independently; load-time queue readiness is not an admission or acceptance gate.
Do not introduce polling, unsafe deletion, or an unsupported declaration.

## Attachment reuse decision and queue boundary audit

Historical evidence only: the later user scope change removes attachment-time
clearing from this feature. The unresolved load-time boundary below no longer
blocks in-quest controls and must not become a release requirement.

Follow-up evidence evaluated 2026-10-31 using the mod owner's updated plan and
Audit-MessageFlagLifecycle.py, independently rerun against the exact Public
SHA256 255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4.
Relevant reproduced span SHA256 values:

- accepted_save_attach_call: 97c02f56bdc08270b327c4e3b74a182ef482bf31f69ac7864275df10b8928705
- world_attach: c104ed9f6f5878ca2613e333954b633b6f512742a1656593560f4e9a906ac93f
- menu_save_attach_call: 69e41700ae4abd5bc2d9d91191dd86da999c8c0a8f4f251493e648f2bbacbadc
- queue_replacement_prefix: 2be079acc92c294bc4e027c5ce69d6ab9cdea178ebf2ddf4872563127693caeb

WorldAttachmentProfiles.h already distinguishes accepted saved and created
routes, rejects absent worlds, requires loader status zero plus identical output
world for both saved callers, and excludes modes 1/2. Reuse this classifier and
its guards rather than inventing another interpretation of the load routes.
However, AttackObservationRuntime.cpp's installation is conditional on an attack
proof/impact policy, native binding registration and checked-placement audited
startup. Its Attach callback invokes attack lifecycle reconciliation and placement
rebinding. Enabling that whole subsystem solely for message controls is not an
acceptable dependency. A future shared attachment notification needs separation
from those consumers while preserving their original ordering and guards.
This is an integration decision, not an implemented shared observer.

The reproduced Public attach return 4252C1 calls 45E5D0 then its virtual +40.
An additional bounded read of 45E5D0..45E65D shows that getter owns global
7C52FC, allocating through 45E500 and publishing via 59CE90. Command-service
getter 4D6FC0..4D702E instead owns global 7C18B8 and constructs through 4D6250.
Therefore the immediate post-attach service call cannot be treated as the
command-service readiness call. No semantic name or queue effect is asserted
for that other service's +40 without further evidence. The menu route at
494981 obtains the actual command service but only writes +258 locally; it
also supplies no local proof of +24 queue readiness.

New cleanup evidence narrows the earlier blocker: deferred command submission,
read-only census-before-dispatch, copied-ID notification and stock camera
fallback now have Public primary evidence. No immediate-delete loop is needed
or permitted. What remains unresolved is the ordering of queue replacement
5975D0 against attachment and first service processing, including modes/state
gates and whether a preexisting queue can be replaced before draining. Neither
nonnull queue storage nor accepted world identity settles that question.

Do not enqueue from Attach/reconciliation, force-drain, or add a pending-action
poller. Next permitted trace must connect the actual command-service invocation
sites/vtable dispatch to 5975D0 and 595BF0/595CD0, establishing an authoritative
readiness boundary. Then validate equivalent paths independently on beta2/GOG.
No load callback has been selected and no runtime mutation has been added.

## Independent HUD entry audit, October 31

The owner requested independent HUD investigation while it continues command
queue timing. Rechecked graph baseline f2644580d33ad98703361cd8fc88c825068161ef,
the two engine-function nodes above, shared-map checkpoint 12962 and spell-ui.md.
Those sources do not establish a global message-controls panel. Existing AP92
evidence in compact-sovereign-row-boundary.md establishes a paid building action
controller, not the requested global UI-only controls.

Bounded static inspection of the same exact Public image establishes that
4645A0 is NOT a callable UI-handler entry: it is an interior case of 464000.
The dispatcher reads a value returned by 4639A0, subtracts 8, bounds it at 76h,
and uses byte table 464748 followed by pointer table 46471C. Selector values
96 and 126 map to case 8, whose target at 46473C is 4645A0. The case eventually
uses the shared epilogue 4646F4..464718 and the dispatcher's stack/register
state. It must not be installed or called as an independent button callback.
No keyboard meaning is asserted for those selector values without tracing the
producer. SHA256 of dispatcher bytes [464000,46471B):
35b1000e9cbe367ede835c314378014cdd0314ccb89112c72198829eed1c9733.

This provides a concrete distinction between the stock dismissal command
factory and its input-dispatch caller. It does not yet identify a HUD panel
constructor, control ownership, refresh or teardown. Next UI-only boundary is
the caller/registration of 464000 and producer 4639A0, plus the actual in-quest
panel construction path; do not infer a panel lifetime from this switch.
Beta2/GOG HUD mappings and the two-control typed runtime surface remain
unadmitted. No executable, package, runtime or profile was modified by this audit.

## Current scope and APMK controller evidence

User scope change relayed by owner 019ff0f4-feb7-7260-97cd-b51b72f3fe63:
"saved doesnt matter at all". No save serialization, automatic restored-flag
cleanup, attachment hook or load-time queue-readiness gate is required. Retain
global preference across process restarts, ON clearing current MSGFs and gating
new creation, OFF restoring future creation, an independent clear command,
reward-flag exclusion and all-three-profile parity. Ordinary commands retain
stock queued execution; submission does not mean completed dismissal.

The relevant stock resource is **APMK**, not AP92. Actual installed textdata.cam
STRT identifies its main map, minimap, tracking windows, ordinary display
toggles and options control. Its SMNU includes stock toggle class 1 and command
class 0 controls. No art has been generated or selected for the new buttons.

`scripts/audit_message_flag_hud.py` now reproduces exact-image-gated linkage
independently on all three available fixtures. Each APMK-specific UI factory
branch allocates 34h bytes, calls the constructor below, and that constructor
installs the shown nine-slot controller table. This is UI construction evidence,
not actor construction or a license to expand excluded actor research.

| Profile | APMK factory branch | Constructor | Vtable | Setup | Command | Hover | Event |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Public | 50BFD3 | 46A780 | 73BD78 | 4698E0 | 469C90 | 46A600 | 46A2B0 |
| beta2 | 51C523 | 46B9C0 | 754E70 | 46AB20 | 46AED0 | 46B840 | 46B4F0 |
| GOG | 50E433 | 46B8E0 | 753EC0 | 46AA40 | 46ADF0 | 46B760 | 46B410 |

Constructor-span SHA256, 15Dh bytes through `ret 8`:

- Public: a52669012fe06c9077067ff0be082793b364ccae9c6000a1e30d85433c861e51
- beta2: d4c8d5a81bedc4501f9f798984dc4ca238c584611905c43dcaec0e34f7324043
- GOG: 290da4fb8619922786840d73ed03ab86ff4446efb109f8e6a1476ad8431b9272

The installed Public command/hover entries are already detoured by the shipped
Lower Tracking Window utility. Its PatchCommon.ps1 independently identifies the
same command/hover entries for all three versions. Future managed-vtable
integration must retain those existing entries as fallback, not overwrite or
skip their owned QoL behavior. ControllerLifecycleRegistry is the existing
exact-instance teardown mechanism; its use still requires verifying the APMK
ordinary destructor and capture ordering.

**Concrete remaining UI boundary:** the installed game has 13 resolution-specific
`Data/UIData_*.dat` resources. The Lower Tracking Window utility edits their
APMK records, rather than only textdata.cam. Public routine 4F0BC0 formats
`UIData_%d_%d.dat` from two display values, obtains a resource handle, and on
the existing-handle branch at 4F0CF1 calls resource-manager virtual +24 then
+2C with the handle and decremented result. The alternate branch uses virtual
+70 and stores a handle at owner+34, retiring an earlier handle via +74.
Resource ordering semantics and the point at which a generated package can
extend the effective APMK safely have not yet been established. Merely appending
buttons to textdata.cam is therefore not a verified implementation. No stock
UIData files should be rewritten as a shortcut.

Next bounded trace is those resource-manager methods and their call ordering
relative to package resource registration, or the stock streamed-dialog child
creation entry if resource precedence cannot supply the controls. Reuse the
actual resolution layout, retain QoL-owned controls and stock teardown, and
verify toggle refresh on setup/click. These UI requirements remain; the removed
saved-world requirement must not be reinstated. No declaration is admitted and
there is no testable package contract yet.

## November 1: resolution precedence resolved; initial-reader route identified

Reconsulted graph f2644580d33ad98703361cd8fc88c825068161ef and research map
checkpoint 13136. Applicable primary records are resource-acquire-contract.md,
archive-context-order.md, archive-close-caller.md, smnu-buffer-lifetime.md and
its seven guarded definitions. The control-clone-family record establishes
allocation/copy requests only, not source aliasing or complete child ownership;
it is not sufficient authority to clone a live control into a second parent.

The independent exact-image audit now links the resource singleton constructor
to its table and all four relevant slots on every profile:

| Profile | Table | +24 count | +2C move | +70 open | +74 close |
| --- | --- | --- | --- | --- | --- |
| Public | 74AE8C | 623280 | 625660 | 6270E0 | 624E40 |
| beta2 | 765FC4 | 642E00 | 6451E0 | 646C60 | 6449C0 |
| GOG | 763E1C | 637B70 | 639F50 | 63B9D0 | 639730 |

The full count method (15 bytes) and full move method (338h bytes) have matching
instruction/CFG signatures across these three exact fixtures after independently
identifying their entries. Normalization retains constants, internal branch
offsets and repeated external-address identity; it does not certify external
callees. The move method finds the descriptor whose +4 equals the supplied
context, shifts intervening pointers, writes the saved descriptor at the
requested index, and returns that index; absent context returns FFFFFFFF.
For the UI loader's count-1 destination this promotes the active resolution
archive to the last vector position. Combined with reverse acquisition search,
an earlier generated APMK resource cannot reliably override that layout.

Move-body SHA256:
- Public: 4a55b7c774d421441d873fc3e98b5901822297482c3cada63d13ae3e33f5faf7
- beta2: cd4d109982a25371efa546450413d38764971943beb73a9611017a7e1a937282
- GOG: 30748f9d7305eb9cfbe2dae442f4a4ef5acc669df112cf9dd358695a709c20ce

**Integration decision:** use the selected APMK stream before its first stock
read/finalization, rather than reopen/reorder archives, rewrite UIData files,
clone already-live controls or rerun finalizers over existing children. This
preserves the selected resolution and Lower Tracking Window's modified record.
Native child creation/insertion/finalization remain in their original order.

The initial SMNU loader is independently identified at Public6515C0,
beta2 666A20, GOG666EA0. Its entire 131-byte body matches the qualified existing
research contract and equivalent normalized instructions on all three images:
acquire selected SMNU; lock its handle; initialize a temporary {base,cursor};
call object virtual+8 once; unlock original handle; release original handle.
Public's virtual+8 call is651611, with reader address from ESP+8 and menu object
inEDI. Resource key is the second explicit loader argument. No extra native
finalization call or replacement parent ownership is justified.

Loader SHA256:
- Public: 60185cdf9ce577db99c805b2278f8ce1237fb3340665ff8ce9d7b96ee6a6bdce
- beta2: 91514231ed1f3f9d008ce3588a8969fa8dbc0067fd582eb2f657459791d9505b
- GOG: 3d6790cd5cd8ed36244846361ca57a79113dac1e71e2834a554836a8cd4941fd

Read-only layout inventory found APMK in the twelve installed UIData layouts
above800x600; UIData_800_600.dat has no APMK and needs the stock fallback.
Do not require every UIData file to contain APMK. The selected-stream approach
handles either source; the base textdata APMK is already identified.

Remaining implementation is explicit: bounded selected-stream augmentation,
its temporary-buffer ownership/error behavior, initial-read hook, APMK managed
controller setup/command/hover/teardown integration, global preference and
MSGF-only stock command backend. Do not admit the capability merely because
the controller and stream entries now have three-profile guards. There is no
user decision required by this evidence and no new saved-world dependency.
The runtime has not been wired or deployed; package admission remains closed.

The mod owner's supplied Audit-DismissCommandProfiles.py has been read. Its
factory/constructor/handler guards are the source for the backend's bounded
command contract; its explicit lack of all-profile queue/camera/persistence
proof is retained. No research-thread request was sent.

## November 1 integration

Contract: docs/message-flag-controls-contract.md. MMFRv13 flag256 selects
stock.message-flag-controls.v1; MMCP must agree. The native feature owns no CAM
or GPL resources, so its schema-v3 two-file package is admitted without either.
The native dispatcher gates the selected stream, exact APMK instance and shared
pre-setup capture. Existing commands/hover/event/destructor continue to stock.

Native checks execute the production code with bounded test doubles: census
before stock submission, MSGF filtering, deleting/stale rejection, no scan from
setup or OFF, preference write/reload, independent clear, old-instance teardown,
creation ON/OFF forwarding, non-APMK original loading and acquire/read/unlock/
release ordering. Production profile constants are checked against all three
exact images, including the installed Public legacy suppression patch. Raw HUD
layout checks cover existing base and resolution APMK resources; an800x600
UIData file need not contain APMK because stock falls back to textdata.

Evidence: artifacts/message-controls-profile-audit.json,
artifacts/message-controls-package-contract.json, local/regression/development-source.json,
and artifacts/message-controls-manager-build.log. The package-contract receipt
reads the owner's actual source package and records its two hashes and MMFR;
it does not construct a Manager profile. Graph baseline remains
f2644580d33ad98703361cd8fc88c825068161ef and the source citations above apply.
Native live acceptance remains outstanding; queued submission is not evidence
that every command completed in a running quest. No save-owned state or load-time
queue behavior is added.

Build-environment corrections: use the existing shared Capstone dependency;
use the canonical Build-Runtime -FeatureTests source list (the old standalone
PanelLifecycle test wrapper omits newer runtime dependencies). The subscribed
MK art fixture changed to SHA2568f776b1329c550ec613679e83708535948149961bb3786679047dcc4f211f6cf.
Its original BBT1 regression witness remains at the independently documented
offsets2344..2504, with unchanged zero XY and2508..2544 event bytes. The fixture
test now admits both recorded archive revisions and verifies those raw fields
plus byte-identical standalone composed BBT1, preserving both original regression
coverage and current installed-package coverage. No production art behavior changed.

## First playtest: missing buttons, November 1

The reported screenshot contains Options but no private controls. Read-only
inspection confirms selected MMFRv13 flags0x1FF and MMCP message-controls, plus
the exact original candidate DLL937be2fb...f1d51c2. It is not missing package
admission. The launch log records APMK creation but the first candidate had no
feature-specific construction logging.

Root cause: the hook used the **already-constructed MenuObject** reader at
Public6515C0/beta666A20/GOG666EA0, not the quest HUD's **menu-construction** reader.
Production quest creation at Public425910 requests a menu through4B4A00's
provider, then creates the APMK controller and invokes its setup. The relevant
menu provider path4B6A20→4B3F80 calls638A20 at4B3FCD, supplying(context=0,
key,mode=1,flags=1). It does not call6515C0.

Actual construction loaders: Public638A20, beta64DE70, GOG64D360. Each is166
bytes and has equivalent complete normalized instruction structure, with
profile-specific calls and RET16. They first request preparation(0), acquire
SMNU, lock its buffer, call the construction primitive with
(reader,context,key,mode,flags), write key to result+2C when nonnull, unlock,
reacquire the manager and release the original handle. The replacement preserves
that sequence and returns the constructed pointer rather than a Boolean.
Per-build prepare/read pairs are646300/637EE0,65B760/64D330,65AC50/64C820.
Evidence: artifacts/message-controls-quest-loader-audit.json. No actor,
exception-handler or shared backend implementation was reopened.

The old native test exercised the wrapper directly and therefore missed the
unconnected call path. Regression now checks real quest-constructor CALL sites
4B3FCD/4B48BD/4B4EBD, their argument sequence and the full loader hashes, as well
as forwarding four original arguments, the result pointer and result+2C.
Lifecycle logging is limited to installation, HUD construction and setup;
there is no repeated unit tracing. Existing merged data needs no change.

Public executable changed independently during this playtest to SHA256
1657fa3a3e16103c78708efc768cd69f7272cb2ade97cf659db20719e5579909. Replacing only
its six restored stock creation bytes with the previously recorded suppression
bytes reproduces the original255957fb...E40B4 hash exactly. Both are the same
audited image with that supported utility state difference, not a new branch.

## Second playtest: clear rejected, November 1

Buttons and dispatch are now observed in game. The 21:56 launch log records
construction/setup and repeated clear rejection, but the old message did not
identify which guard failed. It does not establish a submission or pause fault.

Static review identified a definite omission: Clear admitted GE_AllUnitsList
only, repeating the previously corrected stock AllUnitsList admission issue
in docs/hunter-settlement-boundary-20261008.md. Reuse the existing
PairedOccupantLookupProfiles.h exact tables (Public73A4FC, beta7535BC,
GOG752604); require both lookup+28 and enumerate+30 slots equal the guarded
GE methods before installation. No arbitrary class is admitted. Native tests
exercise both concrete admitted classes and reject an unknown class, missing
world and missing category. Profile tests compare both method slots in all
three actual binaries. No new factory/cleanup research is involved.

Consulted graph engine_function.messageflag at f2644580d33ad98703361cd8fc88c825068161ef
(behavior unknown; registrar citation0x00434365/0x0056bce0), research shared-map
checkpoint13338, world-query-functions.md and level-catalog-ownership.md.
Public stock UI4645A0 corroborates runtimeGlobal+4 world ownership; getter5A15D0
uses thiscall(category), enumerator5CE900 uses thiscall(callback,word1,word2)
and cdecl callback; command4C4790 uses cdecl(world,unit,word). These existing
boundaries were compared directly, not inferred from mocks. Their call ABI
matches the implementation. The false exit from the reported invocation is
not retrospectively known: the corrected build records a specific failure
stage or one census/queued summary per explicit click. No continuous tracing
or additional census was introduced; queued is not a claim of completed deletion.
Evidence: artifacts/message-controls-clear-native.log and
artifacts/message-controls-clear-python.log. In-game clear acceptance pending.
