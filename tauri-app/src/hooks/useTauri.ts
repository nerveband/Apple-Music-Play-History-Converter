import { useState, useEffect } from "react";

export function useTauri() {
    const [isTauri, setIsTauri] = useState(false);

    useEffect(() => {
        if (typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined) {
            setIsTauri(true);
        }
    }, []);

    return isTauri;
}
