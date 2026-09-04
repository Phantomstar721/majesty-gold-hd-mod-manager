from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Callable, Mapping, Sequence
import uuid

from ..compose import (
    ComposeError,
    ScopedSemanticResolution,
    compose_package,
    discover_selected_private_activity_texts,
    inventory_package,
    resolve_building_dialogs,
    resolve_controller_registry,
    resolve_runtime_feature_registry,
    snapshot_stock_compose_inputs,
    validate_controller_stock_evidence,
    validate_gpl_feature_evidence,
    validate_composed_package,
)
from ..gpl import (
    DefinitionKind,
    SemanticItem,
    parse_dat,
    parse_gpl,
    require_complete_semantic_coverage,
)
from ..intent_text import (
    INTENT_REGISTRY_RELATIVE_PATH,
    PrivateActivityTextBinding,
    decode_intent_registry,
)
from ..gpl_features import (
    StockGplmxPurchaseEquipmentTail,
    StockGplmxPurchaseBazaarTail,
    gpl_feature_mapping,
)
from ..package import (
    ModPackage,
    NameGeneratorFeature,
    PackageFormatError,
    load_package,
)
from ..runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    decode_runtime_capability_manifest,
)
from ..runtime_features import (
    RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
    RuntimeFeatureRegistry,
    decode_runtime_feature_registry,
    derive_feature_runtime_capabilities,
    encode_runtime_feature_registry,
)
from ..stock_controller_features import (
    ControllerFeatureError,
    LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,
    controller_feature_mapping,
)
from ..stock_controller_registry import (
    CONTROLLER_REGISTRY_RELATIVE_PATH,
    STOCK_CONTROLLER_RUNTIME_CAPABILITY,
    ResolvedControllerRegistry,
    decode_stock_controller_registry,
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
)
from .catalog import Catalog, CatalogEntry, CatalogKind
from .compatibility import CompatibilityRegistry
from .paths import ManagerPaths
from .preflight import PreparedMergeMod, prepare_merge_package
from .profile import normalize_guid
from .profile_lock import ProfileLockError, acquire_merged_profile_lock


MANAGER_OUTPUT_SENTINEL = ".majesty-mod-manager-owned.json"
PLAN_SCHEMA_VERSION = 6
STANDARD_SELECTION_ISSUE_CODES = frozenset(
    {
        "mutually_exclusive_mods",
        "missing_required_mod",
        "unresolved_standard_overlap",
    }
)


@dataclass(frozen=True)
class StandardContentConflict:
    """Two ordinary Mods which provide different versions of shared changes."""

    left_id: str
    left_name: str
    right_id: str
    right_name: str
    change_keys: tuple[str, ...]

    @property
    def pair_key(self) -> str:
        return standard_conflict_pair_key(self.left_id, self.right_id)


def standard_conflict_pair_key(left_id: str, right_id: str) -> str:
    return "|".join(sorted((normalize_guid(left_id), normalize_guid(right_id))))


def standard_content_conflicts(
    catalog: Catalog,
    selections: Mapping[str, bool] | None = None,
) -> tuple[StandardContentConflict, ...]:
    """Return exact divergent definition keys for each detected Mod pair."""

    by_id = {
        entry.content_id: entry
        for entry in catalog.entries
        if entry.kind is CatalogKind.STANDARD and entry.content_id is not None
    }
    selected_ids = (
        {
            normalize_guid(content_id)
            for content_id, enabled in selections.items()
            if enabled
        }
        if selections is not None
        else set(by_id)
    )
    result: list[StandardContentConflict] = []
    seen: set[tuple[str, str]] = set()
    for left_id in sorted(selected_ids):
        left = by_id.get(left_id)
        if left is None:
            continue
        left_definitions = dict(left.content_definitions)
        for right_id in left.unresolved_overlap_ids:
            if right_id not in selected_ids:
                continue
            pair = tuple(sorted((left_id, right_id)))
            if pair in seen:
                continue
            seen.add(pair)
            right = by_id.get(right_id)
            if right is None:
                continue
            right_definitions = dict(right.content_definitions)
            changes = tuple(
                sorted(
                    key
                    for key in set(left_definitions).intersection(right_definitions)
                    if left_definitions[key] != right_definitions[key]
                )
            )
            if changes:
                result.append(
                    StandardContentConflict(
                        left_id=left_id,
                        left_name=left.display_name,
                        right_id=right_id,
                        right_name=right.display_name,
                        change_keys=changes,
                    )
                )
    return tuple(
        sorted(
            result,
            key=lambda item: (
                item.left_name.casefold(),
                item.right_name.casefold(),
                item.pair_key,
            ),
        )
    )


_EMPTY_CONTROLLER_REGISTRY = resolve_stock_controller_registry((), {})


def _controller_record_count(registry: ResolvedControllerRegistry) -> int:
    return sum(
        len(section)
        for section in (
            registry.panels,
            registry.meters,
            registry.research_rows,
            registry.upgrade_gates,
            registry.timed_rage_actions,
            registry.rage_command_actions,
            registry.sovereign_target_actions,
            registry.reward_panels,
            registry.occupant_action_panels,
            registry.hostile_monster_flags,
            registry.building_open_toggles,
        )
    )


class ManagerBuildError(RuntimeError):
    """Raised when a manager build cannot proceed or publish safely."""


