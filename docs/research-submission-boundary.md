# Private research submission boundary

## Saved activity correction (2026-10-03)

### Follow-up: busy presentation and menu teardown

The 08:45:32 runtime log terminated at descriptor validation while cancelling
research after parent/child UI teardown. The completion adapter incorrectly
required the reason-2 descriptor on reason 1. All three executable callbacks
branch around descriptor lookup for reasons other than 2. The adapter now
validates registration only for success, retaining the existing cancellation
clearing order without reinitializing a registry during teardown. A native
fixture cancels after removing all private descriptors and the resolver.

AP10 activity retains its native idle presenter. While a private research command
owns the tuple, command 8008 is disabled and its price/progress/caption controls
8017/8022/8023 are hidden, without forcing a hidden service-building row visible.
The same IDs are verified in all three stock AP10 activity bodies. After successful
completion, the existing game-update bridge refreshes the still-live parent once
the completion suppression has ended.

The child now includes the shared duration attribute in its existing building-event
refresh filter, since recruitment does not update CurrentResearch. Stock row
eligibility runs before the busy overlay, restoring available research on idle
without enabling already-completed research. No new timer, polling loop or saved
state is introduced. Actual save/reload/menu-exit acceptance remains a user test.

Private AP99 research now uses the stock building's CurrentResearch/start/duration
fields throughout its lifetime. Recruitment and research are serialized per
building, as explicitly approved by the user. Submission no longer clears a busy
tuple; queued execution repeats the busy and completion checks before stock
payment. Accepted research is never moved into a DLL-only owner or overwritten
with the earlier recruitment tuple. The remaining pending record is only an
unaccepted UI request, not the owner of a scheduled research job.

Presentation and completion resolve the saved command rather than a process-local
active flag. Stock event 0x2009 still owns success, notifications and retirement.
Declared private cancellation uses the existing kingdom-research adapter's
command-then-duration clearing order; it introduces no refund or replacement
job. Original stock-only research continues through its original route.

The same guarded research executor, scheduler and completion profiles apply to
default Steam, beta2 and GOG. Native fixtures cover submission while recruiting,
the intervening queued-recruitment race, accepted tuple retention, DLL-state loss,
completion and cancellation. These are not live save/load acceptance results.

The source audit found the AP99 consumer in Alchemist Lab and Witch Hunter's
Silver Workshop. Bard's kingdom research already serializes through its separate
saved-state path. The current Phantom, Adventurer, Zoo and standalone Troubadour
sources do not declare this AP99 feature. No consumer declaration changes are
required by the correction.

An older save with order 0x4005 but CurrentResearch=0 is already missing its
research identity. This correction does not infer a recipe from duration or award
completion by guessing. DJ2 recovery remains a separate, unresolved migration.
The historical capture/restore descriptions below are superseded by this section.

2026-10-03; bounded offline audit and native fixture execution. V12 consumer
source, gameplay data, controls and presentation remain unchanged.

## Proven gap and narrow change

`BeginPrivateResearch` is reached directly by the private controller command
handler. The previous body checked pending/active ownership and called native
AP99 affordability, but did not read completion. A fixture calling that actual
handler with completion=1, no pending/active owner, and an affordable player
reached the real provider submission wrapper. The historical witness is
`artifacts/research-boundary-before.log` and its fixture executable.

Stock row presentation disables a nonzero completion attribute. The native click
helper checks affordability only. The research executor checks order 0x4005 and
owner affordability; it has no completion check. Thus a stale private command
that reaches this boundary could queue again; if processed with no existing
research order, the native executor would debit again. This establishes the
provider gap, not a claim that live input actually generates that stale event,
or that a duplicated serialized packet can reach execution through every queue.

The fix repeats stock's literal nonzero completion-attribute predicate against
the selected building and its registered private descriptor word4. A completed
row or missing/invalid descriptor returns before clearing/restoring AP10 activity,
calling affordability or queueing. Pending and active guards remain unchanged.
The allowed incomplete path keeps the original native price/discount, command,
payment, duration, event and completion lifecycle. No refund, timer or alternate
research state machine is introduced. The misleading comment calling the native
click helper full eligibility has been corrected: stage/prerequisite presentation
is not a general execution-time authorization predicate.

Native controller fixtures cover first allowed submission, pending duplicate,
active duplicate, post-completion replay, positive/negative completion, and
missing registration/completion attribute; rejected completion does not write
activity fields or call affordability. Completion is still native event0x2009
reason2, not a captured positive tuple or an elapsed-time prediction.

## Scheduler normal-return boundary

The GS_OrderProcessor RTTI/vtable was resolved separately in each fixture:

| Profile | Vtable VA | +78 scheduler VA | +88 research executor VA |
|---|---|---|---|
| public | 0x740094 | 0x4dcdf0 | 0x4dfce0 |
| beta2 | 0x758d94 | 0x4dd400 | 0x4e02f0 |
| gog-pristine | 0x757f4c | 0x4ddb40 | 0x4e0a30 |

All addresses use image base0x400000. Identities, the complete70-byte body and
its hash are in `artifacts/research-scheduler-profiles.json`. The installed
modified-beta2 body is independently reopened by the profile test.

The scheduler returns false only when its building argument is null. Otherwise
it calls building virtual+188(orderID), marks the returned order+18 with bit2,
stores duration at+14 and event at+2C, calls building virtual+18C(flags,order),
then unconditionally returns AL=1. It does not branch on either downstream
normal return value. The research executor dereferences the same building at
entry, before affordability or payment; it passes that same pointer to the
scheduler after its field writes. There is therefore no reachable normal false
scheduler return for the proved nonnull, normally returning research path.

