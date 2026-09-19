from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re

from ..cam import read_cam
from ..equipment import require_beta2
from ..gpl import find_foreach_return_violations
from ..compose import (
    ComposeError,
    PackageInventory,
    SelectedMod,
    discover_private_activity_texts,
    discover_selected_private_activity_texts,
    inventory_package,
    resolve_building_dialogs,
    resolve_controller_registry,
    resolve_runtime_feature_registry,
    validate_controller_stock_evidence,
    validate_gpl_feature_evidence,
)
from ..package import (
    DEFINITION_FILE_NAME,
    ModPackage,
    PackageFormatError,
    load_package,
)
from .capabilities import (
    DERIVED_RUNTIME_CAPABILITIES,
    GENERIC_RUNTIME_CAPABILITIES,
    SUPPORTED_RUNTIME_CAPABILITIES,
)
from .catalog import CatalogIssue, IssueSeverity
from .compatibility import CompatibilityRegistry, CompatibilitySpec
from .profile import normalize_guid
from .startup_cache import package_input_metadata_signature, package_input_paths


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
    inventory: PackageInventory | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    package_file_inputs: tuple[tuple[str, str], ...] | None = field(
        default=None,
        compare=False,
        repr=False,
    )
    source_metadata_signature: str = field(
        default="",
        compare=False,
        repr=False,
    )

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
    configured_spec = registry.get(normalized_id)
    replacement = (
        configured_spec.available_replacement()
        if configured_spec is not None
        else None
    )
    effective_root = replacement or source_root
    substituted = replacement is not None and replacement != source_root
    package_owns_definition = (
        effective_root / DEFINITION_FILE_NAME
    ).is_file()
    # A package-owned v2/v3 definition is the public contract and must win over
    # any legacy manager adapter left installed for older Workshop revisions.
    # A complete manager substitution remains adapter-owned by design.
    spec = (
        configured_spec
        if configured_spec is not None
        and (substituted or not package_owns_definition)
        else None
    )
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
    inventory: PackageInventory | None = None
    package_file_inputs: tuple[tuple[str, str], ...] | None = None
    source_metadata_signature = ""
    signature_spec = spec if spec is not None and not substituted else None
    source_metadata_signature_before = _source_metadata_signature(
        effective_root,
        spec=signature_spec,
    )
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
                            "runtime-feature requirements; use schema version 3 "
                            "or a trusted manager compatibility adapter"
                        ),
                        effective_root / "mod-definition.json",
                    )
                )
        if isinstance(package, ModPackage) and package.definition is not None:
            inventory = inventory_package(SelectedMod(alias, package))
        _validate_package(
            package,
            alias=alias,
            issues=issues,
            inventory=inventory,
        )
        if inventory is not None:
            resolve_runtime_feature_registry(
                (inventory,),
                capabilities,
            )
            building_dialogs = resolve_building_dialogs((inventory,))
            resolve_controller_registry(
                (inventory,),
                capabilities,
                building_dialogs=building_dialogs,
            )
        package_file_inputs = _package_file_inputs(
            effective_root, definition=definition
        )
        source_metadata_signature = _source_metadata_signature(
            effective_root,
            spec=signature_spec,
        )
        if source_metadata_signature != source_metadata_signature_before:
            issues.append(
                ReadinessIssue(
                    "package_changed_during_preflight",
                    "The package changed while it was being checked. Rescan it.",
                    effective_root,
                )
            )
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
        inventory=inventory,
        package_file_inputs=package_file_inputs,
        source_metadata_signature=source_metadata_signature,
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
    return prepared_catalog_merge_preflight(prepared, game_path=game_path)


