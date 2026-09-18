# Project Rule: Clone Stock Majesty Mechanisms

Follow the workspace **Majesty Gold HD: Stock-First Rule (Mandatory)**. Preserve
Majesty's native CAM structure, ordering, and merge semantics wherever they can
be traced. If no stock behavior defines a merge decision, stop and ask before
introducing a new policy.

## Public Documentation

Keep the README, Workshop description, and release notes generic. Describe
reusable capabilities and update instructions, not named mods or guilds that
motivated a change. Stock game mechanisms may be identified where needed to
explain a technical contract.

## Packaging Lock Rule (Mandatory)

If an existing application, package, staging directory, executable, or other
release output is locked, stop immediately and ask the user to close the
relevant application or process. Wait for the user to confirm before retrying.

Never work around a lock by rebuilding to an alternate directory, creating a
side-by-side package, renaming or moving the existing output, staging from a
different build, or otherwise producing a substitute package. A locked output
must be resolved with the user before packaging continues.
