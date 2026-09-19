# Private AP52 three-choice recruitment

An opt-in, schema-v3 presentation recipe for a private guild with exactly three
recruit choices. It uses the stock AP52 command dispatcher and per-type counts,
the shared guild recruitment presenter, and the shared building upgrade
lifecycle. The stock Warriors Guild is unchanged.

## Package contract

Declare the building family, not just its first numeric tier:

```json
{
  "custom_buildings": [
    {
      "local_name": "Example_Guild",
      "controller_base": "AP52",
      "panel_resource_template": "AP52"
    }
  ],
  "runtime_features": [
    {
      "type": "stock.ap52-private-recruitment.v1",
      "panel_key": "example_recruitment",
      "parent_building": "Example_Guild",
      "third_price_control_id": 29441
    }
  ]
}
```

This is a fragment of the complete mod definition. The Manager derives the
runtime capability and MMCR record; authors must not distribute their own MMCR.
The third price control is a private, nonzero unsigned 32-bit ID greater than
0x22CE. It must not collide with another recipe's controls on this parent.
Other recipes may use the same AP52 parent with independent private commands.
Parent commands in the stock range through 0x22CE remain reserved.

Descriptions supply the choices and gameplay values:

- Exactly three distinct `Game/Produces/Unit` entries, in the same order at
  every tier. Their IDs are Description names, as in stock XML.
- `IsGuild` and positive shared `MaxGuildMembers`; no per-type capacity is
  added. Hero descriptions retain their stock cost and recruitment-duration
  fields, birth scripts, home ownership, actions and artwork.
- One private `Game/DialogID` shared by the family. SMNU and STRT are
  package-owned and relocated by the Manager; no author FourCC field is
  required in the mod definition.
- At most three levels, with reciprocal `UpgradeTo`/`UpgradeFrom` names,
  stock same-family resource IDs ending in 1/2/3, and the stock upgrade scripts.
  A one-level guild may omit the upgrade links. Price, HP and capacity remain
  description-driven. No fixed mod names, prices, IDs or capacity are used.

## Required SMNU controls

### Separate recruitment subpanel

To put recruitment on a secondary panel instead of the compact main rows, use
`stock.ap52-recruitment-panel.v1` **instead of** the inline recipe:

```json
{
  "type": "stock.ap52-recruitment-panel.v1",
  "panel_key": "example_recruitment",
  "parent_building": "Example_Guild",
  "third_price_control_id": 29441,
  "source_dialog_id": "RCRT",
  "open_command_id": 29442
}
```

The building remains AP52/AP52. Supply the package-owned child SMNU/STRT pair;
the Manager relocates its dialog along with the parent. The opener is a literal
AP10 0x1F49 widget (93x26); its artwork set may be changed to the stock Heroes
button. Back is the literal AP69 0x1F4D widget. Each of the child's three recruit
commands uses AP52 **0x1389's 189x27 widget**, including its caption rectangle,
with separate stock quotes placed inside the button. Command/index bindings
are exactly those in the table below. Keep shared progress/name 0x1F56/0x1F57.
Each recruit button may use either literal stock AP52 font: `fnt4` from
0x1389 or the smaller `fnt7` from 0x1388/0x1F48 (SMNU property 0x12).
No other fonts or changes to caption bounds, colors, drawing flags or artwork
layout are allowed by this font option. Quotes and navigation retain their
exact template fonts. Native caption formatting and ownership are unchanged;
the package chooses the font, with no runtime resizing or font replacement.

The main keeps stock counts, utilities, Heroes and the AP53 upgrade group.
Retain all original AP52 IDs and the third-price control on both resources;
move unused controls offscreen. Main recruit buttons, quotes and progress are
offscreen and suppressed by the runtime. Child utilities/counts/upgrades are
offscreen. Hidden recruit hotkeys cannot execute on the main. Child input is
limited to recruitment, Back and footer tracking controls 0x1F40/0x1F41.
Repair-route command 0x1F5B remains native on the main and is blocked with
the other hidden utilities on the child. Closing the panel does not cancel a
pending recruit.

