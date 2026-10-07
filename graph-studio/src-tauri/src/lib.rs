use serde::Serialize;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    env,
    fs,
    io::{BufRead, BufReader},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Debug, Clone, Serialize)]
struct Coverage {
    min_lat: f64,
    max_lat: f64,
    min_lng: f64,
    max_lng: f64,
}

#[derive(Debug, Clone, Serialize)]
struct RegionSummary {
    id: String,
    name: String,
    border_buffer_km: f64,
    expected_valhalla_version: String,
    source_ids: Vec<String>,
    coverage: Option<Coverage>,
}

#[derive(Debug, Clone, Serialize)]
struct ToolStatus {
    name: String,
    available: bool,
    detail: String,
}

#[derive(Debug, Clone, Serialize)]
struct ToolchainStatus {
    ready: bool,
    tools: Vec<ToolStatus>,
}

#[derive(Debug, Clone, Serialize)]
struct SystemStats {
    logical_cpus: usize,
    load_1m: f64,
    memory_used_bytes: u64,
    memory_total_bytes: u64,
    disk_free_bytes: Option<u64>,
    temperature_c: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
struct BuildStatus {
    running: bool,
    current_region: Option<String>,
    queue: Vec<String>,
    stage: String,
    started_at_epoch_ms: Option<u128>,
    last_error: Option<String>,
}

impl Default for BuildStatus {
    fn default() -> Self {
        Self {
            running: false,
            current_region: None,
            queue: Vec::new(),
            stage: "Idle".into(),
            started_at_epoch_ms: None,
            last_error: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct BuildArtifact {
    region_id: String,
    version: String,
    built_at_utc: String,
    artifact_file: String,
    size_bytes: u64,
    sha256: String,
    tile_count: u64,
    manifest_path: String,
    graph_index_path: Option<String>,
    graph_tile_fingerprint: Option<String>,
    internal_fingerprint: Option<String>,
    boundary_fingerprints: Value,
}

#[derive(Debug, Clone, Serialize)]
struct BuildLog {
    line: String,
}

#[derive(Clone)]
struct BuildState {
    status: Arc<Mutex<BuildStatus>>,
    cancel: Arc<AtomicBool>,
    current_pid: Arc<Mutex<Option<u32>>>,
}

impl Default for BuildState {
    fn default() -> Self {
        Self {
            status: Arc::new(Mutex::new(BuildStatus::default())),
            cancel: Arc::new(AtomicBool::new(false)),
            current_pid: Arc::new(Mutex::new(None)),
        }
    }
}

fn now_epoch_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn safe_token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 96
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'))
}

fn emit_log(app: &AppHandle, line: impl Into<String>) {
    let _ = app.emit(
        "graph-studio://build-log",
        BuildLog { line: line.into() },
    );
}

fn emit_status(app: &AppHandle, state: &BuildState) {
    let snapshot = state.status.lock().expect("build status poisoned").clone();
    let _ = app.emit("graph-studio://build-status", snapshot);
}

fn set_stage(app: &AppHandle, state: &BuildState, stage: impl Into<String>) {
    state.status.lock().expect("build status poisoned").stage = stage.into();
    emit_status(app, state);
}

fn normalize_process_path() {
    let home = env::var("HOME").unwrap_or_default();
    let current = env::var_os("PATH").unwrap_or_default();
    let mut paths: Vec<PathBuf> = env::split_paths(&current).collect();
    for candidate in [
        "/usr/local/bin".to_string(),
        "/usr/bin".to_string(),
        "/bin".to_string(),
        format!("{home}/.local/bin"),
        format!("{home}/.cargo/bin"),
    ] {
        let p = PathBuf::from(candidate);
        if !paths.contains(&p) {
            paths.push(p);
        }
    }
    if let Ok(joined) = env::join_paths(paths) {
        env::set_var("PATH", joined);
    }
}

fn executable_path(name: &str) -> Option<PathBuf> {
    env::var_os("PATH").and_then(|path| {
        env::split_paths(&path)
            .map(|dir| dir.join(name))
            .find(|candidate| candidate.is_file())
    })
}

fn pipeline_root(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(override_path) = env::var("ROADPILOT_PIPELINE_ROOT") {
        let path = PathBuf::from(override_path);
        if path.join("config/regions").is_dir() && path.join("tools").is_dir() {
            return Ok(path);
        }
    }

    let bundled = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Could not resolve Graph Studio resources: {e}"))?
        .join("pipeline");
    if bundled.join("config/regions").is_dir() {
        return Ok(bundled);
    }

    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|e| format!("Could not resolve development pipeline root: {e}"))?;
    if dev.join("config/regions").is_dir() {
        return Ok(dev);
    }

    Err("RoadPilot offline-data pipeline resources were not found.".into())
}

fn workspace_root(app: &AppHandle) -> Result<PathBuf, String> {
    let root = app
        .path()
        .home_dir()
        .map_err(|e| format!("Could not resolve home directory: {e}"))?
        .join("RoadPilotGraphStudio");
    fs::create_dir_all(&root).map_err(|e| format!("Could not create workspace: {e}"))?;
    Ok(root)
}

fn region_config_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let destination = workspace_root(app)?.join("config/regions");
    fs::create_dir_all(&destination)
        .map_err(|e| format!("Could not create writable region config directory: {e}"))?;

    let bundled = pipeline_root(app)?.join("config/regions");
    if bundled.is_dir() {
        for entry in fs::read_dir(&bundled)
            .map_err(|e| format!("Could not read bundled region configs: {e}"))?
            .flatten()
        {
            let source = entry.path();
            if source.extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let Some(file_name) = source.file_name() else {
                continue;
            };
            let target = destination.join(file_name);
            if !target.exists() {
                fs::copy(&source, &target).map_err(|e| {
                    format!(
                        "Could not seed writable region config {}: {e}",
                        target.display()
                    )
                })?;
            }
        }
    }
    Ok(destination)
}

fn geofabrik_cache_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = workspace_root(app)?.join("catalog");
    fs::create_dir_all(&path)
        .map_err(|e| format!("Could not create Geofabrik catalog cache: {e}"))?;
    Ok(path)
}

fn work_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = workspace_root(app)?.join("work");
    fs::create_dir_all(&path).map_err(|e| format!("Could not create work directory: {e}"))?;
    Ok(path)
}

fn dist_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = workspace_root(app)?.join("builds");
    fs::create_dir_all(&path).map_err(|e| format!("Could not create build directory: {e}"))?;
    Ok(path)
}

fn python_env_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_cache_dir()
        .map_err(|e| format!("Could not resolve app cache: {e}"))?
        .join("python-env");
    fs::create_dir_all(path.parent().unwrap_or(Path::new(".")))
        .map_err(|e| format!("Could not create app cache: {e}"))?;
    Ok(path)
}

fn command_output(command: &str, args: &[&str]) -> Result<String, String> {
    let output = Command::new(command)
        .args(args)
        .output()
        .map_err(|e| format!("Could not run {command}: {e}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn ensure_python_env(app: &AppHandle) -> Result<PathBuf, String> {
    let env_dir = python_env_dir(app)?;
    let python = env_dir.join("bin/python");
    let pipeline = pipeline_root(app)?;
    let requirements = pipeline.join("requirements-routing.txt");

    if !python.is_file() {
        emit_log(app, "Preparing Graph Studio Python environment…");
        let status = Command::new("python3")
            .args(["-m", "venv"])
            .arg(&env_dir)
            .status()
            .map_err(|e| format!("Could not create Python virtual environment: {e}"))?;
        if !status.success() {
            return Err(
                "python3 -m venv failed. Install the python3-venv package and retry.".into(),
            );
        }
    }

    let marker = env_dir.join(".roadpilot-requirements-ready");
    let requirements_stamp = fs::metadata(&requirements)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_secs().to_string())
        .unwrap_or_default();
    let marker_value = fs::read_to_string(&marker).unwrap_or_default();

    if marker_value.trim() != requirements_stamp {
        emit_log(app, "Installing/updating Graph Studio Python dependencies…");
        let status = Command::new(&python)
            .args(["-m", "pip", "install", "--upgrade", "pip"])
            .status()
            .map_err(|e| format!("Could not update pip: {e}"))?;
        if !status.success() {
            return Err("pip upgrade failed.".into());
        }

        let status = Command::new(&python)
            .args(["-m", "pip", "install", "-r"])
            .arg(&requirements)
            .status()
            .map_err(|e| format!("Could not install Python requirements: {e}"))?;
        if !status.success() {
            return Err("Installing Graph Studio Python requirements failed.".into());
        }
        fs::write(&marker, &requirements_stamp)
            .map_err(|e| format!("Could not write Python environment marker: {e}"))?;
    }

    Ok(python)
}

#[tauri::command]
fn list_regions(app: AppHandle) -> Result<Vec<RegionSummary>, String> {
    let root = region_config_dir(&app)?;
    let mut entries: Vec<PathBuf> = fs::read_dir(root)
        .map_err(|e| format!("Could not read region configs: {e}"))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    entries.sort();

    let mut regions = Vec::new();
    for path in entries {
        let text = fs::read_to_string(&path)
            .map_err(|e| format!("Could not read {}: {e}", path.display()))?;
        let value: Value = serde_json::from_str(&text)
            .map_err(|e| format!("Could not parse {}: {e}", path.display()))?;
        let Some(routing) = value.get("routing") else {
            continue;
        };
        if routing.get("enabled").and_then(Value::as_bool) != Some(true) {
            continue;
        }

        let source_ids = routing
            .pointer("/source/pbfs")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|item| item.get("id").and_then(Value::as_str))
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();

        let coverage = value
            .pointer("/routing/coverage")
            .or_else(|| value.pointer("/overture/coverage"))
            .and_then(|c| {
            Some(Coverage {
                min_lat: c.get("minLat")?.as_f64()?,
                max_lat: c.get("maxLat")?.as_f64()?,
                min_lng: c.get("minLng")?.as_f64()?,
                max_lng: c.get("maxLng")?.as_f64()?,
            })
        });

        regions.push(RegionSummary {
            id: value.get("id").and_then(Value::as_str).unwrap_or_default().to_string(),
            name: value
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or("Unnamed region")
                .to_string(),
            border_buffer_km: routing
                .get("borderBufferKm")
                .and_then(Value::as_f64)
                .unwrap_or(0.0),
            expected_valhalla_version: routing
                .get("expectedValhallaVersion")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .to_string(),
            source_ids,
            coverage,
        });
    }
    Ok(regions)
}

fn run_graph_studio_region_helper(
    app: &AppHandle,
    arguments: &[String],
) -> Result<Value, String> {
    let python = ensure_python_env(app)?;
    let pipeline = pipeline_root(app)?;
    let script = pipeline.join("tools/graph_studio_regions.py");
    if !script.is_file() {
        return Err(format!(
            "Graph Studio region helper is missing: {}",
            script.display()
        ));
    }

    let output = Command::new(python)
        .arg(script)
        .args(arguments)
        .output()
        .map_err(|e| format!("Could not run Graph Studio region helper: {e}"))?;
    if !output.status.success() {
        let error = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if error.is_empty() {
            "Graph Studio region helper failed.".into()
        } else {
            error
        });
    }
    serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Region helper returned invalid JSON: {e}"))
}

#[tauri::command]
fn geofabrik_catalog(app: AppHandle, refresh: bool) -> Result<Value, String> {
    let cache = geofabrik_cache_dir(&app)?;
    let mut args = vec![
        "--cache-dir".to_string(),
        cache.display().to_string(),
    ];
    if refresh {
        args.push("--refresh".into());
    }
    args.push("catalog".into());
    run_graph_studio_region_helper(&app, &args)
}

