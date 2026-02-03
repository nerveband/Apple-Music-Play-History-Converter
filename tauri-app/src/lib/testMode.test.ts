import { describe, it, expect } from "vitest";
import { isTestMode } from "./testMode";

describe("testMode", () => {
  it("defaults to false", () => {
    expect(isTestMode()).toBe(false);
  });
});
