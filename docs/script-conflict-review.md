# Choosing preferred mods

Prepare safely combines supported independent changes automatically. If changes
cannot be combined safely, choose your preferred mod once for each conflicting
pair. That mod wins every unresolved conflict between the pair, including those
shared across original and expansion quests. There is no code editor or
line-by-line review.

Each card shows the two mod choices and a **Conflicts** summary, such as attack
decisions, potion use, or hero deaths. Click a mod to select it; the selected
button stays highlighted. Expand **Details** for gameplay explanations, affected
quest types, and any existing compatibility notes. Details start collapsed and
opening or closing them does not change your preference.

The categories and explanations identify affected areas, not a promise that
the Manager understands every mod's exact gameplay effects. Unknown behavior
is identified as **Other gameplay changes**, without guessing what it does.

## What the choice means

- The preferred mod supplies the complete behavior in each affected overlap.
  The other mod's changes within that behavior may be lost; choosing a winner
  is not the same as successfully combining those changes.
- Both mods remain enabled. Their other, non-overlapping behavior remains.
- A third mod's independently mergeable changes are retained; appearing in the
  same gameplay area does not automatically make it another conflicting pair.
- Existing authored compatibility rules stay resolved. If their combined behavior
  overlaps another mod, **Details** explains which mods the rule keeps together;
  it does not reopen a choice between those already-compatible mods. Preferences
  against the outside mod must keep or replace the shared behavior consistently.
- One preference covers all conflicts between the same pair. More than two
  mods can be involved; preferences must be consistent. For example, preferring
  one mod over a second, the second over a third, and the third over the first
  cannot produce a consistent result. The chooser asks you to revise a choice.
- Cancel leaves your last completed setup unchanged. You can instead disable
  a conflicting mod or use an author-provided compatibility update.

Successful preferences are reused only with unchanged preparation inputs.
Use **Review mod preferences** before Prepare to reconsider them. Changing
a preference does not bypass compilation or the Manager's normal validation.
A failed preparation does not replace the previous completed setup.
If preparation fails after choices are accepted, the open Manager retains
those choices for the same inputs and preselects them when the chooser reopens.
This retry draft is memory-only: changed inputs, a successful preparation or
closing the Manager discards it. It never bypasses the chooser or validation.

## Safety boundaries

Preferences choose between identified mod versions; they cannot supply edited
source, bypass missing source evidence, or override an unknown compiled owner.
Prepare still checks required features and dependencies for each quest version.
These checks may reject an incompatible choice even though a preference was
provided.

The Manager does not move edits between helper functions, guess argument
meanings, or invent gameplay behavior to avoid a conflict. Safely combined
changes remain automatic; unresolved changes require an explicit preference.
Pair comparisons and recombination use the existing instruction merger, only
for definitions already found unresolved. They add no new rewrite heuristics,
source searches, or compiler invocations. If a whole group cannot be combined
despite compatible pairs, that group requires an explicit priority choice.
The analysis resumes from its existing preparation snapshot after the choice,
without restarting artwork or source discovery.

This preparation-time workflow uses the selected installation's stock inputs
for default Steam, Steam beta2, and GOG. It adds no in-game polling or per-hero
state. Choosing a mod does not guarantee that its gameplay changes are compatible
with every other enabled mod.