#[tauri::command]
fn preview_region(
    app: AppHandle,
    geofabrik_id: String,
    buffer_km: f64,
    refresh: bool,
) -> Result<Value, String> {
    if geofabrik_id.is_empty() || geofabrik_id.len() > 160 {
        return Err("Invalid Geofabrik region id.".into());
    }
    if !buffer_km.is_finite() || !(0.0..=100.0).contains(&buffer_km) || buffer_km == 0.0 {
        return Err("Border buffer must be greater than 0 and no more than 100 km.".into());
    }
    let cache = geofabrik_cache_dir(&app)?;
    let mut args = vec![
        "--cache-dir".to_string(),
        cache.display().to_string(),
    ];
    if refresh {
        args.push("--refresh".into());
    }
    args.extend([
        "preview".into(),
        "--geofabrik-id".into(),
        geofabrik_id,
        "--buffer-km".into(),
        buffer_km.to_string(),
    ]);
    run_graph_studio_region_helper(&app, &args)
}

#[tauri::command]
fn load_region_config(app: AppHandle, region_id: String) -> Result<Value, String> {
    if !safe_token(&region_id) {
        return Err("Invalid RoadPilot region id.".into());
    }
    let path = region_config_dir(&app)?.join(format!("{region_id}.json"));
    let text = fs::read_to_string(&path)
        .map_err(|e| format!("Could not read {}: {e}", path.display()))?;
    serde_json::from_str(&text)
        .map_err(|e| format!("Could not parse {}: {e}", path.display()))
}

#[tauri::command]
fn save_region_config(
    app: AppHandle,
    config: Value,
    refresh_geometry: bool,
) -> Result<Value, String> {
    let region_id = config
        .get("id")
        .and_then(Value::as_str)
        .ok_or("Region config id is required.")?
        .to_string();
    if !safe_token(&region_id) {
        return Err("RoadPilot region id contains unsupported characters.".into());
    }

    let root = region_config_dir(&app)?;
    let destination = root.join(format!("{region_id}.json"));
    let temporary = root.join(format!(".{region_id}.json.tmp"));
    let serialized = serde_json::to_string_pretty(&config)
        .map_err(|e| format!("Could not serialize region config: {e}"))?;
    fs::write(&temporary, format!("{serialized}\n"))
        .map_err(|e| format!("Could not write temporary region config: {e}"))?;

    let validate_result = (|| -> Result<(), String> {
        let python = ensure_python_env(&app)?;
        let pipeline = pipeline_root(&app)?;
        let structural = Command::new(&python)
            .arg(pipeline.join("tools/validate_region_config.py"))
            .arg("--config")
            .arg(&temporary)
            .output()
            .map_err(|e| format!("Could not validate region config: {e}"))?;
        if !structural.status.success() {
            return Err(String::from_utf8_lossy(&structural.stderr).trim().to_string());
        }

        let cache = geofabrik_cache_dir(&app)?;
        let mut args = vec![
            "--cache-dir".to_string(),
            cache.display().to_string(),
        ];
        if refresh_geometry {
            args.push("--refresh".into());
        }
        args.extend([
            "validate-config".into(),
            "--config".into(),
            temporary.display().to_string(),
        ]);
        run_graph_studio_region_helper(&app, &args)?;
        Ok(())
    })();

    if let Err(error) = validate_result {
        let _ = fs::remove_file(&temporary);
        return Err(if error.is_empty() {
            "Region config validation failed.".into()
        } else {
            error
        });
    }

    fs::rename(&temporary, &destination)
        .map_err(|e| format!("Could not activate region config: {e}"))?;
    Ok(config)
}

#[tauri::command]
fn toolchain_status() -> ToolchainStatus {
    let names = [
        "python3",
        "osmium",
        "valhalla_build_config",
        "valhalla_build_timezones",
        "valhalla_build_admins",
        "valhalla_build_tiles",
        "valhalla_build_extract",
        "valhalla_service",
    ];
    let mut tools = Vec::new();
    for name in names {
        let path = executable_path(name);
        tools.push(ToolStatus {
            name: name.to_string(),
            available: path.is_some(),
            detail: path
                .map(|p| p.display().to_string())
                .unwrap_or_else(|| "missing".into()),
        });
    }

    let venv_ready = Command::new("python3")
        .args(["-m", "venv", "--help"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false);
    tools.push(ToolStatus {
        name: "python3-venv".into(),
        available: venv_ready,
        detail: if venv_ready { "ready".into() } else { "missing".into() },
    });

    ToolchainStatus {
        ready: tools.iter().all(|tool| tool.available),
        tools,
    }
}

fn parse_meminfo() -> (u64, u64) {
    let text = fs::read_to_string("/proc/meminfo").unwrap_or_default();
    let mut total_kb = 0_u64;
    let mut available_kb = 0_u64;
    for line in text.lines() {
        let mut parts = line.split_whitespace();
        match parts.next() {
            Some("MemTotal:") => total_kb = parts.next().and_then(|v| v.parse().ok()).unwrap_or(0),
            Some("MemAvailable:") => {
                available_kb = parts.next().and_then(|v| v.parse().ok()).unwrap_or(0)
            }
            _ => {}
        }
    }
    let total = total_kb * 1024;
    let available = available_kb * 1024;
    (total.saturating_sub(available), total)
}

fn read_temperature() -> Option<f64> {
    let mut values = Vec::new();
    for root in ["/sys/class/thermal", "/sys/class/hwmon"] {
        let Ok(entries) = fs::read_dir(root) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(children) = fs::read_dir(&path) else {
                continue;
            };
            for child in children.flatten() {
                let file = child.path();
                let name = file.file_name()?.to_string_lossy();
                if !(name == "temp" || (name.starts_with("temp") && name.ends_with("_input"))) {
                    continue;
                }
                if let Ok(raw) = fs::read_to_string(&file) {
                    if let Ok(value) = raw.trim().parse::<f64>() {
                        let celsius = if value > 500.0 { value / 1000.0 } else { value };
                        if (0.0..=130.0).contains(&celsius) {
                            values.push(celsius);
                        }
                    }
                }
            }
        }
    }
    values.into_iter().reduce(f64::max)
}

fn disk_free(path: &Path) -> Option<u64> {
    let output = Command::new("df")
        .arg("-B1")
        .arg(path)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let line = text.lines().nth(1)?;
    line.split_whitespace().nth(3)?.parse().ok()
}

#[tauri::command]
fn system_stats(app: AppHandle) -> Result<SystemStats, String> {
    let logical_cpus = thread::available_parallelism().map(|v| v.get()).unwrap_or(1);
    let load_1m = fs::read_to_string("/proc/loadavg")
        .ok()
        .and_then(|v| v.split_whitespace().next()?.parse().ok())
        .unwrap_or(0.0);
    let (memory_used_bytes, memory_total_bytes) = parse_meminfo();
    let root = workspace_root(&app)?;

    Ok(SystemStats {
        logical_cpus,
        load_1m,
        memory_used_bytes,
        memory_total_bytes,
        disk_free_bytes: disk_free(&root),
        temperature_c: read_temperature(),
    })
}

#[tauri::command]
fn build_status(state: State<'_, BuildState>) -> BuildStatus {
    state.status.lock().expect("build status poisoned").clone()
}

fn stage_for_log(line: &str) -> Option<&'static str> {
    if line.contains("download:") {
        Some("Downloading Geofabrik sources")
    } else if line.contains("osmium merge") {
        Some("Merging regional OSM sources")
    } else if line.contains("osmium extract") {
        Some("Clipping buffered regional source")
    } else if line.contains("osmium check-refs") {
        Some("Checking OSM reference integrity")
    } else if line.contains("valhalla_build_timezones") {
        Some("Building timezone database")
    } else if line.contains("valhalla_build_admins") {
        Some("Building administrative database")
    } else if line.contains("valhalla_build_tiles") {
        Some("Building Valhalla graph tiles")
    } else if line.contains("valhalla_build_extract") {
        Some("Packing Valhalla tile extract")
    } else if line.contains("validation passed:") {
        Some("Validating routes")
    } else if line.starts_with("built:") {
        Some("Finalizing package")
    } else {
        None
    }
}

fn run_process_streaming(
    app: &AppHandle,
    state: &BuildState,
    mut command: Command,
) -> Result<(), String> {
    command.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = command
        .spawn()
        .map_err(|e| format!("Could not start build process: {e}"))?;
    *state.current_pid.lock().expect("pid lock poisoned") = Some(child.id());

    let stdout = child.stdout.take().ok_or("Build stdout was not available.")?;
    let stderr = child.stderr.take().ok_or("Build stderr was not available.")?;
    let (tx, rx) = std::sync::mpsc::channel::<String>();

    let tx_out = tx.clone();
    let out_thread = thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let _ = tx_out.send(line);
        }
    });
    let tx_err = tx.clone();
    let err_thread = thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = tx_err.send(line);
        }
    });
    drop(tx);

    loop {
        match rx.recv_timeout(std::time::Duration::from_millis(150)) {
            Ok(line) => {
                if let Some(stage) = stage_for_log(&line) {
                    set_stage(app, state, stage);
                }
                emit_log(app, line);
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
        }

        if state.cancel.load(Ordering::SeqCst) {
            let _ = Command::new("kill")
                .args(["-TERM", &child.id().to_string()])
                .status();
        }
    }

    let status = child
        .wait()
        .map_err(|e| format!("Could not wait for build process: {e}"))?;
    let _ = out_thread.join();
    let _ = err_thread.join();
    *state.current_pid.lock().expect("pid lock poisoned") = None;

    if state.cancel.load(Ordering::SeqCst) {
        return Err("Build cancelled.".into());
    }
    if !status.success() {
        return Err(format!("Build process exited with {status}."));
    }
    Ok(())
}

fn run_build_queue(
    app: AppHandle,
    state: BuildState,
    region_ids: Vec<String>,
    package_version: String,
    refresh_sources: bool,
) -> Result<(), String> {
    let pipeline = pipeline_root(&app)?;
    let python = ensure_python_env(&app)?;
    let work = work_dir(&app)?;
    let dist = dist_dir(&app)?;

    for (index, region_id) in region_ids.iter().enumerate() {
        if state.cancel.load(Ordering::SeqCst) {
            return Err("Build cancelled.".into());
        }

        {
            let mut snapshot = state.status.lock().expect("build status poisoned");
            snapshot.current_region = Some(region_id.clone());
            snapshot.queue = region_ids[index..].to_vec();
            snapshot.stage = "Preparing regional build".into();
            snapshot.last_error = None;
        }
        emit_status(&app, &state);
        emit_log(
            &app,
            format!("\n=== {} • {} ===", region_id, package_version),
        );

        let config = region_config_dir(&app)?.join(format!("{region_id}.json"));
        if !config.is_file() {
            return Err(format!("Region config does not exist: {}", config.display()));
        }

        let mut command = Command::new(&python);
        command
            .arg(pipeline.join("tools/build_routing_region.py"))
            .arg("--config")
            .arg(config)
            .arg("--package-version")
            .arg(&package_version)
            .arg("--work-dir")
            .arg(&work)
            .arg("--dist-dir")
            .arg(&dist);
        if refresh_sources {
            command.arg("--refresh-sources");
        }
        run_process_streaming(&app, &state, command)?;

        set_stage(&app, &state, "Validating completed package");
        let region_dist = dist.join(region_id);
        let manifest = fs::read_dir(&region_dist)
            .map_err(|e| format!("Could not inspect build output: {e}"))?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .find(|path| {
                path.file_name()
                    .and_then(|name| name.to_str())
                    .map(|name| {
                        name.contains(&package_version) && name.ends_with("-manifest.json")
                    })
                    .unwrap_or(false)
            })
            .ok_or_else(|| format!("No manifest produced for {region_id} {package_version}"))?;

        let status = Command::new(&python)
            .arg(pipeline.join("tools/validate_routing_pack.py"))
            .arg("--manifest")
            .arg(&manifest)
            .status()
            .map_err(|e| format!("Could not validate completed package: {e}"))?;
        if !status.success() {
            return Err(format!("Routing pack validation failed for {region_id}."));
        }

        let cache = work.join("inspector-cache").join(region_id);
        let _ = fs::remove_dir_all(cache);
        emit_log(&app, format!("✓ {region_id} build validated."));
    }

    Ok(())
}

