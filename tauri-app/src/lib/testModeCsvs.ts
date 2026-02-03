export async function resolveTestCsvs(dir: string | null): Promise<string[]> {
  if (!dir) return [];
  const { readDir } = await import("@tauri-apps/plugin-fs");
  const entries = await readDir(dir);
  return entries
    .filter((e) => e.isFile && e.name?.toLowerCase().endsWith(".csv"))
    .map((e) => `${dir}/${e.name}`);
}
