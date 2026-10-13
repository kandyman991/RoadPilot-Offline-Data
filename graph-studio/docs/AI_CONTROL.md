# Graph Studio AI Control — Milestones 1–3

## Purpose

Expose a **single, structured Rust read-only inspection engine** through two
interfaces: the existing Tauri application command `ai_control_command` and the
packaged desktop executable's headless command line. No separate AI-written
implementation, HTTP listener, MCP server, privileged service or automatic jobs.

This feature is an inspection foundation; it does **not** connect normal ChatGPT
conversations to the Legion on its own. A future explicitly authorized local bridge
may invoke the headless command and inspect its structured JSON output.

## Headless usage on Linux

Run the installed Graph Studio executable with:

```bash
roadpilot-graph-studio --ai-capabilities
roadpilot-graph-studio --ai-inspect
roadpilot-graph-studio --ai-diagnose
```

The executable name may differ by installation; invoke the installed Graph Studio
binary directly if necessary. Both commands return JSON to standard output and
exit without launching a desktop window. They only read the current user's
`~/RoadPilotGraphStudio/config/regions/` and
`~/RoadPilotGraphStudio/builds/` inventories.

Example applications may call the Tauri IPC command from the **trusted application
frontend**:

```ts
const response = await invoke("ai_control_command", { command: "inspect" });
```

The Tauri path includes the in-process build status. **The headless CLI cannot
know whether Graph Studio is currently building** and explicitly returns
`runtime.attached = false` with `runtime.buildStatus = null`. Do not interpret
this as an idle build. Similarly, an inventory manifest does not establish that
a Valhalla route was verified.

## Contract

Both interfaces call `ai_control::execute`:

- `capabilities`: reports versioned read-only commands.
- `diagnose`: returns schema `roadpilot.graph-studio.ai-diagnostics.v1` for retained Valhalla and border-report summaries plus sanitized last-build outcome.
- `inspect`: returns schema `roadpilot.graph-studio.ai-control.v1`,
  allowlisted region summaries, bounded routing-build manifest summaries,
  warnings, and optional in-process build state.

Only safe summary fields are emitted. No raw configuration JSON, arbitrary file
contents, machine paths, R2 secrets, token files, logs or private keys are returned.
Symlinks to unrelated directories and oversized inventory JSON files are skipped.
Both commands perform no filesystem writes; the CLI creates no workspace.

Unknown commands and operations such as `start_build_queue`,
`activate_r2_release`, `save_region_config`, or `delete_handoff_override`
are rejected. No network listener, network token or remote access capability is
introduced.

## Verification

Rust unit tests exercise unknown-command rejection, capability enumeration,
region/build manifest allowlisting, secret redaction, live-versus-headless state
semantics and no-workspace-creation behavior. GitHub's existing Graph Studio
build runs `cargo test --lib` before packaging. No additional artifact upload,
region build or Valhalla graph compilation is needed.

## Next milestone

Add a **permissioned local bridge** (potentially MCP or the existing connected
Remote Desktop Commander transport) after desktop verification. It must default
to read-only, require explicit opt-in and never expose an unauthenticated TCP
listener. Later introduce inspect/validate operations backed by the existing
Valhalla proofs and diagnostic reports, and transactionally controlled mutations
only after dedicated tests and human authorization.

## Milestone 2 — retained graph diagnostics and sanitized errors

`--ai-diagnose` and Tauri `ai_control_command("diagnose")` use the same Rust
diagnostics module to return `roadpilot.graph-studio.ai-diagnostics.v1`.

The result contains:

- **Routing validations:** recorded validation-route pass/fail counts and border
  vs interior counts from retained routing manifests, Valhalla version, fingerprint,
  and whether the named routing TAR is present as a regular file. It **does not**
  rerun routes, validate archive contents or hash large TARs.
- **Border reports:** bounded summaries of the already-exported
  `~/RoadPilotGraphStudio/reports/*.json`: two graph identities, selected
  crossing outcome/probe counts and road overlap counts. Reports may refer to
  stale graph versions; no automatic freshness claim is made.
- **Last recorded build:** Graph Studio records a small
  `~/RoadPilotGraphStudio/diagnostics/latest-build.json` **when a build
  finishes**, even if it fails. Fields are only package/region identifiers,
  finished time, last stage enum, `succeeded/failed/cancelled` and a stable
  failure category such as `osm_duplicate_objects`, `osm_extract` or
  `route_proof_or_pack_validation`. No stdout/stderr, paths, tokens or freeform
  exception messages are persisted or returned. Errors are classified using the
  last observed stage, so categories are *diagnostic hints*, not root-cause proof.