#[tauri::command]
fn start_build_queue(
    app: AppHandle,
    state: State<'_, BuildState>,
    region_ids: Vec<String>,
    package_version: String,
    refresh_sources: bool,
) -> Result<(), String> {
    if region_ids.is_empty() {
        return Err("Select at least one region.".into());
    }
    if !region_ids.iter().all(|id| safe_token(id)) {
        return Err("One or more region ids are invalid.".into());
    }
    if !safe_token(&package_version) {
        return Err("Package version contains unsupported characters.".into());
    }

    let owned = state.inner().clone();
    {
        let mut status = owned.status.lock().expect("build status poisoned");
        if status.running {
            return Err("A graph build is already running.".into());
        }
        *status = BuildStatus {
            running: true,
            current_region: None,
            queue: region_ids.clone(),
            stage: "Starting build queue".into(),
            started_at_epoch_ms: Some(now_epoch_ms()),
            last_error: None,
        };
    }
    owned.cancel.store(false, Ordering::SeqCst);
    emit_status(&app, &owned);

    tauri::async_runtime::spawn_blocking(move || {
        let result = run_build_queue(
            app.clone(),
            owned.clone(),
            region_ids,
            package_version,
            refresh_sources,
        );

        let mut snapshot = owned.status.lock().expect("build status poisoned");
        snapshot.running = false;
        snapshot.current_region = None;
        snapshot.queue.clear();
        match result {
            Ok(()) => {
                snapshot.stage = "Build queue complete".into();
                snapshot.last_error = None;
                emit_log(&app, "✓ Build queue complete.");
            }
            Err(error) => {
                let cancelled = owned.cancel.load(Ordering::SeqCst);
                snapshot.stage = if cancelled {
                    "Build cancelled".into()
                } else {
                    "Build failed".into()
                };
                snapshot.last_error = Some(error.clone());
                emit_log(&app, format!("✗ {error}"));
            }
        }
        owned.cancel.store(false, Ordering::SeqCst);
        drop(snapshot);
        emit_status(&app, &owned);
    });

    Ok(())
}

#[tauri::command]
fn cancel_build(state: State<'_, BuildState>) -> Result<(), String> {
    state.cancel.store(true, Ordering::SeqCst);
    if let Some(pid) = *state.current_pid.lock().expect("pid lock poisoned") {
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status();
    }
    Ok(())
}

#[tauri::command]
fn list_builds(app: AppHandle) -> Result<Vec<BuildArtifact>, String> {
    let root = dist_dir(&app)?;
    let mut result = Vec::new();
    let Ok(regions) = fs::read_dir(root) else {
        return Ok(result);
    };

    for region_dir in regions.flatten().filter(|entry| entry.path().is_dir()) {
        let Ok(files) = fs::read_dir(region_dir.path()) else {
            continue;
        };
        for entry in files.flatten() {
            let path = entry.path();
            let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
                continue;
            };
            if !name.ends_with("-manifest.json") {
                continue;
            }
            let Ok(text) = fs::read_to_string(&path) else {
                continue;
            };
            let Ok(value) = serde_json::from_str::<Value>(&text) else {
                continue;
            };
            let Some(artifact) = value.get("artifact") else {
                continue;
            };
            result.push(BuildArtifact {
                region_id: value
                    .get("regionId")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                version: value
                    .get("packageVersion")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                built_at_utc: value
                    .get("builtAtUtc")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                artifact_file: artifact
                    .get("fileName")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                size_bytes: artifact
                    .get("sizeBytes")
                    .and_then(Value::as_u64)
                    .unwrap_or(0),
                sha256: artifact
                    .get("sha256")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                tile_count: artifact
                    .get("tileCount")
                    .and_then(Value::as_u64)
                    .unwrap_or(0),
                manifest_path: path.display().to_string(),
                graph_index_path: value
                    .pointer("/graphIndex/fileName")
                    .and_then(Value::as_str)
                    .map(|name| path.parent().unwrap_or(Path::new(".")).join(name))
                    .filter(|index_path| index_path.is_file())
                    .map(|index_path| index_path.display().to_string()),
                graph_tile_fingerprint: value
                    .pointer("/graphIndex/graphTileFingerprint")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                internal_fingerprint: value
                    .pointer("/graphIndex/internalFingerprint")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                boundary_fingerprints: value
                    .pointer("/graphIndex/boundaryFingerprints")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
            });
        }
    }

    result.sort_by(|a, b| b.built_at_utc.cmp(&a.built_at_utc));
    Ok(result)
}


fn safe_build_manifest_path(app: &AppHandle, raw: &str) -> Result<PathBuf, String> {
    let requested = PathBuf::from(raw)
        .canonicalize()
        .map_err(|e| format!("Could not resolve build manifest {raw}: {e}"))?;
    let root = dist_dir(app)?
        .canonicalize()
        .map_err(|e| format!("Could not resolve Graph Studio build directory: {e}"))?;
    if !requested.starts_with(&root) || !requested.is_file() {
        return Err("Build manifest is outside the Graph Studio build workspace.".into());
    }
    Ok(requested)
}

fn graph_index_for_manifest(app: &AppHandle, raw: &str) -> Result<Value, String> {
    let manifest_path = safe_build_manifest_path(app, raw)?;
    let text = fs::read_to_string(&manifest_path)
        .map_err(|e| format!("Could not read {}: {e}", manifest_path.display()))?;
    let manifest: Value = serde_json::from_str(&text)
        .map_err(|e| format!("Could not parse {}: {e}", manifest_path.display()))?;
    let index_name = manifest
        .pointer("/graphIndex/fileName")
        .and_then(Value::as_str)
        .ok_or("Selected build predates deterministic graph indexes; rebuild it with current Graph Studio.")?;
    let index_path = manifest_path
        .parent()
        .unwrap_or(Path::new("."))
        .join(index_name);
    let index_text = fs::read_to_string(&index_path)
        .map_err(|e| format!("Could not read graph index {}: {e}", index_path.display()))?;
    let index: Value = serde_json::from_str(&index_text)
        .map_err(|e| format!("Could not parse graph index {}: {e}", index_path.display()))?;
    Ok(json!({"manifest": manifest, "index": index}))
}

