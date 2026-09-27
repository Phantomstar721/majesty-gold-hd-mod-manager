# Stock GPLMx Purchase_Equipment tail callbacks

`stock.gplmx-purchase-equipment-tail.v1` is a source-composed callback point,
not a native hook. Stock expansion heroes call `Purchase_Equipment`; its final
choice is `Stat_Boost_Check`. If every choice declines, the function returns
FALSE. If any choice succeeds, the one stock final block sets
`ActiveScript = Use_Building` and returns TRUE.

The manager uses Majesty's existing boolean decision-chain boundary. For
example, `GPLMx/DecisionTrees/mx_ranger.gpl` tries equipment, then Bazaar, then
entertainment only when the preceding decision returns FALSE. The complete
effective purchase function is retained under a reserved private name, with
only its declaration renamed. Its helpers, checks, ordering and early returns
are not rewritten. The public entry point calls it once and immediately
returns TRUE when it succeeds; its original handoff has already occurred.

Only a FALSE result offers package-declared callbacks in stable normalized
mod UUID, package-local callback key, then symbol order. The first callback
returning TRUE receives the literal stock `ActiveScript = Use_Building` and
`return TRUE` handoff. All-decline returns FALSE to the hero's next decision.
This includes early FALSE returns from a replacement function: these decline
that purchase choice, not every subsequent custom visit. Callbacks own their
own eligibility; they do not inherit Bazaar-specific expansion or probability
gates. No callbacks means no generated wrapper or extra call.

Callbacks own only their package's decision and preparation: they return TRUE
after assigning the Target/TaskName/intent state required by the stock visit
lifecycle. The manager neither polls nor launches a parallel script. Missing
functions, wrong signatures, duplicate symbols, private-name collisions with
authored or native definitions, direct self-function identity references, and
unresolved GPL conflicts fail closed before compilation. Both the purchase
entry point and callbacks retain their stock boolean signatures; argument
spelling is not significant. Standard source/compiled ownership checks still
apply before selecting the effective body.

`stock.gplmx-purchase-bazaar-tail.v1` applies the same guarded composition to
`Purchase_Bazaar`. It does not assume that the effective implementation keeps
the six-item scan inline, or uses stock item ordering or local variable names.
This later extension point is appropriate when a custom visit must not preempt
Magic Bazaar shopping.

The stock visit lifecycle remains unchanged: a decision prepares Target,
TaskName and buyer intent; `Use_Building` travels and dispatches the building's
visited script, or calls `Reset_Tasks` if the target has died. No timer, polling,
per-hero persistence or parallel script is added. Base and expansion views are
composed separately before partitioning; a shared entry point may call a
dataset-specific private body. This source-level mechanism has no executable
addresses and is shared by all three supported executable profiles.
