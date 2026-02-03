import { invoke } from "@tauri-apps/api/core";
import { FileInfo, DatabaseStatus } from "./types";

// Wrapper for Tauri invoke to ensure type safety
export async function analyzeCsv(path: string): Promise<FileInfo> {
    return await invoke<FileInfo>("analyze_csv", { path });
}

export async function startSearch(filePath: string, provider: string): Promise<void> {
    return await invoke("start_search", { filePath, provider });
}

export async function stopSearch(): Promise<void> {
    return await invoke("stop_search");
}

export async function togglePause(): Promise<boolean> {
    return await invoke("toggle_pause");
}

export async function exportResults(format: string, outputPath: string): Promise<string> {
    return await invoke("export_results", { format, outputPath });
}

export async function getDatabaseStatus(): Promise<DatabaseStatus> {
    return await invoke("get_database_status");
}

export async function initializeSidecar(): Promise<void> {
    return await invoke("initialize_sidecar");
}

export async function getCsvPreview(path: string): Promise<string[][]> {
    return await invoke<string[][]>("get_csv_preview", { path });
}

export async function setSettings(settings: Record<string, unknown>): Promise<void> {
    return await invoke("set_settings", { settings });
}

export async function downloadDatabase(): Promise<void> {
    return await invoke("download_database");
}

export async function deleteDatabase(): Promise<void> {
    return await invoke("delete_database");
}

export async function checkDatabaseUpdates(): Promise<void> {
    return await invoke("check_database_updates");
}

export async function checkItunesStatus(): Promise<void> {
    return await invoke("check_itunes_status");
}

export async function getLogDir(): Promise<string> {
    return await invoke<string>("get_log_dir");
}

export async function clearCache(): Promise<void> {
    return await invoke("clear_cache");
}
