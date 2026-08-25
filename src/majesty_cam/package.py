from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping, Optional, Sequence, Tuple, Union
import xml.etree.ElementTree as ET


DEFINITION_FILE_NAME = "mod-definition.json"
DEFINITION_SCHEMA_VERSION = 1


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


LoadDirective = Union[CamLoad, DescriptionsLoad, GplLoad]


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
    dialog_id: str
    controller_base: str
    panel_resource_template: str


@dataclass(frozen=True)
class ModDefinition:
    schema_version: int
    mod_id: str
    internal_name: str
    display_name: str
    custom_buildings: Tuple[CustomBuildingDefinition, ...]


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
    """Parse the exact version-1 ``mod-definition.json`` object shape."""

    expected = {
        "schema_version",
        "mod_id",
        "internal_name",
        "display_name",
        "custom_buildings",
    }
    _require_exact_fields(value, expected, "mod definition")

    schema_version = value["schema_version"]
    if type(schema_version) is not int or schema_version != DEFINITION_SCHEMA_VERSION:
        raise PackageFormatError(
            "unsupported mod definition schema_version: " f"{schema_version!r}"
        )

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
    building_fields = {
        "local_name",
        "dialog_id",
        "controller_base",
        "panel_resource_template",
    }
    for index, raw_building in enumerate(raw_buildings):
        context = f"custom_buildings[{index}]"
        if not isinstance(raw_building, Mapping):
            raise PackageFormatError(f"{context} must be an object")
        _require_exact_fields(raw_building, building_fields, context)
        building = CustomBuildingDefinition(
            local_name=_required_string(raw_building["local_name"], f"{context}.local_name"),
            dialog_id=_required_string(raw_building["dialog_id"], f"{context}.dialog_id"),
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

        dialog_key = building.dialog_id.casefold()
        if dialog_key in seen_dialog_ids:
            raise PackageFormatError(
                f"duplicate custom building dialog_id: {building.dialog_id!r}"
            )
        seen_dialog_ids.add(dialog_key)
        buildings.append(building)

    return ModDefinition(
        schema_version=schema_version,
        mod_id=mod_id,
        internal_name=internal_name,
        display_name=display_name,
        custom_buildings=tuple(buildings),
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


def _parse_manifest(root: Path, manifest: Path) -> ModMetadata:
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
    if len(mod_nodes) != 1:
        raise PackageFormatError(
            f"manifest must contain exactly one Mod element; found {len(mod_nodes)}"
        )
    mod_node = mod_nodes[0]
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
                    directives.append(_parse_gpl_load(child, registry, context))
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
    gpl_node: ET.Element, registry: "_PathRegistry", context: str
) -> GplLoad:
    files = []
    target_count = 0
    for index, child in enumerate(list(gpl_node)):
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
    return GplLoad(files=tuple(files))


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
    return parse_mod_definition(
        {
            "schema_version": definition.schema_version,
            "mod_id": definition.mod_id,
            "internal_name": definition.internal_name,
            "display_name": definition.display_name,
            "custom_buildings": [
                {
                    "local_name": building.local_name,
                    "dialog_id": building.dialog_id,
                    "controller_base": building.controller_base,
                    "panel_resource_template": building.panel_resource_template,
                }
                for building in definition.custom_buildings
            ],
        }
    )


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
    "CamLoad",
    "CustomBuildingDefinition",
    "DatasetLoad",
    "DEFINITION_FILE_NAME",
    "DEFINITION_SCHEMA_VERSION",
    "DescriptionsLoad",
    "GplLoad",
    "GplPath",
    "LoadBlock",
    "LocalizedText",
    "ModDefinition",
    "ModMetadata",
    "ModPackage",
    "PackageFormatError",
    "PackagePath",
    "load_mod_definition",
    "load_package",
    "parse_mod_definition",
]