fn graph_index_tiles(index: &Value) -> BTreeMap<String, Value> {
    index
        .get("tiles")
        .and_then(Value::as_array)
        .map(|tiles| {
            tiles
                .iter()
                .filter_map(|tile| {
                    let path = tile.get("path")?.as_str()?.to_string();
                    Some((path, tile.clone()))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn graph_index_boundary_fingerprints(index: &Value) -> BTreeMap<String, String> {
    index
        .get("boundaries")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    Some((
                        item.get("sourceId")?.as_str()?.to_string(),
                        item.get("fingerprint")?.as_str()?.to_string(),
                    ))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn tile_boundary_ids(tile: Option<&Value>) -> BTreeSet<String> {
    tile.and_then(|value| value.get("boundaries"))
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn tile_bounds_feature(path: &str, status: &str, boundaries: &BTreeSet<String>, tile: &Value) -> Option<Value> {
    let bounds = tile.get("bounds")?;
    let min_lat = bounds.get("minLat")?.as_f64()?;
    let max_lat = bounds.get("maxLat")?.as_f64()?;
    let min_lng = bounds.get("minLng")?.as_f64()?;
    let max_lng = bounds.get("maxLng")?.as_f64()?;
    Some(json!({
        "type": "Feature",
        "properties": {
            "path": path,
            "status": status,
            "boundaries": boundaries.iter().cloned().collect::<Vec<_>>()
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat]
            ]]
        }
    }))
}

#[tauri::command]
fn compare_build_indexes(
    app: AppHandle,
    manifest_path_a: String,
    manifest_path_b: String,
) -> Result<Value, String> {
    let a = graph_index_for_manifest(&app, &manifest_path_a)?;
    let b = graph_index_for_manifest(&app, &manifest_path_b)?;
    let manifest_a = a.get("manifest").ok_or("Build A manifest was not loaded.")?;
    let manifest_b = b.get("manifest").ok_or("Build B manifest was not loaded.")?;
    let region_a = manifest_a.get("regionId").and_then(Value::as_str).unwrap_or_default();
    let region_b = manifest_b.get("regionId").and_then(Value::as_str).unwrap_or_default();
    if region_a.is_empty() || region_a != region_b {
        return Err("Detailed build comparison requires two builds of the same region.".into());
    }

    let index_a = a.get("index").ok_or("Build A graph index was not loaded.")?;
    let index_b = b.get("index").ok_or("Build B graph index was not loaded.")?;
    let tiles_a = graph_index_tiles(index_a);
    let tiles_b = graph_index_tiles(index_b);
    let paths: BTreeSet<String> = tiles_a.keys().chain(tiles_b.keys()).cloned().collect();

    let mut added_tiles = 0_u64;
    let mut removed_tiles = 0_u64;
    let mut changed_tiles = 0_u64;
    let mut internal_changed_tiles = 0_u64;
    let mut boundary_changed_tiles = 0_u64;
    let mut boundary_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut changed_boundary_features = Vec::new();

    for path in paths {
        let old = tiles_a.get(&path);
        let new = tiles_b.get(&path);
        let old_sha = old.and_then(|tile| tile.get("sha256")).and_then(Value::as_str);
        let new_sha = new.and_then(|tile| tile.get("sha256")).and_then(Value::as_str);
        let status = match (old, new) {
            (None, Some(_)) => {
                added_tiles += 1;
                "added"
            }
            (Some(_), None) => {
                removed_tiles += 1;
                "removed"
            }
            (Some(_), Some(_)) if old_sha != new_sha => {
                changed_tiles += 1;
                "changed"
            }
            _ => continue,
        };

        let old_boundaries = tile_boundary_ids(old);
        let new_boundaries = tile_boundary_ids(new);
        let boundaries: BTreeSet<String> = old_boundaries
            .union(&new_boundaries)
            .cloned()
            .collect();
        if boundaries.is_empty() {
            internal_changed_tiles += 1;
            continue;
        }
        boundary_changed_tiles += 1;
        for boundary in &boundaries {
            *boundary_counts.entry(boundary.clone()).or_insert(0) += 1;
        }
        if let Some(tile) = new.or(old) {
            if let Some(feature) = tile_bounds_feature(&path, status, &boundaries, tile) {
                changed_boundary_features.push(feature);
            }
        }
    }

    let fp_a = graph_index_boundary_fingerprints(index_a);
    let fp_b = graph_index_boundary_fingerprints(index_b);
    let boundary_ids: BTreeSet<String> = fp_a.keys().chain(fp_b.keys()).cloned().collect();
    let boundaries: Vec<Value> = boundary_ids
        .into_iter()
        .map(|source_id| {
            let old = fp_a.get(&source_id).cloned();
            let new = fp_b.get(&source_id).cloned();
            json!({
                "sourceId": source_id,
                "oldFingerprint": old,
                "newFingerprint": new,
                "requiresRefresh": old != new,
                "changedTiles": boundary_counts.get(&source_id).copied().unwrap_or(0)
            })
        })
        .collect();

    Ok(json!({
        "regionId": region_a,
        "versionA": manifest_a.get("packageVersion").cloned().unwrap_or(Value::Null),
        "versionB": manifest_b.get("packageVersion").cloned().unwrap_or(Value::Null),
        "graphTileFingerprintA": index_a.get("graphTileFingerprint").cloned().unwrap_or(Value::Null),
        "graphTileFingerprintB": index_b.get("graphTileFingerprint").cloned().unwrap_or(Value::Null),
        "internalFingerprintA": index_a.get("internalFingerprint").cloned().unwrap_or(Value::Null),
        "internalFingerprintB": index_b.get("internalFingerprint").cloned().unwrap_or(Value::Null),
        "counts": {
            "addedTiles": added_tiles,
            "removedTiles": removed_tiles,
            "changedTiles": changed_tiles,
            "internalChangedTiles": internal_changed_tiles,
            "boundaryChangedTiles": boundary_changed_tiles
        },
        "boundaries": boundaries,
        "changedBoundaryTiles": {
            "type": "FeatureCollection",
            "features": changed_boundary_features
        }
    }))
}

fn latest_graph_identity(app: &AppHandle, region_id: &str) -> Result<Value, String> {
    let root = dist_dir(app)?.join(region_id);
    if !root.is_dir() {
        return Err(format!("No completed local build exists for {region_id}."));
    }

    let mut candidates: Vec<(String, Value)> = Vec::new();
    for entry in fs::read_dir(&root)
        .map_err(|e| format!("Could not inspect {}: {e}", root.display()))?
        .flatten()
    {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
            continue;
        };
        if !name.ends_with("-manifest.json") {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(value) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        if value.get("regionId").and_then(Value::as_str) != Some(region_id) {
            continue;
        }
        let built_at = value
            .get("builtAtUtc")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        candidates.push((built_at, value));
    }
    candidates.sort_by(|a, b| b.0.cmp(&a.0));
    let Some((_, manifest)) = candidates.into_iter().next() else {
        return Err(format!("No routing manifest found for {region_id}."));
    };

    Ok(json!({
        "regionId": region_id,
        "packageVersion": manifest.get("packageVersion").cloned().unwrap_or(Value::Null),
        "builtAtUtc": manifest.get("builtAtUtc").cloned().unwrap_or(Value::Null),
        "graphFingerprint": manifest.get("graphFingerprint").cloned().unwrap_or(Value::Null),
        "primaryGeofabrikId": manifest.pointer("/source/primaryGeofabrikId").cloned().unwrap_or(Value::Null),
        "boundaryFingerprints": manifest.pointer("/graphIndex/boundaryFingerprints").cloned().unwrap_or_else(|| json!({}))
    }))
}

fn handoff_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = workspace_root(app)?.join("handoffs");
    fs::create_dir_all(&path)
        .map_err(|e| format!("Could not create handoff override directory: {e}"))?;
    Ok(path)
}

fn transition_artifact_dirs(app: &AppHandle) -> Result<Vec<PathBuf>, String> {
    let workspace = workspace_root(app)?;
    let transitions = workspace.join("transitions");
    let handoff_imports = workspace.join("imports/handoffs");
    let connectivity = workspace.join("connectivity");
    let connectivity_imports = workspace.join("imports/connectivity");
    let connector_matrices = workspace.join("connector-matrices");
    let connector_matrix_imports = workspace.join("imports/connector-matrices");
    for (path, label) in [
        (&transitions, "transition artifact"),
        (&handoff_imports, "handoff import"),
        (&connectivity, "connectivity artifact"),
        (&connectivity_imports, "connectivity import"),
        (&connector_matrices, "connector matrix"),
        (&connector_matrix_imports, "connector matrix import"),
    ] {
        fs::create_dir_all(path)
            .map_err(|e| format!("Could not create Graph Studio {label} directory: {e}"))?;
    }
    Ok(vec![
        transitions,
        handoff_imports,
        connectivity,
        connectivity_imports,
        connector_matrices,
        connector_matrix_imports,
    ])
}

fn collect_json_files(root: &Path, depth: usize, output: &mut Vec<PathBuf>) {
    if depth == 0 || !root.is_dir() || output.len() >= 1000 {
        return;
    }
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        if output.len() >= 1000 {
            break;
        }
        let path = entry.path();
        let Ok(file_type) = entry.file_type() else {
            continue;
        };
        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_dir() {
            collect_json_files(&path, depth - 1, output);
        } else if file_type.is_file()
            && path.extension().and_then(|value| value.to_str()) == Some("json")
        {
            output.push(path);
        }
    }
}

fn sha256_prefixed(path: &Path) -> Result<String, String> {
    let output = Command::new("sha256sum")
        .arg(path)
        .output()
        .map_err(|e| format!("Could not run sha256sum for {}: {e}", path.display()))?;
    if !output.status.success() {
        return Err(format!(
            "sha256sum failed for {}: {}",
            path.display(),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let digest = stdout.split_whitespace().next().unwrap_or_default();
    if digest.len() != 64 || !digest.chars().all(|ch| ch.is_ascii_hexdigit()) {
        return Err(format!("sha256sum returned an invalid digest for {}", path.display()));
    }
    Ok(format!("sha256:{}", digest.to_ascii_lowercase()))
}

fn connector_inventory_current(document: &Value, current: &Value) -> (bool, Vec<Value>) {
    let graph_matches = document
        .pointer("/graph/graphFingerprint")
        .and_then(Value::as_str)
        == current.get("graphFingerprint").and_then(Value::as_str);
    let mut checks = Vec::new();
    let mut current_all = graph_matches;
    if let Some(sources) = document.get("sourceConnectivity").and_then(Value::as_array) {
        for source in sources {
            let neighbor = source
                .get("neighborPrimaryGeofabrikId")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let bound = source
                .get("regionBoundaryFingerprint")
                .and_then(Value::as_str);
            let live = current
                .pointer("/boundaryFingerprints")
                .and_then(Value::as_object)
                .and_then(|values| values.get(neighbor))
                .and_then(Value::as_str);
            let matches = !neighbor.is_empty() && bound.is_some() && bound == live;
            current_all &= matches;
            checks.push(json!({
                "neighborPrimaryGeofabrikId": neighbor,
                "boundBoundaryFingerprint": bound,
                "currentBoundaryFingerprint": live,
                "matches": matches
            }));
        }
    }
    (current_all, checks)
}

#[tauri::command]
fn inspect_region_connector_matrix(app: AppHandle, region_id: String) -> Result<Value, String> {
    if !safe_token(&region_id) {
        return Err("Invalid region id.".into());
    }
    let current = latest_graph_identity(&app, &region_id)?;
    let mut files = Vec::new();
    for root in transition_artifact_dirs(&app)? {
        collect_json_files(&root, 6, &mut files);
    }
    files.sort();
    files.dedup();

    let mut inventories: Vec<(PathBuf, Value, String, bool, Vec<Value>)> = Vec::new();
    let mut matrices: Vec<(PathBuf, Value)> = Vec::new();
    for path in files {
        let Ok(metadata) = fs::metadata(&path) else {
            continue;
        };
        if metadata.len() > 25 * 1024 * 1024 {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(document) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        if document.get("regionId").and_then(Value::as_str) != Some(region_id.as_str()) {
            continue;
        }
        match document.get("schema").and_then(Value::as_str).unwrap_or_default() {
            "roadpilot.region-connector-inventory" => {
                let sha = sha256_prefixed(&path)?;
                let (is_current, checks) = connector_inventory_current(&document, &current);
                inventories.push((path, document, sha, is_current, checks));
            }
            "roadpilot.region-connector-matrix" => matrices.push((path, document)),
            _ => {}
        }
    }

    inventories.sort_by(|a, b| {
        b.3.cmp(&a.3)
            .then_with(|| a.0.display().to_string().cmp(&b.0.display().to_string()))
    });

    let mut matrix_infos = Vec::new();
    for (path, document) in matrices {
        let graph_matches = document
            .pointer("/graph/graphFingerprint")
            .and_then(Value::as_str)
            == current.get("graphFingerprint").and_then(Value::as_str);
        let source_sha = document
            .get("sourceInventorySha256")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let source_anchor_count = document.get("sourceAnchorCount").and_then(Value::as_u64);
        let matching_inventory = inventories.iter().find(|(_, _, sha, _, _)| sha == source_sha);
        let source_inventory_present = matching_inventory.is_some();
        let source_inventory_current = matching_inventory.map(|item| item.3).unwrap_or(false);
        let anchor_count_matches = matching_inventory
            .and_then(|item| item.1.get("anchorCount").and_then(Value::as_u64))
            == source_anchor_count;
        let is_current = graph_matches
            && source_inventory_present
            && source_inventory_current
            && anchor_count_matches;
        matrix_infos.push((
            path,
            document,
            is_current,
            source_inventory_present,
            source_inventory_current,
            anchor_count_matches,
        ));
    }
    matrix_infos.sort_by(|a, b| {
        b.2.cmp(&a.2)
            .then_with(|| a.0.display().to_string().cmp(&b.0.display().to_string()))
    });

    let selected_matrix = matrix_infos.first();
    let current_inventory = inventories.iter().find(|item| item.3);
    let selected_inventory = current_inventory
        .or_else(|| {
            selected_matrix.and_then(|(_, matrix, _, _, _, _)| {
                let source_sha = matrix.get("sourceInventorySha256").and_then(Value::as_str)?;
                inventories.iter().find(|(_, _, sha, _, _)| sha == source_sha)
            })
        })
        .or_else(|| inventories.first());

    let inventory_present = !inventories.is_empty();
    let inventory_current = current_inventory.is_some();
    let matrix_present = !matrix_infos.is_empty();
    let matrix_current = matrix_infos.iter().any(|item| item.2);

    let (status, refresh_action) = if !inventory_present {
        ("MISSING", "BUILD_INVENTORY_AND_MATRIX")
    } else if !inventory_current {
        ("STALE", "REBUILD_INVENTORY_AND_MATRIX")
    } else if !matrix_present {
        ("MISSING", "BUILD_MATRIX")
    } else if !matrix_current {
        ("STALE", "REBUILD_MATRIX")
    } else {
        ("CURRENT", "NONE")
    };

    let inventory_json = selected_inventory.map(|(path, document, sha, is_current, checks)| {
        json!({
            "artifactPath": path.display().to_string(),
            "sha256": sha,
            "current": is_current,
            "graph": document.get("graph").cloned().unwrap_or(Value::Null),
            "anchorCount": document.get("anchorCount").cloned().unwrap_or(Value::from(0)),
            "sourceConnectivity": document.get("sourceConnectivity").cloned().unwrap_or_else(|| json!([])),
            "boundaryChecks": checks,
            "anchors": document.get("anchors").cloned().unwrap_or_else(|| json!([]))
        })
    }).unwrap_or(Value::Null);

    let matrix_json = selected_matrix.map(|(path, document, is_current, source_present, source_current, anchor_count_matches)| {
        json!({
            "artifactPath": path.display().to_string(),
            "current": is_current,
            "graph": document.get("graph").cloned().unwrap_or(Value::Null),
            "sourceInventorySha256": document.get("sourceInventorySha256").cloned().unwrap_or(Value::Null),
            "sourceAnchorCount": document.get("sourceAnchorCount").cloned().unwrap_or(Value::Null),
            "sourceInventoryPresent": source_present,
            "sourceInventoryCurrent": source_current,
            "anchorCountMatches": anchor_count_matches,
            "modes": document.get("modes").cloned().unwrap_or_else(|| json!({}))
        })
    }).unwrap_or(Value::Null);

    Ok(json!({
        "regionId": region_id,
        "status": status,
        "refreshAction": refresh_action,
        "currentGraph": current,
        "recognizedInventories": inventories.len(),
        "recognizedMatrices": matrix_infos.len(),
        "inventory": inventory_json,
        "matrix": matrix_json,
        "searchDirectories": transition_artifact_dirs(&app)?
            .into_iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
    }))
}

fn pair_matches(document: &Value, region_a: &str, region_b: &str) -> bool {
    let from = document.get("fromRegionId").and_then(Value::as_str);
    let to = document.get("toRegionId").and_then(Value::as_str);
    matches!(
        (from, to),
        (Some(from), Some(to))
            if (from == region_a && to == region_b) || (from == region_b && to == region_a)
    )
}

fn coordinate_value(value: Option<&Value>) -> Option<Value> {
    let value = value?;
    let lat = value.get("lat")?.as_f64()?;
    let lng = value.get("lng")?.as_f64()?;
    if !lat.is_finite()
        || !lng.is_finite()
        || !(-90.0..=90.0).contains(&lat)
        || !(-180.0..=180.0).contains(&lng)
    {
        return None;
    }
    Some(json!({"lat": lat, "lng": lng}))
}

fn artifact_graph_fingerprint<'a>(document: &'a Value, side: &str) -> Option<&'a str> {
    let direct = match side {
        "from" => "fromGraphFingerprint",
        "to" => "toGraphFingerprint",
        _ => return None,
    };
    document
        .get(direct)
        .and_then(Value::as_str)
        .or_else(|| document.pointer(&format!("/{side}Graph/graphFingerprint")).and_then(Value::as_str))
}

fn artifact_primary_id<'a>(document: &'a Value, side: &str) -> Option<&'a str> {
    document
        .pointer(&format!("/{side}Graph/primaryGeofabrikId"))
        .and_then(Value::as_str)
}

fn artifact_boundary_fingerprint<'a>(document: &'a Value, side: &str) -> Option<&'a str> {
    document
        .get(match side {
            "from" => "fromBoundaryFingerprint",
            "to" => "toBoundaryFingerprint",
            _ => return None,
        })
        .and_then(Value::as_str)
}

