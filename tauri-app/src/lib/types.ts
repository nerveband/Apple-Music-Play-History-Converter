export interface FileInfo {
    path: string;
    name: string;
    size: number;
    rowCount: number;
    fileType: string;
}

export interface SearchProgress {
    current: number;
    total: number;
    found: number;
    missing: number;
    provider: string;
    status: string;
    currentTrack?: string;
    elapsedSeconds?: number;
    estimatedRemainingSeconds?: number;
}

export interface SearchPaused {
    paused: boolean;
}

export interface SearchStopped {
    current: number;
    total: number;
    found: number;
    missing: number;
}

export interface SidecarError {
    error: string;
    context: string;
}

export interface DatabaseStatus {
    downloaded: boolean;
    trackCount: number;
    size: string;
    lastUpdated: string;
    optimized: boolean;
}

export interface LogEntry {
    type: "info" | "success" | "error" | "warning" | "track";
    message: string;
    timestamp: Date;
}

export type SearchProvider = "musicbrainz" | "musicbrainz_api" | "itunes" | "apple_music";
export type ExportFormat = "lastfm" | "listenbrainz" | "spotify" | "universal";

export const EXPORT_FORMATS: Record<ExportFormat, { name: string; ext: string; description: string }> = {
    lastfm: { name: "Last.fm CSV", ext: ".csv", description: "Compatible with Universal Scrobbler" },
    listenbrainz: { name: "ListenBrainz JSON", ext: ".json", description: "Direct import to ListenBrainz" },
    spotify: { name: "Spotify CSV", ext: ".csv", description: "Spotify-compatible format" },
    universal: { name: "Universal CSV", ext: ".csv", description: "All data preserved" },
};

export const PROVIDERS: Record<SearchProvider, { name: string; description: string; requiresDb?: boolean }> = {
    musicbrainz: { name: "MusicBrainz (Local DB)", description: "Offline database, ~2GB download", requiresDb: true },
    musicbrainz_api: { name: "MusicBrainz API", description: "Online, 1 request/second limit" },
    itunes: { name: "iTunes API", description: "Online, good for Apple Music tracks" },
    apple_music: { name: "Apple Music API", description: "Best accuracy, requires credentials" },
};
