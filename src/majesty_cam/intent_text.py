from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import re
import struct
from typing import Iterable, Mapping, Sequence, Union
import uuid

from .gpl import DefinitionKind, ParsedSemanticSource, SemanticItem


INTENT_REGISTRY_MAGIC = b"MMTX"
INTENT_REGISTRY_VERSION = 1
INTENT_ID_BASE = 0x60000000
INTENT_ID_LIMIT = 0x70000000
INTENT_REGISTRY_RELATIVE_PATH = "Data/MMMIntentText.bin"
INTENT_REGISTRY_ENV_VAR = "MAJESTY_MOD_MANAGER_INTENT_REGISTRY"
INTENT_REGISTRY_MAX_FILE_SIZE = 16 * 1024 * 1024
INTENT_REGISTRY_MAX_RECORDS = 65_536
INTENT_REGISTRY_MAX_TEXT_SIZE = 16_384


class IntentTextError(ValueError):
    """Raised when private activity-text discovery or output is unsafe."""


@dataclass(frozen=True)
class PrivateActivityTextBinding:
    owner: str
    source_mod_id: str
    source_index: int
    expressions: tuple[str, ...]
    expected_text: str
    runtime_id: int
    package_expressions: tuple[str, ...] = ()

    @property
    def generated_expression(self) -> str:
        return f"#MMM_AITX_{self.runtime_id:08X}"


@dataclass(frozen=True)
class PrivateActivityTextRecord:
    binding: PrivateActivityTextBinding
    text: bytes


@dataclass(frozen=True)
class PrivateLiteralTextRecord:
    """Manager-owned text that is not sourced from Majesty's AITX table."""

    runtime_id: int
    text: bytes


PrivateIntentTextRecord = Union[PrivateActivityTextRecord, PrivateLiteralTextRecord]


@dataclass(frozen=True)
class ActivityTextDiscoveryPackage:
    """One package's stock-relative AITX changes and complete GPL sources."""

    owner: str
    source_mod_id: str
    changes: tuple[tuple[int, bytes], ...]
    stock_rows: tuple[tuple[int, bytes], ...]
    gpl_sources: tuple[ParsedSemanticSource, ...]


@dataclass(frozen=True)
class IntegerExpressionEnvironment:
    """Complete exact-value evidence for unowned GPL resolution items."""

    exact_values: Mapping[str, tuple[int, ...]]
    nonexact_names: frozenset[str]


_EXACT_INTEGER_EXPRESSION_RE = re.compile(
    r"\A[ \t]*expression[ \t]+"
    r"(?P<name>#[A-Za-z_][A-Za-z0-9_]*)[ \t]+"
    r"(?P<value>[0-9]+)"
    r"[ \t]*(?://[^\r\n]*)?(?:\r\n|\r|\n)?\Z",
    re.IGNORECASE,
)
_EXPRESSION_SYMBOL_RE = re.compile(r"#[A-Za-z_][A-Za-z0-9_]*")
_DECIMAL_INTEGER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<value>[0-9]+)(?![A-Za-z0-9_])"
)
_AITX_RESOLVER_CALL_RE = re.compile(
    r"\$(SpecifyIntent|MessageFlag|LocalChatMessage)[ \t\r\n]*\(",
    re.IGNORECASE,
)
_AITX_RESOLVER_ARGUMENT_COUNTS = {
    "specifyintent": 2,
    "messageflag": 2,
    "localchatmessage": 3,
}


