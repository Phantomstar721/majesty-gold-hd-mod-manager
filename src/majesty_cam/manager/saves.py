"""Update saves to the mods the Manager launches, written as new copies.

Majesty pins the mods a save may load in the save's ``SVGD`` descriptor:
``SVGD``, a u32 payload length, a u32 revision, a u32 zero, then the payload,
which ends exactly at the ``MAP `` chunk tag.  The payload ends with the mod
list: after a ``Rel@`` marker come the custom-quest UUID, a u32 mod count and
one record per mod, the 16-byte Windows-layout GUID followed by the mod's
NUL-terminated display name.  Revision 10 descriptors end at ``Rel@`` and
carry no list.

A save stores no mod content.  Every load reads the listed mods from disk and
rebinds saved script state by name, and the game refuses a save whose listed
mods are not all installed.  A save made before the player selected more mods
can therefore follow the current selection by rewriting this list alone.

Updates only ever add mods: loading a saved game without a mod it was played
with is not safe, because the saved world can be rebuilt as if its quest had
just started.  Each update is written as a new file beside the original, only
for saves the player selects; the original is never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import itertools
import json
import os
from pathlib import Path
import re
import struct
from typing import Iterable, Mapping, Optional, Sequence
import uuid

from ..compose import profile_mod_id
from ..scoped_output import SCOPES, scoped_mod_id
from .profile import ProfileFormatError, _atomic_write, normalize_guid


SAVE_DIRECTORY_NAME = "SaveGame"
SAVE_EXTENSION = ".gmp"
SHARED_SCOPE = "Any"
HISTORY_FILENAME = "prepared-builds.json"
HISTORY_SCHEMA_VERSION = 1
HISTORY_LIMIT = 64
MAX_MOD_RECORDS = 64
MAX_PROOF_MEMBERS = 16
_HEAD_BYTES = 1 << 18
_DESCRIPTOR_TAG = b"SVGD"
_MAP_TAG = b"MAP "
_LIST_MARKER = b"Rel@"
_SUPPORTED_REVISION = 11
_LISTLESS_REVISION = 10
_UPDATED_SUFFIX = re.compile(r" \(updated(?: \d+)?\)$", re.IGNORECASE)
_TRAILING_MOD_ID = re.compile(r"([0-9a-f]{32})$", re.IGNORECASE)
_RULES = {"majesty": "original quest rules", "majestyexpansion": "expansion quest rules"}


class SaveFormatError(ValueError):
    """The file is not a save whose mod list can be read and rewritten."""


class SaveUpdateError(RuntimeError):
    """An updated copy could not be written; the original is unchanged."""


class SaveUpdateUnavailable(RuntimeError):
    """The current selection has no launchable profile to update saves to."""


# --------------------------------------------------------------------------
# The save's mod list


@dataclass(frozen=True)
class SaveModRecord:
    mod_id: str
    name_bytes: bytes
    start: int
    end: int

    @property
    def name(self) -> str:
        return self.name_bytes.decode("cp1252", errors="replace")


@dataclass(frozen=True)
class SaveModList:
    descriptor: int
    length: int
    revision: int
    count_offset: int
    list_end: int
    records: tuple[SaveModRecord, ...]
    save_name: str = ""
    quest_name: str = ""

    @property
    def mod_ids(self) -> tuple[str, ...]:
        return tuple(record.mod_id for record in self.records)


def _guid_text(raw: bytes) -> str:
    return str(uuid.UUID(bytes_le=raw)).upper()


def _guid_bytes(mod_id: str) -> bytes:
    return uuid.UUID(normalize_guid(mod_id)).bytes_le


def _cstring(data: bytes, start: int, limit: int) -> tuple[str, int]:
    end = data.find(b"\0", start, limit)
    if end < 0:
        return "", start
    return data[start:end].decode("cp1252", errors="replace"), end + 1


def _records_from(data: bytes, position: int, end: int) -> Optional[tuple[int, tuple[SaveModRecord, ...]]]:
    """(count offset, records) when a list starting here fills the payload exactly."""

    if position + 20 > end:
        return None
    count_offset = position + 16  # after the custom quest UUID
    (count,) = struct.unpack_from("<I", data, count_offset)
    if count > MAX_MOD_RECORDS:
        return None
    position = count_offset + 4
    records = []
    for _index in range(count):
        if position + 17 > end:
            return None
        name_end = data.find(b"\0", position + 16, end)
        if name_end < 0:
            return None
        records.append(SaveModRecord(_guid_text(data[position:position + 16]),
                                     data[position + 16:name_end], position, name_end + 1))
        position = name_end + 1
    if position != end:
        return None
    return count_offset, tuple(records)


def read_mod_list(data: bytes) -> SaveModList:
    """Parse the mod list, refusing any layout other than the decoded one."""

    descriptor = data.find(_DESCRIPTOR_TAG)
    if descriptor < 0 or descriptor + 16 > len(data):
        raise SaveFormatError("no save descriptor was found")
    length, revision, reserved = struct.unpack_from("<III", data, descriptor + 4)
    payload = descriptor + 16
    end = payload + length
    if reserved != 0 or data[end:end + len(_MAP_TAG)] != _MAP_TAG:
        raise SaveFormatError("the save descriptor does not end at the map data")
    if revision == _LISTLESS_REVISION and data[end - len(_LIST_MARKER):end] == _LIST_MARKER:
        raise SaveFormatError("this save was made without mods and has no mod list")
    if revision != _SUPPORTED_REVISION:
        raise SaveFormatError(f"unsupported save descriptor revision {revision}")
    # A player's save name may itself contain the marker: accept the marker
    # whose list fills the rest of the descriptor exactly.
    marker = data.find(_LIST_MARKER, payload, end)
    while marker >= 0:
        parsed = _records_from(data, marker + len(_LIST_MARKER), end)
        if parsed is not None:
            count_offset, records = parsed
            save_name, after = _cstring(data, payload, marker)
            quest_name, _after = _cstring(data, after, marker)
            return SaveModList(descriptor, length, revision, count_offset, end, records,
                               save_name, quest_name)
        marker = data.find(_LIST_MARKER, marker + 1, end)
    raise SaveFormatError("the save's mod list could not be read")


def rewrite_mod_list(data: bytes, mod_list: SaveModList, records: Sequence[tuple[str, bytes]]) -> bytes:
    """Replace the mod list with ``records`` (mod id, display-name bytes).

    Only the list and the descriptor length change.  The result is parsed
    again and every byte outside the list is compared with the original.
    """

    if len(records) > MAX_MOD_RECORDS:
        raise SaveFormatError(f"a save can list at most {MAX_MOD_RECORDS} mods")
    wanted = [(normalize_guid(mod_id), bytes(name)) for mod_id, name in records]
    if len({mod_id for mod_id, _name in wanted}) != len(wanted):
        raise SaveFormatError("a mod would be listed twice")
    encoded = bytearray(struct.pack("<I", len(wanted)))
    for mod_id, name in wanted:
        if b"\0" in name:
            raise SaveFormatError("a mod name cannot contain NUL")
        encoded += _guid_bytes(mod_id) + name + b"\0"
    old_size = mod_list.list_end - mod_list.count_offset
    result = bytearray(data[:mod_list.count_offset] + bytes(encoded) + data[mod_list.list_end:])
    struct.pack_into("<I", result, mod_list.descriptor + 4, mod_list.length + len(encoded) - old_size)
    result = bytes(result)
    check = read_mod_list(result)
    if [(record.mod_id, record.name_bytes) for record in check.records] != wanted:
        raise SaveFormatError("the rewritten mod list did not read back as written")
    length_at = mod_list.descriptor + 4
    if (result[:length_at] != data[:length_at]
            or result[length_at + 4:mod_list.count_offset] != data[length_at + 4:mod_list.count_offset]
            or result[check.list_end:] != data[mod_list.list_end:]):
        raise SaveFormatError("the rewrite changed data outside the mod list")
    return result


def read_save_head(path: Path) -> SaveModList:
    """Read just enough of a save to parse its mod list."""

    with path.open("rb") as stream:
        head = stream.read(_HEAD_BYTES)
        try:
            return read_mod_list(head)
        except SaveFormatError as exc:
            first_error = exc
        rest = stream.read()
    if not rest:
        raise first_error
    return read_mod_list(head + rest)


# --------------------------------------------------------------------------
# What the next launch runs


@dataclass(frozen=True)
class ModRef:
    mod_id: str
    name: str


@dataclass(frozen=True)
class KnownBuild:
    """A prepared Merge profile and the Merge mods it was built from."""

    mod_id: str
    members: tuple[ModRef, ...]
    parts: Mapping[str, str]
    label: Optional[str] = None


@dataclass(frozen=True)
class ContentOverlap:
    """A definition several selected mods change, from the merge report.

    ``retained`` lists the mods whose version was kept when the Manager had
    to choose; ``None`` means the changes were combined.
    """

    name: str
    dataset: str
    mod_ids: frozenset[str]
    retained: Optional[frozenset[str]] = None


@dataclass(frozen=True)
class UpdateTarget:
    """The mods the next launch runs, which an updated save must list."""

    standard: tuple[ModRef, ...]
    profile_parts: Mapping[str, ModRef]
    members: tuple[ModRef, ...]
    profile_slug: str
    installed: Mapping[str, str]
    datasets: Mapping[str, str]
    unit_types: Mapping[str, frozenset[str]]
    known_builds: Mapping[str, KnownBuild]
    overlaps: tuple[ContentOverlap, ...] = ()
    stock_unit_types: Optional[Mapping[str, frozenset[str]]] = None
    profile_display_name: str = "Majesty Mod Manager: Merged Profile"

    @property
    def profile_id(self) -> Optional[str]:
        part = self.profile_parts.get(SHARED_SCOPE)
        return part.mod_id if part is not None else None

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(member.mod_id for member in self.members)

    def name_of(self, mod_id: str) -> str:
        if mod_id in self.installed:
            return self.installed[mod_id]
        return next((member.name for member in self.members if member.mod_id == mod_id), mod_id)


def profile_part_ids(profile_id: str, generated_ids: Iterable[str]) -> dict[str, str]:
    """Map a generated profile's Mod records to the quest rules they serve."""

    main = normalize_guid(profile_id)
    generated = {normalize_guid(item) for item in generated_ids}
    parts = {SHARED_SCOPE: main}
    for scope in SCOPES:
        scoped = normalize_guid(scoped_mod_id(main, scope))
        if scoped in generated:
            parts[scope] = scoped
    return parts


