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
    roadpilot_graph_studio_lib::run();
}
