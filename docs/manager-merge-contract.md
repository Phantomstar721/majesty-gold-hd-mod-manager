# Majesty Mod Manager merge-mod contract

## Scope

This contract applies only to packages shown in **Merge**. Standard `.mmxml`
mods remain independent Active Mod selections; `.mqxml` quests are chosen
through Majesty's stock quest browser rather than the Active Mods list. Source
quests are catalog-only and are never rewritten or duplicated. The current catalog
classification is syntactic: a Mod manifest containing a `CAM` directive is
Merge, while a Mod manifest with no `CAM` directive is Standard. GPL/DAT- or
Descriptions-only mods are not yet routed through the semantic composer, so a
Standard label is not proof that such a package cannot conflict. Semantic
classification of those packages is a target, not current behavior.

The current contract is deliberately fail-closed. It describes what the
composer can prove safe today, not every package that Majesty can load by
ordinary last-writer-wins rules.

These requirements reflect the checks performed by the current public manager.
The manager fails closed on structures and declarations it can inspect; it
cannot infer an undeclared runtime hook or an unannounced visitor-atlas
dependency.

## Required package shape

A merge-ready package must be complete and independently loadable. The manager
must be able to consume the installed package without its authoring repository.
It must contain all of the following:

1. Exactly one top-level `.mmxml` manifest with a stable UUID and nonempty
   display name. Every load path is package-relative, stays inside the package,
   names an existing file, and appears only once.
2. Only the currently supported manifest load directives: `CAM`,
   `Descriptions`, and `GPL` (`Target` plus ordered `Source` children). Every
   composed dataset has `base="Any"`. Dataset variants and unknown directives
   are not silently flattened.
3. At least one readable CAM and one GPL load. Each GPL target is nonempty and
   each load has at least one declared `.gpl` or `.dat` Source. Authors must
   ship every source needed to reconstruct the compiled project; current
   preflight verifies presence and the build recompiles it, but cannot
   independently prove that an omitted source never existed.
4. Every Description document, CAM archive, art file, and audio payload used by
   the mod. A generated package must not retain a runtime path back into a
   Workshop folder or private source tree.
5. A generic package supplies a matching top-level version-3
   `mod-definition.json`. Versions 1 and 2 remain readable for existing
   packages. A trusted UUID-keyed manager compatibility adapter may instead
   supply an external definition or a complete audited replacement package;
   that substitution is reported and never overwrites the installed source.

A version-3 package may omit BDEP, main art, interface art, Descriptions, and
custom-building declarations when it does not change those domains. When it
does supply positional art, each TILE archive still needs its auditable IMAG
reference table and one package may provide at most one archive for each art
domain. Legacy version-1 and version-2 replacement packages retain their
original stricter shape so an existing contract is never reinterpreted.

The only CAM section types currently accepted are `SMNU`, `STRT`, `DATA`,
`IMAG`, `TILE`, `SPLT`, `PALT`, `DSND`, and `WAVE`. Within `DATA`, the current composer
accepts only `BDEP`. Any additional section or resource kind needs a typed,
stock-traced parser before it can join this contract.

## `mod-definition.json` v3

Version 3 has an exact field set; additional fields are rejected rather than
ignored:

```json
{
  "schema_version": 3,
  "mod_id": "{stable-package-uuid}",
  "internal_name": "NamespacedInternalName",
  "display_name": "Player-facing name",
  "custom_buildings": [
    {
      "local_name": "NamespacedBuildingDescriptionID",
      "controller_base": "AP10",
      "panel_resource_template": "AP10"
    }
  ],
  "runtime_features": []
}
```

Each `local_name` is unique within the definition. A declared custom building
supplies matching authored `SMNU` and `STRT` resources and declares the stock
controller and panel template it literally follows.

**Do not put `dialog_id`, a building panel FourCC, or a reserved `CGxx` name in
the version-3 definition.** The standalone mod's Building Description and CAM
resources will already refer to their own source panel ID. During composition,
the manager discovers that existing ID, proves that the package owns the
matching `SMNU` and `STRT`, allocates a collision-free internal ID, and rewrites
the Description and both CAM resources together. Set `custom_buildings` to `[]`
when the mod has no custom building.

The Manager catalogs every stock primary-building controller present in both
supported executables:

`AP01`, `AP02`, `AP05`, `AP06`, `AP07`, `AP08`, `AP10`, `AP14`, `AP17`,
`AP19`, `AP23`, `AP24`, `AP25`, `AP26`, `AP28`, `AP31`, `AP39`, `AP47`,
`AP48`, `AP51`, `AP52`, `AP53`, `AP54`, `AP76`, `AP96`, `APa9`, `APb2`,
`APb3`, `APb7`, `APb8`, `APc3`, `APc4`, `MX00`, `MX02`, `MX04`, `MX06`,
`MX08`, `MX09`, and `MX22`.

Normally `controller_base` and `panel_resource_template` use the same ID,
meaning the package cloned that stock building's behavior and primary panel.
The established `AP07` controller with an `AP10` template is also accepted.
Other cross-pairings are rejected because sharing a C++ class does not prove
that two panel command layouts are interchangeable. `MX09` is the parent used
with the typed AP41 reward-panel recipe below.

The controller's construction, dispatch, state ownership, callbacks, cleanup,
cancellation, and UI refresh lifecycle must be traced to its declared stock
base. `controller_base` is not permission to replace that lifecycle with a
custom watcher, timer, or hook.