@dataclass(frozen=True)
class BuildIssue:
    code: str
    message: str
    content_id: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class BuildPlan:
    selected_standard_ids: tuple[str, ...]
    selected_merge: tuple[PreparedMergeMod, ...]
    resolution_owners: Mapping[tuple[DefinitionKind, str], str]
    semantic_resolutions: Mapping[
        tuple[DefinitionKind, str], ScopedSemanticResolution
    ]
    runtime_capabilities: tuple[str, ...]
    fingerprint: str
    issues: tuple[BuildIssue, ...]
    private_activity_texts: tuple[PrivateActivityTextBinding, ...] = ()
    stock_compose_inputs: tuple[tuple[str, str], ...] = ()
    compatibility_file_inputs: tuple[tuple[str, str], ...] = ()
    runtime_feature_registry: RuntimeFeatureRegistry = RuntimeFeatureRegistry()
    controller_registry: ResolvedControllerRegistry = _EMPTY_CONTROLLER_REGISTRY

    @property
    def stock_activity_text_inputs(self) -> tuple[tuple[str, str], ...]:
        """Backward-compatible name for the now-complete stock input snapshot."""

        return self.stock_compose_inputs

    @property
    def has_merge(self) -> bool:
        return bool(self.selected_merge)

    @property
    def valid(self) -> bool:
        return not self.issues and all(item.ready for item in self.selected_merge)

    @property
    def selected_merge_source_ids(self) -> tuple[str, ...]:
        return tuple(item.content_id for item in self.selected_merge)


@dataclass(frozen=True)
class ManagerBuildResult:
    output_root: Path
    manifest: Path
    report: Path
    capability_manifest: Path
    mod_id: str
    fingerprint: str
    selected_source_ids: tuple[str, ...]

    @property
    def runtime_feature_registry(self) -> Path:
        return self.output_root / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)

    @property
    def controller_registry(self) -> Path:
        return self.output_root / CONTROLLER_REGISTRY_RELATIVE_PATH


def _prepare_selected_merge_entries(
    entries: Sequence[CatalogEntry],
    *,
    registry: CompatibilityRegistry,
    order_index: Mapping[str, int],
) -> list[PreparedMergeMod]:
    prepared = [
        prepare_merge_package(
            content_id=entry.content_id,
            display_name=entry.display_name,
            source_root=entry.package_root,
            registry=registry,
        )
        for entry in entries
    ]
    prepared.sort(
        key=lambda item: (
            item.priority,
            order_index.get(item.content_id, 1_000_000),
            item.alias,
        )
    )
    return prepared


