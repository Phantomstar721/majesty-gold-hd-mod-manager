"""Verify the fixed GOG audit without launching or modifying an executable."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


ROOT = Path(__file__).resolve().parents[1]


def verify_native_guards(data: bytes, audit: dict) -> None:
    """Check the actual production fingerprints against their audited bodies."""
    source = "\n".join((ROOT / name).read_text() for name in (
        "runtime/GogAuditedRanges.h", "runtime/GogControllerAudit.h", "runtime/GogRecipeAudit.h"))
    known = {(int(item["gog_rva"], 16), item["size"]) for item in audit["ranges"]}
    rows = re.findall(
        r"\{(0x[0-9A-F]+), (\d+), (0x[0-9A-F]+)u, (\d+), (\d+)\}", source
    )
    if not rows:
        raise ValueError("No production GOG body guards found")
    for rva, size, expected, skip_offset, skip_size in rows:
        rva, size = int(rva, 16), int(size)
        skip_offset, skip_size = int(skip_offset), int(skip_size)
        if (rva, size) not in known:
            raise ValueError(f"Native guard has no matching audit body: {rva:#x}")
        if skip_size and (rva != 0x10D060 or skip_offset != 0x143F or skip_size != 18):
            raise ValueError("Only the separately guarded factory fallback may be normalized")
        body = bytearray(read_rva(data, rva, size))
        body[skip_offset:skip_offset + skip_size] = bytes(skip_size)
        fingerprint = 2166136261
        for value in body:
            fingerprint = ((fingerprint ^ value) * 16777619) & 0xFFFFFFFF
        if fingerprint != int(expected, 16):
            raise ValueError(f"Native body guard differs from GOG: {rva:#x}")


def read_rva(data: bytes, rva: int, size: int) -> bytes:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    for index in range(count):
        offset = pe + 24 + optional_size + 40 * index
        _, address, raw_size, raw_offset = struct.unpack_from("<4I", data, offset + 8)
        if address <= rva and rva + size <= address + raw_size:
            start = raw_offset + rva - address
            result = data[start:start + size]
            if len(result) == size:
                return result
    raise ValueError(f"Unmapped audit range {rva:#x}+{size:#x}")


def verify(executable: Path, *, beta2: bool = False) -> None:
    data = executable.read_bytes()
    audit = json.loads((ROOT / "docs/gog-runtime-audit.json").read_text())
    controllers = json.loads((ROOT / "docs/gog-controller-audit.json").read_text())
    audit["ranges"].extend(controllers["ranges"])
    audit["ranges"].extend(json.loads((ROOT / "docs/gog-recipe-audit.json").read_text())["ranges"])
    side = "steam" if beta2 else "gog"
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    expected_timestamp = 0x5A8A11D5 if beta2 else 0x5BBB8DB8
    if struct.unpack_from("<I", data, pe + 8)[0] != expected_timestamp:
        raise ValueError("Executable timestamp does not match the audit")
    if not beta2 and hashlib.sha256(data).hexdigest() != audit["gog_sha256"]:
        raise ValueError("This audit requires the pristine GOG executable")
    for record in audit["ranges"]:
        actual = read_rva(data, int(record[side + "_rva"], 16), record.get(side + "_size", record["size"]))
        if hashlib.sha256(actual).hexdigest() != record[side + "_sha256"]:
            raise ValueError(f"Audit bytes differ: {record['name']} ({side})")
    if not beta2:
        verify_native_guards(data, audit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gog", required=True, type=Path)
    parser.add_argument("--beta2", type=Path)
    arguments = parser.parse_args()
    verify(arguments.gog)
    if arguments.beta2:
        verify(arguments.beta2, beta2=True)
