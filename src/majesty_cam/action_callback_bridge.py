"""Adapt declared boolean actions to the stock external integer result ABI."""
import hashlib
import re


def bridge_symbol(callback: str) -> str:
    return "MM_Action_" + hashlib.sha256(callback.casefold().encode("ascii")).hexdigest()[:24]


def bridge_source(callback: str) -> str:
    return f'''function {bridge_symbol(callback)}(agent Subject) is integer
declare
begin
    if (${callback}(Subject)) return 1;
    return 0;
end
'''


def add_bridges(result, inventories):
    from .gpl import parse_gpl, SemanticMergeResult
    from .stock_controller_features import StockMx04Mx05OccupantActionPanel, StockMx05LiveAgentListPanel
    callbacks = {feature.action_callback_symbol.casefold(): feature.action_callback_symbol
                 for inventory in inventories
                 for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                                "definition", None), "runtime_features", ())
                 if isinstance(feature, (StockMx04Mx05OccupantActionPanel, StockMx05LiveAgentListPanel))}
    items = list(result.items)
    existing = {item.normalized_name for item in items}
    for key in sorted(callbacks):
        callback = callbacks[key]
        symbol = bridge_symbol(callback)
        if symbol.casefold() in existing:
            raise ValueError(f"generated action bridge collides with authored symbol: {symbol}")
        items.extend(parse_gpl(bridge_source(callback)).items)
        existing.add(symbol.casefold())
    return SemanticMergeResult(tuple(items), result.conflicts)


def validate_bridge(symbol, functions, counts):
    from .gameplay_events import stock_tokens
    from .gpl import parse_gpl, DefinitionKind
    text = functions.get(symbol.casefold(), "")
    calls = re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    if len(calls) != 1 or bridge_symbol(calls[0]).casefold() != symbol.casefold():
        raise ValueError(f"generated action bridge is missing or invalid: {symbol}")
    callback = calls[0]
    if stock_tokens(text) != stock_tokens(bridge_source(callback)):
        raise ValueError(f"generated action bridge body was changed: {symbol}")
    for name in (symbol, callback):
        if counts.get(name.casefold(), 0) != 1:
            raise ValueError(f"action bridge function must exist exactly once: {name}")
    item = parse_gpl(functions[callback.casefold()]).require(DefinitionKind.FUNCTION, callback)
    # Return the owned callback for the existing strict boolean signature check.
    return callback, item.text