def create_build_plan(
    catalog: Catalog,
    selections: Mapping[str, bool],
    *,
    registry: CompatibilityRegistry,
    order: Sequence[str] = (),
    game_path: Path | None = None,
    standard_conflict_winners: Mapping[str, str] = {},
) -> BuildPlan:
    normalized_selections = {
        normalize_guid(key): bool(value) for key, value in selections.items()
    }
    order_index = {
        normalize_guid(content_id): index for index, content_id in enumerate(order)
    }
    issues: list[BuildIssue] = list(
        standard_selection_issues(
            catalog, normalized_selections, standard_conflict_winners
        )
    )
    standards: list[CatalogEntry] = []
    merge_entries: list[CatalogEntry] = []
    for entry in catalog.entries:
        if entry.content_id is None or not normalized_selections.get(entry.content_id, False):
            continue
        if entry.kind is CatalogKind.QUEST:
            continue
        if not entry.selectable:
            issues.append(
                BuildIssue(
                    "selected_item_not_ready",
                    f"{entry.display_name} is selected but did not pass catalog checks.",
                    entry.content_id,
                    entry.package_root,
                )
            )
            continue
        if entry.kind is CatalogKind.MERGE:
            merge_entries.append(entry)
        else:
            standards.append(entry)

    prepared = _prepare_selected_merge_entries(
        merge_entries,
        registry=registry,
        order_index=order_index,
    )
    aliases: dict[str, PreparedMergeMod] = {}
    effective_mod_ids: dict[str, PreparedMergeMod] = {}
    for item in prepared:
        for issue in item.issues:
            issues.append(
                BuildIssue(issue.code, issue.message, item.content_id, issue.path)
            )
        previous = aliases.get(item.alias)
        if previous is not None:
            issues.append(
                BuildIssue(
                    "duplicate_merge_alias",
                    f"{item.display_name} and {previous.display_name} both own alias {item.alias!r}.",
                    item.content_id,
                    item.effective_root,
                )
            )
        aliases[item.alias] = item
        if item.package is not None:
            try:
                effective_mod_id = normalize_guid(item.package.mod_id)
            except ValueError:
                # Intrinsic package preflight already reports a malformed UUID.
                continue
            previous_effective = effective_mod_ids.get(effective_mod_id)
            if previous_effective is not None:
                issues.append(
                    BuildIssue(
                        "duplicate_effective_mod_id",
                        (
                            f"{item.display_name} and {previous_effective.display_name} "
                            "resolve to the same effective Majesty mod identity "
                            f"{effective_mod_id}."
                        ),
                        item.content_id,
                        item.effective_root,
                    )
                )
            else:
                effective_mod_ids[effective_mod_id] = item

    owner_resolutions: dict[tuple[DefinitionKind, str], str] = {}
    for item in prepared:
        if item.compatibility is None:
            continue
        for resolution in item.compatibility.resolution_owners:
            key = (resolution.kind, resolution.name.casefold())
            previous = owner_resolutions.get(key)
            if previous is not None and previous != item.alias:
                issues.append(
                    BuildIssue(
                        "conflicting_resolution_metadata",
                        f"Multiple owners are declared for {resolution.kind.value}:{resolution.name}.",
                        item.content_id,
                    )
                )
            owner_resolutions[key] = item.alias

    semantic_resolutions: dict[
        tuple[DefinitionKind, str], ScopedSemanticResolution
    ] = {}
    semantic_candidates: dict[
        tuple[DefinitionKind, str],
        list[tuple[Path, SemanticItem, frozenset[str]]],
    ] = {}
    compatibility_file_hashes: dict[str, str] = {}
    selected_ids = {item.content_id for item in prepared}
    aliases_by_id = {item.content_id: item.alias for item in prepared}
    for combination in registry.combination_resolutions:
        if not set(combination.required_mod_ids).issubset(selected_ids):
            continue
        try:
            source_key = str(combination.source_path.resolve(strict=True))
            source_hash_before = _sha256_file(combination.source_path)
            parsed_items = _parse_resolution_source(combination.source_path)
            source_hash_after = _sha256_file(combination.source_path)
            if source_hash_before != source_hash_after:
                raise ManagerBuildError(
                    f"{combination.source_path} changed while compatibility "
                    "resolutions were being prepared"
                )
            previous_source_hash = compatibility_file_hashes.get(source_key)
            if (
                previous_source_hash is not None
                and previous_source_hash != source_hash_after
            ):
                raise ManagerBuildError(
                    f"{combination.source_path} changed between compatibility rules"
                )
            compatibility_file_hashes[source_key] = source_hash_after
            indexed: dict[
                tuple[DefinitionKind, str],
                list[SemanticItem],
            ] = {}
            for parsed_item in parsed_items:
                indexed.setdefault(parsed_item.key, []).append(parsed_item)
            participant_owners = frozenset(
                aliases_by_id[content_id]
                for content_id in combination.required_mod_ids
            )
            combination_candidates = []
            for requested in combination.items:
                key = (requested.kind, requested.name.casefold())
                matches = indexed.get(key, [])
                if not matches:
                    raise ManagerBuildError(
                        f"{combination.source_path} does not define "
                        f"{requested.kind.value}:{requested.name}"
                    )
                if len(matches) != 1:
                    raise ManagerBuildError(
                        f"{combination.source_path} defines "
                        f"{requested.kind.value}:{requested.name} more than once"
                    )
                combination_candidates.append(
                    (
                        key,
                        combination.source_path,
                        matches[0],
                        participant_owners,
                    )
                )
            for (
                key,
                source_path,
                source_item,
                candidate_participants,
            ) in combination_candidates:
                semantic_candidates.setdefault(key, []).append(
                    (source_path, source_item, candidate_participants)
                )
        except (OSError, ValueError, ManagerBuildError) as exc:
            issues.append(
                BuildIssue(
                    "invalid_combination_resolution",
                    str(exc),
                    path=combination.source_path,
                )
            )

    for key in sorted(semantic_candidates, key=lambda item: (item[0].value, item[1])):
        candidates = semantic_candidates[key]
        if len(candidates) != 1:
            sources = sorted(
                {str(path) for path, _item, _participants in candidates},
                key=str.casefold,
            )
            issues.append(
                BuildIssue(
                    "duplicate_combination_resolution",
                    (
                        "Multiple active compatibility rules resolve "
                        f"{key[0].value}:{key[1]}: " + ", ".join(sources)
                    ),
                )
            )
            continue
        source_path, source_item, participant_owners = candidates[0]
        semantic_resolutions[key] = ScopedSemanticResolution(
            item=SemanticItem.resolved(
                source_item.kind,
                source_item.name,
                source_item.text,
                source_name=str(source_path),
            ),
            participant_owners=participant_owners,
        )

    capabilities = {"generic-visitor-lists.v1"}
    for item in prepared:
        capabilities.update(item.runtime_capabilities)

    runtime_feature_registry = RuntimeFeatureRegistry()
    controller_registry = _EMPTY_CONTROLLER_REGISTRY
    if prepared and all(
        item.ready and isinstance(item.package, ModPackage) for item in prepared
    ):
        try:
            inventories = tuple(
                inventory_package(item.selected_mod) for item in prepared
            )
            validate_gpl_feature_evidence(inventories)
            runtime_feature_registry = resolve_runtime_feature_registry(
                inventories,
                tuple(sorted(capabilities)),
            )
            building_dialogs = resolve_building_dialogs(inventories)
            controller_result = resolve_controller_registry(
                inventories,
                tuple(sorted(capabilities)),
                building_dialogs=building_dialogs,
            )
            controller_registry = controller_result.registry
            if game_path is not None:
                validate_controller_stock_evidence(
                    game_path,
                    inventories,
                    controller_registry,
                    controller_panels=controller_result.panels,
                    controller_toggles=controller_result.toggles,
                    runtime_feature_registry=runtime_feature_registry,
                )
            capabilities = set(
                derive_feature_runtime_capabilities(
                    capabilities, runtime_feature_registry
                )
            )
            capabilities.discard(LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY)
            capabilities.discard(STOCK_CONTROLLER_RUNTIME_CAPABILITY)
            if _controller_record_count(controller_registry):
                capabilities.add(STOCK_CONTROLLER_RUNTIME_CAPABILITY)
        except (ComposeError, OSError, ValueError) as exc:
            issues.append(
                BuildIssue(
                    "unsafe_runtime_features",
                    str(exc),
                )
            )

    private_activity_texts: tuple[PrivateActivityTextBinding, ...] = ()
    stock_compose_inputs: tuple[tuple[str, str], ...] = ()
    if game_path is not None and prepared and all(item.ready for item in prepared):
        try:
            stock_compose_inputs = _fingerprint_stock_compose_inputs(game_path)
            private_activity_texts = discover_selected_private_activity_texts(
                game_path,
                tuple(item.selected_mod for item in prepared),
            )
        except (ComposeError, OSError, ValueError) as exc:
            issues.append(
                BuildIssue(
                    "unsafe_private_activity_text",
                    str(exc),
                )
            )
    if private_activity_texts:
        capabilities.add(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)

    compatibility_file_inputs = tuple(
        sorted(compatibility_file_hashes.items(), key=lambda item: item[0].casefold())
    )

    fingerprint = _plan_fingerprint(
        prepared,
        owner_resolutions=owner_resolutions,
        semantic_resolutions=semantic_resolutions,
        runtime_capabilities=capabilities,
        runtime_feature_registry=runtime_feature_registry,
        controller_registry=controller_registry,
        private_activity_texts=private_activity_texts,
        stock_compose_inputs=stock_compose_inputs,
        compatibility_file_inputs=compatibility_file_inputs,
    )
    try:
        reparsed = _prepare_selected_merge_entries(
            merge_entries,
            registry=registry,
            order_index=order_index,
        )
        current_stock_inputs = stock_compose_inputs
        if game_path is not None and prepared and all(
            item.ready for item in prepared
        ):
            current_stock_inputs = _fingerprint_stock_compose_inputs(game_path)
        current_compatibility_inputs = tuple(
            (
                raw_path,
                _sha256_file(Path(raw_path)),
            )
            for raw_path, _planned_sha256 in compatibility_file_inputs
        )
        current_fingerprint = _plan_fingerprint(
            reparsed,
            owner_resolutions=owner_resolutions,
            semantic_resolutions=semantic_resolutions,
            runtime_capabilities=capabilities,
            runtime_feature_registry=runtime_feature_registry,
            controller_registry=controller_registry,
            private_activity_texts=private_activity_texts,
            stock_compose_inputs=current_stock_inputs,
            compatibility_file_inputs=current_compatibility_inputs,
        )
        if reparsed != prepared or current_fingerprint != fingerprint:
            issues.append(
                BuildIssue(
                    "inputs_changed_during_prepare",
                    (
                        "Selected Merge mod, trusted compatibility, or installed "
                        "stock files changed while the build plan was being prepared. "
                        "Prepare the current selections again."
                    ),
                )
            )
    except (ComposeError, OSError, ValueError) as exc:
        issues.append(
            BuildIssue(
                "inputs_changed_during_prepare",
                (
                    "Selected Merge mod, trusted compatibility, or installed "
                    "stock files could not be revalidated after preparation: "
                    f"{exc}"
                ),
            )
        )
    standard_order = _order_standard_ids(
        standards,
        order_index,
        standard_conflict_winners,
    )
    return BuildPlan(
        selected_standard_ids=tuple(standard_order),
        selected_merge=tuple(prepared),
        resolution_owners=owner_resolutions,
        semantic_resolutions=semantic_resolutions,
        runtime_capabilities=tuple(sorted(capabilities)),
        private_activity_texts=private_activity_texts,
        stock_compose_inputs=stock_compose_inputs,
        compatibility_file_inputs=compatibility_file_inputs,
        runtime_feature_registry=runtime_feature_registry,
        controller_registry=controller_registry,
        fingerprint=fingerprint,
        issues=tuple(issues),
    )


