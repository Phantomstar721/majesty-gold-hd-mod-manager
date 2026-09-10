from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Mapping

from ..intent_text import INTENT_REGISTRY_RELATIVE_PATH
from ..runtime_capabilities import (
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    write_runtime_capability_manifest,
)
from ..runtime_features import write_runtime_feature_registry
from ..stock_controller_registry import (
    resolve_stock_controller_registry,
    write_stock_controller_registry,
)
from .build import (
    BuildPlan,
    ManagerBuildError,
    ManagerBuildResult,
    STANDARD_SELECTION_ISSUE_CODES,
    build_merged_package,
    create_build_plan,
    standard_selection_issues,
    standard_conflict_pair_key,
    _order_standard_ids,
    read_managed_build,
    _require_current_plan_sources,
)
from .catalog import Catalog, CatalogKind, scan_catalog
from .compatibility import CompatibilityRegistry, load_compatibility_registry
from .launch import LaunchResult, ManagerLaunchError, launch_majesty
from .paths import (
    GAME_EXECUTABLE_NAME,
    GAME_SELECTION_FILENAME,
    ManagerPaths,
    detect_manager_paths,
    save_game_executable_selection,
)
from .preflight import catalog_merge_preflight
from .profile import (
    ManagerProfile,
    ProfileFormatError,
    initial_selection,
    load_profile,
    normalize_guid,
    read_remembered_mods,
    save_profile,
)
from .profile_lock import ProfileLockError, acquire_merged_profile_lock
from .qol import QolPatchStatus
from .qol_service import (
    MajestyBranch,
    QolCatalogSnapshot,
    QolService,
    QolUtilityStatus,
    detect_majesty_branch,
)
from .startup_cache import (
    StartupCache,
    catalog_input_signature,
    metadata_signature,
    merge_preflight_signature,
    qol_input_signature,
)


@dataclass(frozen=True)
class ControllerSnapshot:
    catalog: Catalog
    selections: Mapping[str, bool]
    plan: BuildPlan
    selection_source: str
    build_required: bool
    can_build: bool
    can_launch: bool
    managed_build: ManagerBuildResult | None
    qol_status: tuple[QolPatchStatus, ...]
    qol_utilities: tuple[QolUtilityStatus, ...]
    game_build: MajestyBranch | None
    notices: tuple[str, ...]


