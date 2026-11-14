"""Audit the stock $ListObjects boundary and print the runtime acceleration profile.

Usage:
    python scripts/audit_listobjects_acceleration.py [MajestyHD.exe ...]

Without arguments the script reads MAJESTY_PUBLIC_EXE, MAJESTY_BETA2_EXE and
MAJESTY_GOG_EXE (whichever are set).  Nothing is written.

For each executable it:
  * finds the stock $ListObjects implementation and its per-unit filter callback
    by signature (exactly one match each is required);
  * checks the single `push <filter>` site that hands the filter to each
    candidate collection's ForEach;
  * decodes every helper call and global the filter uses from fixed operand
    offsets, checking the opcode bytes in front of each operand;
  * follows the filter's property lookup to the agent resolver and attribute
    lookup, and checks the structural facts the accelerated filter relies on;
  * prints FNV-1a hashes of every guarded body and the C++ profile row for
    runtime/ListObjectsAccelerationProfiles.h.

See docs/listobjects-acceleration.md for the stock lifecycle and the evidence.
"""
import os
import re
import struct
import sys

BUILDS = {
    0x5897B72F: ("SteamPublic", "default Steam 1.5.2.24"),
    0x5A8A11D5: ("SteamBeta2", "Steam beta2 1.5.2.28"),
    0x5BBB8DB8: ("Gog", "GOG 1.5.2.28"),
}

LIST_OBJECTS_SIGNATURE = (
    "6A FF 68 ?? ?? ?? ?? 64 A1 00 00 00 00 50 83 EC 48 53 55 56 57 A1 ?? ?? ?? ?? "
    "33 C4 50 8D 44 24 5C 64 A3 00 00 00 00 8B 6C 24 6C 6A 01 8B CD E8 ?? ?? ?? ?? "
    "8B 08 8B 01 8B 50 5C FF D2 8B C8 E8 ?? ?? ?? ?? 33 FF A3")
FILTER_SIGNATURE = (
    "6A FF 68 ?? ?? ?? ?? 64 A1 00 00 00 00 50 83 EC 20 53 55 56 57 A1 ?? ?? ?? ?? "
    "33 C4 50 8D 44 24 34 64 A3 00 00 00 00 8B 6C 24 44 8B 85 84 00 00 00 85 C0 74 0D 80 3D")

# Guarded byte ranges (identical instruction layout on every audited build).
SIZES = {
    "list_objects": 0x674,   # code up to the modifier jump table
    "filter": 0x2D1,         # the whole callback, through its final RET
    "get_property": 0xA3,    # agent-reference property lookup, through the throw call
    "push_back": 0x32,       # result-vector push_back
    "resolve_agent": 0x8,    # MOV ECX,[ECX+4] / JMP agent-table find
    "attribute_lookup": 0x65,  # deleted-agent check through the container lookup call
}
PUSH_SITE = 0x432  # `push <filter>` inside $ListObjects, between PUSH 0 / PUSH 0 and CALL EAX

