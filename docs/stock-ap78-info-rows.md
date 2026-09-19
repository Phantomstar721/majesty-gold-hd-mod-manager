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
- Both append functions have the same 54-byte body: create a row with message
  `0x26`, then pass their second argument unchanged to message `0x60`. That
  argument is a **pointer to a 12-byte native string object**, including for
  learned spells and appended passives. Its fields are data pointer at `+0`,
  capacity/flags at `+4` (bit 24 selects wide characters), and length at `+8`.
  Unclaimed stock labels pass through unchanged, including pointer identity.
- Message `0x60` dispatch at `0x673A72` selects **channel 4**, through
  `0x6D0CF0 -> 0x6D0660 -> 0x6CD7E0 -> 0x685050`. It is not channel 0's
  raw-character setter `0x6CD760 -> 0x684F60`. The native parser `0x684A40`
  reads the string's flag byte at `+7` and dereferences the data pointer at
  `+0`; giving it a char buffer treats the first four letters as an address.
  The 2026-09-19 crash at `0x684ACC`, reading `0x6C6C6142` ("Ball"), was this
  ABI mismatch in the learned-row adapter; the passive adapter had the same
  defect. The original harness incorrectly accepted a raw char pointer too.
- `0x685050` clears the old owned label/layout, synchronously parses the source
  to size a new native string, then parses into that allocation. It retains
  no pointer to the Manager view or registry text. The learned adapter's view
  survives its helper's return until the stock append completes; passive views
  live through the direct call. Neither view is a stock-owned allocation and
  neither must be passed to the stock string destructor.
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
- Effect labels first use stock string assignment `0x63AAF0`, which copies the
  source's length, encoding and characters into the stock temporary. The effect
  append then copies/parses that temporary just like a learned label. Tooltip
  channel 5 uses copy constructor `0x63CC60` on first assignment and `0x63AAF0`
  on replacement; null clears its owned string. These paths already used the
  native object ABI. Stock row destruction frees label/layout via `0x6845F0`,
  tooltip via `0x63A3D0`, and image via `0x687770`. Refresh/close retain this
  native ownership, cleanup and existing scheduling; no custom cleanup runs.
- AP78 inherits tooltip forwarding `0x468760`. `SimpleMenu::tooltip` at
  `0x4B4C00` receives the hovered row index and reads its string with message
  `0x61`. The ordinary tooltip manager owns hover timing, painting and removal.
- Hover discovery first requires `FLAG_HAS_TOOLTIP` (`0x400`, enum table
  `0x7DE610`) on the list control. `0x4B5510` rejects controls without it;
  `0x4B5540` then uses native item hit-testing and row status before forwarding
  a row index. Stock AP78 list controls `0x221A/0x221B` have only flags `0x80`.
  Writing tooltip text does not enable that flag. In the 2026-09-19 paused
  capture, the row-owned tooltip strings existed but both controls still had
  `0x80`, explaining why no hover appeared. When info rows are selected, the
  generated AP78 SMNU changes only those two flags to include `0x400`, before
  the stock loader constructs/registers the controls. No event injection,
  hover polling, forced selection or runtime listener is added.
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
row harness cover this boundary. The harness executes the literal stock append
body against a native-object message receiver, exercises learned/passive/effect
labels and both tooltip finish hooks, and checks copying across replacement and
source destruction. Executable audits pin the text dispatcher, parser, copy and
cleanup functions and compare both append bodies to the harness fixture. Actual
in-game display, hover, scroll and level/effect refresh still need user acceptance.