# --------------------------------------------------------------------------
# Prepared-build history


def history_path(state_folder: Path) -> Path:
    return state_folder / HISTORY_FILENAME


def load_prepared_builds(path: Path) -> dict[str, KnownBuild]:
    """Profiles this Manager prepared before; unreadable history counts as none."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(value, dict) or value.get("schema_version") != HISTORY_SCHEMA_VERSION:
        return {}
    builds: dict[str, KnownBuild] = {}
    for row in value.get("builds", ()):
        try:
            mod_id = normalize_guid(row["mod_id"])
            members = tuple(ModRef(normalize_guid(item["mod_id"]), str(item["name"])) for item in row["members"])
            parts = {str(scope): normalize_guid(part) for scope, part in row["parts"].items()}
        except (KeyError, TypeError, AttributeError, ProfileFormatError):
            continue
        if parts.get(SHARED_SCOPE) == mod_id:
            builds[mod_id] = KnownBuild(mod_id=mod_id, members=members, parts=parts)
    return builds


def record_prepared_build(
    path: Path,
    *,
    profile_id: str,
    generated_ids: Iterable[str],
    members: Sequence[ModRef],
) -> None:
    """Remember which Merge mods a prepared profile holds, newest last."""

    mod_id = normalize_guid(profile_id)
    row = {
        "mod_id": mod_id,
        "parts": profile_part_ids(mod_id, generated_ids),
        "members": [{"mod_id": normalize_guid(item.mod_id), "name": item.name} for item in members],
    }
    rows: list = []
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        previous = None
    if isinstance(previous, dict) and previous.get("schema_version") == HISTORY_SCHEMA_VERSION:
        rows = [item for item in previous.get("builds", ())
                if isinstance(item, dict) and item.get("mod_id") != mod_id]
    rows.append(row)
    payload = {"schema_version": HISTORY_SCHEMA_VERSION, "builds": rows[-HISTORY_LIMIT:]}
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))


# --------------------------------------------------------------------------
# Reading the merge report


def report_overlaps(report: Mapping, names: Mapping[str, str]) -> tuple[ContentOverlap, ...]:
    """Definitions the merge report shows several selected mods changing.

    ``names`` maps display names to mod ids, for report rows that name their
    contributors instead of identifying them.
    """

    def owner_id(alias: object) -> Optional[str]:
        match = _TRAILING_MOD_ID.search(str(alias))
        return normalize_guid(match.group(1)) if match else None

    def ids_of(values) -> frozenset[str]:
        found = set()
        for value in values or ():
            try:
                found.add(normalize_guid(str(value)))
            except ProfileFormatError:
                continue
        return frozenset(found)

    if not isinstance(report, Mapping):
        return ()
    merge = report.get("merge")
    gpl = merge.get("gpl", {}) if isinstance(merge, Mapping) else {}
    overlaps = []
    seen = set()
    for row in (*gpl.get("instruction_merges", ()), *gpl.get("conflicts", ())):
        if not isinstance(row, Mapping):
            continue
        name = row.get("function") or row.get("name")
        owners = frozenset(filter(None, (owner_id(alias) for alias in row.get("owners", ()))))
        if name and len(owners) > 1 and (name, owners) not in seen:
            seen.add((name, owners))
            overlaps.append(ContentOverlap(name=str(name), dataset="any", mod_ids=owners))
    for section in ("mod_preferences", "xml_mod_preferences", "sound_mod_preferences"):
        for row in report.get(section) or ():
            if not isinstance(row, Mapping):
                continue
            contributors = frozenset(filter(None, (names.get(str(item)) for item in row.get("contributors", ()))))
            retained = ids_of(row.get("retained_mod_ids"))
            if len(contributors | retained) > 1:
                overlaps.append(ContentOverlap(
                    name=str(row.get("name") or "shared content"),
                    dataset=str(row.get("dataset", "any")).casefold(),
                    mod_ids=contributors | retained,
                    retained=retained,
                ))
    return tuple(overlaps)


# --------------------------------------------------------------------------
# Deciding what to do with each save


class SaveState(str, Enum):
    CURRENT = "current"
    UPDATABLE = "updatable"
    CAUTION = "caution"
    UPDATED = "updated"
    BLOCKED = "blocked"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class SaveUpdatePlan:
    path: Path
    state: SaveState
    summary: str
    details: tuple[str, ...] = ()
    cautions: tuple[str, ...] = ()
    save_name: str = ""
    quest_name: str = ""
    profile_label: Optional[str] = None
    original: tuple[tuple[str, bytes], ...] = ()
    records: tuple[tuple[str, bytes], ...] = ()

    @property
    def selectable(self) -> bool:
        return self.state in (SaveState.UPDATABLE, SaveState.CAUTION)


class MembershipProof:
    """Which Merge mods built a profile id: from history, or by recomputation.

    A profile's Mod id is a pure function of its ordered Merge members.  When
    recomputing it for a subset of the current members, in the current order,
    reproduces a save's profile id, that profile held exactly that subset, so
    everything it had is still selected.  Recomputation is used only when the
    same computation reproduces the current profile's own id.
    """

    def __init__(self, target: UpdateTarget):
        self.target = target
        members = target.member_ids
        self.enabled = (
            target.profile_id is not None
            and len(members) <= MAX_PROOF_MEMBERS
            and normalize_guid(profile_mod_id(members, target.profile_slug)) == target.profile_id
        )
        self._subsets: Optional[dict[str, tuple[str, ...]]] = None

    def members_of(self, profile_id: str) -> Optional[tuple[str, ...]]:
        if profile_id == self.target.profile_id:
            return self.target.member_ids
        known = self.target.known_builds.get(profile_id)
        if known is not None:
            return tuple(member.mod_id for member in known.members)
        if not self.enabled:
            return None
        if self._subsets is None:
            members = self.target.member_ids
            self._subsets = {}
            for size in range(len(members) + 1):
                for subset in itertools.combinations(members, size):
                    self._subsets[normalize_guid(profile_mod_id(subset, self.target.profile_slug))] = subset
        return self._subsets.get(profile_id)


def _names(target: UpdateTarget, mod_ids: Iterable[str]) -> str:
    return ", ".join(sorted({target.name_of(mod_id) for mod_id in mod_ids}, key=str.casefold))


def _display_bytes(name: str) -> bytes:
    return name.replace("\0", "").encode("cp1252", errors="replace")


def _known_parts(target: UpdateTarget) -> dict[str, str]:
    """Every profile record id this Manager knows -> the quest rules it serves."""

    known: dict[str, str] = {}
    for build in target.known_builds.values():
        for scope, part in build.parts.items():
            known[part] = scope
    for scope, part in target.profile_parts.items():
        known[part.mod_id] = scope
    return known


def _profile_entries(
    mod_list: SaveModList,
    target: UpdateTarget,
) -> tuple[Optional[str], dict[str, SaveModRecord], Optional[str]]:
    """(profile id, {scope: record}, problem) for the save's Merge profile."""

    known = _known_parts(target)
    name = target.profile_display_name
    scoped_names = {f"{name} ({scope} scripts)" for scope in SCOPES}
    mains = [r for r in mod_list.records if known.get(r.mod_id) == SHARED_SCOPE or r.name == name]
    if len(mains) > 1:
        return None, {}, "It lists more than one Merge profile."
    if not mains:
        if any(r.name in scoped_names or known.get(r.mod_id) in SCOPES for r in mod_list.records):
            return None, {}, "It lists Merge profile scripts without the profile they belong to."
        return None, {}, None
    main = mains[0]
    entries = {SHARED_SCOPE: main}
    expected = {normalize_guid(scoped_mod_id(main.mod_id, scope)): scope for scope in SCOPES}
    for record in mod_list.records:
        if record is main:
            continue
        if record.mod_id in expected:
            entries[expected[record.mod_id]] = record
        elif record.name in scoped_names or known.get(record.mod_id) in SCOPES:
            return None, {}, "Its Merge profile entries do not belong together."
    return main.mod_id, entries, None


