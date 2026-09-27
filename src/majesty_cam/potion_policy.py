"""Declarative Bazaar eligibility and paired stock-lifecycle transformations."""
from dataclasses import dataclass, asdict, replace
import re
import xml.etree.ElementTree as ET

from .gpl import DefinitionKind, SemanticMergeResult, parse_gpl, _mask_non_code
from .gameplay_events import stock_tokens, _TOKENS, require_callback

TYPE = "stock.bazaar-potion-policy.v1"
# Stock item identities, not private hero identities.
POTIONS = {
    "speed": ("One", "Speed_Tonic"), "fire-balm": ("Two", "Fire_Balm"),
    "strength": ("Three", "Strength_Potion"), "regeneration": ("Four", "Regeneration_Elixer"),
    "invisibility": ("Five", "Invisibility_Brew"), "shapeshift": ("Six", "Shapeshift_Potion"),
}


@dataclass(frozen=True)
class PotionPolicy:
    feature_key: str
    hero_title: str
    potions: dict
    shapeshift: dict
    private_actions: dict
    type: str = TYPE


def parse_feature(value):
    if set(value) != set(PotionPolicy.__dataclass_fields__) or value.get("type") != TYPE:
        raise ValueError("potion policy requires type, feature_key, hero_title, potions, shapeshift, private_actions")
    for field in ("feature_key", "hero_title"):
        if not isinstance(value[field], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_ .-]{0,63}", value[field]):
            raise ValueError(f"invalid potion policy {field}")
    potions, form, actions = value["potions"], value["shapeshift"], value["private_actions"]
    if not isinstance(potions, dict) or set(potions) != set(POTIONS) or any(type(v) is not bool for v in potions.values()):
        raise ValueError("potion policy needs all six boolean potion choices")
    if not isinstance(actions, dict) or set(actions) - set(POTIONS) or any(
        not isinstance(v, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", v) for v in actions.values()):
        raise ValueError("invalid private potion action mapping")
    if not isinstance(form, dict) or form.get("preset") not in ("stock", "dryad", "medusa", "minotaur", "custom"):
        raise ValueError("invalid shapeshift preset")
    if form["preset"] != "custom":
        if set(form) != {"preset"}:
            raise ValueError("stock shapeshift presets have no custom fields")
    else:
        if set(form) != {"preset", "unit_name", "adjustments", "heal"}:
            raise ValueError("custom form requires unit_name, adjustments and heal")
        if not isinstance(form["unit_name"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", form["unit_name"]):
            raise ValueError("invalid custom form unit name")
        if type(form["heal"]) is not int or not 0 <= form["heal"] <= 10000:
            raise ValueError("custom form heal must be 0..10000")
        if not isinstance(form["adjustments"], list) or not 1 <= len(form["adjustments"]) <= 32:
            raise ValueError("custom form requires 1..32 paired adjustments")
        seen = set()
        for row in form["adjustments"]:
            if not isinstance(row, dict) or set(row) != {"attribute", "amount", "mode"}:
                raise ValueError("custom adjustment requires attribute, amount and mode")
            if not isinstance(row["attribute"], str) or not re.fullmatch(r"ATTRIB_[A-Za-z0-9_]+", row["attribute"]):
                raise ValueError("custom adjustment requires a stock attribute constant")
            if row["attribute"].casefold() in ("attrib_hp", "attrib_hitpoints"):
                raise ValueError("use heal for HP; temporary HP subtraction is not stock cleanup")
            if row["attribute"].casefold() in seen or row["mode"] not in ("raw", "magical"):
                raise ValueError("duplicate attribute or invalid adjustment mode")
            seen.add(row["attribute"].casefold())
            if type(row["amount"]) is not int or not -10000 <= row["amount"] <= 10000 or not row["amount"]:
                raise ValueError("custom adjustment amount must be nonzero and bounded")
    return PotionPolicy(**{key: value[key] for key in PotionPolicy.__dataclass_fields__})


def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    return value


def selected(inventories):
    policies = {}
    for inv in inventories:
        definition = getattr(getattr(inv.selected, "package", None), "definition", None)
        for feature in getattr(definition, "runtime_features", ()):
            if not isinstance(feature, PotionPolicy):
                continue
            feature_mapping(feature)
            from .descriptions import parse_descriptions
            owned = [record.to_element() for path in inv.descriptions
                     for record in parse_descriptions(path.read_bytes()).records]
            if len([element for element in owned if element.get("type") == "Unit"
                    and element.get("subType") == "Character"
                    and element.get("Name", "").casefold() == feature.hero_title.casefold()]) != 1:
                raise ValueError("potion policy needs one package-owned Character named " + feature.hero_title)
            for name in feature.private_actions.values():
                if len([element for element in owned if element.get("type") == "Action"
                        and element.get("Name", "").casefold() == name.casefold()]) != 1:
                    raise ValueError("private potion action must be package-owned: " + name)
            title = feature.hero_title.casefold()
            if title in policies:
                raise ValueError(f"conflicting potion declarations for {feature.hero_title}")
            policies[title] = feature
    return tuple(policies[key] for key in sorted(policies))


@dataclass(frozen=True)
class Action:
    potion: str
    name: str
    effect: str
    validation: str
    key: str

    @property
    def validator(self):
        return "MM_BP_Validate_" + self.key.encode("ascii").hex()


@dataclass(frozen=True)
class Plan:
    policies: tuple = ()
    actions: tuple = ()


def prepare_descriptions(result, stock_records, policies):
    if not policies:
        return result, Plan()
    from .descriptions import parse_descriptions, serialize_descriptions
    records = dict(stock_records)
    records.update({r.key: r for r in result.document.records})
    for policy in policies:
        if policy.shapeshift["preset"] == "custom":
            name = policy.shapeshift["unit_name"].casefold()
            units = [r for key, r in records.items() if key[0] == "Unit"
                     and r.to_element().get("Name", "").casefold() == name]
            if len(units) != 1:
                raise ValueError("custom potion form requires one loaded Unit description: " + name)
    requested = {name.casefold(): potion for potion, (_, name) in POTIONS.items()}
    for policy in policies:
        for potion, name in policy.private_actions.items():
            if name.casefold() in requested and requested[name.casefold()] != potion:
                raise ValueError("one action cannot represent two different potions")
            requested[name.casefold()] = potion
    roots = {r.key: r.to_element() for r in result.document.records}
    actions, found = [], set()
    for key, record in records.items():
        element = record.to_element()
        name = element.get("Name", "")
        if key[0] != "Action" or name.casefold() not in requested:
            continue
        if name.casefold() in found:
            raise ValueError("ambiguous potion action name: " + name)
        found.add(name.casefold())
        scripts = element.findall("./Engine/Script")
        game = element.find("Game")
        if len(scripts) != 1 or scripts[0].get("cProc") != "0" or scripts[0].get("type") != "0" or game is None:
            raise ValueError("potion requires one stock GPL effect route: " + name)
        validations = game.findall("ValidationScript")
        if len(validations) > 1:
            raise ValueError("ambiguous potion validation: " + name)
        action = Action(requested[name.casefold()], name, scripts[0].get("GPLFunction", ""),
                        validations[0].get("value", "") if validations else "", key[1])
        if not action.effect:
            raise ValueError("missing potion effect callback")
        if not validations:
            validations = [ET.SubElement(game, "ValidationScript")]
        validations[0].set("value", action.validator)
        roots[key] = element
        actions.append(action)
    if found != set(requested):
        raise ValueError("potion action definitions missing: " + ", ".join(sorted(set(requested)-found)))
    root = ET.fromstring(result.payload)
    root[:] = [roots[key] for key in sorted(roots)]
    document = parse_descriptions(ET.tostring(root, encoding="utf-8"))
    return replace(result, document=document, payload=serialize_descriptions(document)), Plan(policies, tuple(actions))


def _replace_tokens(text, before, after):
    matches = [m for m in _TOKENS.finditer(text) if not m.group().startswith(("//", "/*"))]
    tokens, needle = stock_tokens(text), stock_tokens(before)
    positions = [i for i in range(len(tokens)-len(needle)+1) if tokens[i:i+len(needle)] == needle]
    if len(positions) != 1:
        raise ValueError("potion policy stock boundary is missing or ambiguous: " + before[:70])
    i = positions[0]
    return text[:matches[i].start()] + after + text[matches[i+len(needle)-1].end():]


def _begin(text, code):
    match = re.search(r"\bbegin\b", _mask_non_code(text), re.I)
    if not match:
        raise ValueError("potion callback body missing")
    return text[:match.end()] + "\n" + code + "\n" + text[match.end():]


def _form_block(text, preset):
    """Copy literal stock branch statements, not re-enter an effect callback."""
    target = {"dryad": 'if (thisagent\'s "AttackType" == 2)',
              "medusa": 'else if (title == "Priestess" || title == "Wizard" || title == "Healer")',
              "minotaur": "else"}[preset]
    tokens = stock_tokens(text)
    needle = stock_tokens(target)
    starts = [i+len(needle) for i in range(len(tokens)-len(needle))
              if tokens[i:i+len(needle)] == needle and tokens[i+len(needle)] == "begin"]
    if len(starts) != 1:
        raise ValueError("stock shapeshift branch is ambiguous")
    start = starts[0]
    end = tokens.index("end", start+1)
    # These stock branches are straight-line calls; refuse a changed lifecycle.
    if any(t in ("begin", "if", "return") for t in tokens[start+1:end]):
        raise ValueError("stock shapeshift branch changed")
    matches = [m for m in _TOKENS.finditer(text) if not m.group().startswith(("//", "/*"))]
    return text[matches[start].end():matches[end].start()]


def compose(result, plan, stock_loader, event_stock, *, native_loader=None):
    if not plan.policies:
        return result, event_stock
    items = {i.key: i for i in result.items}
    def fetch(name):
        key = (DefinitionKind.FUNCTION, name.casefold())
        if key not in items:
            items.update((native_loader or stock_loader)((name,)))
        if key not in items:
            raise ValueError("potion policy needs callback source: " + name)
        return items[key]
    def put(item, text):
        items[item.key] = replace(item, text=text, span=None)
    def add(text):
        for item in parse_gpl(text).items:
            if item.key in items:
                raise ValueError("potion generated symbol collision: " + item.name)
            items[item.key] = item
    body = []
    for policy in plan.policies:
        choices = []
        for potion, (number, _) in POTIONS.items():
            choices.append(f'if (Item == #Bazaar_Item_{number}) return {int(policy.potions[potion])};')
        body.append(f'if (ThisAgent\'s "Title" == "{policy.hero_title}") begin\n' + "\n".join(choices) + "\nend")
    add('function MM_BP_Eligibility(agent ThisAgent, integer Item) is integer\ndeclare\nbegin\n' + "\n".join(body) + '\nreturn -1;\nend')
    purchase = fetch("Bazaar_Item_Check")
    # Only wrap stock title restrictions. Existing extra package checks remain.
    restrictions = '''if ((thisagent's "title" == "cultist") && (item == #Bazaar_Item_Six)) return False;
if (item == #Bazaar_Item_Two)
if ((thisagent's "title" != "ranger") && (thisagent's "title" != "rogue") && (thisagent's "title" != "elf")) return False;'''
    text = _replace_tokens(purchase.text, restrictions,
        'if ($MM_BP_Eligibility(ThisAgent, item) == -1) begin\n' + restrictions + '\nend')
    put(purchase, _begin(text, 'if ($MM_BP_Eligibility(ThisAgent, item) == 0) return False;'))
    # Private stock shopping clones may choose a different item order/range.
    # Recognize their literal signature and unmodified stock purchase tail;
    # don't infer arbitrary functions from a name suffix or package identity.
    stock_check = stock_loader(("Bazaar_Item_Check",))[(DefinitionKind.FUNCTION, "bazaar_item_check")]
    tail_marker = stock_tokens('if ($AgentHasInventoryItem(item, ThisAgent))')
    def shopping_tail(source):
        tokens = stock_tokens(source)
        matches = [i for i in range(len(tokens)-len(tail_marker)+1) if tokens[i:i+len(tail_marker)] == tail_marker]
        return tokens[matches[0]:] if len(matches) == 1 else ()
    expected_tail = shopping_tail(stock_check.text)
    signature = r'\s*function\s+\w+\s*\(\s*agent\s+ThisAgent\s*,\s*integer\s+item\s*,\s*list\s+potentials\s*,\s*integer\s+Item_cost\s*\)\s+is\s+boolean\b'
    for candidate in tuple(items.values()):
        if candidate.key == purchase.key or candidate.kind is not DefinitionKind.FUNCTION:
            continue
        if re.match(signature, _mask_non_code(candidate.text), re.I) and shopping_tail(candidate.text) == expected_tail:
            put(candidate, _begin(candidate.text, 'if ($MM_BP_Eligibility(ThisAgent, item) == 0) return False;'))
    for potion, (number, _) in POTIONS.items():
        purchase = fetch("Purchase_Bazaar_Item_" + number)
        # Complete the existing shopping task without charging/granting an item
        # if eligibility changed while travelling or while loading an old save.
        put(purchase, _begin(purchase.text, f'''if ($MM_BP_Eligibility(ThisAgent, #Bazaar_Item_{number}) == 0)
begin
ThisAgent's "ActiveScript" = $Done_Purchasing_Market_Stuff;
return;
end'''))
    stock_shape = stock_loader(("Shapeshift_Potion_Effect", "Shapeshift_Potion_End"))
    original_effect = stock_shape[(DefinitionKind.FUNCTION, "shapeshift_potion_effect")]
    original_end = stock_shape[(DefinitionKind.FUNCTION, "shapeshift_potion_end")]
    expiry = fetch("Shapeshift_Potion_End")
    if stock_tokens(expiry.text) != stock_tokens(original_end.text):
        from .gameplay_events import _additive_title_reference
        native_effect = (native_loader or stock_loader)(("Shapeshift_Potion_Effect",)).get(original_effect.key, original_effect)
        effect_proof = _additive_title_reference(original_effect.text, native_effect.text)
        end_proof = _additive_title_reference(original_end.text, expiry.text)
        if (effect_proof is None or end_proof is None or effect_proof[1] != end_proof[1]
                or stock_tokens(end_proof[0]) != stock_tokens(expiry.text)):
            raise ValueError("Shapeshift_Potion_End must retain matching stock cleanup; migrate custom branches to potion-policy declarations")
    def branches(cleanup):
        rows = []
        for policy in plan.policies:
            form = policy.shapeshift
            preset = form["preset"]
            if preset == "stock":
                continue
            if preset != "custom":
                code = _form_block(original_end.text if cleanup else original_effect.text, preset)
            else:
                code = "" if cleanup else f'$ChangeUnitType(ThisAgent, "{form["unit_name"]}");\n'
                for adjustment in form["adjustments"]:
                    function = "MagicalAdjustAttribute" if adjustment["mode"] == "magical" else "AdjustAttribute"
                    amount = adjustment["amount"] * (-1 if cleanup else 1)
                    code += f'${function}(ThisAgent, #{adjustment["attribute"]}, {amount});\n'
                if not cleanup and form["heal"]:
                    code += f'$AdjustAttribute(ThisAgent, #ATTRIB_HP, {form["heal"]});\n'
            rows.append(f'if (title == "{policy.hero_title}") begin\n{code}\nend else ')
        return "\n".join(rows)
    anchor = 'if (thisagent\'s "AttackType" == 2)'
    from .gpl_function_merge import merge_function
    def transform(current, original, changed):
        # Preserve native/custom instructions through the existing instruction
        # merger. Never treat a modified script as the stock reference itself.
        return merge_function(original, {'selected script': current, 'Manager potion policy': changed})
    put(expiry, transform(expiry.text, original_end.text,
                          _replace_tokens(original_end.text, anchor, branches(True) + anchor)))
    updated_events = dict(event_stock)
    updated_events[expiry.normalized_name] = items[expiry.key]
    used_effects = {}
    for action in plan.actions:
        number = POTIONS[action.potion][0]
        effect = fetch(action.effect)
        require_callback(effect, action.effect, ("agent", "agent"))
        if action.effect.casefold() in used_effects:
            if used_effects[action.effect.casefold()] != (action.potion, action.name.casefold()):
                raise ValueError("private potion actions need distinct callbacks with their own consumption identity")
        else:
            text = effect.text
            if action.potion == "shapeshift":
                expected = re.sub(r'\bShapeshift_Potion_Effect\b', action.effect, original_effect.text, count=1, flags=re.I)
                expected = expected.replace('"Shapeshift_Potion"', '"' + action.name + '"')
                if stock_tokens(effect.text) != stock_tokens(expected):
                    from .gameplay_events import _additive_title_reference
                    effect_proof = _additive_title_reference(expected, effect.text)
                    end_proof = _additive_title_reference(original_end.text, expiry.text)
                    if (effect_proof is None or end_proof is None or effect_proof[1] != end_proof[1]
                            or stock_tokens(effect_proof[0]) != stock_tokens(effect.text)
                            or stock_tokens(end_proof[0]) != stock_tokens(expiry.text)):
                        raise ValueError(action.effect + ': source must retain matching stock effect/cleanup; '
                                         'migrate custom branches to potion-policy declarations')
                text = _replace_tokens(expected, anchor, branches(False) + anchor)
            guard = f'if ($MM_BP_Eligibility(ThisAgent, #Bazaar_Item_{number}) == 0) return;'
            # Keep stock dead-caster guard ahead of all added access to the hero.
            dead = 'if ($IsDead(ThisAgent)) return;'
            text = _replace_tokens(text, dead, dead + '\n' + guard)
            if action.potion == "shapeshift":
                text = transform(effect.text, expected, text)
            put(effect, text)
            used_effects[action.effect.casefold()] = (action.potion, action.name.casefold())
            if effect.normalized_name not in updated_events and action.name.casefold() != POTIONS[action.potion][1].casefold():
                stock_name = POTIONS[action.potion][1] + "_Effect"
                baseline = stock_loader((stock_name,))[(DefinitionKind.FUNCTION, stock_name.casefold())]
                baseline_text = re.sub(r'\b' + re.escape(stock_name) + r'\b', action.effect, baseline.text, count=1, flags=re.I)
                baseline_text = re.sub('"' + re.escape(POTIONS[action.potion][1]) + '"', '"' + action.name + '"', baseline_text, flags=re.I)
                updated_events[effect.normalized_name] = replace(baseline, name=effect.name, text=baseline_text)
            if effect.normalized_name in updated_events:
                baseline = updated_events[effect.normalized_name]
                baseline_text = baseline.text
                if action.potion == "shapeshift":
                    baseline_text = _replace_tokens(baseline_text, anchor, branches(False) + anchor)
                updated_events[effect.normalized_name] = replace(baseline, text=_replace_tokens(baseline_text, dead, dead + '\n' + guard))
        fallback = "1"
        if action.validation:
            validation = fetch(action.validation)
            # Validation is integer-valued stock GPL, never a second effect call.
            if not re.match(r'\s*function\s+' + re.escape(action.validation) +
                            r'\s*\(\s*agent\s+\w+\s*\)\s+is\s+integer\b', _mask_non_code(validation.text), re.I):
                raise ValueError("potion validation must return integer: " + action.validation)
            fallback = f'${action.validation}(ThisAgent)'
        add(f'''function {action.validator}(agent ThisAgent) is integer
declare
begin
if ($IsDead(ThisAgent)) return 0;
if ($MM_BP_Eligibility(ThisAgent, #Bazaar_Item_{number}) == 0) return 0;
return {fallback};
end''')
    return SemanticMergeResult(tuple(items.values()), result.conflicts), updated_events
