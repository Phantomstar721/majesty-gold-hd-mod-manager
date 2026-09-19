# Stock equipment extension audit

Status: **beta2-only stock-value implementation; live lifecycle validation pending**.
Recorded 2026-09-18. See [the authoring contract](stock-equipment-contract.md).

The intended extension is generic registration of private weapon and armor
identities. A display category is not an identity: two packages may use the
same category while owning different items. Neither extra attack slots nor
automatic spell-damage scaling is implied.

## Reference build

The native observations below are from the installed Steam beta2 executable,
PE timestamp `0x5A8A11D5`, preferred image base `0x00400000`. Addresses in this
document are preferred virtual addresses, not runtime pointers. These are
not yet an audited profile for the other supported executable.

GPL references are relative to `SDK/OriginalQuests/GPLMx`. Presentation assets
are the installed stock CAMs, not assets inherited from a mod package.

## Description registration and birth

`Data/M_Characters.xml` supplies `AllowedWeapon`, `AllowedArmor`,
`WeaponBasicDamage`, and `ArmorBasicDamage`.

| Boundary | Observed native behavior |
| --- | --- |
| `0x00421E40` initialization | Registers weapon enum names 0–9 in the map at `0x007DF4F0` and armor names 0–4 at `0x007DF510`, including zero/None. |
| `0x005CAC30` | Stock string/index insertion used by both maps. This establishes a reusable insertion operation, not yet a safe extension installation point. |
| `0x00423B04` / `0x00423B3D` | Parses the allowed equipment enums with `0x005C6790` into description lists at offsets `+0x90` / `+0xB0`. |
| `0x00423F96` / `0x00423FEF` | Uses those same enum maps through `0x005C8120` when writing descriptions. A private numeric value without a registered name is insufficient. |
| `0x0044DA34`–`0x0044DABA` | Reads the first allowed weapon and inserts the native `WeaponTypeIndex` attribute (`0x19565041`). The preceding armor branch inserts `ArmorTypeIndex` (`0x1A565041`). |

The enum maps, hero descriptions, and current native attributes are distinct
objects. In particular, the equipment presenter reads the description's
allowed list; changing only a hero's type-index attribute does not establish
a custom displayed item.

The description-catalog initializer calls enum initialization at `0x00421E15`,
before its subsequent initialization calls. The native vehicle constructor
`0x0044D640` installs vtable `0x0075414C`; slot `+0x0C` is the description-to-
attribute initializer `0x0044D7C0`. Its base-stat writes use attributes
`0x12565041` (weapon) and `0x15565041` (armor).

The native clone path `0x0044D740` calls `0x005CF580`, which copies the existing
integer attribute map at unit `+4` through `0x00678F20`. Private equipment must
use this existing state, not a separate transient map keyed by unit pointer.
Description initialization across repeated game/menu cycles remains an
installation-order verification gate.

## Shopping, timing, callbacks, and cleanup

`DecisionTrees/Modules/mx_Purchase_Equipment.gpl` checks a positive type index,
the hero's existing upgrade preferences, gold, and stock providers. It tries
weapon Blacksmith, armor Blacksmith, weapon Wizard, and armor Wizard before
later stock needs. `BlackSmith_Check` / `WizGuild_Check` select the provider;
`Task_Number` identifies the attribute to upgrade. The final handoff sets
`ActiveScript = Use_Building`.

`TaskModules/Characters/mx_use_building.gpl` owns travel, destination-death
reset, hiding, occupancy, and dispatch to the building's `Visited_Script`.
`mx_Building_Data.dat` selects the upgrade/enchantment visit functions.

`TaskModules/Buildings/mx_Upgrade_Equipment.gpl` uses `Enter_Building`, the
stock interval 19000, and `Obtain_Upgrade`. The callback restores
`Normal_Cycle`, checks successive research/gold thresholds, accumulates the
price, calls `Spend_Gold` once, and writes the highest purchased rank.

`mx_Enchant_Equipment.gpl` uses interval 17000 and `Obtain_Enchantment` with
Wizard level gates. It captures then clears `Task_Number` before the purchase.
`Done_Enhancing_Equipment` owns `Exit_Building`, purchase feedback, existing
palace/Blacksmith trip side effects, task-number cleanup, and `Reset_Tasks`.

An extension must change only the agreed data lookups inside these paths.
It must not introduce another shopping state machine, per-hero watcher, or
purchase timer. Quote and transaction must consult identical prices/gates.
`Buildings/mx_enter_building.gpl` registers the hero in the existing occupant
notification list; `exit_building` removes it if the building remains alive,
calls `Reset_Tasks`, restores the normal active-script interval, unhides the
hero, and creates stock exit feedback. `mx_LowLevel.gpl::reset_tasks` stops
movement, clears the target, restores the basic/back scripts, and clears
hostiles. None writes equipment attributes. Native interrupted-visit dispatch
must remain unchanged: the stock-value extension requires no purchase hook,
extra callback, occupancy state, or cancellation handler.

## Rank is also the bonus

