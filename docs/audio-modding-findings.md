# Audio Modding Findings

Working notes from in-game Majesty Gold HD quest probes.

## Proven Runtime Path

The following path worked in-game through a copied SDK quest under:

```text
Documents\My Games\MajestyHD\Quests\SDK\Example
```

1. GPL script callback runs from the quest entrypoint via a single `$RunThread` stored on
   an existing script attribute, such as `AIRootAgent's "UtilityScript"`.
2. `$PlaySound(ThisAgent, "Rage_of_Krolm", "begin")` resolves and plays a base-game
   non-advisor sound.
3. A quest-local `WrathOfKrolm_soundfx.cam` can override a base WAVE payload when it
   contains a matching entry name.
4. A quest-local `WrathOfKrolm_sounddesc.cam` can override an existing base sound
   description when it contains a matching `DSND` entry.
5. A quest-local `WrathOfKrolm_sounddesc.cam` can register a brand-new `DSND` entry
   callable from GPL.
6. A custom `DSND` and WAVE can be referenced from unit/building data through
   `<DefaultSound>`, then played by phase on that agent.

The successful proof was:

- Script marker: `+15151` gold, then `Rage_of_Krolm` played our local tone after adding
  `RM01Rage of Krolm` to `WrathOfKrolm_soundfx.cam`.
- Script marker: `+16161` gold, then `Rage_of_Krolm` played our local tone after patching
  the `RM01Rage_of_Krolm` `DSND` record so `Begin` pointed at `DQ34`, with no local
  `RM01` WAVE override.
- Script marker: `+17171` gold, then brand-new sound `Tone_of_Krolm` played our local
  tone through a new `TK01Tone_of_Krolm` `DSND` record pointing at `DQ34`.
- Script marker: `+18181` gold, then brand-new sound `Tone_of_Krolm` played our local
  tone through a new `TK01Tone_of_Krolm` `DSND` record pointing at brand-new WAVE key
  `CT01`.
- Script marker: `+19191` gold, then `Krolm_Altar` with
  `<DefaultSound value="Tone_of_Krolm"/>` played our local tone when GPL called
  `$PlaySound(temple, "Select")`.
- Script marker: `+20202` gold, then manual player selection of the revealed
  `Krolm_Altar` played our local tone through `<DefaultSound value="Tone_of_Krolm"/>`.
- Script marker: `+21212` gold, then generated sound `Custom_Tone` played our local
  tone through a resized `TN01Custom_Tone` `DSND` record. This proves new sound
  description records do not require same-length binary replacement.
- Script marker: `+22222` gold, then generated sound `Very_Custom_Tone_Name` played
  our local tone even though the CAM directory entry was truncated to
  `LN01Very_Custom_Tone`. This suggests sound lookup uses the full name inside the
  `DSND` payload, not only the fixed-width CAM entry header.
- Script marker: `+23232` gold, then generated sound `Phase_Tone` played our local
  tone through a brand-new quest-local `DSDP` phase `TP01ProbePhase`. This suggests
  custom phase names are allowed when the phase is defined in `sounddesc.cam`.
- Script marker: `+24242` gold, then `Multi_Phase_Tone` / `PhaseOne` played one tone;
  a second marker `+101` gold later played `Multi_Phase_Tone` / `PhaseTwo` with a
  different tone. This proves one generated `DSND` can contain multiple phase slots.
- Script marker: `+25252` gold played `Grouped_Tone` / `GroupHit`; a second marker
  `+202` gold fired three seconds later but the same sound did not play. The `DSND`
  phase slot referenced custom group `TG01Tone_Group`, whose `DSDG` policy values were
  `[1, 10000, 0]`. This suggests generated sound groups can suppress repeated playback
  within their cooldown window.
- Control: script markers `+26262` and `+303` both played the same ungrouped
  `Ungrouped_Tone` / `GroupHit` sound three seconds apart. This confirms the previous
  suppression came from the custom `DSDG` group reference rather than normal repeat
  playback behavior.
