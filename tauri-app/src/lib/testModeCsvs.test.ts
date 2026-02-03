import { describe, it, expect } from "vitest";
import { resolveTestCsvs } from "./testModeCsvs";

describe("resolveTestCsvs", () => {
  it("returns empty list when no dir set", async () => {
    const csvs = await resolveTestCsvs(null);
    expect(csvs).toEqual([]);
  });
});