Stock structural ranks are 0–3 at the Blacksmith, with incremental weapon
prices 100/200/300 and armor prices 300/600/900. Enchantment ranks are 0–3 with
prices 200/400/800. Stock research/building levels gate availability.

The structural and magical rank attributes also directly supply numerical
combat bonuses. Writing 5 to mean “quality tier 1 grants +5” would make the
stock shop see rank 5 instead of tier 1.

`TaskModules/Subtasks/mx_make_attack.gpl::damage` consumes base weapon damage,
structural and magical bonuses, Strength, armor, and separate coating state.
`spelldamage` uses its spell/Intelligence path and enchanted armor, not the
weapon bonuses. Arbitrary per-tier values therefore require separate,
consistent rank-to-value resolution in combat and display while leaving
shopping/loot rank ownership intact. That is more than name/art registration.

Poison and Fire Balm remain separate stock state. Any selected package's
coating attributes and confirmed-hit callbacks must remain that package's
authority. Equipment registration must not duplicate coating effects or
turn a miss, deflection, or spell into an extra coating trigger.

## Native presentation and stock overflow

Stock `Data/textdata.cam` contains `SMNU/AP22` and its captions/help text.
The weapon control `0x1B5C` uses `IMAG/INBw`; armor `0x1B5D` uses `IMAG/INBa`.
Both controls are 23×23 pixels. The referenced stock TILEs are also 23×23.
The sampled equipment IMAG sets have one direction and four quality frames;
there is no enchantment image matrix in this stock presentation.

The native equipment presenter singleton is obtained at `0x00503D80`, with
constructor `0x005038D0`. It owns four lookup maps:

| Offset | Lookup |
| --- | --- |
| `+0x00` | Armor enum → stock name table |
| `+0x20` | Weapon enum → stock name table |
| `+0x40` | Weapon enum → icon set |
| `+0x60` | Armor enum → icon set |

Names come from `Data/gpltext.cam` `STRT/EN01`–`EN15`, not the AP22 caption
table. These name tables contain between five and seven entries, including
names beyond the three purchasable upgrades.

- `0x005033D0` formats the weapon name; `0x00503190` formats armor. Each reads
  the first allowed type from the hero description, uses the structural rank
  to choose a name, and clamps to the last available name when rank is at or
  above the table length. This does **not** clamp the actual attribute.
- Those formatters append numeric base/structural/magical values. Stock does
  not select a separately authored name for every enchantment combination.
- `0x00503620` / `0x005036D0` resolve weapon/armor icon sets from the same
  description identity. `0x005027A0` / `0x005028C0` return the structural rank
  used as the frame selector.
- AP22 weapon refresh `0x004A34E0` and armor refresh `0x004A3610` call those
  lookups, update the existing text/icon widgets, and retain native ownership.
  Opening the panel (`0x004A38C0`) calls these routines; the attribute-change
  dispatcher preceding `0x004A3AF7` refreshes affected controls.

The stock image draw path at `0x00687A2F` calls `0x0067F020` for the frame
count. `0x00687A34` compares it with the selector at image-object `+0x1C`;
`0x00687A39` writes selector **zero** when it is at or above the frame count.
Consequently a four-frame stock equipment image uses frame 0 above rank 3.
This changes only the widget's selector, not the hero's bonus attribute.
Highest-frame overflow is a different presentation policy and must not be
silently described as a stock clone.

The equipment singleton is released by `0x005038A0`, called from the interface
cleanup path at `0x00428DD9`. It calls destructor `0x00502FC0`, frees the
object, and clears the global pointer. The destructor releases the loaded
name tables through their virtual `+8` method and clears all four maps.
Registration should extend each newly constructed native presenter and use
the stock resource acquisition operation (`0x00679A80`); it must not retain
table pointers across this cleanup or register the same borrowed reference
under multiple owners.

## Loot and transitions

`TaskModules/Buildings/mx_Building_Deaths.gpl::chance_weapon/chance_armor`
produces structural and magical values above the shop cap, compares their
sum with existing equipment, and writes the rank attributes. An equipment
extension must not silently cap these gameplay values to 3.

`TaskModules/Subtasks/mx_give_exp.gpl` changes equipment attributes during the
stock Gnome champion conversion. Other quest scripts also grant ranks
directly. Preserve those writers rather than assuming the shop owns all
equipment updates.

The unit writer at `0x005EB330` writes the unit description identity and then
serializes the attribute map at unit `+4` through `0x00678C00` (call at
`0x005EB444`). The map writer writes a version, count, and every key/value
pair; its value operation `0x0066B2D0` writes four bytes without a stock
equipment enum range restriction. The load path calls `0x006790A0` at
`0x005EB15D`; that reads the pairs and inserts them through `0x00678E30`.
Description resolution uses the saved description ID (`0x005CF7B0`); it does
not serialize the native equipment name/icon lookup tables.

Thus type indices and rank/bonus values can stay in the existing save
structure, while the same prepared profile must recreate their enum and
presentation definitions. A separate equipment save store is unnecessary.
Stable allocation and incompatible/removed-definition handling are still
required; this does not justify loading a save with a changed mod set or
reassigning a saved private index.

