import { useState, useEffect, useCallback } from "react";
import "./index.css";
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Hooks
import { useTauri } from "./hooks/useTauri";
import { useSearch } from "./hooks/useSearch";
import { useResize } from "./hooks/useResize";
import { WarningCircle, Question, Info, SidebarSimple, CaretDown, CaretUp, Sun, Moon, CheckCircle, XCircle, Warning, Clock, File } from "@phosphor-icons/react";

// Components
import { FileSelection } from "./components/FileSelection";
import { ResultsPanel } from "./components/ResultsPanel";
import { ResultsTable } from "./components/ResultsTable";
import { SettingsSidebar } from "./components/SettingsSidebar";
import { PreviewTable } from "./components/PreviewTable";
import { LogPanel } from "./components/LogPanel";
import { Dialogs } from "./components/Dialogs";

// Types
import { FileInfo, SearchProvider, ExportFormat, ResumeState, PROVIDERS } from "./lib/types";
import { analyzeCsv, clearResumeState, getResumeState, getSettings, initializeSidecar, loadExportedCsv, openLogDir, restartSidecar, resumeSearch, startSearchMissingOnly } from "./lib/commands";
import { getErrorMessage, getShortError } from "./lib/errors";
import { listen } from "@tauri-apps/api/event";
import appIcon from "./assets/app-icon.png";

