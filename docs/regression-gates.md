# Offline regression gates

Run `scripts/Test-Regression.ps1` in the relevant checkout. Its checked-in
`regression-mode.txt` distinguishes release from development; selecting the
wrong mode is an error. `-ApplicationRoot` selects an existing packaged
application to **read**, not launch or replace.

The wrapper uses the installed Public executable and the existing beta2/GOG
fixture folders. Set MAJESTY_PUBLIC_EXE, MAJESTY_BETA2_EXE, MAJESTY_GOG_EXE
to override those read-only inputs. Missing or mislabeled fixtures fail.
Whole-file hashes record provenance; admission still checks the supported
profile and consumed native code, not unrelated executable changes.

## Separate coverage

- Release: actual released guild packages, all supported executable profiles,
  all preference orders/subsets in the existing package gate, XML conflicts,
  sparse/named art slots, reordered image bodies, palette-dependent tile placement,
  grouped Standard review and cycle rejection, sound preferences, periodic damage
  call routing, source recovery, generated-event review, and the fixed
  reported Standard-component combination in both preference directions.
  Development-only art packages are excluded.
- Development: actual installed guilds plus the local development package,
  every native profile test, placement/art/scoped-output and private lifecycle
  fixtures. MAJESTY_DEVELOPMENT_PACKAGE overrides the local development package
  folder. The release-only combination engine is not claimed as development
  coverage.
- Both: finalized runtime registry/capability checks, cache regression tests,
  executable admission and targeted corruption tests, and tests of the gate
  itself. Required skipped tests and empty suites fail.
- Packaged phase: import Manager Python modules from the EXE archive, refuse
  source fallback for missing modules, compare every bundled Manager module
  with current source, compare profiles/payload with build inputs, then repeat
  regression tests on bundled code. Runtime .log files are not code inputs.

The latest placement incident has a consumer regression executing the actual
final-validator placement branch with encoded v2/v3 proofs, distinct required
levels, wrong image IDs and truncated data. It covers that branch, not a claim
that the entire game lifecycle has been exercised.

## Output and safeguards

Reports live in local/regression and contain fixture hashes, mode, modules,
source/test input hashes and application file hashes. The Python fixture child
rejects writes outside its disposable temporary directory. Actual package
audits read installed inputs and compile only temporary GPL fixtures. None of
these commands invokes Manager Prepare or writes a user merged profile.

Build-ModManagerExe runs the source gate before packaging and the packaged gate
before reporting completion. Existing native compilation/fixture gates remain
in place. Release staging also requires an unchanged packaged regression
receipt; changed source, tests, runtime, bundled profiles or application files
require re-verification. It does not rebuild automatically.

These are offline checks, not live gameplay certification: launch, save/load,
panels and performance still need bounded user-approved gameplay acceptance.
A receipt explicitly records liveGameplayAcceptance=false.

## Adding a regression

For every fixed incident add a positive case at the production consumer and a
negative corruption/conflict case. Parser-only tests are insufficient for
serialized outputs. Add new native profile tests as test_*profiles.py: the gate
automatically includes them. Keep release-only and development-only cases in
their respective mode. Do not mark unavailable fixtures as optional skips.
