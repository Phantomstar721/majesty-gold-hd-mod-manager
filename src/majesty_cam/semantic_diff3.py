from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence


@dataclass(frozen=True)
class DiffHunk:
    """One replacement of ``base[start:end]`` with ``replacement`` lines."""

    start: int
    end: int
    replacement: tuple[str, ...]


@dataclass(frozen=True)
class MergeRegionConflict:
    """One region where both inputs changed the same stock lines differently."""

    start: int
    end: int
    base: tuple[str, ...]
    left: tuple[str, ...]
    right: tuple[str, ...]
    output_start: int
    output_end: int


@dataclass(frozen=True)
class ThreeWayTextMerge:
    lines: tuple[str, ...]
    conflicts: tuple[MergeRegionConflict, ...]

    @property
    def clean(self) -> bool:
        return not self.conflicts


def split_logical_lines(text: str) -> tuple[str, ...]:
    """Return physical text as newline-free logical lines.

    Majesty's GPL compiler accepts either CRLF or LF.  Reconciliation uses
    logical lines and deliberately emits a single canonical trailing newline,
    which keeps conflict identities stable across packaging tools.
    """

    return tuple(text.splitlines())


def join_logical_lines(lines: Sequence[str]) -> str:
    return "\n".join(lines) + ("\n" if lines else "")


def diff_lines(base: Sequence[str], changed: Sequence[str]) -> tuple[DiffHunk, ...]:
    """Compute deterministic exact-line edits using a longest common subsequence.

    Weak anchors (blank lines, comments, and lone block keywords) are folded
    into their neighboring edits.  This is intentionally conservative for GPL:
    it is safer to ask about a larger conflict than to interleave two unrelated
    rewrites around a ubiquitous ``begin``/``end`` line.
    """

    # ``SequenceMatcher`` provides the same exact-line edit model without the
    # quadratic Python object matrix that made large legacy overhaul functions
    # take tens of seconds and hundreds of megabytes to compare.
    matcher = SequenceMatcher(a=tuple(base), b=tuple(changed), autojunk=False)
    hunks = [
        DiffHunk(left_start, left_end, tuple(changed[right_start:right_end]))
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes()
        if tag != "equal"
    ]

    index = 0
    while index + 1 < len(hunks):
        current = hunks[index]
        following = hunks[index + 1]
        anchors = base[current.end : following.start]
        if all(_weak_anchor(line) for line in anchors):
            hunks[index] = DiffHunk(
                current.start,
                following.end,
                (*current.replacement, *anchors, *following.replacement),
            )
            del hunks[index + 1]
        else:
            index += 1
    return tuple(hunks)


