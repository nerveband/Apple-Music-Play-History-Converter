import { useState } from "react";
import { SearchProvider, ExportFormat } from "../lib/types";
import { ServicesSection } from "./sections/ServicesSection";
import { DatabaseSection } from "./sections/DatabaseSection";
import { AdvancedSection } from "./sections/AdvancedSection";
import { Sun, Moon } from "@phosphor-icons/react";

interface SettingsSidebarProps {
    provider: SearchProvider;
    setProvider: (p: SearchProvider) => void;
    exportFormat: ExportFormat;
    setExportFormat: (f: ExportFormat) => void;
    isSearching: boolean;
    isDark: boolean;
    toggleTheme: () => void;
}

export function SettingsSidebar({
    provider,
    setProvider,
    exportFormat,
    setExportFormat,
    isSearching,
    isDark,
    toggleTheme,
}: SettingsSidebarProps) {
    const [expanded, setExpanded] = useState({
        services: true,
        database: false,
        advanced: false,
    });

    const toggle = (key: keyof typeof expanded) => {
        setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
    };

    return (
        <aside className="w-[320px] flex-shrink-0 border-l border-border bg-foreground-5/50 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border">
                <h2 className="text-base font-semibold">Settings</h2>
            </div>

            <div className="flex-1 overflow-y-auto">
                <ServicesSection
                    expanded={expanded.services}
                    onToggle={() => toggle("services")}
                    provider={provider}
                    setProvider={setProvider}
                    exportFormat={exportFormat}
                    setExportFormat={setExportFormat}
                    isSearching={isSearching}
                />

                <DatabaseSection
                    expanded={expanded.database}
                    onToggle={() => toggle("database")}
                />

                <AdvancedSection
                    expanded={expanded.advanced}
                    onToggle={() => toggle("advanced")}
                />
            </div>

            <div className="p-4 border-t border-border mt-auto bg-background/50">
                <button
                    onClick={toggleTheme}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-foreground-5 transition-colors text-sm font-medium"
                >
                    {isDark ? <Sun size={18} /> : <Moon size={18} />}
                    {isDark ? "Light Mode" : "Dark Mode"}
                </button>
            </div>
        </aside>
    );
}
