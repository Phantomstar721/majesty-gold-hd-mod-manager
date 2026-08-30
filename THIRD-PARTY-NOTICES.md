# Third-party notices

The standalone Majesty Mod Manager distribution contains the components below.
Their licenses apply only to the corresponding components and do not replace
the manager's MIT license.

## Python 3.9

The packaged application includes the CPython interpreter and standard library.
Python is distributed under the Python Software Foundation License and other
historical notices included in `licenses/PYTHON-3.9.txt` in the Workshop
package.

Source: https://www.python.org/downloads/source/

## PySide6, Shiboken6, and Qt 6.8.3

The graphical interface uses PySide6 Essentials, Shiboken6, and dynamically
loaded Qt libraries, version 6.8.3. The packaged copies are distributed under
the GNU Lesser General Public License version 3 option offered by the Qt for
Python project. The LGPLv3 and incorporated GPLv3 texts are included as
`licenses/LGPL-3.0.txt` and `licenses/GPL-3.0.txt`.

The distribution keeps the Qt libraries as separate DLLs so recipients can
replace them with compatible modified versions. Corresponding source is
available from the upstream projects:

- https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.8.3
- https://download.qt.io/archive/qt/6.8/6.8.3/submodules/

## PyInstaller 6.22.2 bootloader

The Windows executable uses the PyInstaller bootloader. PyInstaller is licensed
under GPL version 2 or later with a bootloader exception that permits embedding
and distributing the bootloader with this application. The complete terms are
included as `licenses/PYINSTALLER.txt`.

Source: https://github.com/pyinstaller/pyinstaller/tree/v6.22.2

## Majesty Mod Manager native runtime

The native launcher and DLL are maintained as part of Majesty Mod Manager and
licensed under the repository's MIT license. Their complete source is included
in the public repository under `runtime`, with build scripts and tests retained
alongside the manager source.

Source: https://github.com/Phantomstar721/majesty-gold-hd-mod-manager/tree/main/runtime

The Freestyle CAM support incorporates work derived from
`Iximi-Ixus/freestyle-cam-sidecar`, licensed under MIT. Its retained notice is
included as `licenses/FREESTYLE-CAM-SIDECAR.txt`.

Source: https://github.com/Iximi-Ixus/freestyle-cam-sidecar

## Majesty Gold HD quality-of-life utilities

The distribution includes the version-checked quality-of-life patch scripts,
including Generic Visitor Lists and Remember Active Mods. These utilities are
licensed under MIT by Phantomstar721. Their aggregate and component license
files remain beside the bundled scripts.

Source: https://github.com/Phantomstar721/majesty-gold-hd-qol-utilities

## Custom Guild: Phantoms Haunt compatibility content

The packaged manager includes a manager-compatible edition of Custom Guild:
Phantoms Haunt so players who select the original Workshop mod retain the stock
Elf Guild. That authored game-mod content is distributed with the manager by
its author and is not relicensed under the manager's MIT license.

Source: https://github.com/Phantomstar721/majesty-gold-hd-custom-guild-phantoms-haunt

## Steam icon

The Steam link button uses `Steam icon logo.svg` from Wikimedia Commons. The
source page classifies the simple geometric image as public domain in the
United States. Steam and the Steam logo are trademarks of Valve Corporation;
their descriptive use does not imply endorsement. Full provenance is retained
as `STEAM-ICON-NOTICE.txt` in the application and Workshop license folder.

Source: https://commons.wikimedia.org/wiki/File:Steam_icon_logo.svg

## Majesty Gold HD

Majesty Gold HD, its trademarks, and its assets belong to their respective
owners. The manager does not bundle stock game archives or extracted stock
art. Its Majesty-themed interface art is read from the player's installed game
at runtime. This project is independent and is not endorsed by the game's
rights holders.
