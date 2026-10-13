//! M3: bounded, explicit, read-only Valhalla route verification.
//! Shared by headless CLI and Tauri; never builds, edits, or publishes a graph.
use serde_json::{json, Value};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

const SCHEMA: &str = "roadpilot.graph-studio.ai-route-verification.v1";
const TIMEOUT: Duration = Duration::from_secs(20);
const MAX_STDOUT: u64 = 1024 * 1024;
const MAX_CONFIG_BYTES: u64 = 2 * 1024 * 1024;
const MAX_SNAP_METERS: f64 = 150.0;

#[derive(Debug, Clone)]
pub struct RouteProbe {
    pub region_id: String,
    pub start_lat: f64,
    pub start_lng: f64,
    pub end_lat: f64,
    pub end_lng: f64,
    pub costing: String,
}

impl RouteProbe {
    pub fn from_cli(args: &[String]) -> Result<Self, String> {
        if args.len() != 6 {
            return Err("Usage: --ai-verify-route REGION START_LAT START_LNG END_LAT END_LNG COSTING".into());
        }
        let parse = |i: usize| args[i].parse::<f64>()
            .map_err(|_| "Invalid coordinate argument".to_string());
        let value = Self {
            region_id: args[0].clone(),
            start_lat: parse(1)?,
            start_lng: parse(2)?,
            end_lat: parse(3)?,
            end_lng: parse(4)?,
            costing: args[5].clone(),
        };
        value.validate()?;
        Ok(value)
    }

    fn validate(&self) -> Result<(), String> {
        if self.region_id.len() > 80 || self.region_id.is_empty()
            || !self.region_id.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
            || self.region_id.starts_with('-')
        {
            return Err("Invalid region identifier".into());
        }
        crate::validate_route_request(
            self.start_lat, self.start_lng, self.end_lat, self.end_lng, &self.costing
        )?;
        if haversine_meters(
            self.start_lat, self.start_lng, self.end_lat, self.end_lng
        ) < 1.0 {
            return Err("Verification endpoints must be distinct".into());
        }
        Ok(())
    }
}

fn checked_directory(path: &Path) -> Result<(), String> {
    if fs::symlink_metadata(path).map(|m| m.file_type().is_dir()).unwrap_or(false) {
        Ok(())
    } else {
        Err("Expected a regular local graph directory; missing or unsafe".into())
    }
}

fn checked_config(workspace: &Path, region: &str) -> Result<PathBuf, String> {
    checked_directory(workspace)?;
    let mut path = workspace.to_path_buf();
    for part in ["work", region, "build"] {
        path.push(part);
        checked_directory(&path)?;
    }
    let config = path.join("valhalla.json");
    let metadata = fs::symlink_metadata(&config)
        .map_err(|_| "Region has no locally built Valhalla graph configuration")?;
    if !metadata.file_type().is_file() || metadata.len() > MAX_CONFIG_BYTES {
        return Err("Unsafe or oversized Valhalla graph configuration".into());
    }
    let contents = fs::read_to_string(&config).map_err(|_| "Could not read local graph configuration")?;
    let value: Value = serde_json::from_str(&contents)
        .map_err(|_| "Invalid local graph configuration")?;
    // The config can refer to the tiles or the packed tile extract; either must
    // reside inside the exact selected region build and already exist.
    let tiles = value.pointer("/mjolnir/tile_dir").and_then(Value::as_str);
    let extract = value.pointer("/mjolnir/tile_extract").and_then(Value::as_str);
    let mut found = false;
    for candidate in [tiles, extract].into_iter().flatten() {
        let candidate_path = Path::new(candidate);
        if candidate_path.is_absolute() && candidate_path.starts_with(&path) {
            if let Ok(meta) = fs::symlink_metadata(candidate_path) {
                found |= meta.file_type().is_dir() || (meta.file_type().is_file() && meta.len() > 0);
            }
        }
    }
    if !found {
        return Err("No ready local graph tiles or tile extract in the selected region build".into());
    }
    Ok(config)
}

