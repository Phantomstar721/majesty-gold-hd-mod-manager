"""Tolerant, read-only discovery of installed Majesty content.

This module deliberately does not reuse :mod:`majesty_cam.package` for the
initial catalog pass.  Package loading is strict because it protects the
composer; discovery instead has to preserve malformed items as structured
diagnostics so one bad Workshop download cannot prevent the manager opening.
The strict loader remains the authority when a selected merge package is
actually inventoried or composed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Mapping, Optional, Sequence, Tuple, Union
import uuid
import xml.etree.ElementTree as ET

from majesty_cam.gpl import parse_dat, parse_gpl
from majesty_cam.package import (
    DEFINITION_FILE_NAME,
    PackageFormatError,
    load_mod_definition,
)

from .capabilities import (
    DERIVED_RUNTIME_CAPABILITIES,
    SUPPORTED_RUNTIME_CAPABILITIES,
)


MAJESTY_SCRIPT_MERGER_ID = "FF86AE2B-43A8-4EB0-88FD-1EF1D7D6D2CD"
TOOL_DELIVERY_ISSUE_CODE = "non_gameplay_tool_delivery"
_KNOWN_TOOL_DELIVERY_IDS = frozenset((MAJESTY_SCRIPT_MERGER_ID,))
_TOOL_DELIVERY_PHRASES = (
    "modding tool only",
    "changes nothing in game",
    "changes nothing in the game",
)


class CatalogKind(str, Enum):
    """The manager section which owns an installed item."""

    STANDARD = "standard"
    QUEST = "quest"
    MERGE = "merge"


class CatalogSource(str, Enum):
    """The Majesty installation location where an item was found."""

    LOCAL_MODS = "local_mods"
    LOCAL_QUESTS = "local_quests"
    WORKSHOP = "workshop"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class CatalogIssue:
    """A stable, UI-friendly discovery diagnostic."""

    code: str
    message: str
    severity: IssueSeverity
    path: Optional[Path] = None
    content_id: Optional[str] = None


@dataclass(frozen=True)
class CatalogEntry:
    """One discovered manifest and its manager classification."""

    content_id: Optional[str]
    raw_content_id: Optional[str]
    display_name: str
    kind: CatalogKind
    source: CatalogSource
    package_root: Path
    manifest_path: Path
    has_cam: bool
    merge_ready: bool
    compatibility_applied: bool = False
    generated: bool = False
    issues: Tuple[CatalogIssue, ...] = ()
    description: Optional[str] = None
    details: Optional[str] = None
    collection_id: Optional[str] = None
    collection_name: Optional[str] = None
    collection_index: int = 0
    collection_size: int = 1
    variant_label: Optional[str] = None
    incompatible_ids: Tuple[str, ...] = ()
    incompatible_names: Tuple[str, ...] = ()
    load_after_ids: Tuple[str, ...] = ()
    load_after_names: Tuple[str, ...] = ()
    load_before_ids: Tuple[str, ...] = ()
    load_before_names: Tuple[str, ...] = ()
    required_ids: Tuple[str, ...] = ()
    required_names: Tuple[str, ...] = ()
    unresolved_overlap_ids: Tuple[str, ...] = ()
    unresolved_overlap_names: Tuple[str, ...] = ()
    content_definitions: Tuple[Tuple[str, str], ...] = ()

    @property
    def selectable(self) -> bool:
        """Whether the item may participate in an active-mod selection.

        Quests are cataloged for visibility but are loaded by Majesty's quest
        lifecycle, not its active Mod GUID list.  Generated profiles are
        manager outputs, never inputs to another composition.
        """

        if self.kind is CatalogKind.QUEST or self.generated or self.tool_delivery:
            return False
        if self.content_id is None:
            return False
        if self.kind is CatalogKind.MERGE and not self.merge_ready:
            return False
        return not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)

    @property
    def active_mod_selectable(self) -> bool:
        """Explicit alias for consumers which also display quest entries."""

        return self.selectable

    @property
    def tool_delivery(self) -> bool:
        """Whether the manifest explicitly describes a non-gameplay tool payload."""

        return any(issue.code == TOOL_DELIVERY_ISSUE_CODE for issue in self.issues)

    @property
    def workshop_item_id(self) -> Optional[str]:
        """Return this entry's Steam PublishedFileId when it has one.

        Workshop package roots are named with Steam's decimal PublishedFileId.
        The source check is important: a numeric local Mods folder is not proof
        that an item came from Steam Workshop.
        """

        if self.source is not CatalogSource.WORKSHOP:
            return None
        return _published_file_id_from_path(self.package_root)

    @property
    def in_collection(self) -> bool:
        """Whether this row belongs to a multi-option manifest."""

        return self.collection_id is not None and self.collection_size > 1


@dataclass(frozen=True)
class Catalog:
    """A deterministic snapshot of all discovered content."""

    entries: Tuple[CatalogEntry, ...]
    issues: Tuple[CatalogIssue, ...] = ()

    @property
    def visible_entries(self) -> Tuple[CatalogEntry, ...]:
        """Player-facing entries, excluding manager-owned generated outputs.

        ``entries`` intentionally retains those outputs so controller startup
        can expand a remembered generated profile back to its source Mod IDs.
        They are implementation state, not installed content the user should
        select or see beside source packages.
        """

        return tuple(entry for entry in self.entries if not entry.generated)

    @property
    def standard(self) -> Tuple[CatalogEntry, ...]:
        return tuple(
            entry
            for entry in self.visible_entries
            if entry.kind is CatalogKind.STANDARD
        )

    @property
    def quests(self) -> Tuple[CatalogEntry, ...]:
        return tuple(
            entry for entry in self.visible_entries if entry.kind is CatalogKind.QUEST
        )

    @property
    def merge(self) -> Tuple[CatalogEntry, ...]:
        return tuple(
            entry for entry in self.visible_entries if entry.kind is CatalogKind.MERGE
        )


CompatibilityCallback = Callable[[str, Path], bool]
CompatibilityResolver = Union[Mapping[str, object], CompatibilityCallback]
MergePreflightCallback = Callable[
    [str, str, Path], Sequence[CatalogIssue]
]


@dataclass(frozen=True)
class _Candidate:
    package_root: Path
    manifest_path: Path
    source: CatalogSource
    ambiguous: bool


def normalize_content_id(value: str) -> str:
    """Return Majesty content UUID text in uppercase, without braces."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("content id must be a non-empty UUID string")
    cleaned = value.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1].strip()
    try:
        parsed = uuid.UUID(cleaned)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"invalid Majesty content UUID: {value!r}") from exc
    return str(parsed).upper()


