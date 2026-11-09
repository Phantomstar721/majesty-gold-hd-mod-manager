"""Adapt declared boolean actions to the stock external integer result ABI."""
import hashlib
import re


def bridge_symbol(callback: str, *, paired: bool = False) -> str:
    identity = callback.casefold() + (":building-hero" if paired else "")
    return "MM_Action_" + hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def bridge_source(callback: str, *, paired: bool = False) -> str:
    parameters = "agent Building, agent Hero" if paired else "agent Subject"
    arguments = "Building, Hero" if paired else "Subject"
    return f'''function {bridge_symbol(callback, paired=paired)}({parameters}) is integer
declare
begin
    if (${callback}({arguments})) return 1;
    return 0;
end
'''


def add_bridges(result, inventories):
    from .gpl import parse_gpl, SemanticMergeResult
    from .stock_controller_features import StockMx04Mx05OccupantActionPanel, StockMx05LiveAgentListPanel, StockAp10Ap69SecondaryPanel
    callbacks = {(feature.action_callback_symbol.casefold(),
                  getattr(feature, "action_agent_scope", "selected-row") == "parent-and-selected-row"):
                 feature.action_callback_symbol
                 for inventory in inventories
                 for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                                "definition", None), "runtime_features", ())
                 if isinstance(feature, (StockMx04Mx05OccupantActionPanel, StockMx05LiveAgentListPanel))}
    items = list(result.items)
    for inventory in inventories:
        for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                       "definition", None), "runtime_features", ()):
            if isinstance(feature, StockAp10Ap69SecondaryPanel) and feature.eligibility_callback_symbol:
                name = feature.eligibility_callback_symbol
                callbacks[(name.casefold(), False)] = name
    existing = {item.normalized_name for item in items}
    for key in sorted(callbacks):
        callback = callbacks[key]
        paired = key[1]
        symbol = bridge_symbol(callback, paired=paired)
        if symbol.casefold() in existing:
            raise ValueError(f"generated action bridge collides with authored symbol: {symbol}")
        items.extend(parse_gpl(bridge_source(callback, paired=paired)).items)
        existing.add(symbol.casefold())
    from .stock_controller_features import StockAp10Ap69SecondaryPanel
    from .panel_commands import adapter_symbol, adapter_source
    commands = {command.callback_symbol for inventory in inventories
                for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                               "definition", None), "runtime_features", ())
                if isinstance(feature, StockAp10Ap69SecondaryPanel)
                for command in feature.commands}
    for callback in sorted(commands, key=str.casefold):
        for commit in (False, True, None):
            symbol = adapter_symbol(callback, commit)
            if symbol.casefold() in existing:
                raise ValueError(f"panel command adapter collision: {symbol}")
            items.extend(parse_gpl(adapter_source(callback, commit)).items)
            existing.add(symbol.casefold())
    from .stock_controller_features import StockAp99ResearchRow
    from .queued_building_action import symbol as queued_symbol, source as queued_source
    for inventory in inventories:
        for feature in getattr(getattr(getattr(inventory.selected, 'package', None),
                                       'definition', None), 'runtime_features', ()):
            if not isinstance(feature, StockAp99ResearchRow) or not feature.charge_ms:
                continue
            name = queued_symbol(feature).casefold()
            if name in existing:
                raise ValueError('queued action adapter collision: ' + name)
            items.extend(parse_gpl(queued_source(feature)).items)
            existing.add(name)
    return SemanticMergeResult(tuple(items), result.conflicts)


def validate_bridge(symbol, functions, counts, *, paired=False):
    from .gameplay_events import stock_tokens
    from .gpl import parse_gpl, DefinitionKind
    text = functions.get(symbol.casefold(), "")
    calls = re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    if len(calls) != 1 or bridge_symbol(calls[0], paired=paired).casefold() != symbol.casefold():
        raise ValueError(f"generated action bridge is missing or invalid: {symbol}")
    callback = calls[0]
    if stock_tokens(text) != stock_tokens(bridge_source(callback, paired=paired)):
        raise ValueError(f"generated action bridge body was changed: {symbol}")
    for name in (symbol, callback):
        if counts.get(name.casefold(), 0) != 1:
            raise ValueError(f"action bridge function must exist exactly once: {name}")
    item = parse_gpl(functions[callback.casefold()]).require(DefinitionKind.FUNCTION, callback)
    # Return the owned callback for the existing strict boolean signature check.
    return callback, item.text