fn artifact_side_current(
    document: &Value,
    side: &str,
    opposite_side: &str,
    current: &Value,
) -> bool {
    let bound_graph = artifact_graph_fingerprint(document, side);
    let current_graph = current.get("graphFingerprint").and_then(Value::as_str);
    if bound_graph != current_graph {
        return false;
    }

    let Some(bound_boundary) = artifact_boundary_fingerprint(document, side) else {
        return true;
    };
    let Some(neighbor_primary) = artifact_primary_id(document, opposite_side) else {
        return false;
    };
    current
        .pointer("/boundaryFingerprints")
        .and_then(Value::as_object)
        .and_then(|values| values.get(neighbor_primary))
        .and_then(Value::as_str)
        == Some(bound_boundary)
}

fn artifact_fingerprint_status(
    document: &Value,
    current_a: &Value,
    current_b: &Value,
    region_a: &str,
    region_b: &str,
) -> &'static str {
    let from = document.get("fromRegionId").and_then(Value::as_str).unwrap_or_default();
    let to = document.get("toRegionId").and_then(Value::as_str).unwrap_or_default();
    let matches = if from == region_a && to == region_b {
        artifact_side_current(document, "from", "to", current_a)
            && artifact_side_current(document, "to", "from", current_b)
    } else if from == region_b && to == region_a {
        artifact_side_current(document, "from", "to", current_b)
            && artifact_side_current(document, "to", "from", current_a)
    } else {
        false
    };
    if matches { "CURRENT" } else { "STALE" }
}

fn normalize_transition_document(
    document: &Value,
    path: &Path,
    current_a: &Value,
    current_b: &Value,
    region_a: &str,
    region_b: &str,
    output: &mut Vec<Value>,
) {
    if !pair_matches(document, region_a, region_b) {
        return;
    }
    let schema = document.get("schema").and_then(Value::as_str).unwrap_or_default();
    let status = artifact_fingerprint_status(
        document,
        current_a,
        current_b,
        region_a,
        region_b,
    );
    let from_region = document
        .get("fromRegionId")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let to_region = document
        .get("toRegionId")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let path_text = path.display().to_string();

    match schema {
        "roadpilot.crossing-candidates" => {
            let validation_state = document
                .get("validationState")
                .cloned()
                .unwrap_or(Value::String("UNPROVEN".into()));
            for candidate in document
                .get("candidates")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(from_coordinate) =
                    coordinate_value(candidate.pointer("/fromEdge/correlatedCoordinate"))
                else {
                    continue;
                };
                let Some(to_coordinate) =
                    coordinate_value(candidate.pointer("/toEdge/correlatedCoordinate"))
                else {
                    continue;
                };
                let tier = candidate.pointer("/evidence/tier").and_then(Value::as_u64);
                let mut evidence = vec![Value::String("GENERATED_CANDIDATE".into())];
                if let Some(tier) = tier {
                    evidence.push(Value::String(format!("EVIDENCE_TIER_{tier}")));
                }
                if candidate.pointer("/evidence/bothMatchStableWay").and_then(Value::as_bool) == Some(true) {
                    evidence.push(Value::String("BOTH_MATCH_STABLE_OSM_WAY".into()));
                }
                if candidate.pointer("/evidence/sameCorrelatedWay").and_then(Value::as_bool) == Some(true) {
                    evidence.push(Value::String("SAME_CORRELATED_OSM_WAY".into()));
                }
                output.push(json!({
                    "kind": "candidate",
                    "id": candidate.get("id").cloned().unwrap_or(Value::Null),
                    "status": status,
                    "validationState": validation_state,
                    "fromRegionId": from_region,
                    "toRegionId": to_region,
                    "from": from_coordinate,
                    "to": to_coordinate,
                    "fromWayId": candidate.pointer("/fromEdge/wayId").cloned().unwrap_or(Value::Null),
                    "toWayId": candidate.pointer("/toEdge/wayId").cloned().unwrap_or(Value::Null),
                    "modes": [],
                    "evidence": evidence,
                    "separationMeters": candidate.pointer("/evidence/separationMeters").cloned().unwrap_or(Value::Null),
                    "artifactPath": path_text
                }));
            }
        }
        "roadpilot.runtime-connectivity" => {
            let validation_state = document
                .get("validationState")
                .cloned()
                .unwrap_or(Value::String("VALIDATED".into()));
            for crossing in document
                .get("crossings")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(from_coordinate) =
                    coordinate_value(crossing.pointer("/fromAnchor/coordinate"))
                else {
                    continue;
                };
                let Some(to_coordinate) =
                    coordinate_value(crossing.pointer("/toAnchor/coordinate"))
                else {
                    continue;
                };
                let mut modes: Vec<Value> = Vec::new();
                for (mode_name, mode_key) in [("MOTORCYCLE", "MOTORCYCLE"), ("CAR", "CAR")] {
                    if let Some(mode) = crossing.pointer(&format!("/modes/{mode_key}")).and_then(Value::as_object) {
                        if mode.get("fromTo").and_then(Value::as_bool) == Some(true) {
                            modes.push(Value::String(format!("{mode_name}_FROM_TO")));
                        }
                        if mode.get("toFrom").and_then(Value::as_bool) == Some(true) {
                            modes.push(Value::String(format!("{mode_name}_TO_FROM")));
                        }
                    }
                }
                let tier = crossing.get("evidenceTier").and_then(Value::as_u64);
                let mut evidence = vec![Value::String("VALHALLA_PROVEN_RUNTIME".into())];
                if let Some(tier) = tier {
                    evidence.push(Value::String(format!("EVIDENCE_TIER_{tier}")));
                }
                output.push(json!({
                    "kind": "accepted",
                    "id": crossing.get("candidateId").cloned().unwrap_or(Value::Null),
                    "status": status,
                    "validationState": validation_state,
                    "fromRegionId": from_region,
                    "toRegionId": to_region,
                    "from": from_coordinate,
                    "to": to_coordinate,
                    "fromWayId": crossing.pointer("/fromAnchor/wayId").cloned().unwrap_or(Value::Null),
                    "toWayId": crossing.pointer("/toAnchor/wayId").cloned().unwrap_or(Value::Null),
                    "modes": modes,
                    "evidence": evidence,
                    "artifactPath": path_text
                }));
            }
        }
        "roadpilot.transition-candidates" => {
            for candidate in document
                .get("candidates")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(from_coordinate) =
                    coordinate_value(candidate.pointer("/fromEdge/anchorCoordinate"))
                else {
                    continue;
                };
                let Some(to_coordinate) =
                    coordinate_value(candidate.pointer("/toEdge/anchorCoordinate"))
                else {
                    continue;
                };
                output.push(json!({
                    "kind": "candidate",
                    "id": candidate.get("id").cloned().unwrap_or(Value::Null),
                    "status": status,
                    "validationState": Value::Null,
                    "fromRegionId": from_region,
                    "toRegionId": to_region,
                    "from": from_coordinate,
                    "to": to_coordinate,
                    "fromWayId": candidate.pointer("/fromEdge/wayId").cloned().unwrap_or(Value::Null),
                    "toWayId": candidate.pointer("/toEdge/wayId").cloned().unwrap_or(Value::Null),
                    "modes": candidate.get("commonTravelModes").cloned().unwrap_or_else(|| json!([])),
                    "evidence": candidate.get("matchEvidence").cloned().unwrap_or_else(|| json!([])),
                    "separationMeters": candidate.get("separationMeters").cloned().unwrap_or(Value::Null),
                    "artifactPath": path_text
                }));
            }
        }
        "roadpilot.bound-cross-graph-transitions" => {
            let mode = document.get("bindingMode").cloned().unwrap_or(Value::Null);
            for transition in document
                .get("transitions")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(from_coordinate) =
                    coordinate_value(transition.pointer("/fromBinding/proofCoordinate"))
                else {
                    continue;
                };
                let Some(to_coordinate) =
                    coordinate_value(transition.pointer("/toBinding/proofCoordinate"))
                else {
                    continue;
                };
                output.push(json!({
                    "kind": "accepted",
                    "id": transition.get("sourceProofId").cloned().unwrap_or(Value::Null),
                    "status": status,
                    "fromRegionId": from_region,
                    "toRegionId": to_region,
                    "from": from_coordinate,
                    "to": to_coordinate,
                    "modes": [mode.clone()],
                    "evidence": ["VALHALLA_PROVEN_BOUND_TRANSITION"],
                    "artifactPath": path_text
                }));
            }
        }
        "roadpilot.cross-graph-transitions" => {
            for transition in document
                .get("transitions")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let Some(from_coordinate) =
                    coordinate_value(transition.pointer("/fromAnchor/coordinate"))
                else {
                    continue;
                };
                let Some(to_coordinate) =
                    coordinate_value(transition.pointer("/toAnchor/coordinate"))
                else {
                    continue;
                };
                output.push(json!({
                    "kind": "learned",
                    "id": transition.get("id").cloned().unwrap_or(Value::Null),
                    "status": status,
                    "fromRegionId": from_region,
                    "toRegionId": to_region,
                    "from": from_coordinate,
                    "to": to_coordinate,
                    "modes": transition.get("provenTravelModes").cloned().unwrap_or_else(|| json!([])),
                    "evidence": transition.get("matchEvidence").cloned().map(|value| json!([value])).unwrap_or_else(|| json!([])),
                    "separationMeters": transition.get("frontierSeparationMeters").cloned().unwrap_or(Value::Null),
                    "artifactPath": path_text
                }));
            }
        }
        _ => {}
    }
}

#[tauri::command]
fn inspect_handoff_artifacts(
    app: AppHandle,
    region_a: String,
    region_b: String,
) -> Result<Value, String> {
    handoff_pair_key(&region_a, &region_b)?;
    let current_a = latest_graph_identity(&app, &region_a)?;
    let current_b = latest_graph_identity(&app, &region_b)?;
    let mut files = Vec::new();
    for root in transition_artifact_dirs(&app)? {
        collect_json_files(&root, 6, &mut files);
    }
    files.sort();
    files.dedup();

    let mut items = Vec::new();
    let mut recognized_files = 0usize;
    for path in files {
        let Ok(metadata) = fs::metadata(&path) else {
            continue;
        };
        if metadata.len() > 25 * 1024 * 1024 {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(document) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        let before = items.len();
        normalize_transition_document(
            &document,
            &path,
            &current_a,
            &current_b,
            &region_a,
            &region_b,
            &mut items,
        );
        if items.len() > before {
            recognized_files += 1;
        }
    }

    for override_record in list_handoff_overrides(app.clone())? {
        let a = override_record.get("regionA").and_then(Value::as_str);
        let b = override_record.get("regionB").and_then(Value::as_str);
        if !matches!(
            (a, b),
            (Some(a), Some(b))
                if (a == region_a && b == region_b) || (a == region_b && b == region_a)
        ) {
            continue;
        }
        let Some(from_coordinate) = coordinate_value(override_record.pointer("/snapA/correlated"))
        else {
            continue;
        };
        let Some(to_coordinate) = coordinate_value(override_record.pointer("/snapB/correlated"))
        else {
            continue;
        };
        items.push(json!({
            "kind": "manual",
            "id": override_record.get("id").cloned().unwrap_or(Value::Null),
            "status": override_record.get("status").cloned().unwrap_or(Value::String("STALE".into())),
            "validationState": "VALIDATED",
            "fromRegionId": override_record.get("regionA").cloned().unwrap_or(Value::Null),
            "toRegionId": override_record.get("regionB").cloned().unwrap_or(Value::Null),
            "from": from_coordinate,
            "to": to_coordinate,
            "modes": ["MOTORCYCLE", "CAR"],
            "evidence": ["MANUAL_VALHALLA_PROOF"],
            "artifactPath": "Graph Studio manual override layer"
        }));
    }

    items.sort_by(|a, b| {
        a.get("kind")
            .and_then(Value::as_str)
            .cmp(&b.get("kind").and_then(Value::as_str))
            .then_with(|| {
                a.get("id")
                    .and_then(Value::as_str)
                    .cmp(&b.get("id").and_then(Value::as_str))
            })
    });

    Ok(json!({
        "regionA": region_a,
        "regionB": region_b,
        "graphA": current_a,
        "graphB": current_b,
        "recognizedArtifactFiles": recognized_files,
        "searchDirectories": transition_artifact_dirs(&app)?
            .into_iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>(),
        "items": items
    }))
}

fn reports_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let path = workspace_root(app)?.join("reports");
    fs::create_dir_all(&path)
        .map_err(|e| format!("Could not create Graph Studio reports directory: {e}"))?;
    Ok(path)
}

