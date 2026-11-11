# Window Engine presentation with existing private actions

2026-11-10. Human approval: "Yes, correct that handoff only."

The Window Engine presents every opted-in view. The already registered Manager
controller remains its original setup/command/event handler. There is no new
research scheduler, hiring flow, spell dispatcher, gameplay state, GPL API or
author protocol. The abandoned HOST/MMCR opt-in is not used.

For a registered Manager view, keep the existing declarations, control IDs and
handler-managed captions/prices/progress/hover. Omit BASE/CLASS: the existing
factory mapping chooses the original constructor before wrapping. Presentation
rows such as `WE|1|LABEL|8005|SHORT FIXED TITLE` opt into the engine. Do not bind
CLICK/DOES/PANEL over an existing private action or apply LABEL to dynamic state.
Ordinary native-only engine views retain their existing behavior.

The package uses the existing external patch requirement `window-engine.v1`
with `minimum_revision: 2`. Module revision1 remains supported for its original
native-only use; it cannot satisfy a revision2 requirement. The UI, preflight
and launch now retain the actual installed revision. Updating known modules is
transactional in memory and preserves the other optional module's enabled state.
The QoL cache also persists that revision. Older installed-engine cache records
without a revision trigger a fresh inspection; they cannot downgrade a revision2
dependency to revision1 on the next startup. Cold-start fixtures exercise both
the first scan and cached reopen with the actual revision2 dependency.

## Internal ordering

1. Creation resolves the existing typed private controller record and context.
2. The native factory selects its existing class even when that view has WE rows.
3. Before WE wraps it, the existing Manager capture installs its original action
   methods. Context and view must match the actual constructed controller.
4. WE copies only the registered table's known length and its verified stock RTTI
   locator, then installs its existing presentation methods around that table.
5. A presenter alias in the existing lifecycle registry retains the same cleanup
   owner without replacing the engine destructor. Teardown still passes through
   engine bookkeeping, Manager exact-instance cleanup and the stock destructor.

The private module handshake supplies only capture, registered copy bounds and
cleanup-alias registration. No new author-facing callbacks or instance registry
are introduced. The SDK retains its existing bounded class cache. Copies cannot
be authorized from arbitrary pointers or from an already wrapped table.

## Evidence and current limits

KG f2644580d33ad98703361cd8fc88c825068161ef, evidence nodes515/519 and their
source/scope qualifications; research shared-map, building-research and existing
controller/lifecycle contracts. Pinned SDK SHA256
d6049b8021575241027677db2df441cdb50bd0038735c3fda6058b70d1a40b9b.
All native addresses still come from the verified Public, beta2 and GOG profiles.

Private evidence under `local/panel-engine-host`: actual v3 resource/metadata
parity in `v3-candidate.json`; version2 modules in the alpha's private
`handoff-native-modules`; native descriptor fixtures, SDK ownership fixture,
existing-action runtime fixture and lifecycle-alias checks. The actual seven
candidate LABEL rows are also compiled/executed with local SDK-provider doubles
in `local/panel-engine-alpha/v3-handoff-fixture`. Its nine ordinary research and
fitting declarations are unchanged. The Manager fixture exercises the handoff,
research admission/duplicate rejection and teardown under all three build tags;
separate profile checks compare the actual native provider/constructor bytes.
These are offline checks, not execution of a loaded game or save/load acceptance.

The isolated alpha application and local guild candidates were subsequently
deployed under explicit user authorization; delivery evidence is in
`local/panel-engine-host/DELIVERY.json`. The first user Prepare exposed a
zero-size native price control in the guild migration. Its resource-only repair
and the added production materialization checks are documented in
[panel-engine-resource-contract-audit.md](panel-engine-resource-contract-audit.md).
The alpha executable is unchanged by that repair. In-game validation remains
a separate user-run step; no user merged profile was constructed by these checks.

## Conditional decorative images

An independent decorative image may use the existing
`WE|1|SHOWIF|control|QueryName` directive. This does not replace a registered
action's handler or permit binding engine actions over it. The private handler
continues owning the action, icon, price, busy state and gameplay admission;
SHOWIF controls only the otherwise unbound decorative record.

The pinned SDK's `parse_line` accepts SHOWIF at line435. `call_gpl2` at
lines531-563 invokes `QueryName(building, local_player_number)` and accepts only
an integer return value in result element0. Use explicit integer0/1, not a GPL
boolean result or an output-reference procedure. Callback names have no `$`
prefix and are identifiers of at most47 bytes. Queries must be read-only and
idempotent: the engine reapplies them after original setup, event refresh and
its existing panel notifications. No new timer, scan or Manager API is needed.
At lines696-708 SHOWIF hides the control on zero or failed query and shows it
on a successful nonzero integer. Use completed construction level for a
tier-dependent frame, rather than affordability/cooldown, so a valid disabled
action retains its frame. These statements concern the pinned source contract;
loaded-game unlock/save-load presentation remains separate acceptance.

The November10 guild-owner follow-up identified an independent full-canvas
frame control31350/WBFr1025, omitted by the earlier row-rectangle audit. Its
reported diagnostic captured all three actual action controls hidden at tier1,
while this decoration remained visible. That is evidence for correcting the
guild resource with SHOWIF, not for another shared visibility-counter change.
The owner implements that resource/helper under the existing revision2
handoff. Current Manager parsing already relocates SHOWIF callback and control
references; revision2 does not alter this SDK behavior. No existing generic
linked-decoration declaration was found in the current implementation.

This source review retains the KG commit/nodes and research qualifications
above. It uses the same pinned SDK and three-profile native bindings already
packaged with the alpha; no new addresses or native mappings were introduced.

The accepted handoff is promoted to beta0.3.14 with matching revision2 modules
and a normal beta runtime. The alpha-only persistence path and capped panel-open
diagnostic are not enabled in that runtime. Native-only revision1 content keeps
its existing path; updating an installed module remains an explicit optional
Quality of Life action. Whole-panel/native startup and fixture coverage on all
three executable profiles remains distinct from the reported combined playtest
and from save/load acceptance.
