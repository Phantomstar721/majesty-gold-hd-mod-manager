# Committed status application notification

`stock.gameplay-event-observer.v1` event `status-applied` calls a package-owned
void function `(agent Recipient, string Status)`. Initial supported status is
`Ratman_Plague_Icon`; this is an opt-in stock-status notification, not an
inventory scan or automatic item grant. Consumers own eligibility and consumption.

Stock SDK GPLMx `mx_Spells.gpl` Infectious_Cloud_Hit and
`Rules/Random_Events.gpl` Plague_Event set generation then call
Ratman_Plague_Begin. Ratman_Plague_Active contagion calls Begin then sets
generation. Notify after BOTH adjacent statements, retaining their order and
all selected guards. Never notify inside Begin: that would allow cure cleanup
to be overwritten by the contagion caller. Begin finishes effector creation,
PlagueScript scheduling, and six stat adjustments before returning. The consumer
may then use normal DeleteEffector cleanup; it must not recreate that cleanup.

These synchronous application paths are independent of the recipient's current
task or inside-building state. No extra timer, unit scan, movement interruption,
thread reset, or application replay is added. Original stock enumerations and
timing remain unchanged. Already-infected saves have no new application event;
retain existing consumption at purchase and the next existing plague callback.
That legacy-save case is not claimed to be instantaneous.

The same source-composition contract is used for Public, beta2 and GOG, with
destination-scoped stock lookup and existing expansion-service import for base.
No native offsets or DLL ABI change. Conflicting changes that remove the actual
two-step transaction are not silently overridden. Extra eligibility conditions
and unrelated selected code are retained byte-for-byte.

Evidence consultation: graph commit f2644580d33ad98703361cd8fc88c825068161ef,
script_function.ratman_plague_begin (three SDK call sites),
evidence.ratman_plague_effector_cleanup (qualified native evidence, not live
acceptance); research shared-map/symbol-index and
healing-shared-source-declarations-20261011.md. Actual installed SDK statements
were inspected for order. No excluded cleanup/factory research was reopened.
