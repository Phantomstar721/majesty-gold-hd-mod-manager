# Sibling stock research pages

## Optional page admission (MMCR26; Manager 0.3.11)

`stock.ap10-ap69-secondary-panel.v1` accepts `required_level` (1..3, default1)
and `eligibility_callback_symbol` (default empty). A nonempty callback must be
one package-owned `function Name(agent Building) is boolean`. It must be
read-only, bounded and free of world scans; presentation may call it repeatedly
through the existing panel event path. Manager generates the established
integer-result ABI adapter rather than reading a boolean as an integer.

Example additions: `"required_level": 3, "eligibility_callback_symbol": "Example_PageEligible"`.
These fields gate opening, not payment or delayed-action completion. The opener
remains visible and receives stock disabled-state messages, retaining the
package-authored requirement hover. Existing employment admission is combined
with the gate. Explicitly gated pages require the matching building family,
completed stage/built fields and declared tier. Direct parent commands and
recognized child action commands recheck the child's own context; Back keeps
the original stock route. Private queued research rechecks at execution too.
Other native action executors retain their own execution-time checks: this
feature is not a new universal transaction authorization hook.

MMCR26 records carry tier and optional generated callback. Older records default
to ungated legacy behavior; old runtimes reject26 rather than silently ignoring
the gate. Controller/attribute/evaluator paths reuse existing guarded three-build
profiles; no new native addresses or polling were introduced. Native fixtures
cover the real adapter with controlled endpoints, not live gameplay acceptance.

Additional research pages use the existing AP10 parent / AP69 child contract.
Each page is a separate `stock.ap10-ap69-secondary-panel.v1` record with its
own panel_key, owned SMNU/STRT pair and distinct parent opener. Keep the normal
Research command 8009 on the original page; additional parent buttons use private
IDs greater than 0x22CE. A shared building family is permitted only for the same
parent building (and the same resolved parent dialog). Other family collisions
remain errors. No new registry version or feature type is introduced.

Navigation is parent -> chosen research child -> stock Back -> parent. This is
not a next/previous page widget or a new saved page state. The reference is the
existing stock AP10 child opener plus its distinct Visitors/member child routes,
and Manager's already-verified sibling occupant/list openers. The ordinary native
openDialog call owns building context, layout, parent retention and child setup.
Stock AP69 Back retains its native hide/create-parent/remove-child ordering.
The original 8009 path remains unchanged; private sibling commands select a
different child dialog through the same opener. Repeated opening of the current
child has the existing stock no-action result.

Research rows still use `stock.ap99-research-row.v1`, with globally distinct
private action IDs, normal action+500 icons and action+1000 prices. Keep the
original upgrade gate on the original page. Include every additional parent
opener in the employment feature's gated_control_ids. All pages share the same
building CurrentResearch/start/duration tuple: they do not create parallel
research slots. Parent busy presentation recognizes a research row from any
sibling. Payment, queued order, duration, cancellation and completion stay with
the existing stock research implementation.

## Additional completion identities

The following stock templates have distinct per-building saved completion flags,
separate from the six Blacksmith flags. Query the actual researching building
with `$GetAttribute(Building, #ATTRIB_<Name>) != 0`. This adds no new GPL API,
owner-global ledger or load-time reconstruction.

| completion_template_control_id | Numeric attribute | GPL name |
|---|---|---|
| 5010 | 0x1E425041 | ResearchTournament |
| 5020 | 0x2A425041 | ResearchArrows |
| 5021 | 0x2B425041 | ResearchGoodGuard |

The descriptor_template_control_id separately selects the existing stock duration
template. The declared required_level and price override those template fields.
Never reuse a completion flag for two independent offers on the same building.
These are ordinary stock flags: consumer offer/purchase checks must restrict
their building candidates appropriately rather than query unrelated buildings.

## Evidence and verification scope