#[derive(Debug)]
enum RunnerError {
    Unavailable,
    Failed,
    TimedOut,
    OutputTooLarge,
    InvalidResponse,
}

impl RunnerError {
    fn category(&self) -> &'static str {
        match self {
            Self::Unavailable => "engine_unavailable",
            Self::Failed => "valhalla_nonzero_exit",
            Self::TimedOut => "timeout",
            Self::OutputTooLarge => "output_limit",
            Self::InvalidResponse => "invalid_valhalla_json",
        }
    }
}

fn valhalla_result(
    program: &Path, config: &Path, request: &Value, timeout: Duration
) -> Result<Value, RunnerError> {
    let mut child = Command::new(program)
        .arg(config).arg("route").arg(request.to_string())
        .stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::null())
        .spawn().map_err(|_| RunnerError::Unavailable)?;
    let stdout = child.stdout.take().ok_or(RunnerError::Unavailable)?;
    // Drain on a separate thread to prevent child stdout-pipe deadlocks.
    let reader = thread::spawn(move || {
        let mut buffer = Vec::new();
        let _ = stdout.take(MAX_STDOUT + 1).read_to_end(&mut buffer);
        buffer
    });
    let deadline = Instant::now() + timeout;
    let exit = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(20)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = reader.join();
                return Err(RunnerError::TimedOut);
            }
        }
    };
    let bytes = reader.join().map_err(|_| RunnerError::InvalidResponse)?;
    if bytes.len() as u64 > MAX_STDOUT {
        return Err(RunnerError::OutputTooLarge);
    }
    if !exit.success() {
        return Err(RunnerError::Failed);
    }
    serde_json::from_slice(&bytes).map_err(|_| RunnerError::InvalidResponse)
}

fn haversine_meters(lat_a: f64, lng_a: f64, lat_b: f64, lng_b: f64) -> f64 {
    let r = 6_371_000.0;
    let d_lat = (lat_b - lat_a).to_radians();
    let d_lng = (lng_b - lng_a).to_radians();
    let a = (d_lat / 2.0).sin().powi(2)
        + lat_a.to_radians().cos() * lat_b.to_radians().cos() * (d_lng / 2.0).sin().powi(2);
    2.0 * r * a.sqrt().min(1.0).asin()
}

fn sane_distance(v: &Value, pointer: &str) -> Option<f64> {
    v.pointer(pointer).and_then(Value::as_f64).filter(|n| n.is_finite() && *n >= 0.0)
}

fn base_result(probe: &RouteProbe, elapsed_ms: u128) -> Value {
    json!({
        "schema": SCHEMA,
        "operation": "verify_route",
        "regionId": probe.region_id,
        "costing": probe.costing,
        "requested": {
            "start":{"lat":probe.start_lat,"lng":probe.start_lng},
            "end":{"lat":probe.end_lat,"lng":probe.end_lng}
        },
        "elapsedMs":elapsed_ms,
        "engine":"local_valhalla_service",
        "graphSource":"local_working_graph",
        "routeReplayed":true,
        "retainedPackHashVerified":false,
        "crossRegionProof":false,
        "readOnly":true
    })
}

