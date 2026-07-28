import { useState, useEffect, useRef } from "react";
import { AccordionSection } from "../ui/Accordion";
import { SearchProvider, ExportFormat, PROVIDERS, EXPORT_FORMATS, ITUNES_COUNTRIES, AppleMusicStatus } from "../../lib/types";
import { Warning, GlobeSimple, Key, TestTube, CheckCircle, XCircle, CaretDown, Timer, Pause, Play, Info, FolderOpen } from "@phosphor-icons/react";
import {
    configureAppleMusic,
    testAppleMusicCredentials,
    getAppleMusicStatus,
    setSettings,
    getSettings,
    checkItunesStatus,
    checkMusicBrainzApiStatus,
    checkAppleMusicApiStatus,
    restartSidecar,
} from "../../lib/commands";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { toast } from "react-toastify";

const FORMAT_PREVIEWS: Record<ExportFormat, string> = {
    lastfm: `artist,album,track,timestamp
Joe Hisaishi,Spirited Away,One Summer's Day,1704067200
Memory Tapes,Seek Magic,Bicycle,1704070800
Matchbox Twenty,Yourself or Someone Like You,Push,1704074400`,
    listenbrainz: `[
  {
    "listened_at": 1704067200,
    "track_metadata": {
      "artist_name": "Joe Hisaishi",
      "track_name": "One Summer's Day",
      "release_name": "Spirited Away"
    }
  }
]`,
    spotify: `spotify_id,track_name,artist_name,album_name,played_at
,One Summer's Day,Joe Hisaishi,Spirited Away,2024-01-01T00:00:00Z
,Bicycle,Memory Tapes,Seek Magic,2024-01-01T01:00:00Z`,
    universal: `artist,album,track,timestamp,isrc,duration_ms,provider
Joe Hisaishi,Spirited Away,One Summer's Day,1704067200,JPVI00300060,234000,apple_music
Memory Tapes,Seek Magic,Bicycle,1704070800,,198000,itunes`,
    itunes_xml: `<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>Tracks</key>
  <dict>
    <key>1</key>
    <dict>
      <key>Name</key>
      <string>One Summer's Day</string>
      <key>Artist</key>
      <string>Joe Hisaishi</string>
    </dict>
  </dict>
</dict>
</plist>`,
};

interface ServicesSectionProps {
    expanded: boolean;
    onToggle: () => void;
    provider: SearchProvider;
    setProvider: (p: SearchProvider) => void;
    exportFormat: ExportFormat;
    setExportFormat: (f: ExportFormat) => void;
    isSearching: boolean;
}

type ApiStatus = "idle" | "checking" | "ok" | "rate_limited" | "error";

const DEFAULT_PROXY_URL = "https://am-proxy.wavedepth.workers.dev";
type AppleMusicMode = "shared_proxy" | "own_credentials";

