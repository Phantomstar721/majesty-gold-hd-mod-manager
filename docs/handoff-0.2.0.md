# Majesty CAM Tool 0.2.0 Handoff

This is the working handoff after the first serious audio-modding probe run.

## Current State

- Package version is `0.2.0`.
- The core CAM container reader/writer can list, verify, unpack, and repack CAM archives.
- Proprietary game files and generated probe packages live under `local/`, which is
  ignored by git.
- The deployed test quest has been restored to a known-good safe audio probe after a
  crashy float-WAV test.

Known local paths:

```text
Repo:
C:\Users\bterr\source\repos\majesty-cam-tool

SDK:
C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK

User quest deploy target:
C:\Users\bterr\Documents\My Games\MajestyHD\Quests\SDK\Example
```

## Big Audio Conclusions

Quest-local `soundfx.cam` and `sounddesc.cam` are the practical route for custom audio.
Loose quest sound XML by itself did not register new GPL-callable sounds.

Confirmed working:

- Quest-local WAVE overrides in `WrathOfKrolm_soundfx.cam`.
- Quest-local `sounddesc.cam` overrides of existing base `DSND` records.
- Brand-new generated `DSND` sound descriptions callable from GPL.
- Brand-new generated WAVE keys referenced by generated `DSND` records.
- Custom sound names with variable-length `DSND` payloads.
- Sound names longer than the 20-byte CAM directory entry; lookup used the full payload
  name, while the CAM header could be truncated.
- Custom `DSDP` phase definitions.
- Multiple distinct phase slots in one `DSND`.
- Custom `DSDG` cooldown/playback groups.
- DefaultSound path through building data, including normal manual building selection.
- 44.1 kHz stereo 16-bit PCM WAV.
- 44.1 kHz stereo 24-bit PCM WAV.

Confirmed limitations:

- Duplicate phase slots are not random variants. The engine uses the last matching phase
  slot.
- 32-bit IEEE float WAV crashed the game. Treat float WAV as unsafe and convert to
  integer PCM before packing.
- Loose `<Description type="Sound">` entries in quest XML did not make a new GPL sound
  callable.
- Calling the SDK example `Roar` / `Begin` or `DQ34` / `Begin` directly from GPL did not
  work without a runtime `sounddesc.cam` path.

## Runtime Probe Pattern

Use the copied SDK Wrath of Krolm quest. A reliable GPL probe pattern is:

```text
AIRootAgent's "UtilityScript" = $ProbeFunction;
$RunThread ( AIRootAgent's "UtilityScript", 5000, palace );
```

For two delayed callbacks, reusing existing script attributes worked:

```text
AIRootAgent's "UtilityScript" = $ProbeA;
AIRootAgent's "SpecialSpawnScript" = $ProbeB;
$RunThread ( AIRootAgent's "UtilityScript", 5000, palace );
$RunThread ( AIRootAgent's "SpecialSpawnScript", 11000, palace );
```

Avoid adding arbitrary new AIRoot script attributes during probes; earlier attempts with
new names caused quest initialization failures. Visual markers matter: each probe should
adjust gold, create a gold popup, and ping the minimap before interpreting audio.

## Sounddesc Model So Far

Observed sounddesc CAM sections:

- `DSDP`: phase definitions, e.g. `EBE0Begin`.
- `DSND`: sound descriptions, e.g. `RM01Rage_of_Krolm`.
- `DSDG`: playback/cooldown groups.

Generated simple `DSND` records are currently built from a known-good
`RM01Rage_of_Krolm` template:

- Replace `HEAD` sound ID and sound name.
- Replace the phase token and WAVE key in the `PRIM` phase slot.
- Recalculate `HEAD`, `DATA`, and outer `DSND` size fields.

Multi-phase `DSND` records store a phase count in `PRIM`. One-slot records end with a
56-byte slot. Multi-slot records are spaced every 60 bytes, with four zero bytes between
56-byte slots.

`DSDG` appears to define policy, not variants. A generated group with values
`[1, 10000, 0]` suppressed a second playback inside 10 seconds; the same ungrouped sound
played twice with the same timing.

## Version 0.2.0 Tooling Goals

The next coding pass should turn these hand-built probes into friendly APIs:

- Add typed builders/parsers for `DSDP`, `DSND`, and `DSDG`.
- Add a command that can inject a new sound into quest-local `sounddesc.cam` and
  `soundfx.cam`.
- Validate/import WAV files:
  - allow integer PCM, including 16-bit and 24-bit stereo tested so far;
  - reject or auto-convert IEEE float WAVs;
  - preserve or generate safe 4-byte WAVE keys.
- Generate quest-safe sound names while preserving full payload names beyond the CAM
  header limit.
- Support `DefaultSound` wiring for unit/building XML.
- Offer GPL probe generation for quick in-game validation.

## Bigger Roadmap

Ultimate goal: an extremely friendly Majesty modding toolset that hides the old binary
architecture behind safe workflows.

Near-term:

- Make audio authoring boring and reliable.
- Produce docs that explain what modders can do without asking them to learn CAM internals.
- Keep all deployment local to user quest/mod folders, never the Steam install.

After audio:

- Repeat the same discovery process for sprites, effects, palettes, `TILE`, `IMAG`,
  `SPLT`, and related CAM sections.
- Build import/export helpers and visual previews for sprites/effects.
- Eventually create a higher-level UI or wizard-style workflow for packing a complete
  quest/mod bundle.

## Good Resume Prompt

When resuming in a new session, read these first:

```text
docs/handoff-0.2.0.md
docs/audio-modding-findings.md
docs/cam-format.md
docs/modding-test-setup.md
```

Then inspect `src/majesty_cam/cam.py`, `src/majesty_cam/workspace.py`, and
`src/majesty_cam/cli.py` before implementing the next feature.
