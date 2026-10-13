# Graph Studio AI Control — Milestones 1–2

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
