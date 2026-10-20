/**
 * How a dialect is written in the UI.
 *
 * The slug IS the display name. `hoa-de`, not `Hòa Đê`.
 *
 * Why: the slug is the identifier the rest of the system already uses — the
 * `dialect` column in dataset/samples.csv, the sample folder names, the
 * `model_id` served by /realtime/models, the checkpoint filenames. Showing a
 * translated label meant every screen needed a slug -> name map, and that map
 * was maintained by hand in two different files. They drifted: both listed
 * `ha-noi` and `saigon`, which have never had a single class or sample behind
 * them, while any dialect approved through POST /vocabulary/dialects could not
 * appear at all because nobody had added it to the map.
 *
 * With the slug on screen there is nothing to keep in sync: what the user reads
 * is what is in the CSV, and a newly approved dialect shows up correctly the
 * moment the registry returns it.
 *
 * `display_name` still exists in the registry and is still editable by an admin
 * — it is shown as secondary context on the admin screen, where renaming is the
 * whole point. It is deliberately not used for identification anywhere else.
 */

/** Canonical on-screen form of a dialect: the slug itself. */
export function dialectLabel(dialectId: string | null | undefined): string {
  const s = (dialectId ?? "").trim();
  return s.length > 0 ? s : "—";
}

/**
 * Slug plus the human name in parentheses, e.g. `hoa-de (Hòa Đê)`.
 * For admin screens where the human name is the thing being edited. Falls back
 * to the bare slug when there is no distinct name.
 */
export function dialectLabelWithName(
  dialectId: string | null | undefined,
  displayName?: string | null
): string {
  const slug = dialectLabel(dialectId);
  const name = (displayName ?? "").trim();
  if (!name || name === slug) return slug;
  return `${slug} (${name})`;
}

export default dialectLabel;
