# Inventory-only actions in the Spells panel

Majesty learns inventory actions through `LearnSpell(agent, name, FALSE)`.
The learned node's byte at +0x14 controls AP78 display. Stock saving writes
the action ID and cooldown fields, but not this byte; both legacy load paths
restore it to 1. AP78 therefore displays previously hidden actions after load.

The Manager applies a display-only correction. At preparation, resolved GPL
literal hidden declarations are mapped to effective Action/IsSpell IDs. A
default, visible or computed visibility declaration excludes that action.
A computed action name or indirect LearnSpell reference disables inference,
because its possible targets cannot be established. Ambiguous description names
are not classified. No action names, potion names or mod identities are built
into the classifier. Inference covers available resolved source, not opaque
external compiled scripts; mixed-use actions must remain unclassified.

Classification uses the final common, base and expansion script output together,
after script choices and generated features. A visible or computed use in any
output vetoes a shared display suppression. Effective Action descriptions replace
stock records before their names are resolved; the classification is not a union
of independently approved per-file ID lists.

The sorted shared ID set is MMFR v9 flag 128 with a bounded count (1..1024)
and strictly increasing little-endian numeric FourCCs (not alphabetical ID order).
MMCP capability
`manager.inventory-spell-display.v1` must agree with its presence. It is
manager-derived, not a package-supplied hook request.

The finalized registry and capability manifest are derived together. The build
handoff keeps exact validation of planned features while checking source-derived
display IDs against the composer's finalized result. No reclassification or
additional source lookup runs at launch.

At AP78's existing learned-node visibility gate, a binary search can take the
stock skip-row branch. Otherwise the original byte test is replayed. The
learned node, cooldown, stock availability, item display, casts and save files
are never changed. No per-hero storage, timer, polling or extra source scan at
launch is added. Old saves benefit once prepared with this classification.

Audited AP78 function VAs: Steam beta2 0x4A3C00, default Steam 0x4A3320,
GOG 0x4A41B0. All use gate +0xD9 (`cmp [eax+14h], bl; je`), continuation
+0xE2 and next-node +0x292. The complete functions are guarded by the existing
per-executable HeroInfo profile hashes before any hooks install; the new
9-byte gate is checked again before patching. Stock owns iteration, row
creation and list destruction. The filter also works without custom hero rows.

The installer writes a five-byte jump followed by four NOP bytes across that
complete nine-byte instruction span. The shared branch writer accepts guarded
spans of 5..16 bytes and restores the original page protection. Installer
regressions exercise this route on disposable executable memory for every
profile, including rejected stock bytes and both stock continuation branches;
calling the display filter directly does not cover installation.

Static executable checks cover all three builds. Actual in-game acceptance
still requires loading a save and checking both Spells and Items.
