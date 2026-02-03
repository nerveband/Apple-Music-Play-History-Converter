import { AccordionSection } from "../ui/Accordion";
import { Button } from "../ui/Button";
import { FolderOpen, Broom } from "@phosphor-icons/react";
import { clearCache, getLogDir } from "../../lib/commands";
import { open } from "@tauri-apps/plugin-opener";

interface AdvancedSectionProps {
    expanded: boolean;
    onToggle: () => void;
}

export function AdvancedSection({ expanded, onToggle }: AdvancedSectionProps) {
    return (
        <AccordionSection title="Advanced" expanded={expanded} onToggle={onToggle}>
            <div className="space-y-3">
                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        System
                    </div>
                    <Button
                        variant="ghost"
                        className="w-full justify-start"
                        icon={<FolderOpen size={16} />}
                        onClick={async () => {
                            const dir = await getLogDir();
                            await open(dir);
                        }}
                    >
                        Open Logs Folder
                    </Button>
                </div>

                <div className="border-t border-border" />

                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Maintenance
                    </div>
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-warning hover:text-warning"
                        icon={<Broom size={16} />}
                        onClick={async () => {
                            await clearCache();
                        }}
                    >
                        Clear Search Cache
                    </Button>
                </div>
            </div>
        </AccordionSection>
    );
}
