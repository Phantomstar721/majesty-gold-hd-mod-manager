# Nested GPL error unwinding audit

## Scope and result

Read-only investigation of the 2026-09-19 23:22:20 UTC crash. The initiating
error is a mod-owned death callback reading a building property from a combat
target. Stock's nested GPL error handler then empties the global function-frame
stack. The outer stock projectile script continues and crashes on its next
`foreach` evaluation. This is not evidence of an animation or Manager adapter
fault, and does not justify changing stock interpreter recovery.

No prepared profile, runtime DLL, or mod package was changed for this audit.

## Evidence

- Small dump: installed Steam game directory,
  `majestyhd_crash_2026_9_19T23_22_20C0.mdmp`.
- Full dump: sibling `majesty-gold-hd-freestyle-custom-cam-fix` repository,
  `diagnostics/dumps/MajestyHD.exe.37444.dmp` (536,905,461 bytes).
- Prepared source: user's existing merged package, `GPL/Merged.gpl`.
- Owning source: sibling `majesty-gold-hd-restore-abandoned-zoo` repository,
  `src/GPL/RestoreAbandonedZoo_Capture.gpl`; HEAD at inspection was
  `c9bf86f9b7fda31ddc875416d70b60e91898a26e`.

The full dump retains this formatted error at VA `0x0F812510`:

```text
GplDispatcherHandle script error:
 Call Sequence was: - line 0 : Tried to access non-existent attribute Occupants in agent#210, ().
```

The underlying error text is also retained at `0x1297E650` and other heap
locations. This identifies a prior script exception, not merely a hypothetical
property failure inferred from source.

## Agent and callback ownership

Victim GPL agent 109 (`0x0089CE18`), native unit `0x126549D8`:

- Title `RatmanChampion`; HP -17, maximum HP 60.
- Type `Waiting_to_die`, subtype `Controlled`, original type `Hero`.
- BasicScript `Restore_Zoo_Tame_Guardian`.
- ActiveScript and BackScript `Guardian_Attack_Object`.
- IGdeathScript still `Restore_Captive_Hooligan_Death`.
- Target is GPL agent 210, not a Zoo; `zoo_agent` is NullAgent.

Attacker GPL agent 210 (`0x0089D458`), native unit `0x12C06510`:

- Title `RatmanCatapult`, type `monster`, subtype `Ratman`.
- Target agent 109; Attack_Action `Ratapult_Ball`.
- No `Occupants` property.
- Descriptor `BVq1` / `RatmanCatapult`.

Projectile native unit `0x10F847C0` has descriptor `BPA7` /
`RatapultMissile`. These are actual combat objects, not substituted art IDs.

The tame transition replaces classification and AI task slots but leaves the
earlier captive IGdeathScript installed. `Restore_Captive_Hooligan_Death` saves
`thisagent's "Target"` as `zoo`, calls stock `Hooligan_Death`, then calls
`Restore_Refresh_Zoo_Capacity` whenever that target is a valid game piece.
The latter checks validity only before reading `zoo's "Occupants"`.

The stock Hooligan callback sets `Waiting_to_die`, kills ActiveScript and starts
`henchman_death`; the dump's state agrees with execution reaching that callback.
Once Guardian combat owns Target, validity alone cannot establish Zoo ownership.

Semantic parser extraction confirmed exact source/prepared function text equality
for all four relevant functions (not just approximate normalized matches):

- `Restore_Zoo_Tame_Beast`
- `Restore_Zoo_Tame_Guardian`
- `Restore_Captive_Hooligan_Death`
- `Restore_Refresh_Zoo_Capacity`

## Stock native failure sequence

Addresses below refer to the installed Steam beta2 executable in the dump.

1. Stock `GPLMx/TaskModules/Subtasks/mx_make_attack.gpl:676`, `Ratapult_Hit`,
   collects nearby targets into `t3` and calls `Make_Attack` inside `foreach`.
   Its live function object is `0x13A8FF70`, named by string `0x13AAB950`.
   Instruction container `0x13AAB878` points to code `0x13F7A0A8`, 53 records
   of 36 bytes. Record 47 (`0x13F7A744`) is foreach opcode `0x20`.
2. The damage path reaches native lethal-HP handling and the unit death script.
   The captive callback uses combat target 210 as a building and raises the
   retained missing-Occupants exception.
3. Stock external evaluator `0x5798F0` ordinarily pushes one frame through
   `0x569FC0` before dispatch and pops one through `0x42A4C0` afterward.
   Its exception path, however, formats the above error at `0x5799F4` onward,
   then loops at `0x579B13` calling `0x42A4C0` until frame count is zero.
   It does not preserve an enclosing external evaluator's frame depth.
4. `0x40EFB0` computes frame count from
   `([0x7E2438] - [0x7E2434]) / 0x24`. At the crash both pointers are
   `0x10B2D458`: the vector is empty despite the outer Ratapult evaluator
   still being active.
5. On revisiting Ratapult_Hit's foreach, iterator creation at `0x564D60`
   detects the missing frame, takes `0x564EB1`, and returns zero at
   `0x564EEA`. Caller `0x569020` stores that zero in EBP, then passes it as
   ECX to `0x401E90` at `0x569047` without a null check.
6. `0x401E93` dereferences the null receiver. Exception C0000005 reads address
   zero. The target list itself is valid and contains agent 109; an empty or
   invalid list is not the cause.

The Manager return address `0x5126A358` is outside the stock world-update call,
not an inner damage/death callback. Stack presence alone would not prove or
disprove an earlier adapter fault; the retained script error plus stock recovery
and matching mod source establish the initiating error here.

## Repair boundary

The Zoo owner must correct the transition out of captivity so released tame
guardians receive the appropriate stock death lifecycle, and harden the existing
captive callback against saved agents whose Target no longer denotes a Zoo.
Validate actual building ownership before accessing building-only properties.
The fix must cover already-saved tames retaining this callback, not only newly
created ones. Confirm any chosen replacement against the stock controlled
guardian/death source before implementation.

This is not a reason to modify generic merge precedence, rewrite stock
Ratapult_Hit, suppress script exceptions, or introduce speculative runtime
context restoration. An in-game reproduction after the owning mod correction
remains necessary to validate gameplay recovery.
