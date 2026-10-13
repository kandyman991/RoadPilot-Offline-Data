//! Minimal, versioned read-only command engine shared by the Tauri application and
//! the packaged headless --ai-* commands. No listener, credentials, writes or jobs.
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

const SCHEMA: &str = "roadpilot.graph-studio.ai-control.v1";
const MAX_FILES: usize = 200;
const MAX_JSON_BYTES: u64 = 2 * 1024 * 1024;
const MAX_WARNINGS: usize = 12;

pub fn execute(workspace: &Path, command: &str, runtime_status: Option<Value>) -> Result<Value, String> {
    match command {
        "capabilities" => Ok(json!({
            "schema": SCHEMA,
            "command": "capabilities",
            "readOnly": true,
            "commands": [
                {"name": "capabilities", "readOnly": true, "description": "Describe the versioned inspection contract"},
                {"name": "inspect", "readOnly": true, "description": "Inspect configured routing regions, retained routing manifests and optional in-process build state"},
                {"name": "diagnose", "readOnly": true, "description": "Inspect recorded Valhalla proof summaries, exported border reports and sanitized latest build outcome"}
            ],
            "externalListener": false
        })),
        "inspect" => inspect(workspace, runtime_status),
        "diagnose" => crate::ai_diagnostics::diagnose(workspace, runtime_status),
        _ => Err("Unknown or disallowed AI control command. Only capabilities, inspect and diagnose are permitted.".into()),
    }
}

fn warn(warnings: &mut Vec<String>, message: &str) {
    if warnings.len() < MAX_WARNINGS {
        warnings.push(message.to_string());
    }
}

fn regular_files(directory: &Path, suffix: &str, warnings: &mut Vec<String>) -> Vec<PathBuf> {
    if !directory.exists() {
        return Vec::new();
    }
    // Never follow a directory symlink into another part of the filesystem.
    if fs::symlink_metadata(directory)
        .map(|m| !m.file_type().is_dir())
        .unwrap_or(true)
    {
        warn(warnings, "An inspection directory is not a regular directory.");
        return Vec::new();
    }
    let entries = match fs::read_dir(directory) {
        Ok(entries) => entries,
        Err(_) => {
            warn(warnings, "Unable to list an inspection directory.");
            return Vec::new();
        }
    };
    let mut paths = Vec::new();
    for entry in entries {
        let Ok(entry) = entry else { continue };
        let Ok(kind) = entry.file_type() else { continue };
        if kind.is_file() && entry.file_name().to_string_lossy().ends_with(suffix) {
            paths.push(entry.path());
        }
    }
    paths.sort();
    if paths.len() > MAX_FILES {
        warn(warnings, "File enumeration was limited; inventory is incomplete.");
        paths.truncate(MAX_FILES);
    }
    paths
}

fn read_json(path: &Path, warnings: &mut Vec<String>) -> Option<Value> {
    let Ok(metadata) = fs::symlink_metadata(path) else { return None };
    if !metadata.file_type().is_file() || metadata.len() > MAX_JSON_BYTES {
        warn(warnings, "Skipped a non-regular or oversized inventory file.");
        return None;
    }
    match fs::read_to_string(path).ok().and_then(|raw| serde_json::from_str::<Value>(&raw).ok()) {
        Some(value) => Some(value),
        None => {
            warn(warnings, "Skipped an unreadable or invalid inventory JSON file.");
            None
        }
    }
}

fn string_at(value: &Value, pointer: &str) -> String {
    value.pointer(pointer)
        .and_then(Value::as_str)
        .unwrap_or("")
        .chars()
        .take(160)
        .collect()
}

fn regions(workspace: &Path, warnings: &mut Vec<String>) -> Vec<Value> {
    let mut result = Vec::new();
    for file in regular_files(&workspace.join("config/regions"), ".json", warnings) {
        let Some(value) = read_json(&file, warnings) else { continue };
        if value.pointer("/routing/enabled").and_then(Value::as_bool) != Some(true) {
            continue;
        }
        result.push(json!({
            "id": string_at(&value, "/id"),
            "name": string_at(&value, "/name"),
            "packageVersion": string_at(&value, "/packageVersion"),
            "validationMode": string_at(&value, "/routing/validationMode"),
            "sourceCount": value.pointer("/routing/source/pbfs").and_then(Value::as_array).map_or(0, |v| v.len())
        }));
    }
    result
}

