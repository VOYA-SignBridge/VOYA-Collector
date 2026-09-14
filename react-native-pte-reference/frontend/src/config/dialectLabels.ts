// Centralized dialect display names.
// Add or update mappings here so UI components don't need edits when new dialects are added.
// Kept in sync with vocabulary schema v2 (docs/VOCABULARY_SCHEMA_V2.md):
// "bang-chu-cai" is the standalone alphabet group; regions display as "Miền ...".

const DIALECT_LABELS: Record<string, string> = {
  'common': 'Chung',
  'bang-chu-cai': 'Bảng chữ cái',
  'bac': 'Miền Bắc',
  'trung': 'Miền Trung',
  'nam': 'Miền Nam',
  'hoa-de': 'Hòa Đê',
  'can-tho': 'Cần Thơ',
  'spa': 'Spa',
  'ha-noi': 'Hà Nội',
  'saigon': 'Sài Gòn',

  // extend with any known dialect slugs
};

/**
 * Tên hiển thị của một phương ngữ.
 *
 * Trước đây mỗi màn hình tự chép bảng này (LabelsPage có bản riêng thiếu 4
 * slug, dropdown lọc lại hardcode danh sách thứ ba, còn Realtime với Bước 1 in
 * thẳng slug thô kiểu "bac"/"hoa-de"). Slug lạ trả về chính nó thay vì chuỗi
 * rỗng — thà hiện slug còn hơn hiện ô trống.
 */
export function dialectName(slug?: string | null): string {
  if (!slug) return DIALECT_LABELS.common;
  return DIALECT_LABELS[slug] ?? slug;
}

/** Màu badge theo phương ngữ, dùng chung cho mọi nơi hiển thị chip phương ngữ.
 *  Slug chưa biết vẫn có badge (màu trung tính) thay vì biến mất khỏi giao diện. */
const DIALECT_BADGE_CLASSES: Record<string, string> = {
  'common': 'bg-gray-100 text-gray-800',
  'bang-chu-cai': 'bg-indigo-100 text-indigo-800',
  'bac': 'bg-blue-100 text-blue-800',
  'trung': 'bg-emerald-100 text-emerald-800',
  'nam': 'bg-amber-100 text-amber-800',
  'hoa-de': 'bg-purple-100 text-purple-800',
  'can-tho': 'bg-cyan-100 text-cyan-800',
  'spa': 'bg-teal-100 text-teal-800',
  'ha-noi': 'bg-sky-100 text-sky-800',
  'saigon': 'bg-orange-100 text-orange-800',
};

export function dialectBadgeClass(slug?: string | null): string {
  if (!slug) return DIALECT_BADGE_CLASSES.common;
  return DIALECT_BADGE_CLASSES[slug] ?? 'bg-slate-100 text-slate-700';
}

/** Danh sách slug đã biết, dùng để dựng dropdown lọc. */
export const KNOWN_DIALECT_SLUGS = Object.keys(DIALECT_LABELS);

export default DIALECT_LABELS;
