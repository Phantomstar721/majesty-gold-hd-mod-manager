"""Strict manager-to-runtime capability manifest.

The launcher receives only the path to this generated file.  The file itself
is deliberately small, deterministic, and package-identity agnostic so the
runtime can enable only the features proven necessary by the current merge.
"""

from __future__ import annotations

import re
from pathlib import Path
import struct
import tempfile
from typing import Sequence


RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH = (
    "DataMX/majesty_mod_manager_capabilities.bin"
)
RUNTIME_CAPABILITY_MANIFEST_ENV_VAR = "MAJESTY_MOD_MANAGER_CAPABILITIES"
PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY = (
    "private-activity-text-registry.v1"
)

_MAGIC = b"MMCP"
_VERSION = 1
_HEADER = struct.Struct("<4sII")
_U32 = struct.Struct("<I")
_MAX_RECORDS = 64
_MAX_NAME_BYTES = 128
_MAX_MANIFEST_BYTES = 64 * 1024
_CAPABILITY_NAME = re.compile(
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+"
)


def is_runtime_capability_name(value: object) -> bool:
    """Return whether ``value`` is one canonical portable capability name."""

    return isinstance(value, str) and _CAPABILITY_NAME.fullmatch(value) is not None


def encode_runtime_capability_manifest(capabilities: Sequence[str]) -> bytes:
    """Encode a canonical MMCP v1 manifest.

    Input order is intentionally irrelevant. Duplicate declarations are
    rejected because they indicate an invalid capability aggregation boundary.
    """

    values = tuple(capabilities)
    if len(values) > _MAX_RECORDS:
        raise ValueError(
            f"runtime capability manifest has {len(values)} records; "
            f"maximum is {_MAX_RECORDS}"
        )
    if any(not is_runtime_capability_name(value) for value in values):
        raise ValueError(
            "runtime capability names must be canonical lowercase dotted names"
        )
    if len(set(values)) != len(values):
        raise ValueError("runtime capability manifest contains duplicate names")

    ordered = tuple(sorted(values))
    chunks = [_HEADER.pack(_MAGIC, _VERSION, len(ordered))]
    for value in ordered:
        encoded = value.encode("ascii")
        if not encoded or len(encoded) > _MAX_NAME_BYTES:
            raise ValueError(
                f"runtime capability name must contain 1..{_MAX_NAME_BYTES} bytes"
            )
        chunks.extend((_U32.pack(len(encoded)), encoded))
    payload = b"".join(chunks)
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ValueError(
            f"runtime capability manifest exceeds {_MAX_MANIFEST_BYTES} bytes"
        )
    return payload


def decode_runtime_capability_manifest(payload: bytes) -> tuple[str, ...]:
    """Decode MMCP v1, rejecting ambiguity, truncation, and noncanonical data."""

    if not isinstance(payload, bytes):
        raise ValueError("runtime capability manifest must be bytes")
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise ValueError(
            f"runtime capability manifest exceeds {_MAX_MANIFEST_BYTES} bytes"
        )
    if len(payload) < _HEADER.size:
        raise ValueError("runtime capability manifest header is truncated")
    magic, version, count = _HEADER.unpack_from(payload)
    if magic != _MAGIC:
        raise ValueError("runtime capability manifest magic is invalid")
    if version != _VERSION:
        raise ValueError(
            f"unsupported runtime capability manifest version: {version}"
        )
    if count > _MAX_RECORDS:
        raise ValueError(
            f"runtime capability manifest has {count} records; "
            f"maximum is {_MAX_RECORDS}"
        )

    offset = _HEADER.size
    records: list[str] = []
    previous: bytes | None = None
    for _index in range(count):
        if offset + _U32.size > len(payload):
            raise ValueError("runtime capability record length is truncated")
        (size,) = _U32.unpack_from(payload, offset)
        offset += _U32.size
        if size == 0 or size > _MAX_NAME_BYTES:
            raise ValueError(
                f"runtime capability name must contain 1..{_MAX_NAME_BYTES} bytes"
            )
        end = offset + size
        if end > len(payload):
            raise ValueError("runtime capability record is truncated")
        encoded = payload[offset:end]
        offset = end
        if previous is not None and encoded <= previous:
            raise ValueError(
                "runtime capability names must be strictly bytewise sorted and unique"
            )
        try:
            value = encoded.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("runtime capability name is not ASCII") from exc
        if not is_runtime_capability_name(value):
            raise ValueError(
                "runtime capability name is not canonical"
            )
        records.append(value)
        previous = encoded
    if offset != len(payload):
        raise ValueError("runtime capability manifest has trailing bytes")
    return tuple(records)


def write_runtime_capability_manifest(
    path: Path, capabilities: Sequence[str]
) -> tuple[str, ...]:
    """Atomically write and return the canonical capability sequence."""

    payload = encode_runtime_capability_manifest(capabilities)
    canonical = decode_runtime_capability_manifest(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", dir=path.parent, delete=False
        ) as stream:
            stream.write(payload)
            stream.flush()
            temporary = Path(stream.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return canonical


__all__ = [
    "PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY",
    "RUNTIME_CAPABILITY_MANIFEST_ENV_VAR",
    "RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH",
    "decode_runtime_capability_manifest",
    "encode_runtime_capability_manifest",
    "is_runtime_capability_name",
    "write_runtime_capability_manifest",
]
