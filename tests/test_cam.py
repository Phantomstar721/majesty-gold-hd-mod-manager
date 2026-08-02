from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.cam import (
    CamArchive,
    CamEntry,
    CamFormatError,
    CamSection,
    pad_extension,
    pad_name,
    read_cam,
)
from majesty_cam.cli import main as cli_main
from majesty_cam.workspace import pack_workspace, unpack_archive


class CamTests(unittest.TestCase):
    def test_archive_round_trip_preserves_padding_and_bytes(self):
        archive = _sample_archive()

        packed = archive.to_bytes()
        parsed = read_cam(packed)

        self.assertEqual(parsed.to_bytes(), packed)
        self.assertEqual(parsed.sections[0].padding, b"\x01\x00\x00\x00")
        self.assertEqual(parsed.sections[1].padding, b"\x02\x00\x00\x00")
        self.assertEqual(
            parsed.sections[0].entries[1].name,
            b"\x00\x01binary-name".ljust(20, b"\x00"),
        )

    def test_unpack_pack_workspace_round_trip(self):
        archive = _sample_archive()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cam_path = tmp_path / "sample.cam"
            unpacked_path = tmp_path / "unpacked"
            repacked_path = tmp_path / "repacked.cam"
            cam_path.write_bytes(archive.to_bytes())

            unpack_archive(cam_path, unpacked_path)
            pack_workspace(unpacked_path, repacked_path)

            self.assertEqual(repacked_path.read_bytes(), cam_path.read_bytes())

    def test_unpack_rejects_nonempty_destination_without_changing_it(self):
        archive = _sample_archive()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cam_path = tmp_path / "sample.cam"
            unpacked_path = tmp_path / "unpacked"
            sentinel = unpacked_path / "stale.bin"
            cam_path.write_bytes(archive.to_bytes())
            unpacked_path.mkdir()
            sentinel.write_bytes(b"stale-data")

            with self.assertRaisesRegex(CamFormatError, "destination is not empty"):
                unpack_archive(cam_path, unpacked_path)

            self.assertEqual(sentinel.read_bytes(), b"stale-data")
            self.assertEqual(list(unpacked_path.iterdir()), [sentinel])

    def test_unpack_accepts_existing_empty_destination(self):
        archive = _sample_archive()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cam_path = tmp_path / "sample.cam"
            unpacked_path = tmp_path / "unpacked"
            cam_path.write_bytes(archive.to_bytes())
            unpacked_path.mkdir()

            unpack_archive(cam_path, unpacked_path)

            self.assertTrue((unpacked_path / ".majesty-cam.json").is_file())

    def test_unpack_allows_nonempty_destination_only_when_explicit(self):
        archive = _sample_archive()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cam_path = tmp_path / "sample.cam"
            unpacked_path = tmp_path / "unpacked"
            sentinel = unpacked_path / "stale.bin"
            cam_path.write_bytes(archive.to_bytes())
            unpacked_path.mkdir()
            sentinel.write_bytes(b"stale-data")

            unpack_archive(cam_path, unpacked_path, allow_nonempty=True)

            self.assertEqual(sentinel.read_bytes(), b"stale-data")
            self.assertTrue((unpacked_path / ".majesty-cam.json").is_file())

    def test_cli_warns_when_nonempty_destination_is_explicitly_allowed(self):
        archive = _sample_archive()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cam_path = tmp_path / "sample.cam"
            unpacked_path = tmp_path / "unpacked"
            cam_path.write_bytes(archive.to_bytes())
            unpacked_path.mkdir()
            (unpacked_path / "stale.bin").write_bytes(b"stale-data")
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = cli_main(
                    [
                        "unpack",
                        str(cam_path),
                        str(unpacked_path),
                        "--allow-nonempty",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertIn("warning: unpacking into a nonempty directory", stderr.getvalue())
            self.assertIn("Unpacked", stdout.getvalue())


def _sample_archive() -> CamArchive:
    return CamArchive(
        sections=(
            CamSection(
                extension=pad_extension("WAVE"),
                padding=b"\x01\x00\x00\x00",
                entries=(
                    CamEntry(name=pad_name("DQ10Voice"), data=b"RIFFfake-wave-data"),
                    CamEntry(name=b"\x00\x01binary-name".ljust(20, b"\x00"), data=b"\x00\x01\x02"),
                ),
            ),
            CamSection(
                extension=pad_extension("CUT"),
                padding=b"\x02\x00\x00\x00",
                entries=(
                    CamEntry(name=pad_name("TinyCut"), data=b"cut-data"),
                ),
            ),
        )
    )


if __name__ == "__main__":
    unittest.main()
