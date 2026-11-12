Version 0.3.14 (beta) combines more original source-backed scripts without an
author rewrite and lets custom panel presentation keep existing hiring,
research and spell handlers. It also fixes Standard-only scans and native text
XML handling. Unsupported overlaps keep the usual preferred-mod choices.
Includes the updated native panel/script engine SDK, newer panel records and
script functions, and corrected GOG panel text handling. Original native engine
packages keep their Standard packaging without a Manager-specific copy.
Update optional patches through Quality of Life when selected content requires
a newer revision; patches are never installed automatically. Prepare Again after
updating. Supports Default Steam, beta2 and GOG.

Version 0.3.13 (beta) added optional Custom Building Panels and Scripted Ground
Actions, with credit to mikmak300 on each patch's Quality of Life row. Selected
content explains its detected or declared patch requirements before launch;
install the patches you need from Quality of Life. Native engine mods keep
their Standard packaging. This update also fixes repeated research completion
that could crash the game. Supports Default Steam, beta2 and GOG.

Version 0.3.12 (beta) added Classic Launch for Standard mods without preparing a
merge, up to five named setup profiles, and a global expansion-content toggle
that includes original Majesty quests. New mods stay disabled until selected.
Gold indicators highlight new or updated content, and History shows brief patch
summaries beneath the Manager version.
Fixes Use selected profile so saved setups and their launch settings restore correctly.

Version 0.3.11 added shared custom-hero and ability support, research queues,
cooldown displays, and bounded automatic failure reporting. It also corrects a
repeat-registration check when restarting quests. Existing packages remain
supported on Steam Default 1.5.2.24, Steam beta2 1.5.2.28 and GOG 1.5.2.28.
Use Save Support Report after a failure; reports stay local until you share them.
Close the game and Manager before updating, then Prepare Again.

Majesty Mod Manager makes it easy to organize and launch all of the Majesty Gold
HD mods and quests you have installed or subscribed to.

Mods with custom buildings, panels, and other advanced features need extra
support. Install this manager and launch Majesty through it to use them
individually or together. It automatically finds and organizes your mods and
quests, remembers your choices, and prepares anything that needs extra support.

The latest update preserves timed image data during merging and improves script
comparison. Combine Standard and Merge mods, choosing one preferred mod per
conflicting pair while retaining changes that safely combine.

These choices also cover building XML overrides, including buildings supplied
by another selected mod. Existing-building patches need no new custom-building
declaration, and expansion-only changes stay in expansion quests.
Compact art archives with sparse tile and palette IDs are also supported;
they no longer have to pad their tables with thousands of empty records.
Art merging also preserves authored image-set ordering and correctly places
tiles whose palettes change during combination.

Standard conflict choices are now shown together in one window. Sound conflicts
use preferred-mod choices too, and periodic spell damage keeps the selected
script's arguments and branches rather than requiring an exact stock statement.

The previous update fixes a launch failure when research or movement features
are selected on default Steam or GOG. It also preserves missing stock artwork
needed by merged content and refreshes stale compatibility results after changing game
versions or repairing game files. The Manager automatically refreshes affected
checks while keeping unchanged results cached for faster startup.

Recent updates also simplify conflict choices: see the mods and affected
gameplay at a glance, with more information under Details. Choose a preferred
mod for each pair; both stay enabled, and changes that can be combined are kept.
It also improves compatibility with custom healing-potion behavior and lets mod
authors share hero quest-participation declarations across Standard mod variants.
Close Majesty and the Manager before updating. Afterwards, reopen the Manager
and Prepare Selected Mods (or Prepare Again) before launching Majesty.
Rescan Content remains available if you want to force a fresh mod check.

First launch:

1. Subscribe to this item and the Majesty mods or quests you want to use.
2. In Steam, right-click Majesty Gold HD and choose Manage > Browse local files.
3. In Explorer, go up to steamapps, then open
   workshop\content\73230\3793024054.
4. Run Majesty Mod Manager.exe.
5. Optionally use Desktop Shortcut in the manager so you do not need to find
   the Workshop folder again.
6. Follow the first-time setup prompt.
7. Choose your mods, prepare them if requested, and select Launch Majesty.

Keep the entire downloaded folder together. The manager supports both the
default and beta2 Steam versions, plus GOG Gold HD 1.5.2.28. The manager checks
compatibility with your selected installation before launch.
GOG users should use the complete GitHub download linked below. The manager can
find already-downloaded Workshop content but does not download subscriptions.

More details: https://github.com/Phantomstar721/majesty-gold-hd-mod-manager
Direct download: https://github.com/Phantomstar721/majesty-gold-hd-mod-manager/releases/latest
Join the Majesty community: https://discord.gg/MEjtKZb9GQ
