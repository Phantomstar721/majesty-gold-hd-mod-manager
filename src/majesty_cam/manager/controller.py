from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from ..intent_text import INTENT_REGISTRY_RELATIVE_PATH
from ..runtime_capabilities import write_runtime_capability_manifest
from .build import (
    BuildPlan,
    ManagerBuildError,
    ManagerBuildResult,
    build_merged_package,
    create_build_plan,
    read_managed_build,
    _require_current_plan_sources,
)
from .catalog import Catalog, CatalogKind, scan_catalog
from .compatibility import CompatibilityRegistry, load_compatibility_registry
from .launch import LaunchResult, ManagerLaunchError, launch_majesty
from .paths import ManagerPaths, detect_manager_paths
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
)
from .startup_cache import (
    StartupCache,
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
        self.selection_source = "defaults"
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
        self.notices: list[str] = []

    def scan(
        self,
        *,
        inspect_qol: bool = True,
        force_refresh: bool = False,
    ) -> ControllerSnapshot:
        self.notices = []
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

        self.catalog = scan_catalog(
            local_mods_root=self.paths.local_mods_root,
            local_quests_root=self.paths.local_quests_root,
            workshop_roots=self.paths.workshop_roots,
            compatibility=self.registry.specs,
            merge_preflight=inspect_merge,
        )
        cache.retain_preflight(preflight_ids)
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
        self.profile = saved or ManagerProfile()
        self._replan()
        self._qol_checked = inspect_qol
        if inspect_qol:
            try:
                qol_signature = qol_input_signature(self.qol_service)
                qol_catalog = (
                    None
                    if force_refresh
                    else cache.get_qol(qol_signature, self.qol_service)
                )
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
        cache.save()
        return self.snapshot()

    def change_qol(self, key: str, install: bool) -> ControllerSnapshot:
        """Apply or remove one canonical QOL utility and refresh its status."""

        spec = next((item for item in self.qol_service.specs if item.key == key), None)
        if spec is None:
            raise KeyError(key)
        if not install and spec.required_by_manager:
            raise ValueError(
                f"{spec.name} is required when launching through Majesty Mod Manager."
            )
        if install:
            self.qol_service.apply(key)
        else:
            self.qol_service.remove(key)
        self._qol_checked = True
        catalog = self.qol_service.inspect()
        self._set_qol_catalog(catalog)
        cache = StartupCache.load(self.paths.startup_cache_path)
        cache.set_qol(qol_input_signature(self.qol_service), catalog)
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
        self.selections[normalized] = bool(enabled)
        self._replan()
        self._save_selection_state()
        return self.snapshot()

    def select_all(self, kind: CatalogKind, enabled: bool) -> ControllerSnapshot:
        if kind is CatalogKind.QUEST:
            return self.snapshot()
        for entry in self.catalog.entries:
            if entry.kind is kind and entry.selectable and entry.content_id is not None:
                self.selections[entry.content_id] = bool(enabled)
        self._replan()
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
            else:
                write_runtime_capability_manifest(capability_manifest, ())
            result = launch_majesty(
                self.paths,
                active_ids,
                intent_registry=intent_registry,
                capability_manifest=capability_manifest,
                acquired_profile_lock=profile_lock,
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
        managed = read_managed_build(self.paths.merged_output_root)
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
        )

    def _save_selection_state(self) -> None:
        self.profile = self._profile_with_current_selections()
        save_profile(self.paths.profile_path, self.profile)

    def _profile_with_current_selections(self) -> ManagerProfile:
        order = list(self.order)
        seen = set(order)
        order.extend(key for key in self.selections if key not in seen)
        return self.profile.with_selections(self.selections, order)

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
