# GOG registration of downloaded Workshop quests

The Manager passes valid, already-downloaded Workshop `.mqxml` manifests to
GOG's existing quest loader. It does not copy them into Documents or put quest
GUIDs into Active Mods. Local quests continue through the game's own scan, and
Steam continues to discover its Workshop subscriptions normally. Acquiring
subscriptions without Steam remains outside this change.

## Stock lifecycle

GOG startup at RVA `0xEFC67..0xEFCF1` scans three quest roots, then calls the
quest finalization boundary. The last root is Documents/My Games/MajestyHD/
Quests, obtained by `0xEF160`. The quest owner comes from `0x11D400`. Call
`0xEFCE0 -> 0x119650` is a thiscall with the existing owner in ECX and three
stack arguments: native directory string, recurse flag, and options pointer.
The callee pops 12 bytes. The Manager wraps only that last call, executes it
first, then registers the supplied manifests before stock finalization.

The recursive scanner `0x119650..0x1198B4` uses `*.mqxml`, the same stock
filesystem join/find/next/close calls, and manifest loader
`0x1195A0..0x119646`. The bridge calls this exact manifest loader with the
same owner/options, on the startup thread. Its return is boolean AL and its
thiscall pops the two manifest/options arguments.

The loader constructs and retains a native XML document, loads through
`0xF9DA0` (which retains the manifest path and package-relative directory),
then iterates Quest nodes at `0x119520`. Registration at `0x119380` parses
the GUID, maps it through stock `0x136B10`, checks the manager through
`0x117F60`, and constructs the Quest record at `0x113860`. That constructor
uses the same base initialization `0x136C20` as native Mods, including GUID
storage at `+4` and XML retention at `+0x24`. The original options are copied
into the XML document. Stock list insertion `0x118100 -> 0x1163C0` owns the
record under the quest manager at `+0x324`, sentinel at `+0x338`.

The manager's lazy constructor `0x11D400 -> 0x11CEB0` initializes that list
through `0x11A940`. Registration precedes the quest-selection UI; normal
selection and resource loading consume the native records and their original
relative resource directories. No replacement quest browser, completion
record, refresh loop, polling, or persistent selection state is introduced.
The compass shortcut remains an independent QoL utility.

Resource teardown calls `0xEF027 -> 0x11DC90`, destroys the manager at
`0x11CD90`, clears its list through `0x11A9B0`, and resets global owner
`0x7E0A18`. Quest destruction `0x113A30` delegates to base destructor
`0x135CE0`, releasing retained XML and strings. The bridge retains only the
launch manifest list, so another startup boundary checks the live stock list
and re-registers after teardown. Repeated boundaries do not duplicate entries.
Menu cancellation and quest cleanup remain entirely stock-owned.

## Input and failure checks

Python validates discovered Workshop package roots, manifest paths, type and
catalog errors. Each launch removes inherited quest metadata, supplying it only
for GOG. The bounded environment value contains canonical GUID/tab/absolute
path rows. Native parsing validates the file and lossless ANSI/short-path
conversion needed by Majesty. Several quest IDs may share a manifest; each
manifest is loaded once per registration pass. All expected GUIDs must then
exist; full GUID comparison rejects a collision in the stock numeric key.

Startup refuses missing manifests or changed audited loader bytes before
continuing to the menu. `scripts/audit_gog_quests.py` reproduces the exact
stock body guards in `runtime/GogQuestAudit.h`. Native fixtures verify guard
mutation rejection, owner/options forwarding, ordering, variants, repeated
startup, teardown/reload, missing registrations and cleanup after failed load.
Python fixtures verify GOG-only launch metadata and separation from Active Mods.
Gameplay acceptance with downloaded quest packages remains a user-run check.
