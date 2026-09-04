"""Read-only proof of the MX22 toggle lifecycle in supported executables."""

import os
from pathlib import Path
import struct
import unittest


class PeImage:
    def __init__(self, path: str):
        self.data = Path(path).read_bytes()
        header = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[header:header + 4] != b"PE\0\0":
            raise ValueError("not a PE image")
        count, self.timestamp = struct.unpack_from("<HI", self.data, header + 6)
        optional = struct.unpack_from("<H", self.data, header + 20)[0]
        self.sections = [
            struct.unpack_from("<4I", self.data, header + 24 + optional + 40 * index + 8)
            for index in range(count)
        ]

    def read(self, rva: int, size: int) -> bytes:
        for virtual_size, address, raw_size, offset in self.sections:
            if address <= rva and rva + size <= address + min(raw_size, virtual_size):
                start = offset + rva - address
                return self.data[start:start + size]
        raise ValueError(f"RVA {rva:#x} is not file-backed")


class BuildingToggleRuntimeProfileTests(unittest.TestCase):
    def verify(self, variable: str, timestamp: int, handler: int, presenter: int) -> None:
        path = os.environ.get(variable)
        if not path:
            self.skipTest(f"{variable} is not set")
        image = PeImage(path)
        self.assertEqual(image.timestamp, timestamp)
        # Both builds use the same command range, including MX22's 22AB/22AC.
        self.assertEqual(
            image.read(handler, 28),
            bytes.fromhex(
                "8b 44 24 04 56 33 f6 3d 12 1f 00 00 74 3b 3d aa 22 00 00 "
                "7e 2a 3d ac 22 00 00 7f 23"
            ),
        )
        # Presenter begins with the same stock controller/context sequence.
        self.assertEqual(image.read(presenter, 9), bytes.fromhex("83 ec 24 53 55 56 57 8b f1"))

    def test_public(self) -> None:
        self.verify("MAJESTY_PUBLIC_EXE", 0x5897B72F, 0x000B9540, 0x000B95A0)

    def test_beta2(self) -> None:
        self.verify("MAJESTY_BETA2_EXE", 0x5A8A11D5, 0x000B9F80, 0x000B9FE0)


if __name__ == "__main__":
    unittest.main()
