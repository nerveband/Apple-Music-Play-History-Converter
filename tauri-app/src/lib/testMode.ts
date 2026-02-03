export function isTestMode(): boolean {
  return import.meta.env.VITE_TEST_MODE === "true";
}

export function testDataDir(): string | null {
  return import.meta.env.VITE_TEST_DATA_DIR || null;
}
