import { useState } from "react";
import { File, Spinner } from "@phosphor-icons/react";
import { open } from "@tauri-apps/plugin-dialog";
import { useTauri } from "../hooks/useTauri";
import { analyzeCsv } from "../lib/commands";
import { FileInfo } from "../lib/types";

interface FileSelectionProps {
    onFileSelect: (info: FileInfo) => void;
    onClear: () => void;
    currentFile: FileInfo | null;
    disabled?: boolean;
}

export function FileSelection({ onFileSelect, onClear, currentFile, disabled }: FileSelectionProps) {
    const isTauri = useTauri();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSelect = async () => {
        if (!isTauri) {
            setError("Please use the native Tauri app to select files.");
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const selected = await open({
                multiple: false,
                filters: [{ name: "CSV Files", extensions: ["csv"] }],
            });

            if (selected && typeof selected === "string") {
                const info = await analyzeCsv(selected);
                onFileSelect(info);
            }
        } catch (err) {
            console.error(err);
            setError(`Failed to load file: ${err}`);
        } finally {
            setLoading(false);
        }
    };

    if (currentFile) {
        return (
            <div className="p-4 rounded-xl border border-border bg-foreground-5/30 animate-in fade-in slide-in-from-top-2">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="font-medium flex items-center gap-2">
                            <File size={20} className="text-accent" />
                            {currentFile.name}
                        </h3>
                        <div className="mt-2 flex flex-wrap gap-3 text-sm text-muted-foreground">
                            <span><strong>{currentFile.rowCount.toLocaleString()}</strong> tracks</span>
                            <span>{formatFileSize(currentFile.size)}</span>
                            <span className="px-2 py-0.5 rounded-md bg-accent/10 text-accent text-xs font-medium">
                                {currentFile.fileType}
                            </span>
                        </div>
                    </div>
                    <button
                        onClick={onClear}
                        className="text-muted-foreground hover:text-foreground transition-colors p-1"
                        disabled={disabled}
                    >
                        ✕
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div>
            <button
                onClick={handleSelect}
                disabled={loading || disabled || !isTauri}
                className="w-full h-32 border-2 border-dashed border-border rounded-xl
                   flex flex-col items-center justify-center gap-2
                   hover:border-accent hover:bg-foreground-5/50 transition-all cursor-pointer
                   disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-accent"
            >
                {loading ? (
                    <Spinner size={32} className="animate-spin text-accent" />
                ) : (
                    <>
                        <File size={32} className="text-muted-foreground group-hover:text-accent transition-colors" />
                        <span className="text-base font-medium">Select CSV File</span>
                        <span className="text-xs text-muted-foreground">
                            Play Activity, Recently Played, or Play History Daily Tracks
                        </span>
                    </>
                )}
            </button>
            {error && <p className="mt-2 text-sm text-destructive text-center">{error}</p>}
        </div>
    );
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
