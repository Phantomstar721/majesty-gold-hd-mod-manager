"""Carry an explicit source through synchronous source-stripping GPL helpers."""
from dataclasses import dataclass, asdict
import hashlib
import re

from .gpl import DefinitionKind, SemanticMergeResult, _mask_non_code, parse_gpl
from .spell_policy import signature

FEATURE_TYPE = "stock.source-context-dispatch.v1"
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


@dataclass(frozen=True)
class SourceContextDispatch:
    feature_key: str
    target_symbol: str
    parameter_types: tuple[str, ...]
    callback_symbol: str
    type: str = FEATURE_TYPE


def parse_feature(value):
    if set(value) != set(SourceContextDispatch.__dataclass_fields__) or value.get("type") != FEATURE_TYPE:
        raise ValueError("source-context dispatch requires its exact versioned fields")
    for key in ("feature_key", "target_symbol", "callback_symbol"):
        name = value[key]
        if not isinstance(name, str) or not _SYMBOL.fullmatch(name) or name.casefold().startswith("mm_"):
            raise ValueError(f"source-context {key} must be an unreserved bounded identifier")
    args = value["parameter_types"]
    if (not isinstance(args,(tuple,list)) or not 1 <= len(args) <= 7
            or any(t not in ("agent","integer","string","boolean","location","list") for t in args)):
        raise ValueError("source-context dispatch requires 1..7 GPL parameter types")
    if value["target_symbol"].casefold() == value["callback_symbol"].casefold():
        raise ValueError("source-context adapter cannot replace itself")
    return SourceContextDispatch(value["feature_key"],value["target_symbol"],tuple(args),value["callback_symbol"])


def feature_mapping(feature):
    data = asdict(feature)
    parse_feature(data)
    data["parameter_types"] = list(feature.parameter_types)
    return data


def validate_bindings(packages):
    functions, result, targets = {}, [], set()
    packages = tuple(packages)
    for owner, _, sources in packages:
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    functions.setdefault(item.normalized_name, []).append((owner,item))
    for owner, features, _ in packages:
        for feature in features:
            feature_mapping(feature)
            found = functions.get(feature.callback_symbol.casefold(),())
            if len(found) != 1 or found[0][0] != owner:
                raise ValueError("source-context adapter requires one package-owned function: " + feature.callback_symbol)
            signature(found[0][1],("agent",*feature.parameter_types))
            if feature.target_symbol.casefold() in targets:
                raise ValueError("competing source-context adapters for " + feature.target_symbol)
            targets.add(feature.target_symbol.casefold())
            result.append(feature)
    if targets & {f.callback_symbol.casefold() for f in result}:
        raise ValueError("source-context adapters cannot also be dispatch targets")
    return tuple(sorted(result,key=lambda f:f.target_symbol.casefold()))


_CALL = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_HEADER = re.compile(r"\s*function\s+(\w+)\s*\(\s*([^)]*)\)",re.I)


def compose(result, features, roots, loader):
    """roots are actual XML/DAT native callback names with source at arg 0.

    Only synchronous call paths to selected targets are cloned. Native callbacks,
    original helpers and unrelated call sites keep their ABI. No global context.
    """
    if not features:
        return result
    functions = {i.normalized_name:i for i in result.items if i.kind is DefinitionKind.FUNCTION}
    original = dict(functions)
    targets = {f.target_symbol.casefold():f for f in features}
    barriers = {f.callback_symbol.casefold() for f in features}
    def get(name):
        if name not in functions:
            item = loader(name) if loader else None
            if item is not None:
                functions[name] = item
        return functions.get(name)
    for name, feature in targets.items():
        item = get(name)
        if item is None:
            raise ValueError("source-context target has no verifiable GPL body: " + name)
        signature(item,feature.parameter_types)
    edges = {}
    pending = list(sorted(set(n.casefold() for n in roots)))
    while pending:
        name = pending.pop()
        if name in edges or name in targets or name in barriers:
            continue
        item = get(name)
        edges[name] = set()
        if item is None:
            continue
        for call in _CALL.finditer(_mask_non_code(item.text)):
            child = call[1].casefold()
            if child in barriers:
                continue
            if child in targets or get(child) is not None:
                edges[name].add(child)
                pending.append(child)
    needed = set(targets)
    while True:
        added = {name for name, children in edges.items() if children & needed} - needed
        if not added:
            break
        needed.update(added)
    root_names = set(n.casefold() for n in roots) & needed
    if not root_names:
        return result
    def clone(name):
        return "MM_SC_"+hashlib.sha256(name.encode("ascii")).hexdigest()[:24]
    generated = {}
    def rewrite(item, source, rename=False):
        masked = _mask_non_code(item.text)
        edits = []
        for call in _CALL.finditer(masked):
            child = call[1].casefold()
            if child not in needed or child in barriers:
                continue
            symbol = targets[child].callback_symbol if child in targets else clone(child)
            separator = "" if masked[call.end():].lstrip().startswith(")") else ", "
            edits.extend(((call.start(1),call.end(1),symbol), (call.end(),call.end(),source+separator)))
        header = _HEADER.match(masked)
        if header is None:
            raise ValueError("source-context callback has an unrecognized signature: " + item.name)
        if rename:
            if re.search(r"\bMM_SourceContext\b", masked,re.I):
                raise ValueError("source-context reserved parameter collision: " + item.name)
            edits.extend(((header.start(1),header.end(1),clone(item.normalized_name)),
                          (header.start(2),header.start(2),"agent MM_SourceContext"+(", " if header[2].strip() else ""))))
        text = item.text
        for start,end,replacement in sorted(edits,reverse=True):
            text = text[:start]+replacement+text[end:]
        return parse_gpl(text).items[0]
    # Clone every reachable helper, even if it also serves as a native root.
    # Calls from a root to another root still transport the original source.
    clone_names = set().union(*(children & needed for name,children in edges.items() if name in needed)) - set(targets)
    for name in sorted(clone_names):
        if name not in functions:
            continue
        item = rewrite(functions[name],"MM_SourceContext",True)
        if item.normalized_name in original:
            raise ValueError("source-context generated symbol collision: " + item.name)
        generated[item.key] = item
    for name in sorted(root_names):
        item = functions[name]
        header = _HEADER.match(_mask_non_code(item.text))
        first = re.match(r"agent\s+(\w+)(?:\s*,|\s*$)",header[2],re.I) if header else None
        if first is None:
            raise ValueError("source-context root requires a native source agent as argument zero: " + item.name)
        generated[item.key] = rewrite(item,first[1])
    items = {i.key:i for i in result.items}
    items.update(generated)
    return SemanticMergeResult(tuple(items.values()),result.conflicts)