def scan_catalog(
    *,
    local_mods_root: Optional[Union[str, Path]] = None,
    local_quests_root: Optional[Union[str, Path]] = None,
    workshop_roots: Sequence[Union[str, Path]] = (),
    compatibility: Optional[CompatibilityResolver] = None,
    merge_preflight: Optional[MergePreflightCallback] = None,
) -> Catalog:
    """Scan immediate installed-content roots without mutating them.

    ``local_mods_root`` and ``local_quests_root`` are the respective MajestyHD
    folders; each immediate child directory is inspected.  Each path in
    ``workshop_roots`` may be either one Workshop item root or the Steam app's
    Workshop content directory: when it has no top-level game manifest, its
    immediate child directories are inspected as item roots.

    A compatibility mapping is keyed by Mod UUID (any UUID spelling accepted);
    mapping values are opaque because the catalog only needs to know that the
    manager owns a compatibility definition.  A callback receives the
    normalized UUID and package root and returns the same readiness decision.

    ``merge_preflight`` runs only after a Merge row passes the tolerant
    manifest/definition checks. It receives normalized UUID, display name, and
    package root. Returned errors make that row red and nonselectable before
    the controller restores or defaults any selections.
    """

    candidates = []
    root_issues = []
    if local_mods_root is not None:
        found, issues = _local_candidates(local_mods_root, CatalogSource.LOCAL_MODS)
        candidates.extend(found)
        root_issues.extend(issues)
    if local_quests_root is not None:
        found, issues = _local_candidates(local_quests_root, CatalogSource.LOCAL_QUESTS)
        candidates.extend(found)
        root_issues.extend(issues)
    for workshop_root in workshop_roots:
        found, issues = _workshop_candidates(workshop_root)
        candidates.extend(found)
        root_issues.extend(issues)

    # A root can be supplied through more than one discovery route.  Keep the
    # source with stock-like local precedence, then use lexical paths so results
    # never depend on filesystem enumeration order.
    candidates.sort(key=_candidate_sort_key)
    unique_candidates = []
    seen_manifests = set()
    for candidate in candidates:
        key = str(candidate.manifest_path).casefold()
        if key in seen_manifests:
            continue
        seen_manifests.add(key)
        unique_candidates.append(candidate)

    entries = []
    for candidate in unique_candidates:
        entries.extend(
            _parse_candidate(candidate, compatibility, merge_preflight)
        )
    entries, duplicate_issues = _deduplicate_entries(entries)
    entries = _annotate_explicit_relationships(entries)
    entries = _annotate_standard_content_overlaps(entries)
    entries.sort(key=_entry_sort_key)
    all_issues = list(root_issues)
    all_issues.extend(duplicate_issues)
    for entry in entries:
        all_issues.extend(entry.issues)
    all_issues = _unique_issues(all_issues)
    all_issues.sort(key=_issue_sort_key)
    return Catalog(entries=tuple(entries), issues=tuple(all_issues))


def _local_candidates(
    raw_root: Union[str, Path], source: CatalogSource
) -> Tuple[list[_Candidate], list[CatalogIssue]]:
    root, issue = _scan_root(raw_root, source)
    if root is None:
        return [], ([issue] if issue is not None else [])
    candidates = []
    for child in _sorted_child_directories(root):
        candidates.extend(_manifest_candidates(child, source))
    return candidates, []


def _workshop_candidates(
    raw_root: Union[str, Path],
) -> Tuple[list[_Candidate], list[CatalogIssue]]:
    root, issue = _scan_root(raw_root, CatalogSource.WORKSHOP)
    if root is None:
        return [], ([issue] if issue is not None else [])
    direct = _manifest_candidates(root, CatalogSource.WORKSHOP)
    if direct:
        return direct, []
    candidates = []
    for child in _sorted_child_directories(root):
        # Steam Workshop item directories are decimal PublishedFileIds.  Do
        # not ingest local backup/scratch folders which happen to sit beside
        # them (for example ``3769947406.backup-...``).
        if not child.name.isdecimal():
            continue
        candidates.extend(_manifest_candidates(child, CatalogSource.WORKSHOP))
    return candidates, []


def _scan_root(
    raw_root: Union[str, Path], source: CatalogSource
) -> Tuple[Optional[Path], Optional[CatalogIssue]]:
    try:
        root = Path(raw_root).resolve(strict=True)
    except (OSError, RuntimeError):
        return None, CatalogIssue(
            code="scan_root_missing",
            message=f"{source.value} scan root does not exist: {raw_root}",
            severity=IssueSeverity.WARNING,
            path=Path(raw_root),
        )
    if not root.is_dir():
        return None, CatalogIssue(
            code="scan_root_not_directory",
            message=f"{source.value} scan root is not a directory: {root}",
            severity=IssueSeverity.WARNING,
            path=root,
        )
    return root, None


def _sorted_child_directories(root: Path) -> list[Path]:
    try:
        children = [path.resolve() for path in root.iterdir() if path.is_dir()]
    except OSError:
        return []
    return sorted(children, key=lambda path: (path.name.casefold(), str(path).casefold()))


def _manifest_candidates(root: Path, source: CatalogSource) -> list[_Candidate]:
    try:
        manifests = [
            path.resolve()
            for path in root.iterdir()
            if path.is_file() and path.suffix.casefold() in {".mmxml", ".mqxml"}
        ]
    except OSError:
        return []
    manifests.sort(key=lambda path: (path.name.casefold(), str(path).casefold()))
    mod_count = sum(path.suffix.casefold() == ".mmxml" for path in manifests)
    return [
        _Candidate(
            package_root=root,
            manifest_path=path,
            source=source,
            # A Workshop quest pack normally owns several independent mqxml
            # manifests which share Data/GPL.  That is stock packaging, not an
            # ambiguity.  Merge Mod packages stay one-manifest-per-root.
            ambiguous=(mod_count > 1 if path.suffix.casefold() == ".mmxml" else False),
        )
        for path in manifests
    ]