def _save_dataset(
    mod_list: SaveModList,
    entries: Mapping[str, SaveModRecord],
    target: UpdateTarget,
) -> tuple[Optional[str], Optional[str]]:
    """(dataset, problem): the quest rules the save was played with, if evident.

    Majesty applies only mods for the quest's rules (or for any rules), so a
    listed profile scripts part or a rules-specific mod shows which they are.
    """

    found = {scope.casefold() for scope in entries if scope != SHARED_SCOPE}
    for record in mod_list.records:
        base = target.datasets.get(record.mod_id, "")
        if base in _RULES:
            found.add(base)
    if len(found) > 1:
        return None, "Its mods disagree about which quest rules it uses."
    return (next(iter(found)) if found else None), None


def _insert_position(final: Sequence[tuple[str, bytes]], mod_id: str, order: Sequence[str]) -> int:
    """Before the first listed mod the launch order puts after this one."""

    rank = {item: index for index, item in enumerate(order)}
    mine = rank.get(mod_id, len(order))
    for index, (other, _name) in enumerate(final):
        if rank.get(other, len(order)) > mine:
            return index
    return len(final)


def plan_save_update(
    path: Path,
    mod_list: SaveModList,
    target: UpdateTarget,
    *,
    proof: Optional[MembershipProof] = None,
) -> SaveUpdatePlan:
    """Decide whether this save can follow the current mods by additions only."""

    proof = proof or MembershipProof(target)
    common = dict(path=path, save_name=mod_list.save_name, quest_name=mod_list.quest_name,
                  original=tuple((record.mod_id, record.name_bytes) for record in mod_list.records))
    profile_id, entries, problem = _profile_entries(mod_list, target)
    if problem:
        return SaveUpdatePlan(state=SaveState.BLOCKED, summary=problem, **common)
    label = None
    if profile_id is not None:
        if profile_id == target.profile_id:
            label = "Current profile"
        elif profile_id in target.known_builds:
            label = target.known_builds[profile_id].label

    def blocked(reason: str, *more: str) -> SaveUpdatePlan:
        return SaveUpdatePlan(state=SaveState.BLOCKED, summary=reason, details=more,
                              profile_label=label, **common)

    member_ids = set(target.member_ids)
    standard_ids = [item.mod_id for item in target.standard]
    standard_set = set(standard_ids)
    profile_records = {record.mod_id for record in entries.values()}

    # 1. The Merge profile it was played with may only have gained mods.
    old_members: tuple[str, ...] = ()
    if profile_id is not None:
        if target.profile_id is None:
            return blocked("It uses a Merge profile, but your current selection launches without one.")
        old = proof.members_of(profile_id)
        if old is None:
            return blocked("It was played with a Merge profile this Manager cannot account for.",
                           "That profile may have held a mod you have since removed.")
        removed = [mod_id for mod_id in old if mod_id not in member_ids]
        moved = [mod_id for mod_id in removed if mod_id in standard_set]
        if moved:
            return blocked(f"{_names(target, moved)} moved from its Merge profile to Standard.",
                           "Merge mods can use Manager features that Standard mods do not get.")
        if removed:
            known = {m.mod_id: m.name for m in getattr(target.known_builds.get(profile_id), "members", ())}
            names = sorted((known.get(m) or target.name_of(m) for m in removed), key=str.casefold)
            return blocked("Its Merge profile had mods your current one does not: " + ", ".join(names) + ".")
        for scope in entries:
            if scope not in target.profile_parts:
                return blocked(f"The current Merge profile no longer has scripts for {_RULES[scope.casefold()]}.")
        old_members = tuple(old)

    # 2. Every other mod it lists must still be selected.
    dropped = []
    for record in mod_list.records:
        if record.mod_id in profile_records or record.mod_id in standard_set:
            continue
        if record.mod_id in member_ids:
            dropped.append(record)
        elif record.mod_id not in target.installed:
            return blocked(f"It uses {record.name or record.mod_id}, which is not installed.")
        else:
            return blocked(f"It uses {target.name_of(record.mod_id)}, which is not selected now.",
                           "It may belong to another profile, so it is left as it is.")
    dropped_ids = {record.mod_id for record in dropped}

    dataset, problem = _save_dataset(mod_list, entries, target)
    if problem:
        return blocked(problem)

    # 3. The updated list: listed mods keep their places.
    final: list[tuple[str, bytes]] = []
    for record in mod_list.records:
        if record.mod_id in dropped_ids:
            continue
        scope = next((scope for scope, item in entries.items() if item is record), None)
        if scope is None:
            final.append((record.mod_id, record.name_bytes))
        else:
            part = target.profile_parts[scope]
            final.append((part.mod_id, _display_bytes(part.name)))
    listed = {mod_id for mod_id, _name in final}
    added_standard = [item for item in target.standard if item.mod_id not in listed]
    launch_order = standard_ids + [part.mod_id for part in target.profile_parts.values()]
    for item in added_standard:
        final.insert(_insert_position(final, item.mod_id, launch_order),
                     (item.mod_id, _display_bytes(item.name)))
    for scope in (SHARED_SCOPE, *SCOPES):
        part = target.profile_parts.get(scope)
        if part is None or part.mod_id in {mod_id for mod_id, _name in final}:
            continue
        if scope != SHARED_SCOPE:
            if dataset is None:
                return blocked("It is not clear whether this save uses original or expansion quest rules.",
                               "The Merge profile has separate scripts for each, so the right one "
                               "cannot be chosen.")
            if scope.casefold() != dataset:
                continue
        final.append((part.mod_id, _display_bytes(part.name)))

    if [mod_id for mod_id, _name in final] == list(mod_list.mod_ids):
        return SaveUpdatePlan(state=SaveState.CURRENT, summary="Already uses your current mods.",
                              profile_label=label, **common)

    # 4. Describe the change, and flag what play has not proven.
    added_members = [m for m in target.member_ids if m not in old_members and m not in dropped_ids]
    gains_profile = profile_id is None and target.profile_id is not None
    lines = []
    if gains_profile:
        lines.append("Adds the Merge profile to a save played without one.")
    if added_members:
        lines.append("Adds to its Merge profile: " + _names(target, added_members) + ".")
    if added_standard:
        lines.append("Adds: " + _names(target, (item.mod_id for item in added_standard)) + ".")
    if dropped:
        lines.append("Now loads through the Merge profile: " + _names(target, dropped_ids) + ".")
    if not lines:
        lines.append("Points it at your rebuilt Merge profile.")

    added = set(added_members) | {item.mod_id for item in added_standard}
    kept = set(old_members) | dropped_ids | {m for m in mod_list.mod_ids if m in standard_set}
    cautions = _cautions(target, added, kept, dataset)
    if gains_profile and kept:
        cautions.append("The Merge profile's scripts may also change mods this save already uses.")
    return SaveUpdatePlan(
        state=SaveState.CAUTION if cautions else SaveState.UPDATABLE,
        summary=lines[0], details=tuple(lines[1:]), cautions=tuple(cautions),
        profile_label=label, records=tuple(final), **common)


