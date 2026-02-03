import { useState } from "react";
import { MagnifyingGlass, Play, Pause, Stop, CheckCircle, XCircle, Clock } from "@phosphor-icons/react";
import { Button } from "./ui/Button";
import { Progress } from "./ui/Progress";
import { SearchProgress, PROVIDERS, SearchProvider, ExportFormat } from "../lib/types";
import { startSearch, stopSearch, togglePause, exportResults } from "../lib/commands";
import { save } from "@tauri-apps/plugin-dialog";

interface ResultsPanelProps {
    progress: SearchProgress | null;
    provider: SearchProvider;
    isSearching: boolean;
    isPaused: boolean;
    filePath: string;
    onSearchStatusChange: (searching: boolean, paused: boolean) => void;
    exportFormat: ExportFormat;
}

export function ResultsPanel({
    progress,
    provider,
    isSearching,
    isPaused,
    filePath,
    onSearchStatusChange,
    exportFormat
}: ResultsPanelProps) {
    const [exporting, setExporting] = useState(false);

    const handleStart = async () => {
        onSearchStatusChange(true, false);
        try {
            await startSearch(filePath, provider);
        } catch (err) {
            console.error(err);
            onSearchStatusChange(false, false);
        }
    };

    const handleTogglePause = async () => {
        const paused = await togglePause();
        onSearchStatusChange(true, paused);
    };

    const handleStop = async () => {
        await stopSearch();
        onSearchStatusChange(false, false);
    };

    const handleExport = async () => {
        if (!progress || progress.found === 0) return;
        setExporting(true);
        try {
            const outputPath = await save({
                filters: [{
                    name: "Export File",
                    extensions: ["csv", "json"]
                }],
                defaultPath: "converted_history"
            });

            if (outputPath) {
                await exportResults(exportFormat, outputPath);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setExporting(false);
        }
    };

    if (!isSearching && !progress) {
        return (
            <div className="p-4 border-b border-border bg-foreground-5/30">
                <Button onClick={handleStart} icon={<MagnifyingGlass size={18} />}>
                    Search with {PROVIDERS[provider].name}
                </Button>
            </div>
        );
    }

    return (
        <div className="p-4 border-b border-border bg-foreground-5/30 space-y-4">
            <div className="flex items-center gap-4">
                {isSearching && (
                    <>
                        <Button
                            variant="secondary"
                            onClick={handleTogglePause}
                            icon={isPaused ? <Play size={18} /> : <Pause size={18} />}
                        >
                            {isPaused ? "Resume" : "Pause"}
                        </Button>
                        <Button variant="ghost" onClick={handleStop} icon={<Stop size={18} />}>
                            Stop
                        </Button>
                    </>
                )}
            </div>

            {progress && (
                <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                    <div className="flex justify-between text-sm">
                        <span className="font-medium text-muted-foreground">{progress.status}</span>
                        <span className="font-bold">
                            {progress.current.toLocaleString()} / {progress.total.toLocaleString()}
                        </span>
                    </div>

                    <Progress value={(progress.current / progress.total) * 100} />

                    <div className="flex flex-wrap gap-4 text-sm mt-2">
                        <span className="flex items-center gap-1 text-success">
                            <CheckCircle size={16} weight="fill" />
                            <strong>{progress.found.toLocaleString()}</strong> found
                        </span>
                        <span className="flex items-center gap-1 text-destructive">
                            <XCircle size={16} weight="fill" />
                            <strong>{progress.missing.toLocaleString()}</strong> missing
                        </span>
                        {progress.estimatedRemainingSeconds !== undefined && (
                            <span className="flex items-center gap-1 text-muted-foreground ml-auto">
                                <Clock size={16} />
                                ETA: {formatTime(progress.estimatedRemainingSeconds)}
                            </span>
                        )}
                    </div>

                    {progress.currentTrack && (
                        <div className="text-xs text-muted-foreground truncate font-mono bg-background/50 p-1 rounded">
                            {progress.currentTrack}
                        </div>
                    )}
                </div>
            )}

            {progress && progress.found > 0 && !isSearching && (
                <div className="pt-2 border-t border-border/50">
                    <Button
                        onClick={handleExport}
                        loading={exporting}
                        className="w-full"
                    >
                        Export {progress.found.toLocaleString()} Tracks
                    </Button>
                </div>
            )}
        </div>
    );
}

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
}
