"""Saved, non-scheduled delivery for the opt-in native exploration observer.

The native adapter records after the stock fog call and dispatches after the
stock simulation step. These functions never install a GPL thread or scan a map.
"""
from __future__ import annotations

EVENT = "source-terrain-revealed"
CAPABILITY = "manager.source-exploration.v1"
# GPL binary operators shift integer operands left ten bits into signed 32-bit
# fixed point. Storage is int32, but positive expression operands stop here.
MAX_EXPRESSION_INTEGER = 2097151


def require_supported_profile(executable) -> None:
    """Cheap identity check; the native installer also validates every hook."""
    from .manager.qol_service import (
        detect_majesty_branch, PUBLIC_BRANCH, BETA2_BRANCH, GOG_BRANCH,
    )
    if executable is None or detect_majesty_branch(executable) not in (
        PUBLIC_BRANCH, BETA2_BRANCH, GOG_BRANCH,
    ):
        raise ValueError("Source exploration requires an audited default Steam, Steam beta2, or GOG executable")


def requires_native_observation(definition) -> bool:
    from .shared_features import StockGameplayEventObserver
    return any(isinstance(feature, StockGameplayEventObserver) and feature.event == EVENT
               for feature in getattr(definition, "runtime_features", ()))


def selected(inventories) -> bool:
    return any(requires_native_observation(
        getattr(getattr(inventory.selected, "package", None), "definition", None))
        for inventory in inventories)

# Pending owner/count pairs live on the source agent, while the root holds dirty
# agent references. An ownership transition cancels that source's pending work;
# returning to the original owner cannot resurrect it. Saved references follow
# GPL identity rather than native unit IDs or process addresses.
_SERVICE = '''
function MM_EO_Root() is agent
declare
    agent Root;
begin
    Root = $RetrieveAgent("GplAIRoot");
    if ($HasAttribute("MM_ExplorationDirty_v1", Root) == False)
        $AddAttribute(Root, "MM_ExplorationDirty_v1", "list");
    return Root;
end

function MM_EO_Record(agent Source, integer Owner, integer Tiles) is integer
declare
    agent Root;
    list Dirty;
begin
    if ($IsValidGamePiece(Source) == False) return -1;
    if (Owner < 0 || Owner > 7 || Tiles <= 0) return -1;
    if ($GetUnitPlayerNumber(Source) != Owner) return -1;
    if ($HasAttribute("MM_ExplorationPending_v1", Source) == False)
        begin
            $AddAttribute(Source, "MM_ExplorationPending_v1", "integer", 0);
            $AddAttribute(Source, "MM_ExplorationOwner_v1", "integer", Owner);
            $AddAttribute(Source, "MM_ExplorationQueued_v1", "boolean", False);
            $AddAttribute(Source, "MM_ExplorationEpoch_v1", "integer", 0);
        end
    if (Source's "MM_ExplorationOwner_v1" != Owner)
        begin
            Source's "MM_ExplorationPending_v1" = 0;
            Source's "MM_ExplorationOwner_v1" = Owner;
        end
    if (Tiles > 2097151 - Source's "MM_ExplorationPending_v1") return -2;
    Root = $MM_EO_Root();
    Dirty = Root's "MM_ExplorationDirty_v1";
    if (Source's "MM_ExplorationQueued_v1" == False)
        begin
            Dirty << Source;
            Source's "MM_ExplorationQueued_v1" = True;
        end
    Source's "MM_ExplorationPending_v1" += Tiles;
    Root's "MM_ExplorationDirty_v1" = Dirty;
    return 1;
end

function MM_EO_Invalidate(agent Source) is integer
declare
begin
    if ($IsValidGamePiece(Source) == False) return 0;
    if ($HasAttribute("MM_ExplorationPending_v1", Source))
        begin
            if (Source's "MM_ExplorationEpoch_v1" == 2097151) return -2;
            Source's "MM_ExplorationPending_v1" = 0;
            Source's "MM_ExplorationEpoch_v1" += 1;
        end
    return 1;
end

function MM_EO_Dispatch() is integer
declare
    agent Root, Source;
    list Dirty, Empty, Batch;
    integer Index, Owner, Tiles, Epoch;
begin
    Root = $MM_EO_Root();
    Dirty = Root's "MM_ExplorationDirty_v1";
    Root's "MM_ExplorationDirty_v1" = Empty;
    Index = 1;
    while (Index <= $ListSize(Dirty)) do
        begin
            Source = $ListMember(Dirty, Index);
            if ($IsValidGamePiece(Source))
                if ($HasAttribute("MM_ExplorationPending_v1", Source))
                    begin
                        Tiles = Source's "MM_ExplorationPending_v1";
                        Owner = Source's "MM_ExplorationOwner_v1";
                        Source's "MM_ExplorationPending_v1" = 0;
                        Source's "MM_ExplorationQueued_v1" = False;
                        if (Tiles > 0)
                            begin
                                Batch << Source;
                                Batch << Owner;
                                Batch << Tiles;
                                Batch << Source's "MM_ExplorationEpoch_v1";
                            end
                    end
            Index += 1;
        end
    Index = 1;
    while (Index <= $ListSize(Batch)) do
        begin
            Source = $ListMember(Batch, Index);
            Owner = $ListMember(Batch, Index + 1);
            Tiles = $ListMember(Batch, Index + 2);
            Epoch = $ListMember(Batch, Index + 3);
__CALLBACKS__
            Index += 4;
        end
    return 1;
end
'''


