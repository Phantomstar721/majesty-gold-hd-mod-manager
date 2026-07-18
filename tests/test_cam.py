from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.cam import CamArchive, CamEntry, CamSection, pad_extension, pad_name, read_cam
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
