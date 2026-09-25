# Independent saved building toggles

`stock.mx22-building-open-toggle.v2` extends the existing paired-control recipe
with `state_attribute` and `state_callback_symbol`. Multiple pairs may share a
parent, including one existing v1 Embassy-state pair. Each pair must own unique
commands, a unique private state name, and a unique generated callback name.

```json
{
  "type": "stock.mx22-building-open-toggle.v2",
  "toggle_key": "automatic-operation",
  "parent_building": "PrivateBuilding",
  "open_command_id": 29002,
  "close_command_id": 29003,
  "state_attribute": "PrivateAutomaticOperation",
  "state_callback_symbol": "Private_Automatic_Operation_Enabled"
}
```

The control-pair artwork, parent controller, and geometry obey the same audited
MX22/AP39/AP10 evidence as v1. Refresh hides the inactive action, shows the
opposite action, and sends stock enable message `0xA`. Clicking does not submit
an Embassy recruitment order or touch another toggle's flag.

The Manager generates the declared `(agent Building) is boolean` getter and an
integer native-boundary adapter. An absent property reads false without mutation.
The first click uses stock `AddAttribute` to create the boolean on that building.
Do not declare this property in a prototype/DAT or write it from consumer code;
do not define either generated function. Consumer policy reads the getter.
The Manager owns writes and caches the state for the displayed building. Stock
panel teardown or a changed controller/building handle discards that cache.
A failed read hides the pair until the context changes, without repeated calls.

## Stock persistence reference

Beta2 agent writer `0x577E30` passes the agent's property container to `0x577180`
at `0x577E91`. `0x577180` writes its entry count (`0x5771D3..0x5771D9`) and
iterates every map entry through the serializer virtual method
(`0x577218..0x577234`), not a prototype-only whitelist. Restore `0x577FD0` uses
`0x577A80` to reconstruct the saved names and typed values. Thus dynamic state
uses the existing saved-property lifecycle; there is no separate save file or
timer. Older saves missing the field remain off until first enabled.
See [the saved-agent audit](stock-gpl-prototype-save-audit.md).

MMCR v19 adds an optional private-state tail to toggle records. Earlier records
retain their old wire versions when no v2 toggle is selected. With no selected
private toggles there are no state lookups or generated accessors. Native fixture
coverage includes independent pairs, changing selected buildings, and panel
close/reopen; an actual game save/reload remains a playtest requirement.
