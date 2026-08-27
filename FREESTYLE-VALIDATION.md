# CAM Manager Freestyle validation

## Use these

- Active combined local mod: `TEST - CAM Manager - Freestyle Haunt + Alchemist`
- Launcher: `Launch - CAM Manager Freestyle Validation.bat`
- Runtime: `majesty-gold-hd-expanded-building-slots\artifacts\runtime-freestyle-validation`

Disable the original Haunt, the original Alchemist Lab, the earlier Haunt-only
test profile, and other CAM-changing packages while validating the combined
profile. Unrelated data-only/QoL mods should also be disabled when reproducing a
hang or crash, so the result has one owner.

## Current Siege crash correction

The 2026-08-27 full diagnostic dump resolved the deterministic crash to the
merged `Hero_Drop_Quest_Items`. An obsolete profile rule appended the undefined
numeric symbol `#AlchemistReagent`; the current Alchemist package uses the SDK
named item `"AlchemistReagent"` instead. The compiler emitted a null comparison
operand, which crashed the GPL interpreter when hero cleanup processed numeric
item 22.

The installed combined profile now uses the committed named-reagent package,
does not inject that numeric exclusion, and contains the original three stock
comparisons. Composition also fails before compilation if any future numeric
death-drop exclusion is not a defined GPL expression.

## Current combined correction

The 2026-08-26 Siege run exposed a Vigor affordability regression. Its merged
GPL still had the 1,500-gold guard, but the runtime's private click handler
skipped AP24/Rage's stock click-time treasury check and published Brewing as
active even when GPL rejected payment. The validation DLL now copies AP24's
current-player `APP` (Gold) read before command submission. The GPL remains the
sole payment/effect owner.

Windows classified the later stop from that run as an `AppHangB1`, not an
access-violation crash. No same-session dump was generated, so the Vigor fix is
not considered a hang fix. The captured session evidence is under
`local/reports/2026-08-26-2040-siege-combined-hang`.

## Current validated result

The exact saved manual preset loaded three times in one Majesty process, with a
return to the main menu between maps, functioning Phantoms in every map, and a
normal process exit.

The replacement runtime passed the exact previously failing sequence: Beginner
Random loaded with functioning Phantoms, then after returning to the menu the
saved manual preset loaded with functioning Phantoms. Majesty then exited
normally. A reverse three-map sequence also passed in one process: named manual,
Beginner Random, then named manual again, with functioning Phantoms on every
map and a normal exit. The runtime rejects recycled named-node data unless it
exposes the complete render-wrapper interface stock immediately uses. Automated
runtime, diagnostic-build, and expanded-slot suites also pass.

## Next combined validation sequence

Use one Majesty process for the entire sequence:

1. In a short map, hold the treasury below 1,500 and click Vigor. Confirm that
   no Brewing state appears, no hero receives Vigor, and gold is unchanged.
2. Raise the treasury above 1,500 and click Vigor. Confirm exactly 1,500 is
   charged, the progress display runs for 30 seconds, heroes receive Vigor, and
   the row re-arms after expiry.
3. First load `TEST - CAM Merge Siege Crash Repro.GMP` and continue beyond the
   previous roughly 36-second failure point.
4. Load The Siege, construct and fully upgrade both guilds, recruit both hero
   classes, and play beyond day 35 while exercising both guild panels and the
   named Monster Reagent lifecycle.
5. Save, load that save, continue several minutes, return to the main menu, and
   launch one more map in the same process.

Report whether the replay, full soak, and save/load cycle complete. Manual
category variation remains the final Haunt-only gate after the soak.

Validation DLL SHA256:
`D7D06E643478DC1F34CA2E70CEF44144FE17DC9EB7FEDDC41F5183C5093BC381`.

## Reporting

For a crash, report which numbered load failed and leave Majesty closed. The
runtime log is written beside the validation DLL as
`MajestyBuildingRuntime.log`; crash dumps and that log will be bundled before
the next build.