export function ServicesSection({
    expanded,
    onToggle,
    provider,
    setProvider,
    exportFormat,
    setExportFormat,
    isSearching,
}: ServicesSectionProps) {
    // Apple Music API state
    const [appleMusicStatus, setAppleMusicStatus] = useState<AppleMusicStatus | null>(null);
    const [teamId, setTeamId] = useState("");
    const [keyId, setKeyId] = useState("");
    const [keyPath, setKeyPath] = useState("");
    const [proxyUrl, setProxyUrl] = useState(DEFAULT_PROXY_URL);
    const [proxyKey, setProxyKey] = useState("");
    const [appleMusicMode, setAppleMusicMode] = useState<AppleMusicMode>("shared_proxy");
    const [showLimitsInfo, setShowLimitsInfo] = useState(false);
    const [testingCredentials, setTestingCredentials] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

    // iTunes settings
    const [itunesCountry, setItunesCountry] = useState("us");
    const [rateLimit, setRateLimit] = useState("20");
    const [rateLimitPaused, setRateLimitPaused] = useState(false);
    const [mbApiRateLimit, setMbApiRateLimit] = useState("1");
    const [previewFormat, setPreviewFormat] = useState<ExportFormat | null>(null);
    const [itunesApiStatus, setItunesApiStatus] = useState<ApiStatus>("idle");
    const [musicBrainzApiStatus, setMusicBrainzApiStatus] = useState<ApiStatus>("idle");
    const [appleMusicApiStatus, setAppleMusicApiStatus] = useState<ApiStatus>("idle");
    const [storageRoot, setStorageRoot] = useState("");
    const [savingStorage, setSavingStorage] = useState(false);

    // Load Apple Music status and auto-check all API statuses on mount
    const didInit = useRef(false);
    useEffect(() => {
        if (didInit.current) return;
        didInit.current = true;

        Promise.all([
            getAppleMusicStatus(),
            getSettings(),
        ]).catch(console.error);

        // Auto-check API statuses
        const checkStatuses = async () => {
            try {
                await checkAppleMusicApiStatus();
            } catch { /* handled by event listener */ }
            try {
                setItunesApiStatus("checking");
                await checkItunesStatus();
            } catch { /* handled by event listener */ }
            try {
                setMusicBrainzApiStatus("checking");
                await checkMusicBrainzApiStatus();
            } catch { /* handled by event listener */ }
        };
        checkStatuses();
    }, []);

    // Listen for Apple Music events
    useEffect(() => {
        const unlisteners: Promise<() => void>[] = [];

        unlisteners.push(
            listen<AppleMusicStatus>("apple_music_status", (event) => {
                setAppleMusicStatus(event.payload);
            })
        );

        unlisteners.push(
            listen<{ success: boolean; message: string }>("apple_music_test_result", (event) => {
                setTestingCredentials(false);
                setTestResult(event.payload);
                if (event.payload.success) {
                    toast.success("Apple Music API credentials verified");
                } else {
                    toast.error(`Credential test failed: ${event.payload.message}`);
                }
            })
        );

        unlisteners.push(
            listen<{ success: boolean }>("apple_music_configured", (event) => {
                if (event.payload.success) {
                    toast.success("Apple Music API credentials saved");
                    getAppleMusicStatus().catch(console.error);
                }
            })
        );

        unlisteners.push(
            listen<Record<string, unknown>>("settings_loaded", (event) => {
                const settings = event.payload;

                if (typeof settings.search_provider === "string") {
                    const nextProvider = settings.search_provider as SearchProvider;
                    if (nextProvider in PROVIDERS) {
                        setProvider(nextProvider);
                    }
                }

                if (typeof settings.itunes_country === "string") {
                    setItunesCountry(settings.itunes_country);
                }

                if (typeof settings.itunes_rate_limit === "number") {
                    setRateLimit(String(settings.itunes_rate_limit));
                }

                if (typeof settings.itunes_rate_limit === "string") {
                    setRateLimit(settings.itunes_rate_limit);
                }

                if (typeof settings.rate_limit_paused === "boolean") {
                    setRateLimitPaused(settings.rate_limit_paused);
                }

                if (typeof settings.musicbrainz_api_rate_limit === "number") {
                    setMbApiRateLimit(String(settings.musicbrainz_api_rate_limit));
                } else if (typeof settings.musicbrainz_api_rate_limit === "string") {
                    setMbApiRateLimit(settings.musicbrainz_api_rate_limit);
                }

                if (typeof settings.storage_root === "string") {
                    setStorageRoot(settings.storage_root);
                }

                if (typeof settings.apple_music_team_id === "string") {
                    setTeamId(settings.apple_music_team_id);
                }
                if (typeof settings.apple_music_key_id === "string") {
                    setKeyId(settings.apple_music_key_id);
                }
                if (typeof settings.apple_music_key_path === "string") {
                    setKeyPath(settings.apple_music_key_path);
                }
                if (typeof settings.apple_music_proxy_url === "string") {
                    setProxyUrl(settings.apple_music_proxy_url || DEFAULT_PROXY_URL);
                }
                if (typeof settings.apple_music_proxy_key === "string") {
                    setProxyKey(settings.apple_music_proxy_key);
                }
                // Detect mode: if user has local creds and no proxy (or non-default proxy), show own_credentials
                const hasLocal = settings.apple_music_team_id && settings.apple_music_key_id && settings.apple_music_key_path;
                const savedProxy = typeof settings.apple_music_proxy_url === "string" ? settings.apple_music_proxy_url : "";
                if (hasLocal && !savedProxy) {
                    setAppleMusicMode("own_credentials");
                }
            })
        );

        unlisteners.push(
            listen<{ status: string }>("sidecar_status", (event) => {
                const status = event.payload.status;
                if (status.startsWith("iTunes API:")) {
                    const normalized = status.toLowerCase();

                    if (normalized.includes("ok")) {
                        setItunesApiStatus("ok");
                    } else if (normalized.includes("rate limited")) {
                        setItunesApiStatus("rate_limited");
                    } else {
                        setItunesApiStatus("error");
                    }
                }

                if (status.startsWith("MusicBrainz API:")) {
                    const normalized = status.toLowerCase();

                    if (normalized.includes("ok")) {
                        setMusicBrainzApiStatus("ok");
                    } else if (normalized.includes("rate limited")) {
                        setMusicBrainzApiStatus("rate_limited");
                    } else {
                        setMusicBrainzApiStatus("error");
                    }
                }

                if (status.startsWith("Apple Music API:")) {
                    const normalized = status.toLowerCase();
                    if (normalized.includes("ok")) {
                        setAppleMusicApiStatus("ok");
                    } else if (normalized.includes("rate limited")) {
                        setAppleMusicApiStatus("rate_limited");
                    } else if (normalized.includes("not configured")) {
                        setAppleMusicApiStatus("idle");
                    } else {
                        setAppleMusicApiStatus("error");
                    }
                }
            })
        );

        unlisteners.push(
            listen<{ error: string; context?: string }>("sidecar_error", (event) => {
                if (event.payload.context === "check_itunes_status") {
                    setItunesApiStatus("error");
                }
                if (event.payload.context === "check_musicbrainz_api_status") {
                    setMusicBrainzApiStatus("error");
                }
            })
        );

        return () => {
            unlisteners.forEach(p => p.then(fn => fn()));
        };
    }, [setProvider]);

    const handleSaveAppleMusicConfig = async () => {
        if (appleMusicMode === "shared_proxy") {
            const url = proxyUrl.trim() || DEFAULT_PROXY_URL;
            try {
                await configureAppleMusic("", "", "", url, proxyKey.trim());
                toast.success("Apple Music configured with shared proxy");
            } catch (err) {
                console.error(err);
                toast.error("Failed to save Apple Music configuration");
            }
        } else {
            const hasLocalCreds = teamId.trim().length > 0 && keyId.trim().length > 0 && keyPath.trim().length > 0;
            if (!hasLocalCreds) {
                toast.error("Provide Team ID, Key ID, and .p8 key file path");
                return;
            }
            try {
                await configureAppleMusic(
                    teamId.trim(),
                    keyId.trim(),
                    keyPath.trim(),
                    "",
                    "",
                );
                toast.success("Apple Music configured with your credentials");
            } catch (err) {
                console.error(err);
                toast.error("Failed to save Apple Music credentials");
            }
        }
    };

    const handleTestCredentials = async () => {
        setTestingCredentials(true);
        setTestResult(null);
        try {
            await testAppleMusicCredentials();
        } catch (err) {
            console.error(err);
            setTestingCredentials(false);
            toast.error("Failed to test credentials");
        }
    };

    const hasLocalCredsInput = teamId.trim().length > 0 && keyId.trim().length > 0 && keyPath.trim().length > 0;
    const canSaveAppleMusicConfig = appleMusicMode === "shared_proxy" || hasLocalCredsInput;
    const canTestAppleMusicConfig = !testingCredentials && (appleMusicStatus?.hasCustom || appleMusicMode === "shared_proxy" || hasLocalCredsInput);

    const handleBrowseKeyFile = async () => {
        try {
            const path = await open({
                multiple: false,
                directory: false,
                filters: [{
                    name: "Private Key",
                    extensions: ["p8"]
                }]
            });
            if (path) {
                setKeyPath(path as string);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleBrowseStorage = async () => {
        try {
            const path = await open({ multiple: false, directory: true });
            if (path) setStorageRoot(path as string);
        } catch (err) {
            console.error(err);
            toast.error("Could not select the storage folder");
        }
    };

    const handleSaveStorage = async () => {
        setSavingStorage(true);
        try {
            await setSettings({ storage_root: storageRoot.trim() });
            await restartSidecar();
            toast.success(storageRoot.trim()
                ? "Storage location saved. The sidecar restarted using the new location."
                : "Default storage location restored.");
        } catch (err) {
            console.error(err);
            toast.error("Could not apply the storage location");
        } finally {
            setSavingStorage(false);
        }
    };

    const handleCountryChange = async (country: string) => {
        setItunesCountry(country);
        try {
            await setSettings({ itunes_country: country });
        } catch (err) {
            console.error(err);
        }
    };

    const handleSaveRateLimit = async () => {
        const value = parseInt(rateLimit, 10);
        if (isNaN(value) || value <= 0) {
            toast.error("Rate limit must be a positive number");
            return;
        }
        try {
            await setSettings({ itunes_rate_limit: value });
            toast.success(`Rate limit saved: ${value} req/min`);
        } catch (err) {
            console.error(err);
            toast.error("Failed to save rate limit");
        }
    };

    const handleSaveMbApiRateLimit = async () => {
        const value = parseInt(mbApiRateLimit, 10);
        if (isNaN(value) || value <= 0) {
            toast.error("Rate limit must be a positive number");
            return;
        }
        try {
            await setSettings({ musicbrainz_api_rate_limit: value });
            toast.success(`MusicBrainz API rate limit saved: ${value} req/sec`);
        } catch (err) {
            console.error(err);
            toast.error("Failed to save rate limit");
        }
    };

    const handleToggleRateLimitPause = async () => {
        const newPaused = !rateLimitPaused;
        setRateLimitPaused(newPaused);
        try {
            await setSettings({ rate_limit_paused: newPaused });
            if (newPaused) {
                toast.info("Rate limiting paused -- requests will be sent as fast as possible");
            } else {
                toast.info(`Rate limiting resumed -- using ${rateLimit} req/min`);
            }
        } catch (err) {
            console.error(err);
            setRateLimitPaused(!newPaused); // revert on error
        }
    };


    const renderStatusPill = (status: ApiStatus, message: string) => {
        if (status === "idle" || status === "checking") {
            return <span className="text-[10px] text-muted-foreground">{message}</span>;
        }

        if (status === "ok") {
            return (
                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-success/10 text-success border border-success/20">
                    <CheckCircle size={10} weight="fill" />
                    {message}
                </span>
            );
        }

        if (status === "rate_limited") {
            return (
                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
                    <Warning size={10} weight="fill" />
                    {message}
                </span>
            );
        }

        return (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-destructive/10 text-destructive border border-destructive/20">
                <XCircle size={10} weight="fill" />
                {message}
            </span>
        );
    };

    return (
        <AccordionSection title="Services" expanded={expanded} onToggle={onToggle}>
            <div className="space-y-4">
                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                        <FolderOpen size={12} />
                        App Storage
                    </div>
                    <p className="text-xs text-muted-foreground mb-2">
                        Store MusicBrainz data, mapping cache, temporary cache, and logs on another drive.
                        Leave blank to use the system default.
                    </p>
                    <div className="flex gap-2">
                        <input
                            value={storageRoot}
                            onChange={(event) => setStorageRoot(event.target.value)}
                            disabled={isSearching || savingStorage}
                            placeholder="System default"
                            aria-label="App storage location"
                            className="min-w-0 flex-1 bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50"
                        />
                        <button
                            type="button"
                            onClick={handleBrowseStorage}
                            disabled={isSearching || savingStorage}
                            className="px-3 py-2 rounded-lg border border-border text-sm hover:bg-foreground-5 disabled:opacity-50"
                        >
                            Browse
                        </button>
                        <button
                            type="button"
                            onClick={handleSaveStorage}
                            disabled={isSearching || savingStorage}
                            className="px-3 py-2 rounded-lg bg-accent text-accent-foreground text-sm font-medium disabled:opacity-50"
                        >
                            {savingStorage ? "Applying..." : "Apply"}
                        </button>
                    </div>
                </div>

                <div className="border-t border-border" />

                {/* Search Provider Selection */}
                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Search Provider
                    </div>
                    <div className="space-y-1">
                        {(Object.entries(PROVIDERS) as [SearchProvider, typeof PROVIDERS[SearchProvider]][]).map(([id, info]) => {
                            // Inline status for each provider
                            const providerStatus = id === "apple_music"
                                ? { status: appleMusicApiStatus }
                                : id === "itunes"
                                    ? { status: itunesApiStatus }
                                    : id === "musicbrainz_api"
                                        ? { status: musicBrainzApiStatus }
                                        : null;

                            return (
                                <label
                                    key={id}
                                    className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-all border
                      ${provider === id
                                            ? "bg-accent/10 border-accent/50 ring-1 ring-accent/20"
                                            : "border-transparent hover:bg-foreground-5"
                                        }
                      ${isSearching ? "opacity-50 cursor-not-allowed" : ""}`}
                                >
                                    <input
                                        type="radio"
                                        name="provider"
                                        checked={provider === id}
                                        onChange={() => !isSearching && setProvider(id)}
                                        disabled={isSearching}
                                        className="mt-1 accent-accent text-accent"
                                    />
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <div className="font-medium text-sm">{info.name}</div>
                                            {providerStatus && providerStatus.status !== "idle" && providerStatus.status !== "checking" && (
                                                renderStatusPill(providerStatus.status, providerStatus.status === "ok" ? "Online" : providerStatus.status === "rate_limited" ? "Rate Limited" : "Offline")
                                            )}
                                            {providerStatus && providerStatus.status === "checking" && (
                                                <span className="text-[10px] text-muted-foreground">Checking...</span>
                                            )}
                                        </div>
                                        <div className="text-xs text-muted-foreground leading-snug mt-0.5">{info.description}</div>
                                        {info.requiresDb && (
                                            <div className="text-[10px] text-warning mt-1 font-medium bg-warning/10 inline-flex items-center gap-1 px-1.5 py-0.5 rounded">
                                                <Warning size={10} weight="fill" /> DB Required
                                            </div>
                                        )}
                                    </div>
                                </label>
                            );
                        })}
                    </div>
                </div>

                {/* iTunes Country Selector - shown when iTunes or Apple Music is selected */}
                {(provider === "itunes" || provider === "apple_music") && (
                    <>
                        <div className="border-t border-border" />
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                                <GlobeSimple size={12} />
                                Storefront / Country
                            </div>
                            <div className="relative">
                                <select
                                    value={itunesCountry}
                                    onChange={(e) => handleCountryChange(e.target.value)}
                                    disabled={isSearching}
                                    className="w-full appearance-none bg-background border border-border rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50"
                                >
                                    {Object.entries(ITUNES_COUNTRIES).map(([code, name]) => (
                                        <option key={code} value={code}>{name}</option>
                                    ))}
                                </select>
                                <CaretDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                            </div>
                        </div>
                    </>
                )}

                {/* MusicBrainz API Rate Limit - shown when musicbrainz_api is selected */}
                {provider === "musicbrainz_api" && (
                    <>
                        <div className="border-t border-border" />
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                                <Timer size={12} />
                                Rate Limiting
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    value={mbApiRateLimit}
                                    onChange={(e) => setMbApiRateLimit(e.target.value)}
                                    min={1}
                                    max={10}
                                    disabled={isSearching}
                                    className="w-20 bg-background border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50"
                                />
                                <span className="text-xs text-muted-foreground">req/sec</span>
                                <button
                                    onClick={handleSaveMbApiRateLimit}
                                    disabled={isSearching}
                                    className="px-2.5 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-foreground-5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Save
                                </button>
                            </div>
                            <p className="text-[10px] text-muted-foreground mt-1">
                                MusicBrainz API enforces 1 request/second. Exceeding may result in temporary bans.
                            </p>
                        </div>
                    </>
                )}

                {/* iTunes Rate Limit Controls - shown when iTunes is selected */}
                {provider === "itunes" && (
                    <>
                        <div className="border-t border-border" />
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                                <Timer size={12} />
                                Rate Limiting
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    value={rateLimit}
                                    onChange={(e) => setRateLimit(e.target.value)}
                                    min={1}
                                    max={120}
                                    disabled={isSearching}
                                    className="w-20 bg-background border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50"
                                />
                                <span className="text-xs text-muted-foreground">req/min</span>
                                <button
                                    onClick={handleSaveRateLimit}
                                    disabled={isSearching}
                                    className="px-2.5 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-foreground-5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Save
                                </button>
                            </div>
                            <div className="mt-2">
                                <button
                                    onClick={handleToggleRateLimitPause}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                                        rateLimitPaused
                                            ? "bg-warning/15 text-warning border border-warning/30 hover:bg-warning/25"
                                            : "border border-border hover:bg-foreground-5"
                                    }`}
                                >
                                    {rateLimitPaused ? (
                                        <>
                                            <Play size={12} weight="fill" />
                                            Resume Rate Limiting
                                        </>
                                    ) : (
                                        <>
                                            <Pause size={12} weight="fill" />
                                            Pause Rate Limiting
                                        </>
                                    )}
                                </button>
                                {rateLimitPaused && (
                                    <p className="text-[10px] text-warning mt-1.5 leading-snug">
                                        [!] Rate limiting is paused. Requests will be sent without delays, which may trigger 403 errors from iTunes.
                                    </p>
                                )}
                            </div>
                        </div>
                    </>
                )}

                {/* Apple Music API Configuration - shown when apple_music is selected */}
                {provider === "apple_music" && (
                    <>
                        <div className="border-t border-border" />
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                                <Key size={12} />
                                Apple Music API
                            </div>

                            {/* Mode selector */}
                            <div className="space-y-1 mb-3">
                                <label
                                    className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-all border ${
                                        appleMusicMode === "shared_proxy"
                                            ? "bg-accent/10 border-accent/50 ring-1 ring-accent/20"
                                            : "border-transparent hover:bg-foreground-5"
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="am_mode"
                                        checked={appleMusicMode === "shared_proxy"}
                                        onChange={() => setAppleMusicMode("shared_proxy")}
                                        className="mt-1 accent-accent"
                                    />
                                    <div className="flex-1">
                                        <div className="font-medium text-sm">Hosted Proxy (Default)</div>
                                        <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                                            Uses a hosted server to look up tracks. No setup required. Rate limited.
                                        </div>
                                    </div>
                                </label>
                                <label
                                    className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-all border ${
                                        appleMusicMode === "own_credentials"
                                            ? "bg-accent/10 border-accent/50 ring-1 ring-accent/20"
                                            : "border-transparent hover:bg-foreground-5"
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="am_mode"
                                        checked={appleMusicMode === "own_credentials"}
                                        onChange={() => setAppleMusicMode("own_credentials")}
                                        className="mt-1 accent-accent"
                                    />
                                    <div className="flex-1">
                                        <div className="font-medium text-sm">Own Credentials</div>
                                        <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                                            Use your own Apple Developer account credentials. No rate limits from the shared proxy.
                                        </div>
                                    </div>
                                </label>
                            </div>

                            {/* Shared proxy info */}
                            {appleMusicMode === "shared_proxy" && (
                                <div className="space-y-2">
                                    <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/25 text-[11px] text-foreground/90 leading-relaxed">
                                        <div className="font-semibold text-xs mb-1 flex items-center gap-1">
                                            <Info size={12} />
                                            Hosted, Rate Limited Proxy
                                        </div>
                                        <ul className="list-disc ml-4 space-y-0.5">
                                            <li>Limited to <strong>120 requests per minute</strong> per IP address</li>
                                            <li>This is a free community service and may be <strong>removed or restricted</strong> in future releases if abused</li>
                                            <li>For unrestricted access, switch to "Own Credentials" with an Apple Developer account ($99/year)</li>
                                        </ul>
                                        <button
                                            onClick={() => setShowLimitsInfo(true)}
                                            className="mt-1.5 text-accent hover:underline font-medium"
                                        >
                                            Learn more...
                                        </button>
                                    </div>

                                    <div>
                                        <label className="text-xs text-muted-foreground mb-1 block">Proxy URL</label>
                                        <input
                                            type="text"
                                            value={proxyUrl}
                                            onChange={(e) => setProxyUrl(e.target.value)}
                                            placeholder={DEFAULT_PROXY_URL}
                                            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 placeholder:text-muted-foreground/50"
                                        />
                                        <p className="text-[10px] text-muted-foreground mt-0.5">
                                            Default: {DEFAULT_PROXY_URL}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Own credentials form */}
                            {appleMusicMode === "own_credentials" && (
                                <div className="space-y-2">
                                    <div className="p-2 rounded-lg bg-accent/10 border border-accent/25 text-[11px] text-foreground/90">
                                        Requires an Apple Developer account ($99/year) with a MusicKit API key.
                                        Your credentials are stored locally and never leave this device.
                                    </div>
                                    <div>
                                        <label className="text-xs text-muted-foreground mb-1 block">Team ID</label>
                                        <input
                                            type="text"
                                            value={teamId}
                                            onChange={(e) => setTeamId(e.target.value)}
                                            placeholder="e.g. 7HQVB2S4BX"
                                            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 placeholder:text-muted-foreground/50"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-muted-foreground mb-1 block">Key ID</label>
                                        <input
                                            type="text"
                                            value={keyId}
                                            onChange={(e) => setKeyId(e.target.value)}
                                            placeholder="e.g. ABC123DEFG"
                                            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 placeholder:text-muted-foreground/50"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-muted-foreground mb-1 block">.p8 Private Key File</label>
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                value={keyPath}
                                                onChange={(e) => setKeyPath(e.target.value)}
                                                placeholder="Path to .p8 file"
                                                className="flex-1 bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 placeholder:text-muted-foreground/50 truncate"
                                                readOnly
                                            />
                                            <button
                                                onClick={handleBrowseKeyFile}
                                                className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-foreground-5 transition-colors flex-shrink-0"
                                            >
                                                Browse
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="flex gap-2 pt-2">
                                <button
                                    onClick={handleSaveAppleMusicConfig}
                                    disabled={!canSaveAppleMusicConfig}
                                    className="flex-1 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {appleMusicMode === "shared_proxy" ? "Save & Enable" : "Save Credentials"}
                                </button>
                                <button
                                    onClick={handleTestCredentials}
                                    disabled={!canTestAppleMusicConfig}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-foreground-5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <TestTube size={12} />
                                    {testingCredentials ? "Testing..." : "Test"}
                                </button>
                            </div>

                            {testResult && (
                                <div className={`mt-2 p-2 rounded-lg text-xs flex items-start gap-1.5 ${
                                    testResult.success
                                        ? "bg-success/10 border border-success/30 text-success"
                                        : "bg-destructive/10 border border-destructive/30 text-destructive"
                                }`}>
                                    {testResult.success
                                        ? <CheckCircle size={14} weight="fill" className="flex-shrink-0 mt-0.5" />
                                        : <XCircle size={14} weight="fill" className="flex-shrink-0 mt-0.5" />
                                    }
                                    <span>{testResult.message}</span>
                                </div>
                            )}
                        </div>

                        {/* Limits info dialog */}
                        {showLimitsInfo && (
                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowLimitsInfo(false)}>
                                <div
                                    className="bg-background border border-border rounded-xl shadow-xl max-w-md w-full mx-4 p-5"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <h3 className="text-sm font-semibold mb-3">About the Hosted Proxy</h3>
                                    <div className="text-xs text-foreground/80 space-y-2 leading-relaxed">
                                        <p>
                                            This app includes a <strong>free hosted proxy</strong> that lets you search the Apple Music catalog
                                            without needing your own Apple Developer credentials.
                                        </p>
                                        <p className="font-semibold">Rate Limits:</p>
                                        <ul className="list-disc ml-4 space-y-0.5">
                                            <li><strong>120 requests per minute</strong> per IP address</li>
                                            <li>Requests exceeding the limit receive a 429 error and are automatically retried after a short delay</li>
                                            <li>For most play history files (under 10,000 tracks), this limit will not be reached</li>
                                        </ul>
                                        <p className="font-semibold">Important Notice:</p>
                                        <ul className="list-disc ml-4 space-y-0.5">
                                            <li>This is a <strong>community service</strong> provided at no cost</li>
                                            <li>It may be <strong>removed, restricted, or rate-limited further</strong> in future releases if it is abused or becomes too expensive to operate</li>
                                            <li>No uptime guarantee is provided</li>
                                        </ul>
                                        <p className="font-semibold">Want unrestricted access?</p>
                                        <p>
                                            Switch to "Own Credentials" and provide your own Apple Developer account
                                            credentials ($99/year). Your requests will go directly to Apple with no
                                            shared rate limits.
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => setShowLimitsInfo(false)}
                                        className="mt-4 w-full px-3 py-2 text-xs font-medium bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
                                    >
                                        Got it
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}

                <div className="border-t border-border" />

                {/* Export Format Selection */}
                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Export Format
                    </div>
                    <div className="space-y-1">
                        {(Object.entries(EXPORT_FORMATS) as [ExportFormat, typeof EXPORT_FORMATS[ExportFormat]][]).map(([id, info]) => (
                            <div key={id}>
                                <div
                                    className={`flex items-start gap-2 p-2 rounded-lg transition-all border
                      ${exportFormat === id
                                            ? "bg-accent/10 border-accent/50 ring-1 ring-accent/20"
                                            : "border-transparent hover:bg-foreground-5"
                                        }`}
                                >
                                    <label className="flex items-center gap-3 flex-1 cursor-pointer">
                                        <input
                                            type="radio"
                                            name="format"
                                            checked={exportFormat === id}
                                            onChange={() => setExportFormat(id)}
                                            className="accent-accent"
                                        />
                                        <div className="flex-1">
                                            <div className="font-medium text-sm">{info.name}</div>
                                            <div className="text-xs text-muted-foreground">{info.description}</div>
                                        </div>
                                    </label>
                                    <button
                                        type="button"
                                        onClick={() => setPreviewFormat((current) => current === id ? null : id)}
                                        aria-label={`${previewFormat === id ? "Hide" : "Show"} sample output for ${info.name}`}
                                        title={previewFormat === id ? "Hide sample output" : "Show sample output"}
                                        className={`mt-0.5 p-1 rounded-md transition-colors
                          ${previewFormat === id
                                                ? "text-accent bg-accent/15"
                                                : "text-muted-foreground hover:text-foreground hover:bg-foreground-5"
                                            }`}
                                    >
                                        <Info size={13} weight="bold" />
                                    </button>
                                </div>
                                {previewFormat === id && (
                                    <div className="mt-1 mb-1 ml-7 bg-foreground-5/50 border border-border rounded-lg p-2.5 max-h-40 overflow-auto">
                                        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                            Sample Output ({info.ext})
                                        </div>
                                        <pre className="text-[10px] leading-relaxed text-foreground/70 whitespace-pre overflow-x-auto font-mono">
                                            {FORMAT_PREVIEWS[id]}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </AccordionSection>
    );
}