The child retains the actual AP52 allocation and all 17 native vtable slots,
not AP69's shorter class. Its setup copies AP69's `controller+0x30 = 1`
classification before native AP52 setup reaches the common layout helper.
That helper selects the secondary container or the stock primary replacement
at low resolution. The literal AP10 opener owns the parent-removal return;
AP69 Back resolves the **child's** building context and recreates its private
parent. Parent destruction cannot clear the surviving child's recipe.

Native base setup's beta2 0x495660 auxiliary APb9 is construction UI: it checks
attribute 0x01425041, creates APb9 only while construction is incomplete, and
removes it when complete. APb9 setup 0x4686E0 positions its own widget relative
to the primary container; it does not install a second recruiting controller.
That setup and the base destructor's auxiliary cleanup remain native.

MMCR v18 adds child/opener fields to recruitment records. Inline-only output
continues using v17. Class copies are cached separately for inline, main and
child modes, with no recurring work while their panels are closed.

### Inline recruitment

| Native Produces index | Recruit command | Price | Count | Count icon |
| --- | --- | --- | --- | --- |
| 0 | 0x1F48 | 0x1752 | 0x1F1B | 0x1F19 |
| 1 | 0x1389 | 0x1F51 | 0x1F0D | 0x1F52 |
| 2 | 0x1388 | declared third_price_control_id | 0x1F1C | 0x1F1A |

Each recruit button is a literal clone of AP52's compact 139x21 Call-to-Arms
**widget shape**, with its own command, caption, tooltip and hotkeys. This
does not copy the Call-to-Arms gameplay action. Each price is an independent
clone of stock AP52 control 0x1F51. The three numeric counts and icons retain
their stock widget types. Count rectangles may be resized; other required
widgets retain their native sizes. Positions, text references, hotkeys and
private artwork identities are package presentation.

Recruit buttons may adjust their native SMNU `0x2A` caption rectangle within
the unchanged 139x21 widget. For example, `(2,4,135,14)` uses the spare width
inside the button instead of Call-to-Arms' narrower `(2,4,103,14)` rectangle.
Font, colors, flags, sprite, widget type and the separate price remain stock.
The Manager validates these bounds; it does not resize or draw text at runtime.

Keep the native shared progress/name controls 0x1F56/0x1F57. They show the one
building-wide pending recruit; this does not create three parallel queues.
Import AP53's literal level/upgrade group (0x1E28, 0x1F47, 0x1F4F and its
decorations). The terminal stage is hidden/disabled by stock upgrade logic.

Retain **every original AP52 control ID** once. Original native construction
happens before private controller capture, so unused controls must remain valid.
Move alternate/single-extra controls 0x22CE, 0x1F0E, 0x1F11, 0x1F12,
0x1F13, 0x1F14 and Call-to-Arms 0x1F49/0x1181 outside the panel, for example
to (1500,1500). The private command guard also suppresses 0x1F49/0x22CE.
The double-extra backing 0x1F18 may also be offscreen; its stock presenter
sets visibility, but addresses the numeric counts/icons individually.

The stock presenter writes localized “RECRUIT %s” captions from the actual
hero Description title. Authors must check those captions fit their layout
and localization; a private STRT label does not replace the dynamic caption.
The index in the table is the game's loaded Produces sequence, not an assertion
that XML child order is preserved. Verify each command's actual recruited unit
before assigning row icons, static tooltips or hotkeys. Do not rewrite the
native dispatcher to compensate for an assumed XML order.

### Caption ownership and clipping audit (beta2)

The shared presenter calls `0x4967D0` for the indexed unit's Description title,
then formats the localized caption using the stock scratch String. Panel
setter `0x4B5150` sends property `0x5C` to the exact control ID via `0x667DE0`.
The button's `0x675650` setter owns a separate String at widget `+0x30`;
`0x63AAF0` copies its bytes, so subsequent rows and price formatting do not
overwrite earlier captions. Stock widget teardown owns that String's cleanup.
There is no need for Manager-owned caption buffers or extra refresh callbacks.

