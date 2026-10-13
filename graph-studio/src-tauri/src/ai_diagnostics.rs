//! M2 read-only diagnostic summaries and sanitized, build-time outcome records.
//! The inspector never starts processes, replays Valhalla, or exposes raw logs.
use serde_json::{json, Value};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

const SCHEMA: &str = "roadpilot.graph-studio.ai-diagnostics.v1";
const OUTCOME_SCHEMA: &str = "roadpilot.graph-studio.build-outcome.v1";
const MAX_JSON_BYTES: u64 = 2 * 1024 * 1024;
const MAX_DIRS: usize = 100;
const MAX_FILES: usize = 200;
const MAX_REPORTS: usize = 30;
const MAX_WARNINGS: usize = 12;

fn warning(warnings: &mut Vec<&'static str>, value: &'static str) {
    if warnings.len() < MAX_WARNINGS && !warnings.contains(&value) {
        warnings.push(value);
    }
}

fn token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 96
        && value.bytes().all(|c| c.is_ascii_alphanumeric() || matches!(c, b'.' | b'-' | b'_'))
        && value != "." && value != ".."
}

fn field(value: &Value, pointer: &str) -> Option<String> {
    value.pointer(pointer).and_then(Value::as_str)
        .filter(|s| token(s))
        .map(str::to_owned)
}

fn fingerprint(value: &Value, pointer: &str) -> Option<String> {
    let fingerprint = value.pointer(pointer).and_then(Value::as_str)?;
    let hex = fingerprint.strip_prefix("sha256:")?;
    if hex.len() == 64 && hex.bytes().all(|b| b.is_ascii_hexdigit()) {
        Some(fingerprint.to_owned())
    } else {
        None
    }
}

fn timestamp(value: &Value, pointer: &str) -> Option<String> {
    let s = value.pointer(pointer).and_then(Value::as_str)?;
    if (20..=40).contains(&s.len()) && s.as_bytes().get(4) == Some(&b'-')
        && s.as_bytes().get(7) == Some(&b'-')
        && s.as_bytes().get(10) == Some(&b'T')
        && s.bytes().all(|b| b.is_ascii_digit() || matches!(b, b'-' | b':' | b'T' | b'Z' | b'+' | b'.'))
    {
        Some(s.to_owned())
    } else {
        None
    }
}

fn is_regular_file(path: &Path) -> bool {
    fs::symlink_metadata(path).map(|m| m.file_type().is_file()).unwrap_or(false)
}

fn read_json(path: &Path, warnings: &mut Vec<&'static str>) -> Option<Value> {
    let metadata = fs::symlink_metadata(path).ok()?;
    if !metadata.file_type().is_file() || metadata.len() > MAX_JSON_BYTES {
        warning(warnings, "Skipped unsafe or oversized diagnostic JSON.");
        return None;
    }
    match fs::read_to_string(path).ok().and_then(|s| serde_json::from_str(&s).ok()) {
        Some(value) => Some(value),
        None => {
            warning(warnings, "Skipped unreadable or invalid diagnostic JSON.");
            None
        }
    }
}

fn dirs(root: &Path, warnings: &mut Vec<&'static str>) -> Vec<PathBuf> {
    if !root.exists() { return Vec::new(); }
    if fs::symlink_metadata(root).map(|m| !m.file_type().is_dir()).unwrap_or(true) {
        warning(warnings, "Skipped unsafe inventory directory.");
        return Vec::new();
    }
    let Ok(entries) = fs::read_dir(root) else {
        warning(warnings, "Could not read inventory directory.");
        return Vec::new();
    };
    let mut items: Vec<_> = entries.filter_map(Result::ok)
        .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
        .map(|e| e.path()).collect();
    items.sort();
    if items.len() > MAX_DIRS {
        items.truncate(MAX_DIRS);
        warning(warnings, "Inventory directory limit reached.");
    }
    items
}

