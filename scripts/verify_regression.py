"""Offline regression gate. Never invokes the Manager or a user's Prepare operation."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
sys.dont_write_bytecode = True

COMMON = (
    "test_feature_parity_profiles", "test_native_impact_profiles",
    "test_impact_compatible_image", "test_manager_build", "test_startup_cache",
    "test_stock_input_cache", "test_regression_gate",
)
DEVELOPMENT = (
    "test_checked_placement", "test_placement_art", "test_scoped_descriptions",
    "test_paid_acquisition_profiles", "test_fade_persistence_profiles",
    "test_checked_relocation_profiles", "test_dawnfall_load_profiles",
    "test_checked_cast_profiles", "test_observation_native_profiles",
    "test_observer_body_profiles", "test_attack_observation_profiles",
    "test_placement_binding_profiles", "test_dawnfall_draw_profiles",
    "test_dawnfall_action_profiles", "test_cosmetic_action_profiles",
)
RELEASE = (
    "test_standard_review",
    "test_sound_review",
    "test_release_scope", "test_description_review", "test_sparse_art_ids",
    "test_standard_project_recovery", "test_event_review",
)

def normalized(code):
    """Ignore relocated filenames, not constants, bytecode, or line information."""
    return code.replace(co_filename="<bundle>", co_consts=tuple(
        normalized(v) if isinstance(v, types.CodeType) else v for v in code.co_consts))

class BundleLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, executable):
        from PyInstaller.archive.readers import CArchiveReader
        archive = CArchiveReader(str(executable))
        names = [n for n, entry in archive.toc.items() if entry[-1] == "z"]
        if len(names) != 1:
            raise ValueError("Expected exactly one packaged Python archive")
        self.archive = archive.open_embedded_archive(names[0])
        self.loaded = set()

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "majesty_cam" and not fullname.startswith("majesty_cam."):
            return None
        if fullname not in self.archive.toc:
            raise ImportError("Required module absent from packaged Manager: " + fullname)
        package = self.archive.toc[fullname][0] == 1
        return importlib.util.spec_from_loader(fullname, self, is_package=package)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Preserve source-relative fixture lookups; executed code is ONLY from EXE.
        relative = Path(*module.__name__.split("."))
        source = ROOT / "src" / relative
        source = source / "__init__.py" if module.__spec__.submodule_search_locations is not None else source.with_suffix(".py")
        module.__file__ = str(source)
        if module.__spec__.submodule_search_locations is not None:
            module.__path__ = [str(source.parent)]
        exec(self.archive.extract(module.__name__), module.__dict__)
        self.loaded.add(module.__name__)

    def verify_source(self):
        for name in sorted(n for n in self.archive.toc if n == "majesty_cam" or n.startswith("majesty_cam.")):
            relative = ROOT / "src" / Path(*name.split("."))
            source = relative / "__init__.py" if self.archive.toc[name][0] == 1 else relative.with_suffix(".py")
            if not source.is_file():
                raise ValueError("Unexpected/stale bundled module: " + name)
            expected = compile(source.read_bytes(), str(source), "exec", dont_inherit=True)
            if normalized(expected) != normalized(self.archive.extract(name)):
                raise ValueError("Packaged code differs from current source: " + name)

    def verify_data(self, application):
        for folder in ("profiles", "payload"):
            source = ROOT / folder
            bundled = application / "_internal" / folder
            expected = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in source.rglob("*") if p.is_file() and p.suffix != '.log'}
            actual = {str(p.relative_to(bundled)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in bundled.rglob("*") if p.is_file() and p.suffix != '.log'}
            if expected != actual:
                different = sorted(k for k in set(expected) | set(actual) if expected.get(k) != actual.get(k))
                raise ValueError("Packaged " + folder + " differs from build inputs: " + repr(different[:10]))

def execute_tests(names):
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
    if not result.wasSuccessful() or result.skipped or not result.testsRun:
        raise RuntimeError(output.getvalue() + "\nRequired skipped checks: " + repr(result.skipped))
    return result.testsRun

def write_guard(root):
    """Reject Python fixture writes outside the disposable regression directory."""
    root = Path(root).resolve()
    def check(path):
        if isinstance(path, (str, bytes, os.PathLike)):
            candidate = Path(os.fsdecode(path)).resolve()
            if candidate != root and root not in candidate.parents:
                raise PermissionError("Regression attempted a non-disposable write: " + str(candidate))
    def audit(event, args):
        if event == "open":
            path, mode, flags = args
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                check(path)
        elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime"):
            check(args[0])
        elif event in ("os.rename", "os.link"):
            check(args[0]); check(args[1])
        elif event == "os.symlink":
            check(args[1])
    return audit

def fixture_evidence():
    from majesty_cam.manager.qol_service import detect_majesty_branch, PUBLIC_BRANCH, BETA2_BRANCH, GOG_BRANCH
    expected = dict(PUBLIC=PUBLIC_BRANCH, BETA2=BETA2_BRANCH, GOG=GOG_BRANCH)
    rows = {}
    for name, branch in expected.items():
        value = os.environ.get("MAJESTY_" + name + "_EXE")
        if not value or not Path(value).is_file():
            raise ValueError("Missing required fixture: MAJESTY_" + name + "_EXE")
        path = Path(value)
        actual = detect_majesty_branch(path)
        if actual is None or actual.key != branch.key:
            raise ValueError("Wrong executable profile for " + name)
        rows[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "profile": actual.key}
        os.environ["MAJESTY_EXPLORATION_" + name + "_EXE"] = str(path)
    return rows

def test_inputs():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "runtime", "profiles", "tests", "scripts", "release")
            for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and p.suffix in (".py", ".cpp", ".h", ".json", ".gpl", ".ps1")}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("release", "development"))
    parser.add_argument("--application", type=Path, help="Read and test packaged EXE; never launch it")
    parser.add_argument("--verify-receipt", action="store_true", help="Check unchanged tested artifact before staging")
    args = parser.parse_args()
    configured = (ROOT / "regression-mode.txt").read_text().strip()
    if args.mode != configured:
        raise ValueError("Wrong checkout: this tree's regression mode is " + configured)
    if args.verify_receipt:
        if not args.application:
            raise ValueError("Receipt verification requires --application")
        receipt = json.loads((ROOT / "local/regression" / (args.mode + "-package.json")).read_text())
        if receipt.get("mode") != args.mode or not receipt.get("packaged"):
            raise ValueError("Not a packaged regression receipt for this mode")
        files = {str(p.relative_to(args.application)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(args.application.rglob("*")) if p.is_file() and p.suffix != '.log'}
        if files != receipt.get("application") or test_inputs() != receipt.get("testInputs"):
            raise ValueError("Application or regression inputs changed since verification")
        return 0
    initial_inputs = test_inputs()
    bundle = None
    if args.application:
        bundle = BundleLoader(args.application / "Majesty Mod Manager.exe")
        bundle.verify_source()
        bundle.verify_data(args.application)
        sys.meta_path.insert(0, bundle)
    fixtures = fixture_evidence()
    os.environ["MAJESTY_REQUIRE_DAMAGE_FIXTURES"] = "1"
    names = tuple(dict.fromkeys(COMMON + (RELEASE if args.mode == "release" else DEVELOPMENT)
                  + tuple(p.stem for p in sorted((ROOT / "tests").glob("test_*profiles.py")))))
    # A child owns the audit hook; this process only writes its local receipt.
    if os.environ.get("MMM_REGRESSION_CHILD") == "1":
        sys.addaudithook(write_guard(os.environ["MMM_REGRESSION_TEMP"]))
        execute_tests(names)
        return 0
    import subprocess
    reports = ROOT / "local" / "regression"
    reports.mkdir(parents=True, exist_ok=True)
    receipt = reports / (args.mode + ("-package" if bundle else "-source") + ".json")
    if receipt.exists():
        receipt.unlink()
    with tempfile.TemporaryDirectory(prefix="manager-regression-") as temporary:
        env = dict(os.environ, MMM_REGRESSION_CHILD="1", MMM_REGRESSION_TEMP=temporary,
                   TEMP=temporary, TMP=temporary, TMPDIR=temporary, PYTHONDONTWRITEBYTECODE="1")
        run = subprocess.run([sys.executable, str(Path(__file__)), *sys.argv[1:]], env=env, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(run.stdout + run.stderr)
    if test_inputs() != initial_inputs or fixture_evidence() != fixtures:
        raise ValueError("Regression inputs changed while checks were running; no receipt issued")
    if bundle:
        bundle.verify_source()
        bundle.verify_data(args.application)
    evidence = {"schema": 1, "mode": args.mode, "fixtures": fixtures,
                "modules": names, "packaged": bool(bundle), "liveGameplayAcceptance": False,
                "testInputs": initial_inputs}
    if bundle:
        evidence["application"] = {str(p.relative_to(args.application)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(args.application.rglob("*")) if p.is_file() and p.suffix != '.log'}
    receipt.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        print("Regression gate blocked: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
