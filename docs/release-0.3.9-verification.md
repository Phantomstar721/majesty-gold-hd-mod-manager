# Production release isolation and verification

This checkout starts at 63a8184 and selectively carries forward production fixes:
cache invalidation, description artwork closure, increment/decrement merge safety,
and observer insertion whitespace preservation. The plan schema is advanced to
26 so existing prepared plans require review against this build.

Development integrations remain preserved in the primary checkout. Attack
observation, checked placement, paid source-target v3, saved-attribute rows,
research-submission extensions, presentation sequences and paired progression
are not included here. Existing source-target v2, research, inventory display,
movement scaling, and all other committed production functionality remain.

The reported public-version failure came from stale beta2-only checks in the
shared GPL registration bridge. Research/movement adapters already had explicit
three-build profiles, but the bridge rejected those callbacks first. This
release removes those obsolete checks, retaining all per-build byte guards.

`verify_release_parity.py` requires all three executable fixtures, rejects
skipped profile tests, and enforces this release's feature boundary. Payload
staging runs it plus the x86 native installer matrix. The matrix maps private
data-only executable copies and invokes production validators/installers; it
does not execute game code, launch Majesty, or modify any installed game file.
It covers all combinations of map, movement, timing, research and distance
callbacks, paired-callback rejection and damaged registration rejection.

These are native-code and fixture checks, not a claim of completed human
gameplay acceptance. Live launch, research, movement expiry, save/load and
return-to-menu acceptance must be recorded separately for each game version.