def _cautions(target: UpdateTarget, added: set[str], kept: set[str], dataset: Optional[str]) -> list[str]:
    cautions = []
    stock = None
    if target.stock_unit_types is not None:
        stock = target.stock_unit_types.get(dataset or "majestyexpansion")
    kept_types: set[str] = set()
    for mod_id in kept:
        kept_types |= target.unit_types.get(mod_id, frozenset())
    for mod_id in sorted(added, key=lambda item: target.name_of(item).casefold()):
        types = set(target.unit_types.get(mod_id, frozenset())) - kept_types
        if stock is not None:
            types -= stock
        if types:
            verb = "adds" if stock is not None else "may add"
            cautions.append(f"{target.name_of(mod_id)} {verb} new unit or building types; adding those "
                            "to a game in progress has not been tested.")
    shared: dict[tuple[str, str], set[str]] = {}
    for overlap in target.overlaps:
        if dataset is not None and overlap.dataset in _RULES and overlap.dataset != dataset:
            continue
        for new in overlap.mod_ids & added:
            if overlap.retained is not None and new not in overlap.retained:
                continue
            for old in overlap.mod_ids & kept:
                shared.setdefault((new, old), set()).add(overlap.name)
    order = sorted(shared, key=lambda pair: (target.name_of(pair[0]).casefold(), target.name_of(pair[1]).casefold()))
    for new, old in order:
        names = sorted(shared[(new, old)], key=str.casefold)
        sample = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        cautions.append(f"{target.name_of(new)} changes content that {target.name_of(old)} "
                        f"also changes ({sample}).")
    return cautions


