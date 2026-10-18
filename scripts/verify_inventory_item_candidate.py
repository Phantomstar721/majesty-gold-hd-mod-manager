"""Read-only admission/registry check using source or the actual packaged code.

Does not compose a Manager profile, compile GPL, launch the app, or write a save.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--application", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    loader = None
    if args.application:
        from verify_regression import BundleLoader
        loader = BundleLoader(args.application / "Majesty Mod Manager.exe")
        sys.meta_path.insert(0, loader)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from majesty_cam.package import load_package
    from majesty_cam.compose import inventory_package, SelectedMod, resolve_runtime_feature_registry, _parse_inventory_gpl_sources
    from majesty_cam.hero_info import hero_info_mapping
    from majesty_cam.runtime_features import encode_runtime_feature_registry, decode_runtime_feature_registry
    from majesty_cam.manager.preflight import catalog_merge_preflight
    from majesty_cam.manager.compatibility import CompatibilityRegistry
    package = load_package(args.package)
    issues = catalog_merge_preflight(package.mod_id, package.definition.display_name, args.package,
        registry=CompatibilityRegistry({}), game_path=args.game)
    if issues:
        raise ValueError(f"candidate admission failed: {issues}")
    inventory = inventory_package(SelectedMod("candidate", package))
    registry = resolve_runtime_feature_registry((inventory,))
    encoded = encode_runtime_feature_registry(registry)
    decoded = decode_runtime_feature_registry(encoded)
    assert decoded == registry
    rows = [hero_info_mapping(row) for row in decoded.hero_info_rows if row.kind == "inventory"]
    if not rows:
        raise ValueError("candidate declares no real inventory display row")
    if loader:
        loader.verify_source()
        loader.verify_data(args.application)
    receipt = dict(package=str(args.package.resolve()), application=str(args.application.resolve()) if args.application else None,
        inventory_rows=rows, 
        registry_version=struct.unpack_from("<I", encoded, 4)[0], registry_sha256=hashlib.sha256(encoded).hexdigest(),
        package_files={p.relative_to(args.package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(args.package.rglob("*")) if p.is_file()},
        profile_constructed=False, gameplay_accepted=False)
    args.receipt.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