def _parse_candidate(
    candidate: _Candidate,
    compatibility: Optional[CompatibilityResolver],
    merge_preflight: Optional[MergePreflightCallback],
) -> Tuple[CatalogEntry, ...]:
    manifest = candidate.manifest_path
    expected_tag = "Mod" if manifest.suffix.casefold() == ".mmxml" else "Quest"
    inferred_kind = CatalogKind.STANDARD if expected_tag == "Mod" else CatalogKind.QUEST
    issues = []
    if candidate.ambiguous:
        issues.append(
            CatalogIssue(
                code="ambiguous_manifests",
                message=(
                    f"package contains multiple top-level {manifest.suffix} manifests; "
                    "it cannot be selected safely"
                ),
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )

    try:
        xml_bytes = manifest.read_bytes()
    except OSError as exc:
        issues.append(
            CatalogIssue(
                code="manifest_read_error",
                message=f"cannot read manifest: {exc}",
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )
        return (_invalid_entry(candidate, inferred_kind, issues),)

    upper = xml_bytes.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        issues.append(
            CatalogIssue(
                code="unsafe_xml_declaration",
                message="manifest DTD/entity declarations are not allowed",
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )
        return (_invalid_entry(candidate, inferred_kind, issues),)
    try:
        xml_root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        issues.append(
            CatalogIssue(
                code="invalid_manifest_xml",
                message=f"invalid XML: {exc}",
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )
        return (_invalid_entry(candidate, inferred_kind, issues),)

    content_nodes = [
        node for node in xml_root.iter() if _local_name(node.tag) == expected_tag
    ]
    if expected_tag == "Quest" and (
        len(content_nodes) != 1 or content_nodes[0] not in list(xml_root)
    ):
        issues.append(CatalogIssue(
            code="invalid_manifest_shape",
            message="Quest manifest must contain one direct Quest child of its document root.",
            severity=IssueSeverity.ERROR,
            path=manifest,
        ))
        return (_invalid_entry(candidate, inferred_kind, issues),)
    # Majesty's stock Mod catalog permits one .mmxml document to publish
    # several independent Mod elements.  Each element has its own UUID and is
    # independently selectable in the game's Mod dialog.  Quest manifests and
    # strict Merge package loading retain their narrower shapes.
    if not content_nodes or (expected_tag != "Mod" and len(content_nodes) != 1):
        issues.append(
            CatalogIssue(
                code="invalid_manifest_shape",
                message=(
                    f"{manifest.suffix} manifest must contain exactly one "
                    f"{expected_tag} element; found {len(content_nodes)}"
                ),
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )
        return (_invalid_entry(candidate, inferred_kind, issues),)

    multiple_mod_elements = expected_tag == "Mod" and len(content_nodes) > 1
    parsed = tuple(
        _parse_content_node(
            candidate,
            content,
            expected_tag=expected_tag,
            inherited_issues=issues,
            multiple_mod_elements=multiple_mod_elements,
            compatibility=compatibility,
            merge_preflight=merge_preflight,
        )
        for content in content_nodes
    )
    if multiple_mod_elements:
        return _annotate_mod_collection(candidate, parsed, tuple(content_nodes))
    return parsed


def _parse_content_node(
    candidate: _Candidate,
    content: ET.Element,
    *,
    expected_tag: str,
    inherited_issues: Sequence[CatalogIssue],
    multiple_mod_elements: bool,
    compatibility: Optional[CompatibilityResolver],
    merge_preflight: Optional[MergePreflightCallback],
) -> CatalogEntry:
    """Turn one stock-selectable Mod or Quest element into a catalog row."""

    manifest = candidate.manifest_path
    issues = list(inherited_issues)

    raw_content_id = _clean_text(content.get("id"))
    content_id = None
    if raw_content_id is None:
        issues.append(
            CatalogIssue(
                code="missing_content_id",
                message=f"manifest {expected_tag} has no content UUID",
                severity=IssueSeverity.ERROR,
                path=manifest,
            )
        )
    else:
        try:
            content_id = normalize_content_id(raw_content_id)
        except ValueError:
            issues.append(
                CatalogIssue(
                    code="invalid_content_id",
                    message=f"manifest has an invalid content UUID: {raw_content_id!r}",
                    severity=IssueSeverity.ERROR,
                    path=manifest,
                )
            )

    display_name = _display_name(content) or manifest.stem
    description, details = _content_descriptions(content)
    if _display_name(content) is None and expected_tag == "Mod":
        issues.append(
            CatalogIssue(
                code="missing_display_name",
                message="Mod manifest has no non-empty DisplayName",
                severity=IssueSeverity.ERROR,
                path=manifest,
                content_id=content_id,
            )
        )

    has_cam = expected_tag == "Mod" and any(
        _local_name(node.tag) == "CAM" for node in content.iter()
    )
    kind = (
        CatalogKind.QUEST
        if expected_tag == "Quest"
        else (CatalogKind.MERGE if has_cam else CatalogKind.STANDARD)
    )
    generated = _is_generated_package(candidate.package_root)
    tool_delivery = _is_tool_delivery(content_id, content)
    merge_ready = False
    compatibility_applied = False
    if generated:
        issues.append(
            CatalogIssue(
                code="generated_output",
                message="manager-generated content is an output, not a selectable source",
                severity=IssueSeverity.INFO,
                path=candidate.package_root,
                content_id=content_id,
            )
        )
    elif tool_delivery:
        issues.append(
            CatalogIssue(
                code=TOOL_DELIVERY_ISSUE_CODE,
                message=(
                    "This Workshop-style package only delivers a modding tool and "
                    "changes nothing in-game; it should not be enabled as a Mod."
                ),
                severity=IssueSeverity.INFO,
                path=manifest,
                content_id=content_id,
            )
        )
    elif kind is CatalogKind.MERGE and multiple_mod_elements:
        issues.append(
            CatalogIssue(
                code="multi_mod_merge_manifest",
                message=(
                    "A CAM-changing Mod must be the only Mod element in its "
                    "manifest before it can be combined safely."
                ),
                severity=IssueSeverity.ERROR,
                path=manifest,
                content_id=content_id,
            )
        )
    elif kind is CatalogKind.MERGE and content_id is not None:
        merge_ready, compatibility_applied, definition_issues = _merge_readiness(
            candidate.package_root, content_id, compatibility
        )
        issues.extend(definition_issues)
        if merge_ready and merge_preflight is not None:
            try:
                deep_issues = tuple(
                    merge_preflight(content_id, display_name, candidate.package_root)
                )
            except Exception as exc:  # Application callback boundary.
                deep_issues = (
                    CatalogIssue(
                        code="merge_preflight_error",
                        message=f"deep compatibility check failed: {exc}",
                        severity=IssueSeverity.ERROR,
                        path=candidate.package_root,
                        content_id=content_id,
                    ),
                )
            issues.extend(deep_issues)
            if any(
                issue.severity is IssueSeverity.ERROR for issue in deep_issues
            ):
                merge_ready = False

    return CatalogEntry(
        content_id=content_id,
        raw_content_id=raw_content_id,
        display_name=display_name,
        kind=kind,
        source=candidate.source,
        package_root=candidate.package_root,
        manifest_path=manifest,
        has_cam=has_cam,
        merge_ready=merge_ready,
        compatibility_applied=compatibility_applied,
        generated=generated,
        issues=tuple(_attach_content_id(issues, content_id)),
        description=description,
        details=details,
        content_definitions=(
            _content_definition_fingerprints(content, candidate.package_root)
            if kind is CatalogKind.STANDARD
            else ()
        ),
    )


def _invalid_entry(
    candidate: _Candidate, kind: CatalogKind, issues: Sequence[CatalogIssue]
) -> CatalogEntry:
    generated = _is_generated_package(candidate.package_root)
    combined_issues = list(issues)
    if generated:
        combined_issues.append(
            CatalogIssue(
                code="generated_output",
                message="manager-generated content is an output, not a selectable source",
                severity=IssueSeverity.INFO,
                path=candidate.package_root,
            )
        )
    return CatalogEntry(
        content_id=None,
        raw_content_id=None,
        display_name=candidate.manifest_path.stem,
        kind=kind,
        source=candidate.source,
        package_root=candidate.package_root,
        manifest_path=candidate.manifest_path,
        has_cam=False,
        merge_ready=False,
        generated=generated,
        issues=tuple(combined_issues),
    )


def _display_name(content: ET.Element) -> Optional[str]:
    display_names = [
        child
        for child in list(content)
        if _local_name(child.tag) == "DisplayName" and _element_text(child)
    ]
    for child in display_names:
        language = (_clean_text(child.get("lang")) or "").replace("-", "_").casefold()
        if language == "en_us":
            return _element_text(child)
    if display_names:
        return _element_text(display_names[0])
    if _local_name(content.tag) == "Quest":
        for child in list(content):
            if _local_name(child.tag) == "Name" and _element_text(child):
                return _element_text(child)
    return None


def _content_descriptions(content: ET.Element) -> Tuple[Optional[str], Optional[str]]:
    """Return distinct author Short/Long text without blending it into diagnostics."""

    descendants = tuple(content.iter())

    def localized(tag_name: str) -> Optional[str]:
        candidates = [
            node
            for node in descendants
            if node is not content
            and _local_name(node.tag) == tag_name
            and _element_text(node)
        ]
        for node in candidates:
            language = (_clean_text(node.get("lang")) or "").replace(
                "-", "_"
            ).casefold()
            if language == "en_us":
                return _element_text(node)
        return _element_text(candidates[0]) if candidates else None

    short = localized("Short")
    long = localized("Long")
    if short is not None or long is not None:
        return short or long, long

    # A leaf Description is also valid author text. A container Description
    # with nested Short/Long nodes was handled above and must not be flattened.
    descriptions = [
        node
        for node in descendants
        if node is not content
        and _local_name(node.tag) == "Description"
        and not list(node)
        and _element_text(node)
    ]
    for node in descriptions:
        language = (_clean_text(node.get("lang")) or "").replace(
            "-", "_"
        ).casefold()
        if language == "en_us":
            return _element_text(node), None
    if descriptions:
        return _element_text(descriptions[0]), None
    return None, None


def _annotate_mod_collection(
    candidate: _Candidate,
    entries: Tuple[CatalogEntry, ...],
    content_nodes: Tuple[ET.Element, ...],
) -> Tuple[CatalogEntry, ...]:
    """Describe and conflict-check the independent Mods in one manifest.

    A shared manifest is only a visual collection.  Two options become
    mutually exclusive when their declared load resources overlap, including
    conventional numbered/versioned alternatives such as ``Attributes_v1`` /
    ``Attributes_v2``.  Independent toggles in the same Workshop item remain
    combinable.
    """

    if len(entries) != len(content_nodes):
        return entries
    collection_name = _collection_name(
        tuple(entry.display_name for entry in entries),
        candidate.manifest_path.stem,
    )
    collection_id = (
        f"{candidate.source.value}:"
        f"{candidate.manifest_path.resolve(strict=False).as_posix().casefold()}"
    )
    resource_keys = tuple(_declared_load_resource_keys(node) for node in content_nodes)
    conflicts: list[set[int]] = [set() for _entry in entries]
    for left in range(len(entries)):
        for right in range(left + 1, len(entries)):
            if resource_keys[left].intersection(resource_keys[right]):
                conflicts[left].add(right)
                conflicts[right].add(left)

    result = []
    for index, entry in enumerate(entries):
        conflict_entries = tuple(
            entries[other]
            for other in sorted(conflicts[index])
            if entries[other].content_id is not None
        )
        result.append(
            replace(
                entry,
                collection_id=collection_id,
                collection_name=collection_name,
                collection_index=index,
                collection_size=len(entries),
                variant_label=_variant_label(entry.display_name, collection_name),
                incompatible_ids=tuple(
                    item.content_id for item in conflict_entries if item.content_id
                ),
                incompatible_names=tuple(item.display_name for item in conflict_entries),
            )
        )
    return tuple(result)


def _collection_name(names: Tuple[str, ...], fallback: str) -> str:
    if not names:
        return fallback
    prefix_words = names[0].split()
    for name in names[1:]:
        words = name.split()
        limit = min(len(prefix_words), len(words))
        index = 0
        while (
            index < limit
            and prefix_words[index].casefold() == words[index].casefold()
        ):
            index += 1
        prefix_words = prefix_words[:index]
        if not prefix_words:
            break
    cleaned = " ".join(prefix_words).rstrip(" \t-:+/([{")
    if len(cleaned) < 3:
        return fallback
    return cleaned


def _variant_label(display_name: str, collection_name: str) -> str:
    if display_name.casefold() == collection_name.casefold():
        return "Main version"
    if display_name.casefold().startswith(collection_name.casefold()):
        suffix = display_name[len(collection_name):].lstrip(" \t-:+/([{ ")
        if suffix:
            return suffix
    return display_name


def _declared_load_resource_keys(content: ET.Element) -> frozenset[str]:
    keys: set[str] = set()
    for load in content.iter():
        if _local_name(load.tag) != "Load":
            continue
        for resource in list(load):
            kind = _local_name(resource.tag).casefold()
            target = next(
                (
                    child
                    for child in list(resource)
                    if _local_name(child.tag) == "Target" and _element_text(child)
                ),
                None,
            )
            raw_path = _element_text(target) if target is not None else _element_text(resource)
            if not raw_path:
                continue
            normalized = re.sub(r"/+", "/", raw_path.replace("\\", "/")).casefold()
            keys.add(f"{kind}:{normalized}")
            path = normalized.rsplit("/", 1)
            directory = path[0] + "/" if len(path) == 2 else ""
            filename = path[-1]
            stem, dot, extension = filename.rpartition(".")
            if not dot:
                stem, extension = filename, ""
            family = re.sub(
                r"(?:[_ -]?(?:version|ver|v)?\d+)$",
                "",
                stem,
                flags=re.IGNORECASE,
            ).rstrip("_ -")
            if family:
                family_path = directory + family + (("." + extension) if extension else "")
                keys.add(f"{kind}:variant-family:{family_path}")
    return frozenset(keys)


_MAX_ANALYZED_CONTENT_BYTES = 16 * 1024 * 1024


def _content_definition_fingerprints(
    content: ET.Element,
    package_root: Path,
) -> Tuple[Tuple[str, str], ...]:
    """Inventory behavior-defining content without compiling or mutating it.

    Ordinary Majesty Mods are loaded independently, so the manager cannot
    semantically merge them.  It can still identify when two selected Mods
    replace the same GPL/DAT definition or XML description.  The inventory is
    created during the explicit content scan and then reused by checkbox
    changes; no package files are reread on selection.
    """

    definitions: dict[str, str] = {}
    for load in content.iter():
        if _local_name(load.tag) != "Load":
            continue
        for resource in list(load):
            kind = _local_name(resource.tag).casefold()
            if kind == "gpl":
                for path in _gpl_analysis_sources(resource, package_root):
                    for key, digest in _semantic_file_definitions(path):
                        definitions[key] = digest
            elif kind == "descriptions":
                path = _safe_declared_package_file(package_root, _element_text(resource))
                if path is None:
                    continue
                raw = _read_analysis_bytes(path)
                if raw is None or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                    continue
                try:
                    root = ET.fromstring(raw)
                except ET.ParseError:
                    continue
                for child in list(root):
                    key = _description_definition_key(child)
                    if key is not None:
                        definitions[key] = _xml_digest(child)
    return tuple(sorted(definitions.items()))


def _gpl_analysis_sources(resource: ET.Element, package_root: Path) -> Tuple[Path, ...]:
    declared = []
    for source in list(resource):
        if _local_name(source.tag) != "Source":
            continue
        path = _safe_declared_package_file(package_root, _element_text(source))
        if path is not None and path.suffix.casefold() in {".gpl", ".dat"}:
            declared.append(path)
    if declared:
        return tuple(declared)

    # Many historical Workshop Mods ship a precompiled BCD in the manifest
    # but retain their matching GPL source tree beside it.  That source is the
    # only available compatibility evidence, so inspect it conservatively.
    source_root = package_root / "GPL"
    try:
        candidates = sorted(
            (
                path
                for path in source_root.rglob("*")
                if path.is_file() and path.suffix.casefold() in {".gpl", ".dat"}
            ),
            key=lambda item: item.as_posix().casefold(),
        )
    except OSError:
        return ()
    result = []
    for candidate in candidates[:512]:
        try:
            relative = candidate.relative_to(package_root).as_posix()
        except ValueError:
            continue
        safe = _safe_declared_package_file(package_root, relative)
        if safe is not None:
            result.append(safe)
    return tuple(result)


def _semantic_file_definitions(path: Path) -> Tuple[Tuple[str, str], ...]:
    try:
        info = path.stat()
    except OSError:
        return ()
    return _semantic_file_definitions_cached(
        str(path.resolve(strict=False)), info.st_mtime_ns, info.st_size
    )


@lru_cache(maxsize=4096)
def _semantic_file_definitions_cached(
    path_text: str,
    _mtime_ns: int,
    _size: int,
) -> Tuple[Tuple[str, str], ...]:
    path = Path(path_text)
    text = _read_analysis_text(path)
    if text is None:
        return ()
    try:
        parsed = (
            parse_dat(text, str(path))
            if path.suffix.casefold() == ".dat"
            else parse_gpl(text, str(path))
            if path.suffix.casefold() == ".gpl"
            else None
        )
    except ValueError:
        parsed = None
    if parsed is None:
        return ()
    return tuple(
        (f"{item.kind.value}:{item.normalized_name}", _content_digest(item.text))
        for item in parsed.items
    )


def _safe_declared_package_file(
    package_root: Path,
    raw_path: Optional[str],
) -> Optional[Path]:
    if not raw_path:
        return None
    try:
        root = package_root.resolve(strict=True)
        path = (root / raw_path.replace("\\", "/")).resolve(strict=True)
        path.relative_to(root)
        if not path.is_file() or path.stat().st_size > _MAX_ANALYZED_CONTENT_BYTES:
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return path


def _read_analysis_bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_analysis_text(path: Path) -> Optional[str]:
    raw = _read_analysis_bytes(path)
    if raw is None:
        return None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _content_digest(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.replace("\r", "").split("\n"))
    return hashlib.sha256(normalized.strip().encode("utf-8")).hexdigest()


def _description_definition_key(element: ET.Element) -> Optional[str]:
    attributes = {key.casefold(): value for key, value in element.attrib.items()}
    identifier = attributes.get("id")
    if not identifier:
        return None
    type_name = attributes.get("type", "")
    subtype = attributes.get("subtype", "")
    return ":".join(
        (
            "description",
            _local_name(element.tag).casefold(),
            type_name.casefold(),
            subtype.casefold(),
            identifier.casefold(),
        )
    )


def _xml_digest(element: ET.Element) -> str:
    def canonical(node: ET.Element) -> object:
        return {
            "tag": _local_name(node.tag).casefold(),
            "attributes": sorted(
                (key.casefold(), value.strip()) for key, value in node.attrib.items()
            ),
            "text": (node.text or "").strip(),
            "children": [canonical(child) for child in list(node)],
        }

    payload = json.dumps(canonical(element), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_LOAD_ORDER_SENTENCE = re.compile(
    r"(?:\bload(?:ed|s|ing)?\b.{0,40}\b(?:before|after|first)\b|"
    r"\b(?:before|after|first)\b.{0,40}\bload(?:ed|s|ing)?\b|"
    r"\bload\s+order\b)",
    re.IGNORECASE,
)
_REQUIREMENT_SENTENCE = re.compile(
    r"\b(?:requires?|required|must\s+(?:have|use|load)|will\s+not\s+work\s+standalone)\b",
    re.IGNORECASE,
)
_INCOMPATIBILITY_SENTENCE = re.compile(
    r"\b(?:do\s+not\s+(?:combine|use)|incompatible\s+with|not\s+compatible\s+with|"
    r"cannot\s+be\s+used\s+with)\b",
    re.IGNORECASE,
)
_LOAD_AFTER_CURRENT = re.compile(
    r"(?:\bload\s+after\b|\bloaded\s+before\s+(?:this|it|the\s+patch)\b|"
    r"\bfirst\b.*\b(?:this|the)\s+patch\b.*\bafter\b)",
    re.IGNORECASE,
)
_LOAD_BEFORE_CURRENT = re.compile(
    r"(?:\bload\s+before\b|\bloaded\s+after\s+(?:this|it|the\s+patch)\b|"
    r"\b(?:this|the)\s+patch\b.*\bfirst\b)",
    re.IGNORECASE,
)
_LOAD_NAME_STOPWORDS = frozenset(
    {"a", "an", "and", "for", "mod", "of", "or", "patch", "the", "with"}
)


def _annotate_explicit_relationships(
    entries: Sequence[CatalogEntry],
) -> list[CatalogEntry]:
    """Resolve conservative dependency/order/conflict prose against installed Mods.

    Historical Workshop manifests have no dependency schema, but many authors
    wrote explicit sentences such as "load X before this patch". We accept
    only those strong direction phrases and only when one installed entry has
    the most specific matching display-name tokens. Ambiguous prose is left
    alone rather than guessed.
    """

    standard = tuple(
        entry
        for entry in entries
        if entry.kind is CatalogKind.STANDARD and entry.content_id is not None
    )
    after: dict[str, set[str]] = {entry.content_id: set() for entry in standard}
    before: dict[str, set[str]] = {entry.content_id: set() for entry in standard}
    required: dict[str, set[str]] = {entry.content_id: set() for entry in standard}
    incompatible: dict[str, set[str]] = {
        entry.content_id: set(entry.incompatible_ids) for entry in standard
    }
    by_id = {entry.content_id: entry for entry in standard}

    for entry in standard:
        text = " ".join(
            value for value in (entry.description, entry.details) if value
        )
        if not text:
            continue
        text = re.sub(r"\s+", " ", text).strip()
        sentences = tuple(
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", text)
            if part.strip()
        )
        for sentence in sentences:
            if _INCOMPATIBILITY_SENTENCE.search(sentence):
                for target in _match_relationship_targets(entry, sentence, standard):
                    if target.content_id is None:
                        continue
                    incompatible[entry.content_id].add(target.content_id)
                    incompatible[target.content_id].add(entry.content_id)

            if not _LOAD_ORDER_SENTENCE.search(sentence):
                continue
            relation = (
                "after"
                if _LOAD_AFTER_CURRENT.search(sentence)
                else "before"
                if _LOAD_BEFORE_CURRENT.search(sentence)
                else None
            )
            if relation is None:
                continue
            target = _match_load_order_target(entry, sentence, standard)
            if target is None or target.content_id is None:
                continue
            if relation == "after":
                after[entry.content_id].add(target.content_id)
                before[target.content_id].add(entry.content_id)
                if (
                    _REQUIREMENT_SENTENCE.search(sentence)
                    or "patch" in entry.display_name.casefold()
                ):
                    required[entry.content_id].add(target.content_id)
            else:
                before[entry.content_id].add(target.content_id)
                after[target.content_id].add(entry.content_id)

    result = []
    for entry in entries:
        if entry.content_id not in by_id:
            result.append(entry)
            continue
        after_ids = tuple(
            sorted(
                after[entry.content_id],
                key=lambda item: (by_id[item].display_name.casefold(), item),
            )
        )
        before_ids = tuple(
            sorted(
                before[entry.content_id],
                key=lambda item: (by_id[item].display_name.casefold(), item),
            )
        )
        required_ids = tuple(
            sorted(
                required[entry.content_id],
                key=lambda item: (by_id[item].display_name.casefold(), item),
            )
        )
        incompatible_ids = tuple(
            sorted(
                incompatible[entry.content_id],
                key=lambda item: (by_id[item].display_name.casefold(), item),
            )
        )
        result.append(
            replace(
                entry,
                load_after_ids=after_ids,
                load_after_names=tuple(by_id[item].display_name for item in after_ids),
                load_before_ids=before_ids,
                load_before_names=tuple(by_id[item].display_name for item in before_ids),
                required_ids=required_ids,
                required_names=tuple(by_id[item].display_name for item in required_ids),
                incompatible_ids=incompatible_ids,
                incompatible_names=tuple(
                    by_id[item].display_name for item in incompatible_ids
                ),
            )
        )
    return result


def _annotate_standard_content_overlaps(
    entries: Sequence[CatalogEntry],
) -> list[CatalogEntry]:
    """Mark divergent standard-Mod definitions which lack a known safe order."""

    standard = tuple(
        entry
        for entry in entries
        if entry.kind is CatalogKind.STANDARD and entry.content_id is not None
    )
    by_id = {entry.content_id: entry for entry in standard}
    definitions = {
        entry.content_id: dict(entry.content_definitions) for entry in standard
    }
    unresolved: dict[str, set[str]] = {entry.content_id: set() for entry in standard}
    after: dict[str, set[str]] = {
        entry.content_id: set(entry.load_after_ids) for entry in standard
    }
    before: dict[str, set[str]] = {
        entry.content_id: set(entry.load_before_ids) for entry in standard
    }

    for left_index, left in enumerate(standard):
        left_definitions = definitions[left.content_id]
        if not left_definitions:
            continue
        for right in standard[left_index + 1 :]:
            right_definitions = definitions[right.content_id]
            shared = set(left_definitions).intersection(right_definitions)
            if not any(
                left_definitions[key] != right_definitions[key] for key in shared
            ):
                continue
            already_ordered = (
                right.content_id in after[left.content_id]
                or left.content_id in after[right.content_id]
            )
            if already_ordered:
                continue
            if left.manifest_path == right.manifest_path:
                first, second = sorted(
                    (left, right), key=lambda item: item.collection_index
                )
                after[second.content_id].add(first.content_id)
                before[first.content_id].add(second.content_id)
                continue
            unresolved[left.content_id].add(right.content_id)
            unresolved[right.content_id].add(left.content_id)

    result = []
    for entry in entries:
        if entry.content_id not in by_id:
            result.append(entry)
            continue
        after_ids = tuple(
            sorted(after[entry.content_id], key=lambda item: (by_id[item].display_name.casefold(), item))
        )
        before_ids = tuple(
            sorted(before[entry.content_id], key=lambda item: (by_id[item].display_name.casefold(), item))
        )
        overlap_ids = tuple(
            sorted(
                unresolved[entry.content_id],
                key=lambda item: (by_id[item].display_name.casefold(), item),
            )
        )
        result.append(
            replace(
                entry,
                load_after_ids=after_ids,
                load_after_names=tuple(by_id[item].display_name for item in after_ids),
                load_before_ids=before_ids,
                load_before_names=tuple(by_id[item].display_name for item in before_ids),
                unresolved_overlap_ids=overlap_ids,
                unresolved_overlap_names=tuple(
                    by_id[item].display_name for item in overlap_ids
                ),
            )
        )
    return result


def _match_load_order_target(
    current: CatalogEntry,
    sentence: str,
    candidates: Sequence[CatalogEntry],
) -> Optional[CatalogEntry]:
    matches = [
        (score, len(candidate.display_name), candidate)
        for score, candidate in _scored_relationship_targets(
            current, sentence, candidates
        )
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].display_name.casefold(),
            item[2].content_id or "",
        )
    )
    best = matches[0]
    if len(matches) > 1 and matches[1][:2] == best[:2]:
        return None
    return best[2]


def _match_relationship_targets(
    current: CatalogEntry,
    sentence: str,
    candidates: Sequence[CatalogEntry],
) -> Tuple[CatalogEntry, ...]:
    """Return every unambiguous installed Mod named by one relationship sentence."""

    scored = _scored_relationship_targets(current, sentence, candidates)
    return tuple(
        candidate
        for _score, candidate in sorted(
            scored,
            key=lambda item: (
                item[1].display_name.casefold(),
                item[1].content_id or "",
            ),
        )
    )


def _scored_relationship_targets(
    current: CatalogEntry,
    sentence: str,
    candidates: Sequence[CatalogEntry],
) -> list[tuple[int, CatalogEntry]]:
    sentence_tokens = _load_name_tokens(sentence)
    matches: list[tuple[int, CatalogEntry]] = []
    for candidate in candidates:
        if candidate.content_id == current.content_id:
            continue
        token_options = [_load_name_tokens(candidate.display_name)]
        if candidate.variant_label:
            token_options.append(_load_name_tokens(candidate.variant_label))
        matching = [
            tokens
            for tokens in token_options
            if len(tokens) >= 2 and tokens.issubset(sentence_tokens)
        ]
        if not matching:
            continue
        matches.append((max(len(tokens) for tokens in matching), candidate))
    return matches


def _load_name_tokens(value: str) -> frozenset[str]:
    normalized = value.casefold()
    normalized = re.sub(r"\bmisc\b", "miscellaneous", normalized)
    normalized = re.sub(r"\bversion\s*(\d+)\b", r"v\1", normalized)
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if token not in _LOAD_NAME_STOPWORDS
    )


def _is_tool_delivery(content_id: Optional[str], content: ET.Element) -> bool:
    """Recognize explicit non-gameplay delivery metadata without guessing.

    Some Workshop subscriptions intentionally ship an executable tool inside a
    valid Mod package and tell players not to enable it.  UUID recognition
    keeps known tools stable if their copy changes; narrowly worded metadata
    phrases cover equivalent packages.  The absence of gameplay load
    directives alone is deliberately *not* evidence that a Mod is a tool.
    """

    if content_id in _KNOWN_TOOL_DELIVERY_IDS:
        return True
    searchable = _normalize_metadata_text(" ".join(_manifest_metadata(content)))
    return any(phrase in searchable for phrase in _TOOL_DELIVERY_PHRASES)


def _manifest_metadata(content: ET.Element) -> Tuple[str, ...]:
    values = []
    for node in content.iter():
        if _local_name(node.tag) not in {"DisplayName", "Short", "Long"}:
            continue
        text = _element_text(node)
        if text:
            values.append(text)
    return tuple(values)


def _normalize_metadata_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _merge_readiness(
    package_root: Path,
    content_id: str,
    compatibility: Optional[CompatibilityResolver],
) -> Tuple[bool, bool, list[CatalogIssue]]:
    issues = []
    compatibility_ready = False
    if compatibility is not None:
        try:
            compatibility_ready = _compatibility_matches(
                compatibility, content_id, package_root
            )
        except Exception as exc:  # Catalog callbacks are an application boundary.
            issues.append(
                CatalogIssue(
                    code="compatibility_lookup_error",
                    message=f"compatibility lookup failed: {exc}",
                    severity=IssueSeverity.ERROR,
                    path=package_root,
                    content_id=content_id,
                )
            )

    definition_path = package_root / DEFINITION_FILE_NAME
    if not definition_path.is_file():
        if compatibility_ready:
            return True, True, issues
        issues.append(
            CatalogIssue(
                code="missing_merge_definition",
                message=f"CAM mod is missing required {DEFINITION_FILE_NAME}",
                severity=IssueSeverity.ERROR,
                path=package_root,
                content_id=content_id,
            )
        )
        return False, False, issues

    try:
        definition = load_mod_definition(definition_path)
        definition_id = normalize_content_id(definition.mod_id)
        if definition_id != content_id:
            raise PackageFormatError(
                f"definition Mod id {definition_id} does not match manifest id {content_id}"
            )
    except (PackageFormatError, ValueError) as exc:
        if compatibility_ready:
            issues.append(
                CatalogIssue(
                    code="packaged_merge_definition_ignored",
                    message=f"manager compatibility replaces invalid packaged definition: {exc}",
                    severity=IssueSeverity.WARNING,
                    path=definition_path,
                    content_id=content_id,
                )
            )
            return True, True, issues
        issues.append(
            CatalogIssue(
                code="invalid_merge_definition",
                message=f"invalid {DEFINITION_FILE_NAME}: {exc}",
                severity=IssueSeverity.ERROR,
                path=definition_path,
                content_id=content_id,
            )
        )
        return False, False, issues
    if definition.schema_version == 1:
        if compatibility_ready:
            return True, True, issues
        issues.append(
            CatalogIssue(
                code="legacy_merge_definition_requires_adapter",
                message=(
                    "schema-version 1 mod-definition.json cannot declare the "
                    "runtime features required for safe combining; this mod needs "
                    "a trusted manager compatibility adapter or a newer definition "
                    "(new packages should use schema version 3)"
                ),
                severity=IssueSeverity.ERROR,
                path=definition_path,
                content_id=content_id,
            )
        )
        return False, False, issues
    reserved_capabilities = sorted(
        set(definition.runtime_capabilities) & DERIVED_RUNTIME_CAPABILITIES
    )
    if reserved_capabilities:
        if compatibility_ready:
            issues.append(
                CatalogIssue(
                    code="packaged_merge_definition_ignored",
                    message=(
                        "manager compatibility replaces a packaged definition "
                        "that declares manager-derived runtime features: "
                        + ", ".join(reserved_capabilities)
                    ),
                    severity=IssueSeverity.WARNING,
                    path=definition_path,
                    content_id=content_id,
                )
            )
            return True, True, issues
        issues.append(
            CatalogIssue(
                code="reserved_runtime_capability",
                message=(
                    "mod-definition.json declares runtime features that only "
                    "the manager may derive from inspected content: "
                    + ", ".join(reserved_capabilities)
                ),
                severity=IssueSeverity.ERROR,
                path=definition_path,
                content_id=content_id,
            )
        )
        return False, False, issues
    unknown_capabilities = sorted(
        set(definition.runtime_capabilities) - SUPPORTED_RUNTIME_CAPABILITIES
    )
    if unknown_capabilities:
        issues.append(
            CatalogIssue(
                code="unsupported_runtime_capability",
                message=(
                    "mod-definition.json requests runtime features this manager "
                    "does not support: " + ", ".join(unknown_capabilities)
                ),
                severity=IssueSeverity.ERROR,
                path=definition_path,
                content_id=content_id,
            )
        )
        return False, False, issues
    return True, False, issues


def _compatibility_matches(
    compatibility: CompatibilityResolver, content_id: str, package_root: Path
) -> bool:
    if callable(compatibility):
        return bool(compatibility(content_id, package_root))
    for raw_id in compatibility.keys():
        try:
            if normalize_content_id(raw_id) == content_id:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _deduplicate_entries(
    entries: Sequence[CatalogEntry],
) -> Tuple[list[CatalogEntry], list[CatalogIssue]]:
    by_id = {}
    without_ids = []
    for entry in entries:
        if entry.content_id is None:
            without_ids.append(entry)
        else:
            by_id.setdefault(entry.content_id, []).append(entry)

    kept = list(without_ids)
    duplicate_issues = []
    for content_id in sorted(by_id):
        group = sorted(by_id[content_id], key=_duplicate_precedence)
        winner = group[0]
        if len(group) > 1:
            paths = ", ".join(str(entry.manifest_path) for entry in group)
            issue = CatalogIssue(
                code="duplicate_content_id",
                message=f"content UUID is installed more than once: {paths}",
                severity=IssueSeverity.ERROR,
                path=winner.manifest_path,
                content_id=content_id,
            )
            winner = replace(winner, issues=winner.issues + (issue,))
            duplicate_issues.append(issue)
        kept.append(winner)
    return kept, duplicate_issues


def _is_generated_package(package_root: Path) -> bool:
    if package_root.name.casefold().startswith(
        (".manager-merged-", ".majestymodmanager-build-")
    ):
        return True
    try:
        generated_names = {
            "cam-merge-report.json",
            ".majesty-mod-manager-owned.json",
        }
        return any(
            path.is_file() and path.name.casefold() in generated_names
            for path in package_root.iterdir()
        )
    except OSError:
        return False


def _attach_content_id(
    issues: Sequence[CatalogIssue], content_id: Optional[str]
) -> list[CatalogIssue]:
    return [
        issue
        if issue.content_id is not None or content_id is None
        else replace(issue, content_id=content_id)
        for issue in issues
    ]


def _unique_issues(issues: Sequence[CatalogIssue]) -> list[CatalogIssue]:
    result = []
    seen = set()
    for issue in issues:
        key = (
            issue.code,
            issue.message,
            issue.severity.value,
            str(issue.path).casefold() if issue.path is not None else "",
            issue.content_id or "",
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _candidate_sort_key(candidate: _Candidate) -> tuple:
    return (
        _source_rank(candidate.source),
        str(candidate.package_root).casefold(),
        candidate.manifest_path.name.casefold(),
    )


def _duplicate_precedence(entry: CatalogEntry) -> tuple:
    return (
        _source_rank(entry.source),
        1 if entry.generated else 0,
        str(entry.manifest_path).casefold(),
    )


def _entry_sort_key(entry: CatalogEntry) -> tuple:
    kind_rank = {
        CatalogKind.STANDARD: 0,
        CatalogKind.QUEST: 1,
        CatalogKind.MERGE: 2,
    }[entry.kind]
    has_error = any(issue.severity is IssueSeverity.ERROR for issue in entry.issues)
    problem_rank = (
        2
        if entry.kind is CatalogKind.STANDARD and entry.tool_delivery
        else 1
        if has_error or (entry.kind is CatalogKind.MERGE and not entry.merge_ready)
        else 0
    )
    return (
        kind_rank,
        # Ready content stays alphabetical first. Items which need attention
        # follow alphabetically, with non-gameplay tool deliveries last.
        problem_rank,
        entry.display_name.casefold(),
        entry.content_id or "",
        str(entry.manifest_path).casefold(),
    )


def _published_file_id_from_path(package_root: Path) -> Optional[str]:
    """Read a canonical nonzero uint64 PublishedFileId from a package path."""

    candidate = package_root.name
    if re.fullmatch(r"[1-9][0-9]{0,19}", candidate) is None:
        return None
    if int(candidate) > (2**64 - 1):
        return None
    return candidate


def _issue_sort_key(issue: CatalogIssue) -> tuple:
    severity_rank = {
        IssueSeverity.ERROR: 0,
        IssueSeverity.WARNING: 1,
        IssueSeverity.INFO: 2,
    }[issue.severity]
    return (
        severity_rank,
        issue.code,
        issue.content_id or "",
        str(issue.path).casefold() if issue.path is not None else "",
        issue.message,
    )


def _source_rank(source: CatalogSource) -> int:
    return {
        CatalogSource.LOCAL_MODS: 0,
        CatalogSource.LOCAL_QUESTS: 1,
        CatalogSource.WORKSHOP: 2,
    }[source]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = [
    "Catalog",
    "CatalogEntry",
    "CatalogIssue",
    "CatalogKind",
    "CatalogSource",
    "CompatibilityResolver",
    "IssueSeverity",
    "MAJESTY_SCRIPT_MERGER_ID",
    "MergePreflightCallback",
    "TOOL_DELIVERY_ISSUE_CODE",
    "normalize_content_id",
    "scan_catalog",
]
