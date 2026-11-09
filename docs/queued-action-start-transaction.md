# Optional upfront transaction for a charged building action

MMCR29 adds a paired optional `quote_callback_symbol` and
`start_callback_symbol` to a charged `stock.ap99-research-row.v1` row. Both are
package-owned `(agent Building) is boolean` functions. Native price must be0.

The quote is read-only. Start repeats eligibility and performs the complete
transaction without yielding; false means no debit occurred. The provider owns
its resources and atomicity. The Manager never adds a second payment.
`readiness_callback_symbol` contains structural eligibility/shared cooldown,
not affordability. Void completion applies the action and its success cooldown
without quoting/paying again.

Ordering follows stock research: resolve eligibility/shared activity/native
research-order exclusion, reserve saved owner/pending, perform accepted start,
then stock executor publishes and schedules its charge. An unsuccessful start
clears its reservation and never calls the stock executor. Reservation prevents
duplicate same-action entry. Stock scheduling rejection after successful payment
clears activity/reservation but does not refund, matching stock research policy.
Providers must not yield, submit other commands, or mutate activity/order state
inside the transaction.

The pending owner survives save/load. Completion clears activity/pending before
the effect and checks structural readiness and original ownership only. It never
executes the quote or start callback. Cancellation/ownership invalidation never
refund or apply an effect/cooldown.

Payment callbacks are included in the generated saved identity. An old unpaid
MMCR28 charge therefore has no matching MMCR29 pending reservation: its native
charge retires without a free effect, new payment or cooldown. There is no save
migration. New paid reservations retain their identity and complete after load
even if the payment spent the final gold/reagents.

Stock source/evidence: docs/delayed-building-action-evidence.md and research
docs/building-research.md. Uses the already guarded research executor/order
accessor on Public/beta2/GOG; no new native offset or timer. Human approval for
upfront payment was relayed by Witch Hunter owner on2026-10-18. Existing graph
consultation/research limits remain recorded in optional-provider-and-building-action-intake.md.

## Local installation, 2026-10-18

Canonical `dist/Majesty Mod Manager/Majesty Mod Manager.exe` SHA256:
`0d2f0f40749604c40b78a5cd427844a00529c42b29015ae355bc0a69ce1e2617`.
Bundled `_internal/payload/runtime/MajestyBuildingRuntime.dll` SHA256:
`76c6732038d7327cb4bddbb1d541fb7362c98fde1c6bbb211f955d75dda5f6fd`.
Receipt: local/regression/development-package.json, exact Public/beta2/GOG
fixtures, source and packaged gates. Native QueuedResearchChecks covers
preexisting order/shared duration/insufficient resources/failed start, debit
before schedule, duplicate rejection, spent-last-resource completion with lost
UI state, and scheduling rejection without refund. MMCR29 parser/truncation and
generated-source legacy identity separation are covered separately. These are
offline fixtures, not live gameplay/save acceptance.

Actual guild candidate: ../majesty-gold-hd-custom-guild-witch-hunter/private/cleanse-upfront-v3/WitchHunterFourSkills.
Its exact files match owner verification.json; candidate checker registry hash
`18eff929c474dc48d7d789541a306e06754471d0ab867978fccaee8075ceab08`.
No merged profile construction, current-session alteration, or release changes.