A read-only live trace on 2026-09-17 confirmed complete, independently stored
captions for commands `0x1F48`, `0x1389`, and `0x1388`. The source XML listed
the opposite first/last unit order to the loaded descriptions. The visible
partial labels were not missing names. Native draw `0x674C29` onwards applies
the SMNU caption rectangle from widget `+0x84..+0x90`; the narrow single-line
box clips text wrapped below it. Widen the bounded author rectangle, keeping
the existing stock formatting, layout, invalidation and drawing lifecycle.

## Stock lifecycle audit

Addresses in this section are virtual addresses, base 0x400000. The detailed
gameplay trace is beta2; all copied presenter bytes and branch/operand locations
are separately audited for both supported executable profiles.

| Boundary | Public | Beta2 |
| --- | --- | --- |
| AP52 vtable (17 slots) | 0x73E5F4 | 0x7572CC |
| AP52 setup | 0x4B2010 | 0x4B2900 |
| AP52 command | 0x4B2170 | 0x4B2A60 |
| AP52 event | 0x4B22C0 | 0x4B2BB0 |
| Shared guild recruit presenter | 0x4962E0 | 0x496AF0 |
| Shared guild tooltip | 0x496730 | 0x496F40 |
| AP52 per-type count | 0x4B2440 | 0x4B2D30 |
| AP52 count presenter | 0x4B2580 | 0x4B2E70 |

### Recruitment, ownership and timing

1. AP52 construction/setup delegates to shared guild setup (beta2 0x4963E0).
   Setup invokes virtual +0x34 (recruit rows), +0x40 (counts), then the basic
   building setup. The original deleting destructor and 17-slot class boundary
   are retained.
2. The shared presenter resolves a Produces index through 0x496560; the private
   copies change only the index passed to that resolver and the native
   name/quote/affordability helpers. Construction, busy state, capacity,
   scenario availability for the **actual produced unit ID**, price formatting,
   progress and ordinary native eligibility checks remain in the copied code.
3. AP52 dispatch sends 0x1388 to native recruit index 2 and 0x1389 to index 1.
   Index 0's 0x1F48 delegates to the shared command handler 0x4970C0, which
   checks its quote/funds and invokes 0x496FB0(0). The native dispatcher,
   packet arguments and return values are unchanged.
4. 0x496FB0 resolves Produces, obtains the building position and submits the
   original recruitment message through 0x4DC880 with mode 8, flags 3 and the
   parent building ID. Temporary stock arguments retain their original cleanup.
   Network/world dispatch at 0x4DC770 selects delayed recruitment 0x44E000.
5. 0x44E000 re-resolves the parent, rejects an existing recruit duration or full
   shared capacity, checks/debits the owner, records expenditure and emits the
   native currency notification. It writes native type/flags/start/duration
   attributes (0x0E425041, 0x0F425041, 0x38425041, 0x0D425041).
   Capacity is the native relation-100 member count against MaxGuildMembers
   (0x43E2F0 / 0x43E3A0), not a Manager-maintained list.
6. The native order manager 0x4DCA20 calls +0x7C (0x4DD9C0). This creates the
   existing 0x4002 delayed order with callback 0x2006 and the hero description's
   duration. Its normal serialized order lifecycle owns time and save/load.
   Callback 0x4DDA30 handles native completion reason 2, checks owner state,
   invokes 0x44DC90 with the saved fields, then clears pending recruitment
   attributes. Native cancellation reason 1 clears the same pending state.
   No Manager timer, refund/debit path or pending-unit state is introduced.
7. 0x44DC90 constructs the hero, attaches relation 100 to the parent and invokes
   the native birth-script machinery. SDK `mx_Hero_Births.gpl::hero_birth`
   obtains the native parent as home and updates guild members. Existing
   grave/dismissal handling (`mx_Hero_Deaths.gpl`), stock member filtering and
   guild destruction scripts retain capacity/home cleanup. The recipe never
   creates, removes or refunds a recruit independently of stock gameplay.
8. AP52's event handler delegates to shared guild event 0x496980, which owns
   notification registration/removal and refreshes on currency, pending-duration,
   membership and building changes. Private event copies preserve that ordering.

