import { useState } from "react";
import { LogEntry } from "../lib/types";

export function createLogState(initial: LogEntry[] = []) {
  let logs = [...initial];
  const add = (type: LogEntry["type"], message: string) => {
    logs = [...logs, { type, message, timestamp: new Date() }];
  };
  const clear = () => {
    logs = [];
  };
  return {
    get logs() {
      return logs;
    },
    add,
    clear,
  };
}

export function useLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const add = (type: LogEntry["type"], message: string) => {
    setLogs((prev) => [...prev, { type, message, timestamp: new Date() }]);
  };

  const clear = () => setLogs([]);

  return { logs, add, clear };
}
