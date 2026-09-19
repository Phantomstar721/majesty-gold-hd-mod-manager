# Saved kingdom research and earned-reward bonuses

Test-build author contract: `manager.kingdom-research.v1`. Requires the audited
Steam beta2 1.5.2.28 executable and a private AP52 recruitment parent. The native
order and generated GPL integration must still be exercised through purchase,
completion, cancellation and save/load in the game before a public release.

## Declaration

Add this to schema-3 `runtime_features`, alongside the parent's existing
`stock.ap52-private-recruitment.v1` or `stock.ap52-recruitment-panel.v1` entry:

```json
{
  "type": "manager.kingdom-research.v1",
  "feature_key": "earned-rewards",
  "parent_building": "Example_Guild",
  "action_control_id": 29472,
  "descriptor_template_control_id": 5020,
  "required_level": 3,
  "price": 3000,
  "gold_bonus_percent": 15,
  "experience_bonus_percent": 15,
  "progress_control_id": 29473,
  "active_display_control_id": 29474,
  "completion_text": "Example Research"
}
```

All fields are required. `feature_key` is a stable lowercase key, not a display
name. Identity derives from package UUID plus this key; keep both stable across
updates. Keep command IDs stable while existing saves may contain their orders.
The Manager rejects identity/command/completion-attribute collisions instead of
silently renumbering saved state. At most 32 research features, one per building
family, are supported. Different features add bonuses to the original award;
multiple copies of one qualifying building never stack the same feature.

`parent_building` identifies the package-owned Description chain. All stages
must have the same private dialog and three-character ID prefix, followed by
1/2/3. Their package-owned DAT templates must supply consistent `title` and
numeric `Level` values; the Manager derives the actual GPL title, rather than
assuming it equals the Description name. Those values must also be declared in
their GPL prototype, as with ordinary stock guild templates.

`required_level` is 1..3, `price` is 1..1,000,000, and percentages are 0..100
with at least one nonzero. Price remains subject to Majesty's stock research
cost calculation. The descriptor template supplies the **stock research
duration**, not a timed spell or a borrowed stock completion flag. Supported
template commands are 0x1388..0x138D, 0x1392, 0x139C..0x139D,
0x13A6..0x13AB, 0x13B0..0x13B3, 0x13BA and 0x13C5..0x13CA.
Completion text is 1..96 Windows-1252 bytes without NUL.

## Primary-panel resource group

Supply these five unique controls in the primary SMNU, with package-owned STRT
labels/tooltips. Action, progress and active-display IDs must be greater than
0x22CE. Quote ID is **action + 1000**; icon ID is **action + 500**. None may
overlap recruitment or another recipe's controls. The icon may be offscreen.
Do not place this research group in the recruitment child.

Choose one coherent stock layout:

| Control | Standard group | Compact group |
| --- | --- | --- |
| Action | AP99 / 0x1388 | AP24 / 0x1F49 |
| Quote | AP99 / 0x1770 | AP24 / 0x1184 |
| Progress | AP52 / 0x1F56 | AP24 / 0x2009 |
| Active label | AP52 / 0x1F57 | AP24 / 0x227A |
| Icon | AP99 / 0x157C | AP99 / 0x157C |

Clone the literal widgets; change only private IDs, stock-compatible artwork,
labels/tooltips, hotkeys and positions. Preserve geometry, fonts, drawing flags
and caption bounds. The compact action is 139x21 and quote 33x17; placing them
at (7,223)/(112,225) is valid if the rest of the author's panel leaves that
space. AP24 supplies only the widget shape: this does **not** invoke Rage of
Krolm or use a timed effect. The runtime dispatches the ordinary AP99 research
order against the live AP52 building.

## Ownership, activity and persistence

- The offer requires a living, completed building at the declared level.
  Starting an upgrade is not completion.
- The authoritative queued-command gate reserves the paying player before
  the stock debit. Other buildings cannot start a second purchase for that
  player. Failed submission releases the reservation without a refund or a
  duplicate debit. Stock is the sole payment/scheduling owner.
- Research and recruitment share the stock building activity tuple and cannot
  run concurrently. Hidden recruitment commands cannot bypass the busy state.
  Closing a panel does not cancel the order.