`runtime_features` contains typed, versioned stock-behavior recipes. Unknown
types, unknown fields, malformed values, missing package resources, and
conflicting feature identities make the mod red and nonselectable. The records
contain only bounded data; they cannot contain DLLs, patch addresses, commands,
paths, bytecode, or arbitrary script. A conforming package is discovered from
its content and does not require its UUID to be added to the manager.

### Supported typed runtime features

A private stock name generator is declared as:

```json
{
  "type": "stock.name-generator.v1",
  "generator_id": "NM42",
  "name_tables": ["HN81", "HN82", "HN83", "HN84"]
}
```

The generator ID must be a printable four-byte ASCII ID beginning with `NM`;
stock `NM01` through `NM17` cannot be claimed. The four ordered table IDs must
be distinct printable FourCCs beginning with `HN`, and cannot claim Majesty's
stock `HN01` through `HN68` tables. The declaring package must
contribute exactly one STRT resource for each table and contain a Description
whose `NameGenType` selects the same generator. At runtime the manager repeats
Majesty's stock NM01-NM17 registry-completion lifecycle for every validated
record.

An overlay displayed through the stock AP78 enchantment list is declared as:

```json
{
  "type": "stock.ap78-enchantment-row.v1",
  "overlay_id": "OV42",
  "display_text": "Example enchantment description"
}
```

The overlay ID is one printable four-byte ASCII ID. The declaring package must
own exactly one package-added Overlay Description with that ID; a stock Overlay
cannot be replaced or claimed. The display text must contain
1–512 non-NUL Windows-1252 bytes. The runtime preserves AP78's existing XR01
presenter and substitutes only the validated row identity and text. AP78 draws
these rows from its fixed stock `IX93` interface atlas; the manager includes
that exact atlas and its TILE dependencies automatically, so an overlay's
`ImageIDBase` and `Static` flag do not select the panel-row icon. Multiple
packages may declare either feature; exact duplicates from the same owner
coalesce, while cross-package ownership or conflicting declarations fail.

#### Stock controller recipes

Controller recipes extend a declared `AP10`/`AP10` building through bounded,
already traced stock panel lifecycles. Authors use package-local logical keys;
the manager qualifies those keys by the package UUID, allocates both building
and secondary-panel runtime DialogIDs, rewrites the package-owned `SMNU`/`STRT`
resources, and checks global Majesty IDs separately. Do not reserve a `CGxx`
FourCC and do not add `dialog_id` to `custom_buildings`.

Every controller feature refers to one panel declaration like this:

```json
{
  "type": "stock.ap10-ap69-secondary-panel.v1",
  "panel_key": "workshop-panel",
  "parent_building": "YourNamespacedBuildingID",
  "source_dialog_id": "WP01",
  "building_family_id": "YWB",
  "open_command_id": 16512
}
```

The package must own exactly one `SMNU/WP01` and `STRT/WP01` pair. Here,
`source_dialog_id` identifies that authored **secondary** panel pair so the
manager can find and relocate it; it is not the custom building's dialog ID or
the manager's final allocation. The parent must be declared in
`custom_buildings` with `controller_base` and `panel_resource_template` both
`AP10`. `building_family_id` is the one-to-three byte prefix of package-added
parent Building Description IDs. That prefix must belong exclusively to the
declared parent's level records: it cannot match a stock Building, another
selected building, or overlap another controller panel's family prefix.

Additional records use the same `panel_key`. Their exact required fields are:

| Feature type | Additional fields |
| --- | --- |
| `stock.ap22-resource-meter.v1` | `resource_key`, `attribute_id`, `label_control_id`, `count_control_id`, `binding_control_id` |
| `stock.ap99-research-row.v1` | `recipe_key`, `action_control_id`, `descriptor_template_control_id`, `completion_template_control_id`, `required_level`, `price`, `price_control_id`, `progress_control_id`, `active_display_control_id`, `icon_control_id`, `completion_text` |
| `stock.ap17-upgrade-research-gate.v1` | `parent_building`, `upgrade_control_id`, `upgrade_price_control_id`, and `requirements`, an array of exact `{ "building_level": 1, "recipe_key": "local-recipe-key" }` objects |
| `stock.ap24-timed-rage-action.v1` | `action_key`, `action_control_id`, `descriptor_template_control_id`, `level_price_template_control_id`, `required_level`, `gold_cost`, `resource_key`, `resource_cost`, `callback_symbol`, `duration_ms`, `icon_control_id`, `price_control_id`, `progress_control_id`, `active_display_control_id` |
| `stock.ap24-rage-command-action.v1` | `action_key`, `action_control_id`, `visual_template_control_id`, `completion_template_research_control_id`, `required_level`, `resource_key`, `resource_cost`, `callback_symbol`, `icon_control_id`, `price_control_id` |
| `stock.ap69-sovereign-target-action.v1` | `action_key`, `visual_control_id`, `private_control_id`, `visual_template_control_id`, `target_template_control_id`, `stock_target_mode`, `stock_executor_mode`, `private_mode`, `private_unit_id`, `cursor_ordinal`, `required_level`, `resource_key`, `resource_cost`, `icon_control_id`, `price_control_id` |

An MX09-shaped building can instead open the stock AP41 reward lifecycle with
this linked pair:

