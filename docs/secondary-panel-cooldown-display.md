# Passive secondary-panel cooldown display

MMCR30 extends stock.ap10-ap69-secondary-panel.v1 with an optional owned
agent-to-integer remaining-time callback, duration, progress control and text
control. All four fields are required together. Controls cannot overlap the
page's action/research controls. Composition validates the actual controls and
callback signature, and older registry formats remain readable.

The renderer runs in the existing selected secondary-panel refresh. It reads
the callback once, copies the stock AP24/AP99 progress message shape
0x29 {7, elapsed, 0, total}, then sends 0x08. The text uses the existing native
string setter. There is no new timer, deadline, scan or saved actor pointer.
The existing guarded quest-board scalar/string helpers and native timing
profiles cover Public, beta2 and GOG; cooldown pages now explicitly require
that helper preflight.

Positive remaining time is rounded up to game hours (2500 ms), with 24 hours
per day. Zero says Recharge complete; negative statuses say Recharge
unavailable and hide the progress bar. Neither label changes action gating.
The native effector query remains authoritative for pause, save/load and
expiry; the renderer does not simulate any of them or charge resources.

Evidence consulted: graph commit f2644580d33ad98703361cd8fc88c825068161ef,
clock_day_length and per-building research records and source citations;
research docs/shared-map.md and building-research.md; local
docs/stock-native-timing.md, MapQueryRuntime.cpp timing profiles and
UpdateResearchPresentations stock progress messaging. Graph assertions are
supporting source context, not independent native proof.

Offline coverage: MMCR30 schema/round-trip/truncation; native selected-panel
query/text/progress visibility at full, partial, hour boundaries, zero and
negative statuses; repeated unchanged query values. Live pause/save/load and
visual placement still require user acceptance.

Actual candidate: ../majesty-gold-hd-custom-guild-witch-hunter/private/plague-panel-v4/WitchHunterFourSkills.
Exact package files match its owner's verification.json. In-memory controller
and full catalog admission produce registry SHA256
6bbc88d1c6237edeecafc6641af7d40d1762288fa15ed495905e6b2b491aa0cc.
WSPG uses WHP_PlagueRechargeRemaining, duration 300000, progress 31920 and
text 31921. No merged profile is constructed by this check.

## Local installation, 2026-10-18

Canonical dist/Majesty Mod Manager/Majesty Mod Manager.exe SHA256:
b9dcaebd5523d98d102ba3e40e9a2a7b3e36474e817412ea48fc83bea9110992.
Bundled _internal/payload/runtime/MajestyBuildingRuntime.dll SHA256:
bbb8c153f72639863cad3d5b1401b1f2a84f94674052230bc14d4d6238feedf8.
Source/package receipts: local/regression/development-source.json and
development-package.json, with exact Public/beta2/GOG fixtures.
The user confirmed both applications closed before this local installation.
Live visual and save/load acceptance remains pending.
