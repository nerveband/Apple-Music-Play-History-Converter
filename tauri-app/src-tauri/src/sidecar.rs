use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{Emitter, WebviewWindow};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SearchPaused {
    pub paused: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SearchStopped {
    pub current: usize,
    pub total: usize,
    pub found: usize,
    pub missing: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CsvPreview {
    pub path: String,
    pub rows: Vec<Vec<String>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CsvLoaded {
    pub success: bool,
    #[serde(rename = "rowCount")]
    pub row_count: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SidecarError {
    pub error: String,
    pub context: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SidecarStatus {
    pub status: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(tag = "type")]
pub enum SidecarMessage {
    #[serde(rename = "ready")]
    Ready { version: String },
    #[serde(rename = "progress")]
    Progress(crate::SearchProgress),
    #[serde(rename = "fileAnalysis")]
    FileAnalysis(crate::FileInfo),
    #[serde(rename = "searchComplete")]
    SearchComplete {
        total: usize,
        found: usize,
        missing: usize,
        provider: String,
    },
    #[serde(rename = "searchPaused")]
    SearchPaused(SearchPaused),
    #[serde(rename = "searchStopped")]
    SearchStopped(SearchStopped),
    #[serde(rename = "error")]
    Error(SidecarError),
    #[serde(rename = "status")]
    Status(SidecarStatus),
    #[serde(rename = "databaseStatus")]
    DatabaseStatus(crate::DatabaseStatus),
    #[serde(rename = "csvPreview")]
    CsvPreview(CsvPreview),
    #[serde(rename = "csvLoaded")]
    CsvLoaded(CsvLoaded),
    #[serde(rename = "pong")]
    Pong,
    #[serde(other)]
    Unknown,
}

pub struct SidecarManager {
    process: Option<Child>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self { process: None }
    }

    pub fn start(&mut self, window: WebviewWindow) -> Result<(), String> {
        // Path to sidecar - adjusting for dev vs prod would happen here
        // For now, assuming dev environment structure relative to src-tauri
        let mut command = Command::new("python3");
        command
            .arg("../python-sidecar/sidecar.py") // Adjust path as needed
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = command.spawn().map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

        let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
        let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

        // Spawn thread to read stdout
        let window_clone = window.clone();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(l) => {
                        // Try to parse as JSON first
                        if let Ok(msg) = serde_json::from_str::<SidecarMessage>(&l) {
                            match msg {
                                SidecarMessage::Progress(p) => {
                                    let _ = window_clone.emit("search_progress", p);
                                }
                                SidecarMessage::DatabaseStatus(s) => {
                                    let _ = window_clone.emit("database_status", s);
                                }
                                SidecarMessage::SearchComplete { total, found, missing, provider } => {
                                    let _ = window_clone.emit("search_progress", crate::SearchProgress {
                                        current: total,
                                        total,
                                        found,
                                        missing,
                                        provider,
                                        status: "Complete".to_string(),
                                        current_track: None,
                                        elapsed_seconds: None,
                                        estimated_remaining_seconds: None,
                                    });
                                }
                                SidecarMessage::SearchPaused(p) => {
                                    let _ = window_clone.emit("search_paused", p);
                                }
                                SidecarMessage::SearchStopped(s) => {
                                    let _ = window_clone.emit("search_stopped", s);
                                }
                                SidecarMessage::Error(e) => {
                                    let _ = window_clone.emit("sidecar_error", e);
                                }
                                SidecarMessage::Status(s) => {
                                    let _ = window_clone.emit("sidecar_status", s);
                                }
                                SidecarMessage::FileAnalysis(f) => {
                                    let _ = window_clone.emit("file_analysis", f);
                                }
                                SidecarMessage::CsvPreview(p) => {
                                    let _ = window_clone.emit("csv_preview", p);
                                }
                                SidecarMessage::CsvLoaded(l) => {
                                    let _ = window_clone.emit("csv_loaded", l);
                                }
                                _ => {
                                    println!("[Sidecar] JSON: {:?}", msg);
                                }
                            }
                        } else {
                            println!("[Sidecar] {}", l);
                        }
                    }
                    Err(e) => eprintln!("Error reading sidecar stdout: {}", e),
                }
            }
        });

        // Spawn thread to read stderr
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(l) = line {
                    eprintln!("[Sidecar Error] {}", l);
                }
            }
        });

        self.process = Some(child);
        Ok(())
    }

    pub fn send(&mut self, msg: serde_json::Value) -> Result<(), String> {
        if let Some(child) = &mut self.process {
            if let Some(stdin) = &mut child.stdin {
                let json = serde_json::to_string(&msg).map_err(|e| e.to_string())?;
                writeln!(stdin, "{}", json).map_err(|e| e.to_string())?;
                return Ok(());
            }
        }
        Err("Sidecar not running or stdin not available".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::SidecarMessage;

    #[test]
    fn parses_pause_message() {
        let json = r#"{"type":"searchPaused","paused":true}"#;
        let msg: SidecarMessage = serde_json::from_str(json).unwrap();
        match msg {
            SidecarMessage::SearchPaused(p) => assert!(p.paused),
            _ => panic!("wrong variant"),
        }
    }
}