def _base_stem(path: Path) -> str:
    return _UPDATED_SUFFIX.sub("", path.stem)


def find_saves(folder: Path) -> tuple[Path, ...]:
    try:
        return tuple(sorted(
            (item for item in folder.iterdir()
             if item.suffix.casefold() == SAVE_EXTENSION and item.is_file()),
            key=lambda item: item.name.casefold()))
    except OSError:
        return ()


def plan_save_updates(folder: Path, target: UpdateTarget) -> tuple[SaveUpdatePlan, ...]:
    """One plan per save in ``folder``.  Nothing is written."""

    proof = MembershipProof(target)
    plans = []
    for path in find_saves(folder):
        try:
            mod_list = read_save_head(path)
        except (OSError, SaveFormatError) as exc:
            plans.append(SaveUpdatePlan(path=path, state=SaveState.UNREADABLE,
                                        summary=f"Its mod list cannot be read: {exc}."))
            continue
        plans.append(plan_save_update(path, mod_list, target, proof=proof))
    updated_copies = {}
    for plan in plans:
        if plan.state is SaveState.CURRENT and _UPDATED_SUFFIX.search(plan.path.stem):
            updated_copies.setdefault(_base_stem(plan.path).casefold(), plan.path)
    result = []
    for plan in plans:
        copy = updated_copies.get(_base_stem(plan.path).casefold())
        if plan.selectable and copy is not None:
            plan = SaveUpdatePlan(path=plan.path, state=SaveState.UPDATED,
                                  summary=f"Already updated as {copy.name}.", save_name=plan.save_name,
                                  quest_name=plan.quest_name, profile_label=plan.profile_label,
                                  original=plan.original)
        result.append(plan)
    return tuple(result)