fn files(root: &Path, suffix: &str, warnings: &mut Vec<&'static str>) -> Vec<PathBuf> {
    if !root.exists() { return Vec::new(); }
    if fs::symlink_metadata(root).map(|m| !m.file_type().is_dir()).unwrap_or(true) {
        warning(warnings, "Skipped unsafe inventory directory.");
        return Vec::new();
    }
    let Ok(entries) = fs::read_dir(root) else {
        warning(warnings, "Could not read inventory directory.");
        return Vec::new();
    };
    let mut items: Vec<_> = entries.filter_map(Result::ok)
        .filter(|e| e.file_type().map(|t| t.is_file()).unwrap_or(false))
        .filter(|e| e.file_name().to_string_lossy().ends_with(suffix))
        .map(|e| e.path()).collect();
    items.sort();
    if items.len() > MAX_FILES {
        items.truncate(MAX_FILES);
        warning(warnings, "Inventory file limit reached.");
    }
    items
}

fn route_evidence(manifest: &Value) -> Value {
    let Some(routes) = manifest.pointer("/validation/routes").and_then(Value::as_array) else {
        return json!({"status":"not_recorded", "routeCount":0, "borderCount":0, "interiorCount":0, "failedCount":0, "replayed":false});
    };
    let mut border = 0usize;
    let mut interior = 0usize;
    let mut failed = 0usize;
    let mut unknown = 0usize;
    for route in routes {
        match route.get("kind").and_then(Value::as_str) {
            Some("border") => border += 1,
            Some("interior") => interior += 1,
            _ => unknown += 1,
        }
        match route.get("passed").and_then(Value::as_bool) {
            Some(true) => (),
            Some(false) => failed += 1,
            None => unknown += 1,
        }
    }
    let status = if routes.is_empty() { "not_recorded" }
        else if failed != 0 { "recorded_failure" }
        else if unknown != 0 { "incomplete_record" }
        else { "recorded_pass" };
    json!({
        "status": status, "routeCount":routes.len(), "borderCount":border,
        "interiorCount":interior, "failedCount":failed,
        "replayed":false,
        "evidenceSource":"retained_routing_manifest"
    })
}

fn artifact_present(manifest_path: &Path, value: &Value) -> bool {
    let Some(name) = field(value, "/artifact/fileName") else { return false };
    manifest_path.parent().is_some_and(|dir| is_regular_file(&dir.join(name)))
}

fn routing_validation(workspace: &Path, warnings: &mut Vec<&'static str>) -> Value {
    let mut items = Vec::new();
    let root = workspace.join("builds");
    for dir in dirs(&root, warnings) {
        for path in files(&dir, "-manifest.json", warnings) {
            if items.len() >= MAX_FILES {
                warning(warnings, "Routing validation result limit reached.");
                break;
            }
            let Some(v) = read_json(&path, warnings) else { continue };
            if v.get("schema").and_then(Value::as_str) != Some("roadpilot-routing-pack") {
                continue;
            }
            items.push(json!({
                "regionId":field(&v, "/regionId"),
                "packageVersion":field(&v, "/packageVersion"),
                "builtAtUtc":timestamp(&v,"/builtAtUtc"),
                "valhallaVersion":field(&v, "/valhallaVersion"),
                "artifactPresent":artifact_present(&path,&v),
                "graphFingerprint":fingerprint(&v, "/graphFingerprint"),
                "routeValidation":route_evidence(&v)
            }));
        }
        if items.len() >= MAX_FILES { break; }
    }
    items.sort_by(|a,b| b["builtAtUtc"].as_str().cmp(&a["builtAtUtc"].as_str()));
    json!({
        "count":items.len(), "items":items,
        "note":"Recorded Valhalla routing results from retained manifests, not independently replayed or checksum-verified."
    })
}

fn safe_number(obj: &Value, pointer: &str) -> Option<u64> {
    obj.pointer(pointer).and_then(Value::as_u64)
}

