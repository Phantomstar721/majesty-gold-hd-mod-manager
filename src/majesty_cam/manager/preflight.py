from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ..cam import read_cam
from ..compose import (
    ComposeError,
    SelectedMod,
    discover_selected_private_activity_texts,
    inventory_package,
)
from ..package import ModPackage, PackageFormatError, load_package
from .capabilities import (
    DERIVED_RUNTIME_CAPABILITIES,
    GENERIC_RUNTIME_CAPABILITIES,
    SUPPORTED_RUNTIME_CAPABILITIES,
)
from .catalog import CatalogIssue, IssueSeverity
from .compatibility import CompatibilityRegistry, CompatibilitySpec
from .profile import normalize_guid


_CG_DIALOG = re.compile(r"^CG[A-Z0-9]{2}$")


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    message: str
    path: Path | None = None


@dataclass(frozen=True)
class PreparedMergeMod:
    content_id: str
    display_name: str
    source_root: Path
    effective_root: Path
    alias: str
    package: ModPackage | None
    priority: int
    runtime_capabilities: tuple[str, ...]
    badge: str | None
    substituted: bool
    compatibility: CompatibilitySpec | None
    issues: tuple[ReadinessIssue, ...]

    @property
    def ready(self) -> bool:
        return self.package is not None and not self.issues

    @property
    def selected_mod(self) -> SelectedMod:
        if not self.ready or self.package is None:
            raise ComposeError(f"{self.display_name} did not pass merge preflight")
        return SelectedMod(self.alias, self.package)


def prepare_merge_package(
    *,
    content_id: str,
    display_name: str,
    source_root: Path,
    registry: CompatibilityRegistry,
) -> PreparedMergeMod:
    """Resolve adapters/substitutions and collect intrinsic merge failures."""

    normalized_id = normalize_guid(content_id)
    source_root = source_root.resolve(strict=False)
    spec = registry.get(normalized_id)
    replacement = spec.available_replacement() if spec is not None else None
    effective_root = replacement or source_root
    substituted = replacement is not None and replacement != source_root
    definition = None if substituted else (spec.definition_path if spec else None)
    alias = spec.alias if spec else _slug(display_name, normalized_id)
    priority = spec.merge_priority if spec else 1000
    adapter_capabilities = spec.runtime_capabilities if spec else ()
    capabilities = tuple(
        dict.fromkeys(
            (
                *GENERIC_RUNTIME_CAPABILITIES,
                *(
                    capability
                    for capability in adapter_capabilities
                    if capability not in DERIVED_RUNTIME_CAPABILITIES
                ),
            )
        )
    )
    badge = spec.badge if spec else None

    issues: list[ReadinessIssue] = []
    for capability in adapter_capabilities:
        if capability in DERIVED_RUNTIME_CAPABILITIES:
            issues.append(
                ReadinessIssue(
                    "reserved_runtime_capability",
                    (
                        f"{capability} is manager-derived and cannot be declared "
                        "by a package or compatibility adapter."
                    ),
                    spec.definition_path if spec is not None else source_root,
                )
            )

    package: ModPackage | None = None
    try:
        package = load_package(effective_root, definition=definition)
        effective_mod_id = normalize_guid(package.mod_id)
        if not substituted and effective_mod_id != normalized_id:
            issues.append(
                ReadinessIssue(
                    "stale_catalog_identity",
                    (
                        "The selected catalog identity no longer matches the "
                        f"package manifest ({normalized_id} != {effective_mod_id})."
                    ),
                    package.manifest_path,
                )
            )
        if package.definition is not None:
            for capability in package.definition.runtime_capabilities:
                if capability in DERIVED_RUNTIME_CAPABILITIES:
                    issues.append(
                        ReadinessIssue(
                            "reserved_runtime_capability",
                            (
                                f"{capability} is manager-derived and cannot be "
                                "declared by a package or compatibility adapter."
                            ),
                            effective_root / "mod-definition.json",
                        )
                    )
            capabilities = tuple(
                dict.fromkeys(
                    (
                        *capabilities,
                        *(
                            capability
                            for capability in package.definition.runtime_capabilities
                            if capability not in DERIVED_RUNTIME_CAPABILITIES
                        ),
                    )
                )
            )
            if package.definition.schema_version == 1 and spec is None:
                issues.append(
                    ReadinessIssue(
                        "legacy_merge_definition_requires_adapter",
                        (
                            "schema-version 1 mod-definition.json cannot own its "
                            "runtime-capability requirements; use schema version 2 "
                            "or a trusted manager compatibility adapter"
                        ),
                        effective_root / "mod-definition.json",
                    )
                )
        _validate_package(package, alias=alias, issues=issues)
    except (OSError, PackageFormatError, ComposeError, ValueError) as exc:
        issues.append(
            ReadinessIssue(
                "package_preflight_failed",
                str(exc),
                effective_root,
            )
        )
        package = None

    unknown_caps = sorted(set(capabilities) - SUPPORTED_RUNTIME_CAPABILITIES)
    if unknown_caps:
        issues.append(
            ReadinessIssue(
                "unsupported_runtime_capability",
                "Unsupported runtime capabilities: " + ", ".join(unknown_caps),
                effective_root / "mod-definition.json",
            )
        )

    return PreparedMergeMod(
        content_id=normalized_id,
        display_name=display_name,
        source_root=source_root,
        effective_root=effective_root,
        alias=alias,
        package=package,
        priority=priority,
        runtime_capabilities=tuple(capabilities),
        badge=badge,
        substituted=substituted,
        compatibility=spec,
        issues=tuple(issues),
    )


