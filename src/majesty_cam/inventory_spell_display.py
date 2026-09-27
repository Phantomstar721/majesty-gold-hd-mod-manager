"""Shared AP78 display classification, not a change to learned spell state."""
from .gameplay_events import stock_tokens

CAPABILITY = "manager.inventory-spell-display.v1"


def hidden_action_names(source):
    """Only literal, consistently hidden LearnSpell declarations qualify.

    A computed action name can refer to any action, so it disables inference.
    Visible/default/computed visibility for a literal name excludes that name.
    Comments and string contents cannot introduce fake calls.
    """
    tokens = stock_tokens(source)
    choices = {}
    for i in range(len(tokens) - 1):
        if tokens[i:i+2] != ("$", "learnspell"):
            continue
        if tokens[i+2:i+3] != ("(",):
            return ()  # Indirect reference; no provable argument contract.
        args, part, depth = [], [], 1
        for token in tokens[i+3:]:
            if token == "(":
                depth += 1
            elif token == ")":
                depth -= 1
                if not depth:
                    args.append(tuple(part))
                    break
            if token == "," and depth == 1:
                args.append(tuple(part))
                part = []
            else:
                part.append(token)
        if depth or len(args) not in (2, 3) or len(args[1]) != 1:
            return ()
        name = args[1][0]
        if not name.startswith('"') or "\\" in name:
            return ()
        name = name[1:-1].casefold()
        hidden = len(args) == 3 and args[2] == ("false",)
        choices[name] = choices.get(name, True) and hidden
    return tuple(sorted(name for name, hidden in choices.items() if hidden))


def derive_hidden_action_ids(source, descriptions):
    names = set(hidden_action_names(source))
    matches = {}
    for record in descriptions:
        element = record.to_element()
        name = element.get("Name", "").casefold()
        if element.get("type") != "Action" or name not in names:
            continue
        flags = element.find("./Game/Flags")
        if flags is not None and "IsSpell" in flags.get("value", "").replace("|", " ").replace(",", " ").split():
            matches.setdefault(name, []).append(record.key[1])
    # Ambiguous loaded names must not suppress a potentially different action.
    ids = {values[0] for values in matches.values() if len(values) == 1}
    return tuple(sorted(ids, key=lambda value: int.from_bytes(value.encode("ascii"), "little")))