def merge_three_way(
    base: Sequence[str], left: Sequence[str], right: Sequence[str]
) -> ThreeWayTextMerge:
    """Merge two independently authored stock-relative versions.

    Non-overlapping edits are combined, identical overlapping edits collapse,
    and every genuinely divergent overlap is returned as structured data.  The
    provisional output uses the right side for a conflict so an N-way dry fold
    can continue deterministically; callers must never publish it while
    ``conflicts`` is non-empty.
    """

    left_hunks = diff_lines(base, left)
    right_hunks = diff_lines(base, right)
    left_index = 0
    right_index = 0
    position = 0
    output: list[str] = []
    conflicts: list[MergeRegionConflict] = []

    while True:
        next_left = (
            left_hunks[left_index].start
            if left_index < len(left_hunks)
            else None
        )
        next_right = (
            right_hunks[right_index].start
            if right_index < len(right_hunks)
            else None
        )
        if next_left is None and next_right is None:
            output.extend(base[position:])
            break
        next_start = min(
            value for value in (next_left, next_right) if value is not None
        )
        output.extend(base[position:next_start])

        cluster_start = next_start
        cluster_end = next_start
        cluster_left: list[DiffHunk] = []
        cluster_right: list[DiffHunk] = []
        seeded = False
        changed = True
        while changed:
            changed = False
            while left_index < len(left_hunks) and _cluster_accepts(
                cluster_start,
                cluster_end,
                left_hunks[left_index],
                not seeded,
            ):
                hunk = left_hunks[left_index]
                cluster_left.append(hunk)
                cluster_end = max(cluster_end, hunk.end)
                left_index += 1
                seeded = True
                changed = True
            while right_index < len(right_hunks) and _cluster_accepts(
                cluster_start,
                cluster_end,
                right_hunks[right_index],
                not seeded,
            ):
                hunk = right_hunks[right_index]
                cluster_right.append(hunk)
                cluster_end = max(cluster_end, hunk.end)
                right_index += 1
                seeded = True
                changed = True

        left_value = _apply_cluster(base, cluster_start, cluster_end, cluster_left)
        right_value = _apply_cluster(base, cluster_start, cluster_end, cluster_right)
        if not cluster_left:
            output.extend(right_value)
        elif not cluster_right:
            output.extend(left_value)
        elif left_value == right_value:
            output.extend(left_value)
        else:
            output_start = len(output)
            output.extend(right_value)
            conflicts.append(
                MergeRegionConflict(
                    start=cluster_start,
                    end=cluster_end,
                    base=tuple(base[cluster_start:cluster_end]),
                    left=left_value,
                    right=right_value,
                    output_start=output_start,
                    output_end=len(output),
                )
            )
        position = max(position, cluster_end)

    return ThreeWayTextMerge(tuple(output), tuple(conflicts))


def resolve_three_way_conflicts(
    result: ThreeWayTextMerge, choices: Sequence[str]
) -> tuple[str, ...]:
    """Replace conflict placeholders while retaining every clean merged hunk."""

    if len(choices) != len(result.conflicts):
        raise ValueError("one left/right/base choice is required per conflict")
    lines = list(result.lines)
    for conflict, choice in reversed(tuple(zip(result.conflicts, choices))):
        if choice == "left":
            replacement = conflict.left
        elif choice == "right":
            replacement = conflict.right
        elif choice == "base":
            replacement = conflict.base
        else:
            raise ValueError(f"unsupported three-way conflict choice: {choice!r}")
        lines[conflict.output_start : conflict.output_end] = replacement
    return tuple(lines)


def merge_text(base: str, left: str, right: str) -> tuple[str, ThreeWayTextMerge]:
    result = merge_three_way(
        split_logical_lines(base),
        split_logical_lines(left),
        split_logical_lines(right),
    )
    return join_logical_lines(result.lines), result


def _weak_anchor(line: str) -> bool:
    value = line.strip()
    lowered = value.casefold()
    return (
        not value
        or lowered in {"begin", "end", "else"}
        or value.startswith("//")
        or value.startswith("\\")
    )


def _ranges_overlap(left: DiffHunk, right: DiffHunk) -> bool:
    if left.start == left.end and right.start == right.end:
        return left.start == right.start
    if left.start == left.end:
        return right.start <= left.start < right.end
    if right.start == right.end:
        return left.start <= right.start < left.end
    return left.start < right.end and right.start < left.end


def _cluster_accepts(
    start: int, end: int, hunk: DiffHunk, seed: bool
) -> bool:
    if seed:
        return hunk.start == start
    return _ranges_overlap(DiffHunk(start, end, ()), hunk)


def _apply_cluster(
    base: Sequence[str], start: int, end: int, hunks: Sequence[DiffHunk]
) -> tuple[str, ...]:
    output: list[str] = []
    position = start
    for hunk in hunks:
        output.extend(base[position : hunk.start])
        output.extend(hunk.replacement)
        position = hunk.end
    output.extend(base[position:end])
    return tuple(output)


__all__ = [
    "DiffHunk",
    "MergeRegionConflict",
    "ThreeWayTextMerge",
    "diff_lines",
    "join_logical_lines",
    "merge_text",
    "merge_three_way",
    "resolve_three_way_conflicts",
    "split_logical_lines",
]
