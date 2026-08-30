"""Versioned startup cache for unchanged manager inputs.

The cache stores only derived discovery results.  Source packages, Majesty's
executable, QOL scripts, and the manager compatibility payload remain the
authorities.  Cheap metadata signatures invalidate cached work before it is
reused; build and launch keep their existing content-hash revalidation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Iterable

from ..package import CamLoad, DescriptionsLoad, GplLoad, load_package
from .catalog import CatalogIssue, IssueSeverity
from .compatibility import CompatibilityRegistry
from .qol_service import (
    QolCatalogSnapshot,
    QolService,
    QolUtilityState,
    QolUtilityStatus,
    SUPPORTED_BRANCHES,
    resolve_qol_patch,
)


STARTUP_CACHE_SCHEMA_VERSION = 1
STARTUP_CACHE_FILENAME = "startup-cache.json"
_STOCK_PREFLIGHT_INPUTS = (
    Path("DataMX/mx_gpltext.cam"),
    Path("SDK/OriginalQuests/GPLMx/mx_defines.gpl"),
)


@dataclass
class StartupCache:
    path: Path
    preflight: dict[str, dict[str, object]]
    qol: dict[str, object] | None

    @classmethod
    def load(cls, path: Path) -> "StartupCache":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        if not isinstance(value, dict) or value.get("schema_version") != STARTUP_CACHE_SCHEMA_VERSION:
            value = {}
        preflight = value.get("merge_preflight", {})
        if not isinstance(preflight, dict):
            preflight = {}
        qol = value.get("qol")
        if not isinstance(qol, dict):
            qol = None
        return cls(path=path, preflight=dict(preflight), qol=qol)

    def get_preflight(
        self, content_id: str, signature: str
    ) -> tuple[CatalogIssue, ...] | None:
        raw = self.preflight.get(content_id)
        if not isinstance(raw, dict) or raw.get("signature") != signature:
            return None
        rows = raw.get("issues")
        if not isinstance(rows, list):
            return None
        issues: list[CatalogIssue] = []
        try:
            for row in rows:
                if not isinstance(row, dict):
                    return None
                raw_path = row.get("path")
                if raw_path is not None and not isinstance(raw_path, str):
                    return None
                issues.append(
                    CatalogIssue(
                        code=_required_string(row.get("code")),
                        message=_required_string(row.get("message")),
                        severity=IssueSeverity(_required_string(row.get("severity"))),
                        path=Path(raw_path) if raw_path else None,
                        content_id=(
                            _required_string(row.get("content_id"))
                            if row.get("content_id") is not None
                            else None
                        ),
                    )
                )
        except (TypeError, ValueError):
            return None
        return tuple(issues)

    def set_preflight(
        self,
        content_id: str,
        signature: str,
        issues: Iterable[CatalogIssue],
    ) -> None:
        self.preflight[content_id] = {
            "signature": signature,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity.value,
                    "path": str(issue.path) if issue.path is not None else None,
                    "content_id": issue.content_id,
                }
                for issue in issues
            ],
        }

    def retain_preflight(self, content_ids: Iterable[str]) -> None:
        keep = set(content_ids)
        self.preflight = {
            key: value for key, value in self.preflight.items() if key in keep
        }

    def get_qol(
        self, signature: str, service: QolService
    ) -> QolCatalogSnapshot | None:
        raw = self.qol
        if not isinstance(raw, dict) or raw.get("signature") != signature:
            return None
        branch_key = raw.get("branch")
        if branch_key is not None and not isinstance(branch_key, str):
            return None
        branch = next(
            (item for item in SUPPORTED_BRANCHES if item.key == branch_key), None
        )
        if branch_key is not None and branch is None:
            return None
        rows = raw.get("utilities")
        if not isinstance(rows, list):
            return None
        by_key = {
            row.get("key"): row
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("key"), str)
        }
        if set(by_key) != {spec.key for spec in service.specs}:
            return None
        utilities: list[QolUtilityStatus] = []
        try:
            for spec in service.specs:
                row = by_key[spec.key]
                installed = row.get("installed")
                if installed is not None and type(installed) is not bool:
                    return None
                supported = row.get("supported")
                applicable = row.get("applicable")
                if type(supported) is not bool or type(applicable) is not bool:
                    return None
                utilities.append(
                    QolUtilityStatus(
                        patch=resolve_qol_patch(service.repo_root, spec),
                        state=QolUtilityState(_required_string(row.get("state"))),
                        supported=supported,
                        applicable=applicable,
                        installed=installed,
                        detail=_required_string(row.get("detail"), allow_empty=True),
                    )
                )
        except (KeyError, TypeError, ValueError):
            return None
        return QolCatalogSnapshot(
            game_executable=service.game_executable,
            branch=branch,
            utilities=tuple(utilities),
        )

    def set_qol(self, signature: str, snapshot: QolCatalogSnapshot) -> None:
        self.qol = {
            "signature": signature,
            "branch": snapshot.branch.key if snapshot.branch is not None else None,
            "utilities": [
                {
                    "key": status.key,
                    "state": status.state.value,
                    "supported": status.supported,
                    "applicable": status.applicable,
                    "installed": status.installed,
                    "detail": status.detail,
                }
                for status in snapshot.utilities
            ],
        }

    def save(self) -> None:
        payload = {
            "schema_version": STARTUP_CACHE_SCHEMA_VERSION,
            "merge_preflight": self.preflight,
            "qol": self.qol,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(
                self.path,
                (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        except OSError:
            # A cache failure must never prevent a real scan or launch.
            return


def merge_preflight_signature(
    *,
    content_id: str,
    display_name: str,
    source_root: Path,
    registry: CompatibilityRegistry,
    game_path: Path,
) -> str:
    paths: list[Path] = list(_manager_cache_identity_paths())
    spec = registry.get(content_id)
    effective_root = source_root
    definition: Path | None = None
    if spec is not None:
        replacement = spec.available_replacement()
        if replacement is not None:
            effective_root = replacement
        else:
            definition = spec.definition_path
        paths.append(spec.definition_path)
        paths.extend(spec.replacement_roots)
    paths.extend(_shallow_package_paths(source_root))
    paths.extend(_package_input_paths(effective_root, definition=definition))
    paths.extend(item.source_path for item in registry.combination_resolutions)
    paths.extend(game_path / relative for relative in _STOCK_PREFLIGHT_INPUTS)
    return metadata_signature(
        paths,
        context=("merge-preflight-v1", content_id, display_name),
    )


def qol_input_signature(service: QolService) -> str:
    paths: list[Path] = [
        *_manager_cache_identity_paths(),
        service.game_executable,
        service.prefs_path,
    ]
    for spec in service.specs:
        patch = resolve_qol_patch(service.repo_root, spec)
        for path in (
            patch.install_script,
            patch.remove_script,
            patch.license_path,
        ):
            if path is not None:
                paths.append(path)
    return metadata_signature(
        paths,
        context=("qol-inspection-v1", *(spec.key for spec in service.specs)),
    )


def metadata_signature(
    paths: Iterable[Path],
    *,
    context: Iterable[str] = (),
    recursive_directories: bool = False,
) -> str:
    """Hash stable file identities without reading large package payloads."""

    digest = hashlib.sha256()
    for value in context:
        _feed(digest, "context", value)
    unique = {
        str(Path(path).resolve(strict=False)).casefold(): Path(path).resolve(strict=False)
        for path in paths
    }
    for key, path in sorted(unique.items()):
        _feed(digest, "root", key)
        _snapshot_path(digest, path, recursive=recursive_directories)
    return digest.hexdigest()


def _snapshot_path(
    digest: "hashlib._Hash", path: Path, *, recursive: bool
) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        _feed(digest, "missing", type(exc).__name__)
        return
    if _is_reparse_or_symlink(info):
        try:
            target = os.readlink(path)
        except OSError:
            target = "<unreadable>"
        _feed(digest, "link", target, *_stat_identity(info))
        return
    if stat.S_ISREG(info.st_mode):
        _feed(digest, "file", path.name.casefold(), *_stat_identity(info))
        return
    if not stat.S_ISDIR(info.st_mode):
        _feed(digest, "other", path.name.casefold(), *_stat_identity(info))
        return

    if not recursive:
        _feed(digest, "dir", path.name.casefold(), *_stat_identity(info))
        return

    root = path
    pending = [root]
    visited_directories: set[tuple[int, int]] = set()
    while pending:
        directory = pending.pop()
        try:
            relative_dir = directory.relative_to(root).as_posix().casefold()
            directory_info = directory.lstat()
            identity = (
                getattr(directory_info, "st_dev", 0),
                getattr(directory_info, "st_ino", 0),
            )
            if identity in visited_directories:
                _feed(digest, "directory-cycle", relative_dir, *identity)
                continue
            visited_directories.add(identity)
            _feed(digest, "dir", relative_dir, *_stat_identity(directory_info))
            children = sorted(
                directory.iterdir(), key=lambda item: item.name.casefold(), reverse=True
            )
        except OSError as exc:
            _feed(digest, "unreadable", str(directory).casefold(), type(exc).__name__)
            continue
        for child in children:
            relative = child.relative_to(root).as_posix().casefold()
            try:
                child_info = child.lstat()
            except OSError as exc:
                _feed(digest, "missing-child", relative, type(exc).__name__)
                continue
            if _is_reparse_or_symlink(child_info):
                try:
                    target = os.readlink(child)
                except OSError:
                    target = "<unreadable>"
                _feed(digest, "link", relative, target, *_stat_identity(child_info))
            elif stat.S_ISDIR(child_info.st_mode):
                pending.append(child)
            elif stat.S_ISREG(child_info.st_mode):
                _feed(digest, "file", relative, *_stat_identity(child_info))
            else:
                _feed(digest, "other", relative, *_stat_identity(child_info))


def _package_input_paths(
    root: Path, *, definition: Path | None
) -> tuple[Path, ...]:
    """Return only files that a valid package declares as merge inputs."""

    paths: list[Path] = list(_shallow_package_paths(root))
    try:
        package = load_package(root, definition=definition)
    except (OSError, ValueError):
        return tuple(paths)
    paths.append(package.manifest_path)
    packaged_definition = root / "mod-definition.json"
    if packaged_definition.exists():
        paths.append(packaged_definition)
    if definition is not None:
        paths.append(definition)
    for dataset in package.datasets:
        for load in dataset.loads:
            for directive in load.directives:
                if isinstance(directive, (CamLoad, DescriptionsLoad)):
                    paths.append(directive.file.absolute_path)
                elif isinstance(directive, GplLoad):
                    paths.extend(item.file.absolute_path for item in directive.files)
    return tuple(paths)


def _shallow_package_paths(root: Path) -> tuple[Path, ...]:
    """Cover manifest discovery and missing-file repairs without a tree walk."""

    paths = [root]
    try:
        paths.extend(root.iterdir())
    except OSError:
        pass
    return tuple(paths)


def _manager_cache_identity_paths() -> tuple[Path, ...]:
    """Invalidate prior checks when the installed manager itself changes."""

    if getattr(sys, "frozen", False):
        return (Path(sys.executable),)
    module_root = Path(__file__).resolve().parent
    return tuple(
        module_root / name
        for name in (
            "startup_cache.py",
            "catalog.py",
            "preflight.py",
            "qol_service.py",
            "controller.py",
        )
    )


def _stat_identity(info: os.stat_result) -> tuple[object, ...]:
    return (
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        getattr(info, "st_ino", 0),
    )


def _is_reparse_or_symlink(info: os.stat_result) -> bool:
    file_attributes = getattr(info, "st_file_attributes", 0)
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return stat.S_ISLNK(info.st_mode) or bool(file_attributes & reparse_point)


def _feed(digest: "hashlib._Hash", *values: object) -> None:
    for value in values:
        encoded = str(value).encode("utf-8", errors="surrogatepass")
        digest.update(len(encoded).to_bytes(4, "little"))
        digest.update(encoded)


def _required_string(value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError("cache field must be a string")
    return value


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
    "STARTUP_CACHE_FILENAME",
    "STARTUP_CACHE_SCHEMA_VERSION",
    "StartupCache",
    "merge_preflight_signature",
    "metadata_signature",
    "qol_input_signature",
]
