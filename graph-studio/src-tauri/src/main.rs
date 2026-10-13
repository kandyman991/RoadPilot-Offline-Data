#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // The packaged desktop executable also provides an explicitly read-only
    // headless interface; it never starts Tauri or a local listener in this mode.
    if let Some(first) = std::env::args().nth(1) {
        let command = match first.as_str() {
            "--ai-capabilities" => Some("capabilities"),
            "--ai-inspect" => Some("inspect"),
            "--ai-diagnose" => Some("diagnose"),
            _ => None,
        };
        if let Some(command) = command {
            if std::env::args().len() != 2 {
                eprintln!("AI inspection commands do not accept arguments.");
                std::process::exit(2);
            }
            let Some(home) = std::env::var_os("HOME") else {
                eprintln!("Cannot find the Graph Studio workspace: HOME is not set.");
                std::process::exit(2);
            };
            let root = std::path::PathBuf::from(home).join("RoadPilotGraphStudio");
            match roadpilot_graph_studio_lib::ai_control::execute(&root, command, None) {
                Ok(value) => {
                    println!("{}", serde_json::to_string_pretty(&value).expect("serializable inspection result"));
                    return;
                }
                Err(error) => {
                    eprintln!("{error}");
                    std::process::exit(2);
                }
            }
        }
    }
    if std::env::args().nth(1).as_deref() == Some("--ai-verify-route") {
        let args: Vec<String> = std::env::args().skip(2).collect();
        let result = (|| -> Result<serde_json::Value, String> {
            let probe = roadpilot_graph_studio_lib::ai_verify::RouteProbe::from_cli(&args)?;
            let home = std::env::var_os("HOME").ok_or("HOME is not set")?;
            let workspace = std::path::PathBuf::from(home).join("RoadPilotGraphStudio");
            roadpilot_graph_studio_lib::ai_verify::verify_route(&workspace, &probe)
        })();
        match result {
            Ok(value) => {
                println!("{}", serde_json::to_string_pretty(&value).expect("serializable verification result"));
                if value.get("passed").and_then(serde_json::Value::as_bool) != Some(true) {
                    std::process::exit(1);
                }
                return;
            }
            Err(error) => {
                eprintln!("{error}");
                std::process::exit(2);
            }
        }
    }
    roadpilot_graph_studio_lib::run();
}
