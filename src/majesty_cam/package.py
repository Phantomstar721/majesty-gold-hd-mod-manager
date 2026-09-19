from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Mapping, Optional, Sequence, Tuple, Union
import xml.etree.ElementTree as ET

from .runtime_capabilities import is_runtime_capability_name
from .equipment import StockEquipment, EQUIPMENT_FEATURE_TYPE, parse_equipment, equipment_mapping
from .hero_info import HeroInfoRow, HERO_INFO_TYPE, parse_hero_info, hero_info_mapping
from .kingdom_research import (KingdomResearch, KINGDOM_RESEARCH_TYPE,
                               parse_kingdom_research, kingdom_research_mapping)
from .shared_features import (
    SHARED_FEATURE_TYPES, SharedFeature, StockGameplayEventObserver,
    StockActivityDuration, parse_shared_feature, shared_feature_mapping,
)
from .gpl_features import (
    GplFeature,
    GplFeatureError,
    StockControlledFollowerSpeedSync,
    StockHeroQuestLifecycle,
    StockHeroQuestParticipant,
    StockSpellEvaluationEquivalent,
    StockGplmxPurchaseEquipmentTail,
    StockGplmxPurchaseBazaarTail,
    gpl_feature_mapping,
    normalize_gpl_features,
    parse_gpl_feature,
)
from .runtime_features import (
    EnchantmentRowFeature,
    NameGeneratorFeature,
    MapFogQueryFeature,
    MovementQueryFeature,
    NativeTimingFeature,
    RuntimeFeature,
    normalize_runtime_features,
)
from .stock_building_controllers import is_stock_building_controller_pair
from .stock_controller_features import (
    ControllerFeature,
    ControllerFeatureError,
    StockAp41Fl00HostileMonsterFlag,
    controller_feature_mapping,
    normalize_controller_features,
    parse_controller_feature,
)


DEFINITION_FILE_NAME = "mod-definition.json"
# Versions 1 and 2 remain readable indefinitely for existing packages and
# trusted compatibility adapters. Version 3 is the author-facing declarative
# contract. Keep the supported set explicit so unknown future schemas fail
# closed instead of being partially interpreted as the newest known shape.
DEFINITION_SCHEMA_VERSION = 3
SUPPORTED_DEFINITION_SCHEMA_VERSIONS = frozenset((1, 2, 3))


class PackageFormatError(ValueError):
    """Raised when a Majesty mod package is incomplete, ambiguous, or unsafe."""


@dataclass(frozen=True)
class PackagePath:
    """A manifest path after validation against its package root."""

    declared_path: str
    relative_path: str
    absolute_path: Path


@dataclass(frozen=True)
class LocalizedText:
    language: Optional[str]
    text: str


@dataclass(frozen=True)
class GplPath:
    """One ordered GPL child, whose role is ``target`` or ``source``."""

    role: str
    file: PackagePath


@dataclass(frozen=True)
class GplLoad:
    files: Tuple[GplPath, ...]
    recovered_project: Optional[PackagePath] = None

    @property
    def target(self) -> PackagePath:
        for item in self.files:
            if item.role == "target":
                return item.file
        raise PackageFormatError("GPL load has no Target")

    @property
    def sources(self) -> Tuple[PackagePath, ...]:
        return tuple(item.file for item in self.files if item.role == "source")


@dataclass(frozen=True)
class CamLoad:
    file: PackagePath


@dataclass(frozen=True)
class DescriptionsLoad:
    file: PackagePath


@dataclass(frozen=True)
class StringsLoad:
    file: PackagePath


@dataclass(frozen=True)
class OpaqueLoad:
    """One native Standard-Mod directive the generated profile never emits.

    ``known_native_only`` is true only for stock Majesty directive families
    whose runtime namespace is distinct from CAM, Description, GPL, and
    Strings. Other directives remain visible to reconciliation but fail closed
    because their load-last interaction cannot be proved.
    """

    tag: str
    file: Optional[PackagePath]
    known_native_only: bool = False


LoadDirective = Union[CamLoad, DescriptionsLoad, StringsLoad, GplLoad, OpaqueLoad]


@dataclass(frozen=True)
class LoadBlock:
    """Recognized load directives in their original XML order."""

    directives: Tuple[LoadDirective, ...]

    @property
    def cams(self) -> Tuple[PackagePath, ...]:
        return tuple(item.file for item in self.directives if isinstance(item, CamLoad))

    @property
    def descriptions(self) -> Tuple[PackagePath, ...]:
        return tuple(
            item.file for item in self.directives if isinstance(item, DescriptionsLoad)
        )

    @property
    def strings(self) -> Tuple[PackagePath, ...]:
        return tuple(
            item.file for item in self.directives if isinstance(item, StringsLoad)
        )

    @property
    def gpl(self) -> Tuple[GplLoad, ...]:
        return tuple(item for item in self.directives if isinstance(item, GplLoad))


@dataclass(frozen=True)
class DatasetLoad:
    base: str
    loads: Tuple[LoadBlock, ...]


@dataclass(frozen=True)
class ModMetadata:
    mod_id: str
    display_names: Tuple[LocalizedText, ...]
    short_descriptions: Tuple[LocalizedText, ...]
    long_descriptions: Tuple[LocalizedText, ...]
    datasets: Tuple[DatasetLoad, ...]

    @property
    def display_name(self) -> str:
        for value in self.display_names:
            if value.language and value.language.replace("-", "_").casefold() == "en_us":
                return value.text
        return self.display_names[0].text


