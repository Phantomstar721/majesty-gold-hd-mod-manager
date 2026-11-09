"""One-scan catalog change badges using the existing file metadata fingerprint."""
import json
from .profile import _atomic_write
from .startup_cache import metadata_signature
from ..version import MANAGER_VERSION

MANAGER_CHANGE_KEY = "@manager"


def detect_changes(paths, catalog):
    path = paths.profile_path.parent / "catalog-seen.json"
    previous = json.loads(path.read_text("utf8")) if path.exists() else None
    current, labels, roots = {MANAGER_CHANGE_KEY: MANAGER_VERSION}, {}, {}
    if previous is not None and previous.get(MANAGER_CHANGE_KEY) != MANAGER_VERSION:
        labels[MANAGER_CHANGE_KEY] = "UPDATED"
    for entry in catalog.entries:
        if entry.generated or not entry.content_id:
            continue
        key = str(entry.manifest_path) + "|" + entry.content_id
        if entry.package_root not in roots:
            roots[entry.package_root] = metadata_signature((entry.package_root,), recursive_directories=True)
        current[key] = roots[entry.package_root]
        if previous is not None:
            if key not in previous:
                labels[entry.content_id] = "NEW"
            elif previous[key] != current[key]:
                labels[entry.content_id] = "UPDATED"
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(current).encode())
    return labels
