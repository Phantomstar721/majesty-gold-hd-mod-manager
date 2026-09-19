# Private hero information rows

Implementation audit for the opt-in AP78 extension. This is presentation only:
it must not teach a spell, add a cast command, apply an effect or change hero AI.

## Stock lifecycle (Steam beta2 1.5.2.28)

- AP78 constructor `0x4A4B00` uses the ordinary unit controller and vtable
  `0x7563B8`. It borrows a selected unit ID; `0x468780` resolves that ID against
  the live world. Destruction `0x4A4B90` delegates to the stock controller.
- Setup `0x4A4A20` calls learned-spell refresh `0x4A3C00`, then active-effect
  refresh `0x4A4110`. The event handler `0x4A4A90` retains stock level-change
  notification and its existing 500-unit tick refresh. Add no new timer.
- Learned refresh finds control `0x221A`, preserves scroll, clears the native
  list, walks the unit's existing learned-spell collection, resolves each Action
  Description and checks its required level against native ExperienceLevel.
  Its hard-coded Action-ID switch selects an INTn image set. The common append
  at `0x4A3E16` calls `0x672410` with the Description's display name.
- Active refresh finds `0x221B` and walks the actual attached effects. The
  existing private-overlay adapter aliases only a declared overlay to XR01's
  native label branch. Its common append at `0x4A48CD` calls `0x672450` with a
  native 12-byte string. Native effect ownership/expiration determines presence.
- Both paths build a stock `0x6C`-byte image object (`0x687E50`), select one
  resource (`0x6877A0`), image FourCC (`0x6877F0`), set (`0x687F30`), frame zero
  (`0x6873A0`) and flags 9 (`0x687600`). Message `0x24` copies the image into the
  native list row. The temporary is destroyed through `0x687770`.
- Learned INTn icons are 24×24; active IX93 icons are 25×25. Set 1019 is a
  version-4, one-direction, one-frame static template in both archives. These
  are not the equipment panel's 23×23 icons.
- `CYDialogListboxItem` vtable `0x769844` uses the stock dispatcher `0x6733A0`.
  Message `0x62` sets a row's native tooltip string (channel 5 through
  `0x6D0CF0 -> 0x6D0660 -> 0x6CE250`). It copies a native string; never pass a
  raw char pointer. Native row destruction `0x6CE0C0` frees that copied string
  and the copied image. No Manager hover cache or borrowed row pointer is needed.
- AP78 inherits tooltip forwarding `0x468760`. `SimpleMenu::tooltip` at
  `0x4B4C00` receives the hovered row index and reads its string with message
  `0x61`. The ordinary tooltip manager owns hover timing, painting and removal.
- AP78 command handler `0x4A3B10` handles navigation, not casting a list entry.
  Thus the same native read-only row renderer can present declared passive
  information, appended after learned rows at `0x4A407C`, before stock scrollbar
  and scroll restoration. Filter by the selected native hero Description ID
  and current level; do not create fake learned Actions for passive entries.

The extension changes data supplied to these stock row builders. Source and
generated resources must both prove owned identities and literal icon storage.
Private rows cannot claim stock spells, overlays, heroes or interface atlases.
Unselected features add no hooks or queries. Live row/hover acceptance remains
required before calling this support release-ready.

## Author contract (Steam beta2 test build)

Declare `stock.ap78-info-row.v1` under `runtime_features`:

```json
{
  "type": "stock.ap78-info-row.v1",
  "feature_key": "field-lore",
  "kind": "passive",
  "subject_id": "ZH01",
  "unlock_level": 2,
  "display_text": "Field lore",
  "tooltip_text": "Explains an existing passive ability; this row does not grant it.",
  "image_id": "ZI01",
  "image_set": 1019
}
```

- `kind`: `spell` identifies an owned Action/Standard with `IsSpell`;
  `enchantment` identifies an owned Unit/Overlay; `passive` identifies an owned
  Unit/Character. All subjects must be additions, never stock overrides.
- `unlock_level`: 1–1000 for passives; 0 for spell/effect rows, whose availability
  remains controlled by stock learned-spell levels and actual attached effects.
- `feature_key`: lowercase ASCII logical key, 1–64 bytes. Multiple passive rows
  per hero are allowed and ordered by key, after stock learned-spell rows.
- `display_text` and `tooltip_text`: each 1–512 non-NUL Windows-1252 bytes.
- `image_id`: owned private IMAG FourCC, not any stock atlas. `image_set` is an
  unlayered 24-bit set ID. Clone INTn/1019 for spell/passive (24×24), IX93/1019
  for enchantment (25×25), retaining version-4 header, single direction/frame,
  frame flags and indexed TILE geometry. Only private ID/set/TILE reference,
  palette, transparency index and pixels may differ. The TILE must be in the
  same authored archive. Ordinary art relocation handles its output index.

Do not combine the legacy text-only enchantment declaration and this declaration
for the same overlay. Private ownership is checked across packages; records
cannot claim another package's subject or image. The native record contains no
callback, action or evaluator symbol. A passive display never grants the ability
it describes. No AP78 hook is installed unless this feature is selected.

Source and generated-art validation, malformed-registry rejection and an x86
stock-shaped row harness cover this boundary. Actual in-game display, hover,
scroll and level/effect refresh still need user acceptance.
