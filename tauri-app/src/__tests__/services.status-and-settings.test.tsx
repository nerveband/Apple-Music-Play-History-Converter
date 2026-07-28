import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ServicesSection } from "../components/sections/ServicesSection";
import type { SearchProvider } from "../lib/types";

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
    configureAppleMusic: vi.fn(async () => undefined),
    testAppleMusicCredentials: vi.fn(async () => undefined),
    getAppleMusicStatus: vi.fn(async () => undefined),
    getSettings: vi.fn(async () => undefined),
    setSettings: vi.fn(async () => undefined),
    checkItunesStatus: vi.fn(async () => undefined),
    checkMusicBrainzApiStatus: vi.fn(async () => undefined),
    checkAppleMusicApiStatus: vi.fn(async () => undefined),
    restartSidecar: vi.fn(async () => undefined),
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

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const renderServices = (provider: SearchProvider = "itunes") =>
  render(
    <ServicesSection
      expanded
      onToggle={vi.fn()}
      provider={provider}
      setProvider={vi.fn()}
      exportFormat="lastfm"
      setExportFormat={vi.fn()}
      isSearching={false}
    />
  );

describe("ServicesSection parity wiring", () => {
  beforeEach(() => {
    clearEventListeners();
    listenMock.mockClear();
    Object.values(commandMocks).forEach((mockFn) => mockFn.mockClear());
  });

  it("loads persisted settings on mount", async () => {
    renderServices();
    await waitFor(() => expect(commandMocks.getSettings).toHaveBeenCalledTimes(1));
  });

  it("auto-checks API statuses on mount", async () => {
    renderServices();

    // Auto-check fires on mount
    await waitFor(() => expect(commandMocks.checkItunesStatus).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(commandMocks.checkMusicBrainzApiStatus).toHaveBeenCalledTimes(1));
  });

  it("hydrates iTunes settings from settings_loaded events", async () => {
    renderServices("itunes");

    await waitFor(() => expect(listeners.size).toBeGreaterThan(0));

    act(() => {
      emitEvent("settings_loaded", {
        itunes_country: "jp",
        itunes_rate_limit: 37,
        rate_limit_paused: true,
      });
    });

    await waitFor(() => {
      const countrySelect = screen.getByRole("combobox") as HTMLSelectElement;
      expect(countrySelect.value).toBe("jp");
      expect(screen.getByDisplayValue("37")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Resume Rate Limiting" })).toBeTruthy();
    });
  });

  it("hydrates and applies an external app storage location", async () => {
    renderServices();
    await waitFor(() => expect(listeners.size).toBeGreaterThan(0));

    act(() => {
      emitEvent("settings_loaded", {
        storage_root: "/Volumes/ExternalSSD/AppleMusicConverter",
      });
    });

    const input = await screen.findByLabelText("App storage location");
    expect((input as HTMLInputElement).value).toBe("/Volumes/ExternalSSD/AppleMusicConverter");
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => {
      expect(commandMocks.setSettings).toHaveBeenCalledWith({
        storage_root: "/Volumes/ExternalSSD/AppleMusicConverter",
      });
      expect(commandMocks.restartSidecar).toHaveBeenCalledTimes(1);
    });
  });

  it("allows saving Apple Music config with shared proxy (default)", async () => {
    renderServices("apple_music");

    // Default mode is shared proxy with pre-filled URL
    fireEvent.click(screen.getByRole("button", { name: "Save & Enable" }));

    await waitFor(() =>
      expect(commandMocks.configureAppleMusic).toHaveBeenCalledWith(
        "",
        "",
        "",
        "https://am-proxy.wavedepth.workers.dev",
        "",
      )
    );
  });

  it("toggles export format sample output with info buttons", async () => {
    renderServices();

    expect(screen.queryByText("Sample Output (.csv)")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Show sample output for Last.fm CSV" }));
    expect(await screen.findByText("Sample Output (.csv)")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Hide sample output for Last.fm CSV" }));

    await waitFor(() => {
      expect(screen.queryByText("Sample Output (.csv)")).toBeNull();
    });
  });
});