def catalog_merge_preflight(
    content_id: str,
    display_name: str,
    source_root: Path,
    *,
    registry: CompatibilityRegistry,
    game_path: Path,
) -> tuple[CatalogIssue, ...]:
    """Run package-independent deep checks for one discovered Merge row."""

    prepared = prepare_merge_package(
        content_id=content_id,
        display_name=display_name,
        source_root=source_root,
        registry=registry,
    )
    issues = [
        CatalogIssue(
            code=issue.code,
            message=issue.message,
            severity=IssueSeverity.ERROR,
            path=issue.path or prepared.effective_root,
            content_id=prepared.content_id,
        )
        for issue in prepared.issues
    ]
    if not prepared.ready:
        return tuple(issues)

    try:
        discover_selected_private_activity_texts(
            game_path,
            (prepared.selected_mod,),
        )
    except (ComposeError, OSError, ValueError) as exc:
        issues.append(
            CatalogIssue(
                code="unsafe_custom_text_binding",
                message=str(exc),
                severity=IssueSeverity.ERROR,
                path=prepared.effective_root,
                content_id=prepared.content_id,
            )
        )
    return tuple(issues)


def _validate_package(
    package: ModPackage,
    *,
    alias: str,
    issues: list[ReadinessIssue],
) -> None:
    if package.definition is None:
        issues.append(
            ReadinessIssue(
                "missing_merge_definition",
                "A versioned mod-definition.json (or trusted manager adapter) is required.",
                package.root,
            )
        )
        return

    selected = SelectedMod(alias, package)
    inventory = inventory_package(selected)

    art_domains = {"main": 0, "interface": 0}
    has_bdep = False
    for cam_path in inventory.cams:
        archive = read_cam(cam_path)
        extensions = {section.extension for section in archive.sections}
        if b"DATA" in extensions:
            for section in archive.sections:
                if section.extension == b"DATA" and any(
                    entry.name[:4] == b"BDEP" for entry in section.entries
                ):
                    has_bdep = True
        if b"TILE" in extensions:
            if b"IMAG" not in extensions:
                issues.append(
                    ReadinessIssue(
                        "untyped_art",
                        "A TILE archive has no IMAG reference table and cannot be relocated safely.",
                        cam_path,
                    )
                )
            domain = "main" if b"SPLT" in extensions else "interface"
            art_domains[domain] += 1

    if not has_bdep:
        issues.append(
            ReadinessIssue(
                "missing_bdep",
                "Merge replacement packages must provide their complete effective BDEP table.",
                package.root,
            )
        )
    for domain, count in art_domains.items():
        if count != 1:
            issues.append(
                ReadinessIssue(
                    f"invalid_{domain}_art_provider_count",
                    f"Expected exactly one {domain} TILE/IMAG provider; found {count}.",
                    package.root,
                )
            )

    for load in inventory.gpl_loads:
        try:
            size = load.target.absolute_path.stat().st_size
        except OSError:
            size = 0
        if size <= 0:
            issues.append(
                ReadinessIssue(
                    "empty_compiled_gpl",
                    "The manifest GPL Target must be present and non-empty.",
                    load.target.absolute_path,
                )
            )
        if not load.sources:
            issues.append(
                ReadinessIssue(
                    "missing_gpl_sources",
                    "Complete GPL/DAT sources are required for semantic merging.",
                    package.root,
                )
            )

    if not package.definition.custom_buildings:
        issues.append(
            ReadinessIssue(
                "missing_custom_buildings",
                "The current replacement composer requires at least one declared custom building.",
                package.root,
            )
        )
    for building in package.definition.custom_buildings:
        if not _CG_DIALOG.fullmatch(building.dialog_id):
            issues.append(
                ReadinessIssue(
                    "unsafe_dialog_id",
                    f"{building.local_name} DialogID must be a private CGxx ID; got {building.dialog_id!r}.",
                    package.root,
                )
            )


def _slug(display_name: str, content_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", display_name.casefold()).strip("-")
    if not value:
        value = "mod"
    uuid_suffix = content_id.replace("-", "").casefold()
    return f"{value}-{uuid_suffix}"


__all__ = [
    "GENERIC_RUNTIME_CAPABILITIES",
    "catalog_merge_preflight",
    "PreparedMergeMod",
    "ReadinessIssue",
    "SUPPORTED_RUNTIME_CAPABILITIES",
    "prepare_merge_package",
]