fn handoff_summary(inspection: &Value) -> Value {
    let items = inspection
        .get("items")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut counts = serde_json::Map::new();
    for item in &items {
        let kind = item.get("kind").and_then(Value::as_str).unwrap_or("unknown");
        let status = item.get("status").and_then(Value::as_str).unwrap_or("unknown");
        let key = format!("{kind}.{status}");
        let next = counts.get(&key).and_then(Value::as_u64).unwrap_or(0) + 1;
        counts.insert(key, Value::from(next));
    }

    let mut notable = Vec::new();
    let mut current_candidates = 0usize;
    let mut stale_candidates = 0usize;
    for item in items {
        let kind = item.get("kind").and_then(Value::as_str).unwrap_or_default();
        if kind != "candidate" {
            notable.push(item);
            continue;
        }
        let status = item.get("status").and_then(Value::as_str).unwrap_or_default();
        if status == "CURRENT" && current_candidates < 20 {
            current_candidates += 1;
            notable.push(item);
        } else if status == "STALE" && stale_candidates < 20 {
            stale_candidates += 1;
            notable.push(item);
        }
    }

    json!({
        "counts": counts,
        "recognizedArtifactFiles": inspection.get("recognizedArtifactFiles").cloned().unwrap_or(Value::from(0)),
        "searchDirectories": inspection.get("searchDirectories").cloned().unwrap_or_else(|| json!([])),
        "notableHandoffs": notable
    })
}

fn markdown_scalar(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Number(value)) => value.to_string(),
        Some(Value::Bool(value)) => value.to_string(),
        Some(value) if !value.is_null() => value.to_string(),
        _ => "—".into(),
    }
}

fn border_diagnostics_markdown(report: &Value) -> String {
    let region_a = markdown_scalar(report.get("regionA"));
    let region_b = markdown_scalar(report.get("regionB"));
    let graph_a = report.get("graphA").unwrap_or(&Value::Null);
    let graph_b = report.get("graphB").unwrap_or(&Value::Null);
    let road = report.get("roadDiff").unwrap_or(&Value::Null);
    let summary = report.pointer("/handoffs/counts").unwrap_or(&Value::Null);
    let selected = report.get("selectedValidation").unwrap_or(&Value::Null);

    let mut output = String::new();
    output.push_str("# RoadPilot Border Diagnostics\n\n");
    output.push_str(&format!("**Regions:** {region_a} ↔ {region_b}\n\n"));
    output.push_str(&format!(
        "**Generated epoch ms:** {}\n\n",
        markdown_scalar(report.get("generatedAtEpochMs"))
    ));

    output.push_str("## Graph identity\n\n");
    output.push_str("| Side | Region | Package | Graph fingerprint |\n");
    output.push_str("| --- | --- | --- | --- |\n");
    output.push_str(&format!(
        "| A | {} | {} | {} |\n",
        markdown_scalar(graph_a.get("regionId")),
        markdown_scalar(graph_a.get("packageVersion")),
        markdown_scalar(graph_a.get("graphFingerprint"))
    ));
    output.push_str(&format!(
        "| B | {} | {} | {} |\n\n",
        markdown_scalar(graph_b.get("regionId")),
        markdown_scalar(graph_b.get("packageVersion")),
        markdown_scalar(graph_b.get("graphFingerprint"))
    ));

    output.push_str("## Loaded road overlap\n\n");
    if road.is_null() {
        output.push_str("Road diff was not calculated when this report was exported.\n\n");
    } else {
        output.push_str(&format!(
            "- Common OSM ways: {}\n- Graph A only: {}\n- Graph B only: {}\n- Loaded A edges: {}\n- Loaded B edges: {}\n- Edges without OSM id: A {} / B {}\n\n",
            markdown_scalar(road.get("commonWays")),
            markdown_scalar(road.get("aOnlyWays")),
            markdown_scalar(road.get("bOnlyWays")),
            markdown_scalar(road.get("loadedEdgesA")),
            markdown_scalar(road.get("loadedEdgesB")),
            markdown_scalar(road.get("unidentifiedA")),
            markdown_scalar(road.get("unidentifiedB"))
        ));
    }

    output.push_str("## Handoff artifacts\n\n");
    let count = |key: &str| markdown_scalar(summary.get(key));
    output.push_str(&format!(
        "- Candidate: {} current / {} stale\n- Accepted/bound: {} current / {} stale\n- Learned F8 proof: {} current / {} stale\n- Manual: {} valid / {} stale\n- Recognized artifact files: {}\n\n",
        count("candidate.CURRENT"),
        count("candidate.STALE"),
        count("accepted.CURRENT"),
        count("accepted.STALE"),
        count("learned.CURRENT"),
        count("learned.STALE"),
        count("manual.VALID"),
        count("manual.STALE"),
        markdown_scalar(report.pointer("/handoffs/recognizedArtifactFiles"))
    ));

    output.push_str("## Selected crossing proof\n\n");
    if selected.is_null() {
        output.push_str("No selected crossing validation was attached.\n\n");
    } else {
        output.push_str(&format!(
            "**Overall:** {}\n\n",
            if selected.get("passed").and_then(Value::as_bool) == Some(true) {
                "PASS"
            } else {
                "FAIL"
            }
        ));
        if let Some(probes) = selected.get("probes").and_then(Value::as_object) {
            for (name, result) in probes {
                let passed = result.get("passed").and_then(Value::as_bool) == Some(true);
                let elapsed = markdown_scalar(result.get("elapsedMs"));
                let error = result.get("error").and_then(Value::as_str).unwrap_or("");
                if error.is_empty() {
                    output.push_str(&format!(
                        "- {}: {} ({} ms)\n",
                        name,
                        if passed { "PASS" } else { "FAIL" },
                        elapsed
                    ));
                } else {
                    output.push_str(&format!(
                        "- {}: FAIL — {}\n",
                        name,
                        error.replace('\n', " ")
                    ));
                }
            }
            output.push('\n');
        }
    }

    output.push_str("## Notable handoffs\n\n");
    if let Some(items) = report
        .pointer("/handoffs/notableHandoffs")
        .and_then(Value::as_array)
    {
        if items.is_empty() {
            output.push_str("No handoff artifacts were available for this pair.\n");
        } else {
            output.push_str("| Kind | Status | Direction | Id | Modes |\n");
            output.push_str("| --- | --- | --- | --- | --- |\n");
            for item in items {
                let modes = item
                    .get("modes")
                    .and_then(Value::as_array)
                    .map(|values| {
                        values
                            .iter()
                            .filter_map(Value::as_str)
                            .collect::<Vec<_>>()
                            .join(", ")
                    })
                    .unwrap_or_default();
                output.push_str(&format!(
                    "| {} | {} | {} → {} | {} | {} |\n",
                    markdown_scalar(item.get("kind")),
                    markdown_scalar(item.get("status")),
                    markdown_scalar(item.get("fromRegionId")),
                    markdown_scalar(item.get("toRegionId")),
                    markdown_scalar(item.get("id")).replace('|', "/"),
                    modes.replace('|', "/")
                ));
            }
        }
    }
    output
}

#[tauri::command]
fn export_border_diagnostics(
    app: AppHandle,
    region_a: String,
    region_b: String,
    road_diff: Option<Value>,
    selected_validation: Option<Value>,
) -> Result<Value, String> {
    handoff_pair_key(&region_a, &region_b)?;
    let inspection = inspect_handoff_artifacts(
        app.clone(),
        region_a.clone(),
        region_b.clone(),
    )?;
    let report = json!({
        "schema": "roadpilot.border-diagnostics",
        "version": 1,
        "generatedAtEpochMs": now_epoch_ms(),
        "regionA": region_a,
        "regionB": region_b,
        "graphA": inspection.get("graphA").cloned().unwrap_or(Value::Null),
        "graphB": inspection.get("graphB").cloned().unwrap_or(Value::Null),
        "roadDiff": road_diff.unwrap_or(Value::Null),
        "handoffs": handoff_summary(&inspection),
        "selectedValidation": selected_validation.unwrap_or(Value::Null)
    });

    let pair = handoff_pair_key(
        report.get("regionA").and_then(Value::as_str).unwrap_or("a"),
        report.get("regionB").and_then(Value::as_str).unwrap_or("b"),
    )?;
    let stamp = report
        .get("generatedAtEpochMs")
        .and_then(Value::as_u64)
        .map(u128::from)
        .unwrap_or_else(now_epoch_ms);
    let root = reports_dir(&app)?;
    let json_path = root.join(format!("{pair}-{stamp}.json"));
    let markdown_path = root.join(format!("{pair}-{stamp}.md"));

    fs::write(
        &json_path,
        serde_json::to_string_pretty(&report)
            .map_err(|e| format!("Could not serialize diagnostics report: {e}"))?
            + "\n",
    )
    .map_err(|e| format!("Could not write {}: {e}", json_path.display()))?;
    fs::write(&markdown_path, border_diagnostics_markdown(&report))
        .map_err(|e| format!("Could not write {}: {e}", markdown_path.display()))?;

    Ok(json!({
        "jsonPath": json_path.display().to_string(),
        "markdownPath": markdown_path.display().to_string(),
        "report": report
    }))
}

fn handoff_pair_key(region_a: &str, region_b: &str) -> Result<String, String> {
    if !safe_token(region_a) || !safe_token(region_b) || region_a == region_b {
        return Err("Manual handoff requires two different valid region ids.".into());
    }
    let mut pair = [region_a.to_string(), region_b.to_string()];
    pair.sort();
    Ok(format!("{}__{}", pair[0], pair[1]))
}

fn handoff_pair_path(app: &AppHandle, region_a: &str, region_b: &str) -> Result<PathBuf, String> {
    Ok(handoff_dir(app)?.join(format!("{}.json", handoff_pair_key(region_a, region_b)?)))
}

fn load_handoff_file(path: &Path) -> Result<Vec<Value>, String> {
    if !path.is_file() {
        return Ok(Vec::new());
    }
    let text = fs::read_to_string(path)
        .map_err(|e| format!("Could not read {}: {e}", path.display()))?;
    let value: Value = serde_json::from_str(&text)
        .map_err(|e| format!("Could not parse {}: {e}", path.display()))?;
    value
        .get("overrides")
        .and_then(Value::as_array)
        .cloned()
        .ok_or_else(|| format!("Invalid manual handoff file: {}", path.display()))
}

