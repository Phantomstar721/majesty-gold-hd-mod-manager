# Quest content

In **Quests**, check **Play all quests with expansion content** and launch Majesty through the Manager. Original and Northern Expansion quests then load the expansion resources. Quest-specific rules and restrictions still apply. The Sorcerer’s Abode spell bar uses its stock icons and tooltips. Uncheck the box and relaunch for each quest’s stock content. This setting defaults to off and takes effect on the next Manager launch without Prepare.

## Implementation evidence

The toggle changes the requested base from Majesty to MajestyExpansion at the stock quest configuration calls. The game uses its installed expansion dataset and applies active Any and MajestyExpansion components in the usual order, followed by the quest’s own declarations. This also selects the expansion version of toolbar artwork supplied by active mods. The inactive setting leaves stock dataset selection in effect.

The stock references are the installed AP92 panels, the two release-type checks preceding the visibility call for overlay 9600, and the quest configuration paths described in the research repository’s dataset-application.md. Each supported executable has separate checked call sites for active-mod composition and direct built-in lookup. The toolbar setup signature includes the four changed spell-bar bytes on enabled launches. Knowledge graph f2644580d33ad98703361cd8fc88c825068161ef records the stock dataset inheritance under dataset.majestyexpansion. The distinction between mod scope and dataset file contents comes from the stock active-mod comparison.