def discover_private_activity_text_bindings(
    packages: Iterable[ActivityTextDiscoveryPackage],
    *,
    stock_integer_expressions: Mapping[str, int] | None = None,
) -> tuple[PrivateActivityTextBinding, ...]:
    """Discover changed AITX rows from direct stock-resolver call sites.

    The second argument of each recognized stock consumer is resolved when it
    is either an exact decimal literal or an exact expression symbol. Package
    definitions take precedence; symbols absent from the package may resolve
    through stock integer definitions. A row-bound expression used outside the
    three proven resolver argument positions is rejected because its dataflow
    cannot be safely localized. A changed row with only indirect/dynamic uses
    also fails closed.
    """

    discovered_rows: list[
        tuple[str, str, int, str | Sequence[str], str]
    ] = []
    package_expression_origins: dict[tuple[str, int], tuple[str, ...]] = {}
    seen_owners: set[str] = set()
    for package in packages:
        owner = package.owner
        if owner in seen_owners:
            raise IntentTextError(
                f"duplicate activity-text discovery owner: {owner!r}"
            )
        seen_owners.add(owner)
        changes = _validate_discovery_changes(package)
        if not changes:
            continue

        definitions, defined_symbols = _index_integer_expressions(package)
        resolved_stock = {
            key.casefold(): value
            for key, value in (stock_integer_expressions or {}).items()
        }
        aliases_by_row: dict[int, dict[str, str]] = {
            source_index: {} for source_index, _text in changes
        }
        package_aliases_by_row: dict[int, dict[str, str]] = {
            source_index: {} for source_index, _text in changes
        }
        uses_by_row = {source_index: 0 for source_index, _text in changes}
        nonresolver_uses: dict[str, list[str]] = {}
        nonresolver_numeric_uses: dict[int, list[str]] = {}
        for source in package.gpl_sources:
            for item in source.items:
                masked = _mask_non_code(item.text)
                argument_spans = set(_resolver_argument_spans(masked))
                definition_name_span: tuple[int, int] | None = None
                definition_value_span: tuple[int, int] | None = None
                if item.kind is DefinitionKind.EXPRESSION:
                    expression_match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
                    if expression_match is not None:
                        definition_name_span = expression_match.span("name")
                        definition_value_span = expression_match.span("value")
                for start, end in argument_spans:
                    token = masked[start:end]
                    symbol_match = _EXPRESSION_SYMBOL_RE.fullmatch(token)
                    if symbol_match is not None:
                        key = token.casefold()
                        value = (
                            definitions.get(key)
                            if key in defined_symbols
                            else resolved_stock.get(key)
                        )
                        alias = token
                    elif token.isascii() and token.isdecimal():
                        value = int(token, 10)
                        alias = None
                    else:
                        continue
                    if value not in uses_by_row:
                        continue
                    uses_by_row[value] += 1
                    if alias is not None:
                        aliases_by_row[value].setdefault(alias.casefold(), alias)
                        if alias.casefold() in defined_symbols:
                            package_aliases_by_row[value].setdefault(
                                alias.casefold(), alias
                            )
                for symbol in _EXPRESSION_SYMBOL_RE.finditer(masked):
                    span = symbol.span()
                    if span in argument_spans:
                        continue
                    if (
                        definition_name_span == span
                        and item.normalized_name == symbol.group(0).casefold()
                    ):
                        continue
                    nonresolver_uses.setdefault(symbol.group(0).casefold(), []).append(
                        f"{source.source_name}:{_line_number(item.text, symbol.start())}"
                    )
                for numeric in _DECIMAL_INTEGER_RE.finditer(masked):
                    span = numeric.span("value")
                    if span in argument_spans or span == definition_value_span:
                        continue
                    value = int(numeric.group("value"), 10)
                    if value not in uses_by_row:
                        continue
                    nonresolver_numeric_uses.setdefault(value, []).append(
                        f"{source.source_name}:{_line_number(item.text, numeric.start())}"
                    )
        for source_index, text in changes:
            numeric_locations = nonresolver_numeric_uses.get(source_index, [])
            if numeric_locations:
                labels = ", ".join(numeric_locations[:3])
                suffix = "" if len(numeric_locations) <= 3 else ", ..."
                raise IntentTextError(
                    f"{owner}: decimal AITX row {source_index} has an unsupported "
                    f"indirect/non-resolver use ({labels}{suffix}); safe dataflow "
                    "cannot be proven"
                )
            indirectly_used = []
            for key, locations in nonresolver_uses.items():
                if not locations:
                    continue
                value = (
                    definitions.get(key)
                    if key in defined_symbols
                    else resolved_stock.get(key)
                )
                if value == source_index:
                    indirectly_used.append((key, locations))
            if indirectly_used:
                key, locations = indirectly_used[0]
                labels = ", ".join(locations[:3])
                suffix = "" if len(locations) <= 3 else ", ..."
                raise IntentTextError(
                    f"{owner}: expression {key} resolves to AITX[{source_index}] "
                    f"through an unsupported indirect/non-resolver use "
                    f"({labels}{suffix}); safe dataflow cannot be proven"
                )
            if not uses_by_row[source_index]:
                raise IntentTextError(
                    f"{owner}: AITX[{source_index}] has no directly resolvable "
                    "$SpecifyIntent, $MessageFlag, or $LocalChatMessage argument "
                    "two; dynamic-only activity text cannot be relocated safely"
                )
            unsafe = [
                (alias, nonresolver_uses.get(key, []))
                for key, alias in aliases_by_row[source_index].items()
                if nonresolver_uses.get(key)
            ]
            if unsafe:
                alias, locations = unsafe[0]
                labels = ", ".join(locations[:3])
                suffix = "" if len(locations) <= 3 else ", ..."
                raise IntentTextError(
                    f"{owner}: {alias} also has an unsupported non-resolver use "
                    f"({labels}{suffix}); AITX[{source_index}] cannot be localized safely"
                )
            discovered_rows.append(
                (
                    owner,
                    package.source_mod_id,
                    source_index,
                    tuple(
                        sorted(aliases_by_row[source_index].values(), key=str.casefold)
                    ),
                    text.decode("cp1252"),
                )
            )
            package_expression_origins[(owner, source_index)] = tuple(
                sorted(
                    package_aliases_by_row[source_index].values(),
                    key=str.casefold,
                )
            )

    allocated = allocate_private_activity_text_ids(discovered_rows)
    return tuple(
        replace(
            binding,
            package_expressions=package_expression_origins.get(
                (binding.owner, binding.source_index), ()
            ),
        )
        for binding in allocated
    )


def collect_exact_integer_expressions(
    sources: Iterable[ParsedSemanticSource],
    *,
    owner: str,
) -> dict[str, int]:
    """Collect a case-insensitive exact-integer expression environment."""

    package = ActivityTextDiscoveryPackage(
        owner=owner,
        source_mod_id="stock",
        changes=(),
        stock_rows=(),
        gpl_sources=tuple(sources),
    )
    indexed, _defined = _index_integer_expressions(package)
    return indexed


def collect_integer_expression_environment(
    sources: Iterable[ParsedSemanticSource],
) -> IntegerExpressionEnvironment:
    """Collect all exact values and every non-exact expression definition.

    Multiple selected packages may define the same case-insensitive name. The
    environment retains every distinct exact value so an ownerless semantic
    resolution can reject ambiguity instead of inheriting load order.
    """

    values: dict[str, set[int]] = {}
    nonexact: set[str] = set()
    for source in sources:
        for item in source.items:
            if item.kind is not DefinitionKind.EXPRESSION:
                continue
            key = item.normalized_name
            match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
            if match is None:
                nonexact.add(key)
                continue
            values.setdefault(key, set()).add(int(match.group("value"), 10))
    return IntegerExpressionEnvironment(
        exact_values={
            key: tuple(sorted(item_values))
            for key, item_values in sorted(values.items())
        },
        nonexact_names=frozenset(nonexact),
    )