`mx_Spells.gpl::Shared_Begin_Resurrect/Shared_End_Resurrect` and
`Reanimate_Begin/Reanimate_End` retain the same agent, clear death flags, and
restore activity/HP/type without overwriting equipment attributes.
`Buildings/Mausoleum.gpl::Mausoleum_Resurrect_Begin/Finish` similarly releases
the retained occupant and restores its scripts/HP/home. Preserve those stock
paths.

Native `ChangeUnitType` (`0x00432B10`) resolves the requested description,
records stock transformation attributes, and calls `0x004494C0` with the
initialization flag false. That routine changes the description binding and
refreshes existing native controllers/presentation; it does not call the
birth equipment initializer on this path. Thus converting a hero is not
permission to reset its equipment ranks or base values. Existing explicit
stock GPL conversion writes remain authoritative.

Owner changes at native setter `0x005CF320` update owner and dispatch the
existing refresh without rewriting the attribute map. Base unit destructor
`0x005CF900` performs stock unit notification/engine cleanup and destroys
the map at `+4` through `0x00420BF0`. No extension-owned per-unit state is
needed for equipment identity or bonuses.

## Scope decision before implementing the contract

Two scopes are materially different:

1. **Stock-value equipment:** private identities for both slots, supplied
   names/art/base stats, and the stock rank/bonus, economy, research, loot, and
   enchantment-number rules. Extend the existing lookups and retain the stock
   lifecycle. Above-shop names/art need explicit stock-compatible coverage.
2. **Independently configurable tiers:** in addition, supplied tier bonuses,
   prices, research gates, and enchantment-specific names/art. This requires
   coordinated value/presentation substitutions across shopping, combat,
   loot, and panels; stock does not provide one item-definition table that
   already drives all these behaviors.

The requested first integration now selects stock-value equipment. The
broader scope needs confirmation before adding custom policy. Its
overflow value rule cannot be invented from four declared tiers. Spell
consumers also require an explicit scope decision; neither option
automatically changes spell damage.

For stock-value equipment the existing GPL expression
`$GetAttribute(agent, #ATTRIB_Weapon_Struct_Bonus) +
$GetAttribute(agent, #ATTRIB_Weapon_Magic_Bonus)` is already the generic
read-only weapon bonus lookup. Armor uses the corresponding armor attributes.
No new native function or runtime polling is needed for that query. The mod
owns any explicitly approved damage consumer; the Manager must not globally
inject this expression into spells or add coating callbacks.

The initial `stock.equipment.v1` implementation is restricted to beta2. The
public 1.5.2.24 reference remains unavailable and that executable is rejected
for this feature, not guessed from beta2 address differences. Other supported
features are unchanged. Installation verifies each new native registration
boundary before redirecting either call.

The extension registers strings/indices immediately after stock enum
initialization and presentation entries immediately after each stock presenter
construction. Native teardown owns the additional entries. No purchase,
combat, per-unit attribute, save, timer, or cleanup hook is added. The Python
and native MMFR v4 readers validate the same fixed equipment record format;
profiles without equipment retain their prior wire format and install no
equipment hooks.

Icon evidence is the literal INBw/INBa header and matching
single-direction/four-frame set body: Original/version 3 uses 116 bytes;
MX/version 4 uses 124 bytes, inserting words `0x00010000, 0` before the four
frame pairs. Its four TILE fields may differ; the remaining words must match
the corresponding stock version. Referenced TILEs must preserve stock type-1
23x23 storage, including the embedded palette (1,587 bytes). Private sets are
bound to the native interface image only after positional art relocation,
within the same art domain. Binding clones the destination's stock INBw/1004
or INBa/1000 body and replaces only its four TILE fields, rather than copying
the source body beneath a potentially different container version. Existing
stock sets are untouched. Generated validation checks this same coherent
header/body contract; the general end-anchored reference reader is not enough
to catch a mixed Original/MX layout.

The native frame-count lookup at `0x0067F020` scans the image's set records
linearly and compares the full 32-bit set identity. Appending private IDs does
not require sorting or renumbering existing stock sets. Weapon and armor icon
lookups at `0x00503699` and `0x00503749` use the native maps without a stock-only
enum range clamp. The name map accessor initializes a new value to null at
`0x00502B99`; the destructor iterates and releases both name maps at
`0x00503057` and `0x005030E0`. These boundaries support the extension's collision
check and native ownership of additional resource references.

`tests/test_equipment_source_integration.py` provides an opt-in, read-only
source check using `MAJESTY_EQUIPMENT_PACKAGE`, `MAJESTY_BETA2_EXE`, and optionally
`MAJESTY_EQUIPMENT_DEPLOYED`. It verifies the exact authored identities and
Description substitutions, forces icon relocation to different indices in an
in-memory fixture, binds both stock images, and checks preservation of original
stock sets and source files. It neither prepares nor writes a merged profile.

Remaining beta2 activation check: user-prepared fresh game, both equipment
slots, native purchase/enchantment refresh, above-shop ranks, save/reload with
the unchanged profile, return to menu and start/load again. Static checks and
synthetic tests do not substitute for that controlled in-game lifecycle check.