fn write_handoff_file(path: &Path, overrides: &[Value]) -> Result<(), String> {
    let document = json!({
        "schema": "roadpilot-manual-handoffs",
        "schemaVersion": 1,
        "overrides": overrides
    });
    let temporary = path.with_extension("json.tmp");
    fs::write(
        &temporary,
        serde_json::to_string_pretty(&document)
            .map_err(|e| format!("Could not serialize manual handoffs: {e}"))?
            + "\n",
    )
    .map_err(|e| format!("Could not write {}: {e}", temporary.display()))?;
    fs::rename(&temporary, path)
        .map_err(|e| format!("Could not activate {}: {e}", path.display()))?;
    Ok(())
}

fn first_located_edge(locate: &Value) -> Result<Value, String> {
    let item = locate
        .as_array()
        .and_then(|items| items.first())
        .ok_or("Valhalla locate returned no location result.")?;
    let edges = item
        .get("edges")
        .and_then(Value::as_array)
        .ok_or("Valhalla locate returned no correlated edges.")?;
    let edge = edges
        .iter()
        .filter(|edge| edge.get("correlated_lat").is_some() && edge.get("correlated_lon").is_some())
        .min_by(|a, b| {
            let ad = a.get("distance").and_then(Value::as_f64).unwrap_or(f64::MAX);
            let bd = b.get("distance").and_then(Value::as_f64).unwrap_or(f64::MAX);
            ad.partial_cmp(&bd).unwrap_or(std::cmp::Ordering::Equal)
        })
        .cloned()
        .ok_or("Valhalla locate did not return a usable directed edge.")?;
    Ok(edge)
}

#[tauri::command]
fn snap_handoff_point(
    app: AppHandle,
    region_id: String,
    lat: f64,
    lng: f64,
) -> Result<Value, String> {
    let locate = inspect_locate(app.clone(), region_id.clone(), lat, lng)?;
    let edge = first_located_edge(&locate)?;
    let identity = latest_graph_identity(&app, &region_id)?;
    Ok(json!({
        "regionId": region_id,
        "input": {"lat": lat, "lng": lng},
        "correlated": {
            "lat": edge.get("correlated_lat").cloned().unwrap_or(Value::Null),
            "lng": edge.get("correlated_lon").cloned().unwrap_or(Value::Null)
        },
        "wayId": edge
            .pointer("/edge_info/way_id")
            .cloned()
            .or_else(|| edge.get("way_id").cloned())
            .unwrap_or(Value::Null),
        "percentAlong": edge.get("percent_along").cloned().unwrap_or(Value::Null),
        "distanceMeters": edge.get("distance").cloned().unwrap_or(Value::Null),
        "heading": edge.get("heading").cloned().unwrap_or(Value::Null),
        "linearReference": edge.get("linear_reference").cloned().unwrap_or(Value::Null),
        "edgeId": edge.get("edge_id").cloned().unwrap_or(Value::Null),
        "edge": edge.get("edge").cloned().unwrap_or(Value::Null),
        "edgeInfo": edge.get("edge_info").cloned().unwrap_or(Value::Null),
        "graph": identity
    }))
}

fn handoff_route_probe(
    app: &AppHandle,
    region_id: &str,
    start_lat: f64,
    start_lng: f64,
    end_lat: f64,
    end_lng: f64,
    costing: &str,
) -> Value {
    let config = match valhalla_config_for(app, region_id) {
        Ok(config) => config,
        Err(error) => return json!({"passed": false, "error": error}),
    };
    let request = valhalla_route_request(
        start_lat,
        start_lng,
        end_lat,
        end_lng,
        costing,
        None,
    );
    let started = Instant::now();
    let output = match Command::new("valhalla_service")
        .arg(config)
        .arg("route")
        .arg(request.to_string())
        .output()
    {
        Ok(output) => output,
        Err(error) => {
            return json!({"passed": false, "error": format!("Could not run Valhalla: {error}")})
        }
    };
    let elapsed_ms = started.elapsed().as_millis();
    if !output.status.success() {
        return json!({
            "passed": false,
            "elapsedMs": elapsed_ms,
            "error": String::from_utf8_lossy(&output.stderr).trim()
        });
    }
    match serde_json::from_slice::<Value>(&output.stdout) {
        Ok(response) => json!({
            "passed": response.pointer("/trip/status").and_then(Value::as_i64).unwrap_or(0) == 0,
            "elapsedMs": elapsed_ms,
            "summary": response.pointer("/trip/summary").cloned().unwrap_or(Value::Null),
            "statusMessage": response.pointer("/trip/status_message").cloned().unwrap_or(Value::Null)
        }),
        Err(error) => json!({
            "passed": false,
            "elapsedMs": elapsed_ms,
            "error": format!("Invalid Valhalla response: {error}")
        }),
    }
}

fn snap_coordinate(snap: &Value) -> Result<(f64, f64), String> {
    let lat = snap
        .pointer("/correlated/lat")
        .and_then(Value::as_f64)
        .ok_or("Manual handoff snap is missing correlated latitude.")?;
    let lng = snap
        .pointer("/correlated/lng")
        .and_then(Value::as_f64)
        .ok_or("Manual handoff snap is missing correlated longitude.")?;
    Ok((lat, lng))
}

#[tauri::command]
fn validate_handoff_override(
    app: AppHandle,
    region_a: String,
    region_b: String,
    snap_a: Value,
    snap_b: Value,
) -> Result<Value, String> {
    handoff_pair_key(&region_a, &region_b)?;
    if snap_a.get("regionId").and_then(Value::as_str) != Some(region_a.as_str())
        || snap_b.get("regionId").and_then(Value::as_str) != Some(region_b.as_str())
    {
        return Err("Handoff snaps do not match the selected regions.".into());
    }

    let (a_lat, a_lng) = snap_coordinate(&snap_a)?;
    let (b_lat, b_lng) = snap_coordinate(&snap_b)?;
    let mut probes = serde_json::Map::new();
    let mut all_passed = true;

    for costing in ["motorcycle", "auto"] {
        for (graph_label, region_id) in [("graphA", region_a.as_str()), ("graphB", region_b.as_str())] {
            for (direction, start_lat, start_lng, end_lat, end_lng) in [
                ("aToB", a_lat, a_lng, b_lat, b_lng),
                ("bToA", b_lat, b_lng, a_lat, a_lng),
            ] {
                let result = handoff_route_probe(
                    &app,
                    region_id,
                    start_lat,
                    start_lng,
                    end_lat,
                    end_lng,
                    costing,
                );
                if result.get("passed").and_then(Value::as_bool) != Some(true) {
                    all_passed = false;
                }
                probes.insert(
                    format!("{costing}.{graph_label}.{direction}"),
                    result,
                );
            }
        }
    }

    Ok(json!({
        "passed": all_passed,
        "regionA": region_a,
        "regionB": region_b,
        "graphA": latest_graph_identity(&app, &region_a)?,
        "graphB": latest_graph_identity(&app, &region_b)?,
        "probes": probes
    }))
}

#[tauri::command]
fn save_handoff_override(
    app: AppHandle,
    region_a: String,
    region_b: String,
    snap_a: Value,
    snap_b: Value,
    override_id: Option<String>,
) -> Result<Value, String> {
    let validation = validate_handoff_override(
        app.clone(),
        region_a.clone(),
        region_b.clone(),
        snap_a.clone(),
        snap_b.clone(),
    )?;
    if validation.get("passed").and_then(Value::as_bool) != Some(true) {
        return Err("Manual handoff validation failed; refusing to save it as VALID.".into());
    }

    let path = handoff_pair_path(&app, &region_a, &region_b)?;
    let mut overrides = load_handoff_file(&path)?;
    let id = override_id
        .filter(|id| safe_token(id))
        .unwrap_or_else(|| format!("handoff-{}", now_epoch_ms()));
    let record = json!({
        "id": id,
        "schemaVersion": 1,
        "source": "manual",
        "status": "VALID",
        "createdAtEpochMs": now_epoch_ms(),
        "regionA": region_a,
        "regionB": region_b,
        "graphFingerprintA": validation.pointer("/graphA/graphFingerprint").cloned().unwrap_or(Value::Null),
        "graphFingerprintB": validation.pointer("/graphB/graphFingerprint").cloned().unwrap_or(Value::Null),
        "graphVersionA": validation.pointer("/graphA/packageVersion").cloned().unwrap_or(Value::Null),
        "graphVersionB": validation.pointer("/graphB/packageVersion").cloned().unwrap_or(Value::Null),
        "snapA": snap_a,
        "snapB": snap_b,
        "validation": validation
    });

    if let Some(position) = overrides
        .iter()
        .position(|existing| existing.get("id").and_then(Value::as_str) == record.get("id").and_then(Value::as_str))
    {
        overrides[position] = record.clone();
    } else {
        overrides.push(record.clone());
    }
    write_handoff_file(&path, &overrides)?;
    Ok(record)
}

#[tauri::command]
fn list_handoff_overrides(app: AppHandle) -> Result<Vec<Value>, String> {
    let root = handoff_dir(&app)?;
    let mut result = Vec::new();
    for entry in fs::read_dir(root)
        .map_err(|e| format!("Could not list manual handoffs: {e}"))?
        .flatten()
    {
        let path = entry.path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        for mut record in load_handoff_file(&path)? {
            let region_a = record.get("regionA").and_then(Value::as_str).unwrap_or_default();
            let region_b = record.get("regionB").and_then(Value::as_str).unwrap_or_default();
            let current_a = latest_graph_identity(&app, region_a).ok();
            let current_b = latest_graph_identity(&app, region_b).ok();
            let matches_a = current_a
                .as_ref()
                .and_then(|value| value.get("graphFingerprint"))
                == record.get("graphFingerprintA");
            let matches_b = current_b
                .as_ref()
                .and_then(|value| value.get("graphFingerprint"))
                == record.get("graphFingerprintB");
            record["status"] = Value::String(
                if matches_a && matches_b { "VALID" } else { "STALE" }.into(),
            );
            record["currentGraphA"] = current_a.unwrap_or(Value::Null);
            record["currentGraphB"] = current_b.unwrap_or(Value::Null);
            result.push(record);
        }
    }
    result.sort_by(|a, b| {
        b.get("createdAtEpochMs")
            .and_then(Value::as_u64)
            .cmp(&a.get("createdAtEpochMs").and_then(Value::as_u64))
    });
    Ok(result)
}

#[tauri::command]
fn delete_handoff_override(
    app: AppHandle,
    region_a: String,
    region_b: String,
    override_id: String,
) -> Result<(), String> {
    if !safe_token(&override_id) {
        return Err("Invalid manual handoff id.".into());
    }
    let path = handoff_pair_path(&app, &region_a, &region_b)?;
    let mut overrides = load_handoff_file(&path)?;
    let before = overrides.len();
    overrides.retain(|record| record.get("id").and_then(Value::as_str) != Some(override_id.as_str()));
    if overrides.len() == before {
        return Err(format!("Manual handoff not found: {override_id}"));
    }
    write_handoff_file(&path, &overrides)
}

fn valhalla_config_for(app: &AppHandle, region_id: &str) -> Result<PathBuf, String> {
    if !safe_token(region_id) {
        return Err("Invalid region id.".into());
    }
    let config = work_dir(app)?
        .join(region_id)
        .join("build")
        .join("valhalla.json");
    if !config.is_file() {
        return Err(format!(
            "No local inspected graph exists for {region_id}. Build the region first."
        ));
    }
    Ok(config)
}

