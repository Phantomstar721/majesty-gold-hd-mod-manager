# In-Game Testing Setup

This repo should not live inside the Majesty install. Treat the install as:

- A reference source for SDK examples and real CAM files.
- A test target when we deliberately deploy a small mod or quest.

## Local Paths

On this machine:

```text
SDK:
C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK

SDK example data:
C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Example\Data
```

The game normally reads user mods/quests from:

```text
Documents\My Games\MajestyHD\Mods
Documents\My Games\MajestyHD\Quests
```

We should confirm those exact folders before writing a deploy script.

## Safe Testing Rules

- Do not overwrite files under the Steam install for early tests.
- Do not commit copied game assets.
- Keep copied CAMs under `local/`, which is ignored by git.
- Prefer SDK example quest/mod structures before touching base-game datasets.
- Keep every generated test package easy to delete.

## First Test Loop

1. Copy one SDK example CAM into `local/`.
2. Run `majesty-cam list` to inspect it.
3. Run `majesty-cam unpack`.
4. Run `majesty-cam pack`.
5. Compare the original and repacked bytes.
6. Only after that, test a deliberate replacement in a quest-local CAM.

The first practical target should be audio CAMs like `WrathOfKrolm_soundfx.cam` and
`WrathOfKrolm_voices.cam`, because their entries are standard WAV payloads.

## Later Test Loop

Once audio is reliable:

1. Create a tiny quest-local CAM with a known-good `WAVE` replacement.
2. Reference it from a copied SDK example quest XML.
3. Deploy the copied quest package into the user quest folder.
4. Launch Majesty and verify the sound plays.

Sprite/TILE testing comes after the container tooling has boring round-trip behavior.