```json
{
  "type": "stock.mx09-ap41-reward-panel.v1",
  "panel_key": "capture-rewards",
  "parent_building": "YourNamespacedBuilding",
  "source_dialog_id": "RP01",
  "open_command_id": 5001
},
{
  "type": "stock.ap41-fl00-hostile-monster-flag.v1",
  "panel_key": "capture-rewards",
  "action_key": "capture",
  "private_mode": "RF01",
  "private_flag_id": "RF01",
  "cursor_ordinal": 38,
  "availability_attribute_id": null,
  "unavailable_alert_text": null
}
```

The parent declares `controller_base` and `panel_resource_template` as `MX09`.
The package owns the secondary `SMNU`/`STRT` pair, an added Overlay Description
whose `ID` is `private_flag_id` and whose `Name` is the private GPL flag
prototype, and CUR1 set `1000 + cursor_ordinal`. The manager derives the
prototype name from that Description; authors do not repeat it in JSON.
`private_mode` and `private_flag_id` are intentionally the same private FourCC,
matching stock Fl00's mode-to-Overlay relationship. Each reward panel has
exactly one linked action. `cursor_ordinal` is 32–255 and globally unique among
selected reward actions. The optional availability fields must either both be
`null` or both be present; the ID is 1–4 printable ASCII bytes and the alert is
1–96 non-NUL Windows-1252 bytes. The runtime retains AP41 controls 5002, 8, 10,
11, and 8013 and stock Fl00 placement, validation, debit, cancellation,
completion, and cleanup, adding only the declared hostile-current-monster,
duplicate-private-flag, and optional availability gates.

An occupant-action panel uses Majesty's Mausoleum list, selection, cost, and
queued payment/action lifecycle. Add this record to `runtime_features`:

```json
{
  "type": "stock.mx04-mx05-occupant-action-panel.v1",
  "panel_key": "visitor-actions",
  "parent_building": "YourNamespacedBuilding",
  "source_dialog_id": "VP01",
  "open_command_id": 16641,
  "cost_callback_symbol": "YourMod_Visitor_Cost",
  "action_callback_symbol": "YourMod_Visitor_Action"
}
```

The parent must be a declared custom building using a cataloged stock
primary-building controller and its matching stock panel template. Its private
opener must emit `open_command_id`. Every parent keeps its exact audited stock
controller boundary; choosing a controller does not change this recipe's MX05
child behavior. Multiple panels can share a building, including an existing
research or reward panel, with distinct keys, child resources, and opener
commands.

Supply package-owned `SMNU/VP01` and `STRT/VP01` cloned from stock `MX05`.
Change text, art, and layout but keep its local control IDs: `0x1388` list,
`0x138B` action, `0x1F46` selected cost, `0x1F45` title, `0x1F4D` Back,
`0x1392` scrollbar, and `0x1F40`/`0x1F41` navigation. These are local control
numbers, not globally shared dialog IDs. The manager assigns the final private
dialog and queued-action IDs; do not ship manager registry files.

Both callbacks must exist exactly once in the package's included GPL sources:

```text
Function YourMod_Visitor_Cost (agent selected) is integer
declare
begin
    return 500;
end

Function YourMod_Visitor_Action (agent selected)
declare
begin
    // Your package's stock-derived action for this occupant.
end
```

The cost function is a side-effect-free quote in gold (nonnegative signed
32-bit integer). The action receives the selected agent after stock checks
and deducts that quote. Do not deduct gold again in GPL. The callback owns
any stock-derived changes to the occupant, including removing it from the
building's `Occupants` list when the action releases it. The manager neither
changes unit allegiance nor invents release behavior. The list supports all
occupant agent types through the required Generic Visitor Lists patch.

See [the stock lifecycle and test guide](stock-occupant-action-panel.md) for
native routing, ownership, and validation details.

Any supported custom-building parent can present a bounded multi-row list of
live agents through MX05's native list lifecycle:

```json
{
  "type": "stock.mx05-live-agent-list-panel.v1",
  "panel_key": "available-orders",
  "parent_building": "YourNamespacedBuilding",
  "source_dialog_id": "LP01",
  "open_command_id": 29001,
  "row_count_callback_symbol": "YourMod_Row_Count",
  "row_agent_id_callback_symbol": "YourMod_Row_Agent_Id",
  "revision_callback_symbol": "YourMod_Row_Revision",
  "row_title_text": null,
  "row_text": null,
  "row_variant_callback_symbol": "YourMod_Row_Variant",
  "row_variants": [
    {"title_text": "Delivery", "row_text": "Deliver this order"},
    {"title_text": "Escort", "row_text": "Protect this traveler"}
  ],
  "row_value_callback_symbol": "YourMod_Row_Reward",
  "row_value_suffix_text": " Gold",
  "action_cost_callback_symbol": "YourMod_Action_Cost",
  "action_callback_symbol": "YourMod_Action_After_Debit",
  "stay_on_panel_after_action": true,
  "focus_selected_row_on_click": false,
  "action_agent_scope": "parent"
}
```

The parent must be a declared custom building using a cataloged stock
primary-building controller and its matching stock panel template. The package
owns one exact
stock-shaped MX05 child SMNU/STRT pair and may choose the label of its one
native bottom action. The Manager allocates the final child and queued-action
IDs.