def standard_selection_issues(
    catalog: Catalog,
    selections: Mapping[str, bool],
    conflict_winners: Mapping[str, str] = {},
) -> tuple[BuildIssue, ...]:
    """Validate cheap, scan-cached relationships among selected ordinary Mods."""

    selected_ids = {
        normalize_guid(content_id)
        for content_id, enabled in selections.items()
        if enabled
    }
    by_id = {
        entry.content_id: entry
        for entry in catalog.entries
        if entry.kind is CatalogKind.STANDARD and entry.content_id is not None
    }
    issues: list[BuildIssue] = []
    reported_conflicts: set[tuple[str, str]] = set()
    reported_overlaps: set[tuple[str, str]] = set()
    for content_id in sorted(selected_ids):
        entry = by_id.get(content_id)
        if entry is None:
            continue
        for required_id in entry.required_ids:
            if required_id in selected_ids:
                continue
            required = by_id.get(required_id)
            required_name = required.display_name if required is not None else required_id
            issues.append(
                BuildIssue(
                    "missing_required_mod",
                    f"{entry.display_name} requires {required_name}. Select both Mods.",
                    entry.content_id,
                    entry.manifest_path,
                )
            )
        for incompatible_id in entry.incompatible_ids:
            if incompatible_id not in selected_ids:
                continue
            pair = tuple(sorted((entry.content_id, incompatible_id)))
            if pair in reported_conflicts:
                continue
            reported_conflicts.add(pair)
            incompatible = by_id.get(incompatible_id)
            incompatible_name = (
                incompatible.display_name if incompatible is not None else incompatible_id
            )
            issues.append(
                BuildIssue(
                    "mutually_exclusive_mods",
                    (
                        f"{entry.display_name} cannot be used with {incompatible_name}. "
                        "Choose only one."
                    ),
                    entry.content_id,
                    entry.manifest_path,
                )
            )
        for overlap_id in entry.unresolved_overlap_ids:
            if overlap_id not in selected_ids:
                continue
            pair = tuple(sorted((entry.content_id, overlap_id)))
            if pair in reported_overlaps:
                continue
            reported_overlaps.add(pair)
            winner = conflict_winners.get(
                standard_conflict_pair_key(*pair)
            )
            if winner in pair:
                continue
            overlap = by_id.get(overlap_id)
            overlap_name = overlap.display_name if overlap is not None else overlap_id
            issues.append(
                BuildIssue(
                    "unresolved_standard_overlap",
                    (
                        f"{entry.display_name} and {overlap_name} replace the same "
                        "Majesty behavior, but neither package states a safe load "
                        "order. Disable one of them."
                    ),
                    entry.content_id,
                    entry.manifest_path,
                )
            )
    if _standard_order_has_cycle(by_id, selected_ids, conflict_winners):
        issues.append(
            BuildIssue(
                "conflicting_standard_order_choices",
                (
                    "The chosen conflict winners create an impossible Mod load "
                    "order. Change one of the conflict choices."
                ),
            )
        )
    return tuple(issues)


