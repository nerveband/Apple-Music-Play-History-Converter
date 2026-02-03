import { useState, useEffect } from "react";
import "./index.css";
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { isTestMode } from "./lib/testMode";

// Hooks
import { useTauri } from "./hooks/useTauri";
import { useSearch } from "./hooks/useSearch";
import { MusicNotes, WarningCircle } from "@phosphor-icons/react";

// Components
import { FileSelection } from "./components/FileSelection";
import { ResultsPanel } from "./components/ResultsPanel";
import { SettingsSidebar } from "./components/SettingsSidebar";
import { PreviewTable } from "./components/PreviewTable";
import { TestDashboard } from "./components/TestDashboard";
// import { LogPanel } from "./components/LogPanel"; // FUTURE: Extract logs too

// Types
import { FileInfo, SearchProvider, ExportFormat } from "./lib/types";
import { initializeSidecar } from "./lib/commands";

function App() {
  const isTauri = useTauri();
  const testMode = isTestMode();

  useEffect(() => {
    if (isTauri) {
      initializeSidecar().catch(console.error);
    }
  }, [isTauri]);

  // App State
  const [isDark, setIsDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);

  // File State
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);

  // Search State
  const [provider, setProvider] = useState<SearchProvider>("musicbrainz_api");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("lastfm");

  const {
    progress,
    isSearching,
    isPaused,
    handleStatusChange,
    resetProgress
  } = useSearch(isTauri);

  // Theme handling
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  const handleFileSelect = (info: FileInfo) => {
    setFileInfo(info);
    toast.success(`Loaded ${info.name}`);
  };

  const handleClearFile = () => {
    setFileInfo(null);
    resetProgress();
  };

  return (
    <div className="h-full flex bg-background text-foreground animate-in fade-in duration-500">
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Header */}
        <header className="p-4 border-b border-border bg-background/95 backdrop-blur z-10">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <MusicNotes size={32} className="text-accent" />
              Play History Converter
            </h1>
            {!isTauri && (
              <span className="flex items-center gap-1 text-xs bg-warning/20 text-warning px-2 py-1 rounded border border-warning/30">
                <WarningCircle size={14} weight="fill" />
                Browser Mode (Limited)
              </span>
            )}
          </div>
        </header>

        {/* Content Grid */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left/Top Panel: File & Controls */}
          <div className="flex-1 flex flex-col overflow-auto border-r border-border">
            <div className="p-4 space-y-4">
              {testMode && (
                <TestDashboard
                  provider={provider}
                  exportFormat={exportFormat}
                  progress={progress}
                  onFileLoaded={(info) => {
                    setFileInfo(info);
                    toast.success(`Loaded ${info.name}`);
                  }}
                  onSearchStatusChange={handleStatusChange}
                />
              )}

              <FileSelection
                onFileSelect={handleFileSelect}
                onClear={handleClearFile}
                currentFile={fileInfo}
                disabled={isSearching}
              />

              {fileInfo && (
                <ResultsPanel
                  progress={progress}
                  provider={provider}
                  isSearching={isSearching}
                  isPaused={isPaused}
                  filePath={fileInfo.path}
                  onSearchStatusChange={handleStatusChange}
                  exportFormat={exportFormat}
                />
              )}
            </div>

            {/* Preview Table fills remaining height */}
            <div className="flex-1 border-t border-border min-h-[300px]">
              <PreviewTable filePath={fileInfo ? fileInfo.path : null} />
            </div>
          </div>
        </div>
      </main>

      {/* Settings Sidebar */}
      <SettingsSidebar
        provider={provider}
        setProvider={setProvider}
        exportFormat={exportFormat}
        setExportFormat={setExportFormat}
        isSearching={isSearching}
        isDark={isDark}
        toggleTheme={() => setIsDark(!isDark)}
      />

      <ToastContainer
        position="bottom-right"
        theme={isDark ? "dark" : "light"}
        autoClose={3000}
        hideProgressBar
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
      />
    </div>
  );
}

export default App;