The row-count callback returns `0` through `64`. A second callback receives the
live parent and one-based row index and returns the selected live agent's
integer `ATTRIB_AgentID`. The Manager resolves that ID through Majesty's stock
live-agent lookup, so each row must identify a distinct live agent. A null
common title preserves each agent's stock name. Packages may either use the
same optional `row_title_text`/`row_text` on every row, or set both to null and
provide up to 64 package-declared `row_variants` plus an integer
`row_variant_callback_symbol`. That callback returns a one-based variant index
for `(Parent, Row)`; it never returns text. The optional per-row integer plus
suffix is rendered on its own reward line. `action_agent_scope` optionally
selects `"selected-row"` (the default) or `"parent"`. Selected-row scope passes
the selected row agent to both action callbacks. Parent scope passes the durable
parent building regardless of selection and keeps the paid bottom action usable
with zero rows; use it for panel-global actions such as Refresh. The optional
`stay_on_panel_after_action` boolean defaults to `false`. Set it to `true` when
a successful action should keep this child list open instead of using MX05's
stock post-submit transfer of world selection to the selected row. It does not
change the queued command, payment, callback, row identity, or list refresh.
The optional `focus_selected_row_on_click` boolean defaults to `true`, preserving
stock MX05 behavior. Set it to `false` when selecting a text row should update
the list selection without moving Majesty's world/tracking focus to the row's
live-agent identity. These policies are independent and apply to any compatible
MX05 live-agent list, not to a particular building or gameplay purpose.
See [the generic MX05 live-agent-list proof](stock-quest-board-panel.md) for
the exact resource geometry, callback signatures, stock lifecycle, and fault
bounds.

Any cataloged stock primary-building controller can use MX22's persistent
open/closed state and paired-control presentation:

```json
{
  "type": "stock.mx22-building-open-toggle.v1",
  "toggle_key": "rentals",
  "parent_building": "YourNamespacedBuilding",
  "open_command_id": 24001,
  "close_command_id": 24002
}
```

The parent SMNU must contain a coherent pair of literal stock-shaped MX22
action controls, stock AP39 half-width action controls, or stock AP10 93x26
action controls. The AP39 and AP10 variants are intended for building-panel
layouts where MX22's fixed 139-pixel art cannot fit or is visually unsuitable.
Every pair may change only to the two declared private command IDs and the
package's own visible text and layout. The AP39 variant retains its exact stock
`INBb` set `0x3F8`, image selector `0x52`, font, colors, opcodes, and record
boundary. The AP10 variant retains the literal `INBb` art token and exact stock
font, colors, opcodes, and record boundary while allowing a package-owned
`INBb` image set with the stock 93x26 control geometry. Presentation families
cannot be mixed within a pair. The manager stores the state in stock
`ATTRIB_EmbassyActiveFlag`, shows exactly the action that changes the current
state, and refreshes it after stock setup, events, and ordinary commands. It
does not submit Embassy order `0x16` or create an Embassy recruit order; those
side effects belong only to the Embassy. Toggle keys, parents, and commands
must remain unambiguous across the complete merged selection. See
[the building-toggle lifecycle](stock-building-open-toggle.md).

A package can attach a private hero task to Majesty's complete stock hero
decision lifecycle without replacing any hero decision tree:

```json
{
  "type": "stock.hero-quest-lifecycle.v1",
  "feature_key": "private-hero-tasks",
  "hero_scripts": ["mx_adept", "mx_ranger"],
  "resume_callback_symbol": "YourMod_ResumeHeroTask",
  "consider_callback_symbol": "YourMod_ConsiderHeroTask",
  "reset_callback_symbol": "YourMod_ResetHeroTask",
  "death_callback_symbol": "YourMod_HeroDeath"
}
```

`hero_scripts` contains one to sixteen distinct stock script names from
`mx_adept`, `mx_barbarian`, `mx_cultist`, `mx_discord`, `mx_dwarf`, `mx_elf`,
`mx_gnome`, `mx_healer`, `mx_monk`, `mx_paladin`, `mx_priestess`, `mx_ranger`,
`mx_rogue`, `mx_solarus`, `mx_warrior`, and `mx_wizard`. There is no class
eligibility rule beyond that explicit package declaration.

The resume and consideration callbacks must each be a package-owned GPL
function with signature `Function Name(agent ThisAgent) is boolean`. Resume is
called after unchanged `Check_Nearby` declines and before unchanged
`Check_rewards`. Consideration is called after unchanged
`Pursue_Entertainment` declines. Stock Healer and Monk intentionally omit that
choice, so their consideration callback instead runs immediately after their
unchanged `Purchase_Bazaar` choice declines. Returning `FALSE` preserves every
following stock branch; return `TRUE` only after installing a complete private
task. The reset and death callbacks must each use the void signature
`Function Name(agent ThisAgent)`. They run at the stock `Reset_Tasks` entry and
after `DeleteAllEffectors` but before `IGDeathScript`, respectively. All four
symbols must be distinct, must exist exactly once in package GPL source, and
must not collide with another selected package. Missing, duplicated, or
modified stock anchors fail closed.

A package can add a low-priority hero purchase choice without replacing the
whole stock `Purchase_Equipment` function:

```json
{
  "type": "stock.gplmx-purchase-equipment-tail.v1",
  "callback_key": "rent-a-beast",
  "callback_symbol": "YourMod_Rental_Check"
}
```

The named GPL function must exist exactly once in that package and use
`Function YourMod_Rental_Check (agent ThisAgent) is boolean`. It returns TRUE
only after it has prepared the same Target, TaskName, and intent state expected
by stock `Use_Building`. The manager inserts all declared callbacks in stable
package/key order only after the complete effective purchase chain—including
package-owned additions and stock `Stat_Boost_Check`—has declined. A TRUE
result then passes through stock's single final `ActiveScript = Use_Building`
and `return TRUE` block. Unrecognized or reordered stock anchors fail the
build. See [the purchase-tail lifecycle](stock-purchase-equipment-tail.md).

