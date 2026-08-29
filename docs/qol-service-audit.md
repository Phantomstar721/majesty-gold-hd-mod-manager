# Majesty Mod Manager QOL service audit

Audit date: 2026-08-29

## Decision

The manager's QOL catalog is the same ten-utility boundary already established
by `majesty-gold-hd-qol-utilities`.  The manager may detect and orchestrate
those utilities, but it must never reproduce their patch bytes or restore a
whole `MajestyHD.exe`.  Apply and remove operations call each utility's
canonical guarded PowerShell script synchronously and then re-run its dry-run
inspection.  This preserves independent install/uninstall ordering and avoids
clashes with patches installed outside the manager.

The aggregate QOL application was audited at commit
`b1275cfa36f41a1c59e9e050cc6cbb32da92820a`.  Its
`tests/Test-AllUtilityRoundTrip.ps1` and
`tests/Test-IndependentPatchOrder.ps1` are the integration evidence for this
ten-utility boundary.

## Canonical utility inventory

Every listed standalone repo ships an MIT `LICENSE` owned by Phantomstar721.
Paths below are relative to the named repo.

| Utility | Standalone repository and audited commit | Apply script | Remove script | Applicability |
| --- | --- | --- | --- | --- |
| Skip Intro Videos | `majesty-gold-hd-skip-intro-videos` @ `7b6309e967f69645ccff98af29972b952ed96e98` | `scripts/Install-NoIntro.ps1` | `scripts/Uninstall-NoIntro.ps1` | Branch-independent `MajXPrefs` preference |
| Downloadable Quests Shortcut | `majesty-gold-hd-downloadable-quests-shortcut` @ `2f683319ed03131c87b2dc2fb135b2afa83c4f7b` | `scripts/Install-DownloadableQuestShortcut.ps1` | `scripts/Restore-CustomQuestButton.ps1` | Public and beta2; executable plus surgical UIData fields |
| Quest Map Drag | `majesty-gold-hd-quest-map-drag` @ `72bbf4506afc03485cdc5d2669b8e276057bfdee` | `scripts/Install-QuestMapDragPan.ps1` | `scripts/Restore-QuestMapDragPan.ps1` | Public and beta2 executable profiles |
| Unlock All Quests | `majesty-gold-hd-unlock-all-quests` @ `bd96f850ad00f2394504e4b208c51aed706c28d9` | `scripts/Install-UnlockAllQuests.ps1` | `scripts/Restore-UnlockAllQuests.ps1` | Public and beta2; owned executable edits plus surgical UIData label |
| Suppress All Message Flags | `majesty-gold-hd-suppress-all-message-flags` @ `aa6eeb2114cdbf7b250b6902f45f3f67b34703f6` | `scripts/Install-SuppressAllMessageFlags.ps1` | `scripts/Restore-SuppressAllMessageFlags.ps1` | Public and beta2; six owned executable bytes |
| Remember Active Mods | `majesty-gold-hd-remember-active-mods` @ `d40ddb8c7b7400e22b65a12eeb441a2c533ed8f7` | `scripts/Install-ModPersistence.ps1` | `scripts/Restore-ModPersistence.ps1` | Public and beta2; private `.mpst` section and guarded hooks |
| Remember Game Speed | `majesty-gold-hd-remember-game-speed` @ `8ec657cdd28572eb8c85e6af3e0724c9487acd88` | `scripts/Install-RememberGameSpeed.ps1` | `scripts/Restore-RememberGameSpeed.ps1` | Public and beta2; private runtime section and guarded hooks |
| Remember Camera Zoom | `majesty-gold-hd-remember-camera-zoom` @ `b15779e15eb1326e8980327a7d58541133ee73f7` | `scripts/Install-RememberCameraZoom.ps1` | `scripts/Restore-RememberCameraZoom.ps1` | Public and beta2; private runtime section and guarded hooks |
| Generic Visitor Lists | `majesty-gold-hd-generic-visitor-lists` @ `2790a9632ebd8c43751b009e892d4d130a4e5718` | `scripts/Install-GenericVisitorLists.ps1` | `scripts/Restore-GenericVisitorLists.ps1` | Public and beta2; private `.mgvl` section and three guarded sites |
| Lower Tracking Window | `majesty-gold-hd-lower-tracking-window` @ `17d6762df7917e451db153fd2fee7681b557df41` | `scripts/Install-LowerTrackingWindow.ps1` | `scripts/Restore-LowerTrackingWindow.ps1` | Public and beta2; owned executable/UI changes |

Generic Visitor Lists and Remember Active Mods are marked
`required_by_manager`.  Generic Visitor Lists supplies the visitor behavior
expected by manager-built content.  Remember Active Mods is the stock-list
interoperability bridge: the manager imports its existing persistence file and
writes the chosen Standard IDs plus the generated Merge profile ID before the
special launcher starts.  Their status remains inspectable, but manager service
and controller removal are disabled; launching will idempotently ensure them.

## Supported-branch evidence