### Repair-route command is not recruitment cancellation

The beta2 stock AP52 SMNU control 0x1F5B is the 22x17 repair-route button at
(178,126), with the tooltip "Toggle this building on or off the repair route."
Its native dispatch is AP52 0x4B2A60 -> shared guild 0x4970C0 -> basic building
0x495FA0. The branch at 0x496086 calls 0x4C5730 with utility-message mode 8.
That message's handler at 0x4C5CC4 toggles attribute 0x14425041 and clears
0x15425041; it does not touch recruitment state. This is a different message
API from recruitment's 0x4DC880 mode 8. Equal numeric modes do not establish
shared meaning across these dispatchers.

The AP52 progress 0x1F56 and name 0x1F57 are display controls, not a cancel
button. The shared presenter 0x496AF0 reads pending start/duration and fills
the progress widget; 0x496980 refreshes it on duration 0x0D425041 and tick
0x09435358 notifications. Recruitment cancellation reason 1 is handled by
the existing delayed-order callback 0x4DDA30, as described above. The private
command filter neither reassigns a repair utility nor adds a cancellation
button or callback. Main repair/tax commands delegate to stock; the child's
native event and order lifecycles stay intact.

### Upgrades, construction and cancellation

The primary building base already implements upgrades, even though the stock
Warriors Guild does not expose an upgrade chain. AP53 provides the visible
stock group, not a new controller or order.

- 0x1F47 passes from AP52 to the shared guild handler and basic building
  handler 0x495FA0. Its branch 0x495FE0 calls 0x4C36A0, constructing the
  native UpgradeBuildingMessage (message ID 0x3ED).
- The stock message dispatcher selects 0x4C3F40, resolves the owner, and calls
  0x4C3E40. That checks CurrentStageBuilt, the actual UpgradeTo resource's
  scenario gate and stock quote, then checks/debits gold and enters 0x43D090.
- 0x43AF70 changes the description to UpgradeTo, retains native owner/order
  handling, clears CurrentStageBuilt and updates native state. 0x43D090 emits
  building-change notification 0x02435358, refreshes art and calls the stock
  upgrade-script boundary. This is upgrade **start**, not completion.
- SDK `mx_Building_Births.gpl::basic_upgrade` places the building on the
  palace's stock waiting list. The stock peasant build lifecycle moves it
  between waiting/construction lists, performs basic_build, and calls
  BuildingReachedMaxHP at completion. Dead buildings, completed construction
  and disabled repair retain the stock cleanup/cancellation paths.
- Shared building presentation (0x495790 and inherited event handling) reads
  stock readiness, quote and the resource's numeric level suffix. AP52's
  private event copy retains its extra building-change refresh. No upgrade
  timer, peasant script, refund rule or construction state is replaced.

### Capacity increases at completion: author lifecycle contract

**Description capacity alone takes effect at upgrade start, not completion.**
This is stock building behavior, not a replacement made by the private AP52
presenters. A package that wants its extra spaces only after construction must
set the native capacity at both existing stock GPL lifecycle boundaries. A
private `basic_upgrade` wrapper alone is insufficient.

Read-only beta2 1.5.2.28 trace, 2026-09-18 (addresses are preferred VAs):

