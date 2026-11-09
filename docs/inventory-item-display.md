# Custom inventory item display

Packages may declare `stock.inventory-item-display.v1` with `feature_key`,
numeric `item_id` (0..127), `display_text`, `tooltip_text`, private `image_id`
and `image_set`. The owned image uses a single 24x24 stock-format indexed icon.
The real stock Items row is decorated only after stock inventory enumeration
creates it. Ownership, consumption, refresh, hover and row destruction remain
stock. Unregistered items retain stock presentation. No scans or timer added.

The release accepts MMFR12 kind5 for this feature. Development-only kind4 and
MMFR10/11 saved-attribute presentation are deliberately not admitted. Existing
release declarations remain supported. No status-response or guild-specific
behavior is added.

Native evidence: Public Items body4A2E30, beta2 4A3710, GOG4A3CC0; existing
stock menu append results and synchronous copied row messages24/60/62. Whole
selected bodies and append sites are pinned in tests/test_inventory_display.py;
native fixtures execute the insertion bridge and all three message slots.
scripts/verify_inventory_display.py reproduces independent offline comparison.

Source port reuses the development trace. Graph consultation at commit
f2644580d33ad98703361cd8fc88c825068161ef: inventory ID representation and native
membership evidence, engine_function.createnewinventoryitem. Those records do
not prove UI behavior: the independently traced stock consumer supplies that
evidence. Research shared-map and symbol-index were consulted for the original
implementation. Native gameplay acceptance remains separate from fixture checks.