For a choice that must come after all Magic Bazaar items, use the parallel
`stock.gplmx-purchase-bazaar-tail.v1` record with the same `callback_key` and
`callback_symbol` fields. Its callback has the same `(agent) is boolean`
signature. The manager inserts it after the complete effective Bazaar item
scan and before `Purchase_Bazaar`'s final Flag/`Use_Building` handoff. Use the
equipment-tail and Bazaar-tail types according to Majesty's actual hero
decision order; they are distinct extension points and are sorted
independently.

A complete parser-checked schema-v3 example containing the AP10/AP69 recipe
family is available as
[mod-definition-v3-all-features.json](examples/mod-definition-v3-all-features.json).
It shows exact placement and field spelling, including the distinct
`stock_target_mode` and `stock_executor_mode` fields. Package-owned control
IDs, FourCCs, modes, and callback names in that file are illustrative; an
actual package must use IDs that match its shipped panel resources,
Descriptions, and GPL. Stock template-control fields are not illustrative or
package-owned: they select only the bounded stock descriptor metadata listed
below.

`panel_key`, `resource_key`, `recipe_key`, `action_key`, and `parent_building`
are package-local logical names. Visible action, price, icon, progress, meter,
upgrade, and display controls are reserved within their resolved panel rather
than globally. Global engine identities are checked across the complete
selection: every AP22 `attribute_id`, private descriptor command, callback GPL
symbol, private sovereign mode, and private unit must remain unambiguous. Stock
target/executor modes may be reused by records selecting that same stock
lifecycle, and `cursor_ordinal` is bounded but not a globally exclusive
identity. In particular, two AP22 meters cannot alias the same packed Majesty
attribute. GPL callback identity is
case-insensitive, matching the game. A callback must be one
package-owned GPL function. A `private_unit_id` must be one package-added
Character Description, not a stock override. The AP10/AP69 recipe family supports only the traced
`Sp14` `stock_executor_mode`; another executor family requires a reviewed Mod
Manager runtime feature change. Both supported executables reserve the complete
case-sensitive `Sp**` FourCC namespace for stock sovereign modes, so
`private_mode` cannot begin with `Sp` and must also differ from every selected
stock target and executor mode.

There are two distinct kinds of numeric control fields:

- package-owned panel controls, such as action, price, icon, progress, meter,
  upgrade, and active-display controls, must be present in the appropriate
  authored panel resource; and
- fields named `*_template_control_id` reference a stock Majesty descriptor.
  They do not identify a package control and cannot be an arbitrary nonzero ID.

MMCR v2 accepts only stock template relationships already traced in both
supported executables:

- AP99 descriptor and completion templates may use any of the 26 descriptors
  AP99 actually constructs: `0x1388`–`0x138D`, `0x1392`, `0x139C`–`0x139D`,
  `0x13A6`–`0x13AB`, `0x13B0`–`0x13B3`, `0x13BA`, or
  `0x13C5`–`0x13CA`. Gaps in AP99's wider discovery interval and private IDs
  are not stock templates.
- An AP24 timed action uses descriptor template `0x1140` together with
  level/price template `0x113E`; that stock pair requires
  `required_level: 3` and `gold_cost: 1500`.
- An AP24 Rage-command action uses visual template `0x1132`, requires
  `required_level: 3`, and selects its completion template from the same
  26 proven AP99 descriptors.
- An AP69 sovereign-target action uses visual template `0x1133` and target
  template `0x1132`; the target template requires `stock_target_mode: "Sp23"`
  and `required_level: 3`. Its executor remains the separately traced
  `stock_executor_mode: "Sp14"`.

Another stock template or metadata combination requires a new stock trace and
a reviewed reusable feature-version update. The manager rejects it during
preflight, and the native MMCR parser independently rejects a tampered registry
before Majesty resumes.

These recipes preserve the stock singleton lifecycle that owns each behavior:
AP10/AP69 panel creation and destruction, AP22 packed-resource display, AP99
research registration and cleanup, AP17 post-presenter upgrade gating, AP24
Rage command/callback/cancellation, and AP69 sovereign targeting/cancellation.
Records are selectable alternatives inside those stock-owned lifecycles, not
permission to run replacement watchers, timers, or parallel controllers. All
fields are exact: unknown fields, missing linked records, unowned resources,
or colliding actual IDs make the package nonselectable.

The parser also enforces the following bounds:

- logical keys contain 1–64 ASCII letters, digits, `_`, `.`, or `-`, beginning
  with a letter;
- `required_level` is 1–3; every control ID is an unsigned 32-bit integer;
  `open_command_id`, all AP99 controls except its optional `icon_control_id`,
  and every named template-control field are nonzero, while the other presenter
  controls may use zero when that stock row has no corresponding control;
- nonzero presenter controls cannot be repeated within a record or claimed by
  two records on the same panel;
- AP99 `action_control_id` values must be outside `0x1388` through `0x13EB`,
  the complete stock AP99 control namespace hard-gated by both supported
  executables; template fields may reference only the constructed stock
  descriptor IDs and metadata combinations listed above;
- `price` and `gold_cost` are 0–2,147,483,647, while `resource_cost` is
  1–2,147,483,647;