def service_source(callbacks: tuple[str, ...]) -> str:
    """Symbols are already ownership/signature-validated by gameplay_events."""
    if not callbacks:
        return ""
    return _SERVICE.replace("__CALLBACKS__", "\n".join(
        '            if ($IsValidGamePiece(Source))\n'
        '                if ($GetUnitPlayerNumber(Source) == Owner)\n'
        '                    if (Source\'s "MM_ExplorationEpoch_v1" == Epoch)\n'
        f'                        ${name}(Source, Owner, Tiles, Epoch);'
        for name in callbacks))


def validate_service(functions: dict[str, str], enabled: bool,
                     counts: dict[str, int] | None = None) -> None:
    """Require the literal generated save/dispatch service, not symbol presence."""
    from .gameplay_events import stock_tokens, require_callback
    from .gpl import parse_gpl, DefinitionKind
    owned = {key for key in functions if key.startswith("mm_eo_")}
    if not enabled:
        if owned:
            raise ValueError("source exploration service is present without its native capability")
        return
    tokens = stock_tokens(functions.get("mm_eo_dispatch", ""))
    shape = ("(", "source", ",", "owner", ",", "tiles", ",", "epoch", ")")
    callbacks = tuple(tokens[i+1] for i in range(len(tokens)-10)
                      if tokens[i] == "$" and tokens[i+2:i+11] == shape)
    if not callbacks or len(set(callbacks)) != len(callbacks):
        raise ValueError("source exploration requires distinct declared consumers")
    expected = parse_gpl(service_source(callbacks))
    if owned != {item.normalized_name for item in expected.items}:
        raise ValueError("source exploration generated service is incomplete")
    if counts is not None:
        for symbol in (*owned, *callbacks):
            if counts.get(symbol, 0) != 1:
                raise ValueError(f"source exploration function must be defined exactly once: {symbol}")
    for item in expected.items:
        if stock_tokens(functions[item.normalized_name]) != stock_tokens(item.text):
            raise ValueError(f"source exploration generated service was changed: {item.name}")
    for symbol in callbacks:
        parsed = parse_gpl(functions.get(symbol, ""))
        if len(parsed.items) != 1:
            raise ValueError(f"source exploration callback is missing: {symbol}")
        require_callback(parsed.require(DefinitionKind.FUNCTION, symbol), symbol,
                         ("agent", "integer", "integer", "integer"))