# (name, operand offset inside the filter, kind, expected opcode bytes in front of it)
FILTER_OPERANDS = [
    ("inside", 0x37, "abs", "80 3D"),
    ("anchor", 0x44, "abs", "8B 0D"),
    ("point_given", 0x52, "abs", "80 3D"),
    ("point", 0x5A, "abs", "68"),
    ("unit_position", 0x68, "rel", "E8"),
    ("rect_distance", 0x70, "rel", "E8"),
    ("anchor_distance", 0x78, "rel", "E8"),
    ("range_limit", 0x81, "abs", "A1"),
    ("player_filter", 0x94, "abs", "A1"),
    ("team_filter", 0xCE, "abs", "83 3D"),
    ("team_table", 0xDE, "abs", "8B 0D"),
    ("team_of", 0xE3, "rel", "E8"),
    ("component_find", 0x142, "rel", "E8"),
    ("agent_ref_ctor", 0x154, "rel", "E8"),
    ("type_key", 0x161, "abs", "68"),
    ("get_property", 0x16A, "rel", "E8"),
    ("type_string", 0x170, "abs", "83 3D"),
    ("stricmp_import", 0x177, "abs", "8B 1D"),
    ("check_key", 0x19E, "abs", "A1"),
    ("check_string", 0x1A8, "abs", "83 3D"),
    ("attribute_count", 0x1DD, "abs", "8B 35"),
    ("attribute_ids", 0x1E8, "abs", "8B 0C B5"),
    ("unit_attribute", 0x1F2, "rel", "E8"),
    ("attribute_values", 0x1F9, "abs", "3B 04 B5"),
    ("gpl_manager", 0x209, "rel", "E8"),
    ("value_new", 0x213, "rel", "E8"),
    ("agent_ref_dtor", 0x248, "rel", "E8"),
    ("results", 0x266, "abs", "B9"),
    ("push_back", 0x273, "rel", "E8"),
    ("first_only", 0x279, "abs", "80 3D"),
]
GET_PROPERTY_OPERANDS = [
    ("gpl_manager", 0x2B, "E8"),
    ("resolve_agent", 0x32, "E8"),
    ("attribute_lookup", 0x4B, "E8"),
]
# Structural facts the accelerated filter relies on, as (function, offset, bytes).
INVARIANTS = [
    ("filter", 0x2B, "8B 85 84 00 00 00", "indoor unit = host id at unit+0x84"),
    ("filter", 0xA4, "8B 91 80 00 00 00 3B 95 80 00 00 00", "player id at unit+0x80"),
    ("filter", 0xF5, "8B 42 1C", "unit player for team tests = virtual +0x1C"),
    ("filter", 0x13A, "68 41 45 00 00", "agent component key 'AE' = 0x4541"),
    ("filter", 0x181, "8B 42 30", "property text = virtual +0x30"),
    ("filter", 0x210, "6A 05", "new GPL value kind 5 (agent)"),
    ("filter", 0x20D, "8B 48 1C", "value factory at GPL manager+0x1C"),
    ("filter", 0x237, "8B 42 18", "value is set from an agent reference through virtual +0x18"),
    ("get_property", 0x3D, "80 78 38 00", "deleted agent flag at agent+0x38"),
    ("push_back", 0x07, "8B 7E 10 39 7E 0C", "result vector first/last at +0x0C/+0x10"),
    ("resolve_agent", 0x00, "8B 49 04 E9", "agent resolver thunk"),
    ("attribute_lookup", 0x29, "80 7E 38 00", "attribute lookup rejects deleted agents first"),
]


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def signature_regex(text):
    parts = [b"." if token == "??" else re.escape(bytes([int(token, 16)])) for token in text.split()]
    return re.compile(b"".join(parts), re.DOTALL)


class Image:
    def __init__(self, path):
        with open(path, "rb") as handle:
            self.data = handle.read()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("not a PE file")
        self.stamp = struct.unpack_from("<I", self.data, pe + 8)[0]
        count = struct.unpack_from("<H", self.data, pe + 6)[0]
        optional = pe + 24
        self.base = struct.unpack_from("<I", self.data, optional + 28)[0]
        table = optional + struct.unpack_from("<H", self.data, pe + 20)[0]
        self.sections = []
        for index in range(count):
            entry = table + index * 40
            name = self.data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, rva, rsize, roff = struct.unpack_from("<IIII", self.data, entry + 8)
            self.sections.append((name, self.base + rva, max(vsize, rsize), roff, rsize))

    def section_of(self, va):
        for name, start, size, _, _ in self.sections:
            if start <= va < start + size:
                return name
        return None

    def offset(self, va):
        for _, start, size, roff, rsize in self.sections:
            if start <= va < start + size and va - start < rsize:
                return roff + (va - start)
        raise ValueError("VA %08X is not backed by file data" % va)

    def read(self, va, size):
        start = self.offset(va)
        return self.data[start:start + size]

    def u32(self, va):
        return struct.unpack("<I", self.read(va, 4))[0]

    def rel_target(self, va):
        return (va + 4 + struct.unpack("<i", self.read(va, 4))[0]) & 0xFFFFFFFF

    def find_unique(self, signature, label):
        text = next(s for s in self.sections if s[0] == ".text")
        _, start, _, roff, rsize = text
        hits = [m.start() for m in signature_regex(signature).finditer(self.data, roff, roff + rsize)]
        if len(hits) != 1:
            raise ValueError("%s signature matched %d times (exactly one required)" % (label, len(hits)))
        return start + hits[0] - roff


def expect(image, va, hex_bytes, label):
    wanted = bytes(int(token, 16) for token in hex_bytes.split())
    found = image.read(va, len(wanted))
    if found != wanted:
        raise ValueError("%s: expected %s at %08X, found %s" % (label, hex_bytes, va, found.hex(" ")))


