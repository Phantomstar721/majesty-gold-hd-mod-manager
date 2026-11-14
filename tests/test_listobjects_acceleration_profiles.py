"""$ListObjects acceleration: every audited profile row matches its executable.

runtime/ListObjectsAccelerationProfiles.h holds one row per audited build. This
test re-derives each row the way ListObjectsAcceleration::Install() checks it at
launch, and compares it with the independent signature-based audit in
scripts/audit_listobjects_acceleration.py. Executables are only read. A build
without a row keeps the stock callback (Install() refuses it); adding its row
makes this test cover it. See docs/listobjects-acceleration.md.
"""
import importlib.util
import os
from pathlib import Path
import re
import struct
import unittest

from test_occupant_runtime_profiles import PeImage

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {"SteamPublic": "MAJESTY_PUBLIC_EXE", "SteamBeta2": "MAJESTY_BETA2_EXE",
            "Gog": "MAJESTY_GOG_EXE"}
BODIES = ("list_objects", "filter", "get_property", "push_back", "resolve_agent",
          "attribute_lookup")
SIZE_CONSTANTS = {"list_objects": "kListObjectsSize", "filter": "kFilterSize",
                  "get_property": "kGetPropertySize", "push_back": "kPushBackSize",
                  "resolve_agent": "kResolveAgentSize",
                  "attribute_lookup": "kAttributeLookupSize"}
CALLS = ("UnitPosition", "RectDistance", "AnchorDistance", "TeamOf", "ComponentFind",
         "AgentRefCtor", "GetProperty", "UnitAttribute", "GplManager", "ValueNew",
         "AgentRefDtor", "PushBack")
GLOBALS = ("Inside", "Anchor", "PointGiven", "Point", "RangeLimit", "PlayerFilter",
           "TeamFilter", "TeamTable", "TypeKey", "TypeString", "CheckKey", "CheckString",
           "AttributeCount", "AttributeIds", "AttributeValues", "Results", "FirstOnly")


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def snake(name):
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