- Probe: `Variant_Tone` had two `VariantHit` phase slots in one `DSND`: first
  `TV01 -> CT01`, then `TV01 -> C202`. Script markers `+27272` and `+404` both played
  the lower `C202` tone. Duplicate phase slots did not behave like random variants in
  this order; current hypothesis is that the last matching phase slot wins.
- Reversed control: the same duplicate phase probe with slot order flipped to
  `TV01 -> C202`, then `TV01 -> CT01` played the beepboop `CT01` tone for both
  markers. This confirms duplicate phase lookup uses the last matching phase slot.
- Script marker: `+29292` gold played a brand-new WAVE entry encoded as 44.1 kHz
  stereo, 16-bit PCM. This proves custom audio does not need to match the original
  22.05 kHz mono shape.
- Script marker: `+30303` gold played a brand-new WAVE entry encoded as 44.1 kHz
  stereo, 24-bit PCM.

This proves WAVE lookup, sound description override, and brand-new sound description
registration can be driven from quest-local CAM files.

## Sound Description CAMs

Base runtime sound descriptions live in CAM archives such as:

```text
Data\sounddesc.cam
Data\MDL1_sounddesc.cam
DataMX\mx_sounddesc.cam
```

Observed section types:

- `DSDP`: sound phase definitions, for example `EBE0Begin`.
- `DSND`: sound descriptions, for example `RM01Rage_of_Krolm`.
- `DSDG`: sound groups.

For `Rage_of_Krolm`, the `DSND` payload contains:

```text
HEAD ... RM01 ... Rage_of_Krolm
PRIM ... EBE0 RM01
```

Changing only the phase wave token from `RM01` to `DQ34` worked when the quest loaded the
patched `WrathOfKrolm_sounddesc.cam`.

Generated simple `DSND` records currently use the base `RM01Rage_of_Krolm` record as a
template, replacing the `HEAD` sound ID/name and the `PRIM` phase target, then
recalculating the inner `HEAD`, `DATA`, and outer `DSND` size fields.

Multi-phase `DSND` records store the phase count in the `PRIM` block. A single phase
slot is 56 bytes at the end of one-slot records; multi-slot records are spaced on
60-byte boundaries, matching the generated two-phase probe that worked in-game.

`DSDG` records appear to define playback policy/cooldown groups rather than variant
member lists. A generated group with policy values `[1, 10000, 0]` suppressed a second
playback attempt inside the 10-second window.

Duplicate phase slots inside one `DSND` are not useful as random variants. The engine
uses the last slot matching the requested phase.

## Negative Results

These did not work in-game:

- Adding a new loose `<Description type="Sound">` entry to `WrathOfKrolm_Sounds.xml` and
  calling it from GPL.
- A 44.1 kHz stereo, 32-bit IEEE float WAV entry crashed the game as the scripted gold
  marker fired. Treat float WAV as unsafe; convert imported float audio to integer PCM
  before packing.
- Calling the SDK example sound `Roar` / `Begin` from GPL.
- Calling the SDK example sound ID `DQ34` / `Begin` from GPL.
- Loading a quest-local `WrathOfKrolm_sounddesc.cam` copied from `Data\MDL1_sounddesc.cam`
  and calling `DQ34` / `Begin`.

Current interpretation: runtime `sounddesc.cam` is the practical route for GPL-callable
custom sounds. Loose quest sound XML alone is still not enough.

## GPL Probe Notes

- A single delayed `$RunThread(AIRootAgent's "UtilityScript", delay, palace)` pattern works.
- Direct nested `$RunThread($FunctionName, delay, agent)` compiled but did not run in-game
  during the quiet-window test.
- Adding new script-reference attributes such as `"SoundProbeScript"` and
  `"AdvisorProbeScript"` to `AIRootAgent` appeared to break quest initialization.

Prefer one proven delayed callback while testing audio. Use gold adjustments, effectors,
and minimap pings as visual proof before interpreting audio results.
