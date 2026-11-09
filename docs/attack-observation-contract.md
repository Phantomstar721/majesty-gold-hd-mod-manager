# Guarded attack/projectile observation

## Query cost correction (October 8, 2026)

The original consumer requested settlement on every weapon-preparation
decision. Combined with scalar ReadProcessMemory calls for every field and
repeated native-tree reads for every unit, this made ordinary attacks run an
unnecessarily expensive world audit. The Public stutter observation showed
4.828 game CPU seconds in a five-second sample, zero Manager/launcher CPU,
zero runtime-log growth and no external trace reader. This isolates work to
the game process but is not a sampled native CPU profile.

The stock completion contract requires settlement for actual/pending weapon
changes, not continued fire with the same weapon. That call-placement fix
belongs to the consumer. Runtime callers that explicitly request a complete
shot snapshot still receive one; a rare full saved shot-store recovery must
not be replaced by assuming absent entries or forgetting outstanding shots.

Within the native predicate, adjacent fields are copied in bounded native
structure spans. The same catalog/tree membership, duplicate/cycle, actor,
order, projectile, world and lifecycle checks remain. Tree nodes already
read during one synchronous query are reused only for that query, reducing
repeated index-search reads. There are no native game calls during enumeration,
no result/timing cache and no copied pointer or tree data retained across
queries. A later query reconstructs current state, including restored orders.

The focused fixture contains101 units and200 unrelated orders in a deliberately
deep valid tree. It requires fewer than1200 native reads, checks every required
read failure stays unknown, and mutates the tree between queries to reject stale
reuse. Existing pending-animation, outstanding missile, queued-removal,
callback and lifecycle cases continue to exercise the same result contract.
The core layout and algorithm are common to all three guarded builds; no new
native addresses or hooks are added. The local build receipt is
`local/attack-observation-cost-build.log`. In-game frame-time acceptance remains
separate from these bounded fixtures.

Installed local test runtime SHA256:
`3d56b4936a265661a72c2b137a117b63962fa0ab9bb091dfba2a81dab65f6dd9`.
Local Manager SHA256:
`a0a59a7766a1a13d1955b117d5b647eff995ecbab34745f20a1bcf01982f000c`.
The guild's source-call correction requires the user to Prepare again; replacing
the DLL alone does not remove calls already compiled into the merged profile.
The coordinated consumer deployment is the guild owner's
`private/hunter-full-store-recovery-v1` candidate: ordinary same-mode decisions
with free shot slots issue no native settlement/snapshot query; actual/pending
switches retain settlement, and full-store cleanup retains the existing snapshot
path at a stable decision boundary. Temporary GPL diagnostic bookkeeping is
removed. Local source/BCD deployment is verified against that owner's receipt.

Implemented in the Manager working tree, with offline verification only. The
runtime capability is `manager.attack-projectile-observation.v1`. It is derived
from validated composition, never from a package's capability assertion alone.
No live runtime, gameplay or native save/load acceptance is claimed.

The native implementation now uses explicit default Steam, beta2 and GOG
profiles at x86 image base `0x400000`. Startup checks reviewed observer/cast
bodies and action/image paths before installing hooks, rather than requiring
one modified-beta2 whole-file hash. Python preflight uses the central supported
executable identity check; it does not substitute for those native guards.
See [current lifecycle work](dawnfall-fade-lifecycle.md) and the research
observer/cast ABI manifests. Live gameplay acceptance remains outstanding.

## Consumer declaration

```json
{
  "type": "stock.attack-projectile-observation.v1",
  "feature_key": "projectile-observation",
  "api_prefix": "WHP",
  "actor": "Witch_Hunter_Prototype",
  "action": "WHP_Bolt",
  "projectile": "Red_Rogue_Bolt",
  "release_callback_symbol": "WHP_BoltReleased"
}
```

