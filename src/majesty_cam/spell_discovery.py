"""Provider-owned policy applied to selected, unmodified consumer XML/GPL."""
from dataclasses import dataclass, replace
import hashlib
import re
import xml.etree.ElementTree as ET

from .gpl import DefinitionKind, SemanticMergeResult, parse_gpl, _mask_non_code
from .descriptions import parse_descriptions, serialize_descriptions
from .spell_policy import (SpellPolicyDiscovery, SpellPolicyProvider, SpecialSpell,
    DirectProjectileImpact, signature, compose_guards)


@dataclass(frozen=True)
class Action:
    name: str
    validation: str
    cast: str
    native_begin: str = ""

    def wrapper(self, kind):
        return "MM_SP_" + kind + "_" + hashlib.sha256(self.name.casefold().encode("utf-8")).hexdigest()[:20]

    def begin_source(self):
        return (f"function {self.wrapper('Begin')}(agent Caster, agent Target) is integer\n"
                f"declare\ninteger Result;\nbegin\nResult = 0;\n"
                f'if ($MM_SpecialSpellSuppressed(Caster, "{self.name}")) return 0;\n'
                f"${self.native_begin}(Result, Caster, Target);\nreturn Result;\nend\n")


@dataclass(frozen=True)
class Plan:
    impacts: tuple[str, ...] = ()
    actions: tuple[Action, ...] = ()


def discover(bindings, descriptions, *, placements=()):
    policies = [f for _, f in bindings if isinstance(f, SpellPolicyDiscovery)]
    providers = {f.policy for _, f in bindings if isinstance(f, SpellPolicyProvider)}
    if not providers or not (policies or placements):
        return Plan()
    fields = [k for k in SpellPolicyDiscovery.__dataclass_fields__ if k not in ("type", "feature_key")]
    groups = {k: {n.casefold() for p in policies for n in getattr(p, k)} for k in fields}
    exempt = groups["suppression_exempt_actions"]
    special = groups["suppression_special_actions"]
    # A checked-placement declaration certifies a private stock Teleport clone.
    # Its spell class comes from that typed contract, never from a mod/name list.
    placement_actions = {f.action.casefold(): f for f in placements}
    if len(placement_actions) != len(placements):
        raise ValueError("duplicate checked-placement spell action")
    special = special | set(placement_actions)
    skipped = set().union(*(groups[k] for k in fields if k.endswith("callbacks") and k != "direct_projectile_callbacks"))
    direct = groups["direct_projectile_callbacks"]
    if exempt & special or skipped & direct:
        raise ValueError("selected spell policies disagree about special/direct versus excluded content")
    actions, impacts, missing = {}, set(), []
    for element in descriptions:
        name = element.get("Name", "")
        key = name.casefold()
        if element.get("type") == "Action" and "suppress-special-spell" in providers:
            if not policies and key not in placement_actions:
                continue
            flags = element.find("./Game/Flags")
            is_spell = flags is not None and "isspell" in flags.get("value", "").casefold().split()
            if key in exempt or not (is_spell or key in special):
                continue
            if key not in special:
                missing.append("Action " + name)
                continue
            if key in actions:
                raise ValueError(f"spell policy action name is ambiguous: {name}")
            validations = element.findall("./Game/ValidationScript")
            scripts = element.findall("./Engine/Script")
            if len(validations) > 1 or len(scripts) > 1:
                raise ValueError(f"spell policy cannot establish validation/execution for {name}")
            script = scripts[0] if scripts else None
            if script is None and element.find("./Engine/Projectile") is None:
                raise ValueError(f"spell policy has no stock execution route for {name}")
            cast = script.get("GPLFunction", "") if script is not None and script.get("cProc") == "0" and script.get("type") == "0" else ""
            placement = placement_actions.get(key)
            if placement and cast.casefold() != placement.release_callback_symbol.casefold():
                raise ValueError("checked-placement spell release differs from its declaration")
            actions[key] = Action(name, validations[0].get("value", "") if validations else "", cast,
                                  placement.api_prefix + "_Begin" if placement else "")
        if policies and element.get("subType") == "Projectile" and "block-direct-projectile" in providers:
            for script in element.findall("./Engine/Script"):
                callback = script.get("GPLFunction", "")
                if script.get("cProc") != "0" or not callback:
                    continue
                if callback.casefold() in skipped:
                    continue
                if script.get("type") != "0" or callback.casefold() not in direct:
                    missing.append("Projectile " + name + " callback " + callback)
                    continue
                impacts.add(callback)
    if missing:
        raise ValueError("spell policy needs provider classification (basic/physical/area cannot be guessed): " + "; ".join(sorted(set(missing))))
    # An impact also used outside projectile descriptors is ambiguous. Refuse to
    # turn a generic damage/area/active callback into a projectile-only boundary.
    for element in descriptions:
        if element.get("subType") == "Projectile":
            continue
        for script in element.findall("./Engine/Script"):
            if script.get("GPLFunction", "").casefold() in {n.casefold() for n in impacts}:
                raise ValueError("direct projectile callback is also used outside Projectile: " + script.get("GPLFunction"))
    return Plan(tuple(sorted(impacts, key=str.casefold)), tuple(actions[k] for k in sorted(actions)))