def _standard_order_has_cycle(
    by_id: Mapping[str, CatalogEntry],
    selected_ids: set[str],
    conflict_winners: Mapping[str, str],
) -> bool:
    outgoing: dict[str, set[str]] = {item: set() for item in selected_ids if item in by_id}
    for item, entry in by_id.items():
        if item not in outgoing:
            continue
        for prerequisite in entry.load_after_ids:
            if prerequisite in outgoing:
                outgoing[prerequisite].add(item)
    for pair_key, winner in conflict_winners.items():
        pair = tuple(pair_key.split("|"))
        if len(pair) != 2 or winner not in pair or any(item not in outgoing for item in pair):
            continue
        loser = pair[1] if winner == pair[0] else pair[0]
        outgoing[loser].add(winner)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item: str) -> bool:
        if item in visiting:
            return True
        if item in visited:
            return False
        visiting.add(item)
        if any(visit(dependent) for dependent in outgoing[item]):
            return True
        visiting.remove(item)
        visited.add(item)
        return False

    return any(visit(item) for item in outgoing if item not in visited)


def _order_standard_ids(
    entries: Sequence[CatalogEntry],
    order_index: Mapping[str, int],
    conflict_winners: Mapping[str, str] = {},
) -> tuple[str, ...]:
    """Apply detected before/after edges with stable saved-order tie breaking."""

    by_id = {
        entry.content_id: entry
        for entry in entries
        if entry.content_id is not None
    }
    base_key = lambda item: (order_index.get(item, 1_000_000), item)
    outgoing: dict[str, set[str]] = {item: set() for item in by_id}
    incoming: dict[str, int] = {item: 0 for item in by_id}
    for item, entry in by_id.items():
        for prerequisite in entry.load_after_ids:
            if prerequisite not in by_id or item in outgoing[prerequisite]:
                continue
            outgoing[prerequisite].add(item)
            incoming[item] += 1
    for pair_key, winner in conflict_winners.items():
        pair = tuple(pair_key.split("|"))
        if len(pair) != 2 or winner not in pair or any(item not in by_id for item in pair):
            continue
        loser = pair[1] if winner == pair[0] else pair[0]
        if winner in outgoing[loser]:
            continue
        outgoing[loser].add(winner)
        incoming[winner] += 1

    ready = sorted(
        (item for item, count in incoming.items() if count == 0),
        key=base_key,
    )
    result: list[str] = []
    while ready:
        item = ready.pop(0)
        result.append(item)
        for dependent in sorted(outgoing[item], key=base_key):
            incoming[dependent] -= 1
            if incoming[dependent] == 0:
                ready.append(dependent)
                ready.sort(key=base_key)

    # Cyclic prose is inherently ambiguous. Preserve the player's existing
    # order for that subset rather than inventing a winner.
    seen = set(result)
    result.extend(sorted((item for item in by_id if item not in seen), key=base_key))
    return tuple(result)


def build_merged_package(
    plan: BuildPlan,
    paths: ManagerPaths,
    *,
    progress: Callable[[str], None] | None = None,
) -> ManagerBuildResult:
    if not plan.has_merge:
        raise ManagerBuildError("No Merge mods are selected; a build is not required.")
    if not plan.valid:
        labels = "; ".join(issue.message for issue in plan.issues)
        raise ManagerBuildError(f"Build plan is not safe: {labels}")
    if not paths.game_executable.is_file():
        raise ManagerBuildError(f"MajestyHD.exe was not found: {paths.game_executable}")
    if not plan.stock_compose_inputs:
        raise ManagerBuildError(
            "Build plan has no complete stock composition fingerprint. Prepare the current "
            "Merge selections again before building."
        )

    target = _safe_manager_target(paths.local_mods_root, paths.merged_output_root)
    if target.exists() and not _is_manager_owned_output(target):
        raise ManagerBuildError(
            f"Refusing to replace a non-manager directory: {target}"
        )
    paths.local_mods_root.mkdir(parents=True, exist_ok=True)
    try:
        profile_lock = acquire_merged_profile_lock(target)
    except ProfileLockError as exc:
        raise ManagerBuildError(str(exc)) from exc
    if target.exists() and not _is_manager_owned_output(target):
        profile_lock.close()
        raise ManagerBuildError(
            f"Refusing to replace a non-manager directory: {target}"
        )

    staging = paths.local_mods_root / f".MajestyModManager-build-{uuid.uuid4().hex}"
    if progress:
        progress("Validating selected packages")
    try:
        _require_current_plan_sources(
            plan, game_path=paths.game_path, phase="before composition"
        )
        private_activity_texts = discover_selected_private_activity_texts(
            paths.game_path,
            tuple(item.selected_mod for item in plan.selected_merge),
        )
        if private_activity_texts != plan.private_activity_texts:
            raise ManagerBuildError(
                "Selected Merge mod activity text changed after Prepare. "
                "Prepare the current selections again."
            )
        runtime_capabilities = set(plan.runtime_capabilities)
        if private_activity_texts:
            runtime_capabilities.add(PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY)
        if progress:
            progress("Merging CAM, Description, and GPL resources")
        result = compose_package(
            paths.game_path,
            staging,
            tuple(item.selected_mod for item in plan.selected_merge),
            profile_slug="manager-merged",
            display_name="Majesty Mod Manager: Merged Profile",
            internal_name="MajestyModManagerMergedProfile",
            resolution_owners=plan.resolution_owners,
            semantic_resolutions=plan.semantic_resolutions,
            runtime_capabilities=tuple(sorted(runtime_capabilities)),
            private_activity_texts=private_activity_texts,
        )
        _require_current_plan_sources(
            plan, game_path=paths.game_path, phase="during composition"
        )
        registry_path = staging / Path(INTENT_REGISTRY_RELATIVE_PATH)
        registry_sha256 = _sha256_file(registry_path)
        capability_path = staging / Path(
            RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH
        )
        capability_data = capability_path.read_bytes()
        emitted_capabilities = decode_runtime_capability_manifest(capability_data)
        if emitted_capabilities != tuple(sorted(runtime_capabilities)):
            raise ManagerBuildError(
                "Generated runtime capability manifest does not match the "
                "validated build plan."
            )
        feature_path = staging / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)
        feature_data = feature_path.read_bytes()
        emitted_features = decode_runtime_feature_registry(feature_data)
        if emitted_features != plan.runtime_feature_registry:
            raise ManagerBuildError(
                "Generated runtime feature registry does not match the "
                "validated build plan."
            )
        controller_path = staging / CONTROLLER_REGISTRY_RELATIVE_PATH
        controller_data = controller_path.read_bytes()
        emitted_controllers = decode_stock_controller_registry(controller_data)
        if emitted_controllers != plan.controller_registry:
            raise ManagerBuildError(
                "Generated controller registry does not match the validated "
                "build plan."
            )
        sentinel = {
            "schema_version": 4,
            "fingerprint": plan.fingerprint,
            "mod_id": normalize_guid(result.mod_id),
            "selected_source_ids": list(plan.selected_merge_source_ids),
            "intent_registry": {
                "path": INTENT_REGISTRY_RELATIVE_PATH,
                "sha256": registry_sha256,
                "record_count": len(private_activity_texts),
            },
            "capability_manifest": {
                "path": RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
                "sha256": hashlib.sha256(capability_data).hexdigest(),
                "record_count": len(emitted_capabilities),
            },
            "runtime_feature_registry": {
                "path": RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
                "sha256": hashlib.sha256(feature_data).hexdigest(),
                "name_generator_count": len(emitted_features.name_generators),
                "enchantment_row_count": len(emitted_features.enchantment_rows),
            },
            "controller_registry": {
                "path": CONTROLLER_REGISTRY_RELATIVE_PATH.as_posix(),
                "sha256": hashlib.sha256(controller_data).hexdigest(),
                "record_count": _controller_record_count(emitted_controllers),
            },
            "generated_files": _generated_file_inventory(staging),
        }
        (staging / MANAGER_OUTPUT_SENTINEL).write_text(
            json.dumps(sentinel, indent=2) + "\n", encoding="utf-8"
        )
        _require_current_plan_sources(
            plan, game_path=paths.game_path, phase="before publication"
        )
        if progress:
            progress("Publishing validated profile")
        _publish_staging(staging, target)
    except (ComposeError, OSError, ValueError, ManagerBuildError) as exc:
        if staging.exists() and _is_safe_staging_path(
            staging, paths.local_mods_root, ".MajestyModManager-build-"
        ):
            shutil.rmtree(staging)
        raise ManagerBuildError(str(exc)) from exc
    finally:
        profile_lock.close()

    return ManagerBuildResult(
        output_root=target,
        manifest=target / result.manifest.name,
        report=target / result.report.name,
        capability_manifest=target
        / Path(RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH),
        mod_id=normalize_guid(result.mod_id),
        fingerprint=plan.fingerprint,
        selected_source_ids=plan.selected_merge_source_ids,
    )


