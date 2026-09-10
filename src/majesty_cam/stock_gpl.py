"""Prove that installed stock GPL source describes Majesty's loaded bytecode.

Majesty ships readable GPL projects beside the compiled BCD files used at
runtime.  A source-relative merge is safe only when those two views are proven
equivalent.  This module captures the complete installed source corpus, maps
the six stock projects to the BCDs in the game's actual dataset load order,
and recompiles an isolated mirror before exposing any semantic ancestor.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PureWindowsPath
import re
import stat
import subprocess
import tempfile
import threading
from typing import Callable, Optional
import xml.etree.ElementTree as ET

from ._subprocess import no_console_window_options
from .gpl import (
    DefinitionKind,
    ParsedSemanticSource,
    SemanticItem,
    parse_dat,
    parse_gpl,
    require_complete_semantic_coverage,
)


LINE_METADATA_PROBE_LINES = 65_793
# Distinct 24-bit byte patterns (0x010101 and 0x020203) make the probes
# independent evidence: a byte is never admitted merely because one shifted
# compile happened to differ from the exact compile.
LINE_METADATA_PROBE_SHIFTS = (
    LINE_METADATA_PROBE_LINES,
    131_587,
)
_CORPUS_ROOT = Path("SDK/OriginalQuests")
_CORPUS_DIRECTORIES = (Path("GPL"), Path("GPLMx"))
_CORPUS_SUFFIXES = frozenset((".gpl", ".dat", ".gplproj"))
_COMPILER_RELATIVE = Path("SDK/Gplbcc.exe")
_BASE_MANIFEST = Path("Data/MajestyDatasetDefinitions.xml")
_EXPANSION_MANIFEST = Path("DataMX/MajestyExpansionDatasetDefinitions.xml")
_PROJECT_ROW = re.compile(
    r'\s*(source|data)\s*=\s*"([^"]+)"\s*',
    flags=re.IGNORECASE,
)


class StockGplError(ValueError):
    """Raised when the installed source-to-runtime relationship is not proven."""


@dataclass(frozen=True)
class StockGplRuntimePair:
    """One stock compiler project and the exact BCD loaded for it at runtime."""

    project_relative: Path
    target_relative: Path

    @property
    def label(self) -> str:
        return (
            f"{self.project_relative.as_posix()} -> "
            f"{self.target_relative.as_posix()}"
        )


STOCK_GPL_RUNTIME_PAIRS = (
    StockGplRuntimePair(Path("GPL/path.gplproj"), Path("Data/bytecode.bcd")),
    StockGplRuntimePair(
        Path("GPLMx/Path_MajMisc.gplproj"),
        Path("DataMX/MX_Compatibility.bcd"),
    ),
    StockGplRuntimePair(
        Path("GPLMx/Path_Build.gplproj"),
        Path("DataMX/MX_Build.bcd"),
    ),
    StockGplRuntimePair(
        Path("GPLMx/Path_Data.gplproj"),
        Path("DataMX/MX_Data.bcd"),
    ),
    StockGplRuntimePair(
        Path("GPLMx/Path_Decision.gplproj"),
        Path("DataMX/MX_Decision.bcd"),
    ),
    StockGplRuntimePair(
        Path("GPLMx/Path_Task.gplproj"),
        Path("DataMX/MX_Task.bcd"),
    ),
)


@dataclass(frozen=True)
class StockGplProof:
    """Verified semantic lineage and the complete content snapshot proving it."""

    semantic_sources: tuple[ParsedSemanticSource, ...]
    input_hashes: tuple[tuple[str, str], ...]
    content_key: str
    runtime_pairs: tuple[StockGplRuntimePair, ...] = STOCK_GPL_RUNTIME_PAIRS


@dataclass(frozen=True)
class _CapturedFile:
    relative_path: Path
    absolute_path: Path
    payload: bytes
    sha256: str


@dataclass(frozen=True)
class _StockSnapshot:
    root: Path
    files: tuple[_CapturedFile, ...]
    content_key: str

    @property
    def input_hashes(self) -> tuple[tuple[str, str], ...]:
        return tuple((str(item.absolute_path), item.sha256) for item in self.files)

    def require(self, relative_path: Path) -> _CapturedFile:
        key = relative_path.as_posix().casefold()
        for item in self.files:
            if item.relative_path.as_posix().casefold() == key:
                return item
        raise StockGplError(
            f"stock GPL proof input was not captured: {relative_path.as_posix()}"
        )


@dataclass(frozen=True)
class _DeclaredProjectInput:
    role: str
    declared_relative: Path
    captured: _CapturedFile


@dataclass(frozen=True)
class _CapturedProject:
    pair: StockGplRuntimePair
    project: _CapturedFile
    inputs: tuple[_DeclaredProjectInput, ...]


_CACHE_LOCK = threading.Lock()
_PROOF_CACHE: dict[tuple[str, str], StockGplProof] = {}


def clear_stock_gpl_cache() -> None:
    """Clear successful in-process proofs, primarily for deterministic tests."""

    with _CACHE_LOCK:
        _PROOF_CACHE.clear()


def snapshot_stock_gpl_inputs(game_path: Path) -> tuple[tuple[str, str], ...]:
    """Return the complete, safe content snapshot used by the stock proof."""

    snapshot = _capture_snapshot(game_path)
    _validate_runtime_manifests(snapshot)
    _capture_projects(snapshot)
    return snapshot.input_hashes


def load_verified_stock_semantic_sources(
    game_path: Path,
    *,
    runner: Optional[Callable[..., object]] = None,
    use_cache: bool = True,
) -> tuple[tuple[ParsedSemanticSource, ...], tuple[tuple[str, str], ...]]:
    """Return stock semantics only after proving source against loaded BCDs."""

    proof = verify_stock_gpl(
        game_path,
        runner=runner,
        use_cache=use_cache,
    )
    return proof.semantic_sources, proof.input_hashes


def verify_stock_gpl(
    game_path: Path,
    *,
    runner: Optional[Callable[..., object]] = None,
    use_cache: bool = True,
) -> StockGplProof:
    """Capture, compile, and verify Majesty's complete stock GPL lineage."""

    snapshot = _capture_snapshot(game_path)
    _validate_runtime_manifests(snapshot)
    projects = _capture_projects(snapshot)
    cacheable = use_cache and runner is None
    cache_key = (str(snapshot.root).casefold(), snapshot.content_key)
    if cacheable:
        with _CACHE_LOCK:
            cached = _PROOF_CACHE.get(cache_key)
        if cached is not None:
            return cached

    actual_runner = subprocess.run if runner is None else runner
    _prove_runtime_targets(snapshot, projects, actual_runner)

    try:
        after = _capture_snapshot(snapshot.root)
        _validate_runtime_manifests(after)
        _capture_projects(after)
    except (OSError, StockGplError) as exc:
        raise StockGplError(
            f"stock GPL inputs changed during runtime proof: {exc}"
        ) from exc
    if after.content_key != snapshot.content_key:
        raise StockGplError("stock GPL inputs changed during runtime proof")

    semantic_sources = _parse_verified_sources(projects)
    proof = StockGplProof(
        semantic_sources=semantic_sources,
        input_hashes=after.input_hashes,
        content_key=after.content_key,
    )
    if cacheable:
        with _CACHE_LOCK:
            _PROOF_CACHE[cache_key] = proof
    return proof