def rewrite_private_activity_text_resolver_calls(
    parsed_by_owner: Mapping[str, Sequence[ParsedSemanticSource]],
    bindings: Sequence[PrivateActivityTextBinding],
    *,
    integer_expression_environment: IntegerExpressionEnvironment | None = None,
) -> dict[str, list[ParsedSemanticSource]]:
    """Rewrite only proven stock-resolver argument sites to private IDs.

    One generated expression is added per private ``(Mod UUID, AITX row)`` and
    every proven symbolic alias or decimal literal is replaced only in resolver
    argument two. An exact package-owned alias is removed after all selected
    source uses are proven; a stock-supplied alias is never removed.
    """

    by_owner: dict[str, list[PrivateActivityTextBinding]] = {}
    for binding in bindings:
        by_owner.setdefault(binding.owner, []).append(binding)
    unknown = sorted(set(by_owner) - set(parsed_by_owner))
    if unknown:
        raise IntentTextError(
            "private activity-text bindings name owners with no GPL source: "
            + ", ".join(unknown)
        )

    generated_owners: dict[tuple[DefinitionKind, str], str] = {}
    for binding in bindings:
        generated_key = (
            DefinitionKind.EXPRESSION,
            binding.generated_expression.casefold(),
        )
        previous_owner = generated_owners.get(generated_key)
        if previous_owner is not None:
            raise IntentTextError(
                "generated private activity expression is not unique across "
                f"{previous_owner!r} and {binding.owner!r}: "
                f"{binding.generated_expression}"
            )
        generated_owners[generated_key] = binding.owner
        generated_name = generated_key[1]
        if integer_expression_environment is not None and (
            generated_name in integer_expression_environment.exact_values
            or generated_name in integer_expression_environment.nonexact_names
        ):
            raise IntentTextError(
                f"{binding.owner}: generated private activity expression "
                f"{binding.generated_expression} collides with the complete "
                "selected/stock GPL expression environment"
            )

    generated_names = {name for _kind, name in generated_owners}
    for source_owner, sources in parsed_by_owner.items():
        for source in sources:
            for item in source.items:
                masked = _mask_non_code(item.text)
                for symbol in _EXPRESSION_SYMBOL_RE.finditer(masked):
                    if symbol.group(0).casefold() in generated_names:
                        raise IntentTextError(
                            f"{source_owner}: preexisting GPL reference "
                            f"{symbol.group(0)} collides with the generated private "
                            "activity-expression namespace"
                        )

    removable_by_owner: dict[
        str, dict[str, PrivateActivityTextBinding]
    ] = {}
    resolver_aliases_by_owner: dict[
        str, dict[str, PrivateActivityTextBinding]
    ] = {}
    removable_aliases: set[str] = set()
    for binding in bindings:
        owner_resolver_aliases = resolver_aliases_by_owner.setdefault(
            binding.owner, {}
        )
        for expression in binding.expressions:
            owner_resolver_aliases[expression.casefold()] = binding
        owner_removals = removable_by_owner.setdefault(binding.owner, {})
        for expression in binding.package_expressions:
            key = expression.casefold()
            if key not in owner_resolver_aliases:
                raise IntentTextError(
                    f"{binding.owner}: package-defined activity expression "
                    f"{expression} was not proven as a resolver alias"
                )
            previous = owner_removals.get(key)
            if previous is not None and previous != binding:
                raise IntentTextError(
                    f"{binding.owner}: package-defined activity expression "
                    f"{expression} maps to multiple private AITX rows"
                )
            owner_removals[key] = binding
            removable_aliases.add(key)

    # Removing a proven owner-local expression is safe only when every other
    # selected owner either owns the same proven private alias (and will have
    # its own definition/calls removed/replaced) or does not reference it.
    for source_owner, sources in parsed_by_owner.items():
        allowed_definitions = removable_by_owner.get(source_owner, {})
        allowed_resolvers = resolver_aliases_by_owner.get(source_owner, {})
        for source in sources:
            for item in source.items:
                masked = _mask_non_code(item.text)
                resolver_spans = set(_resolver_argument_spans(masked))
                definition_name_span: tuple[int, int] | None = None
                if item.kind is DefinitionKind.EXPRESSION:
                    match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
                    if match is not None:
                        definition_name_span = match.span("name")
                for symbol in _EXPRESSION_SYMBOL_RE.finditer(masked):
                    key = symbol.group(0).casefold()
                    if key not in removable_aliases:
                        continue
                    span = symbol.span()
                    if (
                        span == definition_name_span
                        and key in allowed_definitions
                    ):
                        continue
                    if span in resolver_spans and key in allowed_resolvers:
                        continue
                    binding_owners = sorted(
                        owner
                        for owner, owner_aliases in removable_by_owner.items()
                        if key in owner_aliases
                    )
                    raise IntentTextError(
                        f"{source_owner}: GPL use of package-defined private AITX "
                        f"alias {symbol.group(0)} depends on owner(s) "
                        + ", ".join(binding_owners)
                        + "; the alias cannot be safely removed"
                    )

    output: dict[str, list[ParsedSemanticSource]] = {}
    for owner, sources in parsed_by_owner.items():
        owner_bindings = by_owner.get(owner, [])
        alias_map: dict[str, PrivateActivityTextBinding] = {}
        row_map: dict[int, PrivateActivityTextBinding] = {}
        for binding in owner_bindings:
            if binding.source_index in row_map:
                raise IntentTextError(
                    f"{owner}: duplicate private AITX row {binding.source_index}"
                )
            row_map[binding.source_index] = binding
            for expression in binding.expressions:
                key = expression.casefold()
                previous = alias_map.get(key)
                if previous is not None and previous != binding:
                    raise IntentTextError(
                        f"{owner}: GPL alias {expression} maps to multiple AITX rows"
                    )
                alias_map[key] = binding

        replacement_counts = {binding.runtime_id: 0 for binding in owner_bindings}
        removal_counts = {
            (binding.runtime_id, expression.casefold()): 0
            for binding in owner_bindings
            for expression in binding.package_expressions
        }
        rewritten_sources: list[ParsedSemanticSource] = []
        for source in sources:
            rewritten_items: list[SemanticItem] = []
            for item in source.items:
                removable_binding = removable_by_owner.get(owner, {}).get(
                    item.normalized_name
                ) if item.kind is DefinitionKind.EXPRESSION else None
                if removable_binding is not None:
                    match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
                    if (
                        match is None
                        or int(match.group("value"), 10)
                        != removable_binding.source_index
                    ):
                        raise IntentTextError(
                            f"{owner}: package-defined private AITX expression "
                            f"{item.name} no longer has its discovered exact value"
                        )
                    removal_counts[
                        (removable_binding.runtime_id, item.normalized_name)
                    ] += 1
                    continue
                masked = _mask_non_code(item.text)
                replacements: list[tuple[int, int, str, PrivateActivityTextBinding]] = []
                for start, end in _resolver_argument_spans(masked):
                    token = masked[start:end]
                    symbol_match = _EXPRESSION_SYMBOL_RE.fullmatch(token)
                    if symbol_match is not None:
                        binding = alias_map.get(token.casefold())
                    elif token.isascii() and token.isdecimal():
                        binding = row_map.get(int(token, 10))
                    else:
                        binding = None
                    if binding is not None:
                        replacements.append(
                            (start, end, binding.generated_expression, binding)
                        )
                if not replacements:
                    rewritten_items.append(item)
                    continue
                rewritten_text = item.text
                for start, end, expression, binding in reversed(replacements):
                    rewritten_text = (
                        rewritten_text[:start] + expression + rewritten_text[end:]
                    )
                    replacement_counts[binding.runtime_id] += 1
                rewritten_items.append(
                    replace(
                        item,
                        text=rewritten_text,
                        source_name=(
                            f"<Majesty Mod Manager AITX call-site rewrite: {owner}>"
                        ),
                        span=None,
                    )
                )
            rewritten_sources.append(
                ParsedSemanticSource(
                    source_name=source.source_name,
                    text=source.text,
                    items=tuple(rewritten_items),
                    trailing_text=source.trailing_text,
                )
            )

        missing = [
            binding
            for binding in owner_bindings
            if replacement_counts[binding.runtime_id] == 0
        ]
        if missing:
            raise IntentTextError(
                f"{owner}: no resolver call sites were rewritten for AITX rows "
                + ", ".join(str(binding.source_index) for binding in missing)
            )
        missing_definitions = [
            (runtime_id, expression)
            for (runtime_id, expression), count in removal_counts.items()
            if count != 1
        ]
        if missing_definitions:
            labels = ", ".join(
                expression for _runtime_id, expression in missing_definitions
            )
            raise IntentTextError(
                f"{owner}: package-defined private AITX expressions were not "
                f"removed exactly once: {labels}"
            )
        generated_sources: list[ParsedSemanticSource] = []
        for binding in sorted(owner_bindings, key=lambda item: item.runtime_id):
            definition = (
                f"expression {binding.generated_expression} {binding.runtime_id}\n"
            )
            generated_sources.append(
                ParsedSemanticSource(
                    source_name=(
                        f"<Majesty Mod Manager private AITX {owner}:"
                        f"{binding.source_index}>"
                    ),
                    text=definition,
                    items=(
                        SemanticItem.resolved(
                            DefinitionKind.EXPRESSION,
                            binding.generated_expression,
                            definition,
                            source_name=(
                                f"<Majesty Mod Manager private AITX {owner}:"
                                f"{binding.source_index}>"
                            ),
                        ),
                    ),
                )
            )
        output[owner] = generated_sources + rewritten_sources
    return output


