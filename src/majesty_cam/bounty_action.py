"""Offline policy for a stock-bounty-backed user action.

Not a native adapter or a shipped capability declaration. Native targeting,
creation, payment and lifetime contracts must be established before integration.
Amounts here allocate one total action price; they never authorize a second fee.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BountyType(str, Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    EXPLORE = "explore"
    CAPTURE = "capture"


@dataclass(frozen=True)
class BountyRequest:
    kind: BountyType
    amount: int
    total_price: int

    def __post_init__(self):
        if not isinstance(self.kind, BountyType):
            raise ValueError("Unknown bounty type")
        for value in (self.amount, self.total_price):
            if type(value) is not int or not 0 < value <= 0x7FFFFFFF:
                raise ValueError("Bounty amount and total price must be positive signed integers")
        if self.amount > self.total_price:
            raise ValueError("Bounty funding must be included in the total action price")


@dataclass(frozen=True)
class PaymentAllocation:
    bounty_funding: int
    remaining_action_fee: int


def allocate_payment(request: BountyRequest, *, matching_bounty_exists: bool) -> PaymentAllocation:
    """Split a single price, without performing or assuming any native debit.

    A native adapter must determine matching eligibility using stock rules.
    Existing flags of other owners/types must not be inferred to match here.
    """
    if type(matching_bounty_exists) is not bool:
        raise ValueError("Existing-bounty state must be established, not guessed")
    funding = 0 if matching_bounty_exists else request.amount
    return PaymentAllocation(funding, request.total_price - funding)


@dataclass(frozen=True)
class FlagIdentity:
    identity: int
    owner: int
    kind: BountyType
    target: int
    amount: int


def continuation_allowed(
    request: BountyRequest, *, native_success: bool, actual_total_debit: int,
    original: Optional[FlagIdentity], final: Optional[FlagIdentity],
    matching_count: int, requested_owner: int, requested_target: int,
) -> bool:
    """Acceptance policy, not an undo/recovery implementation.

    The caller must consume its queued action identity before native dispatch;
    this pure predicate cannot supply at-most-once execution or rollback.
    """
    if native_success is not True or type(actual_total_debit) is not int:
        return False
    if actual_total_debit != request.total_price or matching_count != 1 or final is None:
        return False
    if final.kind != request.kind or final.target != requested_target or final.identity <= 0:
        return False
    if original is not None:
        return final == original
    return final.owner == requested_owner and final.amount == request.amount


ATTACK_SOURCE = r'''// Development stock-interface implementation; not installed or composed.
// Caller owns once-only queued dispatch and must not have debited the price yet.
// Result >=0 is the remaining sovereign fee, NOT the total visible price.
// -1 declines continuation; no speculative refund or credit is performed.
function MMM_PrepareAttackBounty(agent Source, agent Target, integer TotalPrice, integer BountyAmount) is integer
declare
    integer Player, BeforeGold, AfterGold, Matches, InvalidAmount;
    agent Flag, FlagTarget;
    list Flags;
begin
    if (TotalPrice <= 0) return -1;
    if (BountyAmount <= 0) return -1;
    if (BountyAmount > TotalPrice) return -1;
    if ($IsValidGamePiece(Source) == FALSE) return -1;
    if ($IsValidGamePiece(Target) == FALSE) return -1;
    Player = $GetUnitPlayerNumber(Source);
    if (Player < 0) return -1;
    if (Player >= 8) return -1;
    BeforeGold = $GetPlayerData(Source, "gold");
    if (BeforeGold < TotalPrice) return -1;
    // Stock duplicate scope is the offering player plus target, not all players.
    Matches = 0;
    $ListObjects(Source, "RewardFlag", -1, Flags, 6);
    foreach Flag in Flags do
        begin
            if ($GetUnitPlayerNumber(Flag) == Player)
                if (Flag's "title" == "flag_attack")
                    begin
                        FlagTarget = $AgentNumber($GetAttribute(Flag, #ATTRIB_TargetID));
                        if (FlagTarget == Target) Matches = Matches + 1;
                    end
        end
    if (Matches == 1) return TotalPrice;
    if (Matches > 1) return -1;
    // Use the normal stock creation/debit. Ignore its potentially unwritten
    // return slot; verify the resulting flag and treasury through stock queries.
    $PlaceRewardFlag(Target, Player, BountyAmount);
    if ($IsValidGamePiece(Source) == FALSE) return -1;
    if ($IsValidGamePiece(Target) == FALSE) return -1;
    AfterGold = $GetPlayerData(Source, "gold");
    if (BeforeGold - AfterGold != BountyAmount) return -1;
    Matches = 0;
    InvalidAmount = 0;
    $ListObjects(Source, "RewardFlag", -1, Flags, 6);
    foreach Flag in Flags do
        begin
            if ($GetUnitPlayerNumber(Flag) == Player)
                if (Flag's "title" == "flag_attack")
                    begin
                        FlagTarget = $AgentNumber($GetAttribute(Flag, #ATTRIB_TargetID));
                        if (FlagTarget == Target)
                            begin
                                if ($GetAttribute(Flag, #ATTRIB_RewardCost) != BountyAmount) InvalidAmount = 1;
                                Matches = Matches + 1;
                            end
                    end
        end
    if (InvalidAmount != 0) return -1;
    if (Matches != 1) return -1;
    return TotalPrice - BountyAmount;
end
'''


def compose_service(result, enabled):
    from .gpl import parse_gpl, SemanticMergeResult
    service = parse_gpl(ATTACK_SOURCE)
    owned = {item.normalized_name for item in service.items}
    if any(item.normalized_name in owned for item in result.items):
        raise ValueError('package defines a reserved bounty service function')
    return SemanticMergeResult((*result.items, *service.items), result.conflicts) if enabled else result


def selected(inventories):
    from .stock_controller_features import StockAp69AttackBountyAction
    return any(isinstance(feature, StockAp69AttackBountyAction)
               for inventory in inventories
               for feature in getattr(getattr(getattr(inventory.selected, 'package', None),
                   'definition', None), 'runtime_features', ()))


def validate_service(functions, counts, enabled):
    from .gpl import parse_gpl
    from .gameplay_events import stock_tokens
    for item in parse_gpl(ATTACK_SOURCE).items:
        name = item.normalized_name
        if enabled:
            if counts.get(name) != 1 or stock_tokens(functions.get(name, "")) != stock_tokens(item.text):
                raise ValueError("generated bounty preparation service is missing or changed")
        elif name in functions:
            raise ValueError("bounty preparation service present without opt-in action")