| Boundary | Native evidence | Consequence |
| --- | --- | --- |
| Upgrade start | `0x43AF82` calls `0x4494C0(newDescription, true)`; `0x44951A..0x449523` invokes building vtable +8 (`0x4482C0`), which invokes +0xC (`0x43D160`) | Native building initialization runs with the **new** Description before construction completes. |
| Capacity initialization | `0x43D197..0x43D1A2` writes `description.Game +0x24` to attribute `0x00425041` | This is the native `MaxGuildMembers` value, in the unit's normal saved attribute map. |
| Description change | `0x5CF7B0` changes only unit +0x7C (Description ID) and +0x90 (Description pointer) | Native stage identity is not proof that the saved GPL stage properties have advanced. |
| Synchronous start callback | `0x43D125..0x43D133` evaluates `building_upgraded` before returning from the upgrade command | Apply the temporary capacity here, **before** its unchanged `$RunThread(upgradescript, 1, agent)`. Doing it inside `basic_upgrade` leaves a scheduled-delay gap. |
| GPL template completion | `$UpgradeAgentAttributes` is registered at `0x43592E..0x43595D` to `0x4303E0` | `0x43044F..0x4305D9` resolves the current Description's GPL template and assigns its GPL properties through the GPL agent/value interfaces. It does **not** call native building initialization or restore `MaxGuildMembers`. |
| Authoritative full check | `0x43E3A0` reads native attribute `0x00425041` through `0x5CEF70`, then compares it to `0x43E2F0(0)` | Both the stock presenter (`0x496DBA`) and actual delayed-recruit command (`0x44E070`) use this check. The command rejects full capacity before the payment at `0x44E104..0x44E11B`. |
| Capacity setter | `$SetAttribute` (`0x42F860`) calls unit vtable +0x124; building `0x449950` delegates storage to `0x5DE410 -> 0x678E30`, then sends normal notifications | Use the real native attribute, not a similarly named GPL property or a UI-only disabled state. |
| Construction completion | Stock `BuildingReachedMaxHP` calls `UpgradeAgentAttributes` only in its already-built-first-stage / unfinished-current-stage branch | Restore the new native capacity immediately after this call and before the unchanged Legendary Heroes override and readiness notifications. |

For a normal stock-upgrade package, keep a package-private GPL capacity value
in each building template, generated from the same author data as that stage's
XML `Game/MaxGuildMembers`. **Declare that value as an integer in the GPL
prototype used by every stage. A DAT assignment alone does not create an
instance property.** Clone the complete stock `Guild` prototype under a private
name, preserving every stock declaration, type, order and body, and add only
the private integer declaration. Point each stage's DAT block at that private
prototype instead of `{Guild`. Do not modify the shared stock prototype or
substitute dynamic attribute creation in a delayed upgrade script.

The native description changes first; the existing
GPL instance retains its completed-stage template values until the stock
`UpgradeAgentAttributes` call. This makes the capacity source explicit instead
of guessing whether a numeric native stage suffix means construction finished.

A read-only live before/after check on 2026-09-18 established this distinction:
the loaded three-stage DAT templates contained the intended 4/6/8 values, but
their shared `Guild` prototype had only its 26 stock declarations. The live
level-1 guild consequently lacked the private property. Starting its upgrade
changed native capacity from 4 to 6 and cleared `CurrentStageBuilt`, while GPL
`Level` correctly remained 1. The missing-property guard then skipped the
capacity correction. The loaded template values and current compiled package
were not stale. Checking only DAT text or the presence of a property name in
compiled bytecode cannot validate this contract: verify the typed prototype
declaration, every template's prototype binding, and the resulting live field.

The two narrowly scoped source additions are:

1. In `building_upgraded`, for this package's declared building family only,
   write its still-current GPL capacity to native `#ATTRIB_MaxGuildMembers`,
   using **1** instead if the stock Legendary Heroes quest condition is true.
   Then execute the original `$RunThread` line unchanged. Do not replace it
   with a new timer, change `basic_upgrade`, or delay the capacity write.
2. In the actual upgrade-completion branch of `BuildingReachedMaxHP`, directly
   after the original `$UpgradeAgentAttributes(theBuilding)`, write that same
   package-private property (now refreshed from the new template) to native
   `#ATTRIB_MaxGuildMembers`. Leave the immediately following stock Legendary
   Heroes override in place. Do not insert this in the repair or first-birth
   branches and do not duplicate construction completion.

Scope both additions to the package's own family/property; preserve all stock
statements, order, arguments and other buildings. These are ordinary GPL source
changes for the source package, not a new Manager runtime feature or panel
declaration. Supply them through the existing stock-relative GPL merge path.
Do not write a second capacity store, scan the world, hook attribute reads, or
intercept recruitment payments. The existing capacity attribute is serialized
with the unit; its lowered value survives an interrupted upgrade/save/load.
Existing relation-100 members and the saved stock recruit order are untouched;
unused spaces in the completed tier remain available. A destroyed building
uses normal unit and membership cleanup with no extension-owned state.