def rewrite_unowned_private_activity_text_resolver_calls(
    items: Sequence[SemanticItem],
    bindings: Sequence[PrivateActivityTextBinding],
    *,
    integer_expression_environment: IntegerExpressionEnvironment | None = None,
) -> tuple[SemanticItem, ...]:
    """Rewrite/audit resolver sites introduced by semantic resolutions.

    Per-owner sources are rewritten before semantic merging. An explicit
    conflict-resolution item has no natural package owner and can replace one
    of those rewritten functions, so only those explicit items use this
    unowned pass. A symbol or decimal row that identifies more than one
    selected package is rejected instead of choosing an owner. Ordinary final
    items must never be passed here because their coincidental numeric values
    belong to their original owners.
    """

    aliases: dict[str, list[PrivateActivityTextBinding]] = {}
    rows: dict[int, list[PrivateActivityTextBinding]] = {}
    generated_keys: dict[tuple[DefinitionKind, str], PrivateActivityTextBinding] = {}
    for binding in bindings:
        rows.setdefault(binding.source_index, []).append(binding)
        generated_key = (
            DefinitionKind.EXPRESSION,
            binding.generated_expression.casefold(),
        )
        previous = generated_keys.get(generated_key)
        if previous is not None and previous != binding:
            raise IntentTextError(
                "generated private activity expression is not unique across "
                f"{previous.owner!r} and {binding.owner!r}: "
                f"{binding.generated_expression}"
            )
        generated_keys[generated_key] = binding
        for expression in binding.expressions:
            aliases.setdefault(expression.casefold(), []).append(binding)
    for item in items:
        binding = generated_keys.get(item.key)
        if binding is not None:
            raise IntentTextError(
                "semantic resolution defines reserved generated private activity "
                f"expression {binding.generated_expression}"
            )

    final_source = ParsedSemanticSource(
        source_name="<final GPL AITX audit>",
        text="",
        items=tuple(items),
    )
    local_environment = collect_integer_expression_environment((final_source,))
    exact_values: dict[str, set[int]] = {}
    nonexact_names: set[str] = set()
    for environment in (
        integer_expression_environment,
        local_environment,
    ):
        if environment is None:
            continue
        for raw_name, values in environment.exact_values.items():
            exact_values.setdefault(raw_name.casefold(), set()).update(values)
        nonexact_names.update(
            name.casefold() for name in environment.nonexact_names
        )
    complete_environment_supplied = integer_expression_environment is not None
    generated_names = {
        binding.generated_expression.casefold() for binding in bindings
    }

    def require_exact_value(token: str) -> int:
        key = token.casefold()
        values = exact_values.get(key, set())
        if key in nonexact_names:
            raise IntentTextError(
                f"semantic resolution resolver argument {token} has a non-exact "
                "GPL expression definition; its AITX identity cannot be proven"
            )
        if not values:
            fallback = aliases.get(key, [])
            if fallback and not complete_environment_supplied:
                values = {binding.source_index for binding in fallback}
            else:
                raise IntentTextError(
                    f"semantic resolution resolver argument {token} has no exact "
                    "definition in the complete selected/stock GPL environment"
                )
        if len(values) != 1:
            labels = ", ".join(str(value) for value in sorted(values))
            raise IntentTextError(
                f"semantic resolution resolver argument {token} is ambiguous "
                f"across exact GPL values {labels}"
            )
        return next(iter(values))

    rewritten: list[SemanticItem] = []
    for item in items:
        masked = _mask_non_code(item.text)
        argument_spans = _resolver_argument_spans(masked)
        argument_span_set = set(argument_spans)
        definition_name_span: tuple[int, int] | None = None
        definition_value_span: tuple[int, int] | None = None
        if item.kind is DefinitionKind.EXPRESSION:
            expression_match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
            if expression_match is not None:
                definition_name_span = expression_match.span("name")
                definition_value_span = expression_match.span("value")
        for symbol in _EXPRESSION_SYMBOL_RE.finditer(masked):
            span = symbol.span()
            if span in argument_span_set or span == definition_name_span:
                continue
            key = symbol.group(0).casefold()
            values = exact_values.get(key, set())
            maps_private_row = any(value in rows for value in values)
            if (
                maps_private_row
                or key in aliases
                or (key in nonexact_names and maps_private_row)
            ):
                raise IntentTextError(
                    "semantic resolution has an unsupported non-resolver use of "
                    f"private AITX expression {symbol.group(0)}"
                )
        for numeric in _DECIMAL_INTEGER_RE.finditer(masked):
            span = numeric.span("value")
            if span in argument_span_set or span == definition_value_span:
                continue
            value = int(numeric.group("value"), 10)
            if value in rows:
                raise IntentTextError(
                    "semantic resolution has an unsupported non-resolver use of "
                    f"private AITX row {value}"
                )
        replacements: list[tuple[int, int, PrivateActivityTextBinding]] = []
        for start, end in argument_spans:
            token = masked[start:end]
            if _EXPRESSION_SYMBOL_RE.fullmatch(token):
                if token.casefold() in generated_names:
                    raise IntentTextError(
                        "semantic resolution source directly uses reserved generated "
                        f"private activity expression {token}"
                    )
                candidates = rows.get(require_exact_value(token), [])
            elif token.isascii() and token.isdecimal():
                candidates = rows.get(int(token, 10), [])
            else:
                raise IntentTextError(
                    f"semantic resolution resolver argument {token!r} is dynamic; "
                    "its AITX identity cannot be proven"
                )
            unique = {candidate.runtime_id: candidate for candidate in candidates}
            if len(unique) > 1:
                raise IntentTextError(
                    f"final GPL resolver argument {token} is ambiguous across "
                    "selected private AITX rows"
                )
            if unique:
                replacements.append((start, end, next(iter(unique.values()))))
        if not replacements:
            rewritten.append(item)
            continue
        text = item.text
        for start, end, binding in reversed(replacements):
            text = text[:start] + binding.generated_expression + text[end:]
        rewritten.append(
            replace(
                item,
                text=text,
                source_name="<Majesty Mod Manager final AITX resolver audit>",
                span=None,
            )
        )
    result = tuple(rewritten)
    for item in result:
        masked = _mask_non_code(item.text)
        for start, end in _resolver_argument_spans(masked):
            token = masked[start:end]
            if _EXPRESSION_SYMBOL_RE.fullmatch(token):
                if token.casefold() in generated_names:
                    continue
                value = require_exact_value(token)
                if value in rows:
                    raise IntentTextError(
                        f"final GPL retains unresolved private AITX resolver value {token}"
                    )
            elif token.isascii() and token.isdecimal() and int(token, 10) in rows:
                raise IntentTextError(
                    f"final GPL retains unresolved private AITX resolver row {token}"
                )
    return result