def read_managed_build(path: Path) -> ManagerBuildResult | None:
    if not path.is_dir() or path.is_symlink():
        return None
    sentinel_path = path / MANAGER_OUTPUT_SENTINEL
    if not sentinel_path.is_file() or sentinel_path.is_symlink():
        return None
    try:
        value = json.loads(sentinel_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "fingerprint",
            "mod_id",
            "selected_source_ids",
            "intent_registry",
            "capability_manifest",
            "runtime_feature_registry",
            "controller_registry",
            "generated_files",
        }:
            return None
        if value.get("schema_version") != 4:
            return None
        expected_files = _parse_generated_file_inventory(value["generated_files"])
        actual_files = {
            item["path"]: item["sha256"]
            for item in _generated_file_inventory(path)
        }
        if actual_files != expected_files:
            return None
        manifests = sorted(path.glob("CAMManager-*.mmxml"))
        if len(manifests) != 1:
            return None
        fingerprint = str(value["fingerprint"])
        registry = value.get("intent_registry")
        if not isinstance(registry, dict) or set(registry) != {
            "path",
            "sha256",
            "record_count",
        }:
            return None
        if registry["path"] != INTENT_REGISTRY_RELATIVE_PATH:
            return None
        registry_path = path / Path(INTENT_REGISTRY_RELATIVE_PATH)
        registry_data = registry_path.read_bytes()
        records = decode_intent_registry(registry_data)
        if (
            hashlib.sha256(registry_data).hexdigest() != registry["sha256"]
            or type(registry["record_count"]) is not int
            or len(records) != registry["record_count"]
        ):
            return None
        controller = value.get("controller_registry")
        if not isinstance(controller, dict) or set(controller) != {
            "path",
            "sha256",
            "record_count",
        }:
            return None
        if controller["path"] != CONTROLLER_REGISTRY_RELATIVE_PATH.as_posix():
            return None
        controller_path = path / CONTROLLER_REGISTRY_RELATIVE_PATH
        controller_data = controller_path.read_bytes()
        controllers = decode_stock_controller_registry(controller_data)
        if (
            hashlib.sha256(controller_data).hexdigest() != controller["sha256"]
            or type(controller["record_count"]) is not int
            or _controller_record_count(controllers) != controller["record_count"]
        ):
            return None
        capability = value.get("capability_manifest")
        if not isinstance(capability, dict) or set(capability) != {
            "path",
            "sha256",
            "record_count",
        }:
            return None
        if capability["path"] != RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH:
            return None
        capability_path = path / Path(RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH)
        capability_data = capability_path.read_bytes()
        capabilities = decode_runtime_capability_manifest(capability_data)
        if (
            hashlib.sha256(capability_data).hexdigest() != capability["sha256"]
            or type(capability["record_count"]) is not int
            or len(capabilities) != capability["record_count"]
        ):
            return None
        feature = value.get("runtime_feature_registry")
        if not isinstance(feature, dict) or set(feature) != {
            "path",
            "sha256",
            "name_generator_count",
            "enchantment_row_count",
        }:
            return None
        if feature["path"] != RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH:
            return None
        feature_path = path / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)
        feature_data = feature_path.read_bytes()
        runtime_features = decode_runtime_feature_registry(feature_data)
        if (
            hashlib.sha256(feature_data).hexdigest() != feature["sha256"]
            or type(feature["name_generator_count"]) is not int
            or feature["name_generator_count"]
            != len(runtime_features.name_generators)
            or type(feature["enchantment_row_count"]) is not int
            or feature["enchantment_row_count"]
            != len(runtime_features.enchantment_rows)
        ):
            return None
        report_path = path / "CAM-MERGE-REPORT.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_runtime = report.get("runtime")
        if not isinstance(report_runtime, dict):
            return None
        if report_runtime.get("capabilities") != list(capabilities):
            return None
        report_capability = report_runtime.get("capability_manifest")
        if report_capability != capability:
            return None
        if report_runtime.get("feature_registry") != feature:
            return None
        if report_runtime.get("controller_registry") != controller:
            return None
        validation = validate_composed_package(path)
        if validation.get("manifest") != manifests[0].name:
            return None
        package = load_package(path, manifest_path=manifests[0])
        if (
            package.definition is None
            or package.definition.schema_version != 2
            or package.definition.runtime_capabilities != capabilities
        ):
            return None
        mod_id = normalize_guid(value["mod_id"])
        if normalize_guid(package.mod_id) != mod_id:
            return None
        return ManagerBuildResult(
            output_root=path,
            manifest=manifests[0],
            report=report_path,
            capability_manifest=capability_path,
            mod_id=mod_id,
            fingerprint=fingerprint,
            selected_source_ids=tuple(
                normalize_guid(item) for item in value.get("selected_source_ids", [])
            ),
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        ComposeError,
        ManagerBuildError,
        PackageFormatError,
    ):
        return None


