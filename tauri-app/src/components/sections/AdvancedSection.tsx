import { AccordionSection } from "../ui/Accordion";
import { Button } from "../ui/Button";
import { FolderOpen, Broom } from "@phosphor-icons/react";

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
                    <Button variant="ghost" className="w-full justify-start" icon={<FolderOpen size={16} />}>
                        Open Logs Folder
                    </Button>
                </div>

                <div className="border-t border-border" />

                <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                        Maintenance
                    </div>
                    <Button variant="ghost" className="w-full justify-start text-warning hover:text-warning" icon={<Broom size={16} />}>
                        Clear Search Cache
                    </Button>
                </div>
            </div>
        </AccordionSection>
    );
}