Graph f2644580d33ad98703361cd8fc88c825068161ef consulted: evidence.blacksmith_build_discount
and interpretation.majesty_script_proven_research_is_per_building. The graph's
source claims do not prove new native navigation. Existing primary evidence is
documented in panel-lifecycle.md, ap10-service-research-audit.md,
research-submission-boundary.md and stock-kingdom-research-audit.md. Their older
singleton workaround observations are superseded by the current saved stock
activity-tuple implementation in research-submission-boundary.md.

Independent descriptor-prefix RVAs for commands 5010/5020/5021:
Public A7ED9/A7F40/A7FA7; beta2 A87C9/A8830/A8897; GOG A8D79/A8DE0/A8E47.
test_research_descriptor_profiles checks those exact constructors, descriptor
word-4 storage and native ATTRIB name registration on all three builds. Initial
guessed names were rejected by that check and corrected before deployment.
ResearchCompletionAttributes.h also guards these template IDs at runtime.

test_stock_controller_registry exercises sibling serialization and rejects shared
families across different parents. PanelLifecycleRuntimeTests exercises selection
of the correct child, repeat-click suppression and both native parent-retention
results. These are offline checks; actual resource appearance and in-game
save/load/cancel acceptance remain user playtest steps.

The actual-candidate checker `scripts/check_research_pages_candidate.py` also
runs the full `catalog_merge_preflight` with an empty compatibility registry
before checking panel resources and the in-memory registry. Narrow controller
resource validation alone does not cover GPL unsafe-control-flow or saved-row
icon dimensions. Candidate receipt refreshes must rerun this full admission
check as well as the isolated source checks; they do not require a Manager build.

## Research parent visibility and shared busy state (2026-10-17)

The navigation-busy policy in this historical section was superseded by the
user clarification below; research must not disable page navigation.

The private-research and staged-completion activity branches returned before
refreshing parent navigation. Employment admission changed enabled state but
did not restore visibility after native presentation. Declared research-page
openers now receive separate stock visibility and disabled-state operations
after setup/event/activity presentation and queued research admission. This
applies to all siblings of the selected parent, not action-only pages.

The saved native research duration, a pending request for that same building,
and the existing synchronous completion guard disable navigation. Employment
admission remains an additional requirement. Direct commands and the stock
Research shortcut alias receive the same check before dispatch. Completion,
cancellation, selection and reopening derive state from the existing native
tuple; no new timer, unit scan or persistent research owner is introduced.

Evidence remains the graph consultation recorded above (commit
f2644580d33ad98703361cd8fc88c825068161ef,
interpretation.majesty_script_proven_research_is_per_building), the shared map,
building-research.md, and the existing three-profile control/activity contracts.
No new executable addresses are added. Native fixtures exercise both sibling
buttons, pending/active/cleared research, employment admission, unrelated pending
contexts, shortcut rejection and action-only exclusion. Actual in-game visual
appearance and completion/cancellation acceptance remain playtest checks.

## Clarified item-level busy policy (2026-10-17)

Research and Fittings are navigation, not purchases. Their visibility is
restored after native presentation and only ordinary employment admission
controls availability, including shortcuts/direct navigation commands. Research
duration, pending submission and completion do not disable page navigation.

The native row presenter remains responsible for idle eligibility and prices.
Its CurrentResearch mismatch branch hides sibling items and skips price
formatting (research local/decompiled/building-research-verify/4a9160.c,
building-research.md). The explicit user-approved presentation override restores
the nonactive item face/icon while busy and disables the purchase. It does not
show an uncomputed or stale quote; native quotes resume on the idle refresh.
The active item retains its progress/cancel face instead of its purchase face.
No research tuple is temporarily cleared for rendering. Submission and queued
execution retain shared-slot, completion and employment/payment checks. Pending
UI activity is scoped to the selected building, not a different building.

PanelLifecycleRuntimeTests covers navigation under employment/busy states,
browsing either sibling and back, restored saved activity, visible disabled
nonactive items, active progress and rejected second purchase. Existing queued
execution and cold-load descriptor tests remain in place. Graph/map references
above were consulted again; the decompiled presenter is qualified modified-beta2
evidence, with existing three-profile native contracts retained. No new address,
scan, timer or runtime patch site is introduced. Native playtest remains pending.
