"""Approved repeatable stock research order with a saved initiating owner.

Reuse kingdom research's saved GPL attributes and numeric owner reservation.
Keep the reservation on the owning building, avoiding a new global list of
borrowed agents. Native stock orders own time and retirement; no GPL thread.
"""
import hashlib


def symbol(row):
    key = f'{row.action_control_id}:{row.readiness_callback_symbol.casefold()}:{row.completion_callback_symbol.casefold()}'
    if row.start_callback_symbol:
        key += ':' + row.quote_callback_symbol.casefold() + ':' + row.start_callback_symbol.casefold()
    return 'MM_QA_' + hashlib.sha256(key.encode('ascii')).hexdigest()[:24]


def source(row):
    key = symbol(row)
    quote = f'if (${row.quote_callback_symbol}(Building) == False) return 3;' if row.quote_callback_symbol else ''
    start = f'''if (${row.start_callback_symbol}(Building) == False)
                begin
                    Building's "{key}_pending" = 0;
                    return 3;
                end''' if row.start_callback_symbol else ''
    return f'''
// 0 quote; 1 reserve; 2 completed stock charge; 3 cancel/invalidate.
// Status 0 ready/reserved, 1 effect applied, 2 pending, 3 unavailable.
function {key}(agent Building, integer Operation) is integer
declare
    integer Player, Initiator;
    boolean Pending;
begin
    if ($IsValidGamePiece(Building) == False) return 3;
    if ((Operation < 0) || (Operation > 3)) return 3;
    Pending = False;
    if ($HasAttribute("{key}_pending", Building))
        Pending = (Building's "{key}_pending" == 1);
    if (Operation == 3)
        begin
            if (Pending) Building's "{key}_pending" = 0;
            return 0;
        end
    Player = $GetUnitPlayerNumber(Building);
    if (Operation == 2)
        begin
            if (Pending == False) return 3;
            // Retire the reservation BEFORE any callback can reenter.
            Building's "{key}_pending" = 0;
            if ($HasAttribute("{key}_owner", Building) == False) return 3;
            Initiator = Building's "{key}_owner";
            if (Player != Initiator) return 3;
            if ($IsDead(Building)) return 3;
            if (${row.readiness_callback_symbol}(Building) == False) return 3;
            ${row.completion_callback_symbol}(Building);
            return 1;
        end
    if (Pending) return 2;
    if ($IsDead(Building)) return 3;
    if (${row.readiness_callback_symbol}(Building) == False) return 3;
    {quote}
    if (Operation == 1)
        begin
            if ($HasAttribute("{key}_pending", Building) == False)
                begin
                    $AddAttribute(Building, "{key}_pending", "integer");
                end
            if ($HasAttribute("{key}_owner", Building) == False)
                $AddAttribute(Building, "{key}_owner", "integer");
            Building's "{key}_owner" = Player;
            Building's "{key}_pending" = 1;
            {start}
        end
    return 0;
end
'''
