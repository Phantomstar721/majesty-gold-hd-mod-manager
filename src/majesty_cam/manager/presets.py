"""Named selection presets and retained prepared packages."""
import json
from pathlib import Path
import shutil
import uuid
from functools import wraps

from .profile import _atomic_write, load_profile, save_profile
from .profile_lock import acquire_merged_profile_lock
from .build import read_managed_build, _publish_staging
from .paths import GAME_SELECTION_FILENAME, save_game_executable_selection
from .qol_service import detect_majesty_branch
from .quest_dataset import set_enabled


def _serialized(operation):
    @wraps(operation)
    def run(self, *args, **kwargs):
        self.root.mkdir(parents=True, exist_ok=True)
        with acquire_merged_profile_lock(self.root / "index"):
            self.state = Presets(self.paths).state
            if operation.__name__ != "activate" and (self.root / "pending-switch.json").exists():
                raise ValueError("Rescan to finish loading the saved profile before editing profiles.")
            return operation(self, *args, **kwargs)
    return run


class Presets:
    def __init__(self, paths):
        self.paths = paths
        self.root = paths.profile_path.parent / "presets"
        self.index = self.root / "index.json"
        self.state = json.loads(self.index.read_text("utf8")) if self.index.exists() else {"active": None, "items": []}
        items = self.state["items"]
        if len(items) > 5 or len({i["id"] for i in items}) != len(items):
            raise ValueError("Invalid saved profiles")
        for item in items:
            if uuid.UUID(item["id"]).hex != item["id"] or not item["name"].strip():
                raise ValueError("Invalid saved profile identity")

    def flush(self):
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.index, json.dumps(self.state, indent=2).encode())

    def folder(self, identity):
        if not any(i["id"] == identity for i in self.state["items"]):
            raise ValueError("Unknown saved profile")
        return self.root / identity

    def dirty(self, profile):
        active = self.state["active"]
        if active is None:
            return False
        saved = load_profile(self.folder(active) / "profile.json")
        return (profile.game_executable, profile.expansion_content, profile.classic_launch, {k:v for k,v in profile.selections.items() if v}, tuple(k for k in profile.order if profile.selections.get(k)), dict(profile.standard_conflict_winners)) != (
            saved.game_executable, saved.expansion_content, saved.classic_launch, {k:v for k,v in saved.selections.items() if v}, tuple(k for k in saved.order if saved.selections.get(k)), dict(saved.standard_conflict_winners))

    @_serialized
    def save(self, profile, *, name=None):
        if name is not None:
            if len(self.state["items"]) >= 5:
                raise ValueError("You can save up to five profiles.")
            name = name.strip()
            if not name or len(name) > 80:
                raise ValueError("Enter a profile name of up to 80 characters.")
            identity = uuid.uuid4().hex
            self.state["items"].append({"id": identity, "name": name})
        else:
            identity = self.state["active"]
            if identity is None:
                raise ValueError("Save this selection as a new profile first.")
        folder = self.folder(identity)
        folder.mkdir(parents=True, exist_ok=True)
        save_profile(folder / "profile.json", profile)
        self.state["active"] = identity
        self.flush()
        return identity

    @_serialized
    def delete(self, identity):
        folder = self.folder(identity)
        if folder.resolve().parent != self.root.resolve() or folder.is_symlink():
            raise ValueError("Unsafe saved-profile folder")
        self.state["items"] = [item for item in self.state["items"] if item["id"] != identity]
        if self.state["active"] == identity:
            self.state["active"] = None
        self.flush()
        if folder.exists():
            shutil.rmtree(folder)

    @_serialized
    def retain_build(self, profile, fingerprint):
        active = self.state["active"]
        if active is None or self.dirty(profile):
            return
        folder = self.folder(active)
        source = self.paths.merged_output_root
        with acquire_merged_profile_lock(source):
            build = read_managed_build(source)
            if build is None or build.fingerprint != fingerprint:
                raise ValueError("Selections were saved. The current prepared package needs Prepare before it can be retained for this profile.")
            staging = folder / ("package-" + uuid.uuid4().hex)
            try:
                shutil.copytree(source, staging)
                _publish_staging(staging, folder / "package")
            finally:
                if staging.exists():
                    shutil.rmtree(staging)

    @_serialized
    def activate(self, identity):
        folder = self.folder(identity)
        profile = load_profile(folder / "profile.json")
        if profile is None:
            raise ValueError("The saved profile is missing its selections.")
        executable = None
        if profile.game_executable is not None:
            executable = Path(profile.game_executable).resolve(strict=True)
            if executable.name.casefold() != "majestyhd.exe" or detect_majesty_branch(executable) is None:
                raise ValueError("The saved Game Install is unavailable or unsupported. Choose its MajestyHD.exe and update the profile.")
        target = self.paths.merged_output_root
        cached = folder / "package"
        pending = self.root / "pending-switch.json"
        with acquire_merged_profile_lock(target):
            use_cache = cached.exists() and read_managed_build(cached) is not None
            _atomic_write(pending, json.dumps({"id": identity}).encode())
            if use_cache:
                staging = target.parent / (".MajestyModManager-profile-" + uuid.uuid4().hex)
                try:
                    shutil.copytree(cached, staging)
                    _publish_staging(staging, target)
                except Exception:
                    pending.unlink()
                    raise
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            if executable is not None:
                save_game_executable_selection(self.paths.profile_path.parent / GAME_SELECTION_FILENAME, executable)
            if profile.expansion_content is not None:
                set_enabled(self.paths, profile.expansion_content)
            save_profile(self.paths.profile_path, profile)
            self.state["active"] = identity
            self.flush()
            pending.unlink()
        return profile


def recover_switch(paths):
    store = Presets(paths)
    pending = store.root / "pending-switch.json"
    if pending.exists():
        return store.activate(json.loads(pending.read_text("utf8"))["id"])