@dataclass(frozen=True)
class CustomBuildingDefinition:
    local_name: str
    # Schema v1/v2 packages own an explicit private FourCC. Schema v3 packages
    # deliberately omit it; composition derives their authored source DialogID
    # from XML and allocates a collision-free internal ID.
    dialog_id: Optional[str]
    controller_base: str
    panel_resource_template: str


# Backward-compatible descriptive alias for the schema's AP78-specific record
# name; the runtime module intentionally uses the reusable shorter class name.
Ap78EnchantmentRowFeature = EnchantmentRowFeature
PackageRuntimeFeature = Union[RuntimeFeature, ControllerFeature, GplFeature, SharedFeature, StockEquipment, KingdomResearch]


@dataclass(frozen=True)
class ModDefinition:
    schema_version: int
    mod_id: str
    internal_name: str
    display_name: str
    custom_buildings: Tuple[CustomBuildingDefinition, ...]
    runtime_capabilities: Tuple[str, ...] = ()
    runtime_features: Tuple[PackageRuntimeFeature, ...] = ()


@dataclass(frozen=True)
class ModPackage:
    root: Path
    manifest_path: Path
    metadata: ModMetadata
    definition: Optional[ModDefinition]

    @property
    def mod_id(self) -> str:
        return self.metadata.mod_id

    @property
    def display_name(self) -> str:
        return self.metadata.display_name

    @property
    def datasets(self) -> Tuple[DatasetLoad, ...]:
        return self.metadata.datasets


DefinitionInput = Union[ModDefinition, Mapping[str, object], str, Path]


def load_package(
    package_root: Union[str, Path],
    *,
    manifest_path: Optional[Union[str, Path]] = None,
    definition: Optional[DefinitionInput] = None,
) -> ModPackage:
    """Load and validate one Majesty ``.mmxml`` mod package.

    Manifest resource paths are always package-root relative. An explicit
    definition path may be absolute (for a caller-owned compatibility
    definition) or package-root relative. When ``definition`` is omitted,
    ``mod-definition.json`` is loaded if present.
    """

    root = _resolve_package_root(package_root)
    manifest = _select_manifest(root, manifest_path)
    metadata = _parse_manifest(root, manifest)
    parsed_definition = _select_definition(root, definition)

    if parsed_definition is not None and not _same_mod_id(
        metadata.mod_id, parsed_definition.mod_id
    ):
        raise PackageFormatError(
            "mod-definition.json mod_id does not match the .mmxml Mod id: "
            f"{parsed_definition.mod_id!r} != {metadata.mod_id!r}"
        )

    return ModPackage(
        root=root,
        manifest_path=manifest,
        metadata=metadata,
        definition=parsed_definition,
    )


def load_standard_component(
    package_root: Union[str, Path],
    *,
    manifest_path: Union[str, Path],
    mod_id: str,
) -> ModPackage:
    """Load one exact ordinary Mod component for semantic reconciliation.

    Historical Workshop manifests commonly contain several mutually-exclusive
    ``Mod`` elements and sometimes omit their source list even though a matching
    ``.gplproj`` is shipped.  This path selects only the requested UUID, accepts
    Strings resources, and recovers sources solely from the project whose stem
    exactly matches the declared BCD target. A historical sole-project fallback
    is allowed only when the manifest itself contains one Mod component, so a
    project can never be borrowed from a sibling variant.

    The returned schema-v3 definition is deliberately empty: Standard Mods do
    not gain manager runtime features merely by participating in text merging.
    """

    root = _resolve_package_root(package_root)
    manifest = _select_manifest(root, manifest_path)
    metadata = _parse_manifest(
        root,
        manifest,
        selected_mod_id=mod_id,
        allow_strings=True,
        allow_direct_gpl_target=True,
        recover_project_sources=True,
        allow_opaque_native_loads=True,
    )
    definition = ModDefinition(
        schema_version=3,
        mod_id=metadata.mod_id,
        internal_name="StandardMergeComponent",
        display_name=metadata.display_name,
        custom_buildings=(),
        runtime_features=(),
    )
    return ModPackage(
        root=root,
        manifest_path=manifest,
        metadata=ModMetadata(
            mod_id=metadata.mod_id,
            display_names=metadata.display_names,
            short_descriptions=metadata.short_descriptions,
            long_descriptions=metadata.long_descriptions,
            datasets=metadata.datasets,
        ),
        definition=definition,
    )


def load_mod_definition(path: Union[str, Path]) -> ModDefinition:
    """Load a versioned mod definition, rejecting duplicate JSON keys."""

    definition_path = Path(path)
    try:
        definition_path = definition_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PackageFormatError(f"mod definition does not exist: {path}") from exc
    if not definition_path.is_file():
        raise PackageFormatError(f"mod definition is not a file: {definition_path}")

    try:
        text = definition_path.read_text(encoding="utf-8")
        value = json.loads(text, object_pairs_hook=_json_object_without_duplicates)
    except UnicodeError as exc:
        raise PackageFormatError(
            f"mod definition is not valid UTF-8: {definition_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PackageFormatError(
            f"invalid JSON in mod definition {definition_path}: {exc.msg}"
        ) from exc
    except _DuplicateJsonKey as exc:
        raise PackageFormatError(
            f"duplicate JSON key in mod definition {definition_path}: {exc.key!r}"
        ) from exc

    if not isinstance(value, Mapping):
        raise PackageFormatError("mod definition root must be a JSON object")
    return parse_mod_definition(value)