def _generated_file_inventory(path: Path) -> list[dict[str, str]]:
    """Fingerprint every manager-generated file except the owning sentinel."""

    records: list[dict[str, str]] = []
    for item in sorted(
        path.rglob("*"), key=lambda value: value.relative_to(path).as_posix().casefold()
    ):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            raise ManagerBuildError(
                f"Managed output contains an unsupported symlink: {relative}"
            )
        if relative == MANAGER_OUTPUT_SENTINEL:
            continue
        if item.is_file():
            records.append({"path": relative, "sha256": _sha256_file(item)})
    return records


def _parse_generated_file_inventory(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise ValueError("generated file inventory must be an array")
    result: dict[str, str] = {}
    previous: str | None = None
    for record in value:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("generated file inventory record is invalid")
        relative = record["path"]
        digest = record["sha256"]
        if (
            not isinstance(relative, str)
            or not relative
            or "\\" in relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative == MANAGER_OUTPUT_SENTINEL
        ):
            raise ValueError("generated file inventory path is unsafe")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("generated file inventory digest is invalid")
        sort_key = relative.casefold()
        if previous is not None and sort_key <= previous:
            raise ValueError(
                "generated file inventory must be strictly case-insensitively sorted"
            )
        if relative in result:
            raise ValueError("generated file inventory contains duplicate paths")
        result[relative] = digest
        previous = sort_key
    return result


def _parse_resolution_source(path: Path) -> tuple[SemanticItem, ...]:
    text = path.read_text(encoding="cp1252")
    suffix = path.suffix.casefold()
    if suffix == ".gpl":
        source = parse_gpl(text, str(path))
    elif suffix == ".dat":
        source = parse_dat(text, str(path))
    else:
        raise ManagerBuildError(f"Unsupported resolution source extension: {path}")
    try:
        require_complete_semantic_coverage(source)
    except ValueError as exc:
        raise ManagerBuildError(
            f"Resolution source contains unparsed content that cannot be "
            f"preserved: {path}: {exc}"
        ) from exc
    return source.items


def _plan_fingerprint(
    prepared: Sequence[PreparedMergeMod],
    *,
    owner_resolutions: Mapping[tuple[DefinitionKind, str], str],
    semantic_resolutions: Mapping[
        tuple[DefinitionKind, str], ScopedSemanticResolution
    ],
    runtime_capabilities: set[str],
    runtime_feature_registry: RuntimeFeatureRegistry,
    controller_registry: ResolvedControllerRegistry,
    private_activity_texts: Sequence[PrivateActivityTextBinding],
    stock_compose_inputs: Sequence[tuple[str, str]],
    compatibility_file_inputs: Sequence[tuple[str, str]],
) -> str:
    packages = []
    for item in prepared:
        files = []
        if item.effective_root.is_dir():
            for path in sorted(
                (value for value in item.effective_root.rglob("*") if value.is_file()),
                key=lambda value: value.relative_to(item.effective_root).as_posix().casefold(),
            ):
                files.append(
                    (
                        path.relative_to(item.effective_root).as_posix(),
                        _sha256_file(path),
                    )
                )
        definition = getattr(item.package, "definition", None)
        external_definition_sha256 = None
        if item.compatibility is not None and not item.substituted:
            external_definition_sha256 = _sha256_file(
                item.compatibility.definition_path
            )
        packages.append(
            {
                "source_id": item.content_id,
                "effective_mod_id": item.package.mod_id if item.package else None,
                "alias": item.alias,
                "files": files,
                "definition": _canonical_mod_definition(definition),
                "external_definition_sha256": external_definition_sha256,
            }
        )
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "packages": packages,
        "owner_resolutions": sorted(
            (kind.value, name, owner)
            for (kind, name), owner in owner_resolutions.items()
        ),
        "semantic_resolutions": sorted(
            (
                kind.value,
                name,
                hashlib.sha256(
                    resolution.item.text.encode("cp1252")
                ).hexdigest(),
                sorted(resolution.participant_owners),
            )
            for (kind, name), resolution in semantic_resolutions.items()
        ),
        "runtime_capabilities": sorted(runtime_capabilities),
        "runtime_feature_registry_sha256": hashlib.sha256(
            encode_runtime_feature_registry(runtime_feature_registry)
        ).hexdigest(),
        "controller_registry_sha256": hashlib.sha256(
            encode_stock_controller_registry(controller_registry)
        ).hexdigest(),
        "stock_compose_inputs": sorted(stock_compose_inputs),
        "compatibility_file_inputs": sorted(compatibility_file_inputs),
        "private_activity_texts": [
            {
                "owner": binding.owner,
                "source_mod_id": binding.source_mod_id,
                "source_index": binding.source_index,
                "source_expressions": list(binding.expressions),
                "package_defined_source_expressions": list(
                    binding.package_expressions
                ),
                "generated_expression": binding.generated_expression,
                "expected_text_sha256": hashlib.sha256(
                    binding.expected_text.encode("cp1252")
                ).hexdigest(),
                "runtime_id": binding.runtime_id,
            }
            for binding in private_activity_texts
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_mod_definition(definition: object | None) -> object | None:
    """Return the exact semantic definition content used by package loading."""

    if definition is None:
        return None
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
            _canonical_runtime_feature(feature)
            for feature in definition.runtime_features
        ]
    return value


def _canonical_runtime_feature(feature: object) -> dict:
    if isinstance(feature, NameGeneratorFeature):
        return {
            "type": "stock.name-generator.v1",
            "generator_id": feature.generator_id,
            "name_tables": list(feature.name_part_ids),
        }
    if isinstance(feature, (StockGplmxPurchaseEquipmentTail, StockGplmxPurchaseBazaarTail)):
        return gpl_feature_mapping(feature)
    try:
        return controller_feature_mapping(feature)
    except ControllerFeatureError:
        pass
    return {
        "type": "stock.ap78-enchantment-row.v1",
        "overlay_id": feature.overlay_id,
        "display_text": feature.display_text,
    }


def _require_current_plan_sources(
    plan: BuildPlan, *, game_path: Path, phase: str
) -> None:
    try:
        stock_compose_inputs = _fingerprint_stock_compose_inputs(game_path)
        current = _plan_fingerprint(
            plan.selected_merge,
            owner_resolutions=plan.resolution_owners,
            semantic_resolutions=plan.semantic_resolutions,
            runtime_capabilities=set(plan.runtime_capabilities),
            runtime_feature_registry=plan.runtime_feature_registry,
            controller_registry=plan.controller_registry,
            private_activity_texts=plan.private_activity_texts,
            stock_compose_inputs=stock_compose_inputs,
            compatibility_file_inputs=tuple(
                (
                    raw_path,
                    _sha256_file(Path(raw_path)),
                )
                for raw_path, _planned_sha256 in plan.compatibility_file_inputs
            ),
        )
    except (ComposeError, OSError, ValueError) as exc:
        raise ManagerBuildError(
            "Selected Merge mod files, trusted compatibility files, and installed "
            "stock composition inputs could not "
            f"be revalidated {phase}: {exc}"
        ) from exc
    if current != plan.fingerprint:
        raise ManagerBuildError(
            "Selected Merge mod files, trusted compatibility files, or installed "
            f"stock composition inputs changed {phase}. "
            "Prepare the current selections again."
        )


def _fingerprint_stock_compose_inputs(
    game_path: Path,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            item.relative_path.as_posix(),
            item.sha256 if item.present else "absent",
        )
        for item in snapshot_stock_compose_inputs(game_path)
    )


