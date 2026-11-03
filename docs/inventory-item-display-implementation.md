# Real inventory item presentation

User approved the generic icon/name/hover extension on 2026-10-17. This is
separate from the already implemented source-only death-drop exclusion.

## Primary trace and lifecycle

Graph consultation: f2644580d33ad98703361cd8fc88c825068161ef,
inventory-id-representation-20261013 and inventory_membership_native_20261002;
source citations and qualifications are in private-inventory-contract.md.
Research shared-map and existing AP78 row ownership were consulted. The missing
Items consumer was independently traced, not delegated to research.

`scripts/verify_inventory_display.py` and local/inventory-display-static.json
pin all three pristine images. AP22's population function clears control232D,
iterates the selected actor's actual attribute collection, calls the stock
inventory predicate, resolves item text, and appends only actual items. Public
4A3150's attribute notification calls 4A2E30 for inventory keys; panel setup
4A2FE0 also calls it. No new timer, world-unit scan, inventory grant or saved
attribute row is needed. Preserve this iterator and its stock notifications.

The stock Data/textdata.cam AP22/SMNU control232D is type6, bounds12,126,160,60,
row height30, and already has flag1024 (native tooltips). This is the same
list-control type used by AP78. The icon/tooltip extension can reuse native
row messages24/62 and copied string/image ownership documented in
stock-ap78-info-rows.md, rather than creating an overlay or a parallel UI.

The bounded append site is Items-body+138h: `push 232Dh; call eax`, seven bytes,
followed by iterator increment. ECX is the native menu, ESI the controller,
EBX the current attribute node (key at+0Ch). Stack already contains the native
string pointer and insertion index -1. Do not replace the inventory predicate,
resolver or traversal. The new presentation must apply only to registered
numeric INV identities; every other stock or custom item passes unchanged.

## Implemented contract

Schema3 `runtime_features`:

```json
{"type":"stock.inventory-item-display.v1","feature_key":"private-dose",
 "item_id":114,"display_text":"Private dose","tooltip_text":"Use this dose",
 "image_id":"DI01","image_set":1019}
```

IDs are existing numeric inventory IDs0..127, not allocated or granted by this
feature. Duplicate item claims are rejected. Icon evidence uses the existing
stock INTn24x24 single-frame indexed list-icon contract; larger approved art
needs an owner-produced24x24 derivative, not a different research icon.
Registry MMFR12 carries kind5 with the numeric subject ID. Older runtimes
reject this version instead of silently ignoring the binding. Saved attributes
and existing spell/effect entries retain their prior representation.

InventoryItemDisplay.inl replays stock's append, then sends the declared label,
tooltip and copied image to that row. Unclaimed keys and failed appends pass
unchanged. The seven-byte patch and entire stock body have exact three-build
guards. The native x86 fixture exercises the real adapter's stack/register
shape, unchanged key, both message slots, unknown keys and invalid rows.

The menu append wrapper is Public4B4750/beta4B5040/GOG4B5640:30 identical bytes
forward control/index/string through message26 and return EAX unchanged.
It is the+2Ch virtual method used by the stock Items append site. The existing
native list dispatcher owns creation and returns its row index; the existing
stock row setters copy label/tooltip/image and own their cleanup.

## Native acceptance still required

Verify the tooltip hit-test on AP22 and row layout when an image is assigned.
Do not claim native acceptance from package resource presence.

No dose migration belongs in the renderer. Guild owners retain purchase,
consumption and saved-dose migration. Phoenix113 and Salts114 remain distinct.
Alchemist owner was asked to supply approved image/set and label/hover inputs;
the schema above is implemented, with packaging/native acceptance tracked separately.