function App() {
  const isTauri = useTauri();

  useEffect(() => {
    if (isTauri) {
      initializeSidecar()
        .then(() => {
          setStartupIssue(null);
          return Promise.all([getResumeState(), getSettings()]);
        })
        .catch((error) => {
          console.error(error);
          const message = getErrorMessage(error, "The search backend failed to start.");
          setStartupIssue(message);
          toast.error(`Backend startup failed: ${getShortError(error, "Open the logs folder for details.")}`);
        });
    }
  }, [isTauri]);

  // Listen for sidecar crash and auto-restart
  useEffect(() => {
    if (!isTauri) return;

    const unlisten = listen("sidecar_terminated", () => {
      toast.warning("Python sidecar stopped unexpectedly. Restarting...");
      restartSidecar()
        .then(() => Promise.all([getResumeState(), getSettings()]))
        .then(() => {
          setStartupIssue(null);
          toast.success("Sidecar restarted. Saved search progress is ready to resume.");
        })
        .catch((err) => {
          console.error("Failed to restart sidecar:", err);
          setStartupIssue(getErrorMessage(err, "Failed to restart the search backend."));
          toast.error("Failed to restart sidecar. Please restart the app.");
        });
    });

    return () => { unlisten.then(fn => fn()); };
  }, [isTauri]);

  // App State
  const [isDark, setIsDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const [showHowTo, setShowHowTo] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [activeTab, setActiveTab] = useState<"preview" | "results">("preview");
  const [startupIssue, setStartupIssue] = useState<string | null>(null);

  // File State
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);

  // Search State
  const [provider, setProvider] = useState<SearchProvider>("musicbrainz_api");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("lastfm");
  const [lastExportPath, setLastExportPath] = useState<string | null>(null);
  const [resumeState, setResumeState] = useState<ResumeState | null>(null);

  // Exported CSV detection
  const [exportedCsvInfo, setExportedCsvInfo] = useState<{
    fileInfo: FileInfo;
    foundCount: number;
    missingCount: number;
  } | null>(null);

  // Resizable panels
  const sidebar = useResize({
    direction: "horizontal",
    initialSize: 320,
    minSize: 240,
    maxSize: 500,
    invertDrag: true,
    storageKey: "sidebar-width",
  });

  const logPanel = useResize({
    direction: "vertical",
    initialSize: 180,
    minSize: 80,
    maxSize: 500,
    invertDrag: true,
    storageKey: "log-panel-height",
  });

  const {
    progress,
    isSearching,
    isPaused,
    logs,
    handleStatusChange,
    resetProgress,
    clearLogs,
  } = useSearch(isTauri);

  // Unread log count (logs arrived while panel collapsed)
  const [unreadLogs, setUnreadLogs] = useState(0);
  const prevLogCountRef = useState(() => ({ current: 0 }))[0];

  // Track new logs while panel is collapsed
  useEffect(() => {
    if (logs.length > prevLogCountRef.current && logPanel.collapsed) {
      setUnreadLogs(prev => prev + (logs.length - prevLogCountRef.current));
    }
    prevLogCountRef.current = logs.length;
  }, [logs.length, logPanel.collapsed, prevLogCountRef]);

  // Reset unread when panel expands
  useEffect(() => {
    if (!logPanel.collapsed) {
      setUnreadLogs(0);
    }
  }, [logPanel.collapsed]);

  // Auto-switch to results tab and expand log panel when search starts
  useEffect(() => {
    if (isSearching) {
      setActiveTab("results");
      logPanel.expand();
    }
  }, [isSearching]);

  // Listen for persisted resume state
  useEffect(() => {
    if (!isTauri) return;
    const unlisten = listen<ResumeState>("resume_state", (event) => {
      if (event.payload.available) {
        setResumeState(event.payload);
      } else {
        setResumeState(null);
      }
    });
    return () => { unlisten.then(fn => fn()); };
  }, [isTauri]);

  // Hydrate UI state from persisted settings
  useEffect(() => {
    if (!isTauri) return;

    const unlisten = listen<Record<string, unknown>>("settings_loaded", (event) => {
      const rawProvider = event.payload.search_provider;
      if (typeof rawProvider === "string") {
        setProvider(normalizeProvider(rawProvider));
      }
    });

    return () => { unlisten.then(fn => fn()); };
  }, [isTauri]);

  // Theme handling
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  const handleFileSelect = useCallback((info: FileInfo) => {
    // Check if this is a previously exported CSV
    if (info.isConvertedCsv && (info.missingCount ?? 0) > 0) {
      setExportedCsvInfo({
        fileInfo: info,
        foundCount: info.foundCount ?? 0,
        missingCount: info.missingCount ?? 0,
      });
      return; // Don't set fileInfo yet - wait for user decision
    }

    setFileInfo(info);
    setActiveTab("preview");
    toast.success(`Loaded ${info.name}`);
  }, []);

  const handleClearFile = () => {
    setFileInfo(null);
    resetProgress();
    setActiveTab("preview");
  };

  const normalizeProvider = (value: string): SearchProvider => {
    const valid: SearchProvider[] = ["musicbrainz", "musicbrainz_api", "itunes", "apple_music"];
    return valid.includes(value as SearchProvider) ? (value as SearchProvider) : "musicbrainz_api";
  };

  const handleResumeConfirmed = async () => {
    if (!resumeState) return;
    try {
      const info = await analyzeCsv(resumeState.filePath);
      const resumedProvider = normalizeProvider(resumeState.provider);
      setProvider(resumedProvider);
      setFileInfo(info);
      setActiveTab("results");
      handleStatusChange(true, false);
      await resumeSearch(resumedProvider);
      toast.info(`Resuming from track ${resumeState.current.toLocaleString()} of ${resumeState.total.toLocaleString()}`);
      setResumeState(null);
    } catch (err) {
      console.error(err);
      toast.error("Failed to resume previous search");
    }
  };

  const handleExportedCsvResume = async () => {
    if (!exportedCsvInfo) return;
    try {
      const info = exportedCsvInfo.fileInfo;
      await loadExportedCsv(info.path);
      setFileInfo(info);
      setActiveTab("results");
      handleStatusChange(true, false);
      await startSearchMissingOnly(provider);
      toast.info(`Re-searching ${exportedCsvInfo.missingCount} missing tracks`);
    } catch (err) {
      console.error(err);
      toast.error("Failed to resume from exported CSV");
    } finally {
      setExportedCsvInfo(null);
    }
  };

  const handleExportedCsvLoadNormally = () => {
    if (!exportedCsvInfo) return;
    setFileInfo(exportedCsvInfo.fileInfo);
    setActiveTab("preview");
    toast.success(`Loaded ${exportedCsvInfo.fileInfo.name}`);
    setExportedCsvInfo(null);
  };

  const handleResumeDiscarded = async () => {
    try {
      await clearResumeState();
      toast.info("Saved search progress discarded");
    } catch (err) {
      console.error(err);
      toast.error("Failed to clear saved progress");
    } finally {
      setResumeState(null);
    }
  };

  return (
    <div className="h-full flex bg-background text-foreground gradient-mesh noise-texture">
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative min-w-0">
        {/* Header */}
        <header className="p-4 border-b border-border bg-background/95 backdrop-blur-xl z-10 stagger-1">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold flex items-center gap-3" style={{ fontFamily: 'var(--font-display)' }}>
              <img src={appIcon} alt="App icon" width={44} height={44} className="rounded-xl" />
              <span className="bg-gradient-to-r from-foreground to-foreground-70 bg-clip-text text-transparent">
                Play History Converter
              </span>
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowHowTo(true)}
                className="p-2 rounded-lg hover:bg-foreground-5 transition-colors"
                title="How to Use"
              >
                <Question size={20} />
              </button>
              <button
                onClick={() => setShowAbout(true)}
                className="p-2 rounded-lg hover:bg-foreground-5 transition-colors"
                title="About"
              >
                <Info size={20} />
              </button>
              <button
                onClick={() => setIsDark(!isDark)}
                className="p-2 rounded-lg hover:bg-foreground-5 transition-colors"
                title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
              >
                {isDark ? <Sun size={20} /> : <Moon size={20} />}
              </button>
              <button
                onClick={sidebar.toggleCollapse}
                className={`p-2 rounded-lg hover:bg-foreground-5 transition-colors ${sidebar.collapsed ? "text-accent" : ""}`}
                title={sidebar.collapsed ? "Show Settings" : "Hide Settings"}
              >
                <SidebarSimple size={20} />
              </button>
              {!isTauri && (
                <span className="flex items-center gap-1 text-xs bg-warning/20 text-warning px-2 py-1 rounded border border-warning/30">
                  <WarningCircle size={14} weight="fill" />
                  Browser Mode (Limited)
                </span>
              )}
            </div>
          </div>
        </header>

        {startupIssue && (
          <div className="mx-6 mt-4 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground/90">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-semibold text-warning mb-1">Backend Issue</div>
                <p className="leading-relaxed whitespace-pre-line">{startupIssue}</p>
              </div>
              <button
                onClick={() => {
                  openLogDir().catch((error) => {
                    console.error(error);
                    toast.error("Could not open the logs folder.");
                  });
                }}
                className="shrink-0 rounded-lg border border-warning/30 px-3 py-1.5 text-xs font-medium text-warning hover:bg-warning/10 transition-colors"
              >
                Open Logs
              </button>
            </div>
          </div>
        )}

        {/* Content Grid */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top section: File & Controls */}
          <div className="flex-shrink-0 overflow-auto">
            <div className="p-6 space-y-6">
              <div className="stagger-2">
                <FileSelection
                  onFileSelect={handleFileSelect}
                  onClear={handleClearFile}
                  currentFile={fileInfo}
                  disabled={isSearching}
                />
              </div>

              {fileInfo && (
                <div className="stagger-3">
                  <ResultsPanel
                    progress={progress}
                    provider={provider}
                    isSearching={isSearching}
                    isPaused={isPaused}
                    filePath={fileInfo.path}
                    onSearchStatusChange={handleStatusChange}
                    exportFormat={exportFormat}
                    lastExportPath={lastExportPath}
                    onExported={setLastExportPath}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Bottom section: Preview/Results + Log split */}
          <div className="flex-1 flex flex-col min-h-0 border-t border-border">
            {/* Tab bar for Preview / Results */}
            <div className="flex items-center border-b border-border bg-foreground-5/20">
              <button
                onClick={() => setActiveTab("preview")}
                className={`px-4 py-2 text-xs font-semibold uppercase tracking-wide transition-colors border-b-2 ${
                  activeTab === "preview"
                    ? "border-accent text-accent"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Preview
              </button>
              <button
                onClick={() => setActiveTab("results")}
                className={`px-4 py-2 text-xs font-semibold uppercase tracking-wide transition-colors border-b-2 ${
                  activeTab === "results"
                    ? "border-accent text-accent"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Results
                {progress && progress.found > 0 && (
                  <span className="ml-1.5 text-[10px] bg-success/20 text-success px-1.5 py-0.5 rounded-full font-bold">
                    {progress.found}
                  </span>
                )}
              </button>
            </div>

            {/* Tab content - both always mounted to preserve state */}
            <div className="flex-1 min-h-[100px] stagger-4 relative">
              <div className={`absolute inset-0 ${activeTab === "preview" ? "" : "hidden"}`}>
                <PreviewTable filePath={fileInfo ? fileInfo.path : null} />
              </div>
              <div className={`absolute inset-0 ${activeTab === "results" ? "" : "hidden"}`}>
                <ResultsTable
                  progress={progress}
                  isSearching={isSearching}
                  filePath={fileInfo ? fileInfo.path : null}
                />
              </div>
            </div>

            {/* Log Panel - Resizable */}
            {!logPanel.collapsed && (
              <div
                className="resize-handle-horizontal border-t border-border"
                onMouseDown={logPanel.handleMouseDown}
              />
            )}
            <div
              className="flex-shrink-0 bg-background/80 overflow-hidden"
              style={{ height: logPanel.collapsed ? 0 : logPanel.size }}
            >
              {!logPanel.collapsed && (
                <LogPanel logs={logs} onClear={clearLogs} />
              )}
            </div>
            {/* Log collapse toggle */}
            <div className="flex items-center border-t border-border bg-foreground-5/20 px-2">
              <button
                onClick={logPanel.toggleCollapse}
                className="flex items-center gap-1.5 py-1 px-2 text-[11px] text-muted-foreground hover:text-foreground transition-colors rounded"
                title={logPanel.collapsed ? "Show Log Panel" : "Hide Log Panel"}
              >
                {logPanel.collapsed ? <CaretUp size={12} /> : <CaretDown size={12} />}
                {logPanel.collapsed ? "Show Log" : "Log"}
                {logPanel.collapsed && unreadLogs > 0 ? (
                  <span className="text-[10px] bg-accent text-white px-1.5 py-0.5 rounded-full font-bold animate-pulse">
                    {unreadLogs}
                  </span>
                ) : logs.length > 0 ? (
                  <span className="text-[10px] bg-foreground-10 px-1.5 py-0.5 rounded-full font-medium">
                    {logs.length}
                  </span>
                ) : null}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Sidebar Resize Handle */}
      {!sidebar.collapsed && (
        <div
          className="resize-handle-vertical"
          onMouseDown={sidebar.handleMouseDown}
        />
      )}

      {/* Settings Sidebar - Resizable */}
      <div
        className="flex-shrink-0 overflow-hidden"
        style={{ width: sidebar.collapsed ? 0 : sidebar.size }}
      >
        {!sidebar.collapsed && (
          <SettingsSidebar
            provider={provider}
            setProvider={setProvider}
            exportFormat={exportFormat}
            setExportFormat={setExportFormat}
            isSearching={isSearching}
          />
        )}
      </div>

      <ToastContainer
        position="bottom-left"
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

      <Dialogs
        showHowTo={showHowTo}
        onCloseHowTo={() => setShowHowTo(false)}
        showAbout={showAbout}
        onCloseAbout={() => setShowAbout(false)}
        confirm={resumeState ? {
          open: true,
          title: "Resume Previous Search?",
          content: <ResumeContent state={resumeState} />,
          confirmLabel: "Resume Search",
          cancelLabel: "Discard",
          onConfirm: handleResumeConfirmed,
          onCancel: handleResumeDiscarded,
        } : exportedCsvInfo ? {
          open: true,
          title: "Resume Previous Session?",
          content: <ExportedCsvContent info={exportedCsvInfo} />,
          confirmLabel: "Search Missing Tracks",
          cancelLabel: "Start Fresh",
          onConfirm: handleExportedCsvResume,
          onCancel: handleExportedCsvLoadNormally,
        } : null}
      />
    </div>
  );
}

function ResumeContent({ state }: { state: ResumeState }) {
  const percent = state.total > 0 ? (state.current / state.total) * 100 : 0;
  const providerInfo = PROVIDERS[state.provider as SearchProvider];
  const fileName = state.filePath.split("/").pop() || state.filePath.split("\\").pop() || state.filePath;

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ${mins % 60}m`;
  };

  return (
    <div className="space-y-4">
      {/* File info */}
      <div className="flex items-start gap-2 p-2.5 rounded-lg bg-foreground-5/50 border border-border">
        <File size={16} className="text-muted-foreground flex-shrink-0 mt-0.5" />
        <div className="min-w-0">
          <div className="text-sm font-medium truncate" title={state.filePath}>{fileName}</div>
          <div className="text-[11px] text-muted-foreground truncate" title={state.filePath}>{state.filePath}</div>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-bold tabular-nums">
            {state.current.toLocaleString()} / {state.total.toLocaleString()}
          </span>
        </div>
        <div className="h-2 bg-foreground-10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent to-accent/70 rounded-full transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="text-[11px] text-muted-foreground mt-1 tabular-nums">{percent.toFixed(1)}% complete</div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2">
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-success/8 border border-success/15">
          <CheckCircle size={14} weight="fill" className="text-success flex-shrink-0" />
          <div>
            <div className="text-sm font-bold tabular-nums text-success">{state.found.toLocaleString()}</div>
            <div className="text-[10px] text-success/70 uppercase tracking-wide font-medium">Found</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-destructive/8 border border-destructive/15">
          <XCircle size={14} weight="fill" className="text-destructive flex-shrink-0" />
          <div>
            <div className="text-sm font-bold tabular-nums text-destructive">{state.missing.toLocaleString()}</div>
            <div className="text-[10px] text-destructive/70 uppercase tracking-wide font-medium">Missing</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-warning/8 border border-warning/15">
          <Warning size={14} weight="fill" className="text-warning flex-shrink-0" />
          <div>
            <div className="text-sm font-bold tabular-nums text-warning">{state.rateLimited.toLocaleString()}</div>
            <div className="text-[10px] text-warning/70 uppercase tracking-wide font-medium">Rate Ltd</div>
          </div>
        </div>
      </div>

      {/* Metadata pills */}
      <div className="flex flex-wrap gap-1.5">
        {providerInfo && (
          <span className="text-[10px] font-medium bg-accent/10 text-accent px-2 py-0.5 rounded-full">
            {providerInfo.name}
          </span>
        )}
        {state.elapsedSeconds > 0 && (
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground bg-foreground-5 px-2 py-0.5 rounded-full">
            <Clock size={10} />
            {formatTime(state.elapsedSeconds)} elapsed
          </span>
        )}
        <span className="text-[10px] text-muted-foreground bg-foreground-5 px-2 py-0.5 rounded-full">
          {state.fileType}
        </span>
      </div>
    </div>
  );
}

function ExportedCsvContent({ info }: { info: { fileInfo: FileInfo; foundCount: number; missingCount: number } }) {
  const total = info.foundCount + info.missingCount;
  const percent = total > 0 ? (info.foundCount / total) * 100 : 0;
  const fileName = info.fileInfo.name;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 p-2.5 rounded-lg bg-foreground-5/50 border border-border">
        <File size={16} className="text-muted-foreground flex-shrink-0 mt-0.5" />
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">{fileName}</div>
          <div className="text-[11px] text-muted-foreground">
            This file contains results from a previous search session.
          </div>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-muted-foreground">Previously Found</span>
          <span className="font-bold tabular-nums">
            {info.foundCount.toLocaleString()} / {total.toLocaleString()}
          </span>
        </div>
        <div className="h-2 bg-foreground-10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-success to-success/70 rounded-full"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-success/8 border border-success/15">
          <CheckCircle size={14} weight="fill" className="text-success flex-shrink-0" />
          <div>
            <div className="text-sm font-bold tabular-nums text-success">{info.foundCount.toLocaleString()}</div>
            <div className="text-[10px] text-success/70 uppercase tracking-wide font-medium">Already Found</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-destructive/8 border border-destructive/15">
          <XCircle size={14} weight="fill" className="text-destructive flex-shrink-0" />
          <div>
            <div className="text-sm font-bold tabular-nums text-destructive">{info.missingCount.toLocaleString()}</div>
            <div className="text-[10px] text-destructive/70 uppercase tracking-wide font-medium">Missing</div>
          </div>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        This looks like a file from a previous session. Click <strong>"Search Missing Tracks"</strong> to pick up where you left off — only the {info.missingCount.toLocaleString()} unmatched tracks will be searched.
        You can also switch to a different search provider before resuming.
      </p>
    </div>
  );
}

export default App;
