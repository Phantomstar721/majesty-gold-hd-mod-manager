# Majesty CAM Tool

Early working repo for a community-friendly Majesty Gold HD CAM archive tool.

The live Majesty install should stay a reference and test target. This repo keeps code,
synthetic test fixtures, and documentation only. Do not commit proprietary game assets.

## Goals

- Inspect CAM archives without modifying them.
- Unpack CAM archives into an editable directory plus an order-preserving index.
- Repack directories back into valid CAM archives.
- Add focused helpers for audio first, then sprite/TILE workflows after the container
  tool is boringly reliable.

## Current Commands

```powershell
python -m majesty_cam.cli list path\to\archive.cam
python -m majesty_cam.cli verify path\to\archive.cam
python -m majesty_cam.cli unpack path\to\archive.cam local\unpacked
python -m majesty_cam.cli pack local\unpacked local\repacked.cam
```

## Local Setup

```powershell
cd C:\Users\bterr\source\repos\majesty-cam-tool
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m unittest discover -s tests
```

## Local Game Data

Use `local/` for anything copied from the game install while testing. It is ignored by
git on purpose.

Useful paths on this machine:

- SDK: `C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK`
- SDK example CAMs: `C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Example\Data`

## Reference Repos

Use `reference-repos/` for shallow clones of public research/tooling repos. It is also
ignored by git so third-party code and game data are not accidentally bundled.