def audit_private_activity_text_resolver_aliases(
    items: Sequence[SemanticItem],
    bindings: Sequence[PrivateActivityTextBinding],
) -> None:
    """Reject exact private aliases left in final ordinary resolver calls.

    The owning package's proven sites and every explicit resolution are
    rewritten before semantic merge. Any source alias still used as resolver
    argument two therefore came from a different owner and would point at the
    sanitized positional row. Decimal values are intentionally not audited
    here because the same number can independently belong to another package.
    """

    aliases = {
        expression.casefold(): binding
        for binding in bindings
        for expression in binding.expressions
    }
    if not aliases:
        return
    for item in items:
        masked = _mask_non_code(item.text)
        for start, end in _resolver_argument_spans(masked):
            token = masked[start:end]
            if not _EXPRESSION_SYMBOL_RE.fullmatch(token):
                continue
            binding = aliases.get(token.casefold())
            if binding is not None:
                raise IntentTextError(
                    "final GPL contains a cross-owner resolver call using private "
                    f"AITX alias {token} from {binding.owner}:AITX[{binding.source_index}]"
                )


def _validate_discovery_changes(
    package: ActivityTextDiscoveryPackage,
) -> tuple[tuple[int, bytes], ...]:
    if not package.owner or package.owner != package.owner.casefold():
        raise IntentTextError(
            f"activity-text discovery owner must be lowercase: {package.owner!r}"
        )
    ordered = sorted(package.changes, key=lambda item: item[0])
    stock_rows = dict(package.stock_rows)
    if len(stock_rows) != len(package.stock_rows):
        raise IntentTextError(
            f"{package.owner}: duplicate stock AITX discovery row"
        )
    seen: set[int] = set()
    for source_index, text in ordered:
        if type(source_index) is not int or source_index < 0:
            raise IntentTextError(
                f"{package.owner}: changed AITX index must be a non-negative integer"
            )
        if source_index in seen:
            raise IntentTextError(
                f"{package.owner}: duplicate changed AITX index {source_index}"
            )
        seen.add(source_index)
        if source_index not in stock_rows:
            raise IntentTextError(
                f"{package.owner}: AITX[{source_index}] has no stock-row evidence"
            )
        stock_text = stock_rows[source_index]
        if not isinstance(stock_text, bytes) or b"\x00" in stock_text:
            raise IntentTextError(
                f"{package.owner}: AITX[{source_index}] stock text is malformed"
            )
        if stock_text.strip().lower() not in (b"", b"empty"):
            raise IntentTextError(
                f"{package.owner}: AITX[{source_index}] replaces non-placeholder "
                "stock text; "
                "automatic localization cannot prove whether the mod intended a "
                "global stock-row replacement"
            )
        if not isinstance(text, bytes):
            raise IntentTextError(
                f"{package.owner}: AITX[{source_index}] text must be bytes"
            )
        if not text or len(text) > INTENT_REGISTRY_MAX_TEXT_SIZE or b"\x00" in text:
            raise IntentTextError(
                f"{package.owner}: AITX[{source_index}] has invalid length/content"
            )
        text.decode("cp1252")
    return tuple(ordered)


