from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
from typing import Iterable, Mapping, Optional, Sequence, Union


class DefinitionKind(str, Enum):
    """Majesty source definitions with independent, case-insensitive namespaces."""

    FUNCTION = "function"
    EXPRESSION = "expression"
    DAT_BLOCK = "dat_block"
    PROTOTYPE = "prototype"


class ConflictKind(str, Enum):
    DIVERGENT_ADDITION = "divergent_addition"
    DIVERGENT_MODIFICATION = "divergent_modification"


@dataclass(frozen=True)
class SourceSpan:
    """A half-open character span and its inclusive source line range."""

    start: int
    end: int
    start_line: int
    end_line: int

    def extract(self, source_text: str) -> str:
        return source_text[self.start : self.end]


@dataclass(frozen=True)
class SemanticItem:
    """One independently mergeable GPL expression/function or DAT block."""

    kind: DefinitionKind
    name: str
    text: str
    source_name: str
    span: Optional[SourceSpan]
    ordinal: int = 0
    leading_text: str = ""

    @property
    def normalized_name(self) -> str:
        return self.name.casefold()

    @property
    def key(self) -> tuple[DefinitionKind, str]:
        return (self.kind, self.normalized_name)

    @classmethod
    def resolved(
        cls,
        kind: Union[DefinitionKind, str],
        name: str,
        text: str,
        source_name: str = "<resolution>",
    ) -> "SemanticItem":
        """Construct an explicit conflict resolution not tied to an input span."""

        return cls(
            kind=_coerce_kind(kind),
            name=name,
            text=text,
            source_name=source_name,
            span=None,
        )


class SemanticParseError(ValueError):
    """Base class for malformed GPL/DAT semantic input."""


class UnterminatedDefinitionError(SemanticParseError):
    def __init__(self, source_name: str, kind: DefinitionKind, name: str, line: int):
        self.source_name = source_name
        self.kind = kind
        self.name = name
        self.line = line
        super().__init__(
            f"{source_name}:{line}: unterminated {kind.value} definition {name!r}"
        )


@dataclass(frozen=True)
class ForeachReturnViolation:
    """One GPL ``return`` whose statement is owned by a ``foreach`` loop."""

    source_name: str
    return_line: int
    foreach_line: int


class DuplicateDefinitionError(SemanticParseError):
    """A side cannot contain two definitions for the same semantic key."""

    def __init__(
        self,
        side_name: str,
        first: SemanticItem,
        duplicate: SemanticItem,
    ):
        self.side_name = side_name
        self.key = first.key
        self.first = first
        self.duplicate = duplicate
        first_location = _item_location(first)
        duplicate_location = _item_location(duplicate)
        super().__init__(
            f"{side_name}: duplicate {first.kind.value} {first.name!r} "
            f"at {duplicate_location}; first defined at {first_location}"
        )


@dataclass(frozen=True)
class ParsedSemanticSource:
    source_name: str
    text: str
    items: tuple[SemanticItem, ...]
    trailing_text: str = ""

    def get(
        self, kind: Union[DefinitionKind, str], name: str
    ) -> Optional[SemanticItem]:
        key = semantic_key(kind, name)
        return next((item for item in self.items if item.key == key), None)

    def require(self, kind: Union[DefinitionKind, str], name: str) -> SemanticItem:
        item = self.get(kind, name)
        if item is None:
            normalized_kind = _coerce_kind(kind)
            raise KeyError(f"{normalized_kind.value} {name!r} is not defined")
        return item

    def render(self) -> str:
        """Reconstruct the input exactly, including comments and whitespace."""

        return "".join(item.leading_text + item.text for item in self.items) + self.trailing_text


def require_complete_semantic_coverage(source: ParsedSemanticSource) -> None:
    """Reject source text the semantic merger would not preserve.

    Comments and whitespace between definitions are intentionally disposable.
    Any other prefix, inter-definition, or trailing text is executable or an
    unknown directive and must fail closed instead of silently disappearing.
    """

    fragments = [
        *(item.leading_text for item in source.items),
        source.trailing_text,
    ]
    for index, fragment in enumerate(fragments):
        if _has_meaningful_unparsed_text(fragment):
            raise SemanticParseError(
                f"{source.source_name}: unparsed semantic-source text in gap {index}"
            )


@dataclass(frozen=True)
class MergeVariant:
    side_name: str
    item: SemanticItem


@dataclass(frozen=True)
class SemanticConflict:
    kind: ConflictKind
    key: tuple[DefinitionKind, str]
    vanilla: Optional[SemanticItem]
    variants: tuple[MergeVariant, ...]

    @property
    def name(self) -> str:
        if self.vanilla is not None:
            return self.vanilla.name
        return self.variants[0].item.name


class SemanticMergeConflictError(ValueError):
    def __init__(self, conflicts: Sequence[SemanticConflict]):
        self.conflicts = tuple(conflicts)
        labels = ", ".join(
            f"{conflict.key[0].value}:{conflict.name}" for conflict in self.conflicts
        )
        super().__init__(f"unresolved semantic merge conflicts: {labels}")


@dataclass(frozen=True)
class GplProjectSourceSet:
    """Compiler-ready text for one merged GPL project and its source files."""

    project_text: str
    gpl_filename: Optional[str]
    gpl_text: str
    dat_filename: Optional[str]
    dat_text: str

    @property
    def files(self) -> dict[str, str]:
        files: dict[str, str] = {}
        if self.dat_filename is not None:
            files[self.dat_filename] = self.dat_text
        if self.gpl_filename is not None:
            files[self.gpl_filename] = self.gpl_text
        return files


@dataclass(frozen=True)
class SemanticMergeResult:
    items: tuple[SemanticItem, ...]
    conflicts: tuple[SemanticConflict, ...]

    @property
    def is_clean(self) -> bool:
        return not self.conflicts

    def require_clean(self) -> "SemanticMergeResult":
        if self.conflicts:
            raise SemanticMergeConflictError(self.conflicts)
        return self

    def render(
        self,
        kinds: Optional[Iterable[Union[DefinitionKind, str]]] = None,
    ) -> str:
        """Render selected definitions in deterministic merge order."""

        self.require_clean()
        allowed = None
        if kinds is not None:
            allowed = {_coerce_kind(kind) for kind in kinds}
        selected = [
            item for item in self.items if allowed is None or item.kind in allowed
        ]
        return _render_items(selected)

    def emit_project_source_set(
        self,
        gpl_filename: str = "Merged.gpl",
        dat_filename: str = "Merged.dat",
    ) -> GplProjectSourceSet:
        """Emit data-before-source project ordering used by Majesty's GPL compiler."""

        self.require_clean()
        gpl_items = [
            item
            for item in self.items
            if item.kind in (
                DefinitionKind.EXPRESSION,
                DefinitionKind.FUNCTION,
                DefinitionKind.PROTOTYPE,
            )
        ]
        dat_items = [item for item in self.items if item.kind == DefinitionKind.DAT_BLOCK]
        actual_gpl_name = gpl_filename if gpl_items else None
        actual_dat_name = dat_filename if dat_items else None
        project_lines: list[str] = []
        if actual_dat_name is not None:
            project_lines.append(f'data="{actual_dat_name}"')
        if actual_gpl_name is not None:
            project_lines.append(f'source="{actual_gpl_name}"')
        project_text = "\n".join(project_lines)
        if project_text:
            project_text += "\n"
        return GplProjectSourceSet(
            project_text=project_text,
            gpl_filename=actual_gpl_name,
            gpl_text=_render_items(gpl_items),
            dat_filename=actual_dat_name,
            dat_text=_render_items(dat_items),
        )