fn report_summary(value: &Value) -> Option<Value> {
    if value.get("schema").and_then(Value::as_str) != Some("roadpilot.border-diagnostics") {
        return None;
    }
    let selected = value.get("selectedValidation").filter(|v| v.is_object());
    let probes = selected.and_then(|s| s.get("probes")).and_then(Value::as_object);
    let (probe_count, passed_probes) = probes.map_or((0,0), |p| {
        (p.len(), p.values().filter(|v| v.get("passed").and_then(Value::as_bool) == Some(true)).count())
    });
    let proof_state = match selected.and_then(|s| s.get("passed")).and_then(Value::as_bool) {
        Some(true) => "recorded_pass",
        Some(false) => "recorded_failure",
        None => "not_attached",
    };
    let road = value.get("roadDiff").unwrap_or(&Value::Null);
    Some(json!({
        "regionA":field(value,"/regionA"),
        "regionB":field(value,"/regionB"),
        "generatedAtEpochMs":safe_number(value,"/generatedAtEpochMs"),
        "graphA": {
            "regionId":field(value,"/graphA/regionId"),
            "packageVersion":field(value,"/graphA/packageVersion"),
            "graphFingerprint":fingerprint(value,"/graphA/graphFingerprint")
        },
        "graphB": {
            "regionId":field(value,"/graphB/regionId"),
            "packageVersion":field(value,"/graphB/packageVersion"),
            "graphFingerprint":fingerprint(value,"/graphB/graphFingerprint")
        },
        "selectedCrossing": {
            "status":proof_state,
            "probeCount":probe_count,
            "passedProbes":passed_probes,
            "replayed":false
        },
        "roadDiff":{
            "commonWays":safe_number(road,"/commonWays"),
            "aOnlyWays":safe_number(road,"/aOnlyWays"),
            "bOnlyWays":safe_number(road,"/bOnlyWays"),
            "loadedEdgesA":safe_number(road,"/loadedEdgesA"),
            "loadedEdgesB":safe_number(road,"/loadedEdgesB")
        }
    }))
}

fn border_reports(workspace: &Path, warnings: &mut Vec<&'static str>) -> Value {
    let mut reports: Vec<_> = files(&workspace.join("reports"), ".json", warnings)
        .into_iter()
        .filter_map(|path| read_json(&path, warnings))
        .filter_map(|v| report_summary(&v))
        .collect();
    reports.sort_by(|a,b| b["generatedAtEpochMs"].as_u64().cmp(&a["generatedAtEpochMs"].as_u64()));
    let scanned = reports.len();
    reports.truncate(MAX_REPORTS);
    json!({
        "count":reports.len(),
        "truncated":scanned > MAX_REPORTS,
        "items":reports,
        "note":"Summaries of existing exported reports only. They may refer to stale graph builds; no Valhalla probe was run."
    })
}

fn approved_stage(stage: &str) -> &'static str {
    match stage {
        "Starting build queue" => "starting",
        "Preparing regional build" => "preparing",
        "Downloading Geofabrik sources" => "downloading",
        "Merging regional OSM sources" => "merging",
        "Clipping buffered regional source" => "extracting",
        "Checking OSM reference integrity" => "checking_references",
        "Building timezone database" => "timezones",
        "Building administrative database" => "administrative",
        "Building Valhalla graph tiles" => "valhalla_tiles",
        "Packing Valhalla tile extract" => "packing",
        "Validating routes" => "route_validation",
        "Finalizing package" => "finalizing",
        "Validating completed package" => "package_validation",
        "Building retained visual package" | "Building visual PMTiles" => "visual_build",
        "Validating visual road coverage" => "visual_coverage",
        "Retaining visual package" => "visual_retention",
        _ => "unknown",
    }
}

