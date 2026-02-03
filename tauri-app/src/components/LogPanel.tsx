import { LogEntry } from "../lib/types";
import { useMemo, useState } from "react";

interface LogPanelProps {
  logs: LogEntry[];
  onClear: () => void;
}

type Filter = "all" | LogEntry["type"];

export function LogPanel({ logs, onClear }: LogPanelProps) {
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = useMemo(() => {
    if (filter === "all") return logs;
    return logs.filter((l) => l.type === filter);
  }, [logs, filter]);

  return (
    <div className="border-t border-border bg-foreground-5/20">
      <div className="p-3 flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Logs</div>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as Filter)}
            className="text-xs px-2 py-1 rounded border border-border bg-background"
          >
            <option value="all">All</option>
            <option value="info">Info</option>
            <option value="success">Success</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="track">Track</option>
          </select>
          <button
            onClick={onClear}
            className="text-xs px-2 py-1 rounded border border-border hover:bg-foreground-5"
          >
            Clear
          </button>
        </div>
      </div>
      <div className="max-h-48 overflow-auto px-3 pb-3 space-y-1 text-xs">
        {filtered.length === 0 && (
          <div className="text-muted-foreground">No log entries yet.</div>
        )}
        {filtered.map((log, idx) => (
          <div key={idx} className="flex items-start gap-2">
            <span className="text-muted-foreground">[{log.timestamp.toLocaleTimeString()}]</span>
            <span
              className={
                log.type === "error"
                  ? "text-destructive"
                  : log.type === "warning"
                  ? "text-warning"
                  : log.type === "success"
                  ? "text-success"
                  : "text-foreground"
              }
            >
              {log.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