The aggregate app's `scripts/qol_installer.py` identifies builds without a
whole-file hash, so appended private QOL sections do not invalidate detection.
The manager service uses the same evidence and fails closed:

| Branch | Version | COFF timestamp | Required original sections `(name, virtual size, RVA, raw size, raw offset, flags)` |
| --- | --- | ---: | --- |
| Public | `1.5.2.24` | `0x5897B72F` | `.text,333E7D,001000,334000,000400,60000020`; `.rdata,07E88C,335000,07EA00,334400,40000040`; `.data,05826C,3B4000,00C800,3B2E00,C0000040`; `.rsrc,000F34,40D000,001000,3BF600,40000040` |
| beta2 | `1.5.2.28` | `0x5A8A11D5` | `.text,34C20D,001000,34C400,000400,60000020`; `.rdata,08395C,34E000,083A00,34C800,40000040`; `.data,058DF4,3D2000,00D200,3D0200,C0000040`; `.rsrc,000F34,42B000,001000,3DD400,40000040` |

The detector additionally requires an x86 PE32 image, image base `0x00400000`,
section alignment `0x1000`, file alignment `0x0200`, header size `0x0400`, and
valid raw-section bounds.  Unknown timestamps, altered original section
layouts, and malformed PE files are inapplicable.  The preference-only Skip
Intro utility remains applicable because it edits `MajXPrefs`, not the
executable.

Each executable utility still performs its own stronger site-level validation.
Manager branch detection enables a control; it never authorizes bytes by
itself.

A live read-only manager inspection recognized the currently installed,
QOL-patched executable as beta2 `1.5.2.28` and each of the ten canonical
installers reported Installed.  This exercises the appended-section tolerance
against the actual local patch combination, not only synthetic PE fixtures.

## Current manager payload audit

`scripts/Stage-ModManagerPayload.ps1` now writes payload schema 2 and stages
the aggregate utility suite at:

`payload/qol/utilities/<bundle-directory>/...`

All 71 utility files are present, including each canonical installer,
restorer, support script, README, BAT entry point, and per-utility MIT license.
The aggregate MIT license is also retained as
`payload/qol/LICENSE-qol-utilities.txt`.  This path is inside PyInstaller's
frozen resource root and is the QOL service's first source choice.

Two legacy apply-only launch-prerequisite directories remain beneath
`payload/qol` so the existing launch controller can ensure its mandatory
patches without depending on the new optional service:

- `generic-visitor-lists`: installer, `MajestyBuildProfiles.ps1`, and MIT
  license.  SHA-256 values match the standalone repo exactly:
  `B3054E4646050C3DC5AC054C4C6278F7058C87FCA86032614852A82B98F421A8`,
  `2714BCDBE6DF0A8730FE143339AEA478802ADDA0DFFF16BE89E42A8FCA135BC4`,
  and `4A56EFB978D760E566FF73DE44850314D2F907B071092DFA2D55B5E89281E7D3`.
- `remember-active-mods`: installer, `MajestyBuildProfiles.ps1`,
  `NativePathEncoding.ps1`, and MIT license.  SHA-256 values match exactly:
  `D1DE8E14B85EC5B32696A91AE3388451D3D983E29B5A1BB32BCB1C66D918E15B`,
  `D6CE554FF2F30D89FD594A697E8FAF691AA396F62C4F9540A496E62915EE9A17`,
  `4F3F525B5A158C9737B8D797A34E10A0C74CC67750811921BAC3CD89905605F6`,
  and `090643469110673A3CA08ED67F21E65841EE8A373C84CDE3BF2556DC4780F7A5`.

The complete schema-2 suite supplies removal for those two utilities and all
apply/remove operations for the other eight.  `manager/qol_service.py` refuses
to mix an installer from one source revision with a restorer from another.  It
prefers the complete frozen-safe suite, then a complete standalone repo pair,
then the development aggregate repo.  A legacy partial payload is exposed
honestly as apply-only only when no complete pair exists.

## Packaging follow-up

Remaining distribution validation:

1. Record source commit and SHA-256 hashes in a generated payload manifest.
2. Run the aggregate repo's all-utility round-trip and independent-order tests
   against the staged payload, on both supported stock executables.
3. Keep operations serialized and require Majesty to be closed; never run two
   executable patchers concurrently.
4. Re-inspect after every apply/remove and surface canonical script output on
   failure.

## Explicit exclusions

- `majesty-gold-hd-speedrun-timer` is not in the manager QOL catalog.  It has no
  repository license and its README states that physical section uninstall
  order matters relative to `.mfsp`.  That fails the no-clash/reversible-in-any-
  order requirement.
- `majesty-gold-hd-remove-earthquake-screenshake` is an MIT GPL content mod, not
  an executable QOL patch.  It belongs in content discovery and semantic merge
  handling.
- Restore Abandoned Zoo and the custom guilds are gameplay content.  Expanded
  Building Slots and the Freestyle CAM fix are manager runtime capabilities,
  not optional QOL selections.
