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
