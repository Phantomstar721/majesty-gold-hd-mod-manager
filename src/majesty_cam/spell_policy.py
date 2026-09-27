"""Opt-in guards at owned stock-shaped spell callbacks; no damage interception."""
from dataclasses import asdict, dataclass
import re

from .gpl import DefinitionKind, SemanticMergeResult, _mask_non_code, parse_gpl

PROVIDER = "stock.spell-policy-provider.v1"
IMPACT = "stock.direct-projectile-impact.v1"
SPECIAL = "stock.special-spell.v1"
DISCOVERY = "stock.spell-policy-discovery.v1"
FEATURE_TYPES = frozenset((PROVIDER, IMPACT, SPECIAL, DISCOVERY))
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
BLOCK = "MM_BlockDirectProjectile"
SUPPRESS = "MM_SpecialSpellSuppressed"


@dataclass(frozen=True)
class SpellPolicyProvider:
    feature_key: str
    policy: str
    callback_symbol: str
    type: str = PROVIDER


@dataclass(frozen=True)
class DirectProjectileImpact:
    feature_key: str
    callback_symbol: str
    type: str = IMPACT


@dataclass(frozen=True)
class SpecialSpell:
    feature_key: str
    action_name: str
    validation_callback_symbol: str
    cast_callback_symbol: str
    type: str = SPECIAL


@dataclass(frozen=True)
class SpellPolicyDiscovery:
    feature_key: str
    suppression_exempt_actions: tuple[str, ...]
    suppression_special_actions: tuple[str, ...]
    already_guarded_direct_callbacks: tuple[str, ...]
    physical_projectile_callbacks: tuple[str, ...]
    area_or_periodic_projectile_callbacks: tuple[str, ...]
    other_exempt_projectile_callbacks: tuple[str, ...]
    direct_projectile_callbacks: tuple[str, ...]
    type: str = DISCOVERY


FEATURE_CLASSES = (SpellPolicyProvider, DirectProjectileImpact, SpecialSpell, SpellPolicyDiscovery)


def parse_feature(value):
    cls = {PROVIDER: SpellPolicyProvider, IMPACT: DirectProjectileImpact,
           SPECIAL: SpecialSpell, DISCOVERY: SpellPolicyDiscovery}.get(value.get("type"))
    if cls is None or set(value) != set(cls.__dataclass_fields__):
        raise ValueError("spell policy declaration requires its exact versioned field set")
    for key, val in value.items():
        if key in ("type", "policy"):
            continue
        if cls is SpellPolicyDiscovery and key != "feature_key":
            if (not isinstance(val, (list, tuple)) or len(val) > 512 or
                    any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ -]{0,127}", s) for s in val)
                    or len({s.casefold() for s in val}) != len(val)):
                raise ValueError(f"spell discovery {key} must be distinct bounded names")
            continue
        pattern = _KEY if key == "feature_key" else _SYMBOL
        if not isinstance(val, str) or not pattern.fullmatch(val):
            raise ValueError(f"spell policy {key} must be a bounded identifier")
        if key.endswith("symbol") and val.casefold().startswith("mm_"):
            raise ValueError("spell policy callbacks cannot use reserved MM_ names")
    if cls is SpellPolicyProvider and value["policy"] not in (
            "block-direct-projectile", "suppress-special-spell"):
        raise ValueError("unsupported spell policy")
    if cls is SpellPolicyDiscovery:
        value = {k: tuple(v) if isinstance(v, (list, tuple)) else v for k, v in value.items()}
    return cls(**value)


def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    if isinstance(feature, SpellPolicyDiscovery):
        value = {k: list(v) if isinstance(v, tuple) else v for k, v in value.items()}
    return value


def validate_action(feature, descriptions, owner="composed"):
    matches = [e for e in descriptions if e.get("type") == "Action"
               and e.get("Name", "").casefold() == feature.action_name.casefold()]
    if len(matches) != 1:
        raise ValueError(f"{owner}: special spell needs one Action: {feature.action_name}")
    validation = matches[0].findall("./Game/ValidationScript")
    scripts = matches[0].findall("./Engine/Script")
    if (len(validation) != 1 or validation[0].get("value", "").casefold() != feature.validation_callback_symbol.casefold()
            or len(scripts) != 1 or scripts[0].get("GPLFunction", "").casefold() != feature.cast_callback_symbol.casefold()
            or scripts[0].get("cProc") != "0" or scripts[0].get("type") != "0"):
        raise ValueError(f"{owner}: {feature.action_name} must bind its declared stock-shaped validation and cast callbacks")


def signature(item, types, returns=""):
    """Return actual argument names and body entry, never assume author's names."""
    args = r"\s*,\s*".join(kind + r"\s+([A-Za-z_][A-Za-z0-9_]*)" for kind in types)
    result = r"\s+is\s+" + returns if returns else ""
    masked = _mask_non_code(item.text)
    match = re.match(r"\s*function\s+" + re.escape(item.name) + r"\s*\(\s*" +
                     args + r"\s*\)" + result + r"\s*(?:declare\b[\s\S]*?)?\bbegin\b",
                     masked, re.I)
    if not match:
        raise ValueError(f"{item.name}: expected ({', '.join(types)}) {returns or 'void'} callback")
    return match.groups(), match.end()