fn valhalla_config_for_build(app: &AppHandle, raw_manifest_path: &str) -> Result<PathBuf, String> {
    let manifest_path = safe_build_manifest_path(app, raw_manifest_path)?;
    let text = fs::read_to_string(&manifest_path)
        .map_err(|e| format!("Could not read {}: {e}", manifest_path.display()))?;
    let manifest: Value = serde_json::from_str(&text)
        .map_err(|e| format!("Could not parse {}: {e}", manifest_path.display()))?;

    let region_id = manifest
        .get("regionId")
        .and_then(Value::as_str)
        .ok_or("Build manifest is missing regionId.")?;
    let version = manifest
        .get("packageVersion")
        .and_then(Value::as_str)
        .ok_or("Build manifest is missing packageVersion.")?;
    if !safe_token(region_id) || !safe_token(version) {
        return Err("Build manifest contains an unsafe region/version identifier.".into());
    }

    let artifact_name = manifest
        .pointer("/artifact/fileName")
        .and_then(Value::as_str)
        .ok_or("Build manifest is missing artifact.fileName.")?;
    let manifest_dir = manifest_path
        .parent()
        .ok_or("Build manifest has no parent directory.")?
        .canonicalize()
        .map_err(|e| format!("Could not resolve build directory: {e}"))?;
    let artifact_path = manifest_dir
        .join(artifact_name)
        .canonicalize()
        .map_err(|e| format!("Could not resolve retained routing pack {artifact_name}: {e}"))?;
    if !artifact_path.starts_with(&manifest_dir) || !artifact_path.is_file() {
        return Err("Retained routing pack is outside the build directory or missing.".into());
    }

    let base_config_path = valhalla_config_for(app, region_id)?;
    let base_text = fs::read_to_string(&base_config_path)
        .map_err(|e| format!("Could not read {}: {e}", base_config_path.display()))?;
    let mut config: Value = serde_json::from_str(&base_text)
        .map_err(|e| format!("Could not parse {}: {e}", base_config_path.display()))?;

    let cache = workspace_root(app)?
        .join("cache")
        .join("build-diff")
        .join(format!("{region_id}--{version}"));
    let empty_tiles = cache.join("tiles");
    fs::create_dir_all(&empty_tiles)
        .map_err(|e| format!("Could not create historical graph cache: {e}"))?;
    let config_path = cache.join("valhalla.json");

    let mjolnir = config
        .get_mut("mjolnir")
        .and_then(Value::as_object_mut)
        .ok_or("Valhalla config is missing mjolnir settings.")?;
    mjolnir.insert(
        "tile_extract".into(),
        Value::String(artifact_path.display().to_string()),
    );
    mjolnir.insert(
        "tile_dir".into(),
        Value::String(empty_tiles.display().to_string()),
    );
    mjolnir.remove("traffic_extract");

    let serialized = serde_json::to_string_pretty(&config)
        .map_err(|e| format!("Could not serialize historical Valhalla config: {e}"))?;
    fs::write(&config_path, serialized)
        .map_err(|e| format!("Could not write {}: {e}", config_path.display()))?;
    Ok(config_path)
}

fn render_graph_tile(config: &Path, z: u8, x: u32, y: u32) -> Result<Vec<u8>, String> {
    if z > 30 {
        return Err("Invalid graph tile zoom.".into());
    }
    let max = if z >= 32 { u64::MAX } else { 1_u64 << z };
    if u64::from(x) >= max || u64::from(y) >= max {
        return Err("Invalid graph tile coordinate.".into());
    }

    let request = json!({
        "tile": {"z": z, "x": x, "y": y},
        "generalize": 1.0,
        "filters": {
            "action": "include",
            "attributes": [
                "edge.osm_id",
                "edge.country_crossing",
                "edge.use",
                "edge.access_forward",
                "edge.access_backward",
                "edge.length",
                "edge.speed_forward",
                "edge.speed_backward",
                "edge.speed_limit",
                "edge.tunnel",
                "edge.bridge",
                "edge.roundabout",
                "edge.destination_only",
                "edge.unpaved",
                "edge.surface",
                "edge.ramp",
                "edge.not_thru",
                "edge.layer"
            ]
        }
    })
    .to_string();
    let output = Command::new("valhalla_service")
        .arg(config)
        .arg("tile")
        .arg(request)
        .output()
        .map_err(|e| format!("Could not render Valhalla graph tile: {e}"))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    if output.stdout.is_empty() {
        return Err("Valhalla returned an empty graph tile.".into());
    }
    Ok(output.stdout)
}

#[tauri::command]
fn graph_tile_for_build(
    app: AppHandle,
    manifest_path: String,
    z: u8,
    x: u32,
    y: u32,
) -> Result<Vec<u8>, String> {
    let config = valhalla_config_for_build(&app, &manifest_path)?;
    render_graph_tile(&config, z, x, y)
}

fn validate_route_request(
    start_lat: f64,
    start_lng: f64,
    end_lat: f64,
    end_lng: f64,
    costing: &str,
) -> Result<(), String> {
    for (label, lat, lng) in [
        ("start", start_lat, start_lng),
        ("end", end_lat, end_lng),
    ] {
        if !lat.is_finite()
            || !lng.is_finite()
            || !(-90.0..=90.0).contains(&lat)
            || !(-180.0..=180.0).contains(&lng)
        {
            return Err(format!("Invalid {label} coordinate."));
        }
    }
    match costing {
        "motorcycle" | "auto" | "bicycle" | "pedestrian" => Ok(()),
        _ => Err(format!("Unsupported Graph Studio costing: {costing}")),
    }
}

fn decode_polyline6(encoded: &str) -> Result<Vec<Value>, String> {
    let bytes = encoded.as_bytes();
    let mut index = 0usize;
    let mut latitude = 0_i64;
    let mut longitude = 0_i64;
    let mut coordinates = Vec::new();

    fn next_value(bytes: &[u8], index: &mut usize) -> Result<i64, String> {
        let mut result = 0_i64;
        let mut shift = 0_u32;
        loop {
            let Some(byte) = bytes.get(*index).copied() else {
                return Err("Truncated Valhalla route polyline.".into());
            };
            *index += 1;
            let value = i64::from(byte.saturating_sub(63));
            result |= (value & 0x1f) << shift;
            shift += 5;
            if value < 0x20 {
                break;
            }
            if shift > 60 {
                return Err("Invalid Valhalla route polyline.".into());
            }
        }
        Ok(if result & 1 != 0 {
            !(result >> 1)
        } else {
            result >> 1
        })
    }

    while index < bytes.len() {
        latitude += next_value(bytes, &mut index)?;
        longitude += next_value(bytes, &mut index)?;
        coordinates.push(json!([
            longitude as f64 / 1_000_000.0,
            latitude as f64 / 1_000_000.0
        ]));
    }
    Ok(coordinates)
}

fn route_geometry(response: &Value) -> Result<Value, String> {
    let legs = response
        .pointer("/trip/legs")
        .and_then(Value::as_array)
        .ok_or("Valhalla route response did not contain trip.legs.")?;
    let mut coordinates: Vec<Value> = Vec::new();
    for leg in legs {
        let shape = leg
            .get("shape")
            .and_then(Value::as_str)
            .ok_or("Valhalla route leg did not contain an encoded shape.")?;
        let mut leg_coordinates = decode_polyline6(shape)?;
        if !coordinates.is_empty() && !leg_coordinates.is_empty() {
            leg_coordinates.remove(0);
        }
        coordinates.extend(leg_coordinates);
    }
    if coordinates.len() < 2 {
        return Err("Valhalla route returned insufficient geometry.".into());
    }
    Ok(json!({
        "type": "LineString",
        "coordinates": coordinates
    }))
}

fn valhalla_route_request(
    start_lat: f64,
    start_lng: f64,
    end_lat: f64,
    end_lng: f64,
    costing: &str,
    costing_options: Option<Value>,
) -> Value {
    let mut request = json!({
        "locations": [
            {"lat": start_lat, "lon": start_lng},
            {"lat": end_lat, "lon": end_lng}
        ],
        "costing": costing,
        "directions_options": {"units": "kilometers"}
    });
    if let Some(options) = costing_options {
        if !options.is_null() {
            request["costing_options"] = options;
        }
    }
    request
}

#[tauri::command]
fn plan_route(
    app: AppHandle,
    region_id: String,
    start_lat: f64,
    start_lng: f64,
    end_lat: f64,
    end_lng: f64,
    costing: String,
    costing_options: Option<Value>,
) -> Result<Value, String> {
    validate_route_request(start_lat, start_lng, end_lat, end_lng, &costing)?;
    let config = valhalla_config_for(&app, &region_id)?;
    let request = valhalla_route_request(
        start_lat,
        start_lng,
        end_lat,
        end_lng,
        &costing,
        costing_options,
    );

    let started = Instant::now();
    let output = Command::new("valhalla_service")
        .arg(config)
        .arg("route")
        .arg(request.to_string())
        .output()
        .map_err(|e| format!("Could not run Valhalla route: {e}"))?;
    let elapsed_ms = started.elapsed().as_millis();

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    let response: Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Valhalla route returned invalid JSON: {e}"))?;
    let geometry = route_geometry(&response)?;

    Ok(json!({
        "elapsedMs": elapsed_ms,
        "geometry": geometry,
        "response": response
    }))
}

#[tauri::command]
fn route_expansion(
    app: AppHandle,
    region_id: String,
    start_lat: f64,
    start_lng: f64,
    end_lat: f64,
    end_lng: f64,
    costing: String,
    costing_options: Option<Value>,
) -> Result<Value, String> {
    validate_route_request(start_lat, start_lng, end_lat, end_lng, &costing)?;
    let config = valhalla_config_for(&app, &region_id)?;
    let mut request = valhalla_route_request(
        start_lat,
        start_lng,
        end_lat,
        end_lng,
        &costing,
        costing_options,
    );
    request["action"] = Value::String("route".into());
    request["dedupe"] = Value::Bool(true);
    request["expansion_properties"] = json!([
        "duration",
        "distance",
        "cost",
        "edge_status",
        "edge_id",
        "pred_edge_id",
        "expansion_type"
    ]);

    let started = Instant::now();
    let output = Command::new("valhalla_service")
        .arg(config)
        .arg("expansion")
        .arg(request.to_string())
        .output()
        .map_err(|e| format!("Could not run Valhalla expansion: {e}"))?;
    let elapsed_ms = started.elapsed().as_millis();

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    let expansion: Value = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Valhalla expansion returned invalid GeoJSON: {e}"))?;
    let feature_count = expansion
        .get("features")
        .and_then(Value::as_array)
        .map(|features| features.len())
        .unwrap_or(0);

    Ok(json!({
        "elapsedMs": elapsed_ms,
        "featureCount": feature_count,
        "geojson": expansion
    }))
}

#[tauri::command]
fn inspect_locate(
    app: AppHandle,
    region_id: String,
    lat: f64,
    lng: f64,
) -> Result<Value, String> {
    if !lat.is_finite() || !lng.is_finite() || !(-90.0..=90.0).contains(&lat) || !(-180.0..=180.0).contains(&lng) {
        return Err("Invalid inspection coordinate.".into());
    }
    let config = valhalla_config_for(&app, &region_id)?;
    let request = json!({
        "locations": [{"lat": lat, "lon": lng}],
        "verbose": true
    })
    .to_string();
    let output = Command::new("valhalla_service")
        .arg(config)
        .arg("locate")
        .arg(request)
        .output()
        .map_err(|e| format!("Could not run Valhalla locate: {e}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Valhalla locate returned invalid JSON: {e}"))
}

#[tauri::command]
fn graph_tile(
    app: AppHandle,
    region_id: String,
    z: u8,
    x: u32,
    y: u32,
) -> Result<Vec<u8>, String> {
    let config = valhalla_config_for(&app, &region_id)?;
    render_graph_tile(&config, z, x, y)
}

pub fn run() {
    normalize_process_path();
    tauri::Builder::default()
        .manage(BuildState::default())
        .invoke_handler(tauri::generate_handler![
            list_regions,
            geofabrik_catalog,
            preview_region,
            load_region_config,
            save_region_config,
            toolchain_status,
            system_stats,
            build_status,
            start_build_queue,
            cancel_build,
            list_builds,
            compare_build_indexes,
            snap_handoff_point,
            validate_handoff_override,
            save_handoff_override,
            list_handoff_overrides,
            delete_handoff_override,
            inspect_handoff_artifacts,
            inspect_region_connector_matrix,
            export_border_diagnostics,
            plan_route,
            route_expansion,
            inspect_locate,
            graph_tile,
            graph_tile_for_build
        ])
        .run(tauri::generate_context!())
        .expect("error while running RoadPilot Graph Studio");
}
