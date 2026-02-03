import { AccordionSection } from "../ui/Accordion";
import { SearchProvider, ExportFormat, PROVIDERS, EXPORT_FORMATS } from "../../lib/types";
import { Warning } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";
import { checkItunesStatus, setSettings } from "../../lib/commands";
import { listen } from "@tauri-apps/api/event";

interface ServicesSectionProps {
    expanded: boolean;
    onToggle: () => void;
    provider: SearchProvider;
    setProvider: (p: SearchProvider) => void;
    exportFormat: ExportFormat;
    setExportFormat: (f: ExportFormat) => void;
    isSearching: boolean;
}

export function ServicesSection({
    expanded,
    onToggle,
    provider,
    setProvider,
    exportFormat,
    setExportFormat,
    isSearching,
}: ServicesSectionProps) {
    const [itunesStatus, setItunesStatus] = useState("Unknown");
    const [appleMusicEnabled, setAppleMusicEnabled] = useState(true);
    const [appleMusicTeamId, setAppleMusicTeamId] = useState("");
    const [appleMusicKeyId, setAppleMusicKeyId] = useState("");
    const [appleMusicKeyPath, setAppleMusicKeyPath] = useState("");
    const [itunesCountry, setItunesCountry] = useState("US");
    const [itunesRateLimit, setItunesRateLimit] = useState("20");

    useEffect(() => {
        const unlisten = listen<{ status: string }>("sidecar_status", (event) => {
            setItunesStatus(event.payload.status);
        });
        return () => {
            unlisten.then((fn) => fn());
        };
    }, []);

    const applySettings = async () => {
        await setSettings({
            search_provider: provider,
            apple_music_enabled: appleMusicEnabled,
            apple_music_team_id: appleMusicTeamId,
            apple_music_key_id: appleMusicKeyId,
            apple_music_key_path: appleMusicKeyPath,
            itunes_country: itunesCountry,
            itunes_rate_limit: Number(itunesRateLimit || 20),
        });
    };

    return (
        <AccordionSection title="Services" expanded={expanded} onToggle={onToggle}>
            <div className="space-y-4">
                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Search Provider
                    </div>
                    <div className="space-y-1">
                        {(Object.entries(PROVIDERS) as [SearchProvider, typeof PROVIDERS[SearchProvider]][]).map(([id, info]) => (
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
                                    onChange={() => {
                                        if (isSearching) return;
                                        setProvider(id);
                                        setSettings({ search_provider: id });
                                    }}
                                    disabled={isSearching}
                                    className="mt-1 accent-accent text-accent"
                                />
                                <div className="flex-1">
                                    <div className="font-medium text-sm">{info.name}</div>
                                    <div className="text-xs text-muted-foreground leading-snug mt-0.5">{info.description}</div>
                                    {info.requiresDb && (
                                        <div className="text-[10px] text-warning mt-1 font-medium bg-warning/10 inline-flex items-center gap-1 px-1.5 py-0.5 rounded">
                                            <Warning size={10} weight="fill" /> DB Required
                                        </div>
                                    )}
                                </div>
                            </label>
                        ))}
                    </div>
                </div>

                <div className="border-t border-border" />

                <div className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Apple Music API</div>
                    <label className="flex items-center gap-2 text-sm">
                        <input
                            type="checkbox"
                            checked={appleMusicEnabled}
                            onChange={(e) => setAppleMusicEnabled(e.target.checked)}
                            className="accent-accent"
                        />
                        Enabled
                    </label>
                    <Input label="Team ID" value={appleMusicTeamId} onChange={(e) => setAppleMusicTeamId(e.target.value)} />
                    <Input label="Key ID" value={appleMusicKeyId} onChange={(e) => setAppleMusicKeyId(e.target.value)} />
                    <Input label="Key Path" value={appleMusicKeyPath} onChange={(e) => setAppleMusicKeyPath(e.target.value)} />
                    <button
                        onClick={applySettings}
                        className="w-full text-sm px-3 py-2 rounded-lg border border-border hover:bg-foreground-5"
                    >
                        Save Apple Music Settings
                    </button>
                </div>

                <div className="border-t border-border" />

                <div className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">iTunes API</div>
                    <div className="text-xs text-muted-foreground">Status: {itunesStatus}</div>
                    <button
                        onClick={checkItunesStatus}
                        className="w-full text-sm px-3 py-2 rounded-lg border border-border hover:bg-foreground-5"
                    >
                        Check iTunes Status
                    </button>
                    <Select
                        label="Storefront Country"
                        value={itunesCountry}
                        onChange={(e) => setItunesCountry(e.target.value)}
                        options={[
                            { label: "United States", value: "US" },
                            { label: "United Kingdom", value: "GB" },
                            { label: "Italy", value: "IT" },
                            { label: "Germany", value: "DE" },
                            { label: "France", value: "FR" },
                            { label: "Spain", value: "ES" },
                            { label: "Japan", value: "JP" },
                            { label: "Australia", value: "AU" },
                            { label: "Canada", value: "CA" },
                        ]}
                    />
                    <Input
                        label="Rate Limit (req/min)"
                        value={itunesRateLimit}
                        onChange={(e) => setItunesRateLimit(e.target.value)}
                    />
                    <button
                        onClick={applySettings}
                        className="w-full text-sm px-3 py-2 rounded-lg border border-border hover:bg-foreground-5"
                    >
                        Save iTunes Settings
                    </button>
                </div>

                <div className="border-t border-border" />

                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Export Format
                    </div>
                    <div className="space-y-1">
                        {(Object.entries(EXPORT_FORMATS) as [ExportFormat, typeof EXPORT_FORMATS[ExportFormat]][]).map(([id, info]) => (
                            <label
                                key={id}
                                className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all border
                  ${exportFormat === id
                                        ? "bg-accent/10 border-accent/50 ring-1 ring-accent/20"
                                        : "border-transparent hover:bg-foreground-5"
                                    }`}
                            >
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
                        ))}
                    </div>
                </div>
            </div>
        </AccordionSection>
    );
}
