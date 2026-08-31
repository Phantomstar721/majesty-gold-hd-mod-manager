# Majesty Mod Manager

![Majesty Mod Manager](artwork/workshop-preview.jpg)

Majesty Gold HD Mod Manager is a Windows app for finding, organizing, and
launching the **Majesty Gold HD** mods and quests you have installed or
subscribed to through Steam Workshop.

It also provides the extra support required by more complicated mods, such as
custom guilds, so compatible mods can be used individually or together without
overwriting one another.

## Features

- Finds local and Steam Workshop mods and downloaded quests automatically.
- Organizes content into **Merge**, **Standard**, **Quests**, and
  **Quality of Life** tabs.
- Enables detected mods by default and remembers your later choices.
- Clearly marks content that cannot be combined safely.
- Prepares one playable package when selected mods need to be combined.
- Leaves subscribed mods and downloaded quests unchanged.
- Installs and manages the supported Majesty quality-of-life patches.
- Supports both maintained Steam versions of Majesty Gold HD.
- Launches the game with the additional support required by prepared mods and
  Freestyle games.

## Install and use

The Steam Workshop download contains the complete application. Keep
`Majesty Mod Manager.exe` beside its `_internal` folder.

1. Subscribe to the Mod Manager and the Majesty mods or quests you want to use.
2. Open the Mod Manager's Workshop folder and run
   `Majesty Mod Manager.exe`.
3. Follow the first-time prompt to install the two required game helpers.
4. Review the detected content and choose what you want enabled.
5. Select **Prepare Selected Mods** if the Merge tab contains selected mods.
6. Select **Launch Majesty**.

Continue launching through the manager whenever prepared Merge content is
enabled. Ordinary Standard mods and downloaded quests remain usable through
Majesty normally.

## Content tabs

| Tab | Purpose |
| --- | --- |
| **Merge** | Compatible content that needs the manager to work safely alongside other complex mods. |
| **Standard** | Ordinary Majesty mods that the game can load independently. |
| **Quests** | Downloaded adventures and maps available through Majesty's quest browser. |
| **Quality of Life** | Optional game improvements that can be installed or removed individually. |

Items that do not change the game, such as modding tools, are identified but
are not selectable. If a Merge mod is missing required compatibility
information, the manager displays it in red with an explanation instead of
building an unsafe package.

## For mod creators: making a mod compatible

A compatible Merge mod does not need to be hardcoded into the Mod Manager. If
the distributed package follows this format and passes validation, the manager
can detect and combine it automatically. The current public format covers
custom-building packages that contain CAM and GPL content.

### Package layout

Place exactly one `.mmxml` manifest and one `mod-definition.json` in the top
level of the distributed mod folder:

```text
YourMod/
|-- YourMod.mmxml
|-- mod-definition.json
|-- Data/
|   |-- your_mod_data.cam
|   |-- your_mod_interface.cam
|   |-- your_mod.bcd
|   `-- your_descriptions.xml
|-- GPL/
|   |-- your_mod.gpl
|   `-- your_data.dat
`-- Assets/
    `-- any additional files
```

The subfolder names are flexible. Every path used by the `.mmxml` must be
relative to the package, remain inside it, and point to a file included in the
distributed package.

The `.mmxml` must:

- Have a stable, unique Mod UUID and a player-facing display name.
- Contain one `Dataset base="Any"`.
- Use only `CAM`, `Descriptions`, and `GPL` load directives.
- Include at least one CAM load and one GPL load.
- List the compiled GPL target and every `.gpl` or `.dat` source needed to
  rebuild it.
- Include every description, artwork, sound, and data file required by the
  mod.

### Mod definition

The top-level `mod-definition.json` must use schema version 2:

```json
{
  "schema_version": 2,
  "mod_id": "{the-same-uuid-used-by-your-mmxml}",
  "internal_name": "YourNamespacedModName",
  "display_name": "Your Player-Facing Mod Name",
  "custom_buildings": [
    {
      "local_name": "YourNamespacedBuildingID",
      "dialog_id": "CGXX",
      "controller_base": "AP10",
      "panel_resource_template": "AP10"
    }
  ],
  "runtime_capabilities": []
}
```

`schema_version` identifies the Mod Manager compatibility-file format, not the
version of the mod. Keep it at `2` unless a future Mod Manager specification
introduces another supported format.

Replace `CGXX` with a unique four-character ID beginning with `CG` and ending
with two uppercase letters or digits. `controller_base` and
`panel_resource_template` identify the stock Majesty building behavior and
panel layout that the custom building follows.

Leave `runtime_capabilities` empty unless the mod uses one of the optional,
reusable features documented by the Mod Manager. Normal custom guilds and
stock-based building panels do not require a package-specific capability. The
manager automatically supplies shared building-slot, Freestyle, visitor-list,
and compatible custom-text support. Unsupported capability names are rejected
rather than guessed.

### Content requirements

- Namespace all custom Description IDs, CAM resource keys, GPL functions and
  expressions, DAT blocks, dialog IDs, artwork, and sound filenames.
- Ship complete effective tables when changing resources Majesty treats as
  positional or whole-table data.
- Preserve unchanged stock entries, ordering, flags, padding, and references.
- Include a complete BDEP table and exactly one main and one interface
  TILE/IMAG provider.
- Use named inventory items for new carried items rather than adding private
  numeric QITM rows.
- Do not depend on files from an authoring repository or another Workshop
  folder.

The manager currently supports CAM sections `SMNU`, `STRT`, `DATA`, `IMAG`,
`TILE`, `SPLT`, `DSND`, and `WAVE`, with `BDEP` supported inside `DATA`.
Packages using other resource structures require additional typed support
before they can be merged safely.

### Testing compatibility

Install the finished package exactly as players will receive it and select
**Rescan Content** in the Mod Manager. A package that passes validation appears
in the Merge tab as selectable. If required information is missing or an
unsupported structure is detected, the mod appears in red with the reason it
cannot be combined.

For the complete technical rules, see the
[Merge mod authoring guide](docs/manager-merge-contract.md).

## Compatibility and safety

The manager supports both maintained Steam versions:

- Default Public Version `1.5.2.24`
- `beta2` Steam Multiplayer Support `1.5.2.28`

The detected version and installation folder are shown at the top of the app.
Use **Choose…** if you want the manager to use a different supported
`MajestyHD.exe`.

## Building from source

Python 3.9 or newer is required. Building the native runtime also requires the
x86 Visual C++ build tools and a Windows 10 SDK:

```powershell
.\Setup - Majesty Mod Manager.bat
.\Launch - Majesty Mod Manager.bat
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Build the standalone Windows application with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Build-ModManagerExe.ps1
```

The finished application is written to `dist\Majesty Mod Manager`.

Mod authors interested in making compatible content can read the
[Merge mod authoring guide](docs/manager-merge-contract.md).

## Community

Join the Majesty community on [Discord](https://discord.gg/MEjtKZb9GQ).

## License

The Majesty Gold HD Mod Manager source and project-owned artwork are licensed
under the [MIT License](LICENSE).

The packaged application contains separately licensed components. Their
licenses, notices, and source links are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md), and the Workshop package
includes the applicable license texts.

Majesty Gold HD and its assets are the property of their respective owners.
This project is an independent community tool and is not affiliated with or
endorsed by the game's rights holders, Valve, or Steam.