- `duration_ms` is 1–86,400,000 and `cursor_ordinal` is 0–255;
- `completion_text` is 1–96 non-NUL Windows-1252 bytes; and
- every callback is one bounded GPL identifier, not code, a path, or a command.

### Legacy definitions

Version 2 retains its exact `dialog_id` and `runtime_capabilities` fields, and
version 1 retains its original building-only shape. They remain supported so a
manager release does not break existing mods. Version-2 capability aliases for
the current Haunt and Alchemist packages are translated into the same generic
typed records used by version 3. New packages should not copy those
package-specific aliases.

`private-activity-text-registry.v1` is not package-owned. It is reserved and
derived by the composer only when automatic inspection actually detaches one
or more safe private AITX rows. A package or compatibility adapter that tries
to assert it directly is rejected. The generated profile is schema version 2
and records its complete effective hook-selection set, including derived
features, so its definition, binary manifests, merge report, and runtime
registries can be cross-checked as one contract.

Schema version 1 is not accepted as a generic third-party Merge contract. It
cannot state package-owned runtime requirements, so the catalog marks an
unadapted v1 Merge mod red and nonselectable. Version 1 remains usable only
when a trusted manager compatibility profile supplies the missing definition,
capabilities, or complete audited replacement package.

## Stock-relative content requirements

Majesty treats several resources as complete effective tables rather than
independent rows. Whenever a mod changes one, its package must ship the complete
effective resource, preserving stock order, flags, padding, and unchanged
entries. The manager recovers the mod's intended delta by comparing it with the
installed stock game/SDK common ancestor.

The currently supported whole-table resources are:

- `BDEP`, keyed by case-sensitive building ID;
- `UNTN`, `ACTN`, and `HPTX`, keyed by their embedded IDs;
- `QITM` and `AITX`, keyed by positional index; and
- `TILE` and `SPLT`/`PALT`, keyed by positional index and interpreted together with
  their typed references.

Custom quests can load complete `AITX` or `QITM` tables after Active Mods and
therefore supersede Merge-mod text rows. The manager never modifies or copies
installed quests. For `AITX`, the manager automatically finds every
stock-relative changed row in each selected package, then searches that same
package's GPL/DAT sources for direct calls to Majesty's stock text consumers.
The text argument must resolve to the changed row through either an exact
decimal literal or an exact package/stock integer expression. Dynamic and
indirect-only uses fail closed, as does using a row-bound expression through an
unconfirmed non-resolver lifecycle. During Build, the manager restores/removes
the changed positional row, adds one synthetic GPL expression per source Mod
UUID and AITX row, rewrites only the proven stock-resolver argument sites to
that stable manager-owned ID, removes the now-unused exact expression only when
it was defined by that package, and emits
`Data/MMMIntentText.bin`. The launcher DLL resolves only IDs present in that
validated registry; every other ID follows Majesty's stock resolver. Thus
quest-local AITX remains untouched and can load normally. Multiple direct
symbol aliases for one row are supported and share its synthetic ID. A missing
or dynamic-only binding, unsupported indirect use, cross-owner ambiguity,
registry collision, or malformed registry makes the source mod red and
nonselectable.

Package-owned bound expressions are removed only after every use has been
proven and rewritten. Stock-supplied aliases are never removed. If another
selected package refers to an expression that would be removed—outside its own
independently proven private binding—the merge fails rather than breaking that
cross-package dependency. This also lets unrelated packages independently use
the same convenient source alias for different private rows without creating a
false GPL definition conflict.

Before generating a synthetic name, the manager checks every selected GPL/DAT
code reference plus the complete stock/selected expression environment. Any
preexisting use of that reserved `#MMM_AITX_*` name rejects the build instead
of capturing an unrelated symbol.

An explicit GPL conflict resolution has no package owner. Before accepting one,
the manager resolves every stock text-consumer argument against the complete
exact-integer expression environment from the installed stock definitions and
all selected packages. An alternative exact alias for a detached row is
rewritten to that row's synthetic expression; missing, compound, or ambiguous
expression evidence fails closed. This stricter pass applies only to explicit
resolution items and does not reinterpret another package's ordinary numeric
resolver arguments.

Automatic localization is limited structurally to appended rows or installed
stock rows carrying the stock blank-placeholder value (empty text or the stock
literal `empty`). Replacing meaningful stock AITX text may be an
intentional global relabeling, which source syntax cannot prove safe to
privatize, so that package is red and nonselectable. No row numbers are
hardcoded. The merge report records whether each accepted row was appended or
an existing stock placeholder, plus every source expression and generated expression.

Manager IDs are stable hashes of normalized source Mod UUID plus the original
AITX row index in the reserved positive range `0x60000000` through
`0x6FFFFFFF`. Selecting another Merge mod cannot renumber an existing row. The
binary registry is
strictly bounded and fingerprinted in both the manager sentinel and merge
report. This runtime path also covers non-panel consumers that use the common
stock AITX resolver, such as advisor flags and local chat messages. `QITM`
remains an unresolved limitation for legacy private numeric items. New
Merge-ready content should author custom carried items through Majesty's named
inventory-item path rather than adding numeric `QITM` rows. The manager does
not silently migrate numeric items because doing so would change the native
item panel and would not migrate items already stored in saved games.