The capacity-template property is part of the package's saved GPL data.
Adding it does not migrate an already-running/older saved instance that lacks
the property; validate this change in a fresh game first. Do not silently
guess a replacement value in an old save. Repeating the same completion path
must not add capacity cumulatively: assign the stage value, never increment it.

For example, a 4/6/8 author table must produce 4 during the first upgrade,
6 after its completion and throughout the second upgrade, then 8 when that
finishes. Verify full and partially occupied guilds, immediate queued recruit
clicks after Upgrade, construction interruption, mid-upgrade save/load, member
death/dismissal, and the Legendary Heroes one-member rule. No Manager native
capacity interception is required for this stock lifecycle implementation.

### Exact adaptation and overhead

#### Capacity-change presentation

The private controller also handles native `MaxGuildMembers` notification
`0x00425041`. This fixes an inherited stock presentation gap: AP52 refreshes
recruitment for the description-change event at upgrade start, but ignores a
subsequent GPL capacity correction. Dispatch reads the corrected capacity
while the buttons can retain the earlier enabled state.

Beta2 trace: `$SetAttribute` at `0x42F955..0x42F966` calls unit virtual +0x124.
Building setter `0x449994..0x4499B0` stores the attribute first, then publishes
`(unitId, 1, attributeId, value)` through `0x4264F0`. The existing controller
registration filter `0x4687E0` matches the unit/category before invoking event
slot +0x20. Neither AP52 `0x4B2BB0`, shared guild `0x496980`, nor inherited
building `0x496200` handles the capacity ID. AP52's description-change case
already supplies the needed stock analogue: invoke recruit slot +0x34, then
count slot +0x40.

After ordinary native event dispatch, only private three-choice controllers
repeat those two virtual calls for the capacity notification. They do not
interpret its value or determine whether the building is upgrading. The
unchanged stock presenter reads the same current capacity/membership as actual
recruitment, retaining its busy, scenario and funds checks in stock order.
Installed virtual slots preserve hidden parent rows, research gating and the
child's no-count behavior. Both completion increases and start-time decreases
use the same event. Already-empty completed-tier spaces remain recruitable.

No registration, ownership, scheduler, gameplay state, setter or native AP52
code changes. Existing stock controller teardown removes its registrations;
closed panels require no work. Other notifications, including simulation
ticks, do not receive an extra recruitment refresh. Reopening uses normal
setup and immediately reads current saved capacity.

The Manager creates private, read/execute-only copies of five audited functions:
shared recruit presenter, shared tooltip, AP52 count presenter, setup and event.
Three recruit/tooltip copies change only literal command/price IDs and five
typed helper calls' Produces index. The count copy changes its temple query to
two **32-bit** true flags, selecting stock's existing two-extra count layout.
Setup/event copies omit only the obsolete Call-to-Arms presenter.

Every external relative branch is relocated from an explicit audited table.
Other bytes, internal branches, stack frames, exception cleanup and native
calls remain identical. Runtime fingerprint checks reject a changed source
presenter. Metadata is reproducible with `scripts/audit_private_recruitment.py`.
The class cache distinguishes the third-price binding; two private panels
cannot accidentally borrow incompatible control mappings.

Copies are allocated only when a selected private recipe's panel is opened.
There is no background polling, map scan, per-unit watcher or recurring work
when the panel is absent. Stock controller teardown uses the existing exact-
instance lifecycle registry. Stock AP52 vtables and executable code are never
modified by this recipe.

## Verification boundary

Automated checks cover schema/registry round trips and malformed data,
stock-derived panel shape, description chains, both executable profiles,
byte-exact scoped copy changes, relative-call targets, x86 helper argument
shapes and controller routing. These do not replace in-game exercise of all
three recruits, full capacity, insufficient funds, both upgrades, interruption,
destruction, reopening and save/load at both one- and two-panel resolutions.
