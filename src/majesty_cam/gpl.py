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
            if item.kind in (DefinitionKind.EXPRESSION, DefinitionKind.FUNCTION)
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
    r"^[ \t]*function[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
_EXPRESSION_RE = re.compile(
    r"^[ \t]*expression[ \t]+(#[A-Za-z_][A-Za-z0-9_]*)\b[^\r\n]*(?:\r\n|\r|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_BEGIN_END_RE = re.compile(r"\b(begin|end)\b", re.IGNORECASE)
_DAT_HEADER_RE = re.compile(
    r"^[ \t]*\[([^\]\r\n]+)\][^\r\n]*(?:\r\n|\r|\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def semantic_key(
    kind: Union[DefinitionKind, str], name: str
) -> tuple[DefinitionKind, str]:
    return (_coerce_kind(kind), name.casefold())


def parse_gpl(text: str, source_name: str = "<memory>") -> ParsedSemanticSource:
    """Parse top-level GPL function and expression definitions without reformatting."""

    masked = _mask_non_code(text)
    function_starts = list(_FUNCTION_START_RE.finditer(masked))
    provisional: list[SemanticItem] = []
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
        for token in _BEGIN_END_RE.finditer(masked, match.end(), limit):
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

    for match in _EXPRESSION_RE.finditer(masked):
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
    "parse_dat",
    "parse_gpl",
    "semantic_key",
]