def _capture_snapshot(game_path: Path) -> _StockSnapshot:
    requested_root = Path(game_path)
    if _is_reparse_point(requested_root):
        raise StockGplError(f"game path cannot be a symlink or reparse point: {game_path}")
    try:
        root = requested_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StockGplError(f"installed game path was not found: {game_path}") from exc
    if not root.is_dir():
        raise StockGplError(f"installed game path is not a directory: {root}")

    corpus_before = _enumerate_corpus(root)
    required = {
        _BASE_MANIFEST,
        _EXPANSION_MANIFEST,
        _COMPILER_RELATIVE,
        *(pair.target_relative for pair in STOCK_GPL_RUNTIME_PAIRS),
        *(path for path in corpus_before),
    }
    captured = tuple(
        _capture_file(root, relative)
        for relative in sorted(required, key=lambda value: value.as_posix().casefold())
    )
    corpus_after = _enumerate_corpus(root)
    if corpus_after != corpus_before:
        raise StockGplError(
            "installed stock GPL corpus changed while it was being captured"
        )

    digest = hashlib.sha256()
    digest.update(b"MajestyStockGplProof-v1\0")
    for item in captured:
        digest.update(item.relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.sha256.encode("ascii"))
        digest.update(b"\0")
    return _StockSnapshot(root, captured, digest.hexdigest())