Version 1 supports exactly one declared actor binding. Output may be one Any
BCD or the native Any + Majesty + MajestyExpansion bundle. Both effective
dataset views are validated. Multiple actor bindings remain unsupported. If
partitioning originally produces only one dataset patch, composition moves the
unchanged shared release callback into both real patches, preserving both
effective programs and supplying an explicit completion event for each view. All names are bounded; package offsets, patch bytes and native
code are forbidden. The native implementation contains no package UUID or
hard-coded consumer names.

The prefix generates eight native output-argument procedures:

| Suffix | Arguments | Result |
| --- | --- | --- |
| AttackSettled | out integer, agent | -1 unknown, 0 busy, 1 settled |
| ReleaseId | out integer, agent, agent | matching synchronous shot ID or 0 |
| ImpactId | out integer, agent, agent | matching synchronous shot ID or 0 |
| BeginShotSnapshot | out integer, agent | ephemeral token or 0 |
| ShotPending | out integer, agent, integer shot, integer token | -1 unknown, 0 absent, 1 pending |
| EndShotSnapshot | integer token | close matching token |
| PayloadFull | agent, agent, integer shot | diagnostic only |
| ShotRetired | out integer, agent, agent, integer current, integer old | -1 unknown, 0 unproved, 1 concrete retirement |

Identity and token range is conservatively 1..2097151. Unsupported IDs never
truncate or become proved absence. All outstanding native bolts are observed;
32 consumer payload slots do not impose a native scan limit.

## Composition and provenance

`compose.resolve_attack_observation_bindings` checks package ownership against
final effective XML/GPL after resolution. Actor/action and release callback need
one owner. Missing, replaced, ambiguous or signature-incompatible callbacks,
native alias collisions and wrong projectile/script mappings fail closed. The
stock projectile may be shared. Unrelated stock resource-name duplicates do not
invalidate the three resources actually being bound.

`attack_observation_proof.from_composed_output` consumes the actual emitted BCD.
The proof is `DataMX/majesty_mod_manager_attack_observation.bin` (MMOB v1 for Any; v2 for scoped output), beside
the existing MMCP capability manifest. It carries the validated declaration and
SHA256 records for six audited baseline archives, actual generated outputs, and
optional non-overriding BCDs. New MMOB versions5..8 also carry protected names.
The native loader uses a bounded port of the existing BCD ownership parser for
previously unseen files. Optional files cannot override protected stock combat
definitions, linked native callbacks or observer aliases. Unrelated emitted
definitions (such as quest constants and other hero trees) are not an attack
observation dependency. The protected stock names are the existing
prototype audit set: make_attack, hit, gettohit, gettoavoid, notvalid,
notvalid_attacker, damage_dispatch, attack_end, exp_value, attack_object and
rogues_guild_birth. Only names actually supplied by the composed output are
protected from this set; unchanged Standard functions are not conflicts with
the profile. Native aliases and explicitly required callbacks remain protected.
Malformed/opaque files and conflicting first publications make observation
unknown. Older proof formats retain their original digest-only
behavior until the user prepares updated output. No isolated prototype/DLL digest is substituted
for composed-output provenance. MMFR has not been extended.

Generated-package validation checks capability/proof consistency, exact baseline
identities, emitted BCD digest, callback presence and alias absence. Native code
loads the proof via the existing canonical MMCP path, checks exact executable
identity and audited baseline hashes, and never loads package-supplied code.

## Native lifecycle and limits

`AttackObservationRuntime.cpp` installs from `MapQueryRuntime`'s existing
post-stock GPL registration edge. It verifies all fourteen whole-instruction entry
windows before writing any hook and refuses late installation. Installation
failure uses the existing fatal Manager launch handler. Stock arguments, calls,
return values, dispatch and cleanup remain unchanged.