def prepared_catalog_merge_preflight(
    prepared: PreparedMergeMod, *, game_path: Path
) -> tuple[CatalogIssue, ...]:
    """Run catalog checks while preserving an already prepared package."""

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
        if prepared.inventory is None:
            # Retain the public test/adapter seam for synthetic prepared rows.
            discover_selected_private_activity_texts(
                game_path,
                (prepared.selected_mod,),
            )
        else:
            discover_private_activity_texts(game_path, (prepared.inventory,))
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

    try:
        inventory = prepared.inventory or inventory_package(prepared.selected_mod)
        validate_gpl_feature_evidence((inventory,), game_path=game_path)
        runtime_features = resolve_runtime_feature_registry(
            (inventory,),
            prepared.runtime_capabilities,
        )
        if runtime_features.equipment or runtime_features.kingdom_research or runtime_features.hero_info_rows:
            require_beta2(game_path / "MajestyHD.exe")
        dialogs = resolve_building_dialogs((inventory,))
        controller = resolve_controller_registry(
            (inventory,),
            prepared.runtime_capabilities,
            building_dialogs=dialogs,
        )
        validate_controller_stock_evidence(
            game_path,
            (inventory,),
            controller.registry,
            controller_panels=controller.panels,
            controller_toggles=controller.toggles,
            runtime_feature_registry=runtime_features,
        )
    except (ComposeError, OSError, ValueError) as exc:
        issues.append(
            CatalogIssue(
                code="unsafe_runtime_features",
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
    inventory: PackageInventory | None = None,
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

    if inventory is None:
        inventory = inventory_package(SelectedMod(alias, package))

    art_domains = {"main": 0, "interface": 0}
    has_bdep = False
    for cam_path in inventory.cams:
        archive = read_cam(cam_path)
        extensions = {section.extension for section in archive.sections}
        if (b"IMAG" in extensions or b"SPLT" in extensions or b"PALT" in extensions) and b"TILE" not in extensions:
            issues.append(
                ReadinessIssue(
                    "untyped_art",
                    "An IMAG/palette archive has no TILE section and cannot be relocated safely.",
                    cam_path,
                )
            )
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
            if b"SPLT" in extensions and b"PALT" in extensions:
                issues.append(
                    ReadinessIssue(
                        "ambiguous_art_palette",
                        "An art archive cannot contain both SPLT and PALT sections.",
                        cam_path,
                    )
                )
            domain = "main" if b"SPLT" in extensions else "interface"
            art_domains[domain] += 1

    modern_definition = package.definition.schema_version >= 3
    if not has_bdep and not modern_definition:
        issues.append(
            ReadinessIssue(
                "missing_bdep",
                "Merge replacement packages must provide their complete effective BDEP table.",
                package.root,
            )
        )
    for domain, count in art_domains.items():
        invalid_count = count > 1 if modern_definition else count != 1
        if invalid_count:
            issues.append(
                ReadinessIssue(
                    f"invalid_{domain}_art_provider_count",
                    (
                        f"Expected at most one {domain} TILE/IMAG provider; found {count}."
                        if modern_definition
                        else f"Expected exactly one {domain} TILE/IMAG provider; found {count}."
                    ),
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
        for source in load.sources:
            path = source.absolute_path
            if path.suffix.casefold() != ".gpl":
                continue
            text = _read_gpl_source(path)
            for violation in find_foreach_return_violations(text, str(path)):
                issues.append(
                    ReadinessIssue(
                        "unsafe_gpl_foreach_return",
                        (
                            f"GPL return at line {violation.return_line} is inside "
                            f"a foreach loop begun at line {violation.foreach_line}. "
                            "Majesty beta2 can crash on this control-flow shape. "
                            "Mod author: accumulate or select the result during "
                            "foreach, then return it after the loop, following "
                            "stock control flow. The Mod Manager will not rewrite "
                            "author-owned GPL automatically."
                        ),
                        path,
                    )
                )

    if not package.definition.custom_buildings and not modern_definition:
        issues.append(
            ReadinessIssue(
                "missing_custom_buildings",
                "The current replacement composer requires at least one declared custom building.",
                package.root,
            )
        )
    for building in package.definition.custom_buildings:
        if modern_definition:
            continue
        if (
            building.dialog_id is None
            or not _CG_DIALOG.fullmatch(building.dialog_id)
        ):
            issues.append(
                ReadinessIssue(
                    "unsafe_dialog_id",
                    f"{building.local_name} DialogID must be a private CGxx ID; got {building.dialog_id!r}.",
                    package.root,
                )
            )
    if modern_definition and package.definition.custom_buildings:
        try:
            resolve_building_dialogs((inventory,))
        except (ComposeError, ValueError) as exc:
            issues.append(
                ReadinessIssue(
                    "invalid_building_dialog_binding",
                    str(exc),
                    package.root,
                )
            )


def _slug(display_name: str, content_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", display_name.casefold()).strip("-")
    if not value:
        value = "mod"
    uuid_suffix = content_id.replace("-", "").casefold()
    return f"{value}-{uuid_suffix}"


def _package_file_inputs(
    root: Path, *, definition: Path | None
) -> tuple[tuple[str, str], ...]:
    resolved_root = root.resolve(strict=False)
    files: list[tuple[str, str]] = []
    for path in package_input_paths(resolved_root, definition=definition):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(resolved_root).as_posix()
        except ValueError:
            # External compatibility definitions are fingerprinted separately
            # by the build plan and must not be mislabeled as package content.
            continue
        files.append((relative, _sha256_file(path)))
    return tuple(sorted(files, key=lambda item: item[0].casefold()))


def _source_metadata_signature(
    root: Path,
    *,
    spec: CompatibilitySpec | None,
) -> str:
    return package_input_metadata_signature(
        root,
        definition=spec.definition_path if spec is not None else None,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_gpl_source(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ComposeError(f"GPL source is not UTF-8 or Windows-1252: {path}")


__all__ = [
    "GENERIC_RUNTIME_CAPABILITIES",
    "catalog_merge_preflight",
    "prepared_catalog_merge_preflight",
    "PreparedMergeMod",
    "ReadinessIssue",
    "SUPPORTED_RUNTIME_CAPABILITIES",
    "prepare_merge_package",
]
