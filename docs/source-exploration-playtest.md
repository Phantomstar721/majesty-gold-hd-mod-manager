# Source exploration: native acceptance run

Use the canonical development Manager at
`dist/Majesty Mod Manager/Majesty Mod Manager.exe`. Its matching launcher and
DLL are under `_internal/payload/runtime`. This is Steam beta2-only support,
not a Workshop release. Do not substitute an older Manager or runtime DLL.

The Manager does not prepare a profile automatically. The user chooses and
prepares the test configuration, then launches it through the Manager.
Keep production saves separate: use a new disposable quest and test save slot.

## Setup and capture

1. Close the game and any older Manager. Obtain the consumer's approved local
   test package from its owning task. It needs to be discoverable by the
   Manager; this procedure does not copy it into a game directory.
2. In PowerShell from this repository, run:

   ```powershell
   $env:MAJESTY_EXPLORATION_TRACE = '1'
   & '.\dist\Majesty Mod Manager\Majesty Mod Manager.exe'
   Remove-Item Env:MAJESTY_EXPLORATION_TRACE
   ```

   The Manager inherits the flag and passes it to its game child. Removing
   the shell variable does not disable that running Manager's trace. No
   administrator prompt is required. A normally opened Manager has tracing off.
3. Select the beta2 installation. Rescan, select the source-observation
   consumer in Merge, and use **Prepare** and **Launch Majesty** yourself.
   For initial isolation, omit unrelated optional mods. Do not enable a second
   standalone copy of the consumer in Majesty's mod selector.
4. Start a fresh quest with an ordinary recruitable hero and unexplored terrain.
   Note the wall-clock time before each scenario and the hero selected. Capture
   before/after screenshots of its XP/level and the visible terrain.
5. After exiting the game, retain
   `dist/Majesty Mod Manager/_internal/payload/runtime/MajestyBuildingRuntime.log`.
   The log is appended, so retain the timestamps delimiting this run. Do not
   delete prior diagnostics merely to create an empty capture.

## First pass: movement, first reveal, and restoration

- Recruit a new hero. Record its first visible XP and movement. The trace
  must associate reveal with that agent, and no uninitialized-XP error may occur.
- Encourage travel to a new frontier using a normal stock reward flag. Repeat
  over already revealed terrain. Only newly set owner bits should yield
  `Exploration record` lines for that source; stock quest/exploration bonuses
  can also change displayed XP and must not be mistaken for this consumer.
- Let another hero traverse the same revealed area. It must not earn credit
  for those same tiles. Record shared-vision behavior separately if testing
  multiple players; recipient visibility is not another credited owner.
- Pause at a stable location and save to the disposable slot. Reload twice
  without giving a new order. `world-ready` should be followed by a saved-queue
  check, not reconstruction-generated record lines or duplicated rewards.
  Then reveal new terrain and confirm delivery resumes. A genuinely saved
  pending batch may deliver once; distinguish it from already paid XP.

## Second pass: boundary cases

- Use a stock teleport-capable unit whose successful arrival exposes new
  terrain. Record origin/destination and timestamps. Credit must correspond to
  destination reveal, not the intervening map. A failed teleport earns none.
- Observe a reward that levels a hero and increases its sight at a frontier.
  Sight-induced new reveal can produce `pending-next=1`, then a later delivery;
  it must not recurse or lose credit. Native source and consumer saved remainder
  may need a focused paused-state trace to distinguish correct accounting.
- Ownership away-and-back, deleted pending sources, and a deliberately pending
  save require a controlled stock-GPL fixture or a focused native diagnostic.
  Ordinary manual movement alone does **not** qualify these cases. Arrange that
  fixture before declaring the feature production-ready; do not edit a live
  game ad hoc or infer success from a crash-free movement test.

## Timing run

Repeat a representative busy frontier scenario after restarting the Manager
with `MAJESTY_EXPLORATION_TRACE='timing'`. This omits per-source event logging.
`record-us` measures Manager GPL bookkeeping; `dispatch-us` includes consumer
work and any nested native reveal. Nested record time can be contained in
dispatch time, so do not sum the two as independent costs. The line's records
and tiles are recorded since the previous report, not a claim about which
saved batch was delivered. File-writing overhead is outside those timers.

For perceived frame-time overhead, compare the same representative workload
with tracing off and with the consumer unselected. The synthetic native
trampoline benchmark excludes real stock/GPL work and cannot replace this.
Report freezes/crashes with the runtime log, Manager prepare report, selected
mods, exact executable version and scenario timestamps. Live acceptance remains
open until the boundary cases above are actually exercised.
