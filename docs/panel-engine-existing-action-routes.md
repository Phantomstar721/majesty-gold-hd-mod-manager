# Reuse existing panel actions (2026-11-09)

**Superseded ownership recommendation (2026-11-10):** the user clarified that
every building view must use the Window Engine, and explicitly approved correcting
the private controller handoff only. The mixed-owner fallback below is historical,
not the current authoring instruction. See [the narrow handoff](panel-engine-handoff.md).

The user requires existing Window Engine/native functions or existing Manager
handlers. No additional presenter bridge or replacement action lifecycle is
authorized. The provisional HOST/MMCR module-revision-2 prototype was removed;
the ten edited implementation files were restored to release commit df6c995.
No package was built or deployed from that prototype.

## Source findings

Pinned SDK: `.audits/flamey-window-engine-sdk-20261109/sdk/Window Engine/src/we_engine.cpp`
in the workspace root, SHA256
`d6049b8021575241027677db2df441cdb50bd0038735c3fda6058b70d1a40b9b`.

| Action | Existing route | Limitation to retain |
| --- | --- | --- |
| Recruit a new guild member | WE RECRUIT/COST; recruit(), lines605-626, invokes GUILD_COST and GUILD_RECRUIT. | This is recruitment, not the Crucible's existing-hero employment operation. Preserve native class/context, busy state and native refresh. |
| Native research/upgrade | Original native controller commands, optionally forwarded by WE DOES; WE_OnCommand, lines1391-1443. | DOES calls that controller's original OnCommand. It does not turn an arbitrary private command into a registered native research row. |
| Private queued research/fittings | Existing MMCR stock.ap99-research-row.v1 handler: SecondaryPanelControllerSetup/Control, RegisterPrivateResearchDescriptors, BeginPrivateResearch. | Keep these views Manager-owned and retain their declarations/control IDs. Stock payment, saved activity, completion and cancellation already exist. |
| Hire an existing hero | Existing stock.building-employment.v1 selector and paired action. | Keep the selector and employment-gated parent Manager-owned. RECRUIT is a different operation. Do not replace the paired queue with a direct TCLICK callback or a new polling flow. |
| Private sovereign spell and shared cooldown actions | Existing MMCR sovereign/rage command handlers. | Retain existing action views, declarations and controller ownership. No new spell dispatcher. |
| Static layout/text changes | SMNU/STRT resources with existing control IDs and ordinary string rows. | A WND-authored layout need not opt a Manager action view into WE ownership. Preserve native control shapes and dynamic handlers. |

WE CLICK already calls GPL with the panel's building/player. Reuse an existing
callback only when its exact argument/result and dispatch contract matches;
it is not a substitute for a queued paired action or private research handler.

The stock research source evidence is research repo `docs/building-research.md`:
native AP99 refresh enumerates control IDs [5000,5100), while the custom guild's
registered private rows use the existing Manager secondary controller handler.
The sample Adventurers Guild's `WE_AG_Research_Click`/`WE_AG_Check_Research`
instead implement their own GPL run-counter research; they are not a reason to
replace our working saved stock research lifecycle.

## Ownership and navigation

`runtime/PanelEngineOwnerProbe.inl::MMWE_OwnsView` opts in a view when any
recognized WE row is present. `ResolveDialogFactoryRequest` and
`CaptureSecondaryController` bypass Manager capture for that view/controller.
Therefore adding BASE or LABEL to an existing Manager action view is not a
harmless formatting change. Merely retaining original control IDs is insufficient.

Use the existing owner for each view. Manager action views can receive revised
SMNU geometry/static STRT captions without WE directives. Engine-owned views can
use the existing PANEL command to open a separate existing Manager action view:
`ResolveDialogCreationRequest` recognizes the requested private child directly,
and `ActivePanelContext` resolves the child's own native context, rather than a
deleted parent. This is source-established routing, not new live acceptance.
Do not move an employment gate or other parent command guard out of its existing
owner merely to change its presentation.

## Evidence and scope

Knowledge graph commit f2644580d33ad98703361cd8fc88c825068161ef;
nodes evidence.dialog_panel_controls_20261008 (index515) and
evidence.phantomstar_mods_panel_techniques_20261009 (index519), both retaining
their source/scope qualifications. Consulted research shared-map and existing
building-research, panel lifecycle and Manager research-submission/employment
contracts. No new native addresses or mappings were introduced. Released
Public/beta2/GOG profiles remain the implementation reference.

Guild ownership is unchanged: its owner must revise its private WND/CAM candidate
and misleading pending-bridge status. No user merged profile, installed runtime,
beta/alpha application or staged Workshop output is changed by this audit.