class ManagerController:
    """UI-independent orchestration for scan, selection, build, and launch."""

    def __init__(
        self,
        *,
        paths: ManagerPaths | None = None,
        registry: CompatibilityRegistry | None = None,
    ) -> None:
        self.paths = paths or detect_manager_paths()
        self.registry = registry or load_compatibility_registry(
            repo_root=self.paths.repo_root
        )
        self.catalog = Catalog(entries=())
        self.selections: dict[str, bool] = {}
        self.order: tuple[str, ...] = ()
        self.profile = ManagerProfile()
        self.standard_conflict_winners: dict[str, str] = {}
        self.selection_source = "defaults"
        self._prepared_merge_cache = {}
        self.plan = create_build_plan(
            self.catalog,
            self.selections,
            registry=self.registry,
            game_path=self.paths.game_path,
        )
        self.qol_status: tuple[QolPatchStatus, ...] = ()
        self.qol_catalog: QolCatalogSnapshot | None = None
        self.qol_service = QolService(
            repo_root=self.paths.repo_root,
            game_executable=self.paths.game_executable,
        )
        self._qol_checked = False
        self._qol_input_signature: str | None = None
        self._managed_build_cache: ManagerBuildResult | None = None
        self._managed_build_cache_loaded = False
        self.notices: list[str] = []

    def select_game_executable(self, executable: Path) -> MajestyBranch:
        """Validate and remember the Majesty executable used by this manager.

        All game-relative build, QOL, and launch services are rebound together;
        callers should follow this with a forced scan so catalog preflight and
        the displayed branch describe the newly selected installation.
        """

        selected = executable.resolve(strict=True)
        if selected.name.casefold() != GAME_EXECUTABLE_NAME.casefold():
            raise ValueError(
                f"Choose the game's {GAME_EXECUTABLE_NAME} file."
            )
        branch = detect_majesty_branch(selected)
        if branch is None:
            raise ValueError(
                "That executable is not the supported Standard or beta2 "
                "Majesty Gold HD build."
            )
        save_game_executable_selection(
            self.paths.profile_path.parent / GAME_SELECTION_FILENAME,
            selected,
        )
        self.paths = replace(self.paths, game_path=selected.parent)
        self.qol_service = QolService(
            repo_root=self.paths.repo_root,
            game_executable=self.paths.game_executable,
        )
        self.qol_catalog = None
        self.qol_status = ()
        self._qol_checked = False
        self._qol_input_signature = None
        self._prepared_merge_cache.clear()
        self._replan()
        self._managed_build_cache_loaded = False
        return branch

    def scan(
        self,
        *,
        inspect_qol: bool = True,
        force_refresh: bool = False,
    ) -> ControllerSnapshot:
        self.notices = []
        if force_refresh:
            self._prepared_merge_cache.clear()
        cache = StartupCache.load(self.paths.startup_cache_path)
        preflight_ids: set[str] = set()

        def inspect_merge(
            content_id: str, display_name: str, package_root: Path
        ):
            preflight_ids.add(content_id)
            signature = merge_preflight_signature(
                content_id=content_id,
                display_name=display_name,
                source_root=package_root,
                registry=self.registry,
                game_path=self.paths.game_path,
            )
            if not force_refresh:
                cached = cache.get_preflight(content_id, signature)
                if cached is not None:
                    return cached
            issues = catalog_merge_preflight(
                content_id,
                display_name,
                package_root,
                registry=self.registry,
                game_path=self.paths.game_path,
            )
            cache.set_preflight(content_id, signature, issues)
            return issues

        catalog_signature = catalog_input_signature(
            local_mods_root=self.paths.local_mods_root,
            local_quests_root=self.paths.local_quests_root,
            workshop_roots=self.paths.workshop_roots,
            registry=self.registry,
        )
        cached_catalog = (
            None if force_refresh else cache.get_catalog(catalog_signature)
        )
        if cached_catalog is not None:
            self.catalog = cached_catalog
        else:
            self.catalog = scan_catalog(
                local_mods_root=self.paths.local_mods_root,
                local_quests_root=self.paths.local_quests_root,
                workshop_roots=self.paths.workshop_roots,
                compatibility=self.registry.specs,
                merge_preflight=inspect_merge,
            )
            cache.retain_preflight(preflight_ids)
            cache.set_catalog(catalog_signature, self.catalog)
        try:
            saved = load_profile(self.paths.profile_path)
        except ProfileFormatError as exc:
            saved = None
            self.notices.append(str(exc))
        remembered = read_remembered_mods(
            self.paths.remembered_path,
            legacy_path=self.paths.game_path / "MajestyModPersistence.txt",
        )
        remembered = self._expand_generated_profile_ids(remembered)
        selectable_ids = tuple(
            entry.content_id
            for entry in self.catalog.entries
            if entry.selectable and entry.content_id is not None
        )
        selections, order, source = initial_selection(
            selectable_ids,
            saved_profile=saved,
            remembered_ids=remembered,
        )
        self.selections = selections
        self.order = order
        self.selection_source = source
        self._enforce_catalog_exclusivity()
        self.profile = saved or ManagerProfile()
        self.standard_conflict_winners = dict(
            self.profile.standard_conflict_winners
        )
        self._replan()
        self._qol_checked = inspect_qol
        if inspect_qol:
            try:
                qol_signature = qol_input_signature(self.qol_service)
                self._qol_input_signature = qol_signature
                qol_catalog = cache.get_qol(qol_signature, self.qol_service)
                if qol_catalog is None:
                    qol_catalog = self.qol_service.inspect()
                    cache.set_qol(qol_signature, qol_catalog)
                self._set_qol_catalog(qol_catalog)
            except Exception as exc:
                self.qol_catalog = None
                self.qol_status = ()
                self.notices.append(f"QOL preflight failed: {exc}")
        else:
            self.qol_catalog = None
            self.qol_status = ()
            self._qol_input_signature = None
        self._refresh_managed_build_cache(
            startup_cache=cache,
            allow_cached=True,
        )
        cache.save()
        return self.snapshot()

    def change_qol(self, key: str, install: bool) -> ControllerSnapshot:
        """Apply or remove one utility and refresh only the affected status.

        The canonical fail-closed script validates the complete mutation.
        Re-running independent PowerShell dry-runs afterward made a single
        button press needlessly slow and did not provide stronger ownership
        guarantees.
        """

        spec = next((item for item in self.qol_service.specs if item.key == key), None)
        if spec is None:
            raise KeyError(key)
        if not install and spec.required_by_manager:
            raise ValueError(
                f"{spec.name} is required when launching through Majesty Mod Manager."
            )
        previous_catalog = self.qol_catalog
        previous_status = None
        if previous_catalog is not None:
            try:
                previous_status = previous_catalog.get(key)
            except KeyError:
                previous_status = None
        if install:
            changed = self.qol_service.apply(key, current=previous_status)
        else:
            changed = self.qol_service.remove(key, current=previous_status)
        self._qol_checked = True
        if previous_catalog is None or previous_status is None:
            # This path is retained for non-UI callers which request a change
            # before the manager has ever inspected the QOL catalog.
            catalog = self.qol_service.inspect()
        else:
            catalog = QolCatalogSnapshot(
                game_executable=previous_catalog.game_executable,
                branch=previous_catalog.branch,
                utilities=tuple(
                    changed if status.key == key else status
                    for status in previous_catalog.utilities
                ),
            )
        self._set_qol_catalog(catalog)
        cache = StartupCache.load(self.paths.startup_cache_path)
        self._qol_input_signature = qol_input_signature(self.qol_service)
        cache.set_qol(self._qol_input_signature, catalog)
        cache.save()
        return self.snapshot()

    def set_selected(self, content_id: str, enabled: bool) -> ControllerSnapshot:
        normalized = normalize_guid(content_id)
        entry = next(
            (item for item in self.catalog.entries if item.content_id == normalized),
            None,
        )
        if entry is None or not entry.selectable:
            raise ValueError(f"Content is not selectable: {content_id}")
        if enabled:
            for incompatible_id in entry.incompatible_ids:
                self.selections[incompatible_id] = False
        self.selections[normalized] = bool(enabled)
        if entry.kind is CatalogKind.STANDARD:
            self._refresh_standard_plan()
        else:
            self._replan()
        self._save_selection_state()
        return self.snapshot()

    def select_all(self, kind: CatalogKind, enabled: bool) -> ControllerSnapshot:
        if kind is CatalogKind.QUEST:
            return self.snapshot()
        candidates = tuple(
            entry
            for entry in self.catalog.entries
            if entry.kind is kind and entry.selectable and entry.content_id is not None
        )
        if enabled:
            for entry in candidates:
                self.selections[entry.content_id] = False
            selected_ids: set[str] = set()
            for entry in sorted(
                candidates,
                key=lambda item: (
                    item.collection_id or "",
                    item.collection_index,
                    item.display_name.casefold(),
                ),
            ):
                if selected_ids.intersection(entry.incompatible_ids):
                    continue
                self.selections[entry.content_id] = True
                selected_ids.add(entry.content_id)
        else:
            for entry in candidates:
                self.selections[entry.content_id] = False
        if kind is CatalogKind.STANDARD:
            self._refresh_standard_plan()
        else:
            self._replan()
        self._save_selection_state()
        return self.snapshot()

    def set_standard_conflict_winner(
        self,
        left_id: str,
        right_id: str,
        winner_id: str,
    ) -> ControllerSnapshot:
        """Remember which whole Standard Mod should load last for one pair."""

        pair = standard_conflict_pair_key(left_id, right_id)
        winner = normalize_guid(winner_id)
        if winner not in pair.split("|"):
            raise ValueError("The conflict winner must be one of the two Mods.")
        self.standard_conflict_winners[pair] = winner
        self._refresh_standard_plan()
        self._save_selection_state()
        return self.snapshot()

    def build(self, *, progress=None) -> tuple[ManagerBuildResult, ControllerSnapshot]:
        snapshot = self.snapshot()
        if not snapshot.can_build:
            if not self._required_qol_ready():
                raise ManagerBuildError(self._required_qol_message("preparing mods"))
            details = "; ".join(issue.message for issue in self.plan.issues)
            raise ManagerBuildError(
                details or "Select at least one supported Merge mod before preparing mods."
            )
        result = build_merged_package(self.plan, self.paths, progress=progress)
        self._managed_build_cache = result
        self._managed_build_cache_loaded = True
        cache = StartupCache.load(self.paths.startup_cache_path)
        signature = self._managed_build_input_signature()
        cache.set_managed_build(
            signature,
            self._managed_build_cache_payload(result),
        )
        cache.save()
        self.profile = self._profile_with_current_selections().with_successful_build(
            fingerprint=result.fingerprint,
            mod_id=result.mod_id,
            path=result.output_root,
        )
        save_profile(self.paths.profile_path, self.profile)
        return result, self.snapshot()

    def launch(self) -> tuple[LaunchResult, ControllerSnapshot]:
        profile_lock = None
        try:
            if self.plan.has_merge:
                try:
                    profile_lock = acquire_merged_profile_lock(
                        self.paths.merged_output_root
                    )
                except ProfileLockError as exc:
                    raise ManagerLaunchError(str(exc)) from exc

            # For Merge launches the lock is already held, so this snapshot and
            # every subsequent input check observe one stable generated profile.
            if not self._managed_build_cache_loaded:
                self._refresh_managed_build_cache()
            snapshot = self.snapshot()
            if not snapshot.can_launch:
                if not self._required_qol_ready():
                    raise ManagerLaunchError(
                        self._required_qol_message("launching Majesty")
                    )
                if snapshot.build_required:
                    raise ManagerLaunchError(
                        "Build the selected Merge profile before launching."
                    )
                details = "; ".join(issue.message for issue in self.plan.issues)
                raise ManagerLaunchError(
                    details or "The current profile is not ready to launch."
                )
            active_ids = list(self.plan.selected_standard_ids)
            intent_registry: Path | None = None
            capability_manifest = self.paths.empty_runtime_capability_manifest
            runtime_feature_registry = self.paths.empty_runtime_feature_registry
            controller_registry = self.paths.empty_controller_registry
            if self.plan.has_merge:
                try:
                    _require_current_plan_sources(
                        self.plan,
                        game_path=self.paths.game_path,
                        phase="before launch",
                    )
                except ManagerBuildError as exc:
                    raise ManagerLaunchError(str(exc)) from exc
                if snapshot.managed_build is None:
                    raise ManagerLaunchError("The generated Merge profile is missing.")
                active_ids.append(snapshot.managed_build.mod_id)
                intent_registry = (
                    snapshot.managed_build.output_root
                    / Path(INTENT_REGISTRY_RELATIVE_PATH)
                )
                capability_manifest = snapshot.managed_build.capability_manifest
                runtime_feature_registry = (
                    snapshot.managed_build.runtime_feature_registry
                )
                controller_registry = snapshot.managed_build.controller_registry
            else:
                write_runtime_capability_manifest(capability_manifest, ())
                write_runtime_feature_registry(runtime_feature_registry, ())
                write_stock_controller_registry(
                    controller_registry,
                    resolve_stock_controller_registry((), {}),
                )
            result = launch_majesty(
                self.paths,
                active_ids,
                intent_registry=intent_registry,
                capability_manifest=capability_manifest,
                runtime_feature_registry=runtime_feature_registry,
                controller_registry=controller_registry,
                acquired_profile_lock=profile_lock,
                ensure_qol=not self._qol_cache_is_current(),
            )
            self.profile = self._profile_with_current_selections()
            save_profile(self.paths.profile_path, self.profile)
            return result, self.snapshot()
        finally:
            # launch_majesty closes the parent's handle after successful
            # inheritance. This also covers every pre-launch error path.
            if profile_lock is not None:
                profile_lock.close()

    def snapshot(self) -> ControllerSnapshot:
        if not self._managed_build_cache_loaded:
            self._refresh_managed_build_cache()
        managed = self._managed_build_cache
        build_required = bool(
            self.plan.has_merge
            and (
                managed is None
                or managed.fingerprint != self.plan.fingerprint
                or not managed.manifest.is_file()
                or not managed.report.is_file()
            )
        )
        runtime_ready = all(
            path.is_file()
            for path in (
                self.paths.game_executable,
                self.paths.runtime_launcher,
                self.paths.runtime_dll,
            )
        )
        qol_ready = self._required_qol_ready()
        can_build = self.plan.has_merge and self.plan.valid and qol_ready
        can_launch = self.plan.valid and runtime_ready and qol_ready and not build_required
        return ControllerSnapshot(
            catalog=self.catalog,
            selections=dict(self.selections),
            plan=self.plan,
            selection_source=self.selection_source,
            build_required=build_required,
            can_build=can_build,
            can_launch=can_launch,
            managed_build=managed,
            qol_status=self.qol_status,
            qol_utilities=(
                self.qol_catalog.utilities if self.qol_catalog is not None else ()
            ),
            game_build=(
                self.qol_catalog.branch if self.qol_catalog is not None else None
            ),
            notices=tuple(self.notices),
        )

    def _refresh_managed_build_cache(
        self,
        *,
        startup_cache: StartupCache | None = None,
        allow_cached: bool = False,
    ) -> ManagerBuildResult | None:
        """Revalidate generated output only at lifecycle safety boundaries.

        Reading a managed build inventories and hashes the complete generated
        package. Doing that on every scan or launch made unchanged startup
        proportional to package size. A complete metadata signature reuses the
        prior full validation only while every generated file is unchanged.
        """

        signature = self._managed_build_input_signature()
        cached = (
            startup_cache.get_managed_build(signature)
            if allow_cached and startup_cache is not None
            else None
        )
        self._managed_build_cache = self._managed_build_result_from_cache(cached)
        if self._managed_build_cache is None:
            self._managed_build_cache = read_managed_build(
                self.paths.merged_output_root
            )
            signature = self._managed_build_input_signature()
        if startup_cache is not None:
            startup_cache.set_managed_build(
                signature,
                (
                    self._managed_build_cache_payload(self._managed_build_cache)
                    if self._managed_build_cache is not None
                    else None
                ),
            )
        self._managed_build_cache_loaded = True
        return self._managed_build_cache

    def _managed_build_input_signature(self) -> str:
        return metadata_signature(
            (self.paths.merged_output_root,),
            context=("managed-build-v1",),
            recursive_directories=True,
        )

    @staticmethod
    def _managed_build_cache_payload(
        result: ManagerBuildResult,
    ) -> dict[str, object]:
        return {
            "manifest_name": result.manifest.name,
            "report_name": result.report.name,
            "mod_id": result.mod_id,
            "fingerprint": result.fingerprint,
            "selected_source_ids": list(result.selected_source_ids),
        }

    def _managed_build_result_from_cache(
        self,
        raw: Mapping[str, object] | None,
    ) -> ManagerBuildResult | None:
        if raw is None or set(raw) != {
            "manifest_name",
            "report_name",
            "mod_id",
            "fingerprint",
            "selected_source_ids",
        }:
            return None
        try:
            manifest_name = str(raw["manifest_name"])
            report_name = str(raw["report_name"])
            if (
                Path(manifest_name).name != manifest_name
                or not manifest_name.startswith("CAMManager-")
                or not manifest_name.casefold().endswith(".mmxml")
                or report_name != "CAM-MERGE-REPORT.json"
            ):
                return None
            selected = raw["selected_source_ids"]
            if not isinstance(selected, list):
                return None
            root = self.paths.merged_output_root
            result = ManagerBuildResult(
                output_root=root,
                manifest=root / manifest_name,
                report=root / report_name,
                capability_manifest=(
                    root / Path(RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH)
                ),
                mod_id=normalize_guid(str(raw["mod_id"])),
                fingerprint=str(raw["fingerprint"]),
                selected_source_ids=tuple(
                    normalize_guid(str(item)) for item in selected
                ),
            )
            if not all(
                path.is_file()
                for path in (
                    result.manifest,
                    result.report,
                    result.capability_manifest,
                    result.runtime_feature_registry,
                    result.controller_registry,
                )
            ):
                return None
            return result
        except (TypeError, ValueError):
            return None

    def _qol_cache_is_current(self) -> bool:
        return bool(
            self._required_qol_ready()
            and self._qol_input_signature is not None
            and self._qol_input_signature == qol_input_signature(self.qol_service)
        )

    def _set_qol_catalog(self, catalog: QolCatalogSnapshot) -> None:
        self.qol_catalog = catalog
        self.qol_status = tuple(
            QolPatchStatus(
                name=status.patch.spec.name,
                available=status.applicable and status.patch.apply_available,
                installed=status.installed is True,
                detail=status.detail,
            )
            for status in catalog.utilities
            if status.patch.spec.required_by_manager
        )

    def _required_qol_ready(self) -> bool:
        """Return true only after every required utility is confirmed installed.

        ``scan(inspect_qol=False)`` remains a useful, side-effect-free catalog test
        seam, but deliberately leaves build and launch gated: skipping inspection is
        not proof that the executable patches are installed.
        """

        required_specs = tuple(
            spec for spec in self.qol_service.specs if spec.required_by_manager
        )
        return bool(
            self._qol_checked
            and required_specs
            and len(self.qol_status) == len(required_specs)
            and all(status.installed for status in self.qol_status)
        )

    def _required_qol_message(self, action: str) -> str:
        required_names = tuple(
            spec.name for spec in self.qol_service.specs if spec.required_by_manager
        )
        installed_names = {
            status.name for status in self.qol_status if status.installed
        }
        missing = tuple(name for name in required_names if name not in installed_names)
        names = missing or required_names
        return (
            f"Install {' and '.join(names)} on the Quality of Life tab before "
            f"{action}."
        )

    def _replan(self) -> None:
        self.plan = create_build_plan(
            self.catalog,
            self.selections,
            registry=self.registry,
            order=self.order,
            game_path=self.paths.game_path,
            standard_conflict_winners=self.standard_conflict_winners,
            prepared_cache=self._prepared_merge_cache,
        )
        self._prepared_merge_cache.update(
            (item.content_id, item) for item in self.plan.selected_merge
        )

    def _refresh_standard_plan(self) -> None:
        """Update ordinary Mod IDs without re-inventorying selected CAM mods."""

        order_index = {
            normalize_guid(content_id): index
            for index, content_id in enumerate(self.order)
        }
        selected_entries = tuple(
            entry.content_id
            for entry in self.catalog.entries
            if entry.kind is CatalogKind.STANDARD
            and entry.selectable
            and entry.content_id is not None
            and self.selections.get(entry.content_id, False)
        )
        selected_ids = set(selected_entries)
        selected = tuple(
            entry
            for entry in self.catalog.entries
            if entry.content_id in selected_ids
        )
        self.plan = replace(
            self.plan,
            selected_standard_ids=_order_standard_ids(
                selected, order_index, self.standard_conflict_winners
            ),
            issues=tuple(
                issue
                for issue in self.plan.issues
                if issue.code not in STANDARD_SELECTION_ISSUE_CODES
            )
            + standard_selection_issues(
                self.catalog,
                self.selections,
                self.standard_conflict_winners,
            ),
        )

    def _enforce_catalog_exclusivity(self) -> None:
        """Make stale/default choices deterministic when variants conflict."""

        selected_ids: set[str] = set()
        candidates = sorted(
            (
                entry
                for entry in self.catalog.entries
                if entry.selectable
                and entry.content_id is not None
                and self.selections.get(entry.content_id, False)
            ),
            key=lambda item: (
                item.collection_id or "",
                item.collection_index,
                item.display_name.casefold(),
            ),
        )
        for entry in candidates:
            if selected_ids.intersection(entry.incompatible_ids):
                self.selections[entry.content_id] = False
            else:
                selected_ids.add(entry.content_id)

    def _save_selection_state(self) -> None:
        self.profile = self._profile_with_current_selections()
        save_profile(self.paths.profile_path, self.profile)

    def _profile_with_current_selections(self) -> ManagerProfile:
        order = list(self.order)
        seen = set(order)
        order.extend(key for key in self.selections if key not in seen)
        profile = self.profile.with_selections(self.selections, order)
        return replace(
            profile,
            standard_conflict_winners=dict(self.standard_conflict_winners),
        )

    def _expand_generated_profile_ids(self, remembered: tuple[str, ...]) -> tuple[str, ...]:
        result: list[str] = []
        generated_by_id = {
            entry.content_id: entry
            for entry in self.catalog.entries
            if entry.generated and entry.content_id is not None
        }
        for content_id in remembered:
            entry = generated_by_id.get(content_id)
            if entry is None:
                result.append(content_id)
                continue
            report_path = entry.package_root / "CAM-MERGE-REPORT.json"
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                inputs = report.get("inputs", [])
                expanded = [normalize_guid(item["mod_id"]) for item in inputs]
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                expanded = []
            if expanded:
                result.extend(expanded)
            else:
                self.notices.append(
                    "A previous combined setup could not be restored. "
                    "Review the Merge tab before preparing mods."
                )
        return tuple(dict.fromkeys(result))


__all__ = ["ControllerSnapshot", "ManagerController"]
