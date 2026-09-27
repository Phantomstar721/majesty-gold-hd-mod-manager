# Shared Bazaar potion policy

`stock.bazaar-potion-policy.v1` is a source-composed declaration for a
package-owned Character. No executable hook, timer or per-unit state is added.
The same GPL/XML boundary is used for default Steam, beta2 and GOG. Installed
stock functions remain the implementation reference and compilation target.

```json
{
  "type": "stock.bazaar-potion-policy.v1",
  "feature_key": "example-potions",
  "hero_title": "ExampleCaster",
  "potions": {
    "speed": true, "fire-balm": false, "strength": false,
    "regeneration": true, "invisibility": true, "shapeshift": true
  },
  "shapeshift": {"preset": "medusa"},
  "private_actions": {}
}
```

Declare all six choices; healing is deliberately outside this contract.
Duplicate hero declarations fail rather than using package order. Private
actions map a potion key to its package-owned Action Description Name; omitted
entries use the stock action. A private shapeshift effect must remain a literal
stock clone except its function name and action-name references. Remove authored
form branches and shared expiry overrides when migrating.

Presets are `stock`, `dryad`, `medusa`, `minotaur`, and `custom`. Stock presets
copy the corresponding application and removal statements literally from the
installed SDK. Custom forms use:

```json
{
  "preset": "custom", "unit_name": "ExampleForm", "heal": 30,
  "adjustments": [
    {"attribute": "ATTRIB_Strength", "amount": 18, "mode": "magical"},
    {"attribute": "ATTRIB_ActionRateModifier", "amount": -50, "mode": "raw"},
    {"attribute": "ATTRIB_MaxHP", "amount": 30, "mode": "raw"}
  ]
}
```

Each adjustment generates its exact inverse in cleanup. `heal` is an initial
HP increase, not a temporary stat to subtract later; stock expiry still clamps
HP to the restored maximum. Duplicate attributes and unbounded/injected values
are rejected. Custom forms must be real loaded units. Do not change a form's
bonuses while an older saved transformation is active: the original save has
no policy-version ledger, and this feature deliberately adds none.

## Stock lifecycle retained

1. `Bazaar_Item_Check` applies declared eligibility instead of its stock
   title-only restrictions. Undeclared titles still use those restrictions;
   inventory ownership, money, intelligence, target and intent remain stock.
2. Each stock `Purchase_Bazaar_Item_*` checks eligibility again before charging.
   A denied pending purchase advances to stock `Done_Purchasing_Market_Stuff`
   without charging or granting the item.
3. The Action validation wrapper checks eligibility, then calls the original
   validation exactly once. An effect-entry guard also blocks direct bypasses,
   after the stock dead-caster check. Denial does not consume an item.
4. Allowed effects retain native timed effectors, duration lookup, consumption,
   forgetting, and original ordering. Only the existing form-selection branch
   is extended. Stock expiry reverts the unit, removes the matching modifiers
   and clamps HP. There are no new cleanup callbacks or duplicate effectors.
5. Declared consumption observers compose over the generated boundaries,
   including private action clones; blocked uses do not notify.

Private shopping decision routines should call `MM_BP_Eligibility(agent, item)`
before scheduling: 0 denies, 1 explicitly permits, -1 means undeclared and
requires existing stock behavior. Their stock purchase callbacks remain guarded
regardless. Do not implement a second purchase or consumption path.

The Manager's packaged private input declares its own policy during payload
staging, without changing the upstream repository or the user's prepared profile.
