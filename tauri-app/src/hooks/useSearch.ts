import { useState, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { SearchProgress } from "../lib/types";
import { SearchPaused, SearchStopped } from "../lib/types";

export function useSearch(isTauri: boolean) {
    const [progress, setProgress] = useState<SearchProgress | null>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (!isTauri) return;

        const unlistenProgress = listen<SearchProgress>("search_progress", (event) => {
            setProgress(event.payload);
            if (event.payload.status === "Complete") {
                setIsSearching(false);
                setIsPaused(false);
            }
        });

        const unlistenPaused = listen<SearchPaused>("search_paused", (event) => {
            setIsPaused(event.payload.paused);
        });

        const unlistenStopped = listen<SearchStopped>("search_stopped", () => {
            setIsSearching(false);
            setIsPaused(false);
        });

        return () => {
            unlistenProgress.then((fn) => fn());
            unlistenPaused.then((fn) => fn());
            unlistenStopped.then((fn) => fn());
        };
    }, [isTauri]);

    const handleStatusChange = (searching: boolean, paused: boolean) => {
        setIsSearching(searching);
        setIsPaused(paused);
    };

    const resetProgress = () => {
        setProgress(null);
        setIsSearching(false);
        setIsPaused(false);
    };

    return {
        progress,
        isSearching,
        isPaused,
        handleStatusChange,
        resetProgress,
        setProgress // Exposed for manual updates if needed
    };
}
