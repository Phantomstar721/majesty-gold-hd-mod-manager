from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from ..gpl import DefinitionKind
from .paths import application_root, is_frozen_application
from .profile import normalize_guid


COMPATIBILITY_SCHEMA_VERSION = 1


class CompatibilityFormatError(ValueError):
    """Raised when the manager-owned compatibility registry is malformed."""


@dataclass(frozen=True)
class ResolutionOwner:
    kind: DefinitionKind
    name: str


@dataclass(frozen=True)
class CombinationResolution:
    required_mod_ids: tuple[str, ...]
    source_path: Path
    items: tuple[ResolutionOwner, ...]


@dataclass(frozen=True)
class CompatibilitySpec:
    mod_id: str
    alias: str
    definition_path: Path
    replacement_roots: tuple[Path, ...]
    merge_priority: int
    badge: str
    runtime_capabilities: tuple[str, ...]
    resolution_owners: tuple[ResolutionOwner, ...]

    def available_replacement(self) -> Path | None:
        for root in self.replacement_roots:
            if root.is_dir():
                return root.resolve()
        return None


@dataclass(frozen=True)
class CompatibilityRegistry:
    specs: Mapping[str, CompatibilitySpec]
    combination_resolutions: tuple[CombinationResolution, ...] = ()

    def get(self, mod_id: str) -> CompatibilitySpec | None:
        return self.specs.get(normalize_guid(mod_id))

    def __contains__(self, mod_id: object) -> bool:
        if not isinstance(mod_id, str):
            return False
        try:
            return normalize_guid(mod_id) in self.specs
        except ValueError:
            return False


def default_registry_path() -> Path:
    repo_root = application_root()
    return repo_root / "profiles" / "manager" / "compatibility.json"


