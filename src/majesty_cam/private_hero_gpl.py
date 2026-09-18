"""Opt-in stock-derived hero integration, composed only into selected sources."""
from __future__ import annotations

from dataclasses import replace
import re

from .gpl import DefinitionKind, SemanticMergeResult, _mask_non_code, hero_quest_anchor_matches
from .gpl_features import StockHeroQuestParticipant, StockSpellEvaluationEquivalent
from .gpl_function_merge import _Parser, _tokens


def validate_bindings(packages):
    """Return private trees and spell declarations; reject cross-owner aliases.

    Packages are (owner, features, semantic sources, Description elements).
    No provider symbols are added by this validation or by a participant alone.
    """
    trees, spells, seen_spells = {}, [], set()
    for owner, features, sources, descriptions in packages:
        functions = [item for source in sources for item in source.items
                     if item.kind is DefinitionKind.FUNCTION]
        for feature in features:
            if isinstance(feature, StockHeroQuestParticipant):
                key = feature.hero_script.casefold()
                matches = [item for item in functions if item.normalized_name == key]
                if len(matches) != 1 or key in trees:
                    raise ValueError(f"{owner}: quest participant {feature.hero_script} requires exactly one private owned function")
                hero_quest_anchor_matches(matches[0], feature.stock_hero_script)
                trees[key] = (feature.stock_hero_script, matches[0])
            elif isinstance(feature, StockSpellEvaluationEquivalent):
                for name, kind, subtype in ((feature.private_spell, "Action", None),
                                            (feature.hero_title, "Unit", "Character")):
                    matches = [item for item in descriptions if item.get("Name", "").casefold() == name.casefold()
                               and item.get("type") == kind and (subtype is None or item.get("subType") == subtype)]
                    if len(matches) != 1:
                        raise ValueError(f"{owner}: spell evaluation requires one package-owned {kind}/{name}")
                key = feature.hero_title.casefold(), feature.private_spell.casefold()
                if key in seen_spells:
                    raise ValueError(f"{owner}: duplicate private spell evaluation binding {key}")
                seen_spells.add(key)
                spells.append(feature)
    return trees, tuple(sorted(spells, key=lambda item: (item.hero_title.casefold(), item.private_spell.casefold())))


def _spell_clauses(stock):
    signature, declarations, body = _Parser(stock.text).function()
    if (signature != _tokens("function spell_extra_value(agent thisagent) is integer")
            or declarations != {"value": "integer"}):
        raise ValueError("stock spell_extra_value signature or local state is not recognized")
    result = {}
    for node in body[:-1]:
        h = node.head
        if (node.kind != "if" or len(h) != 11 or
                h[:6] != ("if", "(", "$isspellavailable", "(", "thisagent", ",") or
                h[7:] != (",", "1", ")", ")") or not re.fullmatch(r'"[A-Za-z_][A-Za-z_0-9]*"', h[6]) or
                node.otherwise or len(node.body) != 1 or node.body[0].kind != "statement"):
            raise ValueError("stock spell_extra_value availability clause is not recognized")
        change = node.body[0].head
        if len(change) != 4 or change[:2] != ("value", "+=") or not change[2].isdigit() or change[3] != ";":
            raise ValueError("stock spell_extra_value weight is not recognized")
        key = h[6][1:-1].casefold()
        if key in result:
            raise ValueError("stock spell_extra_value repeats a spell")
        result[key] = int(change[2])
    if not body or body[-1].head != ("return", "value", ";"):
        raise ValueError("stock spell_extra_value has no terminal value return")
    return result


def add_spell_evaluation_equivalents(result: SemanticMergeResult, features, stock):
    """Append stock mode-1 clauses before the shared final return, never replace it."""
    if not features:
        return result
    result.require_clean()
    if stock is None:
        raise ValueError("spell equivalents require installed stock spell_extra_value")
    weights = _spell_clauses(stock)
    matches = [item for item in result.items if item.key == stock.key]
    if len(matches) > 1:
        raise ValueError("spell_extra_value has multiple resolved definitions")
    target = matches[0] if matches else stock
    signature, declarations, body = _Parser(target.text).function()
    if signature != _tokens("function spell_extra_value(agent thisagent) is integer") or declarations.get("value") != "integer":
        raise ValueError("shared spell_extra_value changed its stock signature or value local")
    returns = list(re.finditer(r"\breturn\b", _mask_non_code(target.text), re.I))
    if len(returns) != 1 or not body or body[-1].head != ("return", "value", ";"):
        raise ValueError("shared spell_extra_value must retain exactly one terminal return value")
    tokens = {token.casefold() for token in _tokens(target.text)}
    insertions = []
    for feature in features:
        weight = weights.get(feature.stock_spell.casefold())
        if weight is None or feature.private_spell.casefold() in weights:
            raise ValueError(f"{feature.feature_key}: requires a private spell and a recognized stock evaluation analogue")
        if ('"' + feature.private_spell.casefold() + '"') in tokens:
            raise ValueError(f"{feature.private_spell}: shared spell_extra_value already contains this spell; remove the duplicate authored clause")
        insertions.append(
            f'if (ThisAgent\'s "title" == "{feature.hero_title}")\n'
            f'\t\tif ($IsSpellAvailable(ThisAgent,"{feature.private_spell}",1))\n'
            f'\t\t\tvalue += {weight};\n\n\t')
    offset = returns[0].start()
    text = target.text[:offset] + "".join(insertions) + target.text[offset:]
    updated = replace(target, text=text, span=None, source_name="<stock private-spell evaluation composition>")
    items = tuple(updated if item.key == target.key else item for item in result.items)
    return SemanticMergeResult(items if matches else (*items, updated), result.conflicts)
