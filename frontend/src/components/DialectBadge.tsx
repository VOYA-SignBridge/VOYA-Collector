/**
 * One place that renders a dialect.
 *
 * Every page used to spell out its own `item.dialect === 'hoa-de' && <span
 * className="bg-purple-100 …">Hòa Đê</span>` chain. Six copies existed, they
 * disagreed with each other, and none of them could show a dialect approved
 * through the registry — a new one simply rendered as nothing at all.
 *
 * The colour is derived from the id instead of looked up, so a dialect nobody
 * has heard of still gets a stable, distinct chip the first time it appears.
 */

import { dialectLabel } from "../config/dialectLabels";

// Tailwind needs whole class names present in the source to emit them, so these
// are written out rather than composed from `bg-${hue}-100`.
//
// MIỄN TRỪ khỏi bảng màu trạng thái (`theme/status.ts`). Đây là bảng màu PHÂN
// LOẠI: mỗi phương ngữ nhận một sắc ổn định theo băm id, và giá trị của nó nằm
// ở chỗ các sắc PHÂN BIỆT được với nhau. Quy tất cả về xanh dương "thành công"
// sẽ xoá đúng tính chất đó — và một chip phương ngữ không nói điều gì "thành
// công" cả. Xanh lá ở đây không mang nghĩa trạng thái.
const PALETTE = [
  "bg-blue-100 text-blue-800",
  "bg-amber-100 text-amber-800",
  "bg-emerald-100 text-emerald-800",
  "bg-purple-100 text-purple-800",
  "bg-cyan-100 text-cyan-800",
  "bg-rose-100 text-rose-800",
  "bg-indigo-100 text-indigo-800",
  "bg-teal-100 text-teal-800",
];
const NEUTRAL = "bg-gray-100 text-gray-800";

/** Stable across reloads and machines — the same id always gets the same chip. */
function paletteFor(id: string): string {
  if (!id || id === "common") return NEUTRAL;
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export interface DialectBadgeProps {
  dialect?: string | null;
  /** `sm` matches the grid card, `md` the list row. */
  size?: "sm" | "md";
  className?: string;
}

export default function DialectBadge({ dialect, size = "sm", className = "" }: DialectBadgeProps) {
  const id = (dialect ?? "").trim();
  if (!id) return null;
  const dims =
    size === "md" ? "px-3 py-1 text-xs" : "px-2 py-0.5 text-[11px]";
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ${dims} ${paletteFor(id)} ${className}`}
      title={id}
    >
      {dialectLabel(id)}
    </span>
  );
}
