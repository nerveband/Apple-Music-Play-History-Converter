import { AccordionSection } from "../ui/Accordion";
import { SearchProvider, ExportFormat, PROVIDERS, EXPORT_FORMATS } from "../../lib/types";
import { Warning } from "@phosphor-icons/react";

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
                                    onChange={() => !isSearching && setProvider(id)}
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