def validate_bindings(packages):
    """packages: (owner, declarations, parsed sources, effective XML elements)."""
    packages = tuple(packages)
    functions, bindings, keys, owned_targets, actions = {}, [], set(), set(), set()
    for owner, _, sources, _ in packages:
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    functions.setdefault(item.normalized_name, []).append((owner, item))
    for owner, features, _, descriptions in packages:
        def own(symbol, types, returns=""):
            found = functions.get(symbol.casefold(), ())
            if len(found) != 1 or found[0][0] != owner:
                raise ValueError(f"{owner}: {symbol} requires exactly one package-owned function")
            signature(found[0][1], types, returns)

        for feature in features:
            feature_mapping(feature)
            key = (owner, feature.type, feature.feature_key.casefold())
            if key in keys:
                raise ValueError(f"duplicate spell policy declaration: {key}")
            keys.add(key)
            if isinstance(feature, SpellPolicyDiscovery):
                bindings.append((owner, feature))
                continue
            if isinstance(feature, SpellPolicyProvider):
                types = ("agent", "agent") if feature.policy == "block-direct-projectile" else ("agent", "string")
                own(feature.callback_symbol, types, "boolean")
                target = ("provider", feature.callback_symbol.casefold())
                if target in owned_targets:
                    raise ValueError(f"duplicate spell policy provider: {feature.callback_symbol}")
                owned_targets.add(target)
            else:
                targets = ((feature.callback_symbol, ("agent", "agent"), ""),) if isinstance(feature, DirectProjectileImpact) else (
                    (feature.validation_callback_symbol, ("agent",), "integer"),
                    (feature.cast_callback_symbol, ("agent", "agent"), ""))
                for symbol, types, returns in targets:
                    own(symbol, types, returns)
                    target = ("consumer", symbol.casefold())
                    if target in owned_targets:
                        raise ValueError(f"spell policy callback is registered twice: {symbol}")
                    owned_targets.add(target)
                if isinstance(feature, SpecialSpell):
                    name = feature.action_name.casefold()
                    if name in actions:
                        raise ValueError(f"special spell action is registered twice: {feature.action_name}")
                    actions.add(name)
                    validate_action(feature, descriptions, owner)
            bindings.append((owner, feature))
    for name in (BLOCK, SUPPRESS):
        if name.casefold() in functions:
            raise ValueError(f"generated spell policy symbol collides with package function: {name}")
    # A provider must never also be a guarded entry (would recurse).
    if {name for kind, name in owned_targets if kind == "provider"} & {
            name for kind, name in owned_targets if kind == "consumer"}:
        raise ValueError("spell policy providers cannot also be guarded consumers")
    return tuple(sorted(bindings, key=lambda b: (b[0], b[1].type, b[1].feature_key.casefold())))


def compose_guards(result, bindings, stock_loader=None):
    """Guards run before payload; the original callback body remains literal."""
    if not bindings:
        return result
    result.require_clean()
    providers = {policy: sorted({f.callback_symbol for _, f in bindings
                  if isinstance(f, SpellPolicyProvider) and f.policy == policy}, key=str.casefold)
                 for policy in ("block-direct-projectile", "suppress-special-spell")}
    impacts = [f for _, f in bindings if isinstance(f, DirectProjectileImpact)]
    specials = [f for _, f in bindings if isinstance(f, SpecialSpell)]
    items = {item.key: item for item in result.items}

    def guard(name, types, returns, make_line):
        key = (DefinitionKind.FUNCTION, name.casefold())
        item = items.get(key)
        if item is None:
            raise ValueError(f"missing composed spell callback: {name}")
        args, position = signature(item, types, returns)
        text = item.text[:position] + "\n    " + make_line(args) + "\n" + item.text[position:]
        items[key] = parse_gpl(text).require(DefinitionKind.FUNCTION, name)

    def generate(symbol, args, lines):
        key = (DefinitionKind.FUNCTION, symbol.casefold())
        if key in items:
            raise ValueError(f"generated spell policy symbol collision: {symbol}")
        text = f"function {symbol}({args}) is boolean\ndeclare\nbegin\n" + "\n".join(lines) + "\n    return False;\nend\n"
        items[key] = parse_gpl(text).require(DefinitionKind.FUNCTION, symbol)

    if impacts and providers["block-direct-projectile"]:
        generate(BLOCK, "agent Source, agent Target", [f"    if (${p}(Source, Target)) return True;"
                 for p in providers["block-direct-projectile"]])
        for feature in impacts:
            guard(feature.callback_symbol, ("agent", "agent"), "",
                  lambda a: f"if (${BLOCK}({a[0]}, {a[1]})) return;")
    if specials and providers["suppress-special-spell"]:
        lines = []
        for feature in sorted(specials, key=lambda f: f.action_name.casefold()):
            lines += [f'    if (SpellName == "{feature.action_name}")', "    begin"]
            lines += [f"        if (${p}(Caster, SpellName)) return True;" for p in providers["suppress-special-spell"]]
            lines += ["        return False;", "    end"]
        generate(SUPPRESS, "agent Caster, string SpellName", lines)
        for feature in specials:
            guard(feature.validation_callback_symbol, ("agent",), "integer",
                  lambda a, f=feature: f'if (${SUPPRESS}({a[0]}, "{f.action_name}")) return 0;')
            if feature.cast_callback_symbol:
                guard(feature.cast_callback_symbol, ("agent", "agent"), "",
                      lambda a, f=feature: f'if (${SUPPRESS}({a[0]}, "{f.action_name}")) return;')
        cast_key = (DefinitionKind.FUNCTION, "cast")
        if cast_key not in items:
            if stock_loader is None:
                raise ValueError("special spell guards require the installed stock Cast function")
            stock = stock_loader(("cast",))
            if cast_key not in stock:
                raise ValueError("installed stock Cast function is missing")
            items[cast_key] = stock[cast_key]
        guard("Cast", ("agent", "string", "agent", "string"), "",
              lambda a: f"if (${SUPPRESS}({a[0]}, {a[1]})) return;")
    return SemanticMergeResult(tuple(items.values()), result.conflicts)