fn routing_builds(workspace: &Path, warnings: &mut Vec<String>) -> (Vec<Value>, bool) {
    let root = workspace.join("builds");
    let mut items = Vec::new();
    if !root.exists() {
        return (items, false);
    }
    if fs::symlink_metadata(&root).map(|m| !m.file_type().is_dir()).unwrap_or(true) {
        warn(warnings, "Routing build inventory is not a regular directory.");
        return (items, false);
    }
    let region_directories = match fs::read_dir(root) {
        Ok(entries) => entries,
        Err(_) => {
            warn(warnings, "Unable to list routing builds.");
            return (items, false);
        }
    };
    let mut directories: Vec<PathBuf> = region_directories
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().map(|type_| type_.is_dir()).unwrap_or(false))
        .map(|entry| entry.path())
        .collect();
    directories.sort();
    let mut truncated = directories.len() > MAX_FILES;
    if truncated {
        directories.truncate(MAX_FILES);
        warn(warnings, "Routing build directory limit reached.");
    }
    for directory in directories {
        let files = regular_files(&directory, "-manifest.json", warnings);
        for path in files {
            if items.len() >= MAX_FILES {
                truncated = true;
                break;
            }
            let Some(value) = read_json(&path, warnings) else { continue };
            if !value.get("artifact").is_some_and(Value::is_object) {
                continue;
            }
            items.push(json!({
                "regionId": string_at(&value, "/regionId"),
                "packageVersion": string_at(&value, "/packageVersion"),
                "builtAtUtc": string_at(&value, "/builtAtUtc"),
                "sha256": string_at(&value, "/artifact/sha256"),
                "tileCount": value.pointer("/artifact/tileCount").and_then(Value::as_u64),
                "graphTileFingerprint": string_at(&value, "/graphIndex/graphTileFingerprint")
            }));
        }
        if truncated { break; }
    }
    items.sort_by(|a, b| b["builtAtUtc"].as_str().cmp(&a["builtAtUtc"].as_str()));
    if truncated {
        warn(warnings, "Routing build inventory is incomplete due to its bounded scan.");
    }
    (items, truncated)
}

fn inspect(workspace: &Path, runtime_status: Option<Value>) -> Result<Value, String> {
    // Only inspect explicit allowlisted paths. The workspace is never created
    // here; read-only access must not modify the machine under inspection.
    let mut warnings = Vec::new();
    let region_list = regions(workspace, &mut warnings);
    let (build_list, build_truncated) = routing_builds(workspace, &mut warnings);
    let attached = runtime_status.is_some();
    Ok(json!({
        "schema": SCHEMA,
        "command": "inspect",
        "readOnly": true,
        "workspacePresent": workspace.is_dir(),
        "runtime": {
            "attached": attached,
            "buildStatus": runtime_status,
            "note": if attached { "Live state from the running Graph Studio process." }
                    else { "Headless inventory only; running jobs and GUI state are unknown." }
        },
        "regions": { "count": region_list.len(), "items": region_list },
        "routingBuilds": { "count": build_list.len(), "truncated": build_truncated, "items": build_list },
        "warnings": warnings,
        "limitations": [
            "Retained manifests are inventory evidence, not independent proof of graph correctness.",
            "No visual/search pack inspection or live Valhalla probes in milestone 1.",
            "No AI action can start, cancel, edit, publish, or delete anything."
        ]
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct TestWorkspace(PathBuf);
    impl TestWorkspace {
        fn new() -> Self {
            let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let path = std::env::temp_dir().join(format!("roadpilot-ai-inspection-{}-{stamp}", std::process::id()));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
        fn write(&self, suffix: &str, content: &str) {
            let path = self.0.join(suffix);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, content).unwrap();
        }
    }
    impl Drop for TestWorkspace {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); }
    }

    #[test]
    fn capabilities_only_advertise_read_only_commands() {
        let result = execute(Path::new("/nonexistent"), "capabilities", None).unwrap();
        assert_eq!(result["schema"], SCHEMA);
        assert_eq!(result["readOnly"], true);
        assert_eq!(result["commands"].as_array().unwrap().len(), 3);
        assert!(!Path::new("/nonexistent").exists());
        assert!(execute(Path::new("."), "start_build_queue", None).is_err());
        assert!(execute(Path::new("."), "delete_handoff_override", None).is_err());
    }

    #[test]
    fn inspect_redacts_private_config_fields_and_reports_live_state_only_if_attached() {
        let workspace = TestWorkspace::new();
        workspace.write("config/regions/austria.json", r#"{"id":"geofabrik-austria","name":"Austria","secrets":"NEVER_EXPOSE","routing":{"enabled":true,"validationMode":"auto","source":{"pbfs":[{"id":"austria"}]}}}"#);
        workspace.write("builds/geofabrik-austria/2026.10.13-manifest.json", r#"{"regionId":"geofabrik-austria","packageVersion":"2026.10.13","builtAtUtc":"2026-10-13T18:00:00Z","credential":"NEVER_EXPOSE","artifact":{"sha256":"abc123","tileCount":42}}"#);
        workspace.write("publication/r2-credentials.json", r#"{"secret_access_key":"NEVER_EXPOSE"}"#);
        let offline = execute(&workspace.0, "inspect", None).unwrap();
        assert_eq!(offline["regions"]["count"], 1);
        assert_eq!(offline["regions"]["items"][0]["id"], "geofabrik-austria");
        assert_eq!(offline["routingBuilds"]["items"][0]["tileCount"], 42);
        assert_eq!(offline["runtime"]["attached"], false);
        assert!(offline["runtime"]["buildStatus"].is_null());
        assert!(!offline.to_string().contains("NEVER_EXPOSE"));
        let live = execute(&workspace.0, "inspect", Some(json!({"running":true,"stage":"Building"}))).unwrap();
        assert_eq!(live["runtime"]["attached"], true);
        assert_eq!(live["runtime"]["buildStatus"]["running"], true);
    }

    #[test]
    fn headless_inspection_does_not_create_workspace() {
        let missing = std::env::temp_dir().join(format!("roadpilot-inspection-absent-{}", std::process::id()));
        // Even an absent workspace returns a bounded, honest empty inventory.
        let output = execute(&missing.join("no-such-workspace"), "inspect", None).unwrap();
        assert_eq!(output["workspacePresent"], false);
        assert_eq!(output["regions"]["count"], 0);
        assert!(!missing.join("no-such-workspace").exists());
    }
}
