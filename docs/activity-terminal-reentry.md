# Shared activity terminal callback ordering

2026-11-10, Manager-owned source correction; no deployment or profile build.

The Bard report shows a cancellation callback re-entering the same Cancel API,
then the outer MM_AD_Change passing null Root to StopIfEmpty. Source confirmed
that removal committed and Busy cleared before notification, but cleanup still
read a local Root after arbitrary consumer GPL returned. The exact native VM
reason for loss of that local is not established; it is not evidence that the
quest root was deliberately deleted. Prior Python tests allocated independent
local frames, so their re-entry coverage did not exercise this failure.

Cancellation now commits removal, releases Busy and performs StopIfEmpty before
calling consumer GPL. No invocation-local state is accessed after notification.
A duplicate Cancel still returns0 with no second notification. Cancel of a
different record remains supported. A callback can start a new registration;
the already-empty old schedule has been retired and the new registration owns
its normal stock NewThread schedule. Cancellation inside Tick retains its
existing Ticking guard, so it cannot kill the sampler while terminal dispatch
is in progress. Natural completion keeps that existing delayed-stop ordering.

Absent-root checks return the existing invalid/absent API results before any
attribute access. Terminal Tick cleanup additionally verifies that the current
named root is still the same root; it does not initialize a replacement quest's
service after a callback. StopIfEmpty likewise cannot clear a different root.
This is lifecycle validation, not a general suppression of GPL attribute errors.

Focused source tests include synthetic shared/reused Change locals (explicitly
fault injection, not an emulation claim), same/different-key recursive Cancel,
last-record cleanup, callback restart, natural completion and absent/replaced
root. The emitted service plus stock source boundaries compile in an isolated
GPL language fixture. Full-module follow-up identified two older tests tied to
callback positions in EVENT_SIGNATURES. Adding status-applied shifted their
numbered test callbacks; their assertions no longer named the potion/tournament
events they intended to check. The tests now select callbacks by event name and
compare call tokens and ordering. Their source-tampering check also confirms
that the deliberately changed stock attribute is actually replaced. The earlier
failed run remains in local/panel-engine-host/activity-reentry-tests.log.

Stock scheduling remains the approved Day_Counter / GplAIRoot / NewThread clone
documented in stock-events-and-activity-time.md; no new polling, timer or native
hook. Relevant graph commit f2644580d33ad98703361cd8fc88c825068161ef and
mechanic.victory-conditions; existing research shared-map and SDK GPL Reference
remain qualified primary references. The source-only correction applies to the
same Steam and GOG GPL service, with no executable-version addresses added.