def transform_descriptions(result, plan):
    if not plan.actions:
        return result
    actions = {a.name.casefold(): a for a in plan.actions}
    root = ET.fromstring(result.payload)
    for element in root:
        action = actions.get(element.get("Name", "").casefold()) if element.get("type") == "Action" else None
        if action is None or action.native_begin:
            continue
        game = element.find("Game")
        if game is None:
            raise ValueError(f"special action {action.name} lacks Game data")
        validation = game.find("ValidationScript")
        if validation is None:
            validation = ET.SubElement(game, "ValidationScript")
        validation.set("value", action.wrapper("Validate"))
        if action.cast:
            element.find("./Engine/Script").set("GPLFunction", action.wrapper("Cast"))
    document = parse_descriptions(ET.tostring(root, encoding="utf-8"))
    return replace(result, document=document, payload=serialize_descriptions(document),
                   selections=tuple(replace(s, record=document.index[s.key]) for s in result.selections))


def compose_discovered(result, bindings, plan, stock_loader):
    if not plan.actions and not plan.impacts:
        return compose_guards(result,bindings,stock_loader)
    items = {i.key:i for i in result.items}
    def function(name, types, returns="", import_body=False):
        key = (DefinitionKind.FUNCTION, name.casefold())
        item = items.get(key)
        if item is None and stock_loader is not None:
            item = stock_loader((name,)).get(key)
        if item is None:
            raise ValueError(f"discovered spell callback has no verifiable source: {name}")
        signature(item,types,returns)
        if import_body:
            items[key] = item
        return item
    def add(source):
        for item in parse_gpl(source).items:
            if item.key in items:
                raise ValueError("generated spell wrapper collides with source: " + item.name)
            items[item.key] = item
    derived = []
    for callback in plan.impacts:
        function(callback,("agent","agent"),import_body=True)
        derived.append(("<discovery>",DirectProjectileImpact(callback,callback)))
    for action in plan.actions:
        if action.native_begin:
            function(action.cast,("agent","agent"))
            # All GPL callers use the same admission guard. Keep native aliases,
            # XML release identity and native cast observation unchanged.
            pattern = re.compile(r"\$" + re.escape(action.native_begin) + r"\b", re.I)
            arguments = re.compile(r"\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
                                   r"([A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
                                   r"([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;", re.I)
            for key, item in tuple(items.items()):
                text = item.text
                for match in reversed(tuple(pattern.finditer(_mask_non_code(text)))):
                    args = arguments.match(_mask_non_code(text), match.end())
                    if args is None:
                        raise ValueError("checked-placement Begin policy requires a direct call with three local arguments")
                    output, caster, target = args.groups()
                    text = (text[:match.start()] + f"{output} = ${action.wrapper('Begin')}({caster}, {target});"
                            + text[args.end():])
                if text != item.text:
                    items[key] = replace(item, text=text)
            add(action.begin_source())
            derived.append(("<placement>", SpecialSpell(action.name,action.name,"",action.cast)))
            continue
        fallback = "1"
        if action.validation:
            function(action.validation,("agent",),"integer")
            fallback = "$" + action.validation + "(Caster)"
        add(f"function {action.wrapper('Validate')}(agent Caster) is integer\ndeclare\nbegin\nreturn {fallback};\nend\n")
        if action.cast:
            function(action.cast,("agent","agent"))
            add(f"function {action.wrapper('Cast')}(agent Caster, agent Target)\ndeclare\nbegin\n${action.cast}(Caster, Target);\nend\n")
        derived.append(("<discovery>", SpecialSpell(action.name,action.name,action.wrapper("Validate"),
                                                   action.wrapper("Cast") if action.cast else "")))
    return compose_guards(SemanticMergeResult(tuple(items.values()),result.conflicts),
                          (*bindings,*derived),stock_loader)