def parse_mod_definition(value: Mapping[str, object]) -> ModDefinition:
    """Parse one supported, exact ``mod-definition.json`` object shape.

    Version 1 is the original building-only contract. Version 2 adds only
    package-owned runtime capability declarations. Version 3 replaces opaque
    capability strings with exact, typed feature records and manager-owned
    custom-building dialog allocation. Private positional text is handled
    separately: the manager discovers and proves those bindings from the
    package's stock-relative AITX and GPL data.
    """

    common_fields = {
        "schema_version",
        "mod_id",
        "internal_name",
        "display_name",
        "custom_buildings",
    }

    schema_version = value.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version not in SUPPORTED_DEFINITION_SCHEMA_VERSIONS
    ):
        raise PackageFormatError(
            "unsupported mod definition schema_version: " f"{schema_version!r}"
        )
    if schema_version == 1:
        expected = common_fields
    elif schema_version == 2:
        expected = common_fields | {"runtime_capabilities"}
    else:
        expected = common_fields | {"runtime_features"}
    _require_exact_fields(value, expected, "mod definition")

    mod_id = _required_string(value["mod_id"], "mod definition mod_id")
    internal_name = _required_string(
        value["internal_name"], "mod definition internal_name"
    )
    display_name = _required_string(
        value["display_name"], "mod definition display_name"
    )

    raw_buildings = value["custom_buildings"]
    if not isinstance(raw_buildings, (list, tuple)):
        raise PackageFormatError("mod definition custom_buildings must be an array")

    buildings = []
    seen_local_names = set()
    seen_dialog_ids = set()
    building_fields = {"local_name", "controller_base", "panel_resource_template"}
    if schema_version < 3:
        building_fields.add("dialog_id")
    for index, raw_building in enumerate(raw_buildings):
        context = f"custom_buildings[{index}]"
        if not isinstance(raw_building, Mapping):
            raise PackageFormatError(f"{context} must be an object")
        _require_exact_fields(raw_building, building_fields, context)
        building = CustomBuildingDefinition(
            local_name=_required_string(raw_building["local_name"], f"{context}.local_name"),
            dialog_id=(
                _required_string(raw_building["dialog_id"], f"{context}.dialog_id")
                if schema_version < 3
                else None
            ),
            controller_base=_required_string(
                raw_building["controller_base"], f"{context}.controller_base"
            ),
            panel_resource_template=_required_string(
                raw_building["panel_resource_template"],
                f"{context}.panel_resource_template",
            ),
        )

        local_key = building.local_name.casefold()
        if local_key in seen_local_names:
            raise PackageFormatError(
                f"duplicate custom building local_name: {building.local_name!r}"
            )
        seen_local_names.add(local_key)

        if schema_version == 3:
            _required_fourcc(building.controller_base, f"{context}.controller_base")
            _required_fourcc(
                building.panel_resource_template,
                f"{context}.panel_resource_template",
            )
            if not is_stock_building_controller_pair(
                building.controller_base,
                building.panel_resource_template,
            ):
                raise PackageFormatError(
                    f"{context} requests an unsupported stock controller/panel "
                    "combination; use a cataloged stock primary-building "
                    "controller with its matching stock panel template"
                )
        else:
            assert building.dialog_id is not None
            dialog_key = building.dialog_id.casefold()
            if dialog_key in seen_dialog_ids:
                raise PackageFormatError(
                    f"duplicate custom building dialog_id: {building.dialog_id!r}"
                )
            seen_dialog_ids.add(dialog_key)
        buildings.append(building)

    raw_capabilities = value.get("runtime_capabilities", ())
    if not isinstance(raw_capabilities, (list, tuple)):
        raise PackageFormatError(
            "mod definition runtime_capabilities must be an array"
        )
    capabilities = []
    seen_capabilities = set()
    for index, raw_capability in enumerate(raw_capabilities):
        context = f"runtime_capabilities[{index}]"
        capability = _required_string(raw_capability, context)
        if not is_runtime_capability_name(capability):
            raise PackageFormatError(
                f"{context} must be a lowercase dotted capability name"
            )
        if capability in seen_capabilities:
            raise PackageFormatError(
                f"duplicate runtime capability: {capability!r}"
            )
        seen_capabilities.add(capability)
        capabilities.append(capability)

    raw_features = value.get("runtime_features", ())
    if not isinstance(raw_features, (list, tuple)):
        raise PackageFormatError("mod definition runtime_features must be an array")
    features: list[PackageRuntimeFeature] = []
    controller_features: list[ControllerFeature] = []
    gpl_features: list[GplFeature] = []
    seen_feature_keys: set[tuple[str, ...]] = set()
    for index, raw_feature in enumerate(raw_features):
        context = f"runtime_features[{index}]"
        if not isinstance(raw_feature, Mapping):
            raise PackageFormatError(f"{context} must be an object")
        feature_type = _required_string(raw_feature.get("type"), f"{context}.type")
        if feature_type == "stock.name-generator.v1":
            _require_exact_fields(
                raw_feature, {"type", "generator_id", "name_tables"}, context
            )
            generator_id = _required_fourcc(
                raw_feature["generator_id"], f"{context}.generator_id"
            )
            raw_tables = raw_feature["name_tables"]
            if not isinstance(raw_tables, (list, tuple)) or len(raw_tables) != 4:
                raise PackageFormatError(
                    f"{context}.name_tables must contain exactly four FourCCs"
                )
            tables = tuple(
                _required_fourcc(table, f"{context}.name_tables[{table_index}]")
                for table_index, table in enumerate(raw_tables)
            )
            feature: RuntimeFeature = NameGeneratorFeature(
                generator_id=generator_id,
                name_part_ids=(tables[0], tables[1], tables[2], tables[3]),
            )
            feature_key = (feature_type, generator_id.casefold())
        elif feature_type == "stock.map-fog-query.v1":
            _require_exact_fields(raw_feature, {"type"}, context)
            feature = MapFogQueryFeature()
            feature_key = (feature_type, "shared")
        elif feature_type == "stock.movement-query.v1":
            _require_exact_fields(raw_feature, {"type"}, context)
            feature = MovementQueryFeature()
            feature_key = (feature_type, "shared")
        elif feature_type == "stock.native-timing.v1":
            _require_exact_fields(raw_feature, {"type", "spell_ids", "effector_ids"}, context)
            families = []
            for field in ("spell_ids", "effector_ids"):
                values = raw_feature[field]
                if not isinstance(values, (list, tuple)):
                    raise PackageFormatError(f"{context}.{field} must be an array")
                families.append(tuple(_required_fourcc(value, f"{context}.{field}")
                                      for value in values))
            feature = NativeTimingFeature(*families)
            feature_key = (feature_type, "shared")
        elif feature_type == "stock.ap78-enchantment-row.v1":
            _require_exact_fields(
                raw_feature, {"type", "overlay_id", "display_text"}, context
            )
            overlay_id = _required_fourcc(
                raw_feature["overlay_id"], f"{context}.overlay_id"
            )
            display_text = _required_string(
                raw_feature["display_text"], f"{context}.display_text"
            )
            feature = EnchantmentRowFeature(
                overlay_id=overlay_id,
                display_text=display_text,
            )
            feature_key = (feature_type, overlay_id.casefold())
        elif feature_type == HERO_INFO_TYPE:
            try:
                feature = parse_hero_info(raw_feature)
            except ValueError as exc:
                raise PackageFormatError(f"{context}: {exc}") from exc
            feature_key = (feature_type, feature.feature_key)
        elif feature_type == KINGDOM_RESEARCH_TYPE:
            try:
                feature = parse_kingdom_research(raw_feature)
            except ValueError as exc:
                raise PackageFormatError(f"{context}: {exc}") from exc
            feature_key = (feature_type, feature.feature_key)
        elif feature_type == EQUIPMENT_FEATURE_TYPE:
            try:
                feature = parse_equipment(raw_feature)
            except ValueError as exc:
                raise PackageFormatError(f"{context}: {exc}") from exc
            feature_key = (feature_type, feature.feature_key)
        elif feature_type in SHARED_FEATURE_TYPES:
            try:
                feature = parse_shared_feature(raw_feature)
            except ValueError as exc:
                raise PackageFormatError(f"{context} is invalid: {exc}") from exc
            feature_key = (feature_type, feature.feature_key.casefold())
        elif feature_type in {
            "stock.gplmx-purchase-equipment-tail.v1",
            "stock.gplmx-purchase-bazaar-tail.v1",
            "stock.controlled-follower-speed-sync.v1",
            "stock.hero-quest-lifecycle.v1",
            "stock.hero-quest-participant.v1",
            "stock.spell-evaluation-equivalent.v1",
        }:
            try:
                feature = parse_gpl_feature(raw_feature)
            except GplFeatureError as exc:
                raise PackageFormatError(f"{context} is invalid: {exc}") from exc
            gpl_features.append(feature)
            feature_key = (
                feature_type,
                (
                    feature.feature_key
                    if isinstance(feature, (StockControlledFollowerSpeedSync, StockHeroQuestLifecycle, StockHeroQuestParticipant, StockSpellEvaluationEquivalent))
                    else feature.callback_key
                ).casefold(),
            )
        else:
            try:
                controller = parse_controller_feature(raw_feature)
            except ControllerFeatureError as exc:
                if str(exc).startswith("unsupported controller feature type"):
                    raise PackageFormatError(
                        f"{context}.type is unsupported: {feature_type!r}"
                    ) from exc
                raise PackageFormatError(f"{context} is invalid: {exc}") from exc
            feature = controller
            controller_features.append(controller)
            mapping = controller_feature_mapping(controller)
            if feature_type == "stock.ap22-resource-meter.v1":
                local_identity = str(mapping["resource_key"])
            elif feature_type == "stock.ap99-research-row.v1":
                local_identity = str(mapping["recipe_key"])
            elif feature_type in {
                "stock.ap24-timed-rage-action.v1",
                "stock.ap24-rage-command-action.v1",
                "stock.ap69-sovereign-target-action.v1",
                "stock.ap41-fl00-hostile-monster-flag.v1",
            }:
                local_identity = str(mapping["action_key"])
            elif feature_type in {
                "stock.ap10-ap69-secondary-panel.v1",
                "stock.mx04-mx05-occupant-action-panel.v1",
                "stock.mx05-live-agent-list-panel.v1",
                "stock.mx05-data-record-list-panel.v1",
                "stock.mx09-ap41-reward-panel.v1",
                "stock.ap17-upgrade-research-gate.v1",
                "stock.ap52-private-recruitment.v1",
                "stock.ap52-recruitment-panel.v1",
            }:
                local_identity = str(mapping["parent_building"])
            elif feature_type == "stock.mx22-building-open-toggle.v1":
                feature_key = (
                    feature_type,
                    str(mapping["toggle_key"]).casefold(),
                    str(mapping["parent_building"]).casefold(),
                )
                local_identity = ""
            else:  # pragma: no cover - the typed parser owns this closed union
                local_identity = ""
            if feature_type != "stock.mx22-building-open-toggle.v1":
                feature_key = (
                    feature_type,
                    str(mapping["panel_key"]).casefold(),
                    local_identity.casefold(),
                )
        if feature_key in seen_feature_keys:
            raise PackageFormatError(
                f"duplicate runtime feature identity: {feature_key[1]!r}"
            )
        seen_feature_keys.add(feature_key)
        if isinstance(feature, (NameGeneratorFeature, EnchantmentRowFeature, MapFogQueryFeature, MovementQueryFeature, NativeTimingFeature, HeroInfoRow)):
            try:
                normalize_runtime_features((feature,))
            except ValueError as exc:
                raise PackageFormatError(f"{context} is invalid: {exc}") from exc
        features.append(feature)

    if controller_features:
        try:
            normalize_controller_features(controller_features)
        except ControllerFeatureError as exc:
            raise PackageFormatError(
                f"mod definition controller runtime_features are invalid: {exc}"
            ) from exc
    if gpl_features:
        try:
            normalize_gpl_features(gpl_features)
        except GplFeatureError as exc:
            raise PackageFormatError(
                f"mod definition GPL runtime_features are invalid: {exc}"
            ) from exc

    return ModDefinition(
        schema_version=schema_version,
        mod_id=mod_id,
        internal_name=internal_name,
        display_name=display_name,
        custom_buildings=tuple(buildings),
        runtime_capabilities=tuple(capabilities),
        runtime_features=tuple(features),
    )


