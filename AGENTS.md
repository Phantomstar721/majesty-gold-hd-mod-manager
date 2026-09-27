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

## Supported-Version Parity (Mandatory)

Shared Manager features must support all three supported executable profiles:
default Steam 1.5.2.24, Steam beta2 1.5.2.28, and GOG 1.5.2.28. Version parity
is part of the implementation scope, not an optional later port. Do not call a
feature complete or release-ready based on beta2 alone.

Trace and verify the stock lifecycle independently for each build, implement
explicit guarded profiles, and cover capability checks, packaging and docs.
Distinguish static verification from actual in-game acceptance. Never remove
guards, guess addresses, or advertise compatibility without supporting evidence.

If parity requires substantial additional work or a supported build lacks a
required stock mechanism, explain the specific blocker and ask the user before
accepting a version-limited exception. Existing restricted features are parity
debt, not precedent for adding further restrictions.

## Packaging Lock Rule (Mandatory)

If an existing application, package, staging directory, executable, or other
release output is locked, stop immediately and ask the user to close the
relevant application or process. Wait for the user to confirm before retrying.

Never work around a lock by rebuilding to an alternate directory, creating a
side-by-side package, renaming or moving the existing output, staging from a
different build, or otherwise producing a substitute package. A locked output
must be resolved with the user before packaging continues.
