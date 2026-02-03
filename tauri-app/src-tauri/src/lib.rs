use std::sync::Mutex;
use tauri::{State, Window, Manager};
use serde::{Deserialize, Serialize};

mod sidecar;
use sidecar::SidecarManager;

// Shared Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileInfo {
    pub path: String,
    pub name: String,
    pub size: u64,
    #[serde(rename = "rowCount")]
    pub row_count: usize,
    #[serde(rename = "fileType")]
    pub file_type: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SearchProgress {
    pub current: usize,
    pub total: usize,
    pub found: usize,
    pub missing: usize,
    pub provider: String,
    pub status: String,
    #[serde(rename = "currentTrack")]
    pub current_track: Option<String>,
    #[serde(rename = "elapsedSeconds")]
    pub elapsed_seconds: Option<f64>,
    #[serde(rename = "estimatedRemainingSeconds")]
    pub estimated_remaining_seconds: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DatabaseStatus {
    pub downloaded: bool,
    #[serde(rename = "trackCount")]
    pub track_count: usize,
    pub size: String,
    #[serde(rename = "lastUpdated")]
    pub last_updated: String,
    pub optimized: bool,
}

pub struct AppState {
    pub sidecar: Mutex<SidecarManager>,
}

#[tauri::command]
async fn analyze_csv(
    state: State<'_, AppState>,
    path: String,
) -> Result<FileInfo, String> {
    // For fast feedback, we can still analyze basic file stats in Rust
    // But for full consistency, we should ask the sidecar
    // For now, let's keep the Rust implementation for speed but structured correctly
    
    let path_buf = std::path::PathBuf::from(&path);
    if !path_buf.exists() {
        return Err(format!("File not found: {}", path));
    }
    
    let file_name = path_buf.file_name().unwrap().to_string_lossy().to_string();
    let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    
    // Simple line count
    let file = std::fs::File::open(&path).map_err(|e| e.to_string())?;
    let reader = std::io::BufReader::new(file);
    let row_count = std::io::BufRead::lines(reader).count().saturating_sub(1);
    
    Ok(FileInfo {
        path,
        name: file_name,
        size: metadata.len(),
        row_count,
        file_type: "Unknown".to_string(), // Better detection logic could live here or in sidecar
    })
}

#[tauri::command]
async fn start_search(
    state: State<'_, AppState>,
    file_path: String,
    provider: String,
) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    
    // First load csv
    sidecar.send(serde_json::json!({
        "action": "loadCSV",
        "path": file_path
    }))?;
    
    // Then start search
    sidecar.send(serde_json::json!({
        "action": "startSearch",
        "provider": provider
    }))?;
    
    Ok(())
}

#[tauri::command]
async fn stop_search(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "stopSearch" }))?;
    Ok(())
}

#[tauri::command]
async fn toggle_pause(state: State<'_, AppState>) -> Result<bool, String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "pauseSearch" }))?;
    // logic to get actual state would be async/complex, blindly returning toggle for now
    Ok(true) 
}

#[tauri::command]
async fn export_results(
    state: State<'_, AppState>,
    format: String,
    output_path: String,
) -> Result<String, String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({
        "action": "export",
        "format": format,
        "path": output_path
    }))?;
    Ok(output_path)
}

#[tauri::command]
async fn get_database_status(state: State<'_, AppState>) -> Result<DatabaseStatus, String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "getDatabaseStatus" }))?;
    
    // Mock return for immediate UI pending async update event
    Ok(DatabaseStatus {
        downloaded: false,
        track_count: 0,
        size: "0 B".into(),
        last_updated: "Never".into(),
        optimized: false
    })
}

#[tauri::command]
async fn set_settings(state: State<'_, AppState>, settings: serde_json::Value) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({
        "action": "setSettings",
        "settings": settings
    }))?;
    Ok(())
}

#[tauri::command]
async fn download_database(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "downloadDatabase" }))?;
    Ok(())
}

#[tauri::command]
async fn delete_database(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "deleteDatabase" }))?;
    Ok(())
}

#[tauri::command]
async fn check_database_updates(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "checkDatabaseUpdates" }))?;
    Ok(())
}

#[tauri::command]
async fn check_itunes_status(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "checkItunesStatus" }))?;
    Ok(())
}

#[tauri::command]
async fn get_log_dir(app: tauri::AppHandle) -> Result<String, String> {
    let dir = app.path().app_log_dir().map_err(|e| e.to_string())?;
    Ok(dir.to_string_lossy().to_string())
}

#[tauri::command]
async fn clear_cache(app: tauri::AppHandle) -> Result<(), String> {
    let dir = app.path().app_cache_dir().map_err(|e| e.to_string())?;
    if dir.exists() {
        std::fs::remove_dir_all(&dir).map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn initialize_sidecar(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar = state.sidecar.lock().map_err(|_| "Failed to lock sidecar")?;
    sidecar.send(serde_json::json!({ "action": "initialize" }))?;
    Ok(())
}

#[tauri::command]
async fn get_csv_preview(
    state: State<'_, AppState>,
    path: String,
) -> Result<Vec<Vec<String>>, String> {
    // We'll read the file directly in Rust for speed instead of asking sidecar,
    // since it's just a simple head operation.
    // OR we can ask sidecar. Let's ask sidecar to ensure consistency with pandas parsing?
    // Actually, for a quick preview, Rust CSV crate is faster and simpler.
    // Let's stick to doing it here to show hybrid power.
    
    let file = std::fs::File::open(&path).map_err(|e| e.to_string())?;
    let mut rdr = csv::ReaderBuilder::new()
        .has_headers(false) // Validation: we want to read headers as first row? No, Table usually takes headers separately.
        // Let's use flexible mode
        .from_reader(file);

    let mut rows = Vec::new();
    // Read header
    // But wait, the frontend Table expects data rows.
    // Let's just read the first 5 records.
    
    for result in rdr.records().take(5) {
        let record = result.map_err(|e| e.to_string())?;
        let row: Vec<String> = record.iter().map(|s| s.to_string()).collect();
        rows.push(row);
    }
    
    Ok(rows)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            sidecar: Mutex::new(SidecarManager::new()),
        })
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();
            let state = app.state::<AppState>();
            let mut sidecar = state.sidecar.lock().unwrap();
            
            // Start the sidecar
            if let Err(e) = sidecar.start(window) {
                eprintln!("Failed to start sidecar: {}", e);
            }
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            analyze_csv,
            start_search,
            stop_search,
            toggle_pause,
            export_results,
            export_results,
            get_database_status,
            get_csv_preview,
            initialize_sidecar,
            set_settings,
            download_database,
            delete_database,
            check_database_updates,
            check_itunes_status,
            get_log_dir,
            clear_cache
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
