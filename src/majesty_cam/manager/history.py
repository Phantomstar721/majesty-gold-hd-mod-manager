"""Brief player-facing patch history, newest first."""

PATCH_HISTORY = (
    ("0.3.13", (
        "Optional patches support native custom building panels and scripted ground actions.",
        "Selected mods explain which optional patches they need before launch.",
        "Fixes repeated research completion that could crash the game.",
    )),
    ("0.3.12", (
        "Classic Launch runs your selected Standard mods without preparing a merge.",
        "Save up to five profiles, including your mods, game installation and launch options.",
        "Play original Majesty quests with expansion content using the global toggle.",
        "Gold indicators highlight new or updated mods. History shows what's new in the Manager.",
    )),
    ("0.3.11", (
        "Save Support Report collects bounded failure details to make bug reporting easier.",
        "Adds support for advanced hero combat, travel, research and timed effects on all three game versions.",
        "Speeds up Prepare by reusing parsed files.",
    )),
    ("0.3.10", (
        "Review Standard and Merge mod conflicts together and choose your preferred mods.",
        "Combines more building, artwork and sound changes correctly.",
        "Custom inventory items can show their own names, icons and hover text.",
        "Labels the Manager and game versions separately and fixes repeated quest loading.",
    )),
    ("0.3.9", (
        "Fixes research and movement support on Default Steam and GOG.",
        "Restores missing expansion artwork and refreshes outdated compatibility results.",
    )),
    ("0.3.8", (
        "Adds GOG support and easier switching between game installations.",
        "Improves custom ability panels, hover text and research effects.",
    )),
    ("0.3.7", (
        "Adds richer recruitment and list panels, including lower-resolution layouts.",
        "Combines independent script and building-description edits more reliably.",
    )),
    ("0.3.6", (
        "Speeds up repeat scans and mod selection.",
        "Improves recovery after failed preparation and reduces unnecessary logging.",
    )),
    ("0.3.5", (
        "Fixes custom building controls when their panel first opens.",
    )),
    ("0.3.4", (
        "Fixes incorrect compatibility warnings for custom building open/close controls.",
    )),
    ("0.3.3", (
        "Adds support for custom building open/close controls and hero purchases.",
    )),
    ("0.3.2", (
        "Improves custom panels at lower resolutions and fixes panel navigation.",
        "Adds support for actions on building occupants.",
    )),
)
