"""Composition-time typed calls for declared function-valued attributes.

No interpreter hook: stock function equality selects a statically typed call.
Missing-attribute/invalid-function policy stays in the caller.
"""
from dataclasses import dataclass, asdict
import re

PROVIDER_TYPE = "stock.typed-boolean-provider.v1"
DISPATCH_TYPE = "stock.typed-boolean-dispatch.v1"
FEATURE_TYPES = frozenset((PROVIDER_TYPE, DISPATCH_TYPE))
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_ARG_TYPES = frozenset(("agent", "string", "integer", "boolean", "location", "list"))


@dataclass(frozen=True)
class TypedBooleanProvider:
    feature_key: str
    attribute: str
    parameter_types: tuple[str, ...]
    callback_symbol: str
    type: str = PROVIDER_TYPE


@dataclass(frozen=True)
class TypedBooleanDispatch:
    feature_key: str
    attribute: str
    parameter_types: tuple[str, ...]
    dispatch_symbol: str
    type: str = DISPATCH_TYPE


FEATURE_CLASSES = (TypedBooleanProvider, TypedBooleanDispatch)


def parse_feature(value):
    kind = value.get("type")
    symbol_key = "callback_symbol" if kind == PROVIDER_TYPE else "dispatch_symbol"
    if kind not in FEATURE_TYPES or set(value) != {
            "type", "feature_key", "attribute", "parameter_types", symbol_key}:
        raise ValueError("typed provider/dispatch requires its exact versioned field set")
    for key in ("feature_key", "attribute", symbol_key):
        if not isinstance(value[key], str) or not _SYMBOL.fullmatch(value[key]):
            raise ValueError(f"typed provider {key} must be a bounded identifier")
    if value[symbol_key].casefold().startswith("mm_"):
        raise ValueError("typed provider symbols must not use reserved MM_ names")
    args = value["parameter_types"]
    if not isinstance(args, (tuple, list)) or not 1 <= len(args) <= 8 or any(
            not isinstance(arg, str) or arg not in _ARG_TYPES for arg in args):
        raise ValueError("typed provider requires 1..8 supported GPL parameter types")
    cls = TypedBooleanProvider if kind == PROVIDER_TYPE else TypedBooleanDispatch
    return cls(value["feature_key"], value["attribute"], tuple(args), value[symbol_key])


def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    value["parameter_types"] = list(feature.parameter_types)
    return value


def dispatch_source(feature, providers):
    args = ", ".join(f"{kind} Arg{i}" for i, kind in enumerate(feature.parameter_types))
    values = ", ".join(f"Arg{i}" for i in range(len(feature.parameter_types)))
    lines = [f"function {feature.dispatch_symbol}(function Provider, {args}) is boolean",
             "declare", "begin"]
    for callback in sorted(providers, key=str.casefold):
        lines += [f"    if (Provider == ${callback})", f"        return ${callback}({values});"]
    lines += ["    return False;", "end", ""]
    return "\n".join(lines)


def _installed_bindings(tokens, active):
    for i, token in enumerate(tokens):
        attr = token.strip('"').casefold()
        if attr in active:
            if i and tokens[i-1] == "(" and i+2 < len(tokens) and tokens[i+2] == ")":
                yield attr, tokens[i+1]  # DAT initializer.
            else:
                end = i+1
                while end < len(tokens) and tokens[end] == ")":
                    end += 1
                if end < len(tokens) and tokens[end] == "=":
                    target = (tokens[end+2] if end+3 < len(tokens)
                              and tokens[end+1] == "$" and tokens[end+3] == ";" else None)
                    yield attr, target
        if token != "addattribute" or tokens[i+1:i+2] != ("(",):
            continue
        args, current, depth = [], [], 0
        for part in tokens[i+2:]:
            if part == ")" and depth == 0:
                args.append(tuple(current))
                break
            if part == "," and depth == 0:
                args.append(tuple(current))
                current = []
                continue
            if part == "(":
                depth += 1
            elif part == ")":
                depth -= 1
            current.append(part)
        if len(args) >= 4 and len(args[1]) == 1:
            attr = args[1][0].strip('"').casefold()
            if attr in active and args[2] == ('"function"',):
                target = args[3][1] if len(args[3]) == 2 and args[3][0] == "$" else None
                yield attr, target


def compose_dispatches(packages):
    """packages: (owner, features, parsed sources), including undeclared packages."""
    from .gpl import DefinitionKind, parse_gpl
    from .gameplay_events import require_callback, stock_tokens
    packages = tuple(packages)
    providers, dispatches, signatures, all_functions, keys = {}, [], {}, {}, set()
    for owner, features, sources in packages:
        functions = {}
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    functions.setdefault(item.normalized_name, []).append(item)
                    all_functions.setdefault(item.normalized_name, []).append(owner)
        for feature in features:
            feature_mapping(feature)
            key = (owner, feature.type, feature.feature_key.casefold())
            if key in keys:
                raise ValueError(f"duplicate typed provider declaration: {key}")
            keys.add(key)
            attr = feature.attribute.casefold()
            signature = signatures.setdefault(attr, feature.parameter_types)
            if signature != feature.parameter_types:
                raise ValueError(f"typed provider signature disagreement for {feature.attribute}")
            if isinstance(feature, TypedBooleanDispatch):
                dispatches.append(feature)
            else:
                callback = feature.callback_symbol
                matches = functions.get(callback.casefold(), ())
                if len(matches) != 1:
                    raise ValueError(f"{owner}: typed provider {callback} requires one package-owned function")
                require_callback(matches[0], callback, feature.parameter_types, True)
                slots = providers.setdefault(attr, {})
                if callback.casefold() in slots:
                    raise ValueError(f"duplicate typed provider {callback}")
                slots[callback.casefold()] = (owner, callback)
    for slots in providers.values():
        for name, (owner, _) in slots.items():
            if all_functions.get(name) != [owner]:
                raise ValueError(f"typed provider {name} is also defined by another selected package")
    # Audit literal installation sites across every selected source, not only
    # packages that chose to declare providers. Reject computed bindings: their
    # complete set of possible targets cannot be proved at preparation time.
    active = {feature.attribute.casefold() for feature in dispatches}
    for owner, _, sources in packages:
        for source in sources:
            for item in source.items:
                tokens = stock_tokens(item.text)
                for attr, target in _installed_bindings(tokens, active):
                    if (target not in providers.get(attr, {}) or
                            providers[attr][target][0] != owner):
                        raise ValueError(f"{owner}: undeclared or computed provider binding for {attr}: {target}")
    generated, exports = [], set()
    for feature in sorted(dispatches, key=lambda f: f.dispatch_symbol.casefold()):
        symbol = feature.dispatch_symbol.casefold()
        if symbol in all_functions or symbol in exports:
            raise ValueError(f"typed dispatch export collides with package function: {feature.dispatch_symbol}")
        exports.add(symbol)
        generated.extend(parse_gpl(dispatch_source(feature,
            [callback for _, callback in providers.get(feature.attribute.casefold(), {}).values()])).items)
    return tuple(generated)