def _enumerate_corpus(root: Path) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for relative_directory in _CORPUS_DIRECTORIES:
        directory_relative = _CORPUS_ROOT / relative_directory
        directory = _require_safe_directory(root, directory_relative)
        pending = [directory]
        while pending:
            current = pending.pop()
            try:
                children = sorted(
                    current.iterdir(),
                    key=lambda value: value.name.casefold(),
                    reverse=True,
                )
            except OSError as exc:
                raise StockGplError(
                    f"stock GPL directory could not be read: {current}"
                ) from exc
            for child in children:
                if _is_reparse_point(child):
                    raise StockGplError(
                        f"stock GPL corpus cannot contain a symlink or reparse point: {child}"
                    )
                if child.is_dir():
                    pending.append(child)
                    continue
                if not child.is_file() or child.suffix.casefold() not in _CORPUS_SUFFIXES:
                    continue
                relative = child.relative_to(root)
                key = relative.as_posix().casefold()
                if key in seen:
                    raise StockGplError(
                        "installed stock GPL corpus contains duplicate "
                        f"case-insensitive paths: {relative.as_posix()}"
                    )
                seen.add(key)
                result.append(relative)
    return tuple(sorted(result, key=lambda value: value.as_posix().casefold()))


def _capture_file(root: Path, relative: Path) -> _CapturedFile:
    path = _require_safe_file(root, relative)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise StockGplError(f"stock GPL proof input could not be read: {path}") from exc
    return _CapturedFile(
        relative_path=relative,
        absolute_path=path,
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _validate_runtime_manifests(snapshot: _StockSnapshot) -> None:
    specs = (
        (
            _BASE_MANIFEST,
            "Majesty",
            None,
            tuple(pair.target_relative for pair in STOCK_GPL_RUNTIME_PAIRS[:2]),
        ),
        (
            _EXPANSION_MANIFEST,
            "MajestyExpansion",
            "Majesty",
            tuple(pair.target_relative for pair in STOCK_GPL_RUNTIME_PAIRS[2:]),
        ),
    )
    for manifest_relative, configuration_name, dataset_base, expected in specs:
        captured = snapshot.require(manifest_relative)
        try:
            document = ET.fromstring(captured.payload)
        except ET.ParseError as exc:
            raise StockGplError(
                f"stock dataset definition is not valid XML: {captured.absolute_path}"
            ) from exc
        configurations = document.findall("./DataConfiguration")
        if (
            len(configurations) != 1
            or configurations[0].get("name") != configuration_name
        ):
            raise StockGplError(
                f"stock dataset definition has an unexpected configuration: "
                f"{captured.absolute_path}"
            )
        datasets = configurations[0].findall("./Dataset")
        if len(datasets) != 1 or datasets[0].get("base") != dataset_base:
            raise StockGplError(
                f"stock dataset definition has an unexpected dataset lineage: "
                f"{captured.absolute_path}"
            )
        loads = datasets[0].findall("./Load")
        if len(loads) != 1:
            raise StockGplError(
                f"stock dataset definition has an ambiguous load block: "
                f"{captured.absolute_path}"
            )
        nodes = loads[0].findall("./GPL")
        # Stock also carries an empty ``Dataset/Unload/GPL`` marker.  It is not
        # a runtime bytecode load; reject only additional GPL nodes in another
        # Load block while preserving that stock unload shape.
        if nodes != document.findall(".//Dataset/Load/GPL"):
            raise StockGplError(
                f"stock dataset definition has GPL loads outside its runtime load block: "
                f"{captured.absolute_path}"
            )
        actual: list[Path] = []
        for node in nodes:
            if node.attrib or list(node):
                raise StockGplError(
                    f"stock dataset definition has an unsupported GPL load: "
                    f"{captured.absolute_path}"
                )
            actual.append(
                _resolve_runtime_gpl_declaration(
                    (node.text or "").strip(),
                    captured.absolute_path,
                )
            )
        if tuple(actual) != expected:
            rendered = ", ".join(path.as_posix() for path in expected)
            raise StockGplError(
                f"stock dataset GPL load order does not match the supported runtime "
                f"lineage in {captured.absolute_path}; expected {rendered}"
            )


def _resolve_runtime_gpl_declaration(declared: str, manifest: Path) -> Path:
    match = re.fullmatch(r"\$\(([^)]+)\)[\\/]([^<>:\"|?*]+)", declared)
    if match is None:
        raise StockGplError(
            f"unsupported stock GPL runtime path in {manifest}: {declared!r}"
        )
    roots = {
        "majestybytecodedatapath": Path("Data"),
        "majestyexpansionbytecodedatapath": Path("DataMX"),
    }
    base = roots.get(match.group(1).casefold())
    if base is None:
        raise StockGplError(
            f"unsupported stock GPL runtime path variable in {manifest}: {declared!r}"
        )
    suffix = _safe_declared_relative(match.group(2), context=str(manifest))
    return base / suffix


def _capture_projects(snapshot: _StockSnapshot) -> tuple[_CapturedProject, ...]:
    result: list[_CapturedProject] = []
    by_absolute = {
        str(item.absolute_path).casefold(): item for item in snapshot.files
    }
    for pair in STOCK_GPL_RUNTIME_PAIRS:
        project_relative = _CORPUS_ROOT / pair.project_relative
        project = snapshot.require(project_relative)
        try:
            project_text = project.payload.decode("cp1252")
        except UnicodeError as exc:
            raise StockGplError(
                f"stock GPL project could not be decoded: {project.absolute_path}"
            ) from exc
        declared_inputs: list[_DeclaredProjectInput] = []
        declared_keys: set[str] = set()
        for line_number, line in enumerate(project_text.splitlines(), 1):
            match = _PROJECT_ROW.fullmatch(line)
            if match is None:
                if line.strip():
                    raise StockGplError(
                        f"{project.absolute_path}:{line_number}: unsupported stock GPL "
                        "project row"
                    )
                continue
            role = match.group(1).casefold()
            relative = _safe_declared_relative(
                match.group(2),
                context=f"{project.absolute_path}:{line_number}",
            )
            expected_suffix = ".gpl" if role == "source" else ".dat"
            if relative.suffix.casefold() != expected_suffix:
                raise StockGplError(
                    f"{project.absolute_path}:{line_number}: {role} row must name an "
                    f"{expected_suffix} file"
                )
            declared_key = relative.as_posix().casefold()
            if declared_key in declared_keys:
                raise StockGplError(
                    f"{project.absolute_path}:{line_number}: duplicate declared stock "
                    f"GPL input: {relative.as_posix()}"
                )
            declared_keys.add(declared_key)
            absolute = _require_safe_file(
                snapshot.root,
                project_relative.parent / relative,
            )
            captured = by_absolute.get(str(absolute).casefold())
            if captured is None:
                raise StockGplError(
                    f"stock GPL project input was outside the captured corpus: {absolute}"
                )
            declared_inputs.append(
                _DeclaredProjectInput(role, relative, captured)
            )
        if not declared_inputs:
            raise StockGplError(f"stock GPL project is empty: {project.absolute_path}")
        snapshot.require(pair.target_relative)
        result.append(_CapturedProject(pair, project, tuple(declared_inputs)))
    return tuple(result)


def _prove_runtime_targets(
    snapshot: _StockSnapshot,
    projects: tuple[_CapturedProject, ...],
    runner: Callable[..., object],
) -> None:
    with tempfile.TemporaryDirectory(prefix="MajestyStockGpl-") as raw_temp:
        temp = Path(raw_temp)
        mirror_root = temp / "mirror"
        _write_project_mirror(mirror_root, projects, line_shift=0)
        exact_rounds: list[dict[StockGplRuntimePair, bytes]] = []
        for _round in range(2):
            exact_rounds.append(
                {
                    project.pair: _compile_project(
                        snapshot,
                        project,
                        mirror_root,
                        runner,
                        line_shift=0,
                    )
                    for project in projects
                }
            )

        exact_outputs = exact_rounds[0]
        mismatches: list[_CapturedProject] = []
        for project in projects:
            compiled = exact_outputs[project.pair]
            if compiled != exact_rounds[1][project.pair]:
                raise StockGplError(
                    "stock GPL compiler output is not deterministic for the exact "
                    f"mirror of {project.pair.label}"
                )
            runtime = snapshot.require(project.pair.target_relative).payload
            if compiled != runtime:
                mismatches.append(project)

        if not mismatches:
            return

        probe_rounds: list[dict[int, dict[StockGplRuntimePair, bytes]]] = []
        for _round in range(2):
            round_outputs: dict[int, dict[StockGplRuntimePair, bytes]] = {}
            for line_shift in LINE_METADATA_PROBE_SHIFTS:
                # Reuse the exact mirror path so the line count is the only
                # input variable between these deterministic probes.
                _write_project_mirror(
                    mirror_root,
                    projects,
                    line_shift=line_shift,
                )
                round_outputs[line_shift] = {
                    project.pair: _compile_project(
                        snapshot,
                        project,
                        mirror_root,
                        runner,
                        line_shift=line_shift,
                    )
                    for project in mismatches
                }
            probe_rounds.append(round_outputs)

        for project in mismatches:
            probes = []
            for line_shift in LINE_METADATA_PROBE_SHIFTS:
                first = probe_rounds[0][line_shift][project.pair]
                second = probe_rounds[1][line_shift][project.pair]
                if first != second:
                    raise StockGplError(
                        "stock GPL compiler output is not deterministic for the "
                        f"{line_shift}-line metadata probe of {project.pair.label}"
                    )
                probes.append(first)
            exact = exact_outputs[project.pair]
            runtime = snapshot.require(project.pair.target_relative).payload
            if not _matches_outside_probe_mask(runtime, exact, tuple(probes)):
                raise StockGplError(
                    "stock GPL source does not reproduce the BCD Majesty loads for "
                    f"{project.pair.label}"
                )


def _write_project_mirror(
    mirror_root: Path,
    projects: tuple[_CapturedProject, ...],
    *,
    line_shift: int,
) -> None:
    written: dict[str, bytes] = {}
    for project in projects:
        project_destination = mirror_root / project.pair.project_relative
        _write_mirror_file(project_destination, project.project.payload, written)
        for item in project.inputs:
            payload = (
                (b"\r\n" * line_shift) + item.captured.payload
                if line_shift
                else item.captured.payload
            )
            destination = (
                mirror_root
                / project.pair.project_relative.parent
                / item.declared_relative
            )
            _write_mirror_file(destination, payload, written)


def _write_mirror_file(
    destination: Path,
    payload: bytes,
    written: dict[str, bytes],
) -> None:
    key = str(destination).casefold()
    previous = written.get(key)
    if previous is not None:
        if previous != payload:
            raise StockGplError(
                f"stock GPL mirror has conflicting case-insensitive paths: {destination}"
            )
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    written[key] = payload


def _compile_project(
    snapshot: _StockSnapshot,
    project: _CapturedProject,
    mirror_root: Path,
    runner: Callable[..., object],
    *,
    line_shift: int,
) -> bytes:
    project_path = mirror_root / project.pair.project_relative
    output = project_path.parent / project.pair.target_relative.name
    try:
        output.unlink(missing_ok=True)
    except OSError as exc:
        raise StockGplError(
            f"compiled stock GPL target could not be reset for {project.pair.label}"
        ) from exc
    command = (
        str(snapshot.require(_COMPILER_RELATIVE).absolute_path),
        "-in",
        project_path.name,
        "-out",
        output.name,
        "-stdout",
    )
    try:
        process = runner(
            command,
            cwd=project_path.parent,
            check=False,
            capture_output=True,
            text=True,
            encoding="cp1252",
            errors="replace",
            timeout=120,
            **no_console_window_options(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        phase = (
            f"{line_shift}-line metadata probe"
            if line_shift
            else "exact compile"
        )
        raise StockGplError(
            f"stock GPL {phase} failed for {project.pair.label}: {exc}"
        ) from exc
    returncode = getattr(process, "returncode", None)
    if returncode != 0 or not output.is_file() or _is_reparse_point(output):
        phase = (
            f"{line_shift}-line metadata probe"
            if line_shift
            else "exact compile"
        )
        raise StockGplError(
            f"stock GPL {phase} did not produce a valid target for "
            f"{project.pair.label} (exit {returncode!r})"
        )
    try:
        return output.read_bytes()
    except OSError as exc:
        raise StockGplError(
            f"compiled stock GPL target could not be read for {project.pair.label}"
        ) from exc


def _matches_outside_probe_mask(
    runtime: bytes,
    exact: bytes,
    probes: tuple[bytes, ...],
) -> bool:
    if len(probes) < 2 or len(runtime) != len(exact):
        return False
    if any(len(probe) != len(exact) for probe in probes):
        return False

    # A candidate byte must react to every independent line shift, and the
    # shifts must not produce one shared alternate value. This intersection
    # prevents a one-off compiler timestamp/random byte from widening the mask.
    reliably_line_metadata = tuple(
        all(probe_byte != exact_byte for probe_byte in probe_bytes)
        and len(set(probe_bytes)) > 1
        for exact_byte, probe_bytes in zip(exact, zip(*probes))
    )
    if not any(reliably_line_metadata):
        return False
    return all(
        masked or runtime_byte == exact_byte
        for masked, runtime_byte, exact_byte in zip(
            reliably_line_metadata,
            runtime,
            exact,
        )
    )


def _parse_verified_sources(
    projects: tuple[_CapturedProject, ...],
) -> tuple[ParsedSemanticSource, ...]:
    effective: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    for project in projects:
        for item in project.inputs:
            captured = item.captured
            try:
                text = captured.payload.decode("cp1252")
                parsed = (
                    parse_dat(text, str(captured.absolute_path))
                    if item.role == "data"
                    else parse_gpl(text, str(captured.absolute_path))
                )
                require_complete_semantic_coverage(parsed)
            except (UnicodeError, ValueError):
                # The exact compiled BCD remains verified and fingerprinted.
                # An unreadable source contributes no guessed ancestor, so a
                # selected change to that name must be resolved explicitly.
                continue
            for semantic_item in parsed.items:
                effective[semantic_item.key] = semantic_item
    return (
        ParsedSemanticSource(
            source_name="<verified installed stock MajestyExpansion GPL lineage>",
            text="",
            items=tuple(effective.values()),
        ),
    )


def _safe_declared_relative(raw: str, *, context: str) -> Path:
    value = PureWindowsPath(raw)
    if (
        not raw.strip()
        or value.is_absolute()
        or value.drive
        or any(part in ("", ".", "..") for part in value.parts)
    ):
        raise StockGplError(
            f"{context}: stock GPL path is not a safe relative path: {raw!r}"
        )
    return Path(*value.parts)


def _require_safe_directory(root: Path, relative: Path) -> Path:
    return _require_safe_path(root, relative, directory=True)


def _require_safe_file(root: Path, relative: Path) -> Path:
    return _require_safe_path(root, relative, directory=False)


def _require_safe_path(root: Path, relative: Path, *, directory: bool) -> Path:
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise StockGplError(f"unsafe stock GPL proof path: {relative}")
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if _is_reparse_point(current):
            raise StockGplError(
                f"stock GPL proof path cannot use a symlink or reparse point: {current}"
            )
        if index < len(relative.parts) - 1 and not current.is_dir():
            raise StockGplError(f"stock GPL proof directory was not found: {current}")
    if directory:
        if not current.is_dir():
            raise StockGplError(f"stock GPL directory was not found: {current}")
    elif not current.is_file():
        raise StockGplError(f"stock GPL proof file was not found: {current}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise StockGplError(f"stock GPL proof path escapes its game root: {current}") from exc
    return resolved


def _is_reparse_point(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


__all__ = [
    "LINE_METADATA_PROBE_LINES",
    "LINE_METADATA_PROBE_SHIFTS",
    "STOCK_GPL_RUNTIME_PAIRS",
    "StockGplError",
    "StockGplProof",
    "StockGplRuntimePair",
    "clear_stock_gpl_cache",
    "load_verified_stock_semantic_sources",
    "snapshot_stock_gpl_inputs",
    "verify_stock_gpl",
]
