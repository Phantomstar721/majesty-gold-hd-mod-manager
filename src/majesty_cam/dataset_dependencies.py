"""Keep Any-dataset GPL patches independent of expansion-only stock bindings.

Stock loads Bytecode + MX_Compatibility for original quests and adds the four
remaining projects for expansion quests. Expressions are runtime bindings, not
compiler-inlined constants. Import only referenced, base-absent stock bindings;
never replace an existing base-game or selected-mod definition.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from functools import lru_cache
from pathlib import Path
import re
from typing import Callable, Optional
from .stock_input_cache import StockInputCache

from .gpl import DefinitionKind, SemanticItem, SemanticMergeResult, _mask_non_code, parse_gpl
from .stock_gpl import (
    STOCK_GPL_RUNTIME_PAIRS, StockGplError, _BASE_MANIFEST, _EXPANSION_MANIFEST,
    _StockSnapshot, _capture_file, _validate_runtime_manifests,
    _require_safe_file, _safe_declared_relative, _PROJECT_ROW,
    _ancestor_source_parse,
)

_REF = re.compile(r'([#$][A-Za-z_][A-Za-z_0-9]*)')
_EXPR = re.compile(r'(?im)^[ \t]*expression[ \t]+#[A-Za-z_][A-Za-z_0-9]*\b[^\r\n]*')
_FUNCTION = re.compile(r'(?im)^\s*function\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(')
_DATASET_CACHE = StockInputCache()


@dataclass(frozen=True)
class DatasetSymbols:
    base_expressions: frozenset[str]
    expansion_expressions: dict[str, SemanticItem]
    base_functions: frozenset[str]
    expansion_functions: frozenset[str]
    function_loader: Optional[Callable[[str], SemanticItem]] = None
    base_function_loader: Optional[Callable[[str], SemanticItem]] = None


def stock_dependency_paths(game_path: Path) -> tuple[Path, ...]:
    """Explicit project inputs only: no recursive scan or compiler invocation."""
    paths = [_BASE_MANIFEST, _EXPANSION_MANIFEST]
    for pair in STOCK_GPL_RUNTIME_PAIRS:
        project = Path('SDK/OriginalQuests') / pair.project_relative
        paths.append(project)
        for role, relative in _project_rows(str(_require_safe_file(game_path, project)),
                                            (game_path / project).read_bytes()):
            if role == 'source':
                paths.append(project.parent / relative)
    return tuple(dict.fromkeys(paths))


@lru_cache(maxsize=32)
def _project_rows(path: str, payload: bytes):
    rows = []
    for number, line in enumerate(payload.decode('cp1252').splitlines(), 1):
        if not line.strip():
            continue
        match = _PROJECT_ROW.fullmatch(line)
        if match is None:
            raise StockGplError(f'{path}:{number}: unsupported stock project row')
        rows.append((match[1].casefold(), _safe_declared_relative(match[2], context=path)))
    return tuple(rows)


@lru_cache(maxsize=512)
def _symbols(path: str, payload: bytes):
    text = payload.decode('cp1252')
    masked = _mask_non_code(text)
    expressions = []
    for match in _EXPR.finditer(masked):
        # Use original text so string-valued constants retain their literal.
        expressions.extend(parse_gpl(text[match.start():match.end()] + '\n', path).items)
    return (tuple(expressions), frozenset(n.casefold() for n in _FUNCTION.findall(masked)),
            frozenset(n.casefold() for n in _REF.findall(masked) if n.startswith('#')))


def load_dataset_symbols(game_path: Path) -> DatasetSymbols:
    root = game_path.resolve(strict=True)
    return _DATASET_CACHE.get(root, 'symbols',
        lambda: tuple(root / p for p in stock_dependency_paths(root)),
        lambda: _load_dataset_symbols(root))


def _load_dataset_symbols(root: Path) -> DatasetSymbols:
    manifests = tuple(_capture_file(root, p) for p in (_BASE_MANIFEST, _EXPANSION_MANIFEST))
    _validate_runtime_manifests(_StockSnapshot(root, manifests, ''))
    expressions = {}; functions = set(); payloads = {}; function_sources = {}
    base_expressions = frozenset(); base_functions = frozenset(); base_function_sources = {}
    for index, pair in enumerate(STOCK_GPL_RUNTIME_PAIRS):
        project = Path('SDK/OriginalQuests') / pair.project_relative
        project_path = _require_safe_file(root, project)
        for role, relative in _project_rows(str(project_path), project_path.read_bytes()):
            if role != 'source':
                continue
            path = _require_safe_file(root, project.parent / relative)
            if path not in payloads:
                payloads[path] = path.read_bytes()
            expr, funcs, _ = _symbols(str(path), payloads[path])
            expressions.update((item.normalized_name, item) for item in expr)
            functions.update(funcs)
            function_sources.update((name, (str(path), payloads[path])) for name in funcs)
        if index == 1:  # Base includes MX_Compatibility, not just Bytecode.
            base_expressions = frozenset(expressions)
            base_functions = frozenset(functions)
            base_function_sources = dict(function_sources)
    def function_loader(name: str) -> SemanticItem:
        path, payload = function_sources[name]
        return _ancestor_source_parse(path, payload).require(DefinitionKind.FUNCTION, name)

    def base_function_loader(name: str) -> SemanticItem:
        path, payload = base_function_sources[name]
        return _ancestor_source_parse(path, payload).require(DefinitionKind.FUNCTION, name)

    return DatasetSymbols(base_expressions, expressions, base_functions, frozenset(functions),
                          function_loader, base_function_loader)


def close_dataset_dependencies(result: SemanticMergeResult, stock: DatasetSymbols, *, provided=None, dataset='any') -> SemanticMergeResult:
    """Link absent stock helpers transitively without changing their lifecycle.

    Loading a GPL function defines it; it does not execute its body. Existing
    callers, thread assignments, callbacks and cleanup remain exactly as stock.
    Only missing names are added, never expansion replacements for base names.
    """
    result.require_clean()
    if dataset not in ('any', 'majesty', 'majestyexpansion'):
        raise ValueError(f'unsupported dependency dataset: {dataset}')
    available_expr = stock.expansion_expressions if dataset == 'majestyexpansion' else stock.base_expressions
    available_funcs = stock.expansion_functions if dataset == 'majestyexpansion' else stock.base_functions
    owned_expr = {i.normalized_name for i in result.items if i.kind is DefinitionKind.EXPRESSION}
    owned_funcs = {i.normalized_name for i in result.items if i.kind is DefinitionKind.FUNCTION}
    added = {}; visiting = set(); errors = set(); added_functions = {}

    def expression(name: str, chain: str):
        if name in available_expr or name in owned_expr or name in added:
            return
        item = stock.expansion_expressions.get(name)
        if item is None:
            # Native VM and quest-defined bindings are not declared in these
            # six projects. This audit proves only stock dataset dependencies.
            return
        if provided is not None and provided((DefinitionKind.EXPRESSION, name)) is not None:
            return
        if name in visiting:
            errors.add(f'{chain}: cyclic stock expression dependency {name}')
            return
        visiting.add(name)
        body = re.sub(r'^\s*expression\s+#[\w]+', '', _mask_non_code(item.text), flags=re.I)
        # Expressions containing function evaluation are behavior, not constants.
        if '$' in body:
            errors.add(f'{chain}: expansion expression {name} requires function evaluation; '
                       'provide an explicit base-game-compatible definition')
        value_tokens = re.sub(r'#[A-Za-z_][A-Za-z_0-9]*', '', body)
        value_tokens = re.sub(r'\b(?:true|false|0x[0-9a-f]+|[0-9]+(?:\.[0-9]*)?(?:e[+-]?[0-9]+)?)\b',
                              '', value_tokens, flags=re.I)
        if re.search(r'[^\s()+*/%<>=!&|~^.,;:\-]', value_tokens):
            errors.add(f'{chain}: expansion expression {name} is not a static stock value; '
                       'provide an explicit base-game-compatible definition')
        for ref in _REF.findall(body):
            if ref.startswith('#'):
                expression(ref.casefold(), f'{chain} -> {name}')
        visiting.remove(name)
        added[name] = item

    pending = deque(result.items)
    while pending:
        item = pending.popleft()
        for ref in _REF.findall(_mask_non_code(item.text)):
            name = ref.casefold()
            if name.startswith('#'):
                expression(name, f'{item.source_name}: {item.name}')
            elif (name[1:] in stock.expansion_functions
                  and name[1:] not in available_funcs
                  and name[1:] not in owned_funcs
                  and name[1:] not in added_functions):
                if provided is not None and provided((DefinitionKind.FUNCTION, name[1:])) is not None:
                    continue
                if stock.function_loader is None:
                    errors.add(f'{item.source_name}: {item.name}: stock source for expansion-only function '
                               f'{ref} is unavailable')
                    continue
                helper = stock.function_loader(name[1:])
                if helper.kind is not DefinitionKind.FUNCTION or helper.normalized_name != name[1:]:
                    raise ValueError(f'stock dependency loader returned a different function for {ref}')
                # Register before traversing: recursion between functions is
                # legal, unlike a cycle between constant expression values.
                added_functions[name[1:]] = helper
                pending.append(helper)
    if errors:
        raise ValueError('Base-game GPL compatibility:\n' + '\n'.join(sorted(errors)))
    return SemanticMergeResult((*result.items, *added.values(), *added_functions.values()), result.conflicts)
