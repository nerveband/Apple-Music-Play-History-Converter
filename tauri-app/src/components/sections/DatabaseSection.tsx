import { useState, useEffect } from "react";
import { AccordionSection } from "../ui/Accordion";
import { Button } from "../ui/Button";
import { DatabaseStatus } from "../../lib/types";
import { getDatabaseStatus } from "../../lib/commands";
import { Database, DownloadSimple, Trash, ArrowCounterClockwise } from "@phosphor-icons/react";

interface DatabaseSectionProps {
    expanded: boolean;
    onToggle: () => void;
}

export function DatabaseSection({ expanded, onToggle }: DatabaseSectionProps) {
    const [status, setStatus] = useState<DatabaseStatus | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (expanded && !status) {
            loadStatus();
        }
    }, [expanded]);

    const loadStatus = async () => {
        try {
            const s = await getDatabaseStatus();
            setStatus(s);
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <AccordionSection title="Database & MusicBrainz" expanded={expanded} onToggle={onToggle}>
            <div className="space-y-4">
                <div className="p-3 rounded-lg bg-foreground-5/50 border border-border">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium flex items-center gap-2">
                            <Database size={16} /> Status
                        </span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${status?.downloaded ? "bg-success/20 text-success" : "bg-muted/20 text-muted-foreground"
                            }`}>
                            {status?.downloaded ? "Ready" : "Not Downloaded"}
                        </span>
                    </div>

                    {status?.downloaded && (
                        <div className="text-xs text-muted-foreground space-y-1 ml-6">
                            <div>Size: {status.size}</div>
                            <div>Tracks: {status.trackCount.toLocaleString()}</div>
                        </div>
                    )}
                </div>

                <Button
                    className="w-full"
                    variant={status?.downloaded ? "secondary" : "primary"}
                    icon={<DownloadSimple size={16} />}
                >
                    {status?.downloaded ? "Re-download Database" : "Download Database (~2GB)"}
                </Button>

                <div className="grid grid-cols-2 gap-2">
                    <Button variant="ghost" size="sm" onClick={loadStatus} icon={<ArrowCounterClockwise />}>
                        Check Updates
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        disabled={!status?.downloaded}
                        icon={<Trash />}
                    >
                        Delete DB
                    </Button>
                </div>
            </div>
        </AccordionSection>
    );
}