The current report and build plan fingerprint the complete stock composition
input set: the five required stock CAMs, the optional MX main/interface art
CAMs as explicit present-or-absent states (and by hash when present),
`mx_defines.gpl`, both SDK `OriginalQuests` Description XML directories
(including membership), and the `Gplbcc.exe` compiler. The manager reparses
every selected package and rehashes
package, compatibility, and stock inputs after planning, then rechecks them
before, during, and immediately before publishing. Added, removed, changed, or
symlinked inputs fail closed. `MajestyHD.exe` is not part of the merge report;
executable compatibility is guarded separately by the QOL installers and
runtime launcher. A package based on an ancestor the manager cannot identify
is not safe to diff.

## Namespace and asset auditability

GPL functions must not execute `return` from within a `foreach` body. Majesty's
beta2 evaluator can corrupt the function result path for this source shape.
Follow the stock pattern: initialize a result, update or select it during the
loop, and return only after the loop completes. Preflight rejects unsafe source
rather than rewriting author-owned control flow.

Private additions must be namespaced across every runtime namespace they use:
manifest UUID, internal and XML Description IDs, FourCC resource keys, GPL
functions/expressions, DAT blocks, authored panel IDs, IMAG keys,
`DSND`/`WAVE` keys, and custom art or sound filenames. GPL and DAT names are compared
case-insensitively; Description keys are compared as case-sensitive
`(element-type, ID)` pairs.

`TILE`/`SPLT` and `TILE`/`PALT` collisions may be relocated only through known typed structures.
Every moved TILE must be reachable through an audited IMAG frame field, and
every moved palette reference must be a parsed TILE palette field. The package
must preserve complete positional tables and section flags, and its emitted
TILE-to-palette references must close over the generated palette table. Unknown
IMAG layouts, direct or untyped positional references, truncated tables, and
blind byte-pattern rewriting make the package nonselectable.

All custom payloads used by those records must be present and attributable to
the package. A local merge report records source ownership and hashes; it does
not grant permission to republish another author's assets or materialized stock
content.

## Runtime features and native support

Content that needs behavior outside stock CAM/GPL dispatch must declare a
stable, manager-recognized typed runtime feature. New or incompatible recipes
use an explicit `.vN` suffix. A feature is accepted only after its closest
stock mechanism, supported executable fingerprints, hook sites, ownership,
cleanup, and coexistence with the other runtime/QOL patches have been
documented and validated. Unknown declared features fail closed.

