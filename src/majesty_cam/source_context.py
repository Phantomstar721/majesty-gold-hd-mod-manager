"""Carry an explicit source through synchronous source-stripping GPL helpers."""
from dataclasses import dataclass, asdict
import hashlib
import re

from .gpl import DefinitionKind, SemanticMergeResult, _mask_non_code, parse_gpl
from .gpl_function_merge import FunctionMergeError, _Parser, _tokens
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


_DEFERRED_DISPATCH = frozenset((
    "newthread", "runthread", "setthreadinterval", "resumethread",
    "performaction", "cast", "castspell", "createeffector", "createspellunit",
    "spawnunit", "createunit", "createagent",
))


def _require_synchronous(item):
    """Reject explicit dispatch that cannot carry a synchronous GPL parameter.

    This is a source-call contract, not an effect analysis of native functions.
    Inspect the reachable GPL closure, including side helpers: a direct payout
    must not hide an additional function-valued or scheduled payout beside it.
    Target/adapter bodies are the explicit end of this transport contract.
    """
    try:
        _Parser(item.text).function()
        tokens = _tokens(item.text)
    except FunctionMergeError as exc:
        raise ValueError("source-context cannot prove synchronous source: " + item.name) from exc
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token == ")" and following == "(":
            raise ValueError("source-context dynamic dispatch is not synchronous transport: " + item.name)
        if token.startswith("$"):
            if following != "(":
                raise ValueError("source-context function-valued dispatch is not synchronous transport: " + item.name)
            if token[1:] in _DEFERRED_DISPATCH:
                raise ValueError("source-context asynchronous dispatch is not supported: " + item.name + " -> " + token)


def compose(result, features, roots, loader, *, namespace="MM_SC", strict=False):
    """roots are actual XML/DAT native callback names with source at arg 0.

    Only synchronous call paths to selected targets are cloned. Native callbacks,
    original helpers and unrelated call sites keep their ABI. No global context.

    Internal users may supply isolated roots whose first argument is an already
    proved source. A namespace separates independent adapters over the same
    helper. Strict mode requires every root to reach a target through explicit
    synchronous GPL calls and rejects dynamic/function-valued or native deferred
    dispatch in that reachable source closure. It does not infer native effects.
    """
    if not features:
        return result
    if not isinstance(namespace, str) or not re.fullmatch(r"MM_[A-Za-z0-9_]{1,36}", namespace, re.I):
        raise ValueError("source-context namespace must be a bounded reserved MM_ identifier")
    features = tuple(features)
    roots = tuple(sorted(set(n.casefold() for n in roots)))
    if strict and not roots:
        raise ValueError("source-context requires at least one verifiable source root")
    functions = {i.normalized_name:i for i in result.items if i.kind is DefinitionKind.FUNCTION}
    original = dict(functions)
    targets = {f.target_symbol.casefold():f for f in features}
    barriers = {f.callback_symbol.casefold() for f in features}
    missing = set()
    if strict and (len(targets) != len(features) or targets.keys() & barriers):
        raise ValueError("source-context targets and adapters must be distinct")
    def get(name):
        if name not in functions and name not in missing:
            item = loader(name) if loader else None
            if item is not None:
                functions[name] = item
            else:
                missing.add(name)
        return functions.get(name)
    for name, feature in targets.items():
        item = get(name)
        if item is None:
            raise ValueError("source-context target has no verifiable GPL body: " + name)
        signature(item,feature.parameter_types)
        if strict:
            callback = get(feature.callback_symbol.casefold())
            if callback is None:
                raise ValueError("source-context adapter has no verifiable GPL body: " + feature.callback_symbol)
            signature(callback, ("agent", *feature.parameter_types))
    if strict:
        for name in roots:
            if name in targets or name in barriers or get(name) is None:
                raise ValueError("source-context requires a distinct verifiable source root: " + name)
    edges = {}
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in edges or name in targets or name in barriers:
            continue
        item = get(name)
        edges[name] = set()
        if item is None:
            continue
        if strict:
            _require_synchronous(item)
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
    root_names = set(roots) & needed
    if strict and set(roots) != root_names:
        raise ValueError("source-context target is not synchronously reachable from root: " +
                         ", ".join(sorted(set(roots) - root_names)))
    if not root_names:
        return result
    def clone(name):
        return namespace+"_"+hashlib.sha256(name.encode("ascii")).hexdigest()[:24]
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
        if item.normalized_name in original or (strict and get(item.normalized_name) is not None):
            raise ValueError("source-context generated symbol collision: " + item.name)
        generated[item.key] = item
    for name in sorted(root_names):
        item = functions[name]
        header = _HEADER.match(_mask_non_code(item.text))
        first = re.match(r"agent\s+(\w+)(?:\s*,|\s*$)",header[2],re.I) if header else None
        if first is None:
            raise ValueError("source-context root requires a native source agent as argument zero: " + item.name)
        if strict:
            tokens = _tokens(item.text)
            source = first[1].casefold()
            if any(token == source and tokens[index + 1:index + 2] in
                   (("=",), ("+=",), ("-=",), ("*=",), ("/=",))
                   for index, token in enumerate(tokens)):
                raise ValueError("source-context root reassigns its source agent: " + item.name)
        generated[item.key] = rewrite(item,first[1])
    items = {i.key:i for i in result.items}
    items.update(generated)
    return SemanticMergeResult(tuple(items.values()),result.conflicts)
