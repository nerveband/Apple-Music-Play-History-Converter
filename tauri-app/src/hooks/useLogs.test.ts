import { describe, it, expect } from "vitest";
import { createLogState } from "./useLogs";

describe("useLogs", () => {
  it("adds entries", () => {
    const state = createLogState();
    state.add("info", "hello");
    expect(state.logs.length).toBe(1);
  });
});