Packages cannot provide their own DLLs, raw patch addresses, or arbitrary code.
Native behavior that is not covered by an existing reusable capability must be
proposed as a reusable feature in a reviewed
[pull request to this repository](https://github.com/Phantomstar721/majesty-gold-hd-mod-manager/pulls).
See [Contributing new runtime feature support](adding-runtime-features.md) for
the stock-lifecycle, portability, safety, and test requirements.

Version 3 owns typed feature declarations in the package itself. Version 2
retains its legacy capability aliases, and extra runtime requirements for a
version-1 package must come from a trusted compatibility adapter. The manager
cannot discover an undeclared native mechanism merely from data files, so
authors must declare a supported recipe. Positional `AITX` text is different:
its stock-relative row and direct stock-resolver call sites are automatically
discovered rather than being recorded as package-specific rows in the manager
or package definition.

Catalog preflight uses the same typed stock-relative AITX discovery as Build.
Missing or ambiguous bindings are displayed red and cannot be selected; Build
repeats the proof so a package changed after scanning cannot bypass it.

Every generated profile contains
`DataMX/majesty_mod_manager_capabilities.bin`. This is the deterministic MMCP
v1 launcher contract: `MMCP`, little-endian 32-bit version and record count,
then strictly bytewise-sorted records made of a 32-bit byte length and a
canonical lowercase ASCII dotted name. The decoder rejects duplicates,
truncation, trailing bytes, names over 128 bytes, more than 64 records, and
files over 64 KiB. The merge report and manager-owned sentinel both record its
relative path, SHA-256, and record count.

Every generated profile also contains
`DataMX/majesty_mod_manager_features.bin`. This deterministic MMFR registry is
the manager-to-runtime data for the selected typed recipes. It contains bounded
sorted name-generator and AP78-row records only. The manager validates and
normalizes package JSON, translates recognized legacy aliases, detects
cross-mod identity conflicts, and fingerprints the emitted bytes. The runtime
parses MMFR again before installing any feature hook and rejects truncation,
duplicates, invalid FourCCs, invalid Windows-1252 text, trailing data, or a
mismatch between MMCP hook selection and MMFR records.

Controller recipes are emitted separately as
`DataMX/majesty_mod_manager_controllers.bin`. This deterministic MMCR registry
contains only manager-resolved, bounded records for the seven documented stock
controller lifecycles. It contains no package paths, DLLs, addresses, patch
bytes, or executable instructions. The manager qualifies package-local logical
keys, resolves building and secondary-panel DialogIDs, validates linked records
and package evidence, detects global Majesty ID conflicts, and fingerprints the
result. The runtime reparses MMCR and requires its non-empty state to agree with
the canonical `stock.controller-recipes.v1` MMCP capability before installing
the shared hook group.

The manager passes the validated absolute path through
`MAJESTY_MOD_MANAGER_CAPABILITIES` on every launch. A Standard-only launch uses
an atomically written empty MMCP manifest, making absence of the environment
variable distinguishable from an intentional manager launch. A merged launch
uses the manifest inside the fingerprinted generated profile. Before launch,
the manager compares a complete generated-file metadata signature with the last
exact validation. Any metadata change triggers a full generated-file inventory,
SHA-256 verification against the sentinel, and CAM resource reparse before
launch is allowed.

The matching MMFR path is passed through
`MAJESTY_MOD_MANAGER_FEATURES`. Standard-only launches use a validated empty
registry; merged launches use the fingerprinted registry inside the generated
profile. The MMCR path follows the same rule through
`MAJESTY_MOD_MANAGER_CONTROLLERS`. Workshop packages are never allowed to point
the runtime at their own registry or native payload.

### Generic Visitor Lists

Generic Visitor Lists is a mandatory global launch prerequisite, not a CAM mod.
Setup stages its licensed guarded installer; scan dry-runs it; Launch
idempotently installs and verifies it, and stops if the installer is missing,
the executable is unsupported, or verification fails. The manager includes
`generic-visitor-lists.v1` in every plan, so this is not a per-mod opt-in and
packages do not declare it. The current release does not yet detect
visitor-producing content or validate
IX92/IX94/TILE atlas closure. The following are therefore authoring
requirements for such content, not automated readiness checks:

- IMAG `IX92monster icons`;
- IMAG `IX94monstor icons n` (the stock misspelling); and
- the complete positional TILE table from the same
  `DataMX/mx_interfacedata.cam` ancestor, with its stock padding and order.

An augmented atlas preserves every stock mapping. A custom monster adds a
25x25 compatible frame and an entry whose four-character type ID exactly
matches its runtime unit Description ID. Shipping only the new atlas row or
icon is unsafe because it removes or invalidates stock mappings. These
resources belong in an `Any` interface-data provider because base quests do not
normally load the expansion atlases.

## Deterministic merge and conflicts

The manager composes the selected packages in an explicit, stable order and
compares semantic records with the stock ancestor:

- identical co-owned changes are accepted once;
- independent keyed additions are unioned;
- whole-table deltas are combined by their documented typed key;
- positional art collisions use deterministic allocation, with only audited
  references rewritten; and
- divergent changes are never resolved by implicit load order.

An overlap proceeds only when the relevant typed merger can prove it is
independent or an explicit resolution selects or supplies the complete intended
semantic result. Today, GPL/DAT conflicts may use an explicit selected-owner
resolution. Divergent Description, named CAM, and whole-table records must
merge cleanly or stop until an equally explicit typed resolution is added.
Unused, misspelled, or stale resolution rules also stop the build.

Explicit overlap resolutions currently come from checked-in compatibility
metadata: selected-owner rules or supplied complete GPL/DAT semantic
definitions. This is separate from custom-text binding, which is automatic and
UUID-agnostic. There is no interactive diff3/manual conflict editor. Any
unrecognized overlap aborts Build. If multiple simultaneously applicable rules
name the same semantic item, Build also stops; registry order never chooses a
winner. A requested item must appear exactly once in its resolution source.
Each supplied semantic resolution is scoped to the mods named by that
combination rule. A third selected mod may repeat one participant's exact
byte-identical definition, but a novel third-party variant remains an
unresolved conflict and stops the build.

The generated report records ordered inputs, stock and output hashes,
stock-relative deltas, allocations, conflicts, explicit resolutions, runtime
hook selections and typed features, compiled BCD size, and validation results.
Identical ordered inputs and profile identity produce the same generated UUID
and allocations.

## Build, activation, and failure rules

Composition is read-only with respect to every source package. The manager
builds in a staging directory, recompiles GPL with the real SDK compiler,
reparses and round-trips every emitted archive, checks all typed references,
and only then publishes a separate local package through a recoverable
manager-owned staging/backup rename. The generated UUID
is deterministic and never reuses a selected source UUID, even for a one-mod
profile. Build-plan input identity uses the SHA-256 content of every selected
package input, external adapter definition, and compatibility resolution source.
The manager also records a complete metadata signature for those exact inputs.
Before composition, after composition, and immediately before publication it
compares that signature; if metadata changed, it recomputes exact SHA-256
identity and rejects the build. A detected Workshop update or source mutation
at any of those boundaries discards staging and requires Prepare again, so a
registry cannot be published beside GPL built from a different planned input
set.

The fixed generated-profile directory is protected by one exclusive sibling
lock from build validation through publication, and from launch validation
until the launched game exits. A second Build or merged Launch fails safely
while that lock is held. Immediately before a merged launch, the manager also
revalidates the selected package, compatibility, stock, generated-profile, and
runtime inputs used by that launch. Standard-only launches do not take this
merged-profile lock.

While a generated profile is active:

- every source Mod represented inside the generated profile is omitted from the
  Active Mod GUID list;
- exactly the validated generated profile is enabled for that Merge set;
- selected Standard mods remain independent Active Mod GUIDs;
- source quests remain untouched and are chosen in the stock quest browser; and
- changing Merge selection or order makes the prior build stale and disables
  manager Launch.

The current Remember Active Mods bridge restores at most 26 Active Mod GUIDs.
The count is selected Standard mods plus one generated Merge-profile GUID when
Merge content is selected; source Merge GUIDs and quests do not count. Launch
fails closed above 26 until an arbitrary-length restore hook is bundled.

Source Workshop items remain installed and untouched. Any manager-owned
compatibility substitution is keyed by the source UUID, uses a complete
audited replacement input, and is disclosed in the report; it never overwrites
the original package.

Catalog and deep-preflight failures are shown red and nonselectable. Conflicts
discovered only during composition currently abort Build and appear as
build-failure diagnostics rather than a persistent red catalog row. In either
case no new partial package is published or projected into the Active Mods
file; any prior generated package remains stale and manager Launch stays
disabled.
