import { useEffect, useMemo, useState } from "react";
import { FileInfo, ExportFormat, SearchProvider, SearchProgress } from "../lib/types";
import { analyzeCsv, exportResults, startSearch, stopSearch, togglePause } from "../lib/commands";
import { isTestMode, testDataDir } from "../lib/testMode";
import { resolveTestCsvs } from "../lib/testModeCsvs";
import { appDataDir, join } from "@tauri-apps/api/path";
import { exists } from "@tauri-apps/plugin-fs";

interface TestDashboardProps {
  provider: SearchProvider;
  exportFormat: ExportFormat;
  progress: SearchProgress | null;
  onFileLoaded: (info: FileInfo) => void;
  onSearchStatusChange: (searching: boolean, paused: boolean) => void;
}

type ReportStatus = "pending" | "pass" | "fail";

interface ReportRow {
  id: string;
  label: string;
  status: ReportStatus;
  detail?: string;
}

export function TestDashboard({
  provider,
  exportFormat,
  progress,
  onFileLoaded,
  onSearchStatusChange,
}: TestDashboardProps) {
  const [csvs, setCsvs] = useState<string[]>([]);
  const [selectedCsv, setSelectedCsv] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<ReportRow[]>([]);

  const enabled = isTestMode();
  const testDir = testDataDir();

  useEffect(() => {
    if (!enabled) return;
    resolveTestCsvs(testDir).then((paths) => {
      setCsvs(paths);
      if (!selectedCsv && paths.length) setSelectedCsv(paths[0]);
    });
  }, [enabled, testDir]);

  const addReport = (row: ReportRow) => {
    setReport((prev) => [...prev, row]);
  };

  const updateReport = (id: string, status: ReportStatus, detail?: string) => {
    setReport((prev) => prev.map((r) => (r.id === id ? { ...r, status, detail } : r)));
  };

  const resetReport = () => {
    setReport([]);
  };

  const handleLoad = async () => {
    if (!selectedCsv) return;
    const info = await analyzeCsv(selectedCsv);
    onFileLoaded(info);
  };

  const handleStart = async () => {
    if (!selectedCsv) return;
    onSearchStatusChange(true, false);
    await startSearch(selectedCsv, provider);
  };

  const handlePauseToggle = async () => {
    const paused = await togglePause();
    onSearchStatusChange(true, paused);
  };

  const handleStop = async () => {
    await stopSearch();
    onSearchStatusChange(false, false);
  };

  const handleExport = async () => {
    if (!selectedCsv) return;
    const dir = await appDataDir();
    const path = await join(dir, `test_export_${Date.now()}`);
    await exportResults(exportFormat, path);
    return path;
  };

  const scenarioSteps = useMemo(() => [
    { id: "load", label: "Load CSV" },
    { id: "start", label: "Start search" },
    { id: "pause", label: "Pause search" },
    { id: "resume", label: "Resume search" },
    { id: "stop", label: "Stop search" },
    { id: "export", label: "Export results" },
  ], []);

  const runScenario = async () => {
    if (!selectedCsv || running) return;
    setRunning(true);
    resetReport();
    scenarioSteps.forEach((s) => addReport({ id: s.id, label: s.label, status: "pending" }));

    try {
      await handleLoad();
      updateReport("load", "pass");

      await handleStart();
      updateReport("start", "pass");

      const beforePause = progress?.current ?? 0;
      await handlePauseToggle();
      await new Promise((r) => setTimeout(r, 2000));
      const afterPause = progress?.current ?? beforePause;
      updateReport(
        "pause",
        afterPause === beforePause ? "pass" : "fail",
        afterPause === beforePause ? undefined : "Progress changed while paused"
      );

      await handlePauseToggle();
      await new Promise((r) => setTimeout(r, 2000));
      const afterResume = progress?.current ?? afterPause;
      updateReport(
        "resume",
        afterResume > afterPause ? "pass" : "fail",
        afterResume > afterPause ? undefined : "Progress did not advance after resume"
      );

      await handleStop();
      updateReport("stop", "pass");

      const exportPath = await handleExport();
      const existsOnDisk = exportPath ? await exists(exportPath) : false;
      updateReport(
        "export",
        existsOnDisk ? "pass" : "fail",
        existsOnDisk ? undefined : "Export file not found"
      );
    } catch (e) {
      updateReport("export", "fail", String(e));
    } finally {
      setRunning(false);
    }
  };

  if (!enabled) return null;

  return (
    <section className="p-4 border-b border-border bg-foreground-5/30 space-y-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Test Dashboard</div>
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={selectedCsv ?? ""}
          onChange={(e) => setSelectedCsv(e.target.value)}
          className="px-3 py-2 rounded-md bg-background border border-border text-sm"
        >
          {csvs.map((csv) => (
            <option key={csv} value={csv}>
              {csv.split("/").pop()}
            </option>
          ))}
        </select>
        <button onClick={handleLoad} className="px-3 py-2 rounded-md border border-border text-sm">
          Load CSV
        </button>
        <button onClick={handleStart} className="px-3 py-2 rounded-md border border-border text-sm">
          Start
        </button>
        <button onClick={handlePauseToggle} className="px-3 py-2 rounded-md border border-border text-sm">
          Pause/Resume
        </button>
        <button onClick={handleStop} className="px-3 py-2 rounded-md border border-border text-sm">
          Stop
        </button>
        <button onClick={handleExport} className="px-3 py-2 rounded-md border border-border text-sm">
          Export
        </button>
        <button
          onClick={runScenario}
          disabled={running}
          className="px-3 py-2 rounded-md bg-accent text-accent-foreground text-sm font-medium"
        >
          Run Full E2E
        </button>
      </div>

      {report.length > 0 && (
        <div className="text-sm space-y-1">
          {report.map((r) => (
            <div key={r.id} className="flex items-center gap-2">
              <span className={r.status === "pass" ? "text-success" : r.status === "fail" ? "text-destructive" : "text-muted-foreground"}>
                {r.status.toUpperCase()}
              </span>
              <span>{r.label}</span>
              {r.detail && <span className="text-xs text-muted-foreground">({r.detail})</span>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
