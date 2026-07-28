import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import App from "../App";

const {
  listeners,
  listenMock,
  emitEvent,
  clearEventListeners,
  commandMocks,
} = vi.hoisted(() => {
  const eventListeners = new Map<string, Array<(event: { payload: unknown }) => void>>();

  const listen = vi.fn((eventName: string, cb: (event: { payload: unknown }) => void) => {
    const current = eventListeners.get(eventName) ?? [];
    current.push(cb);
    eventListeners.set(eventName, current);
    return Promise.resolve(() => {
      const next = (eventListeners.get(eventName) ?? []).filter((fn) => fn !== cb);
      eventListeners.set(eventName, next);
    });
  });

  const emit = (eventName: string, payload: unknown) => {
    for (const cb of eventListeners.get(eventName) ?? []) {
      cb({ payload });
    }
  };

  const clear = () => eventListeners.clear();

  const commands = {
    analyzeCsv: vi.fn(),
    clearResumeState: vi.fn(async () => undefined),
    getResumeState: vi.fn(async () => undefined),
    getSettings: vi.fn(async () => undefined),
    initializeSidecar: vi.fn(async () => undefined),
    openLogDir: vi.fn(async () => undefined),
    restartSidecar: vi.fn(async () => undefined),
    resumeSearch: vi.fn(async () => undefined),
  };

  return {
    listeners: eventListeners,
    listenMock: listen,
    emitEvent: emit,
    clearEventListeners: clear,
    commandMocks: commands,
  };
});

vi.mock("@tauri-apps/api/event", () => ({
  listen: listenMock,
}));

vi.mock("../lib/commands", () => commandMocks);

vi.mock("../hooks/useTauri", () => ({
  useTauri: () => true,
}));

vi.mock("../hooks/useSearch", () => ({
  useSearch: () => ({
    progress: null,
    isSearching: false,
    isPaused: false,
    logs: [],
    handleStatusChange: vi.fn(),
    resetProgress: vi.fn(),
    clearLogs: vi.fn(),
  }),
}));

vi.mock("../hooks/useResize", () => ({
  useResize: () => ({
    size: 280,
    collapsed: false,
    toggleCollapse: vi.fn(),
    handleMouseDown: vi.fn(),
  }),
}));

vi.mock("../components/FileSelection", () => ({
  FileSelection: () => <div data-testid="file-selection" />,
}));

vi.mock("../components/ResultsPanel", () => ({
  ResultsPanel: () => <div data-testid="results-panel" />,
}));

vi.mock("../components/ResultsTable", () => ({
  ResultsTable: () => <div data-testid="results-table" />,
}));

vi.mock("../components/PreviewTable", () => ({
  PreviewTable: () => <div data-testid="preview-table" />,
}));

vi.mock("../components/LogPanel", () => ({
  LogPanel: () => <div data-testid="log-panel" />,
}));

vi.mock("../components/Dialogs", () => ({
  Dialogs: () => null,
}));

vi.mock("../components/SettingsSidebar", () => ({
  SettingsSidebar: ({ provider }: { provider: string }) => (
    <div data-testid="settings-provider">{provider}</div>
  ),
}));

vi.mock("react-toastify", () => ({
  ToastContainer: () => null,
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

describe("App settings hydration", () => {
  beforeEach(() => {
    clearEventListeners();
    listenMock.mockClear();
    Object.values(commandMocks).forEach((mockFn) => mockFn.mockClear());

    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: "",
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it("requests persisted settings after sidecar initialization", async () => {
    render(<App />);

    await waitFor(() => expect(commandMocks.initializeSidecar).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(commandMocks.getResumeState).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(commandMocks.getSettings).toHaveBeenCalledTimes(1));
  });

  it("hydrates provider state from settings_loaded event", async () => {
    render(<App />);

    await waitFor(() => expect(listeners.size).toBeGreaterThan(0));
    act(() => {
      emitEvent("settings_loaded", { search_provider: "itunes" });
    });

    await waitFor(() => {
      expect(screen.getByTestId("settings-provider").textContent).toBe("itunes");
    });
  });

  it("shows a backend issue banner when startup fails", async () => {
    commandMocks.initializeSidecar.mockRejectedValueOnce(new Error("Bundled sidecar binary is missing"));

    render(<App />);

    expect(await screen.findByText("Backend Issue")).toBeTruthy();
    expect(screen.getByText(/Bundled sidecar binary is missing/)).toBeTruthy();
  });

  it("reloads resumable state and settings after a sidecar crash restart", async () => {
    render(<App />);
    await waitFor(() => expect(commandMocks.getResumeState).toHaveBeenCalledTimes(1));

    act(() => {
      emitEvent("sidecar_terminated", {});
    });

    await waitFor(() => expect(commandMocks.restartSidecar).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(commandMocks.getResumeState).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(commandMocks.getSettings).toHaveBeenCalledTimes(2));
  });
});
