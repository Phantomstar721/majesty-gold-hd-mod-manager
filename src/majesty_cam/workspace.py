from __future__ import annotations

import json
from pathlib import Path
import re

from .cam import CamArchive, CamEntry, CamFormatError, CamSection, read_cam, write_cam


MANIFEST_NAME = ".majesty-cam.json"
MANIFEST_VERSION = 1


def unpack_archive(cam_path: str | Path, output_dir: str | Path) -> None:
    archive = read_cam(cam_path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "version": MANIFEST_VERSION,
        "source": str(cam_path),
        "sections": [],
    }

    manifest_sections: list[dict[str, object]] = []
    for section_index, section in enumerate(archive.sections):
        ext_label = _safe_label(section.display_extension or "section")
        section_dir = f"{section_index:02d}_{ext_label}"
        section_path = root / section_dir
        section_path.mkdir(parents=True, exist_ok=True)

        manifest_entries: list[dict[str, str]] = []
        suffix = section.display_extension or "bin"
        for entry_index, entry in enumerate(section.entries):
            label = _safe_label(entry.display_name or "entry")
            file_name = f"{entry_index:06d}_{label}.{suffix}"
            rel_path = Path(section_dir, file_name).as_posix()
            (root / rel_path).write_bytes(entry.data)
            manifest_entries.append(
                {
                    "name_hex": entry.name.hex(),
                    "file": rel_path,
                }
            )

        manifest_sections.append(
            {
                "extension_hex": section.extension.hex(),
                "padding_hex": section.padding.hex(),
                "entries": manifest_entries,
            }
        )

    manifest["sections"] = manifest_sections
    (root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def pack_workspace(input_dir: str | Path, output_cam: str | Path) -> None:
    root = Path(input_dir)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        raise CamFormatError(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != MANIFEST_VERSION:
        raise CamFormatError(f"Unsupported manifest version: {manifest.get('version')!r}")

    sections: list[CamSection] = []
    for section_data in manifest["sections"]:
        entries: list[CamEntry] = []
        for entry_data in section_data["entries"]:
            data_path = root / entry_data["file"]
            entries.append(
                CamEntry(
                    name=bytes.fromhex(entry_data["name_hex"]),
                    data=data_path.read_bytes(),
                )
            )

        sections.append(
            CamSection(
                extension=bytes.fromhex(section_data["extension_hex"]),
                padding=bytes.fromhex(section_data["padding_hex"]),
                entries=tuple(entries),
            )
        )

    write_cam(CamArchive(sections=tuple(sections)), output_cam)


def _safe_label(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"[^A-Za-z0-9._ -]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:80] or "entry"
