# Majesty Mod Manager native runtime

This directory contains the native Windows launcher and DLL used by Majesty
Mod Manager. They provide the game-side support required by compatible Merge
mods, including custom building dialogs, runtime capability selection,
Freestyle CAM corrections, private activity text, and private name resources.

The runtime supports the maintained Majesty Gold HD Steam executables:

- Default Public Version `1.5.2.24`
- `beta2` Steam Multiplayer Support `1.5.2.28`

Every executable hook is selected from an explicit version profile and checks
the expected stock bytes before making a change. Unknown executable builds or
unexpected bytes fail closed.

Build the launcher and DLL from the repository root with:

```powershell
.\scripts\Build-Runtime.ps1 -OutputRoot .\local\manager-runtime-release
```

The native runtime is part of Majesty Mod Manager and is licensed under the
repository's [MIT License](../LICENSE). `FreestyleCamRuntime.cpp` incorporates
work derived from `Iximi-Ixus/freestyle-cam-sidecar`; its retained MIT notice
is available at
[`licenses/FREESTYLE-CAM-SIDECAR.txt`](../licenses/FREESTYLE-CAM-SIDECAR.txt).

Technical references are kept in the repository's `docs` directory, including
the runtime build profiles and capability-manifest format.
