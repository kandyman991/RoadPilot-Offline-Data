# Graph Studio AI Control — Milestone 1

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
