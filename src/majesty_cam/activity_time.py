"""The approved shared, stock-scheduled activity sampler (no native timer hook)."""
from __future__ import annotations

from .gpl import SemanticMergeResult, parse_gpl, require_complete_semantic_coverage
from .shared_composition import SharedBinding
from .shared_features import StockActivityDuration


# Flat, heterogeneous GPL lists are a documented intrinsic. Keep every record
# fixed-width; never use AddLists (set/union semantics) for a record ledger.
# identity, owner, subject, context, key, duration, elapsed, enabled, qualifying,
# context-required. Terminal notifications contain the borrowed context + reason.
RECORD_WIDTH = 10
MAX_ACTIVITIES = 128

_SERVICE = '''
function MM_AD_Alive(agent Value) is boolean
declare
begin
    if ($IsValidGamePiece(Value) == False) return False;
    return ($IsDead(Value) == False);
end

function MM_AD_Root() is agent
declare
    agent Root;
begin
    Root = $RetrieveAgent("GplAIRoot");
    if ($HasAttribute("MM_ActivityRecords_v1", Root) == False)
        begin
            $AddAttribute(Root, "MM_ActivityRecords_v1", "list");
            $AddAttribute(Root, "MM_ActivityBusy_v1", "boolean", False);
            $AddAttribute(Root, "MM_ActivityRunning_v1", "boolean", False);
            $AddAttribute(Root, "MM_ActivityTicking_v1", "boolean", False);
            $AddAttribute(Root, "MM_ActivityThread_v1", "function", $MM_AD_Tick);
        end
    return Root;
end

function MM_AD_Find(list Records, string Identity, agent Owner, integer Key) is integer
declare
    integer Index;
begin
    Index = 1;
    while (Index <= $ListSize(Records)) do
        begin
            if ($ListMember(Records, Index) == Identity)
                if ($ListMember(Records, Index + 1) == Owner)
                    if ($ListMember(Records, Index + 4) == Key) return Index;
            Index += 10;
        end
    return 0;
end

function MM_AD_StopIfEmpty(agent Root)
declare
begin
    if (Root's "MM_ActivityTicking_v1") return;
    if ($ListSize(Root's "MM_ActivityRecords_v1") == 0)
        if (Root's "MM_ActivityRunning_v1")
            begin
                Root's "MM_ActivityRunning_v1" = False;
                $KillThread(Root's "MM_ActivityThread_v1");
            end
end

function MM_AD_Start(string Identity, agent Owner, agent Subject, agent Context, integer Key, integer Duration) is integer
declare
    agent Root;
    list Records;
    boolean Required;
begin
    if (Key <= 0) return -1;
    if (Duration <= 0) return -1;
    if ($MM_AD_Alive(Owner) == False) return -1;
    if ($MM_AD_Alive(Subject) == False) return -1;
    Required = (Context != $NullAgent());
    if (Required) if ($MM_AD_Alive(Context) == False) return -1;
    Root = $MM_AD_Root();
    if (Root's "MM_ActivityBusy_v1") return -3;
    Root's "MM_ActivityBusy_v1" = True;
    Records = Root's "MM_ActivityRecords_v1";
    if ($MM_AD_Find(Records, Identity, Owner, Key) != 0)
        begin
            Root's "MM_ActivityBusy_v1" = False;
            return 0;
        end
    if ($ListSize(Records) >= 1280)
        begin
            Root's "MM_ActivityBusy_v1" = False;
            return -2;
        end
    Records << Identity;
    Records << Owner;
    Records << Subject;
    Records << Context;
    Records << Key;
    Records << Duration;
    Records << 0;
    Records << True;
    Records << False;
    Records << Required;
    Root's "MM_ActivityRecords_v1" = Records;
    if (Root's "MM_ActivityRunning_v1" == False)
        begin
            Root's "MM_ActivityRunning_v1" = True;
            $NewThread(Root's "MM_ActivityThread_v1", 1000);
        end
    Root's "MM_ActivityBusy_v1" = False;
    return 1;
end

function MM_AD_Read(string Identity, agent Owner, integer Key, boolean State) is integer
declare
    agent Root;
    list Records;
    integer Index;
begin
    Root = $MM_AD_Root();
    Records = Root's "MM_ActivityRecords_v1";
    Index = $MM_AD_Find(Records, Identity, Owner, Key);
    if (Index == 0)
        begin
            if (State) return 0;
            return -1;
        end
    if (State)
        begin
            if ($ListMember(Records, Index + 7) == False) return 3;
            if ($ListMember(Records, Index + 8)) return 1;
            return 2;
        end
    return $ListMember(Records, Index + 6);
end

function MM_AD_Change(string Identity, agent Owner, integer Key, integer Action) is integer
declare
    agent Root, Subject, Context;
    list Records, Kept;
    integer Index, Match, Part;
    boolean Enabled;
begin
    Root = $MM_AD_Root();
    if (Root's "MM_ActivityBusy_v1") return -3;
    Root's "MM_ActivityBusy_v1" = True;
    Records = Root's "MM_ActivityRecords_v1";
    Match = $MM_AD_Find(Records, Identity, Owner, Key);
    if (Match == 0)
        begin
            Root's "MM_ActivityBusy_v1" = False;
            return 0;
        end
    Subject = $ListMember(Records, Match + 2);
    Context = $ListMember(Records, Match + 3);
    Enabled = $ListMember(Records, Match + 7);
    Index = 1;
    while (Index <= $ListSize(Records)) do
        begin
            if ((Index != Match) || (Action != 0))
                begin
                    Part = 0;
                    while (Part < 10) do
                        begin
                            if ((Index == Match) && (Enabled != (Action == 2)))
                                begin
                                    if (Part == 7) Kept << (Action == 2);
                                    else if (Part == 8) Kept << False;
                                    else Kept << $ListMember(Records, Index + Part);
                                end
                            else Kept << $ListMember(Records, Index + Part);
                            Part += 1;
                        end
                end
            Index += 10;
        end
    Root's "MM_ActivityRecords_v1" = Kept;
    Root's "MM_ActivityBusy_v1" = False;
    // Commit removal before cancellation; callbacks may start a new identity.
    if (Action == 0)
        begin
            $MM_AD_Notify(Identity, Owner, Subject, Context, Key, 1);
            $MM_AD_StopIfEmpty(Root);
        end
    return 1;
end

function MM_AD_Tick()
declare
    agent Root, Owner, Subject, Context;
    list Records, Kept, Finished;
    string Identity;
    integer Index, Part, Key, Duration, Elapsed, Reason;
    boolean Enabled, Qualifying, Previous, Required;
begin
    Root = $MM_AD_Root();
    if (Root's "MM_ActivityBusy_v1") return;
    if (Root's "MM_ActivityTicking_v1") return;
    Root's "MM_ActivityTicking_v1" = True;
    Root's "MM_ActivityBusy_v1" = True;
    Records = Root's "MM_ActivityRecords_v1";
    Index = 1;
    while (Index <= $ListSize(Records)) do
        begin
            Identity = $ListMember(Records, Index);
            Owner = $ListMember(Records, Index + 1);
            Subject = $ListMember(Records, Index + 2);
            Context = $ListMember(Records, Index + 3);
            Key = $ListMember(Records, Index + 4);
            Duration = $ListMember(Records, Index + 5);
            Elapsed = $ListMember(Records, Index + 6);
            Enabled = $ListMember(Records, Index + 7);
            Previous = $ListMember(Records, Index + 8);
            Required = $ListMember(Records, Index + 9);
            Reason = -1;
            Qualifying = False;
            if ($MM_AD_Alive(Owner) == False) Reason = 2;
            else if ($MM_AD_Alive(Subject) == False) Reason = 3;
            else if (Required) if ($MM_AD_Alive(Context) == False) Reason = 4;
            if (Reason == -1)
                begin
                    if (Enabled) Qualifying = $MM_AD_Qualifies(Identity, Owner, Subject, Context, Key);
                    if (Qualifying && Previous)
                        begin
                            // Saturation avoids signed overflow for long durations.
                            if ((Duration - Elapsed) <= 1000) Elapsed = Duration;
                            else Elapsed += 1000;
                        end
                    if (Elapsed >= Duration) Reason = 0;
                end
            if (Reason == -1)
                begin
                    Part = 0;
                    while (Part < 10) do
                        begin
                            if (Part == 6) Kept << Elapsed;
                            else if (Part == 8) Kept << Qualifying;
                            else Kept << $ListMember(Records, Index + Part);
                            Part += 1;
                        end
                end
            else
                begin
                    Finished << Identity;
                    Finished << Owner;
                    Finished << Subject;
                    Finished << Context;
                    Finished << Key;
                    Finished << Reason;
                end
            Index += 10;
        end
    Root's "MM_ActivityRecords_v1" = Kept;
    Root's "MM_ActivityBusy_v1" = False;
    // All terminal records leave the saved ledger before any callback runs.
    Index = 1;
    while (Index <= $ListSize(Finished)) do
        begin
            $MM_AD_Notify($ListMember(Finished, Index), $ListMember(Finished, Index + 1),
                $ListMember(Finished, Index + 2), $ListMember(Finished, Index + 3),
                $ListMember(Finished, Index + 4), $ListMember(Finished, Index + 5));
            Index += 6;
        end
    Root's "MM_ActivityTicking_v1" = False;
    $MM_AD_StopIfEmpty(Root);
end
'''