def _safe_manager_target(mods_root: Path, target: Path) -> Path:
    mods = mods_root.resolve(strict=False)
    resolved = target.resolve(strict=False)
    if resolved.parent != mods or resolved.name != "Majesty Mod Manager - Merged":
        raise ManagerBuildError(f"Unsafe manager output target: {resolved}")
    if resolved.is_symlink():
        raise ManagerBuildError(f"Manager output target cannot be a symlink: {resolved}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_manager_owned_output(path: Path) -> bool:
    sentinel = path / MANAGER_OUTPUT_SENTINEL
    return (
        path.is_dir()
        and not path.is_symlink()
        and sentinel.is_file()
        and not sentinel.is_symlink()
    )


def _is_safe_staging_path(path: Path, parent: Path, prefix: str) -> bool:
    resolved = path.resolve(strict=False)
    return (
        resolved.parent == parent.resolve(strict=False)
        and resolved.name.startswith(prefix)
        and not resolved.is_symlink()
    )


def _publish_staging(staging: Path, target: Path) -> None:
    if not staging.is_dir() or staging.is_symlink():
        raise ManagerBuildError(f"Managed staging directory is invalid: {staging}")
    if staging.parent.resolve(strict=False) != target.parent.resolve(strict=False):
        raise ManagerBuildError(
            f"Managed staging and target must share a parent: {staging}, {target}"
        )
    if target.exists() and not _is_manager_owned_output(target):
        raise ManagerBuildError(
            f"Refusing to replace a non-manager directory during publication: {target}"
        )

    backup: Path | None = None
    try:
        if target.exists():
            backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
            target.rename(backup)
        staging.rename(target)
    except Exception as exc:
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        raise ManagerBuildError(f"Managed publication failed: {exc}") from exc

    if backup is not None and backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError:
            pass


__all__ = [
    "BuildIssue",
    "BuildPlan",
    "MANAGER_OUTPUT_SENTINEL",
    "ManagerBuildError",
    "ManagerBuildResult",
    "build_merged_package",
    "create_build_plan",
    "read_managed_build",
]