fn evaluate(probe: &RouteProbe, reply: Value, elapsed_ms: u128) -> Value {
    let mut result = base_result(probe, elapsed_ms);
    let status = reply.pointer("/trip/status").and_then(Value::as_i64);
    if status != Some(0) {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("valhalla_route_status");
        return result;
    }
    let Some(length) = sane_distance(&reply, "/trip/summary/length") else {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("missing_route_summary");
        return result;
    };
    let Ok(geometry) = crate::route_geometry(&reply) else {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("invalid_route_shape");
        return result;
    };
    let Some(points) = geometry.get("coordinates").and_then(Value::as_array) else {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("invalid_route_shape");
        return result;
    };
    let Some(first) = points.first().and_then(Value::as_array) else { unreachable!() };
    let Some(last) = points.last().and_then(Value::as_array) else { unreachable!() };
    let (Some(a_lng), Some(a_lat), Some(b_lng), Some(b_lat)) = (
        first.first().and_then(Value::as_f64), first.get(1).and_then(Value::as_f64),
        last.first().and_then(Value::as_f64), last.get(1).and_then(Value::as_f64)
    ) else {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("invalid_route_shape");
        return result;
    };
    if ![a_lat,a_lng,b_lat,b_lng].into_iter().all(f64::is_finite) {
        result["passed"] = json!(false);
        result["failureCategory"] = json!("invalid_route_shape");
        return result;
    }
    let start_offset = haversine_meters(probe.start_lat,probe.start_lng,a_lat,a_lng);
    let end_offset = haversine_meters(probe.end_lat,probe.end_lng,b_lat,b_lng);
    let passed = start_offset <= MAX_SNAP_METERS && end_offset <= MAX_SNAP_METERS;
    result["passed"] = json!(passed);
    result["failureCategory"] = if passed { Value::Null } else { json!("route_endpoints_mismatch") };
    result["route"] = json!({
        "distanceKm":length,
        "durationSeconds":sane_distance(&reply, "/trip/summary/time"),
        "vertexCount":points.len(),
        "startOffsetMeters":start_offset,
        "endOffsetMeters":end_offset,
        "maxAcceptedEndpointOffsetMeters":MAX_SNAP_METERS,
        "geometryDecoded":true
    });
    result
}