`tests/ResearchSubmissionChecks.inl` executes that literal scheduler body with
bounded virtual-call doubles. Null building returns false without calling them;
a nonnull building returns true even when the publication double returns false.
The fixture verifies exact argument shape, duration/event/flag writes and call
counts. It does not execute native order allocation or publication.

## Remaining limits

Native order allocation, its null/throw behavior, publication lifetime,
exception unwinding, order retirement, cancellation, queue duplication and
save/load are not established by this audit. The scheduler dereferences its
allocation result without a null check; a failure there is not a false return
and does not justify inventing a refund. A true scheduler return alone does not
prove eventual event delivery. Existing pending/active state recovery in those
exceptional paths remains unproved; no automatic reset or refund was added.

The source authority is the research repo's `docs/building-research.md` and
`docs/symbol-index.json`, checked against actual executable bytes. The referenced
research source snapshots include a sibling Manager checkout; they are evidence,
not the edited source. Changes here remain in the owning Manager repository.
No game process, canonical profile, installation or published package changed.

## Notification findings incorporated

The research repo's `docs/research-notifications.md` and
`docs/witch-research-order-return-risk.md` were read after the initial audit.
Their UI broadcast/filter route is synchronous for stable containers and normally
returning callbacks. It filters the controller's captured source/category pair;
it does not track global selection, coalesce repeated broadcasts, or prove an
atomic purchase/completion tuple. One controller takes its first subscription
match; different controllers and repeated broadcasts may each refresh.

Those are presentation notifications, not scheduled event0x2009. Missing refresh,
a duplicate refresh, a clock notification, or a duration/start write alone is not
research completion and supplies no refund evidence. The new guard reads the
resolved active child context's authoritative completion attribute, rather than
assuming the displayed enabled state is fresh. Actual stale-input generation,
setter-side reentry and controller replacement lifetimes remain unproved here.

The added scheduler proof narrows the earlier order-return flag: a normal false
return is not reachable with the nonnull building through the pinned concrete
GS_OrderProcessor+78 body. It does not close downstream allocation/publication,
throwing paths, altered/overridden dispatch, or eventual reason2 delivery.

## Queued affordability rejection recovery

The normal queued rejection is now covered by the existing guarded research
execution hook. Private research rows enable that shared hook even without
kingdom research rows. The adapter calls the stock executor exactly once and
preserves its return. A false return releases only the matching pending,
nonactive private reservation (same building and command), then refreshes the
current private panel. Successful execution retains the existing tuple capture,
completion callback and duplicate guards. No payment, refund, activity-field
write, timer or queue replacement was added.

The gate requires the existing full Research feature profile, the concrete
research execution vtable entry, the scheduler vtable entry and its complete
70-byte body. These are verified for public Steam, beta2 and GOG. With the
normal nonnull scheduler's true return, the pinned executor's normal false
branches precede payment: existing research order or insufficient treasury.

`tests/QueuedResearchChecks.inl` executes the actual 305-byte beta2 research
executor in fixture-owned executable memory. Only its six direct external calls
and two global references are relocated to explicit doubles. A Python check
compares the entire body and relocation targets to the executable. The fixture
first demonstrates the old failure: affordability succeeds at submission, funds
fall before queued execution, native execution rejects without debit or activity
writes, tuple capture fails and pending blocks retry. Through the adapter the
same rejection clears the reservation, preserves the existing AP10 tuple and
refreshes the row. Restored funds permit a retry and exactly one native debit;
normal tuple capture then becomes active. Foreign contexts/commands and active
owners retain their reservations. Existing completed, pending and active
duplicate guards remain covered.

This closes the observed normal pre-debit pending-recovery path. It does not
establish allocation exceptions, malformed or never-delivered queue packets,
controller destruction/reentry, eventual event0x2009 delivery or live save/load
acceptance. Those limits do not justify a reset or refund beyond the matched
normal false return.

## Saved research completing before first panel setup (2026-10-17)

The public-build 14:00:29 runtime log stopped at the descriptor identity guard
on reason2 completion. Only APMK/AP75/AP92 had opened; no AP69 private descriptor
registration had occurred. The user confirmed loading a saved game. The
completion adapter required registration that was previously performed by
secondary-panel setup, so restored research could complete first and fail.
This is an ordering omission, not evidence of corrupt saved research or UI art.

Completion now establishes the same guarded stock-owned AP99 registration
before requiring descriptor identity. The stock resolver lazily initializes
stock templates (building-research.md); existing registration clones their
five-word descriptors using the game allocator and inserts into the game-owned
registry. An all-absent private set retires old borrowed identities after a
quest rebuild; occupied/mixed entries still fail. Already-valid registration
does not allocate. Reason1 cancellation does not register or resolve anything,
including teardown after descriptor destruction. No new hook, timer, payment,
activity rewrite, or unit scan was introduced.

QueuedResearchChecks.inl now invokes the actual completion adapter with no
parent/child controller and no registered descriptor, then with a rebuilt stock
registry and old borrowed identity. It covers the warm path, occupied entries,
missing stock templates, and teardown cancellation. Earlier save/load checks
cleared the pending owner but retained registered descriptors, so they missed
the cold-load ordering. This fixture uses explicit allocator/registry doubles;
it is not a claim of live save-load acceptance.

Evidence: graph commit f2644580d33ad98703361cd8fc88c825068161ef,
interpretation.majesty_script_proven_research_is_per_building, catalog claim23
and propositions116 (source-level scope, not native lifetime proof); research
shared-map.md/building-research.md; existing descriptor and completion contracts
in this repository and test_research_descriptor_profiles.py. Existing guarded
Public/beta2/GOG profiles remain unchanged; no new native address is applied.
