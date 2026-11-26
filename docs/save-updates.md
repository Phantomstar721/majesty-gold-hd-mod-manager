# Save updates

**Update Saves** lets a player keep an existing game after adding mods. It
rewrites one thing in a copy of each save the player selects: the list of mods
the save may load. Implementation: `src/majesty_cam/manager/saves.py` (rules and
file format) and `src/majesty_cam/manager/save_update_dialog.py` (window).

## Why saves need it

Majesty pins the mods a save may load in the save's `SVGD` descriptor and
refuses a save whose listed mods are not all installed (**Mods Missing**). A save
stores no mod content: every load reads the listed mods from disk and rebinds
saved script state by name. Two ordinary changes therefore strand a game in
progress:

- The generated Merge profile's Mod id is a pure function of its ordered Merge
  members (`compose.profile_mod_id`). Adding a Merge mod gives the profile a new
  id, so every older save lists an id that is no longer installed.
- Standard mods do not feed that id. A newly selected Standard mod keeps older
  saves loadable, but they never load it.

## File format

`SVGD`, u32 payload length, u32 revision, u32 zero, then the payload, which ends
exactly at the `MAP ` chunk tag. The payload ends with the mod list: the `Rel@`
marker, the 16-byte custom-quest UUID (zero outside custom quests), a u32 count,
then one record per mod: the 16-byte GUID in Windows binary layout followed by
the mod's NUL-terminated display name. Revision 10 descriptors end at `Rel@` and
carry no list; they are reported as made without mods.

Entries match by GUID. The game rewrites the display names from the loaded mods
when it next saves.

`rewrite_mod_list` replaces only the list and the payload length, parses the
result again, and compares every byte outside the list with the original before
anything is written.

## Rules

A save is offered only when every change is an addition:

1. **Its Merge profile only gained members.** The profile's members come from the
   Manager's prepared-build history (`prepared-builds.json` beside
   `profile.json`, one row per prepared profile id, newest 64 kept), from the
   retained packages of saved profiles, or by recomputation. Recomputation
   searches subsets of the current members in the current order for the save's
   profile id. A match proves that the older profile held exactly that subset.
   It is enabled only when the same computation reproduces the current profile's
   own id. A profile that lost a member, moved a member to Standard, or cannot be
   accounted for is left alone.
2. **Every other listed mod is still selected.** A listed mod that is now a
   Merge member is dropped, because its content loads through the profile. A
   listed mod that is installed but not selected marks the save as belonging to
   another selection, and the save is left alone. So is a save listing a mod that
   is not installed.
3. **Additions keep existing entries in place.** Profile entries are re-pointed
   in place. Newly selected Standard mods are inserted in launch order ahead of
   the profile. A missing profile part is appended, profile last, as Launch
   activates it.
4. **Profile scripts follow the save's quest rules.** A save lists the shared
   profile record plus the scripts record for its rules (original or expansion).
   Those rules are read from a listed scripts record or from a listed mod whose
   dataset is rules-specific. When they cannot be told and a scripts record would
   have to be added, the save is left alone.

Nothing is ticked by default, and each update needs the player's choice. The
copy is written as `<name> (updated).GMP`, or `(updated 2)` and so on, through a
temporary file and a rename that never replaces an existing file. The original
is read again first and must still hold the list the plan was made from.

## Cautions

These updates are offered but marked, and the window asks again before writing
them:

- **New unit or building types.** An added mod's Description records of type
  `Unit` that neither the stock game nor the save's existing mods define. Merge
  members are read from their preflight inventory, Standard mods from the
  catalog's definition inventory.
- **Changed existing content.** A definition that the merge report shows an added
  mod changing together with a mod the save already uses, where the added mod's
  version is kept or combined: `gpl.instruction_merges`, `gpl.conflicts`, and
  the script, XML and sound preference rows.
- **Merge profile added to a save played without one.** Its scripts may change
  mods the save already uses.

## Evidence

The rules come from play tests on long-running saves:

- Adding a Merge member without new types, re-pointed through the profile id,
  kept the game intact: the game clock continued and units were unchanged.
- Adding a Standard mod with its own scripts as a new list entry kept the game
  intact.
- Size-changing list edits load normally.
- Removing two Merge members that add buildings made the game rebuild the
  quest's start-up on the saved world: the game clock restarted near zero,
  start-up spawns repeated, and saved heroes were reinitialised. The same
  happened with Classic Launch, without the runtime. Removal is therefore never
  offered.

Adding new unit types to a game in progress has not been play-tested; that is
why it is a caution.

Offline verification on 68 real saves:

- the parser matched an independent reader on every save;
- an identity rewrite reproduced every file byte for byte;
- recomputation identified the membership of six historical profile builds with
  no history file.

## Version coverage

The feature reads and writes save files only. It uses no executable patch and
no runtime hook. The descriptor layout was verified on saves made with Steam
beta2 (1.5.2.28), and on older Steam saves carrying the same revision-11 list.
No GOG save was available. GOG 1.5.2.28 is expected to share the layout, but
that is unverified and needs a GOG save fixture.

## Limitations

- A save is matched to its profile through history or recomputation. A profile
  whose members were reordered before this history existed cannot be accounted
  for, and its saves are left alone.
- The quest rules of a save that lists no rules-specific record cannot be read
  from its mod list.
- Cautions report what the merge report and the Description files show. They do
  not prove that an update is safe or unsafe.