def load_compatibility_registry(
    path: Path | None = None,
    *,
    repo_root: Path | None = None,
    workspace_root: Path | None = None,
) -> CompatibilityRegistry:
    if path is None and repo_root is not None:
        registry_path = (
            repo_root / "profiles" / "manager" / "compatibility.json"
        ).resolve(strict=True)
    else:
        registry_path = (path or default_registry_path()).resolve(strict=True)
    if repo_root is None:
        repo_root = registry_path.parents[2]
    repo_root = repo_root.resolve(strict=True)
    if workspace_root is None:
        # ``workspace:`` roots are developer fallbacks.  In a one-file build,
        # ``repo_root.parent`` is the shared temporary extraction parent and
        # must never become an implicit content search root.
        workspace_root = repo_root if is_frozen_application() else repo_root.parent
    workspace_root = workspace_root.resolve(strict=True)

    try:
        value = json.loads(
            registry_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except _DuplicateJsonKey as exc:
        raise CompatibilityFormatError(
            f"duplicate JSON key in compatibility registry: {exc.key!r}"
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityFormatError(
            f"cannot read compatibility registry {registry_path}: {exc}"
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != COMPATIBILITY_SCHEMA_VERSION:
        raise CompatibilityFormatError(
            f"unsupported compatibility registry: {registry_path}"
        )
    top_level_fields = set(value)
    required_top_level_fields = {"schema_version", "mods"}
    allowed_top_level_fields = required_top_level_fields | {
        "combination_resolutions"
    }
    if not required_top_level_fields.issubset(top_level_fields) or not top_level_fields.issubset(
        allowed_top_level_fields
    ):
        raise CompatibilityFormatError(
            "compatibility registry must contain only schema_version, mods, "
            "and optional combination_resolutions"
        )
    raw_mods = value.get("mods")
    if not isinstance(raw_mods, dict):
        raise CompatibilityFormatError("compatibility registry mods must be an object")

    specs: dict[str, CompatibilitySpec] = {}
    required_mod_fields = {
        "alias",
        "definition",
        "replacement_roots",
        "merge_priority",
        "badge",
        "runtime_capabilities",
        "resolution_owners",
    }
    for raw_id, raw in raw_mods.items():
        if not isinstance(raw_id, str) or not isinstance(raw, dict):
            raise CompatibilityFormatError("compatibility registry mod rows are invalid")
        mod_id = normalize_guid(raw_id)
        if mod_id in specs:
            raise CompatibilityFormatError(
                "compatibility registry repeats normalized Mod UUID "
                f"{mod_id}"
            )
        if set(raw) != required_mod_fields:
            missing = sorted(required_mod_fields - set(raw))
            unknown = sorted(set(raw) - required_mod_fields)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unknown:
                details.append("unknown " + ", ".join(unknown))
            raise CompatibilityFormatError(
                f"{mod_id} compatibility row has invalid fields: "
                + "; ".join(details)
            )
        alias = _required_slug(raw["alias"], f"{mod_id}.alias")
        definition = _required_string(raw["definition"], f"{mod_id}.definition")
        definition_path = _inside(repo_root, repo_root / definition, f"{mod_id}.definition")
        if not definition_path.is_file():
            raise CompatibilityFormatError(
                f"{mod_id}.definition does not exist: {definition_path}"
            )

        raw_roots = raw["replacement_roots"]
        if not isinstance(raw_roots, list) or any(not isinstance(item, str) for item in raw_roots):
            raise CompatibilityFormatError(f"{mod_id}.replacement_roots must be strings")
        roots = tuple(
            _resolve_replacement(item, repo_root=repo_root, workspace_root=workspace_root)
            for item in raw_roots
        )
        priority = raw["merge_priority"]
        if type(priority) is not int:
            raise CompatibilityFormatError(f"{mod_id}.merge_priority must be an integer")
        badge = _required_string(raw["badge"], f"{mod_id}.badge")

        raw_caps = raw["runtime_capabilities"]
        if not isinstance(raw_caps, list) or any(not isinstance(item, str) or not item.strip() for item in raw_caps):
            raise CompatibilityFormatError(
                f"{mod_id}.runtime_capabilities must be non-empty strings"
            )
        capabilities = tuple(dict.fromkeys(item.strip() for item in raw_caps))

        raw_resolutions = raw["resolution_owners"]
        if not isinstance(raw_resolutions, list):
            raise CompatibilityFormatError(f"{mod_id}.resolution_owners must be an array")
        resolutions: list[ResolutionOwner] = []
        for index, resolution in enumerate(raw_resolutions):
            if not isinstance(resolution, dict) or set(resolution) != {"kind", "name"}:
                raise CompatibilityFormatError(
                    f"{mod_id}.resolution_owners[{index}] must contain kind and name"
                )
            try:
                kind = DefinitionKind(_required_string(resolution["kind"], "kind"))
            except ValueError as exc:
                raise CompatibilityFormatError(
                    f"{mod_id}.resolution_owners[{index}] has unknown kind"
                ) from exc
            resolutions.append(
                ResolutionOwner(
                    kind=kind,
                    name=_required_string(resolution["name"], "name"),
                )
            )

        specs[mod_id] = CompatibilitySpec(
            mod_id=mod_id,
            alias=alias,
            definition_path=definition_path,
            replacement_roots=roots,
            merge_priority=priority,
            badge=badge,
            runtime_capabilities=capabilities,
            resolution_owners=tuple(resolutions),
        )
    raw_combinations = value.get("combination_resolutions", [])
    if not isinstance(raw_combinations, list):
        raise CompatibilityFormatError("combination_resolutions must be an array")
    combinations: list[CombinationResolution] = []
    for index, raw in enumerate(raw_combinations):
        context = f"combination_resolutions[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"requires", "source", "items"}:
            raise CompatibilityFormatError(
                f"{context} must contain requires, source, and items"
            )
        required = raw["requires"]
        if not isinstance(required, list) or len(required) < 2 or any(
            not isinstance(item, str) for item in required
        ):
            raise CompatibilityFormatError(f"{context}.requires needs at least two UUIDs")
        required_ids = tuple(dict.fromkeys(normalize_guid(item) for item in required))
        if len(required_ids) < 2:
            raise CompatibilityFormatError(
                f"{context}.requires needs at least two distinct UUIDs"
            )
        source_path = _inside(
            repo_root,
            repo_root / _required_string(raw["source"], f"{context}.source"),
            f"{context}.source",
        )
        if not source_path.is_file():
            raise CompatibilityFormatError(f"{context}.source does not exist: {source_path}")
        raw_items = raw["items"]
        if not isinstance(raw_items, list) or not raw_items:
            raise CompatibilityFormatError(f"{context}.items must be a non-empty array")
        items: list[ResolutionOwner] = []
        item_keys: set[tuple[DefinitionKind, str]] = set()
        for item_index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict) or set(raw_item) != {"kind", "name"}:
                raise CompatibilityFormatError(
                    f"{context}.items[{item_index}] must contain kind and name"
                )
            try:
                kind = DefinitionKind(
                    _required_string(raw_item["kind"], f"{context}.items[{item_index}].kind")
                )
            except ValueError as exc:
                raise CompatibilityFormatError(
                    f"{context}.items[{item_index}] has unknown kind"
                ) from exc
            name = _required_string(
                raw_item["name"], f"{context}.items[{item_index}].name"
            )
            key = (kind, name.casefold())
            if key in item_keys:
                raise CompatibilityFormatError(
                    f"{context}.items repeats {kind.value}:{name}"
                )
            item_keys.add(key)
            items.append(ResolutionOwner(kind=kind, name=name))
        combinations.append(
            CombinationResolution(
                required_mod_ids=required_ids,
                source_path=source_path,
                items=tuple(items),
            )
        )
    return CompatibilityRegistry(
        specs=specs,
        combination_resolutions=tuple(combinations),
    )


def _resolve_replacement(value: str, *, repo_root: Path, workspace_root: Path) -> Path:
    cleaned = value.strip()
    if cleaned.startswith("workspace:"):
        relative = cleaned[len("workspace:") :]
        return _inside(workspace_root, workspace_root / relative, "replacement root")
    return _inside(repo_root, repo_root / cleaned, "replacement root")


def _inside(root: Path, candidate: Path, context: str) -> Path:
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CompatibilityFormatError(f"{context} escapes its declared root") from exc
    return resolved


def _required_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompatibilityFormatError(f"{context} must be a non-empty string")
    return value.strip()


def _required_slug(value: object, context: str) -> str:
    result = _required_string(value, context)
    if not all(character.islower() or character.isdigit() or character == "-" for character in result):
        raise CompatibilityFormatError(f"{context} must be a lowercase slug")
    return result


class _DuplicateJsonKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _json_object_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


__all__ = [
    "CombinationResolution",
    "CompatibilityFormatError",
    "CompatibilityRegistry",
    "CompatibilitySpec",
    "ResolutionOwner",
    "default_registry_path",
    "load_compatibility_registry",
]