# --------------------------------------------------------------------------
# Writing the copy


def updated_copy_path(original: Path) -> Path:
    stem = _base_stem(original)
    for number in itertools.count(1):
        label = " (updated)" if number == 1 else f" (updated {number})"
        candidate = original.with_name(stem + label + original.suffix)
        if not candidate.exists():
            return candidate
    raise AssertionError("unreachable")


def _publish_new_file(temporary: Path, destination: Path) -> None:
    if os.name == "nt":
        os.rename(temporary, destination)  # a Windows rename never replaces a file
    else:
        os.link(temporary, destination)  # fails when the destination exists
        os.unlink(temporary)


def write_updated_copy(plan: SaveUpdatePlan) -> Path:
    """Write the updated save beside the original and return its path.

    The original is read again and must still hold the mod list the plan was
    made from.  The copy gets a new name; no file is ever replaced.
    """

    if not plan.selectable or not plan.records:
        raise SaveUpdateError("This save has no update to write.")
    try:
        data = plan.path.read_bytes()
        mod_list = read_mod_list(data)
    except (OSError, SaveFormatError) as exc:
        raise SaveUpdateError(f"{plan.path.name} could not be read: {exc}") from exc
    if tuple((record.mod_id, record.name_bytes) for record in mod_list.records) != plan.original:
        raise SaveUpdateError(f"{plan.path.name} changed after the list was made. Refresh and try again.")
    try:
        updated = rewrite_mod_list(data, mod_list, plan.records)
    except SaveFormatError as exc:
        raise SaveUpdateError(f"{plan.path.name} could not be updated: {exc}") from exc
    temporary = plan.path.with_name(f".{plan.path.stem}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        for _attempt in range(100):
            destination = updated_copy_path(plan.path)
            try:
                _publish_new_file(temporary, destination)
            except FileExistsError:
                continue
            return destination
        raise SaveUpdateError("No free name was found for the updated copy.")
    except OSError as exc:
        raise SaveUpdateError(f"The updated copy of {plan.path.name} could not be written: {exc}") from exc
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


__all__ = [
    "ContentOverlap",
    "KnownBuild",
    "MembershipProof",
    "ModRef",
    "SAVE_DIRECTORY_NAME",
    "SaveFormatError",
    "SaveModList",
    "SaveModRecord",
    "SaveState",
    "SaveUpdateError",
    "SaveUpdatePlan",
    "SaveUpdateUnavailable",
    "SHARED_SCOPE",
    "UpdateTarget",
    "find_saves",
    "history_path",
    "load_prepared_builds",
    "plan_save_update",
    "plan_save_updates",
    "profile_part_ids",
    "read_mod_list",
    "read_save_head",
    "record_prepared_build",
    "report_overlaps",
    "rewrite_mod_list",
    "updated_copy_path",
    "write_updated_copy",
]
