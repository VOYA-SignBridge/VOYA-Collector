import type { ClassRow, Label } from "../types";

/** Catalog metadata only. Feature sequences belong in the personal NPZ bundle. */
export function catalogCSV(rows: Array<ClassRow | Label>): string {
  const columns = [...new Set([
    "class_uid", "class_idx", "label_original", "slug", "language", "dialect",
    ...rows.flatMap((row) => Object.keys(row)),
  ])];
  const cell = (value: unknown) => {
    const text = value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  return [columns.map(cell).join(","), ...rows.map((row) => {
    const record = row as unknown as Record<string, unknown>;
    return columns.map((key) => cell(record[key])).join(",");
  })].join("\r\n");
}