fn classify(stage: &str, outcome: &str, error: Option<&str>) -> &'static str {
    if outcome == "cancelled" { return "cancelled"; }
    if outcome == "succeeded" { return "none"; }
    let msg = error.unwrap_or("").to_ascii_lowercase();
    if msg.contains("node id twice") || msg.contains("way id twice") {
        return "osm_duplicate_objects";
    }
    if msg.contains("no unvalidated routing package") || msg.contains("valhalla-proven") ||
        msg.contains("routing pack validation failed") {
        return "route_proof_or_pack_validation";
    }
    match approved_stage(stage) {
        "downloading" => "source_download",
        "merging" => "osm_merge",
        "extracting" => "osm_extract",
        "checking_references" => "osm_reference_integrity",
        "timezones" | "administrative" | "valhalla_tiles" | "packing" => "valhalla_processing",
        "route_validation" | "package_validation" => "route_proof_or_pack_validation",
        "visual_build" | "visual_coverage" | "visual_retention" => "visual_pack",
        _ => "other",
    }
}

/// A side-effect of the *existing build lifecycle*, never of the read-only inspector.
/// Persists only stable enums and identifiers, never subprocess output or error text.
pub fn record_build_outcome(
    workspace: &Path, region_id: Option<&str>, version: &str, stage: &str,
    outcome: &str, error: Option<&str>
) -> Result<(), String> {
    if !matches!(outcome, "succeeded" | "failed" | "cancelled") {
        return Err("Invalid build outcome".into());
    }
    let dir = workspace.join("diagnostics");
    if dir.exists() {
        if fs::symlink_metadata(&dir).map(|m| !m.file_type().is_dir()).unwrap_or(true) {
            return Err("Unsafe diagnostics directory".into());
        }
    } else {
        fs::create_dir(&dir).map_err(|_| "Could not create diagnostics directory")?;
    }
    let end = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|_| "Invalid system clock")?.as_millis();
    let payload = json!({
        "schema":OUTCOME_SCHEMA,
        "finishedAtEpochMs":end,
        "regionId":region_id.filter(|s| token(s)),
        "packageVersion":if token(version) { Some(version) } else { None },
        "lastObservedStage":approved_stage(stage),
        "outcome":outcome,
        "failureCategory":classify(stage,outcome,error),
        "errorTextStored":false
    });
    let destination = dir.join("latest-build.json");
    let temporary = dir.join(format!(".latest-build-{}-{end}.tmp", std::process::id()));
    let mut file = OpenOptions::new().write(true).create_new(true).open(&temporary)
        .map_err(|_| "Could not create temporary build outcome")?;
    let write_result = (|| -> std::io::Result<()> {
        file.write_all(payload.to_string().as_bytes())?;
        file.write_all(b"\n")?;
        file.sync_all()
    })();
    if write_result.is_err() {
        let _ = fs::remove_file(&temporary);
        return Err("Could not write sanitized build outcome".into());
    }
    fs::rename(&temporary, destination).map_err(|_| {
        let _ = fs::remove_file(&temporary);
        "Could not commit sanitized build outcome".to_string()
    })?;
    Ok(())
}

