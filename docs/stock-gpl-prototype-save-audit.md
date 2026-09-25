# GPL prototype construction versus saved-agent restoration

Read-only beta2 native trace, 2026-09-20. Addresses apply to the supported
Steam beta2 executable, not automatically to other executable builds.

## Manager composition boundary

`gpl.merge_semantic_items` identifies definitions by kind and normalized name.
It selects identical/single changes, accepts explicit conflict resolutions,
and instruction-merges differing **functions** against their stock ancestor.
Prototypes remain whole definitions. A separately named private prototype is
not treated as inheriting additions made to a stock prototype. There is no
selected-mod Hero-extension propagation or saved-agent schema migration here.
The kingdom-research composer inspects prototype declarations for its evidence
checks; it does not provide general prototype inheritance.

## Native new-agent construction

`0x575170` resolves the requested DAT template (`0x57D180`), obtains its
prototype name (`0x57A030`), and resolves that prototype (`0x57DDF0`).
The loop at `0x57523E..0x575314` enumerates prototype declarations, obtains each
template value (`0x57D260`), creates its typed value (`0x56E5C0`), and installs
the named property (`0x577D30`) on the new agent. This is the path on which
new declarations/template defaults take effect.

## Native saved-agent restoration

- Registry load `0x575060` first resets registry storage through `0x574F70`,
  then restores the saved registry through `0x5860E0`.
- `0x5861D2..0x586239` reads saved agent entries, allocates a `0x44` agent,
  constructs it with `0x578520`, and calls its restore routine `0x577FD0`.
- The constructor allocates an empty property container; it does not resolve a
  DAT template or prototype.
- `0x577FD0` calls `0x577A80` to restore the property map. That routine reads
  the saved property count, then each serialized property name/typed value,
  inserting the saved entries into the map. The remaining restore path rebuilds
  the scheduled-function list and restores saved identity/state fields.
- This path does not call the new-agent prototype initialization at `0x575170`
  or append newly declared fields from the currently loaded prototype.

Consequently, extending a private prototype and its DAT template is a fix for
newly constructed instances, **not an automatic migration for existing saved
instances**. A saved agent missing a field still needs an explicitly justified
compatibility repair, or replacement with a newly created instance. Rebuilding
the package/reloading the save alone must not be promised to repair that field.
No migration, game-memory mutation, or save rewrite was performed in this audit.

This is a static native lifecycle finding; an updated-package/save reload was
not executed as part of this diagnostic.
