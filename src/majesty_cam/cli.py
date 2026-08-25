from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .cam import CamFormatError, read_cam
from .compose import ComposeError
from .poc import build_poc_profiles
from .workspace import pack_workspace, unpack_archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="majesty-cam")
    subcommands = parser.add_subparsers(dest="command", required=True)

    list_parser = subcommands.add_parser("list", help="List sections and entries in a CAM archive")
    list_parser.add_argument("cam", type=Path)

    verify_parser = subcommands.add_parser("verify", help="Verify read/write identity for a CAM archive")
    verify_parser.add_argument("cam", type=Path)

    unpack_parser = subcommands.add_parser("unpack", help="Unpack a CAM archive to a folder")
    unpack_parser.add_argument("cam", type=Path)
    unpack_parser.add_argument("output_dir", type=Path)
    unpack_parser.add_argument(
        "--allow-nonempty",
        action="store_true",
        help="Keep unrelated files already present in the output directory",
    )

    pack_parser = subcommands.add_parser("pack", help="Pack an unpacked CAM folder")
    pack_parser.add_argument("input_dir", type=Path)
    pack_parser.add_argument("output_cam", type=Path)

    poc_parser = subcommands.add_parser(
        "poc-build",
        help="Build Haunt-only, Alchemist-only, and combined proof profiles",
    )
    poc_parser.add_argument("--game-path", required=True, type=Path)
    poc_parser.add_argument("--input-root", required=True, type=Path)
    poc_parser.add_argument("--output-root", required=True, type=Path)
    poc_parser.add_argument("--definition-root", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            return _list(args.cam)
        if args.command == "verify":
            return _verify(args.cam)
        if args.command == "unpack":
            output_was_nonempty = (
                args.output_dir.is_dir() and any(args.output_dir.iterdir())
            )
            if args.allow_nonempty and output_was_nonempty:
                print(
                    "warning: unpacking into a nonempty directory; unrelated "
                    "existing files will remain",
                    file=sys.stderr,
                )
            unpack_archive(
                args.cam,
                args.output_dir,
                allow_nonempty=args.allow_nonempty,
            )
            print(f"Unpacked {args.cam} -> {args.output_dir}")
            return 0
        if args.command == "pack":
            pack_workspace(args.input_dir, args.output_cam)
            print(f"Packed {args.input_dir} -> {args.output_cam}")
            return 0
        if args.command == "poc-build":
            result = build_poc_profiles(
                args.game_path,
                args.input_root,
                args.output_root,
                definition_root=args.definition_root,
            )
            for profile in result.profiles:
                print(
                    f"Built {profile.profile_slug}: {profile.output_root} "
                    f"({profile.mod_id})"
                )
            return 0
    except (CamFormatError, ComposeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


def _list(cam_path: Path) -> int:
    archive = read_cam(cam_path)
    print(f"{cam_path}")
    print(f"sections: {len(archive.sections)}")
    for section_index, section in enumerate(archive.sections):
        extension = section.extension.decode("ascii", errors="replace")
        padding = section.padding.hex()
        print(
            f"[{section_index}] ext={extension!r} "
            f"entries={len(section.entries)} padding=0x{padding}"
        )
        for entry_index, entry in enumerate(section.entries[:10]):
            print(
                f"  {entry_index:05d} "
                f"name={entry.display_name!r} "
                f"offset={entry.data_offset} "
                f"size={len(entry.data)}"
            )
        remaining = len(section.entries) - 10
        if remaining > 0:
            print(f"  ... {remaining} more")
    return 0


def _verify(cam_path: Path) -> int:
    original = cam_path.read_bytes()
    archive = read_cam(original)
    repacked = archive.to_bytes()
    if repacked == original:
        print(f"OK: {cam_path} round-trips byte-for-byte")
        return 0

    print(f"FAIL: {cam_path} does not round-trip byte-for-byte", file=sys.stderr)
    print(f"original: {len(original)} bytes", file=sys.stderr)
    print(f"repacked: {len(repacked)} bytes", file=sys.stderr)
    for index, (old, new) in enumerate(zip(original, repacked)):
        if old != new:
            print(
                f"first difference at 0x{index:08X}: "
                f"original=0x{old:02X} repacked=0x{new:02X}",
                file=sys.stderr,
            )
            break
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
