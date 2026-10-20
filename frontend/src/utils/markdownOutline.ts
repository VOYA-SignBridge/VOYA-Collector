/**
 * Mục lục của một văn bản markdown: tiêu đề → `id` để liên kết `#...`.
 *
 * Dùng chung bởi `components/Markdown` (gắn `id` lên `<h1..h3>`) và trang đọc
 * văn bản pháp lý (dựng mục lục bên cạnh). Hai bên phải sinh `id` bằng CÙNG
 * một hàm, cùng thứ tự — nếu không mục lục trỏ vào chỗ không có.
 *
 * Tiếng Việt có dấu: bỏ dấu bằng NFD rồi gạt tổ hợp dấu, `đ` → `d`. Trùng
 * tiêu đề (ví dụ hai mục "Phạm vi") thì thêm hậu tố `-2`, `-3`.
 */

export interface OutlineItem {
  level: 1 | 2 | 3;
  text: string;
  id: string;
}

/** Bỏ ký hiệu markdown inline đơn giản để lấy chữ thuần của tiêu đề. */
export function plainHeadingText(raw: string): string {
  return raw
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/\*([^*]*)\*/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .trim();
}

export function slugify(text: string): string {
  const s = plainHeadingText(text)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return s || "muc";
}

export function extractHeadings(markdown: string): OutlineItem[] {
  const seen = new Map<string, number>();
  const out: OutlineItem[] = [];
  for (const line of (markdown || "").replace(/\r\n/g, "\n").split("\n")) {
    const m = /^(#{1,6})\s+(.*)$/.exec(line);
    if (!m) continue;
    const level = Math.min(m[1].length, 3) as 1 | 2 | 3;
    const text = plainHeadingText(m[2]);
    const base = slugify(text);
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    out.push({ level, text, id: n === 1 ? base : `${base}-${n}` });
  }
  return out;
}