- Stock order 0x4005/callback 0x2009 owns research duration and save/load.
  Completion records the original paying player, independently of the original
  building. A namespaced native completion bit is only the row's display mirror;
  no stock upgrade/technology bit is borrowed for ownership.
- Cancellation relinquishes the reservation and clears the private busy tuple
  through ordinary native setters. The existing order manager retains cleanup;
  no extension refund is created. Dead/stale reservation references are pruned
  on the next query. There is no polling worker or custom timer.
- Saved GPL attributes on `GplAIRoot` hold completion/reservations; saved hero
  attributes hold fractional bonus credit. A DLL pointer or external file is
  never the authoritative purchase record. Each benefit requires a currently
  living, completed qualifying building owned by that player. Losing all such
  buildings suspends the benefit; rebuilding restores it without repurchasing.

## Reward boundary and overhead

The Manager inserts the bonus into stock `give_gold` before its positive-award
display/write and into `give_exp` after the stock level divisor. Original pool
splits, payer debits, XP divisors/rounding and level-up callbacks are preserved.
Only living recipients with stock `subtype == Hero` qualify; custom heroes are
included without a title allowlist. Integer fractions accumulate separately per
hero, feature and currency, so repeated small awards retain the full percentage.
Reward arithmetic uses native integer helpers because GPL binary expressions
convert through a narrower fixed-point representation. This protects the added
bonus calculation; it does not enlarge Majesty's stock numeric limits or repair
previously corrupted saved gold/XP.

Transfers, refunds, treasury income and initial purses are not hooked. Custom
genuine earnings must settle through `give_gold`/`give_exp`; direct Gold or XP
writes are not automatically classified. Do not route refunds or transfers
through the earnings helper. Direct level advancement is not earned XP.

## Optional active-building artwork

Add `"active_effector": "Example_Research_Active"` to the declaration to show a
private effect on every currently qualifying building of a researched owner.
Omit this field to retain the effect-free behavior. The name is an ASCII
Description identifier of at most 64 characters, not a function or file path.

Supply one package-owned `Unit/Overlay` Description cloned literally from stock
`super_charge_effector` in `M_Overlays.xml`. Privatize its Name, ID, display text
and ImageIDBase, and supply that private IMAG/art. DefaultSound may be changed
to `0`. Keep the stock directionless, nonblocking, root-attached shape, menu 11,
StackPriority 0, DialogID 0 and TransparentToMouse; do not add AttachmentPointID
or behavior callbacks. Place the visual relative to the building through the
private artwork's stock frame offsets, not a separate tracking controller.

The Manager uses stock `CheckEffector`, `CreateEffector(..., 1, "Infinite")` and
`DeleteEffector`. The effect is cosmetic: its presence never grants research.
Completion updates existing qualifying buildings of the original paying owner.
Readiness/upgrade and ownership events update the affected building after the
stock operation. Rebuilt eligible buildings restore the visual without another
purchase. Stock attached-object destruction owns cleanup when a building dies.

On entering a new or saved game, one pass through the stock building collection
reconciles selected visuals after initialization, not while save links are being
read. The check is idempotent: it leaves an existing correct effect untouched.
There is no per-frame work, timer or periodic scan. Native hooks are installed
only if at least one selected research declares this option. This is not a
migration guarantee for saves loaded with a changed prepared mod set.

The first live acceptance check should include two completed eligible buildings,
research completion, an upgrade/rebuild, transfer to an unresearched owner, and
save/reload using the same prepared profile. These lifecycle paths have not yet
all been demonstrated in the game with this adapter.

No selected research means no service insertion or research hook. When selected,
work occurs at purchase/completion, open-panel stock notifications and eligible
award calls, plus the optional visual events described above. Availability uses a positive cache that revalidates its borrowed
building every award; a cache miss uses the stock owner/title-filtered building
query. Unpurchased features do not query buildings. No background map scan,
per-unit watcher, custom scheduler or per-frame world query is installed.

`MM_KR_*` symbols and the MMFR/MMCP records are Manager-owned implementation
details. Authors declare the feature and resources; they must not add service
functions, native research hooks or handcrafted runtime registries.