The persisted failure record applies only to builds completing after installing
M2. It cannot recover previous session failures. On headless invocation,
`runtime.attached=false` and `runtime.buildStatus=null`: no inference about
running processes is possible. Tauri returns its actual in-process build snapshot.

```bash
roadpilot-graph-studio --ai-diagnose
```

The inspector itself performs **zero writes** and does not open a listener,
start Valhalla, mutate a graph, download sources or touch publication state.
Inventories are bounded; only regular files in fixed workspace-relative folders
are scanned, with symlink directories ignored. No raw log contents or arbitrary
JSON fields are surfaced. To investigate the original failure text, the user
still uses the existing Graph Studio build console.

M2 adds Rust unit tests for successful/missing/failed recorded proof, prior
border report summaries, sanitized outcome writes, absent workspaces and
symlink avoidance; existing PR CI runs these tests. No separate runner, artifact
upload or real regional build was added.

**Next:** confirm the new binary on Legion, compare `--ai-diagnose` results with
actual manifests and border reports, and complete the pending Austria rebuild
smoke test. Future M3 can add explicit, permissioned graph integrity/Valhalla
verification operations without duplicating the existing tools.

## M3 — explicit on-demand Valhalla route verification

M3 deliberately **does not** expose unrestricted agent control. One request
runs one local Valhalla route probe using the same request validation, route
request encoding, and route polyline decoding as Graph Studio's own route
planner. It uses the current working graph under
`~/RoadPilotGraphStudio/work/<region>/build/`.

```bash
roadpilot-graph-studio --ai-verify-route geofabrik-austria 47.582889 12.162319 47.609970 12.200709 motorcycle
```

No desktop window or HTTP listener is required. The CLI exits 0 only if its
endpoint-correlated route passes, 1 on a bounded Valhalla failure, 2 on invalid
arguments or missing/unsafe local graph. Output is a **bounded structured
summary**, not arbitrary Valhalla JSON or stderr.

From a **trusted Graph Studio frontend**, the same Rust verifier is called as:

```ts
await invoke("ai_verify_route", {
  regionId: "geofabrik-austria",
  startLat: 47.582889, startLng: 12.162319,
  endLat: 47.609970, endLng: 12.200709,
  costing: "motorcycle",
});
```

Security and resource boundaries:

- Explicit operation only; no schedule, discovery scan or silent route probes.
- Valid region id and finite GPS coordinates; allowed costings:
  motorcycle/auto/bicycle/pedestrian.
- Local existing config/tiles only, no downloads or graph generation. 
  Traversal and symlinked graph directories are rejected.
- Fixed `valhalla_service` executable, **no shell interpolation**, no arbitrary
  commands, paths or custom costing JSON. 20-second timeout, 1-MiB output cap.
- Test uses ordinary Valhalla `route`, status 0, decoded route geometry, summary,
  and checks both actual returned endpoints within 150 m of the requested ones.
- Reports distance, travel time, vertex count, endpoint offsets, duration,
  graph source and failure category. Raw engine stderr is discarded.
- Tauri refuses to start the probe during an in-process graph build. A headless
  invocation **cannot** know if the GUI is building: caller should ensure no
  build is in progress.
- `crossRegionProof=false`, `retainedPackHashVerified=false`: this is not
  a border-crossing proof, exact retained-package replay or cross-region F8
  test. These remain separate, stronger validations.

This interface performs no intentional Graph Studio workspace writes; it
invokes Valhalla against an existing local working graph. Passing CI tests
of parsing and safeguards is **not** a real Legion graph test.

## GUI routing parity fix (post-M3)

A real Legion test proved M3 headless routing through Austria: 4.725 km,
161 ms, endpoint offsets 8.36 m / 4.32 m. The desktop planner independently
failed, even with both endpoints in Austria, and displayed only stderr messages
about the optional Valhalla traffic archive.

Graph Studio initialized the GUI by rewriting PATH to prepend pyvalhalla's
**native** command directory for binary graph tile output. Headless M3 bypassed
that rewrite and instead successfully used the pyvalhalla **launcher**.
The GUI therefore did not actually use the same Valhalla executable as M3.

After this fix Graph Studio retains the original launcher path before the
native-tool rewrite. Route planning, route expansion, locate, handoff route
probes and M3 verification choose that same launcher and use one bounded
JSON-aware runner. Binary graph-tile rendering still uses the native command,
because launcher stdout would corrupt binary output.

The GUI now reports a bounded error category or Valhalla status instead
of unrelated stderr warnings. A failed optional expansion no longer makes an
otherwise successful normal route appear to fail. No graph, PBF, cache or
package format changes are required. Desktop acceptance testing is still
required to prove the fix against Austria on the Legion.