/// Explicitly invoked: no temporary files, source downloads, graph edits or publication.
pub fn verify_route(workspace: &Path, probe: &RouteProbe) -> Result<Value, String> {
    probe.validate()?;
    let config = checked_config(workspace, &probe.region_id)?;
    let request = crate::valhalla_route_request(
        probe.start_lat,probe.start_lng,probe.end_lat,probe.end_lng,&probe.costing,None);
    let started = Instant::now();
    let response = valhalla_result(Path::new("valhalla_service"),&config,&request,TIMEOUT);
    let elapsed = started.elapsed().as_millis();
    Ok(match response {
        Ok(reply) => evaluate(probe,reply,elapsed),
        Err(error) => {
            let mut result = base_result(probe,elapsed);
            result["passed"] = json!(false);
            result["failureCategory"] = json!(error.category());
            result
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime,UNIX_EPOCH};

    struct Temp(PathBuf);
    impl Temp {
        fn new() -> Self {
            let n=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let p=std::env::temp_dir().join(format!("graph-studio-ai-m3-{}-{n}",std::process::id()));
            fs::create_dir(&p).unwrap();
            Self(p)
        }
    }
    impl Drop for Temp { fn drop(&mut self) { let _=fs::remove_dir_all(&self.0); } }

    fn probe() -> RouteProbe {
        RouteProbe { region_id:"test-region".into(),start_lat:0.0,start_lng:0.0,
            end_lat:0.01,end_lng:0.01,costing:"motorcycle".into() }
    }

    fn encode(points:&[(f64,f64)]) -> String {
        let mut out=String::new();
        let (mut last_lat, mut last_lng)=(0_i64,0_i64);
        for &(lat,lng) in points {
            let (new_lat,new_lng)=((lat*1_000_000.0).round() as i64,(lng*1_000_000.0).round() as i64);
            for diff in [new_lat-last_lat,new_lng-last_lng] {
                let mut n=if diff<0 { (!(diff<<1)) as u64 } else { (diff<<1) as u64 };
                while n>=32 { out.push(char::from_u32(((n&31)|32) as u32+63).unwrap());n>>=5;}
                out.push(char::from_u32(n as u32+63).unwrap());
            }
            last_lat=new_lat;last_lng=new_lng;
        }
        out
    }

    #[test]
    fn reject_bad_identifiers_costing_and_coordinates() {
        let mut p=probe();
        p.region_id="../secrets".into();assert!(p.validate().is_err());
        p=probe();p.costing="shell".into();assert!(p.validate().is_err());
        p=probe();p.start_lat=f64::NAN;assert!(p.validate().is_err());
        p=probe();p.end_lng=0.0;p.end_lat=0.0;assert!(p.validate().is_err());
        assert!(RouteProbe::from_cli(&[]).is_err());
        assert!(RouteProbe::from_cli(&["a".into(),"not_a_number".into(),"0".into(),"1".into(),"1".into(),"auto".into()]).is_err());
    }

    #[test]
    fn checks_true_route_endpoints_from_valhalla_shape() {
        let p=probe();
        let reply=json!({"trip":{"status":0,"summary":{"length":1.5,"time":145.0},
            "legs":[{"shape":encode(&[(0.0,0.0),(0.01,0.01)])}]}});
        let out=evaluate(&p,reply,3);
        assert_eq!(out["passed"],true);
        assert_eq!(out["route"]["vertexCount"],2);
        assert_eq!(out["crossRegionProof"],false);
        assert!(out.get("response").is_none());
        let far=json!({"trip":{"status":0,"summary":{"length":1.5},
            "legs":[{"shape":encode(&[(0.0,0.0),(0.005,0.005)])}]}});
        let bad=evaluate(&p,far,3);
        assert_eq!(bad["passed"],false);
        assert_eq!(bad["failureCategory"],"route_endpoints_mismatch");
    }

    #[test]
    fn reject_invalid_and_empty_valhalla_results() {
        let p=probe();
        let a=evaluate(&p,json!({"trip":{"status":442}}),0);
        assert_eq!(a["failureCategory"],"valhalla_route_status");
        let b=evaluate(&p,json!({"trip":{"status":0,"summary":{"length":1.0}}}),0);
        assert_eq!(b["failureCategory"],"invalid_route_shape");
    }

    #[test]
    fn missing_graph_does_not_create_workspace() {
        let t=Temp::new();
        let root=t.0.join("missing");
        assert!(verify_route(&root,&probe()).is_err());
        assert!(!root.exists());
    }

    #[test]
    fn only_existing_graph_with_matching_local_tiles_is_accepted() {
        let t=Temp::new();
        let region=t.0.join("work/test-region/build");
        fs::create_dir_all(&region).unwrap();
        let outsider=t.0.join("outside");fs::create_dir(&outsider).unwrap();
        fs::write(region.join("valhalla.json"),
            format!(r#"{{"mjolnir":{{"tile_dir":"{}"}}}}"#,outsider.display())).unwrap();
        assert!(checked_config(&t.0,"test-region").is_err());
        let tiles=region.join("tiles");fs::create_dir(&tiles).unwrap();
        fs::write(region.join("valhalla.json"),
            format!(r#"{{"mjolnir":{{"tile_dir":"{}"}}}}"#,tiles.display())).unwrap();
        assert!(checked_config(&t.0,"test-region").is_ok());
    }

    #[cfg(unix)]
    #[test]
    fn timeout_kills_process_without_shell_execution() {
        use std::os::unix::fs::PermissionsExt;
        let t=Temp::new();
        let file=t.0.join("fake-valhalla");
        fs::write(&file,"#!/bin/sh\nsleep 2\n").unwrap();
        let mut mode=fs::metadata(&file).unwrap().permissions();mode.set_mode(0o700);
        fs::set_permissions(&file,mode).unwrap();
        let start=Instant::now();
        let err=valhalla_result(&file,Path::new("unused"),&json!({}),
            Duration::from_millis(60)).unwrap_err();
        assert!(matches!(err,RunnerError::TimedOut));
        // A shell may leave a sleeping grandchild holding stdout after the
        // shell is killed. This test only proves direct-child cancellation.
        assert!(start.elapsed() < Duration::from_secs(4));
    }
}