The BCD wrapper locks and hashes the actual native filename with a read-only,
read-sharing-only handle held throughout loading. It invalidates observation
before native definitions change. `LoadProof` checks successful nested completion
of baseline IDs 5,4,3,2,1,0 followed by actual common output ID6 and, for scoped
output, exactly one dataset patch ID7 or ID8, in either order. Public live logs
show sequential baseline calls followed by dataset then shared. Both sequential
and properly nested baseline completion are covered. Neither common-only loading
nor mixing both dataset patches establishes readiness. Inspected non-overlapping
files may load between or after required records. Within the verified category1
reverse list, later exact-name duplicates of already admitted generated entries
are shadowed, not conflicts. Namespace and exact symbol spelling are retained.
The filename-wrapper observer identifies the exact per-profile category1 caller
and receiver. Postload closes this evidence before stock linking; no record is
borrowed from a previous batch. Unknown callers cannot establish shadowing.
The native selection/link behavior is unchanged. See research
`script-winner-20261006.md` and `script-batch-observer-20261006.md` for all-profile
winner, ABI, entry and caller evidence. These additions classify later duplicate
loads, not universal dispatcher or source-context lifetime safety. Missing,
failed, repeated or conflicting loads cannot establish readiness. A full
baseline reload outside the current generated-output batch requires generated
output again. Within that batch, an exact audited baseline digest may continue
after generated outputs: generated exact-name winners remain first, while
unmodified protected callbacks may still come from the audited stock archive.
This requires the verified category1 caller, completed generated outputs,
bounded parsed definitions and no case-only competing symbol spelling.
Unknown archives do not receive this baseline allowance. Postload clears the
batch evidence, so it cannot authorize a later reload. A fault stays latched until
process restart. This order is an acceptance guard, not a claim that a composed
package has been observed loading in a live session.

Readiness additionally checks effective loaded resource names, action/script
fields, projectile engine and callback registry. Mutation guards cover stock
release, impact dispatch, order submission/unlink/destruction, restoration and
spawn boundary. Spawn is only an observation guard; construction and failure
cleanup are not replaced or newly certified. Concrete retirement copies identity
before the stock call and records only a normal return. No freed pointer is read.

World destruction invalidates first. A successful stock load at 44EAD0 must
produce a nonnull world; attachment at 425C90 must return to 426291 in mode0/3,
with runtime world slots matching. Other startup/attach routes remain unknown.
Save/load, mutation and world generation changes invalidate snapshots and
retirement evidence. Synchronous nested callbacks restore their caller context.
No timers, polling, saved native pointers or replacement gameplay state machine
are introduced.

Evidence: supplied consumer HookWindows/observation source and recovery BCD
completion evidence; research `docs/witch-load-handoff.md`; Manager
`docs/stock-bcd-ownership.md`; exact-image byte fixtures. The supplied recovery
log establishes baseline completion only; candidate/composed load acceptance and
native gameplay remain untested. Static models do not close those runtime limits.

## Offline verification

Python fixtures cover parser, ownership, actual-output proof, archive overrides,
malformed wire records, capability derivation, profile refusal and compatibility
source composition. Native fixtures cover load-order state, world replacement,
retirement, nested context, snapshots, more than 32 bolts, numeric bounds and
Python/native MMOB decoding. `tests/test_attack_observation_profiles.py` checks
the fourteen windows and six archive hashes against read-only executable fixtures.

Build with `scripts/Build-Runtime.ps1 -OutputRoot artifacts/runtime-test
-AttackObservationTests`. The build never launches Majesty. The read-only v6
consumer proof check is recorded under `artifacts/attack-observation-consumer-check.json`;
it is an input integration check. The later explicitly authorized isolated
compositions are recorded in `artifacts/observer-composition-verification.json`: 
v6 alone, with Bards, with Alchemist, and with both. Each includes the actual
three BCD hashes, MMOB/native fixture result and six research rows. Outputs live
only under `artifacts/observer-composition`; no canonical profile is changed.
Native load-order fixtures verify the acceptance state machine, not observed
live execution of those compositions.

AP10 service research: [audit](ap10-service-research-audit.md). Reviewed spell
combination binding: [contract](reviewed-compatibility-components.md). Paid
hostile-lair casting and safe exterior movement remain separate provider gaps.