def _index_integer_expressions(
    package: ActivityTextDiscoveryPackage,
) -> tuple[dict[str, int], set[str]]:
    indexed: dict[str, int] = {}
    defined: set[str] = set()
    for source in package.gpl_sources:
        for item in source.items:
            if item.kind is not DefinitionKind.EXPRESSION:
                continue
            key = item.name.casefold()
            if key in defined:
                raise IntentTextError(
                    f"{package.owner}: GPL expression {item.name} is defined more than once"
                )
            defined.add(key)
            match = _EXACT_INTEGER_EXPRESSION_RE.fullmatch(item.text)
            if match is None:
                continue
            indexed[key] = int(match.group("value"), 10)
    return indexed, defined


def _resolver_argument_spans(masked: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    for call in _AITX_RESOLVER_CALL_RE.finditer(masked):
        function = call.group(1).casefold()
        open_paren = call.end() - 1
        close_paren = _matching_paren(masked, open_paren)
        if close_paren is None:
            continue
        arguments = _split_call_arguments(masked, open_paren + 1, close_paren)
        if len(arguments) != _AITX_RESOLVER_ARGUMENT_COUNTS[function]:
            continue
        start, end = arguments[1]
        while start < end and masked[start].isspace():
            start += 1
        while end > start and masked[end - 1].isspace():
            end -= 1
        spans.append((start, end))
    return tuple(spans)


def _matching_paren(text: str, open_paren: int) -> int | None:
    depth = 0
    for index in range(open_paren, len(text)):
        character = text[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_call_arguments(
    text: str, start: int, end: int
) -> tuple[tuple[int, int], ...]:
    arguments: list[tuple[int, int]] = []
    depth = 0
    argument_start = start
    for index in range(start, end):
        character = text[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            arguments.append((argument_start, index))
            argument_start = index + 1
    arguments.append((argument_start, end))
    return tuple(arguments)


def _mask_non_code(text: str) -> str:
    chars = list(text)
    index = 0
    state = "code"
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if current == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current == '"':
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
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
            index += 1
            continue
        if state == "string":
            if current == "\\" and following:
                chars[index] = " "
                if following not in "\r\n":
                    chars[index + 1] = " "
                index += 2
                continue
            if current == '"':
                chars[index] = " "
                index += 1
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
            index += 1
    return "".join(chars)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def allocate_private_activity_text_ids(
    discovered_rows: Iterable[
        tuple[str, str, int, str | Sequence[str], str]
    ],
) -> tuple[PrivateActivityTextBinding, ...]:
    """Allocate manager IDs in a stable order from proven discovered rows.

    Each row is ``(owner, source_mod_id, source_index, source_expressions,
    expected_text)``. ``source_expressions`` may contain one or more safe aliases,
    or be empty when the package used an exact decimal resolver argument.
    The allocation identity is the normalized Mod UUID plus AITX source index,
    never a chosen alias, package discovery order, or filesystem order.
    """

    normalized: list[tuple[str, str, int, tuple[str, ...], str]] = []
    seen_symbols: set[tuple[str, str]] = set()
    seen_rows: set[tuple[str, int]] = set()
    for owner, source_mod_id, source_index, raw_expressions, expected_text in discovered_rows:
        if not owner or owner != owner.casefold():
            raise IntentTextError(
                f"private activity-text owner must be lowercase: {owner!r}"
            )
        if type(source_index) is not int or source_index < 0:
            raise IntentTextError(
                f"{owner}: private AITX index must be a non-negative integer"
            )
        if not isinstance(source_mod_id, str):
            raise IntentTextError(f"{owner}: source Mod ID must be a UUID")
        try:
            normalized_mod_id = str(uuid.UUID(source_mod_id)).upper()
        except ValueError as exc:
            raise IntentTextError(
                f"{owner}: source Mod ID is not a UUID: {source_mod_id!r}"
            ) from exc
        expressions = (
            (raw_expressions,)
            if isinstance(raw_expressions, str)
            else tuple(raw_expressions)
        )
        if any(not _valid_expression_name(expression) for expression in expressions):
            raise IntentTextError(
                f"{owner}: invalid private activity-text GPL expressions {expressions!r}"
            )
        if len({expression.casefold() for expression in expressions}) != len(expressions):
            raise IntentTextError(
                f"{owner}: duplicate private activity-text GPL expression alias"
            )
        expressions = tuple(sorted(expressions, key=str.casefold))
        try:
            encoded = expected_text.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise IntentTextError(
                f"{owner}:AITX[{source_index}] text is not representable in Majesty's CP1252 encoding"
            ) from exc
        if (
            not encoded
            or len(encoded) > INTENT_REGISTRY_MAX_TEXT_SIZE
            or b"\x00" in encoded
        ):
            raise IntentTextError(
                f"{owner}:AITX[{source_index}] text has invalid length/content"
            )
        row_key = (owner, source_index)
        for expression in expressions:
            symbol_key = (owner, expression.casefold())
            if symbol_key in seen_symbols:
                raise IntentTextError(
                    f"{owner}: duplicate private activity-text expression {expression}"
                )
            seen_symbols.add(symbol_key)
        if row_key in seen_rows:
            raise IntentTextError(
                f"{owner}: duplicate private AITX index {source_index}"
            )
        seen_rows.add(row_key)
        normalized.append(
            (owner, normalized_mod_id, source_index, expressions, expected_text)
        )

    normalized.sort(
        key=lambda item: (
            item[1].casefold(),
            item[2],
            item[0],
        )
    )
    if len(normalized) > INTENT_REGISTRY_MAX_RECORDS:
        raise IntentTextError("private activity-text registry has too many records")
    allocated: list[PrivateActivityTextBinding] = []
    allocated_ids: dict[int, tuple[str, int]] = {}
    for owner, source_mod_id, source_index, expressions, expected_text in normalized:
        identity = f"{source_mod_id.casefold()}\0aitx\0{source_index}".encode("ascii")
        # Keep AITX-derived rows in the lower half of the private range. The
        # upper half is reserved for other manager-owned literal text domains.
        offset = int.from_bytes(hashlib.sha256(identity).digest()[:4], "little") & 0x07FFFFFF
        runtime_id = INTENT_ID_BASE + offset
        previous = allocated_ids.get(runtime_id)
        if previous is not None:
            raise IntentTextError(
                "private activity-text ID collision at "
                f"0x{runtime_id:08X}: {previous[0]}:AITX[{previous[1]}] and "
                f"{source_mod_id}:AITX[{source_index}]"
            )
        allocated_ids[runtime_id] = (source_mod_id, source_index)
        allocated.append(PrivateActivityTextBinding(
            owner=owner,
            source_mod_id=source_mod_id,
            source_index=source_index,
            expressions=expressions,
            expected_text=expected_text,
            runtime_id=runtime_id,
        ))
    return tuple(allocated)


def allocate_private_literal_text_id(
    source_mod_id: str,
    namespace: str,
    local_key: str,
) -> int:
    """Allocate a stable manager text ID outside the AITX-derived namespace."""

    try:
        normalized_mod_id = str(uuid.UUID(source_mod_id)).casefold()
    except (TypeError, ValueError, AttributeError) as exc:
        raise IntentTextError("private literal text source Mod ID must be a UUID") from exc
    for label, value in (("namespace", namespace), ("local_key", local_key)):
        if not isinstance(value, str) or not value or "\x00" in value:
            raise IntentTextError(f"private literal text {label} is invalid")
        try:
            value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise IntentTextError(
                f"private literal text {label} must be ASCII"
            ) from exc
    identity = (
        normalized_mod_id + "\0literal-text\0" + namespace + "\0" + local_key
    ).encode("ascii")
    # 0x68000000..0x6FFFFFFF is reserved for non-AITX manager text. Existing
    # AITX allocations remain readable; combined-registry encoding catches the
    # vanishingly unlikely legacy hash collision and fails closed.
    return 0x68000000 + (
        int.from_bytes(hashlib.sha256(identity).digest()[:4], "little")
        & 0x07FFFFFF
    )


def _private_text_record_id(record: PrivateIntentTextRecord) -> int:
    if isinstance(record, PrivateActivityTextRecord):
        return record.binding.runtime_id
    if isinstance(record, PrivateLiteralTextRecord):
        return record.runtime_id
    raise IntentTextError("private activity-text registry record type is invalid")


def encode_intent_registry(records: Iterable[PrivateIntentTextRecord]) -> bytes:
    """Serialize the strict launcher/DLL activity-text registry."""

    ordered = sorted(records, key=_private_text_record_id)
    if len(ordered) > INTENT_REGISTRY_MAX_RECORDS:
        raise IntentTextError("private activity-text registry has too many records")
    seen: set[int] = set()
    output = bytearray(INTENT_REGISTRY_MAGIC)
    output += struct.pack("<II", INTENT_REGISTRY_VERSION, len(ordered))
    for record in ordered:
        runtime_id = _private_text_record_id(record)
        if not INTENT_ID_BASE <= runtime_id < INTENT_ID_LIMIT:
            raise IntentTextError(
                f"private activity-text ID is outside the reserved range: 0x{runtime_id:08X}"
            )
        if runtime_id in seen:
            raise IntentTextError(
                f"duplicate private activity-text ID: 0x{runtime_id:08X}"
            )
        seen.add(runtime_id)
        if (
            not record.text
            or len(record.text) > INTENT_REGISTRY_MAX_TEXT_SIZE
            or b"\x00" in record.text
        ):
            raise IntentTextError(
                f"private activity text 0x{runtime_id:08X} has invalid length/content"
            )
        try:
            record.text.decode("cp1252")
        except UnicodeDecodeError as exc:  # pragma: no cover - CP1252 maps all bytes
            raise IntentTextError(
                f"private activity text 0x{runtime_id:08X} is not CP1252"
            ) from exc
        output += struct.pack("<II", runtime_id, len(record.text))
        output += record.text
        if len(output) > INTENT_REGISTRY_MAX_FILE_SIZE:
            raise IntentTextError("private activity-text registry exceeds 16 MiB")
    return bytes(output)


def decode_intent_registry(data: bytes) -> tuple[tuple[int, bytes], ...]:
    """Strictly parse a registry using the same contract as the runtime DLL."""

    if len(data) > INTENT_REGISTRY_MAX_FILE_SIZE:
        raise IntentTextError("private activity-text registry exceeds 16 MiB")
    if len(data) < 12 or data[:4] != INTENT_REGISTRY_MAGIC:
        raise IntentTextError("private activity-text registry has invalid magic/header")
    version, count = struct.unpack_from("<II", data, 4)
    if version != INTENT_REGISTRY_VERSION:
        raise IntentTextError(
            f"unsupported private activity-text registry version: {version}"
        )
    if count > INTENT_REGISTRY_MAX_RECORDS:
        raise IntentTextError("private activity-text registry has too many records")
    offset = 12
    records: list[tuple[int, bytes]] = []
    previous_id = -1
    for ordinal in range(count):
        if offset + 8 > len(data):
            raise IntentTextError(
                f"private activity-text registry record {ordinal} is truncated"
            )
        runtime_id, length = struct.unpack_from("<II", data, offset)
        offset += 8
        if not INTENT_ID_BASE <= runtime_id < INTENT_ID_LIMIT:
            raise IntentTextError(
                f"private activity-text ID is outside the reserved range: 0x{runtime_id:08X}"
            )
        if runtime_id <= previous_id:
            raise IntentTextError(
                "private activity-text registry IDs are not strictly increasing"
            )
        if (
            length == 0
            or length > INTENT_REGISTRY_MAX_TEXT_SIZE
            or offset + length > len(data)
        ):
            raise IntentTextError(
                f"private activity-text registry record 0x{runtime_id:08X} has invalid length"
            )
        text = data[offset : offset + length]
        offset += length
        if b"\x00" in text:
            raise IntentTextError(
                f"private activity text 0x{runtime_id:08X} contains NUL"
            )
        text.decode("cp1252")
        records.append((runtime_id, text))
        previous_id = runtime_id
    if offset != len(data):
        raise IntentTextError("private activity-text registry contains trailing bytes")
    return tuple(records)


def _valid_expression_name(value: object) -> bool:
    if not isinstance(value, str) or len(value) < 2 or value[0] != "#":
        return False
    first = value[1]
    if not (first.isascii() and (first.isalpha() or first == "_")):
        return False
    return all(
        character.isascii() and (character.isalnum() or character == "_")
        for character in value[2:]
    )


__all__ = [
    "INTENT_ID_BASE",
    "INTENT_ID_LIMIT",
    "INTENT_REGISTRY_MAGIC",
    "INTENT_REGISTRY_ENV_VAR",
    "INTENT_REGISTRY_MAX_FILE_SIZE",
    "INTENT_REGISTRY_MAX_RECORDS",
    "INTENT_REGISTRY_MAX_TEXT_SIZE",
    "INTENT_REGISTRY_RELATIVE_PATH",
    "INTENT_REGISTRY_VERSION",
    "ActivityTextDiscoveryPackage",
    "IntegerExpressionEnvironment",
    "IntentTextError",
    "PrivateActivityTextBinding",
    "PrivateActivityTextRecord",
    "PrivateIntentTextRecord",
    "PrivateLiteralTextRecord",
    "allocate_private_literal_text_id",
    "allocate_private_activity_text_ids",
    "audit_private_activity_text_resolver_aliases",
    "collect_exact_integer_expressions",
    "collect_integer_expression_environment",
    "decode_intent_registry",
    "discover_private_activity_text_bindings",
    "encode_intent_registry",
    "rewrite_private_activity_text_resolver_calls",
    "rewrite_unowned_private_activity_text_resolver_calls",
]
