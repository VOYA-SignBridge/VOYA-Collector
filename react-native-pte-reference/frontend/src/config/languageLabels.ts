/**
 * Tên hiển thị của mã ngôn ngữ trong bộ từ vựng.
 *
 * Dropdown ngôn ngữ ở trang Nhận dạng trước đây in thẳng mã thô ("vn", "en"),
 * trong khi Thư viện nhãn lại hiện "Tiếng Việt" / "English" — cùng dữ liệu, hai
 * cách đọc. Mã lạ trả về chính nó thay vì chuỗi rỗng.
 */

const LANGUAGE_LABELS: Record<string, string> = {
  vn: 'Tiếng Việt',
  vi: 'Tiếng Việt',
  en: 'English',
};

export function languageName(code?: string | null): string {
  if (!code) return '';
  return LANGUAGE_LABELS[code.toLowerCase()] ?? code;
}

export default LANGUAGE_LABELS;
