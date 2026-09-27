"""Manager-owned declaration applied only to its bundled private input copy."""
import json
from pathlib import Path
import sys

from .potion_policy import TYPE, parse_feature

POLICY = {
    "type": TYPE, "feature_key": "phantom-bazaar-policy", "hero_title": "Phantom",
    "potions": {"speed": True, "fire-balm": False, "strength": True,
                "regeneration": False, "invisibility": True, "shapeshift": True},
    "shapeshift": {"preset": "medusa"}, "private_actions": {},
}


def apply(root):
    path = Path(root) / "mod-definition.json"
    definition = json.loads(path.read_text(encoding="utf-8-sig"))
    if definition.get("mod_id", "").strip("{}").casefold() != "8fafa371-810c-419d-8f5c-7e3931450e3f":
        raise ValueError("not the Manager's bundled private Phantom input")
    parse_feature(POLICY)
    features = definition.setdefault("runtime_features", [])
    existing = [f for f in features if f.get("type") == TYPE and f.get("hero_title", "").casefold() == "phantom"]
    if existing and existing != [POLICY]:
        raise ValueError("bundled Phantom potion policy conflicts with Manager declaration")
    if not existing:
        features.append(POLICY)
    from .package import parse_mod_definition
    parse_mod_definition(definition)
    path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    apply(sys.argv[1])
