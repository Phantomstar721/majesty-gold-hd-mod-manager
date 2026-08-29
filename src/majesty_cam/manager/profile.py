from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable, Mapping, Sequence
import uuid


PROFILE_SCHEMA_VERSION = 1
REMEMBERED_FILENAME = "MajestyModPersistence.txt"
PROFILE_FILENAME = "profile.json"


class ProfileFormatError(ValueError):
    """Raised when manager-owned selection state is malformed."""


def normalize_guid(value: str) -> str:
    """Return Majesty's canonical persistence spelling for one UUID."""

    try:
        parsed = uuid.UUID(value.strip().strip("{}"))
    except (AttributeError, ValueError) as exc:
        raise ProfileFormatError(f"invalid Majesty mod UUID: {value!r}") from exc
    return str(parsed).upper()


def default_local_appdata() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Local"


def canonical_remembered_path(local_appdata: Path | None = None) -> Path:
    root = local_appdata or default_local_appdata()
    return root / "MajestyHD" / REMEMBERED_FILENAME


def default_profile_path(local_appdata: Path | None = None) -> Path:
    root = local_appdata or default_local_appdata()
    return root / "MajestyModManager" / PROFILE_FILENAME


def read_remembered_mods(
    canonical_path: Path,
    *,
    legacy_path: Path | None = None,
) -> tuple[str, ...]:
    """Read the Remember Active Mods preset without weakening its format.

    The canonical LocalAppData path wins.  The game-directory legacy path is
    consulted only when the canonical file is absent, matching the QOL patch.
    Bad or duplicate rows are ignored so a stale hand-edited preset cannot
    prevent the manager from opening.
    """

    source = canonical_path
    if not source.is_file() and legacy_path is not None and legacy_path.is_file():
        source = legacy_path
    if not source.is_file():
        return ()

    try:
        text = source.read_text(encoding="ascii", errors="strict")
    except (OSError, UnicodeError):
        return ()

    result: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        try:
            mod_id = normalize_guid(raw_line)
        except ProfileFormatError:
            continue
        if mod_id in seen:
            continue
        seen.add(mod_id)
        result.append(mod_id)
    return tuple(result)


def write_remembered_mods(path: Path, mod_ids: Iterable[str]) -> tuple[str, ...]:
    """Atomically project a manager profile into the QOL interoperability file."""

    ordered: list[str] = []
    seen: set[str] = set()
    for value in mod_ids:
        mod_id = normalize_guid(value)
        if mod_id in seen:
            continue
        seen.add(mod_id)
        ordered.append(mod_id)

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{mod_id}\r\n" for mod_id in ordered).encode("ascii")
    _atomic_write(path, payload)
    return tuple(ordered)


@dataclass(frozen=True)
class ManagerProfile:
    """The manager's authoritative choices and last successful build."""

    selections: Mapping[str, bool] = field(default_factory=dict)
    order: tuple[str, ...] = ()
    last_build_fingerprint: str | None = None
    last_build_mod_id: str | None = None
    last_build_path: str | None = None

    def selected(self, mod_id: str, *, default: bool = True) -> bool:
        return bool(self.selections.get(normalize_guid(mod_id), default))

    def with_selections(
        self,
        selections: Mapping[str, bool],
        order: Sequence[str],
    ) -> "ManagerProfile":
        normalized = {normalize_guid(key): bool(value) for key, value in selections.items()}
        normalized_order = _unique_guids(order)
        return ManagerProfile(
            selections=normalized,
            order=normalized_order,
            last_build_fingerprint=self.last_build_fingerprint,
            last_build_mod_id=self.last_build_mod_id,
            last_build_path=self.last_build_path,
        )

    def with_successful_build(
        self,
        *,
        fingerprint: str,
        mod_id: str,
        path: Path,
    ) -> "ManagerProfile":
        return ManagerProfile(
            selections=dict(self.selections),
            order=self.order,
            last_build_fingerprint=fingerprint,
            last_build_mod_id=normalize_guid(mod_id),
            last_build_path=str(path.resolve(strict=False)),
        )


def load_profile(path: Path) -> ManagerProfile | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileFormatError(f"cannot read manager profile {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ProfileFormatError(f"unsupported manager profile: {path}")

    raw_selections = value.get("selections", {})
    raw_order = value.get("order", [])
    if not isinstance(raw_selections, dict) or not isinstance(raw_order, list):
        raise ProfileFormatError(f"invalid manager selections in {path}")
    selections: dict[str, bool] = {}
    for key, enabled in raw_selections.items():
        if not isinstance(key, str) or type(enabled) is not bool:
            raise ProfileFormatError(f"invalid manager selection row in {path}")
        selections[normalize_guid(key)] = enabled
    if any(not isinstance(item, str) for item in raw_order):
        raise ProfileFormatError(f"invalid manager order in {path}")

    build = value.get("last_build")
    if build is None:
        build = {}
    if not isinstance(build, dict):
        raise ProfileFormatError(f"invalid manager build state in {path}")
    fingerprint = _optional_string(build.get("fingerprint"))
    build_id = _optional_string(build.get("mod_id"))
    build_path = _optional_string(build.get("path"))
    return ManagerProfile(
        selections=selections,
        order=_unique_guids(raw_order),
        last_build_fingerprint=fingerprint,
        last_build_mod_id=normalize_guid(build_id) if build_id else None,
        last_build_path=build_path,
    )


def save_profile(path: Path, profile: ManagerProfile) -> None:
    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "selections": dict(sorted(profile.selections.items())),
        "order": list(profile.order),
        "last_build": {
            "fingerprint": profile.last_build_fingerprint,
            "mod_id": profile.last_build_mod_id,
            "path": profile.last_build_path,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def initial_selection(
    mod_ids: Iterable[str],
    *,
    saved_profile: ManagerProfile | None,
    remembered_ids: Sequence[str] = (),
) -> tuple[dict[str, bool], tuple[str, ...], str]:
    """Choose manager state precedence and default every new valid mod on.

    Manager-owned state is authoritative after the first run.  On first run an
    existing Remember Active Mods file is imported exactly.  Without either
    source, every detected mod starts enabled as requested.
    """

    detected = _unique_guids(mod_ids)
    if saved_profile is not None:
        selections = {
            mod_id: saved_profile.selections.get(mod_id, True) for mod_id in detected
        }
        ordered = _order_subset(detected, saved_profile.order)
        return selections, ordered, "manager"

    remembered = _unique_guids(remembered_ids)
    if remembered:
        remembered_set = set(remembered)
        selections = {mod_id: mod_id in remembered_set for mod_id in detected}
        ordered = _order_subset(detected, remembered)
        return selections, ordered, "remembered"

    return {mod_id: True for mod_id in detected}, detected, "defaults"


def _order_subset(detected: Sequence[str], preferred: Sequence[str]) -> tuple[str, ...]:
    available = set(detected)
    front = [item for item in preferred if item in available]
    seen = set(front)
    front.extend(item for item in detected if item not in seen)
    return tuple(front)


def _unique_guids(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        mod_id = normalize_guid(value)
        if mod_id in seen:
            continue
        seen.add(mod_id)
        result.append(mod_id)
    return tuple(result)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProfileFormatError("manager profile optional strings must be non-empty")
    return value.strip()


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}-", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


__all__ = [
    "ManagerProfile",
    "PROFILE_SCHEMA_VERSION",
    "ProfileFormatError",
    "canonical_remembered_path",
    "default_profile_path",
    "initial_selection",
    "load_profile",
    "normalize_guid",
    "read_remembered_mods",
    "save_profile",
    "write_remembered_mods",
]
