import { ReactNode } from "react";
import { CaretDown } from "@phosphor-icons/react";

interface AccordionSectionProps {
    title: string;
    expanded: boolean;
    onToggle: () => void;
    children: ReactNode;
    className?: string;
}

export function AccordionSection({
    title,
    expanded,
    onToggle,
    children,
    className = "",
}: AccordionSectionProps) {
    return (
        <div className={`border-b border-border ${className}`}>
            <button
                onClick={onToggle}
                className="w-full p-3 flex items-center justify-between hover:bg-foreground-5/50 transition-colors focus:outline-none focus:bg-foreground-5/50"
            >
                <span className="font-medium text-sm">{title}</span>
                <CaretDown
                    size={16}
                    weight="bold"
                    className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                />
            </button>
            <div
                className={`overflow-hidden transition-all duration-300 ease-in-out ${expanded ? "max-h-[500px] opacity-100 mb-3" : "max-h-0 opacity-0"
                    }`}
            >
                <div className="px-3">{children}</div>
            </div>
        </div>
    );
}
