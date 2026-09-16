"""Parity and executable evidence for every cataloged stock building parent."""

import os
from pathlib import Path
import re
import struct
import unittest

from majesty_cam.stock_building_controllers import (
    STOCK_BUILDING_CONTROLLERS,
    is_stock_building_controller,
    is_stock_building_controller_pair,
)


EXPECTED_CONTROLLER_IDS = {
    "AP01", "AP02", "AP05", "AP06", "AP07", "AP08", "AP10", "AP14",
    "AP17", "AP19", "AP23", "AP24", "AP25", "AP26", "AP28", "AP31",
    "AP39", "AP47", "AP48", "AP51", "AP52", "AP53", "AP54", "AP76",
    "AP96", "APa9", "APb2", "APb3", "APb7", "APb8", "APc3", "APc4",
    "MX00", "MX02", "MX04", "MX06", "MX08", "MX09", "MX22",
}


class PeImage:
    def __init__(self, path: str) -> None:
        self.data = Path(path).read_bytes()
        header = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[header:header + 4] != b"PE\0\0":
            raise ValueError("not a PE image")
        count, self.timestamp = struct.unpack_from("<HI", self.data, header + 6)
        optional = struct.unpack_from("<H", self.data, header + 20)[0]
        self.base = struct.unpack_from("<I", self.data, header + 24 + 28)[0]
        self.sections = []
        for index in range(count):
            offset = header + 24 + optional + 40 * index
            virtual_size, address, raw_size, raw_offset = struct.unpack_from(
                "<4I", self.data, offset + 8
            )
            characteristics = struct.unpack_from("<I", self.data, offset + 36)[0]
            self.sections.append(
                (virtual_size, address, raw_size, raw_offset, characteristics)
            )

    def raw_offset(self, rva: int) -> int:
        for virtual_size, address, raw_size, offset, _ in self.sections:
            if address <= rva < address + min(raw_size, virtual_size):
                return offset + rva - address
        raise ValueError(f"RVA {rva:#x} is not file-backed")

    def words(self, rva: int, count: int) -> tuple[int, ...]:
        return struct.unpack_from(
            f"<{count}I", self.data, self.raw_offset(rva)
        )

    def is_executable_address(self, value: int) -> bool:
        rva = value - self.base
        return any(
            address <= rva < address + virtual_size
            and characteristics & 0x20000000
            for virtual_size, address, _, _, characteristics in self.sections
        )


def _native_catalog() -> dict[str, tuple[tuple[int, ...], tuple[int, ...]]]:
    source = (
        Path(__file__).resolve().parents[1]
        / "runtime/StockBuildingControllerCatalog.h"
    ).read_text()
    enum_body = re.search(
        r"enum class ControllerClass[^\{]*\{(.*?)\};", source, re.S
    )[1]
    class_names = [
        line.strip().rstrip(",")
        for line in enum_body.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]
    profiles_body = re.search(
        r"static const ClassProfiles kClassProfiles\[\] = \{(.*?)\n\};",
        source,
        re.S,
    )[1]
    profile_pairs = re.findall(
        r"\{\{([^{}]+)\},\s*\{([^{}]+)\}\}", profiles_body, re.S
    )
    self_profiles = []
    for public, beta2 in profile_pairs:
        pair = []
        for values in (public, beta2):
            tokens = re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", values)
            pair.append(tuple(int(token, 0) for token in tokens))
        self_profiles.append(tuple(pair))
    if len(self_profiles) != len(class_names):
        raise AssertionError("native class/profile catalog is structurally inconsistent")
    by_class = dict(zip(class_names, self_profiles))

    records_body = re.search(
        r"static const ControllerRecord kControllerRecords\[\] = \{(.*?)\n\};",
        source,
        re.S,
    )[1]
    records = {}
    for value, class_name, label in re.findall(
        r"\{(0x[0-9A-Fa-f]+)u,\s*ControllerClass::(\w+)\},\s*//\s*(\S+)",
        records_body,
    ):
        if int(value, 16) != int.from_bytes(label.encode("ascii"), "little"):
            raise AssertionError(f"native FourCC/comment mismatch: {label}")
        records[label] = by_class[class_name]
    return records


class StockBuildingControllerCatalogTests(unittest.TestCase):
    def test_catalog_covers_all_stock_primary_building_controllers(self) -> None:
        self.assertEqual(
            {record.controller_base for record in STOCK_BUILDING_CONTROLLERS},
            EXPECTED_CONTROLLER_IDS,
        )
        self.assertEqual(len(STOCK_BUILDING_CONTROLLERS), 39)
        for controller_id in EXPECTED_CONTROLLER_IDS:
            self.assertTrue(is_stock_building_controller(controller_id))
            self.assertTrue(
                is_stock_building_controller_pair(controller_id, controller_id)
            )
        self.assertTrue(is_stock_building_controller_pair("AP07", "AP10"))
        self.assertFalse(is_stock_building_controller_pair("AP08", "AP10"))
        self.assertFalse(is_stock_building_controller("AP03"))

    def test_python_and_native_catalogs_are_identical(self) -> None:
        native = _native_catalog()
        self.assertEqual(set(native), EXPECTED_CONTROLLER_IDS)
        for record in STOCK_BUILDING_CONTROLLERS:
            expected = (
                (
                    record.public.vtable_rva,
                    record.public.entry_count,
                    record.public.destructor_rva,
                    record.public.setup_rva,
                    record.public.control_rva,
                    record.public.event_rva,
                ),
                (
                    record.beta2.vtable_rva,
                    record.beta2.entry_count,
                    record.beta2.destructor_rva,
                    record.beta2.setup_rva,
                    record.beta2.control_rva,
                    record.beta2.event_rva,
                ),
            )
            self.assertEqual(native[record.controller_base], expected)

    def _verify_executable(self, variable: str, profile_name: str, timestamp: int) -> None:
        path = os.environ.get(variable)
        if not path:
            self.skipTest(f"{variable} is not set")
        image = PeImage(path)
        self.assertEqual(image.timestamp, timestamp)
        for record in STOCK_BUILDING_CONTROLLERS:
            profile = getattr(record, profile_name)
            table = image.words(profile.vtable_rva, profile.entry_count + 1)
            self.assertTrue(
                all(image.is_executable_address(value) for value in table[:-1]),
                record.controller_base,
            )
            self.assertFalse(
                image.is_executable_address(table[-1]),
                f"{record.controller_base} vtable count no longer ends at its class boundary",
            )
            self.assertEqual(
                tuple(table[index] - image.base for index in (0, 1, 3, 8)),
                (
                    profile.destructor_rva,
                    profile.setup_rva,
                    profile.control_rva,
                    profile.event_rva,
                ),
                record.controller_base,
            )

    def test_public_executable_profiles(self) -> None:
        self._verify_executable("MAJESTY_PUBLIC_EXE", "public", 0x5897B72F)

    def test_beta2_executable_profiles(self) -> None:
        self._verify_executable("MAJESTY_BETA2_EXE", "beta2", 0x5A8A11D5)


if __name__ == "__main__":
    unittest.main()