_FUNCTION_START_RE = re.compile(
    # GPL also uses `function Name` for callback parameters and local
    # variables (e.g. stock Set_Spire_Levels). Only definitions introduce
    # an argument list. This runs on masked code, so comments/newlines
    # between the name and '(' remain valid without changing source spans.
    r"^[ \t]*function[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()",
    re.IGNORECASE | re.MULTILINE,
)
_PROTOTYPE_START_RE = re.compile(
    r"^[ \t]*prototype[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
_TOP_LEVEL_END_RE = re.compile(
    r"^[ \t]*end[ \t]*(?://[^\r\n]*)?(?:\r\n|\r|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_EXPRESSION_RE = re.compile(
    r"^[ \t]*expression[ \t]+(#[A-Za-z_][A-Za-z0-9_]*)\b[^\r\n]*(?:\r\n|\r|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_INTEGER_EXPRESSION_RE = re.compile(
    r"\A(?P<prefix>[ \t]*expression[ \t]+"
    r"(?P<name>#[A-Za-z_][A-Za-z0-9_]*)[ \t]+)"
    r"(?P<value>[0-9]+)"
    r"(?P<suffix>[ \t]*(?://[^\r\n]*)?(?:\r\n|\r|\n)?)\Z",
    re.IGNORECASE,
)
_BEGIN_END_RE = re.compile(r"\b(begin|end)\b", re.IGNORECASE)
_FOREACH_RE = re.compile(r"\bforeach\b", re.IGNORECASE)
_DO_RE = re.compile(r"\bdo\b", re.IGNORECASE)
_RETURN_RE = re.compile(r"\breturn\b", re.IGNORECASE)
_DAT_HEADER_RE = re.compile(
    r"^[ \t]*\[([^\]\r\n]+)\][^\r\n]*(?:\r\n|\r|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def semantic_key(
    kind: Union[DefinitionKind, str], name: str
) -> tuple[DefinitionKind, str]:
    return (_coerce_kind(kind), name.casefold())


def find_foreach_return_violations(
    text: str,
    source_name: str = "<memory>",
) -> tuple[ForeachReturnViolation, ...]:
    """Find beta2-unsafe function exits from within GPL ``foreach`` bodies.

    Majesty GPL permits both ``begin``/``end`` blocks and single-statement loop
    bodies (including nested ``if`` statements).  Work from a same-length copy
    with comments and strings masked, then find the lexical extent of every
    loop body.  This deliberately reports the unsafe source shape rather than
    attempting to rewrite author-owned control flow.
    """

    masked = _mask_non_code(text)
    by_return_offset: dict[int, ForeachReturnViolation] = {}
    for loop in _FOREACH_RE.finditer(masked):
        do = _DO_RE.search(masked, loop.end())
        if do is None:
            # Malformed GPL is diagnosed by the semantic/compiler preflight.
            continue
        body_start = _skip_masked_space(masked, do.end())
        body_end = _gpl_statement_end(masked, body_start)
        if body_end <= body_start:
            continue
        for result in _RETURN_RE.finditer(masked, body_start, body_end):
            # An inner foreach encountered later owns the more useful loop line
            # when the same return is nested in multiple loops.
            by_return_offset[result.start()] = ForeachReturnViolation(
                source_name=source_name,
                return_line=_line_number(text, result.start()),
                foreach_line=_line_number(text, loop.start()),
            )
    return tuple(by_return_offset[offset] for offset in sorted(by_return_offset))


def parse_gpl(text: str, source_name: str = "<memory>") -> ParsedSemanticSource:
    """Parse top-level GPL prototypes, functions, and expressions exactly."""

    masked = _mask_non_code(text)
    provisional: list[SemanticItem] = []
    prototype_ranges: list[tuple[int, int]] = []
    prototype_starts = list(_PROTOTYPE_START_RE.finditer(masked))
    for index, match in enumerate(prototype_starts):
        limit = (
            prototype_starts[index + 1].start()
            if index + 1 < len(prototype_starts)
            else len(text)
        )
        end_match = _TOP_LEVEL_END_RE.search(masked, match.end(), limit)
        if end_match is None:
            raise UnterminatedDefinitionError(
                source_name,
                DefinitionKind.PROTOTYPE,
                match.group(1),
                _line_number(text, match.start()),
            )
        span = _make_span(text, match.start(), end_match.end())
        provisional.append(
            SemanticItem(
                kind=DefinitionKind.PROTOTYPE,
                name=match.group(1),
                text=span.extract(text),
                source_name=source_name,
                span=span,
            )
        )
        prototype_ranges.append((span.start, span.end))

    masked_without_prototypes = _mask_spans(masked, prototype_ranges)
    function_starts = list(_FUNCTION_START_RE.finditer(masked_without_prototypes))
    function_ranges: list[tuple[int, int]] = []

    for index, match in enumerate(function_starts):
        limit = (
            function_starts[index + 1].start()
            if index + 1 < len(function_starts)
            else len(text)
        )
        depth = 0
        saw_begin = False
        definition_end: Optional[int] = None
        for token in _BEGIN_END_RE.finditer(masked_without_prototypes, match.end(), limit):
            keyword = token.group(1).casefold()
            if keyword == "begin":
                saw_begin = True
                depth += 1
            elif saw_begin:
                depth -= 1
                if depth == 0:
                    definition_end = _line_end(text, token.end())
                    break
                if depth < 0:
                    break
        name = match.group(1)
        if definition_end is None:
            raise UnterminatedDefinitionError(
                source_name,
                DefinitionKind.FUNCTION,
                name,
                _line_number(text, match.start()),
            )
        span = _make_span(text, match.start(), definition_end)
        provisional.append(
            SemanticItem(
                kind=DefinitionKind.FUNCTION,
                name=name,
                text=span.extract(text),
                source_name=source_name,
                span=span,
            )
        )
        function_ranges.append((span.start, span.end))

    for match in _EXPRESSION_RE.finditer(masked_without_prototypes):
        if _inside_any_range(match.start(), function_ranges):
            continue
        span = _make_span(text, match.start(), match.end())
        provisional.append(
            SemanticItem(
                kind=DefinitionKind.EXPRESSION,
                name=match.group(1),
                text=span.extract(text),
                source_name=source_name,
                span=span,
            )
        )

    return _finish_parse(source_name, text, provisional)


def _mask_spans(text: str, spans: Sequence[tuple[int, int]]) -> str:
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for index in range(start, end):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def parse_dat(text: str, source_name: str = "<memory>") -> ParsedSemanticSource:
    """Parse Majesty GPL data records delimited by ``[Name]`` and ``[end]``."""

    masked = _mask_non_code(text)
    headers = list(_DAT_HEADER_RE.finditer(masked))
    provisional: list[SemanticItem] = []
    index = 0
    while index < len(headers):
        start = headers[index]
        name = start.group(1).strip()
        if name.casefold() == "end":
            raise SemanticParseError(
                f"{source_name}:{_line_number(text, start.start())}: "
                "DAT block terminator has no opening block"
            )
        end_match: Optional[re.Match[str]] = None
        cursor = index + 1
        while cursor < len(headers):
            candidate = headers[cursor]
            candidate_name = candidate.group(1).strip()
            if candidate_name.casefold() == "end":
                end_match = candidate
                break
            raise UnterminatedDefinitionError(
                source_name,
                DefinitionKind.DAT_BLOCK,
                name,
                _line_number(text, start.start()),
            )
        if end_match is None:
            raise UnterminatedDefinitionError(
                source_name,
                DefinitionKind.DAT_BLOCK,
                name,
                _line_number(text, start.start()),
            )
        span = _make_span(text, start.start(), end_match.end())
        provisional.append(
            SemanticItem(
                kind=DefinitionKind.DAT_BLOCK,
                name=name,
                text=span.extract(text),
                source_name=source_name,
                span=span,
            )
        )
        index = cursor + 1

    return _finish_parse(source_name, text, provisional)


def merge_semantic_items(
    vanilla_items: Iterable[SemanticItem],
    mod_items: Mapping[str, Iterable[SemanticItem]],
    resolutions: Optional[
        Mapping[tuple[Union[DefinitionKind, str], str], SemanticItem]
    ] = None,
) -> SemanticMergeResult:
    """Perform an N-way merge using vanilla as the common ancestor.

    Missing definitions on a mod side mean "no change", matching Majesty BCD
    overlays. Divergent edits are never ordered or guessed: callers must provide
    an explicit resolved item under the conflicting semantic key.
    """

    vanilla = tuple(vanilla_items)
    vanilla_by_key = _index_side("vanilla", vanilla)
    mods: list[tuple[str, tuple[SemanticItem, ...], dict[tuple[DefinitionKind, str], SemanticItem]]] = []
    for side_name, side_items_iterable in mod_items.items():
        side_items = tuple(side_items_iterable)
        mods.append((side_name, side_items, _index_side(side_name, side_items)))

    normalized_resolutions: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    if resolutions is not None:
        for raw_key, item in resolutions.items():
            key = semantic_key(raw_key[0], raw_key[1])
            if item.key != key:
                raise ValueError(
                    f"resolution key {key!r} does not match item key {item.key!r}"
                )
            normalized_resolutions[key] = item

    all_keys = set(vanilla_by_key)
    for _side_name, _side_items, side_by_key in mods:
        all_keys.update(side_by_key)

    selected: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    conflicts: list[SemanticConflict] = []
    used_resolutions: set[tuple[DefinitionKind, str]] = set()

    for key in all_keys:
        base = vanilla_by_key.get(key)
        variants: list[MergeVariant] = []
        for side_name, _side_items, side_by_key in mods:
            candidate = side_by_key.get(key)
            if candidate is None:
                continue
            if base is not None and candidate.text == base.text:
                continue
            variants.append(MergeVariant(side_name, candidate))

        if not variants:
            if base is not None:
                selected[key] = base
            continue

        distinct_texts = {variant.item.text for variant in variants}
        if len(distinct_texts) == 1:
            selected[key] = variants[0].item
            continue

        resolution = normalized_resolutions.get(key)
        if resolution is not None:
            selected[key] = resolution
            used_resolutions.add(key)
            continue

        conflict_kind = (
            ConflictKind.DIVERGENT_MODIFICATION
            if base is not None
            else ConflictKind.DIVERGENT_ADDITION
        )
        conflicts.append(
            SemanticConflict(
                kind=conflict_kind,
                key=key,
                vanilla=base,
                variants=tuple(variants),
            )
        )

    unused_resolutions = set(normalized_resolutions) - used_resolutions
    if unused_resolutions:
        unused = sorted((kind.value, name) for kind, name in unused_resolutions)
        raise ValueError(f"resolutions were supplied for non-conflicting items: {unused!r}")

    ordered: list[SemanticItem] = []
    emitted: set[tuple[DefinitionKind, str]] = set()
    for item in vanilla:
        chosen = selected.get(item.key)
        if chosen is not None and item.key not in emitted:
            ordered.append(chosen)
            emitted.add(item.key)
    for _side_name, side_items, _side_by_key in mods:
        for item in side_items:
            if item.key in vanilla_by_key or item.key in emitted:
                continue
            chosen = selected.get(item.key)
            if chosen is not None:
                ordered.append(chosen)
                emitted.add(item.key)

    conflict_order = {item.key: index for index, item in enumerate(vanilla)}
    next_order = len(conflict_order)
    for _side_name, side_items, _side_by_key in mods:
        for item in side_items:
            if item.key not in conflict_order:
                conflict_order[item.key] = next_order
                next_order += 1
    conflicts.sort(key=lambda conflict: conflict_order[conflict.key])
    return SemanticMergeResult(tuple(ordered), tuple(conflicts))


def merge_sources(
    vanilla_sources: Iterable[ParsedSemanticSource],
    mod_sources: Mapping[str, Iterable[ParsedSemanticSource]],
    resolutions: Optional[
        Mapping[tuple[Union[DefinitionKind, str], str], SemanticItem]
    ] = None,
) -> SemanticMergeResult:
    """Flatten complete source sets and merge them with duplicate detection."""

    vanilla_items = [
        item for source in vanilla_sources for item in source.items
    ]
    flattened_mods = {
        side_name: [item for source in sources for item in source.items]
        for side_name, sources in mod_sources.items()
    }
    return merge_semantic_items(vanilla_items, flattened_mods, resolutions)


_INVENTORY_EXPRESSION_RE = re.compile(r"^#[A-Za-z_][A-Za-z0-9_]*$")
_STOCK_DEATH_DROP_LAST_EXCLUSION_RE = re.compile(
    r"(?P<indent>^[ \t]*)WhatItem[ \t]*!=[ \t]*"
    r"#MarketItem_Market3_Item[ \t]*\)",
    re.IGNORECASE | re.MULTILINE,
)

_PURCHASE_EQUIPMENT_FINAL_RE = re.compile(
    r"(?P<indent>^[ \t]*)If\s*\(\s*Flag\s*\)\s*"
    r"begin\s*"
    r"ThisAgent's\s+\"ActiveScript\"\s*=\s*\$Use_Building\s*;\s*"
    r"return\s+TRUE\s*;\s*"
    r"end\s*"
    r"return\s+False\s*;\s*End\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def add_purchase_equipment_tail_callbacks(
    result: SemanticMergeResult,
    callback_symbols: Iterable[str],
    *,
    stock_purchase_equipment: Optional[SemanticItem] = None,
    source_name: str = "<Purchase_Equipment tail composition>",
) -> SemanticMergeResult:
    """Compose boolean callbacks at stock GPLMx Purchase_Equipment's tail.

    The insertion point is after the complete shipped purchase chain, including
    ``Stat_Boost_Check``, and before the stock final ``Flag`` handoff to
    ``Use_Building``.  Each later callback is evaluated only when every stock,
    package-owned, and earlier tail choice declined the hero.
    """

    requested: list[str] = []
    seen: set[str] = set()
    for symbol in callback_symbols:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", symbol):
            raise ValueError(f"invalid Purchase_Equipment callback symbol: {symbol!r}")
        key = symbol.casefold()
        if key in seen:
            raise ValueError(f"duplicate Purchase_Equipment callback symbol: {symbol!r}")
        seen.add(key)
        requested.append(symbol)
    if not requested:
        return result

    result.require_clean()
    items = list(result.items)
    target_key = semantic_key(DefinitionKind.FUNCTION, "Purchase_Equipment")
    targets = [item for item in items if item.key == target_key]
    if not targets:
        if stock_purchase_equipment is None or stock_purchase_equipment.key != target_key:
            raise ValueError(
                "Purchase_Equipment tail callbacks require the installed stock "
                "GPLMx Purchase_Equipment source"
            )
        target = replace(stock_purchase_equipment, span=None)
        items.append(target)
    elif len(targets) == 1:
        target = targets[0]
    else:  # pragma: no cover - semantic merge prevents duplicate keys
        raise ValueError("Purchase_Equipment is defined more than once")

    function_names = {
        item.normalized_name
        for item in items
        if item.kind == DefinitionKind.FUNCTION
    }
    missing = [symbol for symbol in requested if symbol.casefold() not in function_names]
    if missing:
        raise ValueError(
            "Purchase_Equipment tail callbacks must name package-owned boolean "
            f"functions; missing: {', '.join(missing)}"
        )

    masked = _mask_non_code(target.text)
    required_calls = (
        "$BlackSmith_Check",
        "$WizGuild_Check",
        "$Poison_Check",
        "$Potion_Check",
        "$Ring_Check",
        "$Market3_Check",
        "$Stat_Boost_Check",
    )
    positions: list[int] = []
    for call in required_calls:
        matches = list(re.finditer(re.escape(call), masked, re.IGNORECASE))
        minimum = 2 if call in {"$BlackSmith_Check", "$WizGuild_Check"} else 1
        if len(matches) < minimum:
            raise ValueError(
                "Purchase_Equipment does not contain the complete recognized "
                f"stock GPLMx purchase chain ({call})"
            )
        positions.append(matches[-1].start())
    if positions != sorted(positions):
        raise ValueError(
            "Purchase_Equipment stock GPLMx purchase checks are not in the "
            "recognized order"
        )

    final_matches = list(_PURCHASE_EQUIPMENT_FINAL_RE.finditer(target.text))
    if len(final_matches) != 1:
        raise ValueError(
            "Purchase_Equipment does not contain exactly one recognized stock "
            "final Flag/Use_Building handoff"
        )
    final_match = final_matches[0]
    if positions[-1] >= final_match.start():
        raise ValueError(
            "Purchase_Equipment Stat_Boost_Check is not before the stock final handoff"
        )

    indent = final_match.group("indent")
    callback_lines = []
    for symbol in requested:
        callback_lines.extend(
            (
                f"{indent}If (Flag == FALSE)",
                f"{indent}\tbegin",
                f"{indent}\t\tIf (${symbol} (ThisAgent))",
                f"{indent}\t\t\tFlag = TRUE;",
                f"{indent}\tend",
                "",
            )
        )
    newline = "\r\n" if "\r\n" in target.text else "\n"
    insertion = newline.join(callback_lines)
    resolved = replace(
        target,
        text=target.text[: final_match.start()] + insertion + target.text[final_match.start() :],
        source_name=source_name,
        span=None,
    )
    return SemanticMergeResult(
        tuple(resolved if item.key == target_key else item for item in items),
        result.conflicts,
    )


def add_purchase_bazaar_tail_callbacks(
    result: SemanticMergeResult,
    callback_symbols: Iterable[str],
    *,
    stock_purchase_bazaar: Optional[SemanticItem] = None,
    source_name: str = "<Purchase_Bazaar tail composition>",
) -> SemanticMergeResult:
    """Compose boolean callbacks after stock GPLMx Bazaar choices decline."""

    requested: list[str] = []
    seen: set[str] = set()
    for symbol in callback_symbols:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", symbol):
            raise ValueError(f"invalid Purchase_Bazaar callback symbol: {symbol!r}")
        key = symbol.casefold()
        if key in seen:
            raise ValueError(f"duplicate Purchase_Bazaar callback symbol: {symbol!r}")
        seen.add(key)
        requested.append(symbol)
    if not requested:
        return result

    result.require_clean()
    items = list(result.items)
    target_key = semantic_key(DefinitionKind.FUNCTION, "Purchase_Bazaar")
    targets = [item for item in items if item.key == target_key]
    if not targets:
        if stock_purchase_bazaar is None or stock_purchase_bazaar.key != target_key:
            raise ValueError(
                "Purchase_Bazaar tail callbacks require the installed stock "
                "GPLMx Purchase_Bazaar source"
            )
        target = replace(stock_purchase_bazaar, span=None)
        items.append(target)
    elif len(targets) == 1:
        target = targets[0]
    else:  # pragma: no cover - semantic merge prevents duplicate keys
        raise ValueError("Purchase_Bazaar is defined more than once")

    function_names = {
        item.normalized_name
        for item in items
        if item.kind == DefinitionKind.FUNCTION
    }
    missing = [symbol for symbol in requested if symbol.casefold() not in function_names]
    if missing:
        raise ValueError(
            "Purchase_Bazaar tail callbacks must name package-owned boolean "
            f"functions; missing: {', '.join(missing)}"
        )

    masked = _mask_non_code(target.text)
    required = (
        "Flag = FALSE",
        "$RandomNumber",
        "$listobjects",
        "#Bazaar_Item_One",
        "#Bazaar_Item_Two",
        "#Bazaar_Item_Three",
        "#Bazaar_Item_Four",
        "#Bazaar_Item_Five",
        "#Bazaar_Item_Six",
        "foreach Item in Item_list",
        "$Researched_Item",
        "$Get_Bazaar_Cost",
        "$Bazaar_Item_Check",
    )
    positions = []
    for token in required:
        position = masked.casefold().find(token.casefold())
        if position < 0:
            raise ValueError(
                "Purchase_Bazaar does not contain the complete recognized "
                f"stock GPLMx purchase chain ({token})"
            )
        positions.append(position)
    if positions != sorted(positions):
        raise ValueError(
            "Purchase_Bazaar stock GPLMx purchase checks are not in the "
            "recognized order"
        )

    final_matches = list(_PURCHASE_EQUIPMENT_FINAL_RE.finditer(target.text))
    if len(final_matches) != 1:
        raise ValueError(
            "Purchase_Bazaar does not contain exactly one recognized stock "
            "final Flag/Use_Building handoff"
        )
    final_match = final_matches[0]
    if positions[-1] >= final_match.start():
        raise ValueError(
            "Purchase_Bazaar item selection is not before the stock final handoff"
        )

    indent = final_match.group("indent")
    callback_lines = []
    for symbol in requested:
        callback_lines.extend(
            (
                f"{indent}If (Flag == FALSE)",
                f"{indent}\tbegin",
                f"{indent}\t\tIf (${symbol} (ThisAgent))",
                f"{indent}\t\t\tFlag = TRUE;",
                f"{indent}\tend",
                "",
            )
        )
    newline = "\r\n" if "\r\n" in target.text else "\n"
    insertion = newline.join(callback_lines)
    resolved = replace(
        target,
        text=target.text[: final_match.start()] + insertion + target.text[final_match.start() :],
        source_name=source_name,
        span=None,
    )
    return SemanticMergeResult(
        tuple(resolved if item.key == target_key else item for item in items),
        result.conflicts,
    )


def add_hero_quest_lifecycle_callbacks(
    result: SemanticMergeResult,
    hooks: Iterable[tuple[Sequence[str], str, str, str, str]],
    *,
    stock_hero_trees: Mapping[str, SemanticItem],
    stock_reset_tasks: Optional[SemanticItem] = None,
    stock_unit_death: Optional[SemanticItem] = None,
    source_name: str = "<hero-quest lifecycle composition>",
) -> SemanticMergeResult:
    """Splice package callbacks into four exact stock hero boundaries.

    Resume callbacks run after ``Check_Nearby`` declines and immediately
    before the unchanged ``Check_rewards`` call.  Consider callbacks run after
    stock ``Pursue_Entertainment`` declines; Healer and Monk use their audited
    post-``Purchase_Bazaar`` continuation because those two stock trees omit
    entertainment.  Reset callbacks run before stock ``Reset_Tasks`` clears
    Target/scripts, and death callbacks run after stock
    ``DeleteAllEffectors`` and before ``IGDeathScript``.  A TRUE boolean
    callback owns the task it just installed and short-circuits only the
    remaining stock decision-tree cascade.
    """

    requested = []
    seen = set()
    for raw_scripts, resume, consider, reset, death in hooks:
        scripts = tuple(sorted({script.casefold() for script in raw_scripts}))
        if not scripts:
            raise ValueError("hero-quest lifecycle requires at least one hero script")
        for symbol in (resume, consider, reset, death):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", symbol):
                raise ValueError(f"invalid hero-quest callback symbol: {symbol!r}")
            if symbol.casefold() in seen:
                raise ValueError(f"duplicate hero-quest callback symbol: {symbol!r}")
            seen.add(symbol.casefold())
        requested.append((scripts, resume, consider, reset, death))
    if not requested:
        return result

    result.require_clean()
    items = list(result.items)
    functions = {
        item.normalized_name: item
        for item in items
        if item.kind is DefinitionKind.FUNCTION
    }
    for _, resume, consider, reset, death in requested:
        for symbol, returns_boolean in (
            (resume, True), (consider, True), (reset, False), (death, False),
        ):
            item = functions.get(symbol.casefold())
            if item is None:
                raise ValueError(
                    "hero-quest callbacks must name package-owned GPL functions; "
                    f"missing: {symbol}"
                )
            masked = _mask_non_code(item.text)
            suffix = r"\s+is\s+boolean" if returns_boolean else ""
            signature = (
                r"\s*function\s+" + re.escape(symbol)
                + r"\s*\(\s*agent\s+[A-Za-z_][A-Za-z0-9_]*\s*\)"
                + suffix + r"\s*(?:declare|begin)\b"
            )
            if re.match(signature, masked, re.IGNORECASE) is None:
                expected = "(agent) is boolean" if returns_boolean else "(agent)"
                raise ValueError(
                    f"hero-quest callback {symbol!r} must use signature {expected}"
                )

    by_script: dict[str, tuple[list[str], list[str]]] = {}
    reset_symbols = []
    death_symbols = []
    for scripts, resume, consider, reset, death in requested:
        for script in scripts:
            resume_callbacks, consider_callbacks = by_script.setdefault(
                script, ([], [])
            )
            resume_callbacks.append(resume)
            consider_callbacks.append(consider)
        reset_symbols.append(reset)
        death_symbols.append(death)

    for script, (resume_callbacks, consider_callbacks) in sorted(by_script.items()):
        stock = stock_hero_trees.get(script)
        if stock is None:
            raise ValueError(f"unsupported or missing stock hero decision tree: {script}")
        target = next(
            (item for item in items if item.key == stock.key),
            None,
        )
        if target is None:
            target = replace(stock, span=None)
            items.append(target)
        masked_target = _mask_non_code(target.text)
        near_matches = list(re.finditer(
            r"^[ \t]*if\s*\(\s*\$check_nearby\s*\(\s*thisagent\s*\)\s*==\s*False\s*\)[ \t]*\r?$",
            masked_target, re.IGNORECASE | re.MULTILINE,
        ))
        reward_matches = list(re.finditer(
            r"^[ \t]*if\s*\(\s*\$Check_rewards\s*\(\s*thisagent\s*,\s*(?:TRUE|FALSE)\s*\)\s*==\s*False\s*\)[ \t]*\r?$",
            masked_target, re.IGNORECASE | re.MULTILINE,
        ))
        if (
            len(near_matches) != 1 or len(reward_matches) != 1
            or near_matches[0].end() > reward_matches[0].start()
            or masked_target[near_matches[0].end():reward_matches[0].start()].strip()
        ):
            raise ValueError(
                f"{script} does not contain exactly one recognized "
                "Check_Nearby/Check_rewards resume anchor"
            )
        pursue_matches = list(re.finditer(
            r"^[ \t]*if\s*\(\s*\$pursue_entertainment\s*\(\s*thisagent\s*\)\s*==\s*False\s*\)[ \t]*\r?$",
            masked_target, re.IGNORECASE | re.MULTILINE,
        ))
        bazaar_matches = list(re.finditer(
            r"^[ \t]*if\s*\(\s*\$Purchase_bazaar\s*\(\s*thisagent\s*,\s*70\s*\)\s*==\s*False\s*\)[ \t]*\r?$",
            masked_target, re.IGNORECASE | re.MULTILINE,
        ))
        if script in {"mx_healer", "mx_monk"}:
            if pursue_matches or len(bazaar_matches) != 1:
                raise ValueError(
                    f"{script} does not contain its recognized stock "
                    "post-Purchase_Bazaar consideration anchor"
                )
            consider_match = bazaar_matches[0]
        else:
            if len(pursue_matches) != 1:
                raise ValueError(
                    f"{script} does not contain exactly one recognized stock "
                    "post-Pursue_Entertainment consideration anchor"
                )
            consider_match = pursue_matches[0]

        reward_match = reward_matches[0]
        newline = "\r\n" if "\r\n" in target.text else "\n"
        reward_line = target.text[reward_match.start():reward_match.end()]
        resume_indent = re.match(r"[ \t]*", reward_line).group(0)
        resume_insertion = "".join(
            f"{resume_indent}if (${symbol}(ThisAgent) == False){newline}{newline}"
            for symbol in resume_callbacks
        )
        consider_line = target.text[
            consider_match.start():consider_match.end()
        ]
        consider_indent = re.match(r"[ \t]*", consider_line).group(0)
        next_code = re.search(r"\S", target.text[consider_match.end():])
        if next_code is None:
            raise ValueError(
                f"{script} stock consideration anchor has no continuation"
            )
        consider_insert_at = consider_match.end() + next_code.start()
        consider_insertion = "".join(
            f"{consider_indent}if (${symbol}(ThisAgent) == False){newline}{newline}"
            for symbol in consider_callbacks
        )
        updated_text = (
            target.text[:consider_insert_at] + consider_insertion
            + target.text[consider_insert_at:]
        )
        updated_text = (
            updated_text[:reward_match.start()] + resume_insertion
            + updated_text[reward_match.start():]
        )
        updated = replace(
            target,
            text=updated_text,
            source_name=source_name,
            span=None,
        )
        items = [updated if item.key == target.key else item for item in items]

    def materialize(name: str, stock: Optional[SemanticItem]) -> SemanticItem:
        key = semantic_key(DefinitionKind.FUNCTION, name)
        existing = [item for item in items if item.key == key]
        if len(existing) == 1:
            return existing[0]
        if existing:
            raise ValueError(f"{name} is defined more than once")
        if stock is None or stock.key != key:
            raise ValueError(f"hero-quest lifecycle requires installed stock {name}")
        item = replace(stock, span=None)
        items.append(item)
        return item

    reset_item = materialize("reset_tasks", stock_reset_tasks)
    reset_anchor = re.compile(
        r"(?P<begin>\bbegin\s*\r?\n)(?P<body>[\s\S]*?\$StopMoving\s*\(\s*ThisAgent\s*\)\s*;)",
        re.IGNORECASE,
    )
    reset_matches = list(reset_anchor.finditer(reset_item.text))
    if len(reset_matches) != 1:
        raise ValueError("reset_tasks does not contain the recognized stock entry anchor")
    reset_match = reset_matches[0]
    newline = "\r\n" if "\r\n" in reset_item.text else "\n"
    reset_insert = "".join(f"\t${symbol}(ThisAgent);{newline}" for symbol in reset_symbols)
    updated_reset = replace(
        reset_item,
        text=(reset_item.text[:reset_match.end("begin")] + reset_insert
              + reset_item.text[reset_match.end("begin"):]),
        source_name=source_name,
        span=None,
    )
    items = [updated_reset if item.key == reset_item.key else item for item in items]

    death_item = materialize("Unit_Call_Deathscript", stock_unit_death)
    death_anchor = re.compile(
        r"(?P<delete>^[ \t]*\$DeleteAllEffectors\s*\(\s*thisagent\s*\)\s*;\s*$)"
        r"(?P<gap>\r?\n(?:[ \t]*\r?\n|[ \t]*//[^\r\n]*\r?\n)*)"
        r"(?P<callback>^[ \t]*if\s*\(\s*\$validfunction\s*\(\s*thisagent's\s+\"IGDeathScript\"\s*\)\s*==\s*TRUE\s*\))",
        re.IGNORECASE | re.MULTILINE,
    )
    death_matches = list(death_anchor.finditer(death_item.text))
    if len(death_matches) != 1:
        raise ValueError(
            "Unit_Call_Deathscript does not contain the recognized stock cleanup anchor"
        )
    death_match = death_matches[0]
    newline = "\r\n" if "\r\n" in death_item.text else "\n"
    indent = re.match(r"[ \t]*", death_match.group("callback")).group(0)
    death_insert = "".join(
        f"{indent}${symbol}(ThisAgent);{newline}" for symbol in death_symbols
    ) + newline
    updated_death = replace(
        death_item,
        text=(death_item.text[:death_match.start("callback")] + death_insert
              + death_item.text[death_match.start("callback"):]),
        source_name=source_name,
        span=None,
    )
    items = [updated_death if item.key == death_item.key else item for item in items]
    return SemanticMergeResult(tuple(items), result.conflicts)


def add_controlled_follower_movement_adjustments(
    result: SemanticMergeResult,
    hooks: Iterable[tuple[str, int, Sequence[str]]],
    *,
    stock_control_monster: Optional[SemanticItem] = None,
    stock_controlled_monster_death: Optional[SemanticItem] = None,
    stock_leader_dead: Optional[SemanticItem] = None,
    source_name: str = "<controlled-follower movement composition>",
) -> SemanticMergeResult:
    """Attach reversible movement adjustments to stock controlled followers.

    Each hook is ``(eligibility_callback, per_tier_step, four_markers)``.  The
    callback is evaluated only after stock ``Control_Monster`` has completed
    its follower setup.  For each positive stock Speed-tier difference from
    one through four, one generated private effector records one applied step.
    Stock death and leader-loss callbacks remove the exact applied steps once,
    without timers, polling, or replacement AI.
    """

    requested: list[tuple[str, int, tuple[str, str, str, str]]] = []
    seen_symbols: set[str] = set()
    seen_markers: set[str] = set()
    for symbol, adjustment, raw_markers in hooks:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", symbol):
            raise ValueError(
                f"invalid controlled-follower eligibility callback: {symbol!r}"
            )
        if (
            not isinstance(adjustment, int)
            or isinstance(adjustment, bool)
            or not -10000 <= adjustment <= -1
        ):
            raise ValueError(
                "controlled-follower movement step must be an integer "
                "from -10000 to -1"
            )
        markers = tuple(raw_markers)
        if len(markers) != 4 or any(
            re.fullmatch(r"MCF[0-9A-F]{12}[1-4]", marker) is None
            for marker in markers
        ):
            raise ValueError("controlled-follower speed sync requires four manager markers")
        symbol_key = symbol.casefold()
        if symbol_key in seen_symbols:
            raise ValueError(
                f"duplicate controlled-follower eligibility callback: {symbol!r}"
            )
        seen_symbols.add(symbol_key)
        for marker in markers:
            marker_key = marker.casefold()
            if marker_key in seen_markers:
                raise ValueError(
                    f"duplicate manager controlled-follower marker: {marker!r}"
                )
            seen_markers.add(marker_key)
        requested.append((symbol, adjustment, markers))
    if not requested:
        return result

    result.require_clean()
    items = list(result.items)
    for _symbol, _adjustment, markers in requested:
        for marker in markers:
            owners = [
                item.source_name
                for item in items
                if marker.casefold() in item.text.casefold()
            ]
            if owners:
                raise ValueError(
                    f"generated controlled-follower marker {marker!r} already "
                    f"appears in package GPL source: {', '.join(owners)}"
                )
    control = _materialize_stock_function(
        items, "Control_Monster", stock_control_monster,
        "controlled-follower movement adjustments",
    )
    death = _materialize_stock_function(
        items, "Controlled_Monster_Death", stock_controlled_monster_death,
        "controlled-follower movement adjustments",
    )
    leader_dead = _materialize_stock_function(
        items, "leader_dead", stock_leader_dead,
        "controlled-follower movement adjustments",
    )

    function_names = {
        item.normalized_name
        for item in items
        if item.kind == DefinitionKind.FUNCTION
    }
    missing = [symbol for symbol, _adjustment, _markers in requested
               if symbol.casefold() not in function_names]
    if missing:
        raise ValueError(
            "controlled-follower movement features must name package-owned "
            f"eligibility callbacks; missing: {', '.join(missing)}"
        )

    control = _inject_controlled_follower_begin(control, requested, source_name)
    death = _inject_controlled_follower_cleanup(
        death,
        requested,
        re.compile(
            r"(?P<indent>^[ \t]*)\$Monster_Gravestone\s*"
            r"\(\s*ThisAgent\s*\)\s*;",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Controlled_Monster_Death stock gravestone handoff",
        source_name,
    )
    leader_dead = _inject_controlled_follower_cleanup(
        leader_dead,
        requested,
        re.compile(
            r"(?P<indent>^[ \t]*)\$deleteeffector\s*"
            r"\(\s*thisagent\s*,\s*\"charm_icon\"\s*\)\s*;",
            re.IGNORECASE | re.MULTILINE,
        ),
        "leader_dead stock charm cleanup",
        source_name,
    )
    replacements = {
        control.key: control,
        death.key: death,
        leader_dead.key: leader_dead,
    }
    return SemanticMergeResult(
        tuple(replacements.get(item.key, item) for item in items),
        result.conflicts,
    )


def _materialize_stock_function(
    items: list[SemanticItem],
    name: str,
    stock_item: Optional[SemanticItem],
    label: str,
) -> SemanticItem:
    key = semantic_key(DefinitionKind.FUNCTION, name)
    matches = [item for item in items if item.key == key]
    if not matches:
        if stock_item is None or stock_item.key != key:
            raise ValueError(
                f"{label} require installed stock GPLMx {name} source"
            )
        item = replace(stock_item, span=None)
        items.append(item)
        return item
    if len(matches) != 1:  # pragma: no cover - semantic merge prevents this
        raise ValueError(f"{name} is defined more than once")
    return matches[0]


def _inject_controlled_follower_begin(
    target: SemanticItem,
    hooks: Sequence[tuple[str, int, tuple[str, str, str, str]]],
    source_name: str,
) -> SemanticItem:
    masked = _mask_non_code(target.text)
    required = (
        "$IsDead",
        "++",
        "$fake_wander",
        "$createeffector",
        "$Controlled_Monster",
        "$Controlled_Monster_Death",
        "= ThisAgent",
    )
    positions = [masked.casefold().find(token.casefold()) for token in required]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(
            "Control_Monster does not contain the complete recognized stock "
            "controlled-follower setup lifecycle"
        )
    anchor = re.compile(
        r"(?P<indent>^[ \t]*)\$setunitplayernumber\s*\(\s*target\s*,\s*"
        r"\$getunitplayernumber\s*\(\s*thisagent\s*\)\s*\)\s*;",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(anchor.finditer(masked))
    if len(matches) != 1 or positions[-1] >= matches[0].start():
        raise ValueError(
            "Control_Monster does not contain exactly one recognized stock "
            "player-ownership handoff"
        )
    for _symbol, _adjustment, markers in hooks:
        for marker in markers:
            if marker.casefold() in target.text.casefold():
                raise ValueError(
                    f"Control_Monster already contains generated marker {marker!r}"
                )
    match = matches[0]
    indent = match.group("indent")
    newline = "\r\n" if "\r\n" in target.text else "\n"
    lines: list[str] = []
    for symbol, adjustment, markers in hooks:
        lines.extend((
            f"{indent}If (${symbol} ( ThisAgent, Target ))",
            f"{indent}\tbegin",
            f"{indent}\t\tIf ($GetAttribute ( ThisAgent, #ATTRIB_Speed ) >= 1 &&",
            f"{indent}\t\t\t$GetAttribute ( ThisAgent, #ATTRIB_Speed ) <= 5 &&",
            f"{indent}\t\t\t$GetAttribute ( Target, #ATTRIB_Speed ) >= 1 &&",
            f"{indent}\t\t\t$GetAttribute ( Target, #ATTRIB_Speed ) <= 5)",
            f"{indent}\t\t\tbegin",
        ))
        for tier, marker in enumerate(markers, start=1):
            lines.extend((
                f"{indent}\t\t\t\tIf ("
                f"$GetAttribute ( ThisAgent, #ATTRIB_Speed ) - "
                f"$GetAttribute ( Target, #ATTRIB_Speed ) >= {tier} &&",
                f"{indent}\t\t\t\t\t$CheckEffector ( Target, \"{marker}\" ) == FALSE)",
                f"{indent}\t\t\t\t\tbegin",
                f"{indent}\t\t\t\t\t\t$AdjustAttribute ( Target, "
                f"#ATTRIB_MovementRateModifier, {adjustment} );",
                f"{indent}\t\t\t\t\t\t$CreateEffector ( Target, \"{marker}\", 1, \"infinite\" );",
                f"{indent}\t\t\t\t\tend",
            ))
        lines.extend((
            f"{indent}\t\t\tend",
            f"{indent}\tend",
        ))
    insertion = newline + newline.join(lines)
    return replace(
        target,
        text=target.text[:match.end()] + insertion + target.text[match.end():],
        source_name=source_name,
        span=None,
    )


def _inject_controlled_follower_cleanup(
    target: SemanticItem,
    hooks: Sequence[tuple[str, int, tuple[str, str, str, str]]],
    anchor: re.Pattern[str],
    anchor_label: str,
    source_name: str,
) -> SemanticItem:
    matches = list(anchor.finditer(target.text))
    if len(matches) != 1:
        raise ValueError(f"{anchor_label} is missing or ambiguous")
    for _symbol, _adjustment, markers in hooks:
        for marker in markers:
            if marker.casefold() in target.text.casefold():
                raise ValueError(
                    f"{target.name} already contains generated marker {marker!r}"
                )
    match = matches[0]
    indent = match.group("indent")
    newline = "\r\n" if "\r\n" in target.text else "\n"
    lines: list[str] = []
    for _symbol, adjustment, markers in hooks:
        reverse = -adjustment
        for marker in markers:
            lines.extend((
                f"{indent}If ($CheckEffector ( ThisAgent, \"{marker}\" ))",
                f"{indent}\tbegin",
                f"{indent}\t\t$AdjustAttribute ( ThisAgent, "
                f"#ATTRIB_MovementRateModifier, {reverse} );",
                f"{indent}\t\t$DeleteEffector ( ThisAgent, \"{marker}\" );",
                f"{indent}\tend",
            ))
    insertion = newline.join(lines) + newline
    return replace(
        target,
        text=target.text[:match.start()] + insertion + target.text[match.start():],
        source_name=source_name,
        span=None,
    )


def add_inventory_death_drop_exclusions(
    result: SemanticMergeResult,
    expressions: Iterable[str],
    *,
    source_name: str = "<inventory-death-drop-composition>",
) -> SemanticMergeResult:
    """Extend Majesty's stock hero-death non-drop condition.

    Numeric inventory keys (``INVx``) are reported droppable by the engine even
    when a private unit description carries ``CanDropItem=0``. Stock handles its
    own exceptions directly in ``Hero_Drop_Quest_Items`` before ``SpawnUnit``.
    This composes additional private IDs through that same lifecycle and fails
    closed if the selected function no longer has the stock condition shape.
    """

    requested: list[str] = []
    seen: set[str] = set()
    for expression in expressions:
        if not _INVENTORY_EXPRESSION_RE.fullmatch(expression):
            raise ValueError(
                f"invalid inventory death-drop exclusion expression: {expression!r}"
            )
        key = expression.casefold()
        if key in seen:
            raise ValueError(
                f"duplicate inventory death-drop exclusion: {expression!r}"
            )
        seen.add(key)
        requested.append(expression)
    if not requested:
        return result

    result.require_clean()
    defined_expressions = {
        item.normalized_name
        for item in result.items
        if item.kind == DefinitionKind.EXPRESSION
    }
    undefined = [
        expression
        for expression in requested
        if expression.casefold() not in defined_expressions
    ]
    if undefined:
        labels = ", ".join(undefined)
        raise ValueError(
            "inventory death-drop exclusions must name defined numeric "
            f"GPL expressions; missing: {labels}"
        )

    target_key = semantic_key(DefinitionKind.FUNCTION, "Hero_Drop_Quest_Items")
    target = next((item for item in result.items if item.key == target_key), None)
    if target is None:
        raise ValueError(
            "inventory death-drop exclusions require Hero_Drop_Quest_Items"
        )
    already_present = {
        expression.casefold()
        for expression in requested
        if re.search(rf"\bWhatItem\s*!=\s*{re.escape(expression)}\b", target.text, re.I)
    }
    additions = [
        expression
        for expression in requested
        if expression.casefold() not in already_present
    ]
    if not additions:
        return result

    matches = list(_STOCK_DEATH_DROP_LAST_EXCLUSION_RE.finditer(target.text))
    if len(matches) != 1:
        raise ValueError(
            "Hero_Drop_Quest_Items does not contain exactly one recognized "
            "stock inventory exclusion condition"
        )
    match = matches[0]
    indent = match.group("indent")
    replacement = (
        f"{indent}WhatItem != #MarketItem_Market3_Item &&\n"
        + "\n".join(
            f"{indent}WhatItem != {expression}{')' if index == len(additions) - 1 else ' &&'}"
            for index, expression in enumerate(additions)
        )
    )
    resolved = replace(
        target,
        text=target.text[: match.start()] + replacement + target.text[match.end() :],
        source_name=source_name,
        span=None,
    )
    return SemanticMergeResult(
        tuple(resolved if item.key == target_key else item for item in result.items),
        result.conflicts,
    )


def rewrite_integer_expression(
    item: SemanticItem,
    *,
    expected_value: int,
    replacement_value: int,
    source_name: str = "<integer-expression-rewrite>",
) -> SemanticItem:
    """Rewrite one declared GPL integer literal and no other numeric content.

    Private positional resources may be detached from their old table index only
    when compatibility metadata names the exact expression that carries it.  A
    compound expression, stale value, renamed symbol, or non-decimal literal is
    rejected instead of searching/replacing arbitrary numbers in GPL source.
    """

    if item.kind is not DefinitionKind.EXPRESSION:
        raise ValueError(f"{item.name} is not a GPL expression")
    if type(expected_value) is not int or expected_value < 0:
        raise ValueError("expected GPL expression value must be a non-negative integer")
    if type(replacement_value) is not int or replacement_value < 0:
        raise ValueError("replacement GPL expression value must be a non-negative integer")
    match = _INTEGER_EXPRESSION_RE.fullmatch(item.text)
    if match is None or match.group("name").casefold() != item.normalized_name:
        raise ValueError(
            f"{item.source_name}: {item.name} is not an exact decimal integer expression"
        )
    actual_value = int(match.group("value"), 10)
    if actual_value != expected_value:
        raise ValueError(
            f"{item.source_name}: {item.name} is {actual_value}, expected {expected_value}"
        )
    rewritten = (
        match.group("prefix")
        + str(replacement_value)
        + match.group("suffix")
    )
    return replace(item, text=rewritten, source_name=source_name, span=None)


def _finish_parse(
    source_name: str,
    text: str,
    provisional: Iterable[SemanticItem],
) -> ParsedSemanticSource:
    sorted_items = sorted(provisional, key=lambda item: item.span.start if item.span else -1)
    completed: list[SemanticItem] = []
    cursor = 0
    for ordinal, item in enumerate(sorted_items):
        assert item.span is not None
        completed.append(
            replace(
                item,
                ordinal=ordinal,
                leading_text=text[cursor : item.span.start],
            )
        )
        cursor = item.span.end
    _index_side(source_name, completed)
    return ParsedSemanticSource(
        source_name=source_name,
        text=text,
        items=tuple(completed),
        trailing_text=text[cursor:],
    )


def _index_side(
    side_name: str, items: Iterable[SemanticItem]
) -> dict[tuple[DefinitionKind, str], SemanticItem]:
    indexed: dict[tuple[DefinitionKind, str], SemanticItem] = {}
    for item in items:
        existing = indexed.get(item.key)
        if existing is not None:
            raise DuplicateDefinitionError(side_name, existing, item)
        indexed[item.key] = item
    return indexed


def _mask_non_code(text: str) -> str:
    """Blank comments and strings while retaining offsets and line endings."""

    chars = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if current == "/" and following == "/":
                chars[index] = " "
                chars[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                chars[index] = " "
                chars[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current == '"':
                quote = current
                chars[index] = " "
                index += 1
                state = "string"
                continue
            index += 1
            continue
        if state == "line_comment":
            if current in "\r\n":
                state = "code"
            else:
                chars[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if current == "*" and following == "/":
                chars[index] = " "
                chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
            index += 1
            continue
        if state == "string":
            if current == "\\" and following:
                if current not in "\r\n":
                    chars[index] = " "
                if following not in "\r\n":
                    chars[index + 1] = " "
                index += 2
                continue
            if current == quote:
                chars[index] = " "
                state = "code"
            elif current not in "\r\n":
                chars[index] = " "
            index += 1
    return "".join(chars)


def _skip_masked_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _word_at(text: str, offset: int, word: str) -> Optional[re.Match[str]]:
    return re.compile(rf"{re.escape(word)}\b", re.IGNORECASE).match(text, offset)


def _matching_parenthesis(text: str, opening: int) -> Optional[int]:
    if opening >= len(text) or text[opening] != "(":
        return None
    depth = 0
    for offset in range(opening, len(text)):
        char = text[offset]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return offset + 1
    return None


def _begin_block_end(text: str, opening: int) -> Optional[int]:
    depth = 0
    for token in _BEGIN_END_RE.finditer(text, opening):
        keyword = token.group(1).casefold()
        if keyword == "begin":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return token.end()
            if depth < 0:
                return None
    return None


def _simple_statement_end(text: str, start: int) -> int:
    parentheses = 0
    offset = start
    while offset < len(text):
        char = text[offset]
        if char == "(":
            parentheses += 1
        elif char == ")" and parentheses:
            parentheses -= 1
        elif char == ";" and parentheses == 0:
            return offset + 1
        offset += 1
    return len(text)


def _gpl_statement_end(text: str, start: int) -> int:
    """Return the lexical end of one GPL statement in already-masked text."""

    start = _skip_masked_space(text, start)
    if start >= len(text):
        return start

    begin = _word_at(text, start, "begin")
    if begin is not None:
        return _begin_block_end(text, start) or len(text)

    conditional = _word_at(text, start, "if")
    if conditional is not None:
        condition_start = _skip_masked_space(text, conditional.end())
        condition_end = _matching_parenthesis(text, condition_start)
        if condition_end is None:
            # GPL normally parenthesizes conditions.  Keeping the whole simple
            # statement is conservative for a malformed source and still does
            # not cross a terminating semicolon.
            return _simple_statement_end(text, start)
        then_end = _gpl_statement_end(text, condition_end)
        cursor = _skip_masked_space(text, then_end)
        otherwise = _word_at(text, cursor, "else")
        if otherwise is not None:
            return _gpl_statement_end(text, otherwise.end())
        return then_end

    for keyword in ("foreach", "while"):
        control = _word_at(text, start, keyword)
        if control is None:
            continue
        do = _DO_RE.search(text, control.end())
        if do is None:
            return _simple_statement_end(text, start)
        return _gpl_statement_end(text, do.end())

    return _simple_statement_end(text, start)


def _has_meaningful_unparsed_text(text: str) -> bool:
    """Return true unless ``text`` consists solely of whitespace/comments."""

    index = 0
    state = "code"
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if current.isspace():
                index += 1
                continue
            if current == "/" and following == "/":
                state = "line_comment"
                index += 2
                continue
            if current == "/" and following == "*":
                state = "block_comment"
                index += 2
                continue
            return True
        if state == "line_comment":
            if current in "\r\n":
                state = "code"
            index += 1
            continue
        if current == "*" and following == "/":
            state = "code"
            index += 2
            continue
        index += 1
    return state == "block_comment"


def _render_items(items: Iterable[SemanticItem]) -> str:
    output = ""
    for item in items:
        if output:
            if not output.endswith(("\r", "\n")):
                output += "\n"
            if not output.endswith(("\n\n", "\r\n\r\n")):
                output += "\n"
        output += item.text
    if output and not output.endswith(("\r", "\n")):
        output += "\n"
    return output


def _inside_any_range(offset: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _line_end(text: str, offset: int) -> int:
    match = re.match(r"[^\r\n]*(?:\r\n|\r|\n|$)", text[offset:])
    assert match is not None
    return offset + match.end()


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _make_span(text: str, start: int, end: int) -> SourceSpan:
    end_probe = max(start, end - 1)
    return SourceSpan(
        start=start,
        end=end,
        start_line=_line_number(text, start),
        end_line=_line_number(text, end_probe),
    )


def _item_location(item: SemanticItem) -> str:
    if item.span is None:
        return item.source_name
    return f"{item.source_name}:{item.span.start_line}"


def _coerce_kind(kind: Union[DefinitionKind, str]) -> DefinitionKind:
    if isinstance(kind, DefinitionKind):
        return kind
    normalized = kind.casefold().replace("-", "_")
    aliases = {
        "function": DefinitionKind.FUNCTION,
        "expression": DefinitionKind.EXPRESSION,
        "dat": DefinitionKind.DAT_BLOCK,
        "dat_block": DefinitionKind.DAT_BLOCK,
        "block": DefinitionKind.DAT_BLOCK,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown semantic definition kind: {kind!r}") from exc


__all__ = [
    "ConflictKind",
    "DefinitionKind",
    "DuplicateDefinitionError",
    "ForeachReturnViolation",
    "GplProjectSourceSet",
    "MergeVariant",
    "ParsedSemanticSource",
    "SemanticConflict",
    "SemanticItem",
    "SemanticMergeConflictError",
    "SemanticMergeResult",
    "SemanticParseError",
    "SourceSpan",
    "UnterminatedDefinitionError",
    "merge_semantic_items",
    "merge_sources",
    "add_inventory_death_drop_exclusions",
    "add_purchase_equipment_tail_callbacks",
    "add_purchase_bazaar_tail_callbacks",
    "add_hero_quest_lifecycle_callbacks",
    "add_controlled_follower_movement_adjustments",
    "find_foreach_return_violations",
    "rewrite_integer_expression",
    "parse_dat",
    "parse_gpl",
    "require_complete_semantic_coverage",
    "semantic_key",
]
