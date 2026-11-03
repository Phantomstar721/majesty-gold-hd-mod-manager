"""Bounded attack-observer declarations and effective-output ownership proof."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re

from .gpl import DefinitionKind
from .gameplay_events import stock_tokens
from .spell_policy import signature

FEATURE_TYPE = "stock.attack-projectile-observation.v1"
CAPABILITY = "manager.attack-projectile-observation.v1"
MAX_IDENTITY = 2097151
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")

# Argument zero is an output integer reference where indicated; these are
# native procedures, not return-valued GPL wrapper functions.
EXPORT_ARGUMENTS = (
    ("AttackSettled", ("out integer", "agent")),
    ("ReleaseId", ("out integer", "agent", "agent")),
    ("ImpactId", ("out integer", "agent", "agent")),
    ("BeginShotSnapshot", ("out integer", "agent")),
    ("ShotPending", ("out integer", "agent", "integer", "integer")),
    ("EndShotSnapshot", ("integer",)),
    ("PayloadFull", ("agent", "agent", "integer")),
    ("ShotRetired", ("out integer", "agent", "agent", "integer", "integer")),
)


@dataclass(frozen=True)
class AttackObservation:
    feature_key: str
    api_prefix: str
    actor: str
    action: str
    projectile: str
    release_callback_symbol: str
    type: str = FEATURE_TYPE


def parse_feature(value):
    if (not isinstance(value, dict) or set(value) != set(AttackObservation.__dataclass_fields__)
            or value.get("type") != FEATURE_TYPE):
        raise ValueError("attack observation requires its exact versioned fields; offsets and code are forbidden")
    for key in set(value) - {"type"}:
        name = value[key]
        pattern = _KEY if key == "feature_key" else _SYMBOL
        if not isinstance(name, str) or not pattern.fullmatch(name) or name.casefold().startswith("mm_"):
            raise ValueError(f"attack observation {key} must be an unreserved bounded identifier")
    if len(value["api_prefix"]) > 46:
        raise ValueError("attack observation api_prefix must be at most 46 characters")
    result = AttackObservation(**value)
    if result.release_callback_symbol.casefold() in {name.casefold() for name, _ in exports(result)}:
        raise ValueError("release callback cannot replace an observer export")
    return result


def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    return value


def exports(feature):
    return tuple((feature.api_prefix + "_" + suffix, args) for suffix, args in EXPORT_ARGUMENTS)


def selected(inventories):
    return any(isinstance(f, AttackObservation) for inventory in inventories
               for f in getattr(getattr(getattr(inventory.selected, "package", None),
                                       "definition", None), "runtime_features", ()))


def declared(definition):
    return any(isinstance(f, AttackObservation) for f in getattr(definition, "runtime_features", ()))


def require_exact_profile(executable):
    """Central PE identity preflight; native startup guards complete code bodies.

    Retain the internal entry name for existing callers. An unrelated supported
    QoL edit no longer invalidates a whole-file hash. This does not replace the
    native observer/cast/action body checks or effective-content admission.
    """
    from .manager.runtime_profiles import require_supported_runtime
    require_supported_runtime(executable)


@dataclass(frozen=True)
class Binding:
    owner: str
    feature: AttackObservation
    # Actual emitted definitions, not an isolated prototype's BCD digest.
    descriptions: tuple
    release_tokens: tuple
    impact_tokens: tuple


def _description_index(records, relevant=None):
    result = {}
    for record in records:
        element = record.to_element()
        key = (element.get("type", "").casefold(), element.get("Name", "").casefold())
        if relevant is not None and key not in relevant:
            continue
        if key in result:
            raise ValueError("ambiguous observer Description: " + str(key))
        result[key] = record
    return result


def _shape(record):
    # Preserve child order and every attribute; ignore XML indentation only.
    def tree(element):
        return (element.tag, tuple(sorted(element.attrib.items())),
                (element.text or "").strip(), tuple(tree(child) for child in element))
    return tree(record.to_element())


def validate_bindings(packages, effective_descriptions, effective_functions):
    """Validate package ownership against the actual post-merge definitions.

    packages: (owner, declarations, DescriptionRecords, parsed GPL sources).
    Effective inputs must come from the final emitted output, after resolution.
    An unchanged stock projectile is allowed, but its complete emitted record
    is bound into the proof. No source package may assert an address or digest.
    """
    packages = tuple(packages)
    relevant = {(kind, name.casefold()) for _, features, _, _ in packages for feature in features
                for kind, name in (("unit",feature.actor),("action",feature.action),("unit",feature.projectile))}
    effective = _description_index(effective_descriptions, relevant)
    functions = {}
    for item in effective_functions:
        if item.kind is DefinitionKind.FUNCTION:
            if item.normalized_name in functions:
                raise ValueError("ambiguous effective observer callback: " + item.name)
            functions[item.normalized_name] = item
    owners, description_owners, declared, prefixes, actors = {}, {}, [], set(), set()
    for owner, features, records, sources in packages:
        own = _description_index(records, relevant)
        for key in own:
            description_owners.setdefault(key, []).append(owner)
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    owners.setdefault(item.normalized_name, []).append((owner, item))
        for feature in features:
            feature_mapping(feature)
            prefix = feature.api_prefix.casefold()
            if prefix in prefixes or feature.actor.casefold() in actors:
                raise ValueError("observer API prefixes and actors must have one owner")
            prefixes.add(prefix)
            actors.add(feature.actor.casefold())
            declared.append((owner, feature, own))
    result = []
    for owner, feature, own in declared:
        records = []
        for index, (kind, name) in enumerate((("unit", feature.actor), ("action", feature.action), ("unit", feature.projectile))):
            key = (kind, name.casefold())
            record = effective.get(key)
            if record is None:
                raise ValueError("missing effective observer Description: " + name)
            if index < 2 and (key not in own or description_owners[key] != [owner]):
                raise ValueError("observer actor/action must be package-owned: " + name)
            if key in own and _shape(record) != _shape(own[key]):
                raise ValueError("observer Description overridden in generated output: " + name)
            records.append(record)
        actor, action, projectile = (r.to_element() for r in records)
        if (actor.get("subType") != "Character" or action.get("subType") != "Standard"
                or projectile.get("subType") != "Projectile"):
            raise ValueError("observer requires a Character actor, Standard action and Projectile")
        engine = action.find("Engine")
        if engine is None or engine.find("Projectile") is None or engine.find("Projectile").get("value") != feature.projectile:
            raise ValueError("observer action/projectile mapping differs from generated output")
        script = engine.find("Script")
        if (script is None or script.attrib != {"type": "0", "cProc": "0", "GPLFunction": feature.release_callback_symbol}
                or engine.find("Effect") is not None):
            raise ValueError("observer requires the declared direct release callback without an action effect")
        impact = projectile.find("Engine/Script")
        if impact is None or impact.attrib != {"type": "0", "cProc": "0", "GPLFunction": "make_attack"}:
            raise ValueError("observer projectile must retain the stock make_attack dispatch route")
        name = feature.release_callback_symbol.casefold()
        matches = owners.get(name, ())
        if len(matches) != 1 or matches[0][0] != owner or name not in functions:
            raise ValueError("observer release callback requires one package-owned and emitted function")
        callback = functions[name]
        signature(callback, ("agent", "agent"))
        if stock_tokens(callback.text) != stock_tokens(matches[0][1].text):
            raise ValueError("observer release callback overridden in generated output")
        for export, _ in exports(feature):
            if export.casefold() in owners or export.casefold() in functions:
                raise ValueError("GPL function collides with native observer export: " + export)
        if "make_attack" not in functions:
            raise ValueError("effective make_attack function is missing")
        signature(functions["make_attack"], ("agent", "agent"))
        result.append(Binding(owner, feature, tuple(records), stock_tokens(callback.text),
                              stock_tokens(functions["make_attack"].text)))
    return tuple(sorted(result, key=lambda item: (item.owner, item.feature.feature_key.casefold())))