def activity_source(bindings: tuple[SharedBinding, ...]) -> str:
    activities = tuple(b for b in bindings if isinstance(b.feature, StockActivityDuration))
    if not activities:
        return ""
    conditions, notifications, wrappers = [], [], []
    args = "Owner, Subject, Context, Key"
    for binding in activities:
        feature = binding.feature
        identity = binding.identity
        # Identity contains only validated UUID/logical-key characters.
        if any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-:_." for c in identity):
            raise ValueError("activity identity must be a canonical mod UUID and feature key")
        conditions.append(f'    if (Identity == "{identity}") return ${feature.condition_callback_symbol}({args});')
        notifications.append(f'''    if (Identity == "{identity}")
        begin
            if (Reason == 0) ${feature.completion_callback_symbol}({args});
            else ${feature.cancellation_callback_symbol}({args}, Reason);
            return;
        end''')
        prefix = feature.api_prefix
        wrappers.append(f'''function {prefix}_Start(agent Owner, agent Subject, agent Context, integer Key, integer Duration) is integer
declare
begin
    return $MM_AD_Start("{identity}", {args}, Duration);
end
''')
        for suffix, action in (("Pause", 1), ("Resume", 2), ("Cancel", 0)):
            wrappers.append(f'''function {prefix}_{suffix}(agent Owner, integer Key) is integer
declare
begin
    return $MM_AD_Change("{identity}", Owner, Key, {action});
end
''')
        for suffix, state in (("Elapsed", "False"), ("State", "True")):
            wrappers.append(f'''function {prefix}_{suffix}(agent Owner, integer Key) is integer
declare
begin
    return $MM_AD_Read("{identity}", Owner, Key, {state});
end
''')
    return _SERVICE + '''
function MM_AD_Qualifies(string Identity, agent Owner, agent Subject, agent Context, integer Key) is boolean
declare
begin
''' + "\n".join(conditions) + '''
    return False;
end
function MM_AD_Notify(string Identity, agent Owner, agent Subject, agent Context, integer Key, integer Reason)
declare
begin
''' + "\n".join(notifications) + "\nend\n" + "\n".join(wrappers)


def add_activity_service(result: SemanticMergeResult,
                         bindings: tuple[SharedBinding, ...]) -> SemanticMergeResult:
    text = activity_source(bindings)
    if not text:
        return result
    result.require_clean()
    source = parse_gpl(text, "<Manager shared activity duration>")
    require_complete_semantic_coverage(source)
    existing = {item.key for item in result.items}
    for item in source.items:
        if item.key in existing:
            raise ValueError(f"activity service symbol collides with package: {item.name}")
    return SemanticMergeResult((*result.items, *source.items), result.conflicts)