def audit(path):
    image = Image(path)
    if image.stamp not in BUILDS:
        raise ValueError("unknown executable (TimeDateStamp %08X)" % image.stamp)
    if image.base != 0x400000:
        raise ValueError("unexpected image base %08X" % image.base)
    build, label = BUILDS[image.stamp]
    va = {}
    va["list_objects"] = image.find_unique(LIST_OBJECTS_SIGNATURE, "$ListObjects")
    va["filter"] = image.find_unique(FILTER_SIGNATURE, "$ListObjects filter")

    push = va["list_objects"] + PUSH_SITE
    expect(image, push - 4, "6A 00 6A 00 68", "push site")
    if image.u32(push + 1) != va["filter"]:
        raise ValueError("the push site does not hand over the stock filter")
    expect(image, push + 5, "FF D0", "push site call")
    if image.data.count(struct.pack("<I", va["filter"])) != 1:
        raise ValueError("the filter address appears more than once in the file")

    decoded = {}
    for name, operand, kind, opcode in FILTER_OPERANDS:
        at = va["filter"] + operand
        expect(image, at - len(opcode.split()), opcode, "filter operand %s" % name)
        value = image.rel_target(at) if kind == "rel" else image.u32(at)
        wanted = ".text" if kind == "rel" else (".rdata" if name == "stricmp_import" else ".data")
        if image.section_of(value) != wanted:
            raise ValueError("filter operand %s = %08X is not in %s" % (name, value, wanted))
        decoded[name] = value
    if decoded["attribute_values"] != decoded["attribute_count"]:
        raise ValueError("attribute value table no longer starts at the count")
    va["get_property"] = decoded["get_property"]
    va["push_back"] = decoded["push_back"]
    for name, operand, opcode in GET_PROPERTY_OPERANDS:
        at = va["get_property"] + operand
        expect(image, at - 1, opcode, "property lookup operand %s" % name)
        target = image.rel_target(at)
        if name == "gpl_manager":
            if target != decoded["gpl_manager"]:
                raise ValueError("property lookup uses a different GPL manager getter")
        else:
            va[name] = target
            decoded[name] = target
    for function, offset, hex_bytes, meaning in INVARIANTS:
        expect(image, va[function] + offset, hex_bytes, meaning)
    for function in ("filter", "list_objects", "get_property", "push_back"):
        tail = image.read(va[function] + SIZES[function] - 1, 1)
        if function == "filter" and tail != b"\xC3":
            raise ValueError("filter no longer ends at the guarded RET")

    hashes = {name: fnv1a(image.read(va[name], size)) for name, size in SIZES.items()}
    return build, label, image.stamp, va, decoded, hashes


def main(argv):
    paths = argv[1:]
    if not paths:
        paths = [os.environ[name] for name in ("MAJESTY_PUBLIC_EXE", "MAJESTY_BETA2_EXE", "MAJESTY_GOG_EXE")
                 if os.environ.get(name)]
    if not paths:
        print(__doc__)
        return 2
    failed = 0
    for path in paths:
        try:
            build, label, stamp, va, decoded, hashes = audit(path)
        except (OSError, ValueError, StopIteration) as error:
            print("FAILED %s: %s" % (path, error))
            failed += 1
            continue
        print("== %s (%s, TimeDateStamp %08X)" % (label, os.path.basename(path), stamp))
        for name in ("list_objects", "filter", "get_property", "push_back", "resolve_agent", "attribute_lookup"):
            print("  %-17s %08X  size %3X  fnv1a %08X" % (name, va[name], SIZES[name], hashes[name]))
        print("  push site         %08X" % (va["list_objects"] + PUSH_SITE))
        for name, _, _, _ in FILTER_OPERANDS:
            print("    %-17s %08X" % (name, decoded[name]))
        print("  C++: {MajestyBuildId::%s, 0x%05X, 0x%05X, 0x%08X, 0x%08X, 0x%08X, 0x%08X, 0x%08X, 0x%08X},"
              % (build, va["list_objects"] - 0x400000, va["filter"] - 0x400000,
                 hashes["list_objects"], hashes["filter"], hashes["get_property"],
                 hashes["push_back"], hashes["resolve_agent"], hashes["attribute_lookup"]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