fn last_build(workspace: &Path, warnings: &mut Vec<&'static str>) -> Value {
    let path = workspace.join("diagnostics/latest-build.json");
    let Some(v) = read_json(&path, warnings) else { return Value::Null };
    if v.get("schema").and_then(Value::as_str) != Some(OUTCOME_SCHEMA) {
        warning(warnings, "Unrecognized recorded build outcome.");
        return Value::Null;
    }
    let outcome = v.get("outcome").and_then(Value::as_str).unwrap_or("");
    let category = v.get("failureCategory").and_then(Value::as_str).unwrap_or("");
    let allowed_category = matches!(category, "none" | "cancelled" | "osm_duplicate_objects" |
        "route_proof_or_pack_validation" | "source_download" | "osm_merge" |
        "osm_extract" | "osm_reference_integrity" | "valhalla_processing" |
        "visual_pack" | "other");
    if !matches!(outcome, "succeeded" | "failed" | "cancelled") || !allowed_category {
        warning(warnings, "Invalid sanitized build outcome.");
        return Value::Null;
    }
    let stage = v.get("lastObservedStage").and_then(Value::as_str).unwrap_or("unknown");
    let stage = match stage {
        "starting" | "preparing" | "downloading" | "merging" | "extracting" |
        "checking_references" | "timezones" | "administrative" | "valhalla_tiles" |
        "packing" | "route_validation" | "finalizing" | "package_validation" |
        "visual_build" | "visual_coverage" | "visual_retention" => stage,
        _ => "unknown"
    };
    json!({
        "source":"recorded_at_graph_studio_build_completion",
        "finishedAtEpochMs":safe_number(&v,"/finishedAtEpochMs"),
        "regionId":field(&v,"/regionId"),
        "packageVersion":field(&v,"/packageVersion"),
        "lastObservedStage":stage,
        "outcome":outcome,
        "failureCategory":category,
        "rawErrorAvailable":false
    })
}

