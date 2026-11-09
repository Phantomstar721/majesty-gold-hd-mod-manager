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

## Manager Change Ownership (Mandatory)

All changes to this repository must go through the owning **Mod Manager**
thread `01a03025-a437-7891-9db0-e4ecb66f264e` for integration and the complete
three-version verification below. This applies to runtime, Python, profiles,
tests, build/staging tooling, and documentation, including work requested by
other mod threads.

Other threads must deliver proposed patches and supporting evidence to this
thread; they must not independently modify Manager files, deploy Manager builds,
or bypass its verification. Preserve existing work during handoff and identify
changed files, in-flight writes, and outstanding limitations. A feature request
or approval in another thread is not permission to bypass this ownership rule.
Changes to this arrangement require explicit user authorization.

## Supported-Version Parity (Inviolable Release Requirement)

ALL Manager functionality must support all three supported executable profiles:
default Steam 1.5.2.24, Steam beta2 1.5.2.28, and GOG 1.5.2.28. Version parity
is part of the implementation scope, not an optional later port. Do not call a
feature complete or release-ready based on beta2 alone.

Trace and verify the stock lifecycle independently for each build, implement
explicit guarded profiles, and cover capability checks, packaging and docs.
Distinguish static verification from actual in-game acceptance. Never remove
guards, guess addresses, or advertise compatibility without supporting evidence.

This applies to existing and future features, optional features, derived
capabilities, integration work from other threads, and every reachable native
helper, not only the top-level feature selector. Beta2-only helpers, hardcoded
beta2 addresses, exact-beta2 image gates, and silent feature disabling do not
satisfy parity. Storefront-specific loaders may differ, but the resulting
gameplay capability must be equivalent on all three builds.

Before implementation, inventory the feature's complete dependency chain for
all three builds. Before completion or packaging, verify declaration acceptance,
capability derivation, preflight, runtime installation, dispatch, persistence,
cleanup and UI behavior wherever applicable. Test the actual production path,
including combinations that activate shared helpers. Merely having three
profile entries or passing parser tests is insufficient.

Release verification must require all three executable fixtures and fail if a
fixture is missing, skipped, mismatched, or an applicable capability lacks a
verified implementation. Keep machine-code verification and live acceptance
separate; never label an untested lifecycle verified. Build, staging and release
gates must check parity, not rely only on prose or developer memory.

Do not stage, publish, recommend beta2 as the permanent remedy, or mark work
complete with version-limited functionality. Missing evidence is a blocker to
resolve, not permission to remove guards or copy addresses. Offline prototypes
may remain explicitly non-production and unreachable from shipped declarations.
Only a new, explicit user instruction naming the feature and excluded versions
can amend this requirement; prior exceptions and unfinished integrations do not.

## Packaging Lock Rule (Mandatory)

If an existing application, package, staging directory, executable, or other
release output is locked, stop immediately and ask the user to close the
relevant application or process. Wait for the user to confirm before retrying.

Never work around a lock by rebuilding to an alternate directory, creating a
side-by-side package, renaming or moving the existing output, staging from a
different build, or otherwise producing a substitute package. A locked output
must be resolved with the user before packaging continues.