def profile_header():
    text = (ROOT / "runtime/ListObjectsAccelerationProfiles.h").read_text()
    rows = [(build, [int(value, 16) for value in values.split(",")])
            for build, values in re.findall(r"\{MajestyBuildId::(\w+),([^}]*)\}", text)]
    constants = {name: int(value, 16) for name, value in
                 re.findall(r"\b(k\w+Size|kPushSite) = (0x[0-9A-Fa-f]+)", text)}

    def operands(namespace):
        block = re.search(r"namespace " + namespace + r" \{(.*?)\}", text, re.S)[1]
        return {name: int(value, 16)
                for name, value in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", block)}

    return rows, constants, operands("FilterOperand"), operands("GetPropertyOperand")


def load_audit():
    path = ROOT / "scripts/audit_listobjects_acceleration.py"
    spec = importlib.util.spec_from_file_location("audit_listobjects_acceleration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Executable:
    """Read-only virtual-address view of one fixture executable."""

    def __init__(self, path):
        self.image = PeImage(path)
        self.base = self.image.base
        data = self.image.data
        header = struct.unpack_from("<I", data, 0x3C)[0]
        count = struct.unpack_from("<H", data, header + 6)[0]
        table = header + 24 + struct.unpack_from("<H", data, header + 20)[0]
        self.sections = {}
        for index in range(count):
            entry = table + 40 * index
            name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
            size, address = struct.unpack_from("<II", data, entry + 8)
            self.sections[name] = (self.base + address, self.base + address + size)

    def read(self, va, size):
        return self.image.read(va - self.base, size)

    def word(self, va):
        return struct.unpack("<I", self.read(va, 4))[0]

    def relative(self, function, operand):
        displacement = struct.unpack("<i", self.read(function + operand, 4))[0]
        return (function + operand + 4 + displacement) & 0xFFFFFFFF

    def within(self, section, va, size=1):
        start, end = self.sections[section]
        return start <= va and va + size <= end


class ListObjectsAccelerationProfiles(unittest.TestCase):
    def setUp(self):
        self.rows, self.constants, self.filter_operands, self.property_operands = profile_header()

    def fixture(self, build):
        path = os.environ.get(FIXTURES[build])
        self.assertTrue(path, FIXTURES[build] + " is required")
        return path

    def test_rows_name_distinct_supported_builds(self):
        builds = [build for build, _ in self.rows]
        self.assertTrue(builds, "no audited profile rows")
        self.assertEqual(len(builds), len(set(builds)))
        for build, values in self.rows:
            self.assertIn(build, FIXTURES)
            self.assertEqual(len(values), 8, build)

    def test_rows_hold_for_their_executables_as_install_checks_them(self):
        for build, values in self.rows:
            with self.subTest(build=build):
                self.check_row(Executable(self.fixture(build)), values)

    def test_rows_and_decode_offsets_match_the_signature_audit(self):
        audit = load_audit()
        self.assertEqual(dict(audit.SIZES),
                         {name: self.constants[SIZE_CONSTANTS[name]] for name in BODIES})
        self.assertEqual(audit.PUSH_SITE, self.constants["kPushSite"])
        self.assertEqual({name: offset for name, offset, _, _ in audit.FILTER_OPERANDS},
                         {snake(name): offset for name, offset in self.filter_operands.items()})
        self.assertEqual({name: offset for name, offset, _ in audit.GET_PROPERTY_OPERANDS},
                         {snake(name): offset for name, offset in self.property_operands.items()})
        for build, values in self.rows:
            with self.subTest(build=build):
                found, _, _, va, _, hashes = audit.audit(self.fixture(build))
                self.assertEqual(found, build)
                self.assertEqual([va["list_objects"] - 0x400000, va["filter"] - 0x400000]
                                 + [hashes[name] for name in BODIES], values)

    def check_row(self, exe, values):
        self.assertEqual(exe.base, 0x400000)
        operand = self.filter_operands
        size = {name: self.constants[SIZE_CONSTANTS[name]] for name in BODIES}
        expected = dict(zip(BODIES, values[2:]))
        list_objects, filter_ = exe.base + values[0], exe.base + values[1]
        body = {"list_objects": list_objects, "filter": filter_}

        def guarded(name):
            self.assertTrue(exe.within(".text", body[name], size[name]), name)
            self.assertEqual(fnv1a(exe.read(body[name], size[name])), expected[name], name)

        # Same order as Install(): a body is decoded only after its hash matched.
        guarded("list_objects")
        guarded("filter")
        body["get_property"] = exe.relative(filter_, operand["GetProperty"])
        body["push_back"] = exe.relative(filter_, operand["PushBack"])
        guarded("get_property")
        guarded("push_back")
        body["resolve_agent"] = exe.relative(body["get_property"],
                                             self.property_operands["ResolveAgent"])
        body["attribute_lookup"] = exe.relative(body["get_property"],
                                                self.property_operands["AttributeLookup"])
        guarded("resolve_agent")
        guarded("attribute_lookup")

        # The single hand-over: PUSH 0, PUSH 0, PUSH <filter>, CALL EAX. No other
        # copy of the filter address exists, so the one operand is the only route.
        push = list_objects + self.constants["kPushSite"]
        self.assertEqual(exe.read(push - 4, 11), bytes.fromhex("6a006a0068")
                         + struct.pack("<I", filter_) + bytes.fromhex("ffd0"))
        self.assertEqual(exe.image.data.count(struct.pack("<I", filter_)), 1)

        # The property getter and the filter share the GPL manager getter.
        self.assertEqual(exe.relative(body["get_property"], self.property_operands["GplManager"]),
                         exe.relative(filter_, operand["GplManager"]))
        for name in CALLS:
            self.assertEqual(exe.read(filter_ + operand[name] - 1, 1), b"\xe8", name)
            self.assertTrue(exe.within(".text", exe.relative(filter_, operand[name])), name)
        for name in GLOBALS:
            self.assertTrue(exe.within(".data", exe.word(filter_ + operand[name])), name)
        self.assertTrue(exe.within(".rdata", exe.word(filter_ + operand["StricmpImport"]), 4))
        # Attribute values are indexed from the count itself (stock 1-based pairs).
        self.assertEqual(exe.word(filter_ + operand["AttributeValues"]),
                         exe.word(filter_ + operand["AttributeCount"]))


if __name__ == "__main__":
    unittest.main()
