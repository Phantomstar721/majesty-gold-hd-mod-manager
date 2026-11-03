"""Static building buttons using stock queued, zero-native-price actions."""
from dataclasses import dataclass, asdict
import hashlib
import re


@dataclass(frozen=True)
class PanelCommand:
    control_id: int
    callback_symbol: str


def parse_commands(values):
    if not isinstance(values, (tuple, list)) or len(values) > 16:
        raise ValueError("secondary panel commands must be an array of at most 16 entries")
    result = []
    for raw in values:
        value = asdict(raw) if isinstance(raw, PanelCommand) else raw
        if not isinstance(value, dict) or set(value) != {"control_id", "callback_symbol"}:
            raise ValueError("panel command requires control_id and callback_symbol")
        control, symbol = value['control_id'], value['callback_symbol']
        if type(control) is not int or not 0x22CE < control <= 65535:
            raise ValueError("panel command control must be a private uint16")
        if not isinstance(symbol, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', symbol):
            raise ValueError("invalid panel command callback")
        if symbol.casefold().startswith('mm_'):
            raise ValueError("panel command callback must be package-owned")
        result.append(PanelCommand(control, symbol))
    if len({r.control_id for r in result}) != len(result):
        raise ValueError("duplicate panel command control")
    return tuple(result)


def adapter_symbol(callback, commit):
    key = callback.casefold().encode('ascii')
    suffix = '_Owner' if commit is None else '_Commit' if commit else '_Quote'
    return 'MM_Panel_' + hashlib.sha256(key).hexdigest()[:24] + suffix


def adapter_source(callback, commit):
    if commit is None:
        return f'''function {adapter_symbol(callback, None)}(agent Building) is integer
declare
begin
    return $GetUnitPlayerNumber(Building);
end
'''
    return f'''function {adapter_symbol(callback, commit)}(agent Building) is integer
declare
begin
    if (${callback}(Building, {'True' if commit else 'False'})) return 1;
    return 0;
end
'''
