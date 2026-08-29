# Majesty Mod Manager

Majesty Mod Manager is a Windows desktop app for organizing and launching
**Majesty Gold HD** mods. It keeps ordinary mods independent, lists downloaded
quests, manages compatible quality-of-life improvements, and safely combines
supported CAM-based content mods into one playable setup.

The manager is currently in private preview. It supports both Steam game
executables:

- Default Public Version `1.5.2.24`
- `beta2` Steam Multiplayer Support `1.5.2.28`

## What it does

The app scans the normal Majesty Mods and Quests folders plus subscribed Steam
Workshop items, then presents four player-facing tabs:

- **Merge** contains compatible mods that replace shared Majesty data. Choose
  any supported combination and select **Prepare Selected Mods** to build one
  combined package.
- **Standard** contains ordinary mods that Majesty can load independently.
- **Quests** lists downloaded adventures and maps. They remain available
  through Majesty's normal quest browser.
- **Quality of Life** installs or removes the supported utility patches. Each
  optional improvement remains independent.

All compatible detected mods begin enabled. The manager remembers later
choices and restores them on the next run. Mods that cannot yet be combined
safely are shown in red with a plain explanation and cannot be selected.

When Merge mods are selected, the manager:

1. compares each package with the installed stock game data;
2. combines independent data, descriptions, artwork, audio, and game-script
   changes;
3. recompiles and validates one private local package;
4. leaves every source mod and downloaded quest untouched; and
5. launches Majesty through the bundled runtime required by combined custom
   guilds and Freestyle mode.

Custom activity messages are discovered from every selected compatible
package and assigned stable private IDs. This prevents downloaded quests from
overwriting those messages without requiring a manager-specific copy of each
quest.

The original **Custom Guild: Phantoms Haunt** is recognized automatically. If
selected, the manager uses its included compatibility edition, which keeps the
stock Elf Guild intact while providing the Phantom guild separately.

## Install and use

The Steam Workshop download contains the complete windowed application.
Keep `Majesty Mod Manager.exe` beside its `_internal` folder.

1. Close Majesty Gold HD.
2. Run `Majesty Mod Manager.exe` and approve the Windows administrator prompt.
3. On first use, open **Quality of Life** and install the two required helpers
   when prompted.
4. Review the automatically selected mods. Incompatible Merge entries explain
   what they need.
5. If Merge mods are selected, choose **Prepare Selected Mods**.
6. Choose **Launch Majesty**.

Always launch through the manager while using prepared Merge content. Standard
mods can still be used without a prepared package.

The application is community-built and is not code-signed, so Windows may show
a SmartScreen warning. Use **More info > Run anyway** only when the download
came from the official Workshop item or this repository's releases.

## Compatibility and safety

Majesty normally lets complete CAM tables overwrite one another according to
load order. The manager instead performs a stock-relative merge and stops when
it cannot prove that a result is safe. It never silently chooses one conflicting
mod over another.

A generic Merge mod must include the files and versioned compatibility
definition described in the
[merge-mod authoring contract](docs/manager-merge-contract.md). Existing legacy
mods can be supported through audited external compatibility profiles. New
native runtime behavior must declare a manager-supported capability; unknown
capabilities are rejected rather than guessed.

The manager currently supports the package structures exercised by Custom
Guild: Phantoms Haunt and Custom Guild: Alchemist Lab. Broader compatibility
will grow as independently authored CAM mods become available for testing.

The two required launch helpers are:

- **Generic Visitor Lists**, which safely displays custom guild visitors; and
- **Remember Active Mods**, which restores the exact selection prepared by the
  manager when Majesty starts.

They are installed through version-checked patchers and coexist with the other
quality-of-life utilities offered in the app. Unknown Majesty executables are
rejected before executable changes are applied.

## Build from source

Python 3.9 or newer is required for source development:

```powershell
.\Setup - Majesty Mod Manager.bat
.\Launch - Majesty Mod Manager.bat
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Build the redistributable windowed application with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Build-ModManagerExe.ps1
```

The complete application is written to `dist\Majesty Mod Manager`. It is a
one-directory build by design: the bundled runtime and support files must remain
available for the full Majesty session.

Maintainers can prepare an RGSEditor upload directory with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Stage-Workshop.ps1
```

## License

The Majesty Mod Manager source and project-owned artwork are licensed under the
MIT License. See [LICENSE](LICENSE).

The packaged application also contains separately licensed components,
including Python, PySide6/Qt, the PyInstaller bootloader, the Expanded Building
Slots runtime, and the Majesty quality-of-life utilities. Their notices and
source links are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md), and the Workshop package
includes the applicable license texts.

Majesty Gold HD and its assets are the property of their respective owners.
This project is an independent community tool and is not affiliated with or
endorsed by the game's rights holders, Valve, or Steam.
