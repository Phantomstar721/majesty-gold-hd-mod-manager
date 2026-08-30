# Majesty Mod Manager

![Majesty Mod Manager](workshop/workshop-preview.jpg)

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

## Compatibility and safety

The manager supports both maintained Steam versions:

- Default Public Version `1.5.2.24`
- `beta2` Steam Multiplayer Support `1.5.2.28`

The detected version and installation folder are shown at the top of the app.
Use **Choose…** if you want the manager to use a different supported
`MajestyHD.exe`.

## Building from source

Python 3.9 or newer is required:

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