pub fn diagnose(workspace: &Path, runtime_status: Option<Value>) -> Result<Value, String> {
    // Every input is an allowlisted workspace-relative path, without shell execution.
    // The inspection operation has *zero* filesystem writes.
    let mut warnings = Vec::new();
    let attached = runtime_status.is_some();
    Ok(json!({
        "schema":SCHEMA,
        "command":"diagnose",
        "readOnly":true,
        "workspacePresent":workspace.is_dir(),
        "runtime":{
            "attached":attached,
            "buildStatus":runtime_status,
            "note":if attached { "Live process snapshot. Raw failures are deliberately omitted." }
                  else { "Headless mode: live build/GUI state is unknown." }
        },
        "lastRecordedBuild":last_build(workspace,&mut warnings),
        "routingValidation":routing_validation(workspace,&mut warnings),
        "borderReports":border_reports(workspace,&mut warnings),
        "warnings":warnings,
        "limitations":[
            "A historical successful manifest is not a freshly rerun Valhalla proof.",
            "A border report is a prior export and may be stale for current graph fingerprints.",
            "Only builds completed after M2 record sanitized outcome metadata; raw historical failures cannot be reconstructed.",
            "No new Valhalla routes, integrity hashes, disk writes, builds, publication or destructive actions."
        ]
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Workspace(PathBuf);
    impl Workspace {
        fn new() -> Self {
            let n = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let dir = std::env::temp_dir().join(format!("roadpilot-ai-m2-{}-{n}",std::process::id()));
            fs::create_dir_all(&dir).unwrap();
            Self(dir)
        }
        fn write(&self, name: &str, value: &str) {
            let path = self.0.join(name);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path,value).unwrap();
        }
    }
    impl Drop for Workspace { fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); } }

    #[test]
    fn retained_valhalla_proof_is_only_reported_as_recorded() {
        let w=Workspace::new();
        w.write("builds/austria/test-manifest.json", r#"{"schema":"roadpilot-routing-pack","regionId":"austria","packageVersion":"2026.10.13","builtAtUtc":"2026-10-13T00:00:00Z","graphFingerprint":"sha256:abc","valhallaVersion":"3.6.3","artifact":{"fileName":"test.tar"},"validation":{"routes":[{"kind":"border","passed":true},{"kind":"interior","passed":true}]}, "rawSecret":"SECRET_DO_NOT_EXPOSE"}"#);
        let v=diagnose(&w.0,None).unwrap();
        assert_eq!(v["routingValidation"]["count"],1);
        assert_eq!(v["routingValidation"]["items"][0]["routeValidation"]["status"],"recorded_pass");
        assert_eq!(v["routingValidation"]["items"][0]["routeValidation"]["borderCount"],1);
        assert_eq!(v["routingValidation"]["items"][0]["routeValidation"]["replayed"],false);
        assert_eq!(v["routingValidation"]["items"][0]["artifactPresent"],false);
        assert_eq!(v["runtime"]["attached"],false);
        assert!(!v.to_string().contains("SECRET_DO_NOT_EXPOSE"));
    }

    #[test]
    fn empty_and_failed_route_evidence_cannot_be_called_success() {
        let no_routes=json!({"validation":{"routes":[]}});
        let failed=json!({"validation":{"routes":[{"kind":"border","passed":false}]}});
        let unknown=json!({"validation":{"routes":[{"kind":"interior"}]}});
        assert_eq!(route_evidence(&no_routes)["status"],"not_recorded");
        assert_eq!(route_evidence(&failed)["status"],"recorded_failure");
        assert_eq!(route_evidence(&unknown)["status"],"incomplete_record");
    }

    #[test]
    fn exported_border_report_only_exposes_bounded_fields() {
        let w=Workspace::new();
        w.write("reports/a.json", r#"{"schema":"roadpilot.border-diagnostics","regionA":"austria","regionB":"oberbayern","generatedAtEpochMs":100,"selectedValidation":{"passed":false,"probes":{"one":{"passed":true,"error":"PRIVATE_SECRET"},"two":{"passed":false,"error":"PRIVATE_SECRET"}}},"roadDiff":{"commonWays":8,"aOnlyWays":2},"handoffs":{"notableHandoffs":[{"private":"PRIVATE_SECRET"}]}}"#);
        let v=diagnose(&w.0,None).unwrap();
        assert_eq!(v["borderReports"]["count"],1);
        assert_eq!(v["borderReports"]["items"][0]["selectedCrossing"]["status"],"recorded_failure");
        assert_eq!(v["borderReports"]["items"][0]["selectedCrossing"]["passedProbes"],1);
        assert_eq!(v["borderReports"]["items"][0]["roadDiff"]["commonWays"],8);
        assert!(!v.to_string().contains("PRIVATE_SECRET"));
    }

    #[test]
    fn sanitized_failure_outcome_never_persists_raw_error() {
        let w=Workspace::new();
        record_build_outcome(&w.0,Some("austria"),"test-v1","Clipping buffered regional source",
            "failed",Some("Node ID twice in input /private/secret=PRIVATE_SECRET")).unwrap();
        let on_disk=fs::read_to_string(w.0.join("diagnostics/latest-build.json")).unwrap();
        assert!(!on_disk.contains("PRIVATE_SECRET"));
        assert!(!on_disk.contains("/private/"));
        let v=diagnose(&w.0,None).unwrap();
        assert_eq!(v["lastRecordedBuild"]["outcome"],"failed");
        assert_eq!(v["lastRecordedBuild"]["failureCategory"],"osm_duplicate_objects");
        assert_eq!(v["lastRecordedBuild"]["lastObservedStage"],"extracting");
        assert!(!v.to_string().contains("PRIVATE_SECRET"));
    }

    #[test]
    fn diagnose_unknown_workspace_is_read_only() {
        let w=Workspace::new();
        let missing=w.0.join("does-not-exist");
        let v=diagnose(&missing,None).unwrap();
        assert_eq!(v["workspacePresent"],false);
        assert_eq!(v["lastRecordedBuild"],Value::Null);
        assert!(!missing.exists());
    }

    #[cfg(unix)]
    #[test]
    fn diagnostic_symlinks_cannot_escape_workspace() {
        use std::os::unix::fs::symlink;
        let w=Workspace::new();
        let outside=Workspace::new();
        outside.write("private.json",r#"{"schema":"roadpilot.border-diagnostics","regionA":"private","secrets":"PRIVATE_SECRET"}"#);
        symlink(&outside.0,w.0.join("reports")).unwrap();
        let v=diagnose(&w.0,None).unwrap();
        assert_eq!(v["borderReports"]["count"],0);
        assert!(!v.to_string().contains("PRIVATE_SECRET"));
    }
}