def _resolve_package_root(package_root: Union[str, Path]) -> Path:
    try:
        root = Path(package_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PackageFormatError(f"package root does not exist: {package_root}") from exc
    if not root.is_dir():
        raise PackageFormatError(f"package root is not a directory: {root}")
    return root


def _select_manifest(
    root: Path, manifest_path: Optional[Union[str, Path]]
) -> Path:
    if manifest_path is None:
        manifests = []
        for path in root.iterdir():
            if not path.is_file() or path.suffix.casefold() != ".mmxml":
                continue
            resolved = path.resolve()
            _ensure_inside_root(root, resolved, "manifest")
            manifests.append(resolved)
        manifests.sort(key=lambda path: path.name.casefold())
        if not manifests:
            raise PackageFormatError(f"no top-level .mmxml manifest in package: {root}")
        if len(manifests) > 1:
            names = ", ".join(path.name for path in manifests)
            raise PackageFormatError(f"multiple top-level .mmxml manifests in package: {names}")
        return manifests[0]

    candidate = Path(manifest_path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PackageFormatError(f"manifest does not exist: {manifest_path}") from exc
        _ensure_inside_root(root, candidate, "manifest")
    else:
        candidate = _resolve_relative_file(root, str(manifest_path), "manifest").absolute_path
    if candidate.suffix.casefold() != ".mmxml":
        raise PackageFormatError(f"manifest must have a .mmxml extension: {candidate}")
    return candidate


def _parse_manifest(
    root: Path,
    manifest: Path,
    *,
    selected_mod_id: str | None = None,
    allow_strings: bool = True,
    allow_direct_gpl_target: bool = False,
    recover_project_sources: bool = False,
    allow_opaque_native_loads: bool = False,
) -> ModMetadata:
    try:
        xml_bytes = manifest.read_bytes()
    except OSError as exc:
        raise PackageFormatError(f"cannot read manifest: {manifest}") from exc
    upper = xml_bytes.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise PackageFormatError("manifest DTD/entity declarations are not allowed")
    try:
        xml_root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise PackageFormatError(f"invalid XML in manifest {manifest}: {exc}") from exc

    mod_nodes = [node for node in xml_root.iter() if _local_name(node.tag) == "Mod"]
    if selected_mod_id is None and len(mod_nodes) != 1:
        raise PackageFormatError(
            f"manifest must contain exactly one Mod element; found {len(mod_nodes)}"
        )
    if selected_mod_id is None:
        mod_node = mod_nodes[0]
    else:
        requested = _uuid_text(selected_mod_id)
        matches = [
            node
            for node in mod_nodes
            if _uuid_text(node.get("id", "")) == requested
        ]
        if len(matches) != 1:
            raise PackageFormatError(
                "manifest must contain exactly one requested Mod element "
                f"{selected_mod_id!r}; found {len(matches)}"
            )
        mod_node = matches[0]
    mod_id = _required_string(mod_node.get("id"), "manifest Mod id")

    display_names = _localized_children(mod_node, "DisplayName")
    if not display_names:
        raise PackageFormatError("manifest Mod must contain a non-empty DisplayName")

    short_descriptions = []
    long_descriptions = []
    for description in _direct_children(mod_node, "Description"):
        language = _clean_optional_string(description.get("lang"))
        for child in list(description):
            tag = _local_name(child.tag)
            text = _element_text(child)
            if not text:
                continue
            item = LocalizedText(
                language=_clean_optional_string(child.get("lang")) or language,
                text=text,
            )
            if tag == "Short":
                short_descriptions.append(item)
            elif tag == "Long":
                long_descriptions.append(item)

    registry = _PathRegistry(root)
    datasets = []
    dataset_nodes = [
        node for node in mod_node.iter() if _local_name(node.tag) == "Dataset"
    ]
    if not dataset_nodes:
        raise PackageFormatError("manifest Mod must contain at least one Dataset")

    for dataset_index, dataset_node in enumerate(dataset_nodes):
        base = _clean_optional_string(dataset_node.get("base")) or "Any"
        load_nodes = _direct_children(dataset_node, "Load")
        if not load_nodes:
            raise PackageFormatError(f"Dataset[{dataset_index}] has no Load element")
        loads = []
        for load_index, load_node in enumerate(load_nodes):
            directives = []
            for directive_index, child in enumerate(list(load_node)):
                tag = _local_name(child.tag)
                context = (
                    f"Dataset[{dataset_index}]/Load[{load_index}]/"
                    f"{tag}[{directive_index}]"
                )
                if tag == "CAM":
                    directives.append(
                        CamLoad(registry.add(_element_text(child), context))
                    )
                elif tag == "Descriptions":
                    directives.append(
                        DescriptionsLoad(registry.add(_element_text(child), context))
                    )
                elif tag == "GPL":
                    directives.append(
                        _parse_gpl_load(
                            child,
                            registry,
                            context,
                            allow_direct_target=allow_direct_gpl_target,
                            recover_project_sources=recover_project_sources,
                            allow_sole_project_fallback=len(mod_nodes) == 1,
                        )
                    )
                elif tag == "Strings" and allow_strings:
                    directives.append(
                        StringsLoad(registry.add(_element_text(child), context))
                    )
                elif allow_opaque_native_loads:
                    raw_path = _element_text(child)
                    known_native_only = tag in {"Constants", "Template"} and not list(
                        child
                    )
                    opaque_path = None
                    if raw_path:
                        try:
                            opaque_path = registry.add(raw_path, context)
                        except PackageFormatError:
                            if known_native_only:
                                raise
                            # Unknown directives are retained for a precise
                            # reconciliation error. Their grammar may not be a
                            # package-relative file path, so do not reinterpret
                            # arbitrary content as one.
                    directives.append(
                        OpaqueLoad(
                            tag=tag,
                            file=opaque_path,
                            known_native_only=known_native_only,
                        )
                    )
                else:
                    raise PackageFormatError(
                        f"{context} is an unsupported manifest Load directive"
                    )
            loads.append(LoadBlock(directives=tuple(directives)))
        datasets.append(DatasetLoad(base=base, loads=tuple(loads)))

    return ModMetadata(
        mod_id=mod_id,
        display_names=display_names,
        short_descriptions=tuple(short_descriptions),
        long_descriptions=tuple(long_descriptions),
        datasets=tuple(datasets),
    )


def _parse_gpl_load(
    gpl_node: ET.Element,
    registry: "_PathRegistry",
    context: str,
    *,
    allow_direct_target: bool = False,
    recover_project_sources: bool = False,
    allow_sole_project_fallback: bool = False,
) -> GplLoad:
    files = []
    recovered_project = None
    target_count = 0
    children = list(gpl_node)
    if not children and allow_direct_target:
        target = registry.add(_element_text(gpl_node), context)
        files.append(GplPath(role="target", file=target))
        target_count = 1
    for index, child in enumerate(children):
        tag = _local_name(child.tag)
        if tag not in {"Target", "Source"}:
            raise PackageFormatError(
                f"{context}/{tag}[{index}] is an unsupported GPL directive"
            )
        role = tag.casefold()
        if role == "target":
            target_count += 1
        file = registry.add(_element_text(child), f"{context}/{tag}[{index}]")
        files.append(GplPath(role=role, file=file))
    if target_count != 1:
        raise PackageFormatError(
            f"{context} must contain exactly one Target; found {target_count}"
        )
    if recover_project_sources and not any(item.role == "source" for item in files):
        target = next(item.file for item in files if item.role == "target")
        recovered_project, recovered_sources = _recover_exact_project_sources(
            registry.root,
            target,
            context,
            allow_sole_project_fallback=allow_sole_project_fallback,
        )
        files.extend(recovered_sources)
    return GplLoad(files=tuple(files), recovered_project=recovered_project)


_GPL_PROJECT_ROW = re.compile(
    r'^\s*(source|data)\s*=\s*"([^"]+)"\s*$', re.IGNORECASE
)


def _recover_exact_project_sources(
    root: Path,
    target: PackagePath,
    context: str,
    *,
    allow_sole_project_fallback: bool,
) -> tuple[Optional[PackagePath], list[GplPath]]:
    target_stem = target.absolute_path.stem.casefold()
    candidates = tuple(
        path
        for path in root.rglob("*.gplproj")
        if path.is_file() and not path.is_symlink() and path.stem.casefold() == target_stem
    )
    if not candidates and allow_sole_project_fallback:
        all_projects = tuple(
            path
            for path in root.rglob("*.gplproj")
            if path.is_file() and not path.is_symlink()
        )
        # A handful of early Workshop packages called their sole project
        # ``path.gplproj`` while naming the emitted target ``bytecode.bcd``.
        # One project is still unambiguous; multiple non-matching projects are not.
        candidates = all_projects if len(all_projects) == 1 else ()
    if not candidates:
        return None, []
    if len(candidates) != 1:
        raise PackageFormatError(
            f"{context} has multiple matching source projects for {target.relative_path!r}"
        )
    project = candidates[0].resolve(strict=True)
    _ensure_inside_root(root, project, context)
    project_package_path = PackagePath(
        declared_path=project.name,
        relative_path=project.relative_to(root).as_posix(),
        absolute_path=project,
    )
    try:
        project_text = project.read_text(encoding="cp1252")
    except (OSError, UnicodeError) as exc:
        raise PackageFormatError(f"cannot read GPL project: {project}") from exc
    result: list[GplPath] = []
    for line_number, line in enumerate(project_text.splitlines(), 1):
        match = _GPL_PROJECT_ROW.fullmatch(line)
        if match is None:
            if line.strip():
                raise PackageFormatError(
                    f"{project}:{line_number}: unsupported GPL project row"
                )
            continue
        candidate = (project.parent / Path(match.group(2).replace("\\", "/"))).resolve(
            strict=True
        )
        _ensure_inside_root(root, candidate, context)
        if not candidate.is_file() or candidate.suffix.casefold() not in {".gpl", ".dat"}:
            raise PackageFormatError(
                f"{project}:{line_number}: source is not a GPL/DAT file"
            )
        result.append(
            GplPath(
                role="source",
                file=PackagePath(
                    declared_path=match.group(2),
                    relative_path=candidate.relative_to(root).as_posix(),
                    absolute_path=candidate,
                ),
            )
        )
    return project_package_path, result


def _uuid_text(value: str) -> str:
    import uuid

    try:
        return str(uuid.UUID(value.strip().strip("{}"))).casefold()
    except (AttributeError, ValueError) as exc:
        raise PackageFormatError(f"invalid manifest Mod id: {value!r}") from exc


class _PathRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._seen = {}

    def add(self, declared_path: str, context: str) -> PackagePath:
        package_path = _resolve_relative_file(self.root, declared_path, context)
        key = str(package_path.absolute_path).casefold()
        previous = self._seen.get(key)
        if previous is not None:
            raise PackageFormatError(
                f"duplicate package path {package_path.relative_path!r}: "
                f"{previous} and {context}"
            )
        self._seen[key] = context
        return package_path


def _resolve_relative_file(root: Path, declared_path: str, context: str) -> PackagePath:
    declared = _required_string(declared_path, f"{context} path")
    if "\x00" in declared:
        raise PackageFormatError(f"{context} path contains a null byte")

    windows_path = PureWindowsPath(declared)
    normalized = declared.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    if windows_path.is_absolute() or windows_path.drive or windows_path.root:
        raise PackageFormatError(f"{context} path must be package-relative: {declared!r}")
    if posix_path.is_absolute():
        raise PackageFormatError(f"{context} path must be package-relative: {declared!r}")

    try:
        candidate = root.joinpath(*posix_path.parts).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PackageFormatError(f"{context} path does not exist: {declared!r}") from exc
    _ensure_inside_root(root, candidate, context)
    if not candidate.is_file():
        raise PackageFormatError(f"{context} path is not a file: {declared!r}")

    relative = candidate.relative_to(root).as_posix()
    return PackagePath(
        declared_path=declared,
        relative_path=relative,
        absolute_path=candidate,
    )


def _ensure_inside_root(root: Path, candidate: Path, context: str) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PackageFormatError(
            f"{context} path escapes package root: {candidate}"
        ) from exc


def _select_definition(
    root: Path, definition: Optional[DefinitionInput]
) -> Optional[ModDefinition]:
    if definition is None:
        default_path = root / DEFINITION_FILE_NAME
        if not default_path.exists():
            return None
        safe_default = _resolve_relative_file(
            root, DEFINITION_FILE_NAME, "default mod definition"
        )
        return load_mod_definition(safe_default.absolute_path)
    if isinstance(definition, ModDefinition):
        return _validate_definition_object(definition)
    if isinstance(definition, Mapping):
        return parse_mod_definition(definition)

    definition_path = Path(definition)
    if not definition_path.is_absolute():
        definition_path = _resolve_relative_file(
            root, str(definition_path), "mod definition override"
        ).absolute_path
    return load_mod_definition(definition_path)


def _validate_definition_object(definition: ModDefinition) -> ModDefinition:
    return parse_mod_definition(mod_definition_mapping(definition))


def mod_definition_mapping(definition: ModDefinition) -> dict:
    """Canonical package-definition data shared by validation and fingerprints.

    Keep every supported feature's mapping in this one serialization path;
    consumers must not maintain a separate feature-type whitelist.
    """

    value = {
        "schema_version": definition.schema_version,
        "mod_id": definition.mod_id,
        "internal_name": definition.internal_name,
        "display_name": definition.display_name,
        "custom_buildings": [
            dict(
                {
                "local_name": building.local_name,
                "controller_base": building.controller_base,
                "panel_resource_template": building.panel_resource_template,
                },
                **(
                    {"dialog_id": building.dialog_id}
                    if definition.schema_version < 3
                    else {}
                ),
            )
            for building in definition.custom_buildings
        ],
    }
    if definition.schema_version == 2:
        value["runtime_capabilities"] = list(definition.runtime_capabilities)
    elif definition.schema_version == 3:
        value["runtime_features"] = [
            _runtime_feature_mapping(feature)
            for feature in definition.runtime_features
        ]
    return value


def _runtime_feature_mapping(feature: PackageRuntimeFeature) -> dict:
    if isinstance(feature, HeroInfoRow):
        return hero_info_mapping(feature)
    if isinstance(feature, KingdomResearch):
        return kingdom_research_mapping(feature)
    if isinstance(feature, StockEquipment):
        return equipment_mapping(feature)
    if isinstance(feature, MapFogQueryFeature):
        return {"type": "stock.map-fog-query.v1"}
    if isinstance(feature, MovementQueryFeature):
        return {"type": "stock.movement-query.v1"}
    if isinstance(feature, NativeTimingFeature):
        return {"type": "stock.native-timing.v1", "spell_ids": list(feature.spell_ids),
                "effector_ids": list(feature.effector_ids)}
    if isinstance(feature, NameGeneratorFeature):
        return {
            "type": "stock.name-generator.v1",
            "generator_id": feature.generator_id,
            "name_tables": list(feature.name_part_ids),
        }
    if isinstance(feature, EnchantmentRowFeature):
        return {
            "type": "stock.ap78-enchantment-row.v1",
            "overlay_id": feature.overlay_id,
            "display_text": feature.display_text,
        }
    if isinstance(feature, (StockGameplayEventObserver, StockActivityDuration)):
        return shared_feature_mapping(feature)
    if isinstance(
        feature,
        (
            StockGplmxPurchaseEquipmentTail,
            StockGplmxPurchaseBazaarTail,
            StockControlledFollowerSpeedSync,
            StockHeroQuestLifecycle,
            StockHeroQuestParticipant,
            StockSpellEvaluationEquivalent,
        ),
    ):
        return gpl_feature_mapping(feature)
    try:
        return controller_feature_mapping(feature)
    except ControllerFeatureError as exc:
        raise PackageFormatError(
            "mod definition runtime_features contains an unsupported object"
        ) from exc


def _localized_children(parent: ET.Element, name: str) -> Tuple[LocalizedText, ...]:
    values = []
    for child in _direct_children(parent, name):
        text = _element_text(child)
        if text:
            values.append(
                LocalizedText(
                    language=_clean_optional_string(child.get("lang")),
                    text=text,
                )
            )
    return tuple(values)


def _direct_children(parent: ET.Element, name: str) -> Tuple[ET.Element, ...]:
    return tuple(child for child in list(parent) if _local_name(child.tag) == name)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _clean_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackageFormatError(f"{context} must be a non-empty string")
    return value.strip()


def _required_fourcc(value: object, context: str) -> str:
    fourcc = _required_string(value, context)
    try:
        encoded = fourcc.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PackageFormatError(f"{context} must be an ASCII FourCC") from exc
    if len(encoded) != 4 or any(byte < 0x21 or byte > 0x7E for byte in encoded):
        raise PackageFormatError(
            f"{context} must be exactly four printable ASCII characters"
        )
    return fourcc


def _require_exact_fields(
    value: Mapping[str, object], expected: set, context: str
) -> None:
    if any(not isinstance(key, str) for key in value.keys()):
        raise PackageFormatError(f"{context} field names must be strings")
    actual = set(value.keys())
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise PackageFormatError(f"{context} fields are invalid: {'; '.join(details)}")


def _same_mod_id(left: str, right: str) -> bool:
    def normalize(value: str) -> str:
        return value.strip().strip("{}").casefold()

    return normalize(left) == normalize(right)


class _DuplicateJsonKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _json_object_without_duplicates(pairs: Sequence[Tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


__all__ = [
    "Ap78EnchantmentRowFeature",
    "CamLoad",
    "CustomBuildingDefinition",
    "DatasetLoad",
    "DEFINITION_FILE_NAME",
    "DEFINITION_SCHEMA_VERSION",
    "SUPPORTED_DEFINITION_SCHEMA_VERSIONS",
    "DescriptionsLoad",
    "GplLoad",
    "GplPath",
    "LoadBlock",
    "LocalizedText",
    "ModDefinition",
    "ModMetadata",
    "ModPackage",
    "NameGeneratorFeature",
    "OpaqueLoad",
    "PackageFormatError",
    "PackageRuntimeFeature",
    "PackagePath",
    "RuntimeFeature",
    "StockGplmxPurchaseEquipmentTail",
    "StockGplmxPurchaseBazaarTail",
    "StockControlledFollowerSpeedSync",
    "StringsLoad",
    "load_mod_definition",
    "load_package",
    "load_standard_component",
    "mod_definition_mapping",
    "parse_mod_definition",
]
