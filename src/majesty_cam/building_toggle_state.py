"""Stock saved-GPL-boolean backing for independent MX22 control pairs."""
import re
from .gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from .gameplay_events import stock_tokens
from .stock_controller_features import StockMx22IndependentToggle


def accessor_symbol(feature):
    return "MM_Toggle_" + feature.state_callback_symbol


def source(feature):
    name, attr = feature.state_callback_symbol, feature.state_attribute
    return f'''function {name}(agent Building) is boolean
declare
begin
    if ($HasAttribute("{attr}", Building) == False) return False;
    return Building's "{attr}";
end

function {accessor_symbol(feature)}(agent Building, integer Operation) is integer
declare
begin
    if (Operation == 0 || Operation == 1)
        begin
            if ($HasAttribute("{attr}", Building) == False)
                $AddAttribute(Building, "{attr}", "boolean", False);
            Building's "{attr}" = (Operation == 1);
        end
    if (${name}(Building)) return 1;
    return 0;
end
'''


def selected(inventories):
    return tuple(feature for inventory in inventories
                 for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                                 "definition", None), "runtime_features", ())
                 if isinstance(feature, StockMx22IndependentToggle))


def validate_declarations(features, sources_by_owner, stock_sources=()):
    """Claim private state and generated names before loading any package."""
    claimed = {}
    generated = set()
    for owner, declarations in features:
        for feature in declarations:
            key = feature.state_attribute.casefold()
            if key in claimed:
                raise ValueError(f"independent toggle state attribute has multiple owners: {key}")
            claimed[key] = owner
            for item in parse_gpl(source(feature)).items:
                if item.normalized_name in generated:
                    raise ValueError(f"independent toggle generated symbol is duplicated: {item.name}")
                generated.add(item.normalized_name)
    for owner, sources in (*sources_by_owner, (None, stock_sources)):
        for parsed in sources:
            for item in parsed.items:
                if item.normalized_name in generated:
                    raise ValueError(f"generated toggle function collides with authored symbol: {item.name}")
                if item.kind is not DefinitionKind.PROTOTYPE:
                    continue
                text = ' '.join(stock_tokens(item.text))
                for kind, names in re.findall(r'\b(boolean|integer|agent|string|list|function|float|coordinate)\s+([^;]+);', text):
                    for name in (part.strip() for part in names.split(',')):
                        if name.casefold() in claimed:
                            raise ValueError(f"toggle state {name} is Manager-owned; do not declare it in a prototype")


def add_state_functions(result, features):
    items = list(result.items)
    names = {item.normalized_name for item in items}
    attributes = set()
    for feature in sorted(features, key=lambda f: f.state_callback_symbol.casefold()):
        if feature.state_attribute.casefold() in attributes:
            raise ValueError("independent toggle state attribute is claimed more than once")
        attributes.add(feature.state_attribute.casefold())
        for item in parse_gpl(source(feature)).items:
            if item.normalized_name in names:
                raise ValueError(f"generated toggle function collides with authored symbol: {item.name}")
            names.add(item.normalized_name)
            items.append(item)
    return SemanticMergeResult(tuple(items), result.conflicts)


def validate_state_functions(feature, functions, counts):
    for item in parse_gpl(source(feature)).items:
        key = item.normalized_name
        if counts.get(key) != 1 or stock_tokens(functions.get(key, "")) != stock_tokens(item.text):
            raise ValueError(f"generated toggle state function missing or changed: {item.name}")
