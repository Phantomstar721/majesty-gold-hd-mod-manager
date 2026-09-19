# GOG Standard mod discovery lifecycle

GOG 1.5.2.28 does not enumerate Steam Workshop. A selected Standard GUID in
Remember Active Mods is ignored if no matching record exists in Majesty's
installed-mod list. Merge output already lives in the stock local Mods tree;
downloaded Standard packages remain in Workshop item directories.

The Manager supplies selected Standard Workshop GUID/manifest pairs only on
GOG launches. It does not copy packages into the shared local Mods directory.
Steam launches use their existing discovery. One manifest can define several
variants: registration loads that manifest once, but Active Mods still receives
only the ordered selected IDs, followed by the Merge ID when present.

## Audited stock lifecycle

All addresses below are RVAs in the pristine GOG image at base `0x400000`, SHA-256
`65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792`.
`scripts/audit_gog_standard_mods.py` reproduces the full-body fingerprints in
`gog-standard-mod-audit.json` and `runtime/GogStandardModAudit.h`.

1. CRT initializer `0x349AA0` constructs the installed-list owner at VA
   `0x7E0C20` through `0x136E20 -> 0x136AA0`: native list proxy and sentinel.
   Active-list storage is separate at VA `0x7E0C3C`.
2. Resource startup `0xEF7F0` initializes the filesystem before discovery. Its
   call at `0xEFD14` passes the Documents Mods string returned by `0xEF240`,
   recursion value `1`, and the original stack options `{0, 1}` to `0x139890`.
   This is a cdecl call; the caller pops twelve bytes and ignores its return.
3. `0x139890` synchronously enumerates `*.mmxml`, joins each path using native
   filesystem virtual `+0x90`, and invokes `0x1397E0(path, options)`. It then
   recurses through child directories with the same options. Search handles
   close through virtual `+0x50`; temporary strings use `0x23C520`.
4. `0x1397E0` allocates/constructs the XML document (`0xFBA20`), retains it,
   calls `0xF9DA0`, and dispatches `0x139760` if loading succeeds. `0xF9DA0`
   stores the manifest path at document `+4` and its directory at `+0x10`
   through filesystem virtual `+0x7C`. Thus relative GPL/CAM/description paths
   continue to resolve against the original Workshop package.
5. `0x139760` visits every `<Mod>` node in XML order and calls `0x139590`.
   Registration checks the tag/ID, parses the GUID using `0x2867C0 -> 0x286530`,
   and checks existing records using `0x138EA0`. A Mod is constructed through
   `0x136E70 -> 0x136C20` with the native GUID-by-value and XML pointer. It
   retains that document, uses the stock `0x135320(3,0,0)` and `(3,1,0)` setup,
   copies both original option dwords to document `+0x20/+0x24`, and appends
   through `0x138370`. The installed list owns these records.
6. The manifest wrapper drops its temporary XML reference; every registered
   Mod retains its own reference. The native parser returns success if any Mod
   registered. The Manager also verifies every requested GUID using stock
   lookup, preventing partial-manifest success from silently dropping a choice.
7. Later startup/menu restore `0x772C0 -> 0x139240` applies Remember Active
   Mods. It searches the now-populated installed list, restores selected IDs in
   saved order through the stock Active list, and invokes canonical apply for
   XML/UI refresh. The registration bridge does not alter Active-list nodes,
   dirty flags, selection callbacks, or UI dispatch.
8. Resource teardown `0xEF06D -> 0x138E90 -> 0x138D90` destroys installed Mod
   records through `0x135CE0`, which releases the XML reference and native name
   string. The last XML reference calls `0xF8C70` and stock delete. Teardown
   clears installed and Active list nodes/counts. CRT exit `0x31CAB0 -> 0x1366E0`
   destroys the remaining list storage. There is no asynchronous registration,
   timer, pending callback, or additional cancellation lifecycle to own.

## Bridge boundary and validation

The suspended runtime validates the exact GOG profile and bounded stock bodies,
then replaces only the five-byte startup call at `0xEFD14`. The wrapper calls
the original directory scan first with all three arguments unchanged. It then
uses the native string constructor `0x23C370`, native manifest loader `0x1397E0`
with the **same original options pointer**, and native string destructor.
Stock GUID parsing/lookup determines which manifests still need registration;
no Manager-owned installed list or duplicate-registration flag is introduced.
If startup repeats after stock cleanup, the now-empty stock list causes normal
registration again. If records still exist, they are not re-added.

The environment protocol is bounded to 26 canonical GUID/tab/absolute-path
records and 30,000 UTF-16 units. Python verifies selected Standard ownership and
the Workshop package root; native initialization validates delimiters, paths,
file existence and lossless conversion for the stock ANSI filesystem. A real
Windows short path is used if necessary; unrepresentable paths are rejected.
No engine string, filesystem or GUID function runs on the injection thread.
All engine work runs at the original stock discovery boundary. Missing files,
missing selected IDs, changed audited code and partial registration fail the
launch with diagnostic log details. The protocol is cleared from inherited
environments on every launch and never supplied to Steam.

Headless native tests stub the audited stock endpoints to check argument
forwarding, sequence, per-manifest loading, repeated startup, cleanup/reload,
string ownership and partial/missing-ID failures. Non-executable GOG fixtures
exercise complete body guards and mutation rejection, including QoL-patched
fixtures. The user reported that selected Standard mods worked in-game with
the GOG trial; broader feature acceptance is tracked in [GOG support](gog-support.md).
